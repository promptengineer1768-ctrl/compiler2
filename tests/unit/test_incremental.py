"""Unit tests for incremental compilation state management."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None

INPUT_ADDR = 0xCA00


def _address(symbol: str) -> int:
    """Resolve a linked routine or exported data address."""
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    return int(data["routines"][symbol]["address"].removeprefix("$"), 16)


def _routine_record(symbol: str) -> dict[str, Any]:
    """Return the generated placement record for one production routine."""
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    return cast(dict[str, Any], data["routines"][symbol])


def _linked_address(symbol: str) -> int:
    """Resolve a symbol's linked address from the production label file."""
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(
        rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}$", labels, re.M
    )
    assert match is not None, f"missing linked symbol: {symbol}"
    return int(match.group(1), 16)


def _emulator() -> Any:
    """Load the linked compiler into a fresh emulator."""
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    paths = [TOOLS_ROOT / "emu6502.dll", TOOLS_ROOT / "msys-emu6502.dll"]
    dll = next((path for path in paths if path.exists()), None)
    if dll is None:
        pytest.skip("Emulator DLL not found in tools folder.")
    emu = C64Emu6502(lib_path=dll)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    return emu


def _run(emu: Any, symbol: str, pointer: int = INPUT_ADDR) -> Any:
    """Page in and execute an incremental routine's assembled production bytes."""
    record = _routine_record(symbol)
    if record["layer"] == "georam":
        image = (ROOT / "build" / "georam.bin").read_bytes()
        assert image[:2] == b"\x00\xde"
        emu.set_georam_enabled(True)
        emu.load_georam(image[2:])
        emu.write_mem(0xDFFF, int(record["block"]))
        emu.write_mem(0xDFFE, int(record["page"]))
    emu.set_x(pointer & 0xFF)
    emu.set_y(pointer >> 8)
    entry = _address(symbol)
    emu.execute(entry, 3000)
    return emu.get_state()


def _fingerprint(data: bytes) -> int:
    """Return the assembly fingerprint oracle for eight dependency bytes."""
    low, high = 0x5A, 0xC3
    for index, value in enumerate(data):
        mixed = value ^ low
        low = ((mixed << 1) | (mixed >> 7)) & 0xFF
        high = ((index ^ high) + low) & 0xFF
    return low | (high << 8)


@pytest.mark.unit
@pytest.mark.local
def test_fingerprint_covers_all_dependency_generations() -> None:
    """The cache key deterministically incorporates every dependency class."""
    emu = _emulator()
    dependencies = bytes([1, 3, 5, 7, 11, 13, 17, 19])
    emu.write_mem_range(INPUT_ADDR, dependencies)
    state = _run(emu, "incremental_fingerprint")
    assert (state.x | (state.y << 8)) == _fingerprint(dependencies)
    assert (state.p & 1) == 0


@pytest.mark.unit
@pytest.mark.local
def test_fingerprint_changes_for_each_dependency_byte() -> None:
    """Changing any generation invalidates the cache key."""
    baseline = bytes(8)
    expected = _fingerprint(baseline)
    for index in range(8):
        changed = bytearray(baseline)
        changed[index] = 1
        assert _fingerprint(bytes(changed)) != expected


@pytest.mark.unit
@pytest.mark.local
def test_mark_dependents_accumulates_dirty_classes() -> None:
    """Structural edits union their reverse dependency masks."""
    emu = _emulator()
    emu.write_mem_range(INPUT_ADDR, b"\x05")
    _run(emu, "incremental_mark_dependents")
    emu.write_mem_range(INPUT_ADDR, b"\x12")
    _run(emu, "incremental_mark_dependents")
    assert emu.read_mem(_linked_address("incremental_dirty_mask")) == 0x17


@pytest.mark.unit
@pytest.mark.local
def test_resolve_dirty_clears_all_required_repairs() -> None:
    """Resolution leaves no record eligible for interpreter fallback."""
    emu = _emulator()
    emu.write_mem_range(INPUT_ADDR, b"\xff")
    _run(emu, "incremental_mark_dependents")
    state = _run(emu, "incremental_resolve_dirty")
    assert emu.read_mem(_linked_address("incremental_dirty_mask")) == 0
    assert (state.p & 1) == 0


@pytest.mark.unit
@pytest.mark.local
def test_can_run_rejects_unpublished_state() -> None:
    """RUN is blocked before any verified generation is published."""
    emu = _emulator()
    state = _run(emu, "incremental_can_run", pointer=0)
    assert (state.p & 1) == 1
