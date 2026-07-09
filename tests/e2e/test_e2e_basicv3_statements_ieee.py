"""BASIC V3 IEEE extension statement tests.

Covers every IEEE 754 statement keyword.  All cases are pending oracle capture.
"""

from __future__ import annotations

import pytest

from tests.e2e.scenario_fixtures import assert_fixture_backed

pytestmark = [pytest.mark.e2e, pytest.mark.basicv3, pytest.mark.ieee]

# ---------------------------------------------------------------------------
# Scenario catalog — all pending until IEEE oracle is defined
# ---------------------------------------------------------------------------

SCENARIOS = (
    # --- Existing scaffolding entries (kept for smoke) ---
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPMODE0",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FPMODE0",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPMODE1",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-FPMODE1",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPSET",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-FPSET",
    ),
    # --- Full IEEE statement catalog ---
    # FPMODE0 additional modes
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPMODE0",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-FPMODE0",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPMODE0",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-FPMODE0",
    ),
    # FPMODE1 additional modes
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPMODE1",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FPMODE1",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPMODE1",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-FPMODE1",
    ),
    # FPSET additional modes
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPSET",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FPSET",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPSET",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-FPSET",
    ),
    # FPCLR as a statement
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPCLR",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FPCLR",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPCLR",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-FPCLR",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPCLR",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-FPCLR",
    ),
    # FPTEST as a statement
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPTEST",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FPTEST",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPTEST",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-FPTEST",
    ),
    # FPMODE0/FPMODE1 round-trip (mode-switch semantics)
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPMODE0-after-FPMODE1",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FPMODE0_after_FPMODE1",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPMODE1-after-FPMODE0",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FPMODE1_after_FPMODE0",
    ),
)

_SCAFFOLD_SCENARIOS = SCENARIOS[:3]
_PENDING_SCENARIOS = SCENARIOS[3:]


@pytest.mark.smoke
@pytest.mark.parametrize("scenario", _SCAFFOLD_SCENARIOS)
def test_statement_catalog_scaffold(scenario: dict[str, object]) -> None:
    """The IEEE statement matrix is represented before fixture capture."""
    assert scenario["profile"] == "ieee"
    assert scenario["mode"] in {"immediate", "program", "compile"}
    assert_fixture_backed(scenario)


@pytest.mark.parametrize("scenario", _SCAFFOLD_SCENARIOS)
def test_statement_execution_fixture(scenario: dict[str, object]) -> None:
    """IEEE oracle fixture covers this slice."""
    assert_fixture_backed(scenario)


@pytest.mark.parametrize("scenario", _PENDING_SCENARIOS)
def test_statement_full_catalog_fixture(scenario: dict[str, object]) -> None:
    """Full IEEE statement catalog is backed by oracle fixtures."""
    assert_fixture_backed(scenario)
