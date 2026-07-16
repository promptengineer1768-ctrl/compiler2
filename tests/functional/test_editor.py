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
PROG_BASE = 0x0400
RANGE_RECORD = 0x0500


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
    emu.set_georam_enabled(True)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    # EDITOR / EDITOR_PINNED live in RAM_HIGH ($E000+), not compiler.bin.
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
        emu.write_mem(0x0001, 0x35)
    return emu


def _run(emu: Any, symbol: str, handle: int = LINE_RECORD, cycles: int = 50_000) -> Any:
    """Run an editor service with a pointer handle in X/Y."""
    emu.set_x(handle & 0xFF)
    emu.set_y(handle >> 8)
    emu.execute(_address(symbol), cycles)
    return emu.get_state()


def _carry_set(state: Any) -> bool:
    return (int(state.p) & 0x01) != 0


def _read_c_string(emu: Any, addr: int, limit: int = 80) -> bytes:
    out = bytearray()
    for i in range(limit):
        b = emu.read_mem(addr + i)
        if b == 0:
            break
        out.append(b)
    return bytes(out)


@pytest.mark.functional
@pytest.mark.local
@pytest.mark.smoke
def test_full_editor_interaction() -> None:
    """Submit, detokenize, list range, delete, and return to READY."""
    emu = _emulator()

    # Canonical tokenized line: line 10, empty body.
    emu.write_mem_range(LINE_RECORD, bytes([10, 0, 0]))

    submit = _run(emu, "editor_submit_line")
    assert submit.a == 0
    assert not _carry_set(submit)

    listed = _run(emu, "editor_detokenize_line")
    assert not _carry_set(listed)
    text_addr = int(listed.x) | (int(listed.y) << 8)
    assert text_addr != 0
    text = _read_c_string(emu, text_addr)
    assert text.startswith(b"10")

    # Stock-linked program: 10 PRINT
    emu.write_mem_range(
        PROG_BASE,
        bytes(
            [
                0x07,
                0x04,  # next = $0407
                10,
                0,  # line number
                0x99,
                0,  # PRINT, end of line
                0,
                0,  # end of program
            ]
        ),
    )
    emu.write_mem_range(
        RANGE_RECORD,
        bytes(
            [
                0,
                0,  # start
                0xFF,
                0xFF,  # end
                PROG_BASE & 0xFF,
                PROG_BASE >> 8,
            ]
        ),
    )
    ranged = _run(emu, "editor_list_range", handle=RANGE_RECORD, cycles=200_000)
    assert not _carry_set(ranged)
    result = _address("editor_result_buffer")
    list_text = _read_c_string(emu, result)
    assert list_text.startswith(b"10 ")
    assert b"PRINT" in list_text

    deleted = _run(emu, "editor_delete_line")
    assert not _carry_set(deleted)

    ready = _run(emu, "editor_ready_transition")
    assert ready.a == ord("R")
    assert not _carry_set(ready)
