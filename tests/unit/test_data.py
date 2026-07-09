"""Direct real-byte tests for DATA stream routines."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    pass


@dataclass(frozen=True)
class DataState:
    """Private DATA stream state addresses recovered from linked bytes."""

    data_ptr: int
    data_generation: int
    source_generation: int
    data_saved_ptr: int


def _dll_path() -> Path:
    """Return the real 6502 emulator binding."""
    for path in (
        ROOT.parent / "tools" / "emu6502.dll",
        ROOT.parent / "tools" / "msys-emu6502.dll",
    ):
        if path.exists():
            return path
    pytest.skip("Emulator DLL not found in tools folder.")


def _load_symbol_address(symbol_name: str) -> int:
    """Load a linked symbol address."""
    labels_path = ROOT / "build" / "compiler.lbl"
    if labels_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    map_path = ROOT / "build" / "compiler.map"
    if not map_path.exists():
        pytest.fail(
            f"build/compiler.map not found. Run build.ps1 first. Missing: {symbol_name}"
        )
    match = re.search(
        rf"\b{re.escape(symbol_name)}\b\s+([0-9A-Fa-f]{{6}})",
        map_path.read_text(encoding="utf-8"),
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol {symbol_name!r} not found in linked outputs.")


def _linked_bytes(symbol_name: str, length: int) -> bytes:
    """Read linked compiler bytes for a symbol body."""
    address = _load_symbol_address(symbol_name)
    bin_path = ROOT / "build" / "compiler.bin"
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    start = address - load_addr + 2
    if start < 2 or start + length > len(payload):
        pytest.fail(f"Symbol {symbol_name!r} is outside build/compiler.bin.")
    return payload[start : start + length]


def _word(data: bytes, offset: int) -> int:
    """Return a little-endian word from data."""
    return data[offset] | (data[offset + 1] << 8)


def _data_state() -> DataState:
    """Recover private BSS state addresses without exporting test ABI."""
    read_body = _linked_bytes("data_read", 28)
    reset_body = _linked_bytes("data_reset", 10)
    if read_body[4] != 0xAD or read_body[12] != 0xAD or read_body[15] != 0xCD:
        pytest.fail("data_read no longer exposes the expected state-access shape.")
    if reset_body[6] != 0xAD:
        pytest.fail("data_reset no longer reads DATA_SAVED_PTR at the expected point.")
    return DataState(
        data_ptr=_word(read_body, 5),
        data_generation=_word(read_body, 13),
        source_generation=_word(read_body, 16),
        data_saved_ptr=_word(reset_body, 7),
    )


def _new_emu() -> C64Emu6502:
    """Load the linked compiler image into a fresh emulator."""
    emu = C64Emu6502(lib_path=_dll_path())
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.set_georam_enabled(True)
    return emu


def _carry_is_set(emu: C64Emu6502) -> bool:
    """Return whether carry is set after a routine call."""
    return bool(int(emu.get_state().p) & 0x01)


def _read_word(emu: C64Emu6502, address: int) -> int:
    """Read a little-endian word from emulated memory."""
    return emu.read_mem(address) | (emu.read_mem(address + 1) << 8)


def _write_word(emu: C64Emu6502, address: int, value: int) -> None:
    """Write a little-endian word to emulated memory."""
    emu.write_mem(address, value & 0xFF)
    emu.write_mem(address + 1, (value >> 8) & 0xFF)


def _seed_data_stream(emu: C64Emu6502, stream: int, generation: int) -> DataState:
    """Seed DATA start pointer and run the production reset routine."""
    state = _data_state()
    _write_word(emu, state.data_saved_ptr, stream)
    emu.set_x(generation & 0xFF)
    emu.set_y((generation >> 8) & 0xFF)
    emu.execute(_load_symbol_address("data_reset"), 10000)
    return state


@pytest.mark.unit
@pytest.mark.local
class TestDataRead:
    """READ statement data stream tests."""

    def test_data_read_advances_cursor_and_stores_bytes(self) -> None:
        """READ consumes nonzero DATA bytes, stores them, and stops at marker."""
        emu = _new_emu()
        stream = 0x1800
        destination = 0x1900
        emu.write_mem_range(stream, b"AB\x00")
        state = _seed_data_stream(emu, stream, 0x1234)

        read = _load_symbol_address("data_read")
        emu.set_x(destination & 0xFF)
        emu.set_y(destination >> 8)
        emu.execute(read, 10000)
        assert not _carry_is_set(emu)
        assert emu.read_mem(destination) == ord("A")
        assert _read_word(emu, state.data_ptr) == stream + 1

        emu.set_x(destination & 0xFF)
        emu.set_y(destination >> 8)
        emu.execute(read, 10000)
        assert not _carry_is_set(emu)
        assert emu.read_mem(destination) == ord("B")
        assert _read_word(emu, state.data_ptr) == stream + 2

        emu.execute(read, 10000)
        assert _carry_is_set(emu)
        assert _read_word(emu, state.data_ptr) == stream + 2

    def test_data_read_rejects_stale_generation_without_store(self) -> None:
        """READ fails when DATA generation no longer matches source generation."""
        emu = _new_emu()
        stream = 0x1810
        destination = 0x1910
        emu.write_mem_range(stream, b"Z\x00")
        state = _seed_data_stream(emu, stream, 0x0001)
        _write_word(emu, state.data_generation, 0x0002)
        emu.write_mem(destination, 0xEE)

        emu.set_x(destination & 0xFF)
        emu.set_y(destination >> 8)
        emu.execute(_load_symbol_address("data_read"), 10000)

        assert _carry_is_set(emu)
        assert emu.read_mem(destination) == 0xEE
        assert _read_word(emu, state.data_ptr) == stream


@pytest.mark.unit
@pytest.mark.local
class TestDataRestore:
    """RESTORE statement tests."""

    def test_data_restore_without_target_uses_saved_start(self) -> None:
        """Targetless RESTORE resets cursor to the published DATA start."""
        emu = _new_emu()
        state = _seed_data_stream(emu, 0x1820, 0x0003)
        _write_word(emu, state.data_ptr, 0x1888)

        emu.set_x(0)
        emu.set_y(0)
        emu.execute(_load_symbol_address("data_restore"), 10000)

        assert not _carry_is_set(emu)
        assert _read_word(emu, state.data_ptr) == 0x1820

    def test_data_restore_with_line_target_sets_cursor(self) -> None:
        """RESTORE with a resolved target cursor publishes that cursor."""
        emu = _new_emu()
        state = _seed_data_stream(emu, 0x1830, 0x0004)

        emu.set_x(0x44)
        emu.set_y(0x18)
        emu.execute(_load_symbol_address("data_restore"), 10000)

        assert not _carry_is_set(emu)
        assert _read_word(emu, state.data_ptr) == 0x1844


@pytest.mark.unit
@pytest.mark.local
class TestDataReset:
    """Data stream initialization tests."""

    def test_data_reset_initializes_cursor_and_generations(self) -> None:
        """RUN/CLR reset publishes the saved start and current generation."""
        emu = _new_emu()
        stream = 0x1850
        generation = 0xBEEF
        state = _seed_data_stream(emu, stream, generation)

        assert _read_word(emu, state.data_ptr) == stream
        assert _read_word(emu, state.source_generation) == generation
        assert _read_word(emu, state.data_generation) == generation
