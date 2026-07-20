"""Keyword E2E matrix: catalog integrity, stock oracles, product execution.

Priority order (from the matrix groups):

1. Capture stock VICE reference observations for the group.
2. Run product tests in immediate, then program, then compile mode.
3. Advance to the next group only after oracles and product coverage exist.

Group 1 focuses on numeric vars, LET/assignment, loops, string assignment,
TI/TI$/ST, PRINT, and BASIC dialect commands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.e2e.keyword_matrix import (
    cell_has_oracle,
    coverage_report,
    expand_cells,
    load_matrix,
    release_readiness_errors,
)
from tests.e2e.product_runner import compare_to_oracle, run_product_cell

ROOT = Path(__file__).resolve().parents[2]
DISK = ROOT / "build" / "compiler.d64"

pytestmark = [pytest.mark.e2e]

_MODE_ORDER = ("immediate", "program", "compile")


def _mode_sort_key(cell: dict[str, Any]) -> tuple[int, str]:
    mode = str(cell["mode"])
    try:
        index = _MODE_ORDER.index(mode)
    except ValueError:
        index = 99
    return (index, str(cell["cell_id"]))


# ---------------------------------------------------------------------------
# Catalog integrity (host-only, no VICE)
# ---------------------------------------------------------------------------


def test_keyword_matrix_loads() -> None:
    """Matrix YAML is well-formed and has group1 cases."""
    doc = load_matrix()
    assert "cases" in doc
    groups = {c["group"] for c in doc["cases"]}
    assert "group1" in groups
    cells = expand_cells(group="group1")
    assert len(cells) >= 10
    report = coverage_report("group1")
    assert report["total_cells"] == len(cells)


def test_group1_cells_have_source_and_modes() -> None:
    """Every group1 cell has source lines and a known mode."""
    for cell in expand_cells(group="group1"):
        assert cell["mode"] in _MODE_ORDER
        assert cell["source_lines"], f"{cell['cell_id']} missing source"
        if cell["oracle"] == "stock":
            assert cell["fixture_id"], f"{cell['cell_id']} missing fixture_id"


def test_group1_oracle_presence_report() -> None:
    """Required group1 cells need reviewed, deterministic reference oracles."""
    missing = [
        c["cell_id"]
        for c in expand_cells(group="group1")
        if c["applicability"] == "required" and not cell_has_oracle(c)
    ]
    assert not missing, "group1 required cells lack oracles: " + ", ".join(missing)


def test_group1_matrix_is_release_ready() -> None:
    """Pending or blocked required cells cannot masquerade as E2E coverage."""
    assert release_readiness_errors("group1") == []


# ---------------------------------------------------------------------------
# Product E2E (VICE + release disk)
# ---------------------------------------------------------------------------


def _product_cells(
    *,
    group: str = "group1",
    mode: str | None = None,
    only_implemented: bool = True,
) -> list[dict[str, Any]]:
    """Cells eligible for product execution, ordered by mode priority."""
    cells = expand_cells(group=group, mode=mode)  # type: ignore[arg-type]
    if only_implemented:
        cells = [c for c in cells if c.get("product_status") == "implemented"]
    # Require an oracle for deterministic compare; project oracles count.
    ready = []
    for cell in cells:
        if cell.get("oracle") == "project":
            if cell.get("expected_result") is not None:
                ready.append(cell)
            continue
        if cell_has_oracle(cell):
            ready.append(cell)
    ready.sort(key=_mode_sort_key)
    return ready


def _product_params(mode: str) -> list[Any]:
    cells = _product_cells(mode=mode, only_implemented=True)
    if not cells:
        return [
            pytest.param(
                {},
                id=f"no-implemented-{mode}",
                marks=[
                    getattr(pytest.mark, mode),
                    pytest.mark.skip(reason=f"no implemented group1 {mode} cells yet"),
                ],
            )
        ]
    return [
        pytest.param(cell, id=str(cell["cell_id"]), marks=getattr(pytest.mark, mode))
        for cell in cells
    ]


@pytest.mark.vice
@pytest.mark.hardware
@pytest.mark.georam
@pytest.mark.basicv3
@pytest.mark.timeout(1900)
@pytest.mark.parametrize("cell", _product_params("immediate"))
def test_group1_product_immediate(cell: dict[str, Any], vice_port: int) -> None:
    """Group1 product path: immediate mode against stock/project oracles."""
    _run_and_compare(cell, port=vice_port)


@pytest.mark.vice
@pytest.mark.hardware
@pytest.mark.georam
@pytest.mark.basicv3
@pytest.mark.timeout(1900)
@pytest.mark.parametrize("cell", _product_params("program"))
def test_group1_product_program(cell: dict[str, Any], vice_port: int) -> None:
    """Group1 product path: program mode against stock oracles."""
    _run_and_compare(cell, port=vice_port)


@pytest.mark.vice
@pytest.mark.hardware
@pytest.mark.georam
@pytest.mark.basicv3
@pytest.mark.timeout(1900)
@pytest.mark.parametrize("cell", _product_params("compile"))
def test_group1_product_compile(cell: dict[str, Any], vice_port: int) -> None:
    """Group1 product path: compile mode (reuses program stock oracle)."""
    _run_and_compare(cell, port=vice_port)


def _run_and_compare(cell: dict[str, Any], *, port: int) -> None:
    if not DISK.exists():
        pytest.skip(f"missing release disk: {DISK}")
    # basicv35 product path is not yet the default boot image.
    if cell.get("profile") == "basicv35":
        pytest.skip("basicv35 product profile not yet on C64 release image")
    observation = run_product_cell(cell, port=port)
    result = compare_to_oracle(cell, observation["actual"])
    if result["passed"] is None:
        pytest.skip(f"oracle not ready: {result['detail']}")
    assert result["passed"], (
        f"{cell['cell_id']} mismatch ({result['detail']})\n"
        f"expected_core:\n{result['expected_core']!r}\n"
        f"actual_core:\n{result['actual_core']!r}\n"
        f"screen:\n{observation['screen']}"
    )


# Optional fixture: unique port per test when available via conftest.
# Fall back to a high port if no fixture is defined.
@pytest.fixture(name="vice_port")
def _vice_port_fixture(request: pytest.FixtureRequest) -> int:
    """Prefer a project-wide unique port fixture; else allocate a fixed base."""
    if "unique_vice_port" in request.fixturenames:
        return int(request.getfixturevalue("unique_vice_port"))
    # Derive a stable-ish port from the node id hash to reduce collisions
    # when users run multiple workers (best-effort; sequential is preferred).
    base = 6700
    digest = abs(hash(request.node.nodeid)) % 200
    return base + digest
