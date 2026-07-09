"""Focused VICE keyboard-path validation."""

from __future__ import annotations

from pathlib import Path
import sys

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
@pytest.mark.smoke
def test_keyboard_path_types_command_and_gets_basic_output() -> None:
    """VICE keyboard events should reach BASIC through the normal input path."""
    _require_vice_exe()
    machine = MACHINES["basicv2"]
    with running_vice(machine, port=6541) as vice:
        vice.wait_for_ready_screen(machine, timeout=20.0, settle_reads=1)
        screen = vice.submit_command(machine, 'PRINT "OK"', timeout=20.0)
    assert 'PRINT "OK"' in screen
    assert "\nOK\n" in f"\n{screen}\n"
