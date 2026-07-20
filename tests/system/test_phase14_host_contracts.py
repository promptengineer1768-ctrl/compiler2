"""Host-side Phase 14 preparation contracts that do not require VICE.

These checks inventory the keyword matrix / mode-runner surface and the dual
REU placement records so Wave-3 readiness can be audited without claiming
emulator E2E green.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import generate_expansion_contracts  # noqa: E402
import validate_build  # noqa: E402
from e2e.keyword_matrix import expand_cells, load_matrix  # noqa: E402


@pytest.mark.system
def test_keyword_matrix_inventory_is_loadable_and_grouped() -> None:
    """The Phase 14 keyword matrix must expand into group1-3 cells with modes."""
    document = load_matrix()
    cases = document["cases"]
    assert isinstance(cases, list) and cases
    cells = expand_cells()
    assert cells
    groups = {cell["group"] for cell in cells}
    modes = {cell["mode"] for cell in cells}
    assert groups >= {"group1"}
    assert modes <= {"immediate", "program", "compile"}
    assert modes & {"immediate", "program", "compile"}

    implemented = [cell for cell in cells if cell["product_status"] == "implemented"]
    # Inventory only: product E2E may still be incomplete; report counts for baseline.
    inventory = {
        "total_cells": len(cells),
        "implemented_cells": len(implemented),
        "groups": sorted(groups),
        "modes": sorted(modes),
    }
    assert inventory["total_cells"] > 0
    # Do not require VICE; do require a stable catalog shape for T14.9 prep.
    for cell in cells:
        assert cell["case_id"]
        assert cell["keyword"]
        assert cell["profile"] in {"basicv2", "basicv35", "ieee"}
        assert cell["mode"] in {"immediate", "program", "compile"}


@pytest.mark.system
def test_mode_runner_modules_are_importable() -> None:
    """Shared mode/product runners must exist for Phase 14 keyword slices."""
    from e2e import mode_runner, product_runner  # noqa: F401

    assert hasattr(mode_runner, "get_runner_for_mode") or hasattr(
        mode_runner, "run_mode"
    ) or callable(mode_runner)
    assert product_runner is not None


@pytest.mark.system
def test_expansion_contracts_are_truthful_and_dual_recorded() -> None:
    """Release REU layout remains patch-only while dual records cover geoRAM pages."""
    errors = validate_build.validate_expansion_contracts(ROOT / "build")
    assert errors == []

    reu_layout = json.loads((ROOT / "build" / "reu_layout.json").read_text())
    assert reu_layout["implementation_status"] == (
        generate_expansion_contracts.IMPLEMENTATION_STATUS
    )
    assert reu_layout["overlays"] == []
    assert reu_layout["slot_classes"] == []
    assert reu_layout["routine_record_count"] == len(reu_layout["routine_records"])
    assert reu_layout["routine_record_count"] > 0
    for record in reu_layout["routine_records"]:
        assert record["reu"]["execution_status"] == "not_live"
        assert record["reu"]["image_length"] == 256
        assert record["reu"]["slot_origin"] == "$CE00"


@pytest.mark.system
def test_pre_migration_baseline_tool_is_runnable() -> None:
    """T14.3 capture tool must load and produce a schema-versioned report."""
    import capture_pre_migration_baseline as baseline

    report = baseline.capture(ROOT)
    assert report["schema_version"] == 1
    assert report["status"] in {"ready", "stale", "missing", "unbuildable"}
    assert "keyword_matrix" in report
    assert report["e2e_execution"]["status"] == "not_captured"
