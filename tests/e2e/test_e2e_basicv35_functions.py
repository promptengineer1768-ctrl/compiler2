"""BASIC V3.5 E2E function tests.

Covers every BASIC V3.5 function/structured-control keyword across immediate,
program, and compile modes.  Fixture-backed cases assert Plus/4 VICE semantics.
Pending cases hold the catalog entry until VICE capture.
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
            "keyword": "DO",
            "mode": "immediate",
            "vice_pending": False,
            "fixture_id": "basicv35-immediate-DO",
        },
        marks=pytest.mark.immediate,
        id="immediate-DO",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "LOOP",
            "mode": "program",
            "vice_pending": False,
            "fixture_id": "basicv35-program-LOOP",
        },
        marks=pytest.mark.program,
        id="program-LOOP",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "EXIT DO",
            "mode": "compile",
            "vice_pending": False,
            "fixture_id": "basicv35-program-EXIT_DO",
        },
        marks=pytest.mark.compile,
        id="compile-EXIT_DO",
    ),
    # --- Pending VICE capture ---
    # DO / LOOP conditional forms
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "DO WHILE",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-DO_WHILE",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "DO WHILE",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-DO_WHILE",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "DO UNTIL",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-DO_UNTIL",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "DO UNTIL",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-DO_UNTIL",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "LOOP WHILE",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-LOOP_WHILE",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "LOOP WHILE",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-LOOP_WHILE",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "LOOP UNTIL",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-LOOP_UNTIL",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "LOOP UNTIL",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-LOOP_UNTIL",
    ),
    # EXIT (bare)
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "EXIT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-EXIT",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "EXIT",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-EXIT",
    ),
    # WHILE keyword used with DO
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "WHILE",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-WHILE",
    ),
    # UNTIL keyword used with LOOP
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
    # ELSE used with IF
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
    # DO immediate mode
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "DO",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-DO",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "DO",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-DO",
    ),
    # LOOP immediate mode
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "LOOP",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-LOOP",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "LOOP",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-LOOP",
    ),
    # EXIT DO immediate mode
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "EXIT DO",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-EXIT_DO",
    ),
    pytest.param(
        {
            "profile": "basicv35",
            "keyword": "EXIT DO",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-EXIT_DO",
    ),
)

_FIXTURE_SCENARIOS = SCENARIOS[:3]
_PENDING_SCENARIOS = SCENARIOS[3:]


@pytest.mark.smoke
@pytest.mark.parametrize("scenario", _FIXTURE_SCENARIOS)
def test_function_catalog_scaffold(scenario: dict[str, object]) -> None:
    """The BASIC V3.5 function matrix is represented before fixture capture."""
    assert scenario["profile"] == "basicv35"
    assert scenario["mode"] in {"immediate", "program", "compile"}
    assert scenario["vice_pending"] is False


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_function_reference_fixture(scenario: dict[str, object]) -> None:
    """Every catalog entry resolves to a captured Plus/4 observation."""
    fixture = assert_fixture_backed(scenario)
    assert "?LOOP WITHOUT DO ERROR" not in fixture["normalized_result"]


@pytest.mark.parametrize("scenario", _PENDING_SCENARIOS)
def test_function_execution_fixture(scenario: dict[str, object]) -> None:
    """Every function/mode combination has executable fixture coverage."""
    assert_fixture_backed(scenario)
