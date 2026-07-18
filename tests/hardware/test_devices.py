"""Focused VICE device-path validation."""

from __future__ import annotations

from pathlib import Path
import shutil
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


def _require_compiler_disk() -> Path:
    """Require the packaged compiler disk image."""
    disk = ROOT / "build" / "compiler.d64"
    if not disk.exists():
        pytest.skip("build/compiler.d64 not found; run tools/package_d64.py")
    return disk


@pytest.mark.hardware
@pytest.mark.vice
def test_device_save_and_load_round_trip() -> None:
    """KERNAL device 8 should save and load a BASIC program on the D64 image."""
    _require_vice_exe()
    source_disk = _require_compiler_disk()
    debug_dir = ROOT / "debug"
    debug_dir.mkdir(exist_ok=True)
    writable_disk = debug_dir / "hardware_device_roundtrip.d64"
    shutil.copy(source_disk, writable_disk)

    machine = MACHINES["basicv2"]
    with running_vice(
        machine, port=6543, extra_args=("-8", str(writable_disk))
    ) as vice:
        vice.wait_for_ready_screen(machine, timeout=20.0, settle_reads=1)
        vice.call("vice.execution.run", timeout=1.0)
        time.sleep(0.5)
        vice.submit_command(machine, "NEW", timeout=20.0)
        vice.type_text('10 PRINT "HW"\n')
        time.sleep(2.0)
        saved = vice.submit_command(machine, 'SAVE "HWTEST",8', timeout=90.0)
        vice.submit_command(machine, "NEW", timeout=20.0)
        loaded = vice.submit_command(machine, 'LOAD "HWTEST",8', timeout=90.0)

    assert "SAVING HWTEST" in saved
    assert "SEARCHING FOR HWTEST" in loaded
    assert "LOADING" in loaded
