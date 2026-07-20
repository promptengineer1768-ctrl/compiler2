"""Installed-editor VICE acceptance test for Noel's Retro Lab benchmark.

This deliberately exercises stored source and ``RUN`` only.  It must never be
replaced with an exported PRG or the historical hand-authored native fixture.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.e2e.product_runner import run_product_cell
from tools.e2e_evidence import release_preflight

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "performance" / "noels_retro_lab_cbm_v2.bas"
EXPECTED_SUM = 500500
STOCK_C64_NTSC_JIFFIES = 2388


@pytest.fixture(name="vice_port")
def _vice_port_fixture(request: pytest.FixtureRequest) -> int:
    """Allocate a stable, low-collision VICE monitor port for this test."""
    if "unique_vice_port" in request.fixturenames:
        return int(request.getfixturevalue("unique_vice_port"))
    return 6900 + abs(hash(request.node.nodeid)) % 100


def _benchmark_cell() -> dict[str, object]:
    """Return the exact stored-source case consumed by the product runner."""
    return {
        "cell_id": "basicv2-program-noels-retro-lab",
        "profile": "basicv2",
        "mode": "program",
        "source_lines": SOURCE.read_text(encoding="ascii").splitlines(),
    }


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.vice
@pytest.mark.hardware
@pytest.mark.georam
@pytest.mark.basicv2
@pytest.mark.program
@pytest.mark.timeout(420)
def test_noels_retro_lab_runs_in_memory_from_installed_editor(
    vice_port: int,
) -> None:
    """Enter Noel unchanged, RUN it in memory, and enforce result/timing."""
    errors = release_preflight(ROOT / "build")
    assert not errors, "fresh release artifact required before Noel E2E:\n" + "\n".join(
        errors
    )

    observation = run_product_cell(_benchmark_cell(), port=vice_port)
    actual = str(observation["actual"])
    assert "S" in actual, f"benchmark start marker missing:\n{observation['screen']}"
    assert "." * 10 in actual, f"expected ten progress dots:\n{observation['screen']}"
    assert str(EXPECTED_SUM) in actual, f"sum mismatch:\n{observation['screen']}"
    timing = re.search(
        r"TIME:\s*(?:\d+(?:\.\d+)?)\s*SECONDS,\s*JIFFIES:\s*(\d+)", actual
    )
    assert timing, f"benchmark timing was not printed:\n{observation['screen']}"
    jiffies = int(timing.group(1))
    assert jiffies < STOCK_C64_NTSC_JIFFIES, (
        f"Noel benchmark took {jiffies} jiffies; expected faster than the "
        f"{STOCK_C64_NTSC_JIFFIES}-jiffy stock C64 BASIC V2 baseline"
    )
