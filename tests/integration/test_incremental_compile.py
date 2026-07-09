"""Integration tests for transactional incremental line publication."""

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

TX_ADDR = 0xCB00


def _address(symbol: str) -> int:
    """Resolve a routine or exported state symbol."""
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(
        rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}$", labels, re.MULTILINE
    )
    if match:
        return int(match.group(1), 16)
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    return int(data["routines"][symbol]["address"].removeprefix("$"), 16)


def _emulator() -> Any:
    """Return an emulator loaded with the linked compiler image."""
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
    emu.set_georam_enabled(True)
    return emu


def _run(emu: Any, symbol: str, value: int = TX_ADDR) -> Any:
    """Execute an incremental routine using X/Y for its 16-bit input."""
    emu.set_x(value & 0xFF)
    emu.set_y(value >> 8)
    emu.execute(_address(symbol), 3000)
    return emu.get_state()


def _transaction(source: int, code: int) -> bytes:
    """Build a valid six-byte source/code publication transaction."""
    fields = bytes([0xA5, source & 0xFF, source >> 8, code & 0xFF, code >> 8])
    checksum = 0
    for value in fields:
        checksum ^= value
    return fields + bytes([checksum])


@pytest.mark.integration
@pytest.mark.local
def test_incremental_line_entry_publishes_both_roots_atomically() -> None:
    """A valid clean transaction publishes source and code in one generation."""
    emu = _emulator()
    emu.write_mem_range(TX_ADDR, _transaction(0x3210, 0x7654))
    state = _run(emu, "incremental_publish")
    assert (state.p & 1) == 0
    assert state.x | (state.y << 8) == 1
    assert emu.read_mem(_address("incremental_source_root")) == 0x10
    assert emu.read_mem(_address("incremental_code_root")) == 0x54
    run_state = _run(emu, "incremental_can_run", value=1)
    assert (run_state.p & 1) == 0


@pytest.mark.integration
@pytest.mark.local
def test_dirty_or_corrupt_transaction_cannot_publish() -> None:
    """Dirty dependencies and checksum errors preserve the prior generation."""
    emu = _emulator()
    emu.write_mem_range(TX_ADDR, _transaction(0x1111, 0x2222))
    _run(emu, "incremental_publish")
    emu.write_mem_range(TX_ADDR, b"\x08")
    _run(emu, "incremental_mark_dependents")
    emu.write_mem_range(TX_ADDR, _transaction(0x3333, 0x4444))
    state = _run(emu, "incremental_publish")
    assert (state.p & 1) == 1
    assert emu.read_mem(_address("incremental_generation")) == 1
    _run(emu, "incremental_resolve_dirty")
    corrupt = bytearray(_transaction(0x3333, 0x4444))
    corrupt[-1] ^= 1
    emu.write_mem_range(TX_ADDR, bytes(corrupt))
    assert (_run(emu, "incremental_publish").p & 1) == 1
    assert emu.read_mem(_address("incremental_source_root")) == 0x11


@pytest.mark.integration
@pytest.mark.local
def test_abort_preserves_last_valid_generation() -> None:
    """Rollback discards scratch dirtiness without touching published roots."""
    emu = _emulator()
    emu.write_mem_range(TX_ADDR, _transaction(0x1357, 0x2468))
    _run(emu, "incremental_publish")
    emu.write_mem_range(TX_ADDR, b"\xff")
    _run(emu, "incremental_mark_dependents")
    state = _run(emu, "incremental_abort")
    assert (state.p & 1) == 0
    assert emu.read_mem(_address("incremental_generation")) == 1
    assert emu.read_mem(_address("incremental_source_root")) == 0x57
    assert (_run(emu, "incremental_can_run", value=1).p & 1) == 0
