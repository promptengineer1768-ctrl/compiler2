"""Unit tests for the resident screen/cursor helpers."""

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
TESTS_ROOT = ROOT / "tests"
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

try:
    from emu6502_bindings import Emu6502, StopCondition  # type: ignore[import-not-found]
except ImportError:
    pass


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _load_symbol_address(symbol_name: str) -> int:
    dir_path = ROOT / "build" / "routine_directory.json"
    if dir_path.exists():
        try:
            data = json.loads(dir_path.read_text(encoding="utf-8"))
            routines = data.get("routines", {})
            if symbol_name in routines:
                addr_str = routines[symbol_name].get("address", "")
                if addr_str.startswith("$"):
                    return int(addr_str[1:], 16)
        except Exception:
            pass
    lbl_path = ROOT / "build" / "compiler.lbl"
    if lbl_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            lbl_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    map_path = ROOT / "build" / "compiler.map"
    if not map_path.exists():
        pytest.fail("build/compiler.map not found. Run build.ps1 first.")
    match = re.search(
        rf"\b{symbol_name}\b\s+([0-9A-Fa-f]{{6}})",
        map_path.read_text(encoding="utf-8"),
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found in compiler.map.")


def _load_zp_address(name: str) -> int:
    inc_path = ROOT / "build" / "zp_symbols.inc"
    if inc_path.exists():
        match = re.search(
            rf"^{re.escape(name)}\s*=\s*\$([0-9A-Fa-f]+)$",
            inc_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    path = ROOT / "build" / "zp_allocation.json"
    if not path.exists():
        pytest.fail("build/zp_allocation.json not found. Run build.ps1 first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    addr_str = data.get("allocation", {}).get(name, "")
    if addr_str.startswith("$"):
        return int(addr_str[1:], 16)
    pytest.fail(f"Zero page symbol '{name}' not found in allocation.")


def _load_binary(emu: Emu6502) -> None:
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])


@pytest.mark.unit
@pytest.mark.local
class TestScreen:
    """Screen and cursor behavior tests."""

    def test_init_clears_screen_state(self) -> None:
        """screen_init should use the production clear path."""
        dll = _dll_path()
        emu = Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_crsr_x = _load_zp_address("zp_crsr_x")
        zp_crsr_y = _load_zp_address("zp_crsr_y")
        zp_crsr_vis = _load_zp_address("zp_crsr_vis")

        emu.write_mem(zp_crsr_x, 0x27)
        emu.write_mem(zp_crsr_y, 0x18)
        emu.write_mem(zp_crsr_vis, 0x01)
        emu.write_mem_range(0x0400, b"\x51" * 1000)

        assert emu.execute(_load_symbol_address("screen_init"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(zp_crsr_x) == 0x00
        assert emu.read_mem(zp_crsr_y) == 0x00
        assert emu.read_mem(zp_crsr_vis) == 0x00
        assert emu.read_mem_range(0x0400, 0x0400 + 999) == b" " * 1000

    def test_clear_homes_cursor_and_fills_spaces(self) -> None:
        """screen_clear should blank the visible screen and home the cursor."""
        dll = _dll_path()
        emu = Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_crsr_x = _load_zp_address("zp_crsr_x")
        zp_crsr_y = _load_zp_address("zp_crsr_y")
        zp_crsr_vis = _load_zp_address("zp_crsr_vis")

        emu.write_mem(zp_crsr_x, 0x12)
        emu.write_mem(zp_crsr_y, 0x08)
        emu.write_mem(zp_crsr_vis, 0x01)
        emu.write_mem_range(0x0400, b"\x41" * 1000)

        assert emu.execute(_load_symbol_address("screen_clear"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(zp_crsr_x) == 0x00
        assert emu.read_mem(zp_crsr_y) == 0x00
        assert emu.read_mem(zp_crsr_vis) == 0x00
        assert emu.read_mem_range(0x0400, 0x0400 + 39) == b" " * 40

    def test_scroll_up_moves_rows_and_clears_bottom_row(self) -> None:
        """screen_scroll_up should shift visible rows up by one."""
        dll = _dll_path()
        emu = Emu6502(lib_path=dll)
        _load_binary(emu)

        screen = b"".join(bytes([0x41 + row]) * 40 for row in range(25))
        emu.write_mem_range(0x0400, screen)

        assert emu.execute(_load_symbol_address("screen_scroll_up"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem_range(0x0400, 0x0400 + 39) == b"B" * 40
        assert emu.read_mem_range(0x0400 + 23 * 40, 0x0400 + 24 * 40 - 1) == (b"Y" * 40)
        assert emu.read_mem_range(0x0400 + 24 * 40, 0x0400 + 25 * 40 - 1) == (b" " * 40)

    def test_putchar_and_cursor_wrapping(self) -> None:
        """screen_putchar should write at the cursor and wrap to the next line."""
        dll = _dll_path()
        emu = Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_crsr_x = _load_zp_address("zp_crsr_x")
        zp_crsr_y = _load_zp_address("zp_crsr_y")

        emu.write_mem(zp_crsr_x, 0x27)
        emu.write_mem(zp_crsr_y, 0x00)
        emu.set_a(ord("A"))
        assert emu.execute(_load_symbol_address("screen_putchar"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(0x0400 + 39) == ord("A")
        assert emu.read_mem(zp_crsr_x) == 0x00
        assert emu.read_mem(zp_crsr_y) == 0x01

        assert emu.execute(_load_symbol_address("screen_cursor_left"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(zp_crsr_x) == 0x27
        assert emu.read_mem(zp_crsr_y) == 0x00

    def test_getchar_and_cursor_visibility_helpers(self) -> None:
        """screen_getchar and cursor visibility helpers should use real state."""
        dll = _dll_path()
        emu = Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_crsr_x = _load_zp_address("zp_crsr_x")
        zp_crsr_y = _load_zp_address("zp_crsr_y")
        zp_crsr_vis = _load_zp_address("zp_crsr_vis")

        emu.write_mem(zp_crsr_x, 0x03)
        emu.write_mem(zp_crsr_y, 0x02)
        emu.write_mem(0x0400 + 2 * 40 + 3, ord("Z"))
        assert emu.execute(_load_symbol_address("screen_getchar"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.get_state().a == ord("Z")

        emu.write_mem(zp_crsr_x, 0x28)
        assert emu.execute(_load_symbol_address("screen_getchar"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.get_state().a == 0x00

        assert emu.execute(_load_symbol_address("screen_cursor_on"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(zp_crsr_vis) == 0x01
        assert emu.execute(_load_symbol_address("screen_cursor_off"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(zp_crsr_vis) == 0x00

    def test_cursor_movement_edges_and_bottom_scroll(self) -> None:
        """Cursor movement should wrap at edges and scroll at the bottom."""
        dll = _dll_path()
        emu = Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_crsr_x = _load_zp_address("zp_crsr_x")
        zp_crsr_y = _load_zp_address("zp_crsr_y")

        emu.write_mem(zp_crsr_x, 0x27)
        emu.write_mem(zp_crsr_y, 0x03)
        assert emu.execute(_load_symbol_address("screen_cursor_right"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(zp_crsr_x) == 0x00
        assert emu.read_mem(zp_crsr_y) == 0x04

        emu.write_mem(zp_crsr_x, 0x05)
        assert emu.execute(_load_symbol_address("screen_cursor_up"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(zp_crsr_y) == 0x03

        screen = b"".join(bytes([0x61 + row]) * 40 for row in range(25))
        emu.write_mem_range(0x0400, screen)
        emu.write_mem(zp_crsr_y, 0x18)
        assert emu.execute(_load_symbol_address("screen_cursor_down"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(zp_crsr_y) == 0x18
        assert emu.read_mem_range(0x0400, 0x0400 + 39) == b"b" * 40
        assert emu.read_mem_range(0x0400 + 24 * 40, 0x0400 + 25 * 40 - 1) == (b" " * 40)

    def test_put_petscii_maps_letter_a_to_screen_code_01(self) -> None:
        """PETSCII 'A' ($41) must store screen code $01, not raw $41 graphics."""
        dll = _dll_path()
        emu = Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_crsr_x = _load_zp_address("zp_crsr_x")
        zp_crsr_y = _load_zp_address("zp_crsr_y")
        emu.write_mem(zp_crsr_x, 0x00)
        emu.write_mem(zp_crsr_y, 0x00)
        emu.set_a(ord("A"))
        assert emu.execute(_load_symbol_address("screen_put_petscii"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(0x0400) == 0x01
        assert emu.read_mem(zp_crsr_x) == 0x01

    def test_line_input_trims_or_keeps_spaces_by_quote_mode(self) -> None:
        """screen_line_input converts screen codes to PETSCII and trims spaces."""
        dll = _dll_path()
        emu = Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_crsr_x = _load_zp_address("zp_crsr_x")
        zp_crsr_y = _load_zp_address("zp_crsr_y")
        zp_linebuf = _load_zp_address("zp_linebuf")
        zp_line_len = _load_zp_address("zp_line_len")
        zp_quotemode = _load_zp_address("zp_quotemode")

        buffer_addr = 0xC000
        emu.write_mem(zp_linebuf, buffer_addr & 0xFF)
        emu.write_mem(zp_linebuf + 1, buffer_addr >> 8)
        emu.write_mem(zp_crsr_x, 0x00)
        emu.write_mem(zp_crsr_y, 0x00)
        emu.write_mem(zp_quotemode, 0x00)
        # Screen codes for HELLO (H=$08 E=$05 L=$0C L=$0C O=$0F).
        emu.write_mem_range(
            0x0400, bytes([0x08, 0x05, 0x0C, 0x0C, 0x0F]) + b" " * 35
        )

        assert emu.execute(_load_symbol_address("screen_line_input"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(zp_line_len) == 0x05
        assert emu.read_mem_range(buffer_addr, buffer_addr + 4) == b"HELLO"

        emu.write_mem(zp_quotemode, 0x01)
        emu.write_mem_range(buffer_addr, b"\x00" * 40)
        assert emu.execute(_load_symbol_address("screen_line_input"), 10_000) == (
            StopCondition.RTS
        )
        assert emu.read_mem(zp_line_len) == 0x28
        assert emu.read_mem_range(buffer_addr, buffer_addr + 4) == b"HELLO"
