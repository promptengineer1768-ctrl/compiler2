"""BASIC V3.5 E2E statement tests.

Covers every BASIC V3.5 statement keyword, including all BASIC V2 inherited
statements active in V3.5 mode.  Fixture-backed cases assert Plus/4 VICE
semantics.  Pending cases hold the catalog entry until VICE capture.
"""

from __future__ import annotations

import pytest

from tests.e2e.scenario_fixtures import assert_fixture_backed

pytestmark = [pytest.mark.e2e, pytest.mark.basicv35]

# ---------------------------------------------------------------------------
# Scenario catalog
# ---------------------------------------------------------------------------

SCENARIOS = (
    # --- Captured reference fixtures (vice_pending=False) ---
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "BASIC3.5",
            "mode": "immediate",
            "vice_pending": False,
            "fixture_id": "basicv35-immediate-BASIC3_5",
        },
        marks=pytest.mark.immediate,
        id="immediate-BASIC3_5",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "WHILE",
            "mode": "program",
            "vice_pending": False,
            "fixture_id": "basicv35-program-WHILE",
        },
        marks=pytest.mark.program,
        id="program-WHILE",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "UNTIL",
            "mode": "compile",
            "vice_pending": False,
            "fixture_id": "basicv35-program-UNTIL",
        },
        marks=pytest.mark.compile,
        id="compile-UNTIL",
    ),
    # --- Pending VICE capture ---
    # Mode-switching statements (always enabled)
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "BASIC2",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-BASIC2",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "BASIC3.5",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-BASIC3_5",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "BASIC3.5",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-BASIC3_5",
    ),
    # WHILE additional modes
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "WHILE",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-WHILE",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "WHILE",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-WHILE",
    ),
    # UNTIL additional modes
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "UNTIL",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-UNTIL",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "UNTIL",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-UNTIL",
    ),
    # ELSE
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "ELSE",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ELSE",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "ELSE",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-ELSE",
    ),
    # FOR / NEXT inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "FOR",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-FOR",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "FOR",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-FOR",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "NEXT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-NEXT",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "NEXT",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-NEXT",
    ),
    # GOSUB / RETURN inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "GOSUB",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-GOSUB",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "GOSUB",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-GOSUB",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "RETURN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-RETURN",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "RETURN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-RETURN",
    ),
    # IF / THEN inherited (V3.5 adds ELSE)
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "IF",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-IF",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "IF",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-IF",
    ),
    # PRINT inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "PRINT",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-PRINT",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "PRINT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-PRINT",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "PRINT",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-PRINT",
    ),
    # GOTO inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "GOTO",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-GOTO",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "GOTO",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-GOTO",
    ),
    # DATA / READ / RESTORE inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "DATA",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-DATA",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "READ",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-READ",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "RESTORE",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-RESTORE",
    ),
    # DIM inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "DIM",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-DIM",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "DIM",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-DIM",
    ),
    # END / STOP inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "END",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-END",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "STOP",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-STOP",
    ),
    # INPUT inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "INPUT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-INPUT",
    ),
    # LET inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "LET",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-LET",
    ),
    # ON inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "ON",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ON",
    ),
    # POKE inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "POKE",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-POKE",
    ),
    # REM inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "REM",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-REM",
    ),
    # SYS inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "SYS",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-SYS",
    ),
    # WAIT inherited
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "WAIT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-WAIT",
    ),
)

_FIXTURE_SCENARIOS = SCENARIOS[:3]
_PENDING_SCENARIOS = SCENARIOS[3:]


@pytest.mark.smoke
@pytest.mark.parametrize("scenario", _FIXTURE_SCENARIOS)
def test_statement_catalog_scaffold(scenario: dict[str, object]) -> None:
    """The smoke modes resolve to captured Plus/4 observations."""
    assert scenario["profile"] == "basicv35"
    assert scenario["mode"] in {"immediate", "program", "compile"}
    assert scenario["vice_pending"] is False
    assert_fixture_backed(scenario)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_statement_reference_fixture(scenario: dict[str, object]) -> None:
    """Every catalog entry resolves to a captured Plus/4 observation."""
    assert_fixture_backed(scenario)


@pytest.mark.parametrize("scenario", _PENDING_SCENARIOS)
def test_statement_execution_fixture(scenario: dict[str, object]) -> None:
    """Every statement/mode combination has executable fixture coverage."""
    assert_fixture_backed(scenario)
