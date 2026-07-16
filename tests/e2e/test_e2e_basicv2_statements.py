"""BASIC V2 E2E statement tests.

Covers every BASIC V2 statement keyword across immediate, program, and compile
modes.  Fixture-backed cases (vice_pending=False) assert stock VICE semantics.
Pending cases (vice_pending=True) hold the catalog entry until VICE capture.
"""

from __future__ import annotations

import pytest

from tests.e2e.scenario_fixtures import assert_fixture_backed

pytestmark = [pytest.mark.e2e, pytest.mark.basicv2]

# ---------------------------------------------------------------------------
# Scenario catalog
# Fixture-backed entries come first (vice_pending=False).
# ---------------------------------------------------------------------------

SCENARIOS = (
    # --- Captured reference fixtures ---
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "PRINT",
            "mode": "immediate",
            "vice_pending": False,
            "fixture_id": "basicv2-immediate-PRINT",
        },
        marks=pytest.mark.immediate,
        id="immediate-PRINT",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "FOR",
            "mode": "program",
            "vice_pending": False,
            "fixture_id": "basicv2-program-FOR",
        },
        marks=pytest.mark.program,
        id="program-FOR",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "GOTO",
            "mode": "compile",
            "vice_pending": False,
            "fixture_id": "basicv2-program-GOTO",
        },
        marks=pytest.mark.compile,
        id="compile-GOTO",
    ),
    # --- Pending VICE capture ---
    # CLOSE
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "CLOSE",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-CLOSE",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "CLOSE",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-CLOSE",
    ),
    # CLR (immediate only)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "CLR",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-CLR",
    ),
    # CMD
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "CMD",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-CMD",
    ),
    # CONT (immediate only)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "CONT",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-CONT",
    ),
    # DATA
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "DATA",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-DATA",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "DATA",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-DATA",
    ),
    # DEF FN
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "DEF",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-DEF",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "DEF",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-DEF",
    ),
    # DIM
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "DIM",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-DIM",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "DIM",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-DIM",
    ),
    # END
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "END",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-END",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "END",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-END",
    ),
    # FOR (additional modes beyond the fixture)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "FOR",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FOR",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "FOR",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-FOR",
    ),
    # GET
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "GET",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-GET",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "GET",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-GET",
    ),
    # GOSUB
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "GOSUB",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-GOSUB",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "GOSUB",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-GOSUB",
    ),
    # GOTO (additional modes)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "GOTO",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-GOTO",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "GOTO",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-GOTO",
    ),
    # IF / THEN
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "IF",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-IF",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "IF",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-IF",
    ),
    # INPUT
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "INPUT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-INPUT",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "INPUT",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-INPUT",
    ),
    # INPUT#
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "INPUT#",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-INPUT_hash",
    ),
    # LET
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LET",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-LET",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LET",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-LET",
    ),
    # LIST (immediate only)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LIST",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-LIST",
    ),
    # LOAD (immediate only)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LOAD",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-LOAD",
    ),
    # NEW (immediate only)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "NEW",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-NEW",
    ),
    # NEXT
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "NEXT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-NEXT",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "NEXT",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-NEXT",
    ),
    # ON GOTO / ON GOSUB
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ON",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ON",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ON",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-ON",
    ),
    # OPEN
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "OPEN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-OPEN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "OPEN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-OPEN",
    ),
    # POKE
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "POKE",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-POKE",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "POKE",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-POKE",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "POKE",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-POKE",
    ),
    # PRINT (additional modes)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "PRINT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-PRINT",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "PRINT",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-PRINT",
    ),
    # PRINT#
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "PRINT#",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-PRINT_hash",
    ),
    # READ
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "READ",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-READ",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "READ",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-READ",
    ),
    # REM
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "REM",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-REM",
    ),
    # RESTORE
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RESTORE",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-RESTORE",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RESTORE",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-RESTORE",
    ),
    # RETURN
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RETURN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-RETURN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RETURN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-RETURN",
    ),
    # RUN (immediate only)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RUN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-RUN",
    ),
    # SAVE (immediate only)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SAVE",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-SAVE",
    ),
    # STOP
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "STOP",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-STOP",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "STOP",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-STOP",
    ),
    # SYS
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SYS",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-SYS",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SYS",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-SYS",
    ),
    # VERIFY (immediate only)
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "VERIFY",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-VERIFY",
    ),
    # WAIT
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "WAIT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-WAIT",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "WAIT",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-WAIT",
    ),
)

# Split fixture-backed from pending for targeted parametrization
_FIXTURE_SCENARIOS = SCENARIOS[:3]
_PENDING_SCENARIOS = SCENARIOS[3:]


@pytest.mark.smoke
@pytest.mark.parametrize("scenario", _FIXTURE_SCENARIOS)
def test_statement_catalog_scaffold(scenario: dict[str, object]) -> None:
    """The smoke modes resolve to captured stock VICE observations."""
    assert scenario["profile"] == "basicv2"
    assert scenario["mode"] in {"immediate", "program", "compile"}
    assert scenario["keyword"] in {"PRINT", "FOR", "GOTO"}
    assert scenario["vice_pending"] is False
    assert_fixture_backed(scenario)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_statement_reference_fixture(scenario: dict[str, object]) -> None:
    """Every catalog entry resolves to a captured stock VICE observation."""
    assert_fixture_backed(scenario)


@pytest.mark.parametrize("scenario", _PENDING_SCENARIOS)
def test_statement_execution_fixture(scenario: dict[str, object]) -> None:
    """Every statement/mode combination has executable fixture coverage."""
    assert_fixture_backed(scenario)
