"""Functional editor workflow tests against the linked compiler image."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None

LINE_RECORD = 0xCD00


def _address(symbol: str) -> int:
    """Resolve a linked routine address."""
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(
        rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}$",
        labels,
        re.MULTILINE,
    )
    if match:
        return int(match.group(1), 16)
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    return int(data["routines"][symbol]["address"].removeprefix("$"), 16)


def _emulator() -> Any:
    """Load the production compiler image into the local C64 emulator."""
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    dll = next(
        (
            path
            for path in (TOOLS_ROOT / "emu6502.dll", TOOLS_ROOT / "msys-emu6502.dll")
            if path.exists()
        ),
        None,
    )
    if dll is None:
        pytest.skip("Emulator DLL not found in tools folder.")
    emu = C64Emu6502(lib_path=dll)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    return emu


def _run(emu: Any, symbol: str) -> Any:
    """Run an editor service with the shared line-record handle."""
    emu.set_x(LINE_RECORD & 0xFF)
    emu.set_y(LINE_RECORD >> 8)
    emu.execute(_address(symbol), 10_000)
    return emu.get_state()


@pytest.mark.functional
@pytest.mark.local
@pytest.mark.smoke
def test_full_editor_interaction() -> None:
    """Submit, list, delete, and return to READY through editor services."""
    emu = _emulator()
    emu.write_mem_range(LINE_RECORD, bytes([10, 0]))

    submit = _run(emu, "editor_submit_line")
    assert submit.a == 0
    assert (submit.p & 1) == 0

    listed = _run(emu, "editor_detokenize_line")
    assert (listed.p & 1) == 0
    assert listed.x | (listed.y << 8) != 0

    deleted = _run(emu, "editor_delete_line")
    assert (deleted.p & 1) == 0

    ready = _run(emu, "editor_ready_transition")
    assert ready.a == ord("R")
    assert (ready.p & 1) == 0
