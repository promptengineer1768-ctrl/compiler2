"""Capture reproducible pre-migration evidence without accepting stale builds."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

import yaml

REQUIRED_ARTIFACTS = (
    "build_manifest.json",
    "size_report.json",
    "compiler.bin",
    "georam.bin",
    "basicv3.prg",
    "compiler.map",
    "compiler.lbl",
    "compiler.d64",
    "keyword_lookup_report.json",
)
SOURCE_INPUTS = (
    "src",
    "manifests",
    "tools",
    "docs",
    "build.ps1",
    "REQUIREMENTS.md",
    "DESIGN2.md",
    "REU_REQUIREMENTS.md",
    "REU_DESIGN.md",
)


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest for one file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_files(root: Path) -> list[Path]:
    """Return the build inputs whose modification time establishes freshness."""
    files: list[Path] = []
    for relative in SOURCE_INPUTS:
        path = root / relative
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file())
    return files


def _artifact_status(build_dir: Path) -> dict[str, Any]:
    """Check manifest-declared artifact bytes without invoking a toolchain."""
    manifest_path = build_dir / "build_manifest.json"
    missing = [name for name in REQUIRED_ARTIFACTS if not (build_dir / name).is_file()]
    result: dict[str, Any] = {
        "manifest": "missing",
        "missing": missing,
        "mismatched": [],
    }
    if not manifest_path.is_file():
        return result
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = manifest["artifacts"]
        if not isinstance(records, dict):
            raise ValueError("artifacts is not an object")
    except (json.JSONDecodeError, KeyError, OSError, ValueError, TypeError) as error:
        result["manifest"] = "invalid"
        result["error"] = str(error)
        return result

    result["manifest"] = "valid"
    for name, record in sorted(records.items()):
        path = build_dir / name
        if not path.is_file():
            if name not in result["missing"]:
                result["missing"].append(name)
            continue
        if not isinstance(record, dict):
            result["mismatched"].append(f"{name}: invalid manifest record")
            continue
        if record.get("size") != path.stat().st_size:
            result["mismatched"].append(f"{name}: size")
        if record.get("sha256") != _sha256(path):
            result["mismatched"].append(f"{name}: sha256")
    result["missing"].sort()
    return result


def _size_status(build_dir: Path) -> dict[str, Any]:
    """Return the linked memory totals and any failed budget gates."""
    path = build_dir / "size_report.json"
    if not path.is_file():
        return {"status": "missing"}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"status": "invalid", "error": str(error)}
    gates = {
        name: report.get(name)
        for name in (
            "resident_within_limit",
            "georam_within_limit",
            "compile_within_limit",
        )
    }
    failed = sorted(name for name, value in gates.items() if value is not True)
    return {
        "status": "valid" if not failed else "failed_budget",
        "gates": gates,
        "failed_gates": failed,
        "totals": {
            name: report.get(name)
            for name in ("resident_bytes", "georam_pages", "compile_bytes")
        },
    }


def _keyword_matrix_status(root: Path) -> dict[str, Any]:
    """Summarize catalog cells and oracle availability for E2E baseline evidence."""
    matrix = root / "tests" / "e2e" / "cases" / "keyword_matrix.yaml"
    if not matrix.is_file():
        return {"status": "missing"}
    try:
        document = yaml.safe_load(matrix.read_text(encoding="utf-8"))
        cases = document["cases"]
        if not isinstance(cases, list):
            raise ValueError("cases is not a list")
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        return {"status": "invalid", "error": str(error)}

    by_group: dict[str, dict[str, int]] = {}
    total = implemented = cells_with_oracle = 0
    fixture_root = root / "tests" / "fixtures" / "reference"
    profiles = {
        "basicv2": "c64_basicv2",
        "basicv35": "plus4_basicv35",
        "ieee": "ieee_oracle",
    }
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("keyword matrix case is not an object")
        group = str(case.get("group", "ungrouped"))
        bucket = by_group.setdefault(
            group, {"cells": 0, "implemented": 0, "with_oracle": 0}
        )
        fixture_ids = case.get("fixture_id_by_mode") or {}
        expected = case.get("expected_result_by_mode") or {}
        for mode in case.get("modes") or []:
            total += 1
            bucket["cells"] += 1
            status = case.get("product_status", "not_implemented")
            allowed = case.get("product_modes")
            if status == "implemented" and (allowed is None or mode in allowed):
                implemented += 1
                bucket["implemented"] += 1
            fixture_id = fixture_ids.get(mode) or (
                fixture_ids.get("program") if mode == "compile" else None
            )
            has_oracle = case.get("oracle", "stock") == "project" and (
                expected.get(mode) is not None
                or (mode == "compile" and expected.get("program") is not None)
            )
            directory = profiles.get(str(case.get("profile")))
            if not has_oracle and fixture_id and directory:
                fixture = fixture_root / directory / f"{fixture_id}.json"
                try:
                    has_oracle = (
                        json.loads(fixture.read_text(encoding="utf-8")).get(
                            "normalization_rules"
                        )
                        != "catalog-v1"
                    )
                except (OSError, json.JSONDecodeError, TypeError):
                    has_oracle = False
            if has_oracle:
                cells_with_oracle += 1
                bucket["with_oracle"] += 1
    return {
        "status": "valid",
        "total_cells": total,
        "implemented_cells": implemented,
        "cells_with_oracle": cells_with_oracle,
        "cells_missing_oracle": total - cells_with_oracle,
        "by_group": by_group,
    }


def capture(root: Path, build_dir: Path | None = None) -> dict[str, Any]:
    """Capture baseline status for one workspace without rebuilding it.

    Args:
        root: Workspace root containing source inputs and tests.
        build_dir: Build artifact directory. Defaults to ``root / 'build'``.

    Returns:
        JSON-serializable evidence. ``status`` is ready, stale, missing, or
        unbuildable; consumers must reject every status other than ready.
    """
    root = root.resolve()
    build_dir = (build_dir or root / "build").resolve()
    artifacts = _artifact_status(build_dir)
    size = _size_status(build_dir)
    keyword_matrix = _keyword_matrix_status(root)
    source_files = _source_files(root)
    manifest = build_dir / "build_manifest.json"
    newest_source = max(
        (item.stat().st_mtime_ns for item in source_files), default=None
    )
    stale = bool(
        manifest.is_file()
        and newest_source is not None
        and newest_source > manifest.stat().st_mtime_ns
    )
    if artifacts["missing"] or artifacts["manifest"] == "missing":
        status = "missing"
    elif (
        artifacts["manifest"] != "valid"
        or artifacts["mismatched"]
        or size["status"] != "valid"
    ):
        status = "unbuildable"
    elif stale:
        status = "stale"
    else:
        status = "ready"
    return {
        "schema_version": 1,
        "status": status,
        "build_dir": str(build_dir),
        "artifact_integrity": artifacts,
        "source_freshness": {
            "status": "stale" if stale else "current",
            "tracked_source_files": len(source_files),
        },
        "size_report": size,
        "keyword_matrix": keyword_matrix,
        "e2e_execution": {
            "status": "not_captured",
            "reason": (
                "This read-only capture does not infer VICE execution from catalog "
                "or artifact presence. Record a separate real E2E result before "
                "declaring a migration baseline verified."
            ),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Write baseline evidence and return nonzero when it is not usable."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = capture(args.root, args.build_dir)
    output = args.output or args.root / "build" / "pre_migration_baseline.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {output}")
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
