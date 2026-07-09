"""BASIC V3 IEEE extension function tests.

Covers every IEEE 754 function keyword.  All cases are pending VICE oracle
capture since no stock VICE machine implements IEEE extensions.
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
            "keyword": "FPMODE()",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FPMODE_query",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPFLAGS",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-FPFLAGS",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "BIN32$",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-BIN32",
    ),
    # --- Full IEEE function catalog ---
    # FPCLR
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
    # FPFLAGS additional modes
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPFLAGS",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FPFLAGS",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPFLAGS",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-FPFLAGS",
    ),
    # FPSET
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
    # FPTEST / FPTTEST
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
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPTTEST",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FPTTEST",
    ),
    # FPMODE() additional modes
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPMODE()",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-FPMODE_query",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FPMODE()",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-FPMODE_query",
    ),
    # ISNAN
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISNAN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-ISNAN",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISNAN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ISNAN",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISNAN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-ISNAN",
    ),
    # ISSNAN
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISSNAN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-ISSNAN",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISSNAN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ISSNAN",
    ),
    # ISINF
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISINF",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-ISINF",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISINF",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ISINF",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISINF",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-ISINF",
    ),
    # ISFIN
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISFIN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-ISFIN",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISFIN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ISFIN",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISFIN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-ISFIN",
    ),
    # ISNORM
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISNORM",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-ISNORM",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISNORM",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ISNORM",
    ),
    # ISZERO
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISZERO",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-ISZERO",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISZERO",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ISZERO",
    ),
    # SGNBIT
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "SGNBIT",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-SGNBIT",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "SGNBIT",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-SGNBIT",
    ),
    # ISUNORD
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISUNORD",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-ISUNORD",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "ISUNORD",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-ISUNORD",
    ),
    # COPYSGN
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "COPYSGN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-COPYSGN",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "COPYSGN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-COPYSGN",
    ),
    # TOTALORDER
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "TOTALORDER",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-TOTALORDER",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "TOTALORDER",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-TOTALORDER",
    ),
    # BIN32$ additional modes
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "BIN32$",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-BIN32",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "BIN32$",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-BIN32",
    ),
    # VAL32
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "VAL32",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-VAL32",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "VAL32",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-VAL32",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "VAL32",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-VAL32",
    ),
    # FMA
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "FMA",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-FMA",
    ),
    pytest.param(
        {"profile": "ieee", "keyword": "FMA", "mode": "program", "vice_pending": True},
        marks=pytest.mark.program,
        id="program-FMA",
    ),
    pytest.param(
        {"profile": "ieee", "keyword": "FMA", "mode": "compile", "vice_pending": True},
        marks=pytest.mark.compile,
        id="compile-FMA",
    ),
    # REMAIN
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "REMAIN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-REMAIN",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "REMAIN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-REMAIN",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "REMAIN",
            "mode": "compile",
            "vice_pending": True,
        },
        marks=pytest.mark.compile,
        id="compile-REMAIN",
    ),
    # MIN
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "MIN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-MIN",
    ),
    pytest.param(
        {"profile": "ieee", "keyword": "MIN", "mode": "program", "vice_pending": True},
        marks=pytest.mark.program,
        id="program-MIN",
    ),
    pytest.param(
        {"profile": "ieee", "keyword": "MIN", "mode": "compile", "vice_pending": True},
        marks=pytest.mark.compile,
        id="compile-MIN",
    ),
    # MAX
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "MAX",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-MAX",
    ),
    pytest.param(
        {"profile": "ieee", "keyword": "MAX", "mode": "program", "vice_pending": True},
        marks=pytest.mark.program,
        id="program-MAX",
    ),
    pytest.param(
        {"profile": "ieee", "keyword": "MAX", "mode": "compile", "vice_pending": True},
        marks=pytest.mark.compile,
        id="compile-MAX",
    ),
    # SCALB
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "SCALB",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-SCALB",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "SCALB",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-SCALB",
    ),
    # LOGB
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "LOGB",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-LOGB",
    ),
    pytest.param(
        {"profile": "ieee", "keyword": "LOGB", "mode": "program", "vice_pending": True},
        marks=pytest.mark.program,
        id="program-LOGB",
    ),
    # MANT
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "MANT",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-MANT",
    ),
    pytest.param(
        {"profile": "ieee", "keyword": "MANT", "mode": "program", "vice_pending": True},
        marks=pytest.mark.program,
        id="program-MANT",
    ),
    # RINT
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "RINT",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-RINT",
    ),
    pytest.param(
        {"profile": "ieee", "keyword": "RINT", "mode": "program", "vice_pending": True},
        marks=pytest.mark.program,
        id="program-RINT",
    ),
    pytest.param(
        {"profile": "ieee", "keyword": "RINT", "mode": "compile", "vice_pending": True},
        marks=pytest.mark.compile,
        id="compile-RINT",
    ),
    # NEXTUP
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "NEXTUP",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-NEXTUP",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "NEXTUP",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-NEXTUP",
    ),
    # NEXTDOWN
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "NEXTDOWN",
            "mode": "immediate",
            "vice_pending": True,
        },
        marks=pytest.mark.immediate,
        id="immediate-NEXTDOWN",
    ),
    pytest.param(
        {
            "profile": "ieee",
            "keyword": "NEXTDOWN",
            "mode": "program",
            "vice_pending": True,
        },
        marks=pytest.mark.program,
        id="program-NEXTDOWN",
    ),
)

_SCAFFOLD_SCENARIOS = SCENARIOS[:3]
_PENDING_SCENARIOS = SCENARIOS[3:]


@pytest.mark.smoke
@pytest.mark.parametrize("scenario", _SCAFFOLD_SCENARIOS)
def test_function_catalog_scaffold(scenario: dict[str, object]) -> None:
    """The IEEE function matrix is represented before fixture capture."""
    assert scenario["profile"] == "ieee"
    assert scenario["mode"] in {"immediate", "program", "compile"}
    assert_fixture_backed(scenario)


@pytest.mark.parametrize("scenario", _SCAFFOLD_SCENARIOS)
def test_function_execution_fixture(scenario: dict[str, object]) -> None:
    """IEEE oracle fixture covers this slice."""
    assert_fixture_backed(scenario)


@pytest.mark.parametrize("scenario", _PENDING_SCENARIOS)
def test_function_full_catalog_fixture(scenario: dict[str, object]) -> None:
    """Full IEEE function catalog is backed by oracle fixtures."""
    assert_fixture_backed(scenario)
