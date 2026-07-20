"""Test harness runner and traceability matrix generator.

Provides coverage verification and generates requirements matrix reports.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any, Sequence


def collect_assembly_entries(
    production_entries_path: str,
    test_entries_path: str,
    covered_entries: set[str] | None = None,
) -> dict[str, Any]:
    """Build the callable assembly coverage matrix.

    Args:
        production_entries_path: Generated production entry manifest.
        test_entries_path: Generated test-only entry manifest.
        covered_entries: Entry names observed in direct unit coverage.

    Returns:
        Matrix containing every callable and uncovered names.
    """
    covered = covered_entries or set()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path, key, kind in (
        (production_entries_path, "production_entries", "production"),
        (test_entries_path, "test_entries", "test_only"),
    ):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for entry in data.get(key, []):
            name = str(entry["name"])
            if name in seen:
                raise ValueError(f"duplicate callable entry: {name}")
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "kind": kind,
                    "module": str(entry["module"]),
                    "covered": name in covered,
                }
            )
    rows.sort(key=lambda row: str(row["name"]))
    return {
        "entries": rows,
        "uncovered": [str(row["name"]) for row in rows if not bool(row["covered"])],
    }


def collect_covered_entries(tests_dir: str, entry_names: set[str]) -> set[str]:
    """Return entries backed by explicit production-byte test evidence.

    A name appearing in a test's prose, fixture, or assertion is not evidence
    that the assembled entry was executed.  Direct callable coverage is
    therefore opt-in: a test must use ``pytest.mark.callable_coverage`` and
    name the helper which performs the linked-byte invocation.  The marked
    test must actually call that helper.

    Args:
        tests_dir: Directory containing direct unit tests.
        entry_names: Callable names allowed by the generated entry manifests.

    Returns:
        Callable names with at least one structurally valid execution claim.
    """
    return set(collect_callable_execution_evidence(tests_dir, entry_names))


def collect_callable_execution_evidence(
    tests_dir: str, entry_names: set[str]
) -> dict[str, list[dict[str, str]]]:
    """Collect explicit direct-execution claims from unit-test ASTs.

    The accepted form is ``@pytest.mark.callable_coverage("entry",
    executor="_call")`` on a test function whose body calls ``_call``.  This
    gate is deliberately conservative: it rejects the old name-search scheme
    and records evidence locations for later runtime instrumentation.

    Args:
        tests_dir: Directory containing direct unit tests.
        entry_names: Callable names allowed by the generated entry manifests.

    Returns:
        Mapping from callable name to deterministic evidence records.
    """
    evidence: dict[str, list[dict[str, str]]] = {}
    for path in sorted(Path(tests_dir).rglob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except SyntaxError as error:
            raise ValueError(f"cannot inspect callable coverage: {path}: {error}") from error
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                claim = _callable_coverage_claim(decorator)
                if claim is None:
                    continue
                name, executor = claim
                if name not in entry_names:
                    raise ValueError(
                        f"callable coverage names unknown entry '{name}' in {path}:{node.lineno}"
                    )
                if not _function_calls_name(node, executor):
                    raise ValueError(
                        f"callable coverage for '{name}' in {path}:{node.lineno} "
                        f"does not call executor '{executor}'"
                    )
                evidence.setdefault(name, []).append(
                    {
                        "test": f"{path.as_posix()}::{node.name}",
                        "executor": executor,
                        "kind": "declared_direct_execution",
                    }
                )
    return {name: evidence[name] for name in sorted(evidence)}


def _callable_coverage_claim(decorator: ast.expr) -> tuple[str, str] | None:
    """Parse one explicit ``pytest.mark.callable_coverage`` decorator."""
    if not isinstance(decorator, ast.Call) or len(decorator.args) != 1:
        return None
    function = decorator.func
    if not (
        isinstance(function, ast.Attribute)
        and function.attr == "callable_coverage"
        and isinstance(function.value, ast.Attribute)
        and function.value.attr == "mark"
        and isinstance(function.value.value, ast.Name)
        and function.value.value.id == "pytest"
        and isinstance(decorator.args[0], ast.Constant)
        and isinstance(decorator.args[0].value, str)
    ):
        return None
    executor = next(
        (
            keyword.value.value
            for keyword in decorator.keywords
            if keyword.arg == "executor"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ),
        None,
    )
    if not executor:
        raise ValueError("callable_coverage requires executor='direct_call_helper'")
    return decorator.args[0].value, executor


def _function_calls_name(node: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    """Return whether a function body directly calls a named executor."""
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == name
        for child in ast.walk(node)
    )


def validate_callable_coverage(
    production_entries_path: str,
    test_entries_path: str,
    tests_dir: str,
    output_path: str,
) -> dict[str, Any]:
    """Generate the callable matrix and expose missing direct unit coverage."""
    names: set[str] = set()
    for path, key in (
        (production_entries_path, "production_entries"),
        (test_entries_path, "test_entries"),
    ):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        names.update(str(entry["name"]) for entry in data.get(key, []))
    evidence = collect_callable_execution_evidence(tests_dir, names)
    matrix = collect_assembly_entries(
        production_entries_path,
        test_entries_path,
        set(evidence),
    )
    report = {
        "schema_version": "2.0",
        "total_routines": len(matrix["entries"]),
        "covered_routines": len(matrix["entries"]) - len(matrix["uncovered"]),
        "uncovered_routines": matrix["uncovered"],
        "entries": matrix["entries"],
        "evidence": evidence,
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def replay_boundary(boundary_path: str) -> dict[str, Any]:
    """Validate and replay a serialized compilation boundary.

    Args:
        boundary_path: JSON boundary record containing version, state, and CRC32.

    Returns:
        A copy of the validated serialized state.

    Raises:
        ValueError: If the version or checksum is invalid.
    """
    record = json.loads(Path(boundary_path).read_text(encoding="utf-8"))
    if record.get("version") != 1:
        raise ValueError(f"unsupported boundary version: {record.get('version')}")
    state = record.get("state")
    if not isinstance(state, dict):
        raise ValueError("boundary state must be an object")
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    expected = f"{zlib.crc32(encoded):08x}"
    if record.get("crc32") != expected:
        raise ValueError("boundary checksum mismatch")
    return dict(state)


def _run_pytest(arguments: Sequence[str], cwd: str | None = None) -> int:
    """Run pytest with a stable interpreter and return its exit status."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", *arguments],
        cwd=cwd,
        check=False,
    ).returncode


def run_smoke_selection(test_path: str = "tests", cwd: str | None = None) -> int:
    """Run the authoritative smoke selection."""
    return _run_pytest((test_path, "-m", "smoke"), cwd)


def run_full_selection(
    test_path: str = "tests",
    selection: str | None = None,
    cwd: str | None = None,
) -> int:
    """Run the full suite or a caller-provided pytest expression."""
    arguments = [test_path]
    if selection:
        arguments.extend(["-k", selection])
    return _run_pytest(arguments, cwd)


def generate_requirements_matrix(
    trace_path: str, output_json: str, output_md: str
) -> None:
    """Generates the requirements traceability reports.

    Args:
        trace_path: Path to traceability.json.
        output_json: Path to save JSON report.
        output_md: Path to save Markdown report.
    """
    if not os.path.exists(trace_path):
        return

    with open(trace_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", [])
    mapped_tests: dict[str, list[str]] = {}
    for record in records:
        requirement_id = str(record["id"])
        for test_name in record.get("tests", []):
            mapped_tests.setdefault(str(test_name), []).append(requirement_id)

    # Write requirements_matrix.json
    matrix_data = {
        "valid": True,
        "requirements_count": len(records),
        "tests_count": len(mapped_tests),
        "mapped_requirements": [
            {
                "id": r["id"],
                "ears": r["ears"],
                "source_section": r["source_section"],
                "design_section": r["design_section"],
                "implementation": r["implementation"],
                "tests": r["tests"],
                "status": r["status"],
                **(
                    {"reference_fixture_provenance": r["reference_fixture_provenance"]}
                    if "reference_fixture_provenance" in r
                    else {}
                ),
            }
            for r in records
        ],
        "mapped_tests": [
            {
                "test": test_name,
                "requirements": sorted(requirement_ids),
            }
            for test_name, requirement_ids in sorted(mapped_tests.items())
        ],
    }

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(matrix_data, f, indent=2)

    # Write requirements_matrix.md
    md_lines = [
        "# Requirements Traceability Matrix",
        "",
        "| Requirement ID | EARS Requirement | Source Section | Design Section | Implementation | Test Nodes | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in records:
        tests_str = ", ".join(f"`{t}`" for t in r["tests"])
        md_lines.append(
            f"| `{r['id']}` | {r['ears']} | `{r['source_section']}` | "
            f"`{r['design_section']}` | `{r['implementation']}` | {tests_str} | "
            f"{r['status']} |"
        )
    md_lines.extend(
        [
            "",
            "## Test-to-Requirement Index",
            "",
            "| Test Node | Requirement IDs |",
            "|---|---|",
        ]
    )
    for test_name, requirement_ids in sorted(mapped_tests.items()):
        reqs = ", ".join(f"`{req_id}`" for req_id in sorted(requirement_ids))
        md_lines.append(f"| `{test_name}` | {reqs} |")

    with open(output_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")


def _generate_reference(profile: str) -> int:
    """Generate stock VICE fixtures for one BASIC profile."""
    generator = Path(__file__).with_name("generate_vice_fixtures.py")
    return subprocess.run(
        [sys.executable, str(generator), "--profile", profile],
        check=False,
    ).returncode


def main() -> int:
    """Main execution entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-reference", choices=("basicv2", "basicv35"))
    parser.add_argument("--validate-coverage", action="store_true")
    args = parser.parse_args()

    if args.generate_reference is not None:
        return _generate_reference(args.generate_reference)

    if args.validate_coverage:
        report = validate_callable_coverage(
            "build/production_entries.json",
            "build/test_entries.json",
            "tests/unit",
            "build/test_coverage.json",
        )
        uncovered = report["uncovered_routines"]
        if uncovered:
            print(
                f"Callable coverage incomplete: {len(uncovered)} of "
                f"{report['total_routines']} entries lack direct unit coverage."
            )
            for name in uncovered:
                print(f"  {name}")
            return 1
        print(f"Callable coverage complete: {report['total_routines']} entries.")
        return 0

    trace_path = "manifests/traceability.json"
    output_json = "build/requirements_matrix.json"
    output_md = "build/requirements_matrix.md"

    generate_requirements_matrix(trace_path, output_json, output_md)
    print("Requirements matrix generated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
