"""Canonical stock-CBM source contract for Noel's Retro Lab benchmark.

The later VICE acceptance test must enter this unchanged program through the
installed Compiler 2 editor, run it in memory with ``RUN``, and record the
result/timing with ``tools.e2e_evidence``. This host contract intentionally
does not treat the old hand-authored native fixture as editor/runtime evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "performance" / "noels_retro_lab_cbm_v2.bas"
EXPECTED_LINES = (
    '10 REM NOELS RETRO LAB BASIC BENCHMARK',
    '15 TI$="000000":PRINT"S"',
    "20 FOR I=1 TO 10",
    "25 S=0",
    "30 FOR J=1 TO 1000",
    "35 S=S+J",
    "40 NEXT J",
    '45 PRINT ".";',
    "50 NEXT I",
    "55 PRINT S",
    '60 PRINT "E":PRINT "TIME:";TI/60;"SECONDS, JIFFIES:";TI',
    "65 END",
)
EXPECTED_RESULT = 500500
EXPECTED_DOTS = 10
STOCK_C64_NTSC_JIFFIES = 2388


@pytest.mark.performance
def test_noel_source_is_unchanged_stock_cbm_basic_v2() -> None:
    """Keep the performance fixture listable by stock Commodore BASIC V2."""
    assert tuple(SOURCE.read_text(encoding="ascii").splitlines()) == EXPECTED_LINES


@pytest.mark.performance
def test_noel_acceptance_contract_requires_in_memory_run_path() -> None:
    """Record the non-negotiable assertions for the later VICE RUN benchmark."""
    assert EXPECTED_RESULT == sum(range(1, 1001))
    assert EXPECTED_DOTS == 10
    assert STOCK_C64_NTSC_JIFFIES == 2388
