"""Unit tests for the resident main loop."""

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
        zp_gr_page = _load_zp_address("zp_gr_page")
        resident_input = _load_symbol_address("resident_input_byte")

        buffer_addr = 0xC000
        emu.write_mem(zp_quotemode, 0x00)
        emu.write_mem(0x0001, 0x35)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.write_mem(zp_linebuf, buffer_addr & 0xFF)
        emu.write_mem(zp_linebuf + 1, buffer_addr >> 8)
        emu.write_mem(resident_input, 0x41)
        emu.write_mem_range(0x0400, b"READY" + b" " * 35)

        emu.execute(_load_symbol_address("resident_poll_input"), 10_000)
        assert emu.get_state().a == 0x41
        emu.execute(_load_symbol_address("resident_submit_line"), 10_000)
        assert emu.read_mem(resident_input) == 0x00
        assert emu.read_mem(zp_line_len) == 0x05
        assert emu.read_mem_range(buffer_addr, buffer_addr + 4) == b"READY"
        assert emu.read_mem(zp_gr_block) == 0x00
        assert emu.read_mem(zp_gr_page) == 0x00

    def test_resident_main_is_linked_as_non_returning_loop(self) -> None:
        """resident_main should loop back to itself instead of returning."""
        resident_main = _load_symbol_address("resident_main")
        resident_poll_input = _load_symbol_address("resident_poll_input")
        body = _linked_bytes(resident_main, 16)

        assert body[:3] == bytes(
            [0x20, resident_poll_input & 0xFF, resident_poll_input >> 8]
        )
        assert bytes([0x4C, resident_main & 0xFF, resident_main >> 8]) in body
        assert 0x60 not in body

    def test_submit_line_hands_off_to_generated_editor_service(self) -> None:
        """resident_submit_line should dispatch through the generated geoRAM gate."""
        resident_submit_line = _load_symbol_address("resident_submit_line")
        georam_call_group_n = _load_symbol_address("georam_call_group_n")
        body = _linked_bytes(resident_submit_line, 32)

        assert (
            bytes([0x20, georam_call_group_n & 0xFF, georam_call_group_n >> 8]) in body
        )

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
