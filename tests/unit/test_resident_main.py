"""Unit tests for the resident main loop."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
_DOCS_TOOLS = Path(r"C:\Users\me\Documents\Coding Projects\tools")
for _tools in (TOOLS_ROOT, _DOCS_TOOLS):
    if str(_tools) not in sys.path:
        sys.path.insert(0, str(_tools))
try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None  # type: ignore[misc, assignment]


def _dll_path() -> Path:
    candidates = [
        ROOT.parent / "tools" / "emu6502.dll",
        ROOT.parent / "tools" / "msys-emu6502.dll",
        Path(r"C:\Users\me\Documents\Coding Projects\tools\emu6502.dll"),
        Path(r"C:\Users\me\Documents\Coding Projects\tools\msys-emu6502.dll"),
    ]
    for path in candidates:
        if path.exists():
            return path
    pytest.skip("Emulator DLL not found in tools folder.")


def _load_symbol_address(symbol_name: str) -> int:
    # Prefer the linked label file: routine_directory.json records the geoRAM
    # window address ($DE00) for XIP entries, which is wrong for body scans.
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


def _load_binary(emu: C64Emu6502) -> None:
    emu.set_georam_enabled(True)
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])


def _load_georam_image(emu: C64Emu6502) -> None:
    """Load the built geoRAM payload into the emulator backing store."""
    image_path = ROOT / "build" / "georam.bin"
    if not image_path.exists():
        pytest.fail("build/georam.bin not found. Run build.ps1 first.")
    image = image_path.read_bytes()
    assert image[:2] == b"\x00\xde"
    emu.load_georam(image[2:])


def _linked_bytes(address: int, length: int) -> bytes:
    """Read linked compiler bytes at an absolute address."""
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    offset = 2 + address - load_addr
    return payload[offset : offset + length]


@pytest.mark.unit
@pytest.mark.local
class TestResidentMain:
    """Resident loop and boundary assertion tests."""

    @pytest.mark.callable_coverage("resident_submit_line", executor="execute_rts")
    @pytest.mark.callable_coverage("resident_poll_input", executor="execute_rts")
    @pytest.mark.callable_coverage("georam_select", executor="execute_rts")
    def test_poll_and_submit_line_use_screen_capture(self) -> None:
        """resident helpers should drain a byte and submit the captured line."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        _load_georam_image(emu)

        zp_linebuf = _load_zp_address("zp_linebuf")
        zp_line_len = _load_zp_address("zp_line_len")
        zp_quotemode = _load_zp_address("zp_quotemode")
        zp_gr_block = _load_zp_address("zp_gr_block")
        resident_input = _load_symbol_address("resident_input_byte")

        buffer_addr = 0xC000
        emu.write_mem(zp_quotemode, 0x00)
        emu.write_mem(0x0001, 0x35)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.write_mem(zp_linebuf, buffer_addr & 0xFF)
        emu.write_mem(zp_linebuf + 1, buffer_addr >> 8)
        emu.write_mem(resident_input, 0x41)
        # Screen RAM holds screen codes, not PETSCII ("READY" → $12,$05,$01,$04,$19).
        emu.write_mem_range(0x0400, bytes([0x12, 0x05, 0x01, 0x04, 0x19]) + b" " * 35)
        capture = _load_symbol_address("resident_line_capture")

        emu.execute(_load_symbol_address("resident_poll_input"), 10_000)
        assert emu.get_state().a == 0x41
        emu.execute(_load_symbol_address("resident_submit_line"), 10_000)
        assert emu.read_mem(resident_input) == 0x00
        assert emu.read_mem(zp_line_len) == 0x05
        # Capture always lands in resident_line_capture (pointer re-armed).
        assert emu.read_mem_range(capture, capture + 4) == b"READY"
        assert emu.read_mem(zp_gr_block) == 0x00

    def test_resident_main_is_linked_as_non_returning_loop(self) -> None:
        """resident_main should poll, dispatch keys, and loop without RTS."""
        resident_main = _load_symbol_address("resident_main")
        resident_poll_input = _load_symbol_address("resident_poll_input")
        resident_handle_key = _load_symbol_address("resident_handle_key")
        body = _linked_bytes(resident_main, 48)

        assert (
            bytes([0x20, resident_poll_input & 0xFF, resident_poll_input >> 8]) in body
        )
        assert (
            bytes([0x20, resident_handle_key & 0xFF, resident_handle_key >> 8]) in body
        )
        assert bytes([0x4C, resident_main & 0xFF, resident_main >> 8]) in body
        assert 0x60 not in body

    @pytest.mark.callable_coverage("georam_select", executor="execute_rts")
    def test_handle_key_echoes_printable_and_submits_on_return(self) -> None:
        """Printable keys paint the cell; RETURN captures and submits the line."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        _load_georam_image(emu)

        zp_crsr_x = _load_zp_address("zp_crsr_x")
        zp_crsr_y = _load_zp_address("zp_crsr_y")
        zp_linebuf = _load_zp_address("zp_linebuf")
        zp_quotemode = _load_zp_address("zp_quotemode")
        buffer_addr = 0xC000

        emu.write_mem(0x0001, 0x35)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.write_mem(zp_linebuf, buffer_addr & 0xFF)
        emu.write_mem(zp_linebuf + 1, buffer_addr >> 8)
        emu.write_mem(zp_quotemode, 0x00)
        emu.write_mem(zp_crsr_x, 0x00)
        emu.write_mem(zp_crsr_y, 0x00)
        emu.write_mem_range(0x0400, b" " * 40)

        # GETIN PETSCII 'A' ($41) must paint screen code $01 (not $41 graphics).
        emu.set_a(ord("A"))
        emu.execute(_load_symbol_address("resident_handle_key"), 10_000)
        assert emu.read_mem(0x0400) == 0x01
        assert emu.read_mem(zp_crsr_x) == 0x01

        # PETSCII 'X' ($58) → screen code $18.
        emu.set_a(ord("X"))
        emu.execute(_load_symbol_address("resident_handle_key"), 10_000)
        assert emu.read_mem(0x0401) == 0x18

    def test_submit_line_uses_pipeline_for_direct_mode(self) -> None:
        """Direct-mode submit enters the line pipeline through the XIP gate."""
        resident_submit_line = _load_symbol_address("resident_submit_line")
        pipeline_id = _load_symbol_address("GEORAM_ROUTINE_ID_PIPELINE_COMPILE_LINE")
        gate = _load_symbol_address("georam_call_group_n_xy")
        body = _linked_bytes(resident_submit_line, 220)

        assert (
            bytes(
                [
                    0xA9,
                    pipeline_id & 0xFF,
                    0x20,
                    gate & 0xFF,
                    gate >> 8,
                ]
            )
            in body
        )

    def test_submit_line_wires_direct_and_program_store(self) -> None:
        """Submit path tokenizes direct commands and stores numbered lines."""
        resident_submit_line = _load_symbol_address("resident_submit_line")
        try_direct = _load_symbol_address("resident_try_direct_command")
        put_line = _load_symbol_address("program_lines_put_linebuf")
        direct_exec_id = _load_symbol_address(
            "GEORAM_ROUTINE_ID_DIRECT_EXECUTE_COMMAND"
        )
        gate = _load_symbol_address("georam_call_group_n_xy")
        token_init_id = _load_symbol_address("GEORAM_ROUTINE_ID_TOKEN_INIT")
        token_gate = _load_symbol_address("georam_call_group_0_xy")
        body = _linked_bytes(resident_submit_line, 220)
        try_body = _linked_bytes(try_direct, 160)

        assert bytes([0x20, try_direct & 0xFF, try_direct >> 8]) in body
        assert bytes([0x20, put_line & 0xFF, put_line >> 8]) in body
        assert (
            bytes(
                [
                    0xA9,
                    token_init_id & 0xFF,
                    0x20,
                    token_gate & 0xFF,
                    token_gate >> 8,
                ]
            )
            in try_body
        )
        assert (
            bytes(
                [
                    0xA9,
                    direct_exec_id & 0xFF,
                    0x20,
                    gate & 0xFF,
                    gate >> 8,
                ]
            )
            in try_body
        )

    def test_enter_degraded_sets_flag_and_shows_error(self) -> None:
        """Degraded entry marks the mode and paints the expansion error."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        # Execute only the show-error helper (non-looping).
        emu.execute(_load_symbol_address("resident_show_expansion_error"), 10_000)
        screen = bytes(emu.read_mem(0x0400 + i) for i in range(28))
        assert screen.startswith(b"?EXPANSION MEMORY REQUIRED")
        emu.write_mem(_load_symbol_address("resident_degraded"), 0)
        # Enter degraded briefly: first instruction sets the flag then shows error.
        body = _linked_bytes(_load_symbol_address("resident_enter_degraded"), 8)
        # lda #1 / sta resident_degraded
        assert body[0] == 0xA9 and body[1] == 0x01

    def test_quit_explicit_clr_keeps_program_resets_vars(self) -> None:
        """quit_explicit_clr matches stock clearc: keep program, reset var map."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        emu.write_mem(0x002B, 0x01)
        emu.write_mem(0x002C, 0x08)
        emu.write_mem(0x002D, 0x20)
        emu.write_mem(0x002E, 0x08)
        emu.write_mem(0x002F, 0x80)
        emu.write_mem(0x0030, 0x09)
        emu.write_mem(0x0031, 0x90)
        emu.write_mem(0x0032, 0x09)
        emu.write_mem(0x0037, 0x00)
        emu.write_mem(0x0038, 0xA0)
        emu.execute(_load_symbol_address("quit_explicit_clr"), 10_000)
        assert emu.read_mem(0x002B) == 0x01
        assert emu.read_mem(0x002C) == 0x08
        assert emu.read_mem(0x002F) == 0x20
        assert emu.read_mem(0x0030) == 0x08
        assert emu.read_mem(0x0031) == 0x20
        assert emu.read_mem(0x0032) == 0x08
        assert emu.read_mem(0x0033) == 0x00
        assert emu.read_mem(0x0034) == 0xA0
        assert emu.read_mem(0x0016) == 0x19

    @pytest.mark.callable_coverage("resident_assert_boundary", executor="execute_rts")
    @pytest.mark.callable_coverage("georam_select", executor="execute_rts")
    def test_boundary_assertion_checks_port_decimal_and_mirror(self) -> None:
        """resident_assert_boundary should fail when the caller state drifts."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_gr_ctx_sp = _load_zp_address("zp_gr_ctx_sp")
        emu.write_mem(0x0001, 0x35)
        emu.write_mem(zp_gr_ctx_sp, 0x00)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.execute(_load_symbol_address("resident_assert_boundary"), 10_000)
        assert (emu.get_state().p & 0x01) == 0

        emu.write_mem(0x0001, 0x30)
        emu.execute(_load_symbol_address("resident_assert_boundary"), 10_000)
        assert emu.get_state().p & 0x01

        emu.write_mem(0x0001, 0x35)
        emu.set_p(emu.get_state().p | 0x08)
        emu.execute(_load_symbol_address("resident_assert_boundary"), 10_000)
        assert emu.get_state().p & 0x01
