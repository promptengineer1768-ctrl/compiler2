"""Unit tests for runtime error helpers (errors.asm)."""

from __future__ import annotations

import json
import re
import sys
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


def _artifact_root() -> Path:
    debug_root = ROOT / "debug" / "runtime_slice"
    return debug_root if debug_root.exists() else ROOT / "build"


def _dll_path() -> Path:
    for candidate in (
        ROOT.parent / "tools" / "emu6502.dll",
        ROOT.parent / "tools" / "msys-emu6502.dll",
    ):
        if candidate.exists():
            return candidate
    pytest.skip("Emulator DLL not found in tools folder.")


def _load_binary(emu: C64Emu6502) -> None:
    payload = (_artifact_root() / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.set_georam_enabled(True)


def _load_symbol_address(symbol_name: str) -> int:
    labels_path = _artifact_root() / "compiler.lbl"
    if labels_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    directory_path = _artifact_root() / "routine_directory.json"
    if directory_path.exists():
        data = json.loads(directory_path.read_text(encoding="utf-8"))
        routine = data.get("routines", {}).get(symbol_name)
        if routine:
            addr = routine.get("address", "")
            if addr.startswith("$"):
                return int(addr[1:], 16)
    map_path = _artifact_root() / "compiler.map"
    match = re.search(
        rf"\b{re.escape(symbol_name)}\b\s+([0-9A-Fa-f]{{6}})",
        map_path.read_text(encoding="utf-8"),
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found.")


def _zp_address(name: str) -> int:
    data = json.loads(
        (ROOT / "build" / "zp_allocation.json").read_text(encoding="utf-8")
    )
    addr = data.get("allocation", {}).get(name, "")
    if addr.startswith("$"):
        return int(addr[1:], 16)
    pytest.fail(f"Zero page symbol '{name}' not found.")


def _carry_is_set(emu: C64Emu6502) -> bool:
    return (int(emu.get_state().p) & 0x01) != 0


def _carry_is_clear(emu: C64Emu6502) -> bool:
    return (int(emu.get_state().p) & 0x01) == 0


@pytest.mark.unit
@pytest.mark.local
class TestErrors:
    """Runtime error helper tests."""

    def test_error_codes_and_raise(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        errnum = _zp_address("zp_errnum")
        for name, expected in (
            ("err_syntax", 0x0B),
            ("err_type", 0x16),
            ("err_overflow", 0x0F),
            ("err_outofmemory", 0x10),
            ("err_undefdfunction", 0x1B),
        ):
            emu.execute(_load_symbol_address(name), 10000)
            assert emu.read_mem(errnum) == expected
            assert emu.get_state().a == expected
            assert _carry_is_set(emu)

        emu.set_a(0x09)
        emu.execute(_load_symbol_address("err_raise_direct"), 10000)
        assert emu.read_mem(errnum) == 0x09
        assert _carry_is_set(emu)

        raise_addr = _load_symbol_address("err_raise")
        errline = _zp_address("zp_errline")
        emu.set_a(0x06)
        emu.set_x(0x34)
        emu.set_y(0x12)
        emu.execute(raise_addr, 10000)
        assert emu.read_mem(errnum) == 0x06
        assert emu.read_mem(errline) == 0x34
        assert emu.read_mem(errline + 1) == 0x12
        assert _carry_is_set(emu)

    def test_error_bridge_break_and_continuation(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        from_kernal = _load_symbol_address("err_from_kernal")
        break_addr = _load_symbol_address("err_break")
        save_cont_addr = _load_symbol_address("err_save_cont")
        errnum = _zp_address("zp_errnum")
        cont_handle = _zp_address("zp_cont_handle")
        cont_generation = _zp_address("zp_cont_generation")
        stop_flag = _zp_address("zp_stop_flag")

        emu.set_a(0xA5)
        emu.write_mem(errnum, 0xFF)
        emu.set_p(emu.get_state().p & 0xFE)
        emu.execute(from_kernal, 10000)
        assert emu.get_state().a == 0x00
        assert emu.read_mem(errnum) == 0x00
        assert _carry_is_clear(emu)

        for kernal_error in range(1, 10):
            emu.set_a(kernal_error)
            emu.write_mem(errnum, 0xFF)
            emu.set_p(emu.get_state().p | 0x01)
            emu.execute(from_kernal, 10000)
            assert emu.get_state().a == kernal_error
            assert emu.read_mem(errnum) == kernal_error
            assert _carry_is_set(emu)

        for invalid_status in (0x00, 0x0A, 0xFF):
            emu.set_a(invalid_status)
            emu.write_mem(errnum, 0xFF)
            emu.set_p(emu.get_state().p | 0x01)
            emu.execute(from_kernal, 10000)
            assert emu.get_state().a == 0x02
            assert emu.read_mem(errnum) == 0x02
            assert _carry_is_set(emu)

        emu.set_x(0x78)
        emu.set_y(0x56)
        emu.execute(break_addr, 10000)
        assert emu.read_mem(cont_handle) == 0x78
        assert emu.read_mem(cont_handle + 1) == 0x56
        assert emu.read_mem(stop_flag) == 0x01
        assert emu.read_mem(errnum) == 0x00
        assert _carry_is_set(emu)

        emu.set_x(0xAB)
        emu.set_y(0xCD)
        emu.write_mem(cont_generation, 0x5A)
        emu.execute(save_cont_addr, 10000)
        assert emu.read_mem(cont_handle) == 0xAB
        assert emu.read_mem(cont_handle + 1) == 0xCD
        assert emu.get_state().a == 0x5A
        assert _carry_is_clear(emu)

    @pytest.mark.parametrize(
        ("entry", "message"),
        [
            ("err_syntax", b"?SYNTAX ERROR"),
            ("err_type", b"?TYPE MISMATCH ERROR"),
            ("err_overflow", b"?OVERFLOW ERROR"),
            ("err_outofmemory", b"?OUT OF MEMORY ERROR"),
            ("err_undefdfunction", b"?UNDEF'D FUNCTION ERROR"),
        ],
    )
    def test_error_shortcuts_format_stock_messages(
        self, entry: str, message: bytes
    ) -> None:
        """Every shortcut publishes its exact stock-compatible message."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.execute(_load_symbol_address(entry), 10000)
        buffer = _load_symbol_address("err_message_buffer")
        length = emu.read_mem(_load_symbol_address("err_message_length"))
        assert emu.read_mem_range(buffer, buffer + length - 1) == message

    def test_error_raise_unwinds_runtime_and_formats_program_line(self) -> None:
        """Program errors restore channels/graphics and format the source line."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.write_mem(0xD011, 0x3B)
        emu.write_mem(_zp_address("zp_stop_flag"), 1)
        emu.write_mem(_zp_address("zp_cont_handle"), 0x34)
        emu.write_mem(_zp_address("zp_cont_handle") + 1, 0x12)
        emu.set_a(0x06)
        emu.set_x(0x34)
        emu.set_y(0x12)

        emu.execute(_load_symbol_address("err_raise"), 100000)

        buffer = _load_symbol_address("err_message_buffer")
        length = emu.read_mem(_load_symbol_address("err_message_length"))
        assert emu.read_mem_range(buffer, buffer + length - 1) == (
            b"?NOT INPUT FILE ERROR IN 4660"
        )
        assert emu.read_mem(0xD011) == 0x1B
        assert emu.read_mem(_zp_address("zp_stop_flag")) == 0
        assert emu.read_mem(_zp_address("zp_cont_handle")) == 0
        assert emu.read_mem(_zp_address("zp_cont_handle") + 1) == 0
        assert emu.read_mem(_load_symbol_address("kernal_output_byte")) == 0x0D
