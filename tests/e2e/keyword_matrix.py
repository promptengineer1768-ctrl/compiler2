"""Keyword E2E matrix catalog loader and cell expansion."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Iterator, Literal

import yaml

ROOT: Final = Path(__file__).resolve().parents[2]
MATRIX_PATH: Final = ROOT / "tests" / "e2e" / "cases" / "keyword_matrix.yaml"
FIXTURE_ROOT: Final = ROOT / "tests" / "fixtures" / "reference"
PROFILE_DIRS: Final = {
    "basicv2": "c64_basicv2",
    "basicv35": "plus4_basicv35",
    "ieee": "ieee_oracle",
}

Mode = Literal["immediate", "program", "compile"]
Group = Literal["group1", "group2", "group3"]


def load_matrix() -> dict[str, Any]:
    """Load the keyword matrix YAML document."""
    data = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "cases" not in data:
        raise ValueError(f"invalid keyword matrix: {MATRIX_PATH}")
    return data


def expand_cells(
    *,
    group: Group | None = None,
    mode: Mode | None = None,
    product_status: str | None = None,
    only_with_oracle: bool = False,
) -> list[dict[str, Any]]:
    """Expand catalog cases into one cell per (case, mode).

    Each cell is a flat dict suitable for pytest parametrization and runners.
    """
    doc = load_matrix()
    cells: list[dict[str, Any]] = []
    for case in doc["cases"]:
        if group is not None and case.get("group") != group:
            continue
        modes: list[str] = list(case.get("modes") or [])
        for m in modes:
            if mode is not None and m != mode:
                continue
            if product_status is not None and case.get("product_status") != product_status:
                continue
            fixture_map = case.get("fixture_id_by_mode") or {}
            source_map = case.get("source_by_mode") or {}
            expected_map = case.get("expected_result_by_mode") or {}
            # compile reuses program oracle / source when omitted
            fixture_id = fixture_map.get(m)
            if fixture_id is None and m == "compile":
                fixture_id = fixture_map.get("program")
            source_lines = source_map.get(m)
            if source_lines is None and m == "compile":
                source_lines = source_map.get("program")
            expected = expected_map.get(m)
            if expected is None and m == "compile":
                expected = expected_map.get("program")
            # Optional product_modes restricts which modes run product tests when
            # product_status is implemented (e.g. immediate-only until program entry
            # is stable). Do not shadow the product_status filter parameter.
            product_modes = case.get("product_modes")
            cell_product_status = case.get("product_status", "not_implemented")
            if (
                cell_product_status == "implemented"
                and product_modes is not None
                and m not in product_modes
            ):
                cell_product_status = "not_implemented"
            cell = {
                "cell_id": f"{case['id']}-{m}",
                "case_id": case["id"],
                "group": case["group"],
                "profile": case["profile"],
                "keyword": case["keyword"],
                "mode": m,
                "applicability": case.get("applicability", "required"),
                "oracle": case.get("oracle", "stock"),
                "product_status": cell_product_status,
                "fixture_id": fixture_id,
                "source_lines": list(source_lines or []),
                "expected_result": expected,
                "reference_mode": "program" if m == "compile" else m,
            }
            if only_with_oracle and not cell_has_oracle(cell):
                continue
            cells.append(cell)
    return cells


def cell_has_oracle(cell: dict[str, Any]) -> bool:
    """Return True when a stock or project expected result is available."""
    if cell.get("oracle") == "project":
        return cell.get("expected_result") is not None
    fixture_id = cell.get("fixture_id")
    if not fixture_id:
        return False
    profile = str(cell["profile"])
    directory = PROFILE_DIRS.get(profile)
    if not directory:
        return False
    path = FIXTURE_ROOT / directory / f"{fixture_id}.json"
    if not path.exists():
        return False
    # Reject catalog placeholders
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("normalization_rules") != "catalog-v1"
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def iter_fixture_capture_jobs(group: Group = "group1") -> Iterator[dict[str, Any]]:
    """Yield unique stock fixture capture jobs for a group.

    compile mode shares program fixtures, so it is not double-captured.
    """
    seen: set[str] = set()
    for cell in expand_cells(group=group):
        if cell.get("oracle") != "stock":
            continue
        if cell["mode"] == "compile":
            continue  # reuse program fixture
        fixture_id = cell.get("fixture_id")
        if not fixture_id or fixture_id in seen:
            continue
        seen.add(fixture_id)
        yield {
            "case_id": fixture_id,
            "profile": cell["profile"],
            "reference_mode": cell["reference_mode"],
            "source_lines": tuple(cell["source_lines"]),
            "keyword": cell["keyword"],
            "group": cell["group"],
            "matrix_case_id": cell["case_id"],
        }


def coverage_report(group: Group | None = None) -> dict[str, Any]:
    """Summarize matrix oracle and product readiness."""
    cells = expand_cells(group=group)
    summary = {
        "total_cells": len(cells),
        "with_oracle": 0,
        "missing_oracle": 0,
        "implemented": 0,
        "not_implemented": 0,
        "by_mode": {},
    }
    for cell in cells:
        mode = cell["mode"]
        summary["by_mode"].setdefault(mode, {"total": 0, "oracle": 0, "implemented": 0})
        summary["by_mode"][mode]["total"] += 1
        if cell_has_oracle(cell):
            summary["with_oracle"] += 1
            summary["by_mode"][mode]["oracle"] += 1
        else:
            summary["missing_oracle"] += 1
        if cell["product_status"] == "implemented":
            summary["implemented"] += 1
            summary["by_mode"][mode]["implemented"] += 1
        else:
            summary["not_implemented"] += 1
    return summary


def release_readiness_errors(group: Group) -> list[str]:
    """Return release-blocking gaps for required keyword-matrix cells.

    A catalog row is planning data, not executable coverage. A release claim
    requires every required cell in its priority group to have a deterministic
    oracle and an implemented product path.
    """
    errors: list[str] = []
    for cell in expand_cells(group=group):
        if cell.get("applicability") != "required":
            continue
        if not cell_has_oracle(cell):
            errors.append(f"{cell['cell_id']}: missing deterministic oracle")
        if cell.get("product_status") != "implemented":
            errors.append(
                f"{cell['cell_id']}: product status is {cell['product_status']!r}"
            )
    return errors
