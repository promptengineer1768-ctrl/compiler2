"""Add @pytest.mark.callable_coverage decorators to test functions.

For each uncovered routine, scan all test_*.py files using AST. When a string
literal matching an uncovered routine name appears inside a test function body,
add the decorator before the function definition.

Idempotent: skips functions already decorated for a given routine.
Detects the actual executor used by the test function body.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests" / "unit"
COVERAGE_PATH = ROOT / "build" / "test_coverage.json"


def load_uncovered_routines() -> list[str]:
    data = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    return data.get("uncovered_routines", [])


def has_callable_coverage_for(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef, name: str
) -> bool:
    for decorator in func_node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        func = decorator.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "callable_coverage"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "mark"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "pytest"
        ):
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                if decorator.args[0].value == name:
                    return True
    return False


def collect_string_literals(node: ast.expr) -> set[str]:
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            found.add(child.value)
    return found


def detect_executor(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Detect which executor the function body calls.

    Returns the executor name that should be used in the decorator.
    Recognises direct calls and common wrapper patterns.
    """
    for child in ast.walk(func_node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        # Direct calls: execute_rts(...), execute(...), _execute_routine(...)
        if isinstance(func, ast.Name):
            if func.id in {"execute_rts", "_execute_routine"}:
                return "execute_rts"
            if func.id == "execute":
                return "execute"
            # Common wrapper patterns - these all call emu.execute() internally
            if func.id in {"_call", "_execute", "_run_paged", "_invoke",
                           "_run_xip", "_execute_xip_no_args"}:
                return "execute"
        # Method calls: emu.execute_rts(...), emu.execute(...)
        if isinstance(func, ast.Attribute):
            if func.attr in {"execute_rts", "_execute_routine"}:
                return "execute_rts"
            if func.attr == "execute":
                return "execute"
    return None


def process_file(path: Path, uncovered: set[str], dry_run: bool = False) -> dict[str, list[str]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    source = raw.decode("utf-8")
    tree = ast.parse(source, filename=str(path))

    results: dict[str, tuple[int, list[str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue

        all_strings: set[str] = set()
        all_strings.update(collect_string_literals(node))
        for decorator in node.decorator_list:
            all_strings.update(collect_string_literals(decorator))

        matched = all_strings & uncovered
        matched = {n for n in matched if not has_callable_coverage_for(node, n)}
        if matched:
            results[node.name] = (node.lineno, sorted(matched))

    if not results or dry_run:
        return {k: v[1] for k, v in results.items()}

    sorted_funcs = sorted(results.items(), key=lambda x: x[1][0], reverse=True)

    line_ending = "\r\n" if "\r\n" in source else "\n"
    lines = source.split(line_ending)

    for func_name, (def_lineno, names) in sorted_funcs:
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                func_node = node
                break
        if not func_node:
            continue

        executor = detect_executor(func_node)
        if executor is None:
            # Function doesn't execute any routine - skip it
            continue

        if func_node.decorator_list:
            insert_before_line = func_node.decorator_list[0].lineno - 1
            target_line = lines[func_node.decorator_list[0].lineno - 1]
        else:
            insert_before_line = func_node.lineno - 1
            target_line = lines[func_node.lineno - 1]

        indent = ""
        for ch in target_line:
            if ch in (" ", "\t"):
                indent += ch
            else:
                break

        for name in sorted(names):
            decorator_line = f'{indent}@pytest.mark.callable_coverage("{name}", executor="{executor}")'
            lines.insert(insert_before_line, decorator_line)

    for line in lines:
        stripped = line.strip()
        if stripped == "import pytest" or stripped.startswith("from pytest"):
            break
    else:
        last_import_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                last_import_idx = i
        lines.insert(last_import_idx + 1, "import pytest")

    new_source = line_ending.join(lines)
    path.write_bytes(new_source.encode("utf-8"))
    return {k: v[1] for k, v in results.items()}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    uncovered_list = load_uncovered_routines()
    uncovered = set(uncovered_list)
    print(f"Uncovered routines: {len(uncovered)}")

    test_files = sorted(TESTS_DIR.glob("test_*.py"))
    total_added = 0
    for path in test_files:
        results = process_file(path, uncovered, dry_run=args.dry_run)
        if results:
            added = sum(len(v) for v in results.values())
            total_added += added
            action = "Would add" if args.dry_run else "Added"
            print(f"  {action} {added} decorator(s) in {path.name}:")
            for fname, names in results.items():
                print(f"    {fname}: {names}")
    print(f"\nTotal decorators added: {total_added}")


if __name__ == "__main__":
    main()
