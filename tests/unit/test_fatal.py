"""Unit tests for the resident fatal cleanup path."""

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


@pytest.mark.unit
@pytest.mark.local
class TestFatal:
    """Fatal path behavior tests."""

    @pytest.mark.callable_coverage("fatal_restore_machine", executor="execute_rts")
    def test_restore_machine_returns_to_canonical_state(self) -> None:
        """fatal_restore_machine should reset selection, context, and port."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")
        zp_gr_ctx_sp = _load_zp_address("zp_gr_ctx_sp")
        zp_crsr_vis = _load_zp_address("zp_crsr_vis")

        emu.write_mem(zp_gr_block, 0x04)
        emu.write_mem(zp_gr_page, 0x05)
        emu.write_mem(zp_gr_ctx_sp, 0x03)
        emu.write_mem(zp_crsr_vis, 0x01)
        emu.write_mem(0x0001, 0x30)
        emu.write_mem(0xDFFF, 0x04)
        emu.write_mem(0xDFFE, 0x05)

        emu.execute(_load_symbol_address("fatal_restore_machine"), 10_000)
        assert emu.read_mem(zp_gr_block) == 0x00
        assert emu.read_mem(zp_gr_page) == 0x00
        assert emu.read_mem(zp_gr_ctx_sp) == 0x00
        assert emu.read_mem(zp_crsr_vis) == 0x00
        assert emu.read_mem(0x0001) == 0x35
        assert emu.read_mem(0xDFFF) == 0x00
        assert emu.read_mem(0xDFFE) == 0x00

    @pytest.mark.callable_coverage("fatal_georam", executor="execute_rts")
    def test_fatal_georam_records_reason_and_restores_state(self) -> None:
        """fatal_georam should store the failure metadata and exit cleanly."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")
        fatal_reason = _load_symbol_address("fatal_reason")
        fatal_diag_lo = _load_symbol_address("fatal_diag_lo")
        fatal_diag_hi = _load_symbol_address("fatal_diag_hi")

        emu.write_mem(zp_gr_block, 0x09)
        emu.write_mem(zp_gr_page, 0x0A)
        emu.write_mem(0x0001, 0x30)
        emu.write_mem(0xDFFF, 0x09)
        emu.write_mem(0xDFFE, 0x0A)
        emu.set_a(0x5A)
        emu.set_x(0x12)
        emu.set_y(0x34)

        emu.execute(_load_symbol_address("fatal_georam"), 10_000)
        assert emu.get_state().p & 0x01
        assert emu.read_mem(fatal_reason) == 0x5A
        assert emu.read_mem(fatal_diag_lo) == 0x12
        assert emu.read_mem(fatal_diag_hi) == 0x34
        assert emu.read_mem(zp_gr_block) == 0x00
        assert emu.read_mem(zp_gr_page) == 0x00
        assert emu.read_mem(0x0001) == 0x35
        assert emu.read_mem(0xDFFF) == 0x00
        assert emu.read_mem(0xDFFE) == 0x00
