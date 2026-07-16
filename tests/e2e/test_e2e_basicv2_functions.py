"""BASIC V2 E2E function tests.

Covers every BASIC V2 function keyword across immediate, program, and compile
modes.  Fixture-backed cases (vice_pending=False) assert stock VICE semantics.
Pending cases (vice_pending=True) hold the catalog entry until VICE capture.
"""

from __future__ import annotations

import pytest

from tests.e2e.scenario_fixtures import assert_fixture_backed

pytestmark = [pytest.mark.e2e, pytest.mark.basicv2]

# ---------------------------------------------------------------------------
# Scenario catalog
# Each entry: profile, keyword, mode, vice_pending, (fixture_id if not pending)
# ---------------------------------------------------------------------------

SCENARIOS = (
    # --- Captured reference fixtures (vice_pending=False) ---
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SGN",
            "mode": "immediate",
            "vice_pending": False,
            "fixture_id": "basicv2-immediate-SGN",
        },
        marks=pytest.mark.immediate,
        id="immediate-SGN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ASC",
            "mode": "program",
            "vice_pending": False,
            "fixture_id": "basicv2-program-ASC",
        },
        marks=pytest.mark.program,
        id="program-ASC",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SPC",
            "mode": "compile",
            "vice_pending": False,
            "fixture_id": "basicv2-program-SPC",
        },
        marks=pytest.mark.compile,
        id="compile-SPC",
    ),
    # --- Pending VICE capture ---
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ABS",
            "mode": "immediate",
            "vice_pending": False,
            "fixture_id": "basicv2-immediate-ABS",
        },
        marks=pytest.mark.immediate,
        id="immediate-ABS",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ABS",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ABS",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ABS",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-ABS",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ATN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-ATN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ATN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ATN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ATN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-ATN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "CHR$",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-CHR_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "CHR$",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-CHR_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "CHR$",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-CHR_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "COS",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-COS",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "COS",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-COS",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "COS",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-COS",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "EXP",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-EXP",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "EXP",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-EXP",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "EXP",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-EXP",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "FRE",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FRE",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "FRE",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-FRE",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "INT",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-INT",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "INT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-INT",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "INT",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-INT",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LEFT$",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-LEFT_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LEFT$",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-LEFT_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LEFT$",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-LEFT_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LEN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-LEN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LEN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-LEN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LEN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-LEN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LOG",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-LOG",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LOG",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-LOG",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "LOG",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-LOG",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "MID$",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-MID_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "MID$",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-MID_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "MID$",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-MID_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "PEEK",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-PEEK",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "PEEK",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-PEEK",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "PEEK",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-PEEK",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "POS",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-POS",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "POS",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-POS",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RIGHT$",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-RIGHT_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RIGHT$",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-RIGHT_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RIGHT$",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-RIGHT_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RND",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-RND",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RND",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-RND",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "RND",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-RND",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SIN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-SIN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SIN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-SIN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SIN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-SIN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SQR",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-SQR",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SQR",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-SQR",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SQR",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-SQR",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ST",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-ST",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ST",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ST",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "STR$",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-STR_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "STR$",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-STR_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "STR$",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-STR_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "TAB",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-TAB",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "TAB",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-TAB",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "TAN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-TAN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "TAN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-TAN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "TAN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-TAN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "TI$",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-TI_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "TI$",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-TI_dollar",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "USR",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-USR",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "VAL",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-VAL",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "VAL",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-VAL",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "VAL",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-VAL",
    ),
    # DEF FN / FN invocation
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "FN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-FN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "FN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-FN",
    ),
    # SPC is already covered by the fixture-backed compile-SPC above.
    # ASC immediate mode
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ASC",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-ASC",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "ASC",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-ASC",
    ),
    # SGN program and compile modes
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SGN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-SGN",
    ),
    pytest.param(
        {
            "profile": "basicv2",
            "keyword": "SGN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-SGN",
    ),
)


@pytest.mark.smoke
@pytest.mark.parametrize("scenario", SCENARIOS[:3])
def test_function_catalog_scaffold(scenario: dict[str, object]) -> None:
    """The smoke modes resolve to captured stock VICE observations."""
    assert scenario["profile"] == "basicv2"
    assert scenario["mode"] in {"immediate", "program", "compile"}
    assert scenario["keyword"] in {"SGN", "ASC", "SPC"}
    assert scenario["vice_pending"] is False
    assert_fixture_backed(scenario)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_function_reference_fixture(scenario: dict[str, object]) -> None:
    """Every catalog entry resolves to a captured stock VICE observation."""
    assert_fixture_backed(scenario)


@pytest.mark.parametrize("scenario", SCENARIOS[3:])
def test_function_execution_fixture(scenario: dict[str, object]) -> None:
    """Every function/mode combination has executable fixture coverage."""
    assert_fixture_backed(scenario)
