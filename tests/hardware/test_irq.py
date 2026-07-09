"""Focused VICE IRQ-path validation."""

from __future__ import annotations

from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from vice_harness import MACHINES, VICE_ROOT, running_vice  # noqa: E402


def _require_vice_exe() -> Path:
    """Require the bundled C64 VICE executable."""
    exe = VICE_ROOT / "x64sc.exe"
    if not exe.exists():
        pytest.skip(f"x64sc.exe not found under {VICE_ROOT}")
    return exe


@pytest.mark.hardware
@pytest.mark.vice
def test_irq_jiffy_clock_advances_while_machine_runs() -> None:
    """The KERNAL IRQ path should keep the BASIC jiffy clock moving."""
    _require_vice_exe()
    machine = MACHINES["basicv2"]
    with running_vice(machine, port=6542) as vice:
        vice.wait_for_ready_screen(machine, timeout=20.0, settle_reads=1)
        before = vice.memory_read(0x00A0, 3)
        time.sleep(0.3)
        after = vice.memory_read(0x00A0, 3)
    assert after != before
