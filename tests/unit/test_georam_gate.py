"""Unit tests for geoRAM gate and context stack helpers."""

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
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.set_georam_enabled(True)


def _write_descriptor(
    emu: C64Emu6502,
    base: int,
    offset: int,
    page: int,
    length: int = 0,
    ptr: int = 0,
    value: int = 0,
) -> None:
    emu.set_x(base & 0xFF)
    emu.set_y((base >> 8) & 0xFF)
    emu.write_mem(base, offset & 0xFF)
    emu.write_mem(base + 1, page & 0xFF)
    emu.write_mem(base + 2, length & 0xFF)
    emu.write_mem(base + 3, ptr & 0xFF)
    emu.write_mem(base + 4, (ptr >> 8) & 0xFF)
    emu.write_mem(base + 5, value & 0xFF)
    emu.write_mem(base + 6, (value >> 8) & 0xFF)


@pytest.mark.unit
@pytest.mark.local
class TestContextStack:
    """Context stack round-trip and overflow tests."""

    def test_round_trip_and_depth(self) -> None:
        """ctx_push/ctx_pop should preserve the selected block/page pair."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")
        zp_gr_ctx_sp = _load_zp_address("zp_gr_ctx_sp")

        emu.execute(_load_symbol_address("ctx_init"), 10_000)
        emu.write_mem(zp_gr_block, 0x03)
        emu.write_mem(zp_gr_page, 0x07)
        emu.execute(_load_symbol_address("ctx_push"), 10_000)
        assert emu.read_mem(zp_gr_ctx_sp) == 0x01

        emu.write_mem(zp_gr_block, 0x09)
        emu.write_mem(zp_gr_page, 0x0B)
        emu.execute(_load_symbol_address("ctx_pop"), 10_000)
        assert emu.read_mem(zp_gr_block) == 0x03
        assert emu.read_mem(zp_gr_page) == 0x07
        assert emu.read_mem(zp_gr_ctx_sp) == 0x00
        emu.execute(_load_symbol_address("ctx_depth"), 10_000)
        assert emu.get_state().a == 0x00

    def test_overflow_is_reported(self) -> None:
        """ctx_check_overflow should report a full stack."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")

        emu.execute(_load_symbol_address("ctx_init"), 10_000)
        for idx in range(8):
            emu.write_mem(zp_gr_block, idx)
            emu.write_mem(zp_gr_page, idx + 1)
            emu.execute(_load_symbol_address("ctx_push"), 10_000)
        emu.execute(_load_symbol_address("ctx_check_overflow"), 10_000)
        assert emu.get_state().p & 0x01


@pytest.mark.unit
@pytest.mark.local
class TestHibasicGraphicsSwap:
    """Resident HIBASIC backing-store lifecycle tests."""

    def test_reserve_and_restore_round_trip_real_bytes(self) -> None:
        """The resident mover preserves every occupied HIBASIC byte."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        hibasic = (ROOT / "build" / "hibasic.bin").read_bytes()
        emu.write_mem_range(0xE000, hibasic)

        emu.execute(_load_symbol_address("hibasic_graphics_reserve"), 200000)
        emu.write_mem_range(0xE000, b"\xa5" * len(hibasic))
        emu.execute(_load_symbol_address("hibasic_graphics_restore"), 200000)

        restored = bytes(emu.read_mem(0xE000 + i) for i in range(len(hibasic)))
        assert restored == hibasic

    def test_restore_is_lazy_and_idempotent(self) -> None:
        """A restore without an active graphics reservation changes nothing."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        sentinel = bytes(range(64))
        emu.write_mem_range(0xE000, sentinel)

        emu.execute(_load_symbol_address("hibasic_graphics_restore"), 10000)

        assert bytes(emu.read_mem(0xE000 + i) for i in range(64)) == sentinel


class TestGeoramGate:
    """geoRAM gate helpers and handle-based access tests."""

    def test_gate_context_pop_restores_hardware_selection(self) -> None:
        """georam_ctx_pop restores mirrored and hardware page selection."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        block = _load_zp_address("zp_gr_block")
        page = _load_zp_address("zp_gr_page")
        emu.execute_rts(_load_symbol_address("ctx_init"), 10_000)
        emu.write_mem(block, 3)
        emu.write_mem(page, 7)
        emu.execute_rts(_load_symbol_address("georam_ctx_push"), 10_000)
        emu.write_mem(block, 9)
        emu.write_mem(page, 11)
        emu.execute_rts(_load_symbol_address("georam_ctx_pop"), 10_000)
        assert (emu.read_mem(block), emu.read_mem(page)) == (3, 7)
        assert (emu.read_mem(0xDFFF), emu.read_mem(0xDFFE)) == (3, 7)

    def test_direct_word_and_byte_access_use_selected_page(self) -> None:
        """Handle primitives read and write real assembled geoRAM bytes."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.set_a(7)
        emu.set_x(0)
        emu.execute_rts(_load_symbol_address("georam_select"), 10_000)
        descriptor = 0xC100
        _write_descriptor(emu, descriptor, offset=0x20, page=7, value=0xBBAA)
        emu.execute_rts(_load_symbol_address("georam_write_word"), 10_000)
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)
        emu.execute_rts(_load_symbol_address("georam_read_word"), 10_000)
        state = emu.get_state()
        assert (state.a, state.x) == (0xAA, 0xBB)
        _write_descriptor(emu, descriptor, offset=0x22, page=7, value=0x5A)
        emu.execute_rts(_load_symbol_address("georam_write_byte"), 10_000)
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)
        emu.execute_rts(_load_symbol_address("georam_read_byte"), 10_000)
        assert emu.get_state().a == 0x5A

    def test_select_and_mirror_check(self) -> None:
        """georam_select should update the mirror and verification helper."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")

        emu.set_x(0x02)
        emu.set_a(0x05)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        assert emu.read_mem(zp_gr_block) == 0x02
        assert emu.read_mem(zp_gr_page) == 0x05
        assert emu.read_mem(0xDFFF) == 0x02
        assert emu.read_mem(0xDFFE) == 0x05
        emu.execute(_load_symbol_address("georam_verify_mirror"), 10_000)
        assert (emu.get_state().p & 0x01) == 0

    def test_nested_call_cycle_preserves_caller_state(self) -> None:
        """georam_call_group_n should run the directory target and restore selection."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        directory = json.loads(
            (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
        )
        target = directory["routines"]["wedge_parse"]
        target_index = target["id"] & 0xFF

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")
        zp_gr_ctx_sp = _load_zp_address("zp_gr_ctx_sp")

        emu.execute(_load_symbol_address("ctx_init"), 10_000)
        emu.set_x(target["block"])
        emu.set_a(target["page"])
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.write_mem_range(
            0xDE00 + target["offset"],
            bytes([0xA9, 0x42, 0xA2, 0x77, 0xA0, 0x88, 0x18, 0x60]),
        )

        emu.set_x(0x04)
        emu.set_a(0x01)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.set_x(target_index)
        emu.execute(_load_symbol_address("georam_call_group_n"), 10_000)
        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert state.a == 0x42
        assert state.x == 0x77
        assert state.y == 0x88
        assert emu.read_mem(zp_gr_ctx_sp) == 0x00
        assert emu.read_mem(zp_gr_block) == 0x04
        assert emu.read_mem(zp_gr_page) == 0x01
        assert emu.read_mem(0xDFFF) == 0x04
        assert emu.read_mem(0xDFFE) == 0x01

    def test_missing_directory_entry_restores_selection_and_reports_error(self) -> None:
        """A missing generated directory entry should fail without leaking context."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")
        zp_gr_ctx_sp = _load_zp_address("zp_gr_ctx_sp")

        emu.execute(_load_symbol_address("ctx_init"), 10_000)
        emu.set_x(0x04)
        emu.set_a(0x01)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.set_x(0x00)
        emu.execute(_load_symbol_address("georam_call_group_n"), 10_000)

        state = emu.get_state()
        assert state.p & 0x01
        assert state.a == 0x00
        assert state.x == 0x00
        assert state.y == 0x00
        assert emu.read_mem(zp_gr_ctx_sp) == 0x00
        assert emu.read_mem(zp_gr_block) == 0x04
        assert emu.read_mem(zp_gr_page) == 0x01
        assert emu.read_mem(0xDFFF) == 0x04
        assert emu.read_mem(0xDFFE) == 0x01

    def test_tail_group_jumps_to_directory_target_and_reuses_frame(self) -> None:
        """georam_tail_group_n should jump to the target instead of aliasing call."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        directory = json.loads(
            (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
        )
        target = directory["routines"]["wedge_parse"]
        target_index = target["id"] & 0xFF

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")
        zp_gr_ctx_sp = _load_zp_address("zp_gr_ctx_sp")

        emu.execute(_load_symbol_address("ctx_init"), 10_000)
        emu.set_x(0x04)
        emu.set_a(0x01)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.execute(_load_symbol_address("georam_ctx_push"), 10_000)
        assert emu.read_mem(zp_gr_ctx_sp) == 0x01

        emu.set_x(target["block"])
        emu.set_a(target["page"])
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.write_mem_range(
            0xDE00 + target["offset"],
            bytes([0xA9, 0x33, 0xA2, 0x44, 0xA0, 0x55, 0x18, 0x60]),
        )

        emu.set_x(0x04)
        emu.set_a(0x01)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.set_x(target_index)
        emu.execute(_load_symbol_address("georam_tail_group_n"), 10_000)

        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert state.a == 0x33
        assert state.x == 0x44
        assert state.y == 0x55
        assert emu.read_mem(zp_gr_ctx_sp) == 0x00
        assert emu.read_mem(zp_gr_block) == target["block"]
        assert emu.read_mem(zp_gr_page) == target["page"]
        assert emu.read_mem(0xDFFF) == target["block"]
        assert emu.read_mem(0xDFFE) == target["page"]

    def test_tail_group_missing_entry_preserves_frame_and_selection(self) -> None:
        """Missing tail targets should fail before consuming the current frame."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")
        zp_gr_ctx_sp = _load_zp_address("zp_gr_ctx_sp")

        emu.execute(_load_symbol_address("ctx_init"), 10_000)
        emu.set_x(0x04)
        emu.set_a(0x01)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.execute(_load_symbol_address("georam_ctx_push"), 10_000)

        emu.set_x(0x00)
        emu.execute(_load_symbol_address("georam_tail_group_n"), 10_000)

        state = emu.get_state()
        assert state.p & 0x01
        assert state.a == 0x00
        assert state.x == 0x00
        assert state.y == 0x00
        assert emu.read_mem(zp_gr_ctx_sp) == 0x01
        assert emu.read_mem(zp_gr_block) == 0x04
        assert emu.read_mem(zp_gr_page) == 0x01
        assert emu.read_mem(0xDFFF) == 0x04
        assert emu.read_mem(0xDFFE) == 0x01

    def test_handle_based_byte_and_copy_operations_validate_page(self) -> None:
        """Handle-based reads, writes, copies, and checksum should round-trip."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_gr_page = _load_zp_address("zp_gr_page")
        emu.execute(_load_symbol_address("ctx_init"), 10_000)
        emu.set_a(0x07)
        emu.set_x(0x00)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        assert emu.read_mem(zp_gr_page) == 0x07

        source = b"GEOR"
        source_addr = 0xC200
        dest_addr = 0xC240
        emu.write_mem_range(source_addr, source)

        desc = 0xC100
        _write_descriptor(
            emu, desc, offset=0x20, page=0x07, ptr=source_addr, length=len(source)
        )
        emu.execute(_load_symbol_address("georam_copy_from_ram"), 10_000)
        assert (emu.get_state().p & 0x01) == 0

        _write_descriptor(
            emu, desc + 16, offset=0x20, page=0x07, ptr=dest_addr, length=4
        )
        emu.execute(_load_symbol_address("georam_copy_to_ram"), 10_000)
        assert emu.read_mem_range(dest_addr, dest_addr + 3) == source

        _write_descriptor(emu, desc + 32, offset=0x20, page=0x07, length=4)
        emu.execute(_load_symbol_address("georam_checksum"), 10_000)
        state = emu.get_state()
        checksum = sum(source) & 0xFFFF
        assert state.a == (checksum & 0xFF)
        assert state.x == ((checksum >> 8) & 0xFF)

        _write_descriptor(emu, desc + 48, offset=0x20, page=0x06, value=0xA5)
        emu.execute(_load_symbol_address("georam_write_byte"), 10_000)
        assert emu.get_state().p & 0x01

    def test_copy_pages_copies_between_georam_pages_and_restores_selection(
        self,
    ) -> None:
        """georam_copy_pages should copy via the real geoRAM window."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_gr_page = _load_zp_address("zp_gr_page")
        emu.execute(_load_symbol_address("ctx_init"), 10_000)
        emu.set_a(0x09)
        emu.set_x(0x00)
        emu.execute(_load_symbol_address("georam_select"), 10_000)

        source = b"COPY"
        source_ram = 0xC280
        desc = 0xC100
        source_desc = desc
        dest_desc = desc + 16
        emu.write_mem_range(source_ram, source)
        _write_descriptor(
            emu,
            source_desc,
            offset=0x30,
            page=0x09,
            length=len(source),
            ptr=source_ram,
        )
        emu.execute(_load_symbol_address("georam_copy_from_ram"), 10_000)
        assert (emu.get_state().p & 0x01) == 0

        _write_descriptor(emu, dest_desc, offset=0x50, page=0x0A)
        _write_descriptor(
            emu,
            source_desc,
            offset=0x30,
            page=0x09,
            length=len(source),
            ptr=dest_desc,
        )
        emu.execute(_load_symbol_address("georam_copy_pages"), 10_000)
        assert (emu.get_state().p & 0x01) == 0
        assert emu.read_mem(zp_gr_page) == 0x09
        assert emu.read_mem(0xDFFE) == 0x09

        dest_ram = 0xC2C0
        emu.set_a(0x0A)
        emu.set_x(0x00)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        _write_descriptor(
            emu,
            desc + 32,
            offset=0x50,
            page=0x0A,
            length=len(source),
            ptr=dest_ram,
        )
        emu.execute(_load_symbol_address("georam_copy_to_ram"), 10_000)
        assert emu.read_mem_range(dest_ram, dest_ram + len(source) - 1) == source
