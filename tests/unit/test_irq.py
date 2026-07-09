"""Unit tests for the pinned resident IRQ helpers."""

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
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])


def _linked_bytes(address: int, length: int) -> bytes:
    """Return linked compiler bytes for an absolute memory address range."""
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    offset = address - load_addr
    if offset < 0 or offset + length > len(payload) - 2:
        pytest.fail(f"Address ${address:04X} is outside build/compiler.bin")
    return payload[2 + offset : 2 + offset + length]


@pytest.mark.unit
@pytest.mark.local
class TestIrq:
    """IRQ entry and helper tests."""

    def test_irq_helpers_update_visible_state(self) -> None:
        """IRQ helper routines should advance clock and cursor state."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_time = _load_zp_address("zp_time")
        zp_crsr_vis = _load_zp_address("zp_crsr_vis")
        zp_ndx = _load_zp_address("zp_ndx")
        zp_lstx = _load_zp_address("zp_lstx")
        zp_crsr_x = _load_zp_address("zp_crsr_x")

        emu.write_mem(zp_time, 0xFE)
        emu.write_mem(zp_time + 1, 0x00)
        emu.write_mem(zp_time + 2, 0x00)
        emu.write_mem(zp_crsr_vis, 0x00)
        emu.write_mem(zp_ndx, 0x03)
        emu.write_mem(zp_crsr_x, 0x44)

        emu.execute(_load_symbol_address("irq_update_jiffy"), 10_000)
        assert emu.read_mem(zp_time) == 0xFF

        emu.execute(_load_symbol_address("irq_cursor_blink"), 10_000)
        assert emu.read_mem(zp_crsr_vis) == 0x01

        emu.execute(_load_symbol_address("irq_scan_keyboard"), 10_000)
        assert emu.read_mem(zp_lstx) == 0x44
        assert emu.read_mem(zp_ndx) == 0x04

    def test_irq_restore_mapping_writes_saved_port(self) -> None:
        """irq_restore_mapping should write the supplied mapping byte to $01."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        emu.write_mem(0x0001, 0x30)
        emu.set_a(0x35)
        emu.execute(_load_symbol_address("irq_restore_mapping"), 10_000)
        assert emu.read_mem(0x0001) == 0x35

    def test_irq_entry_restores_cpu_port_and_updates_helpers(self) -> None:
        """irq_entry should preserve mapping and call the resident helpers."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_time = _load_zp_address("zp_time")
        zp_crsr_vis = _load_zp_address("zp_crsr_vis")
        zp_ndx = _load_zp_address("zp_ndx")
        zp_lstx = _load_zp_address("zp_lstx")
        zp_crsr_x = _load_zp_address("zp_crsr_x")

        emu.write_mem(0x0001, 0x35)
        emu.write_mem(zp_time, 0x00)
        emu.write_mem(zp_crsr_vis, 0x00)
        emu.write_mem(zp_ndx, 0x00)
        emu.write_mem(zp_crsr_x, 0x21)
        state = emu.get_state()
        emu.set_p(state.p & ~0x04)

        emu.execute(_load_symbol_address("irq_entry"), 10_000)
        assert emu.read_mem(0x0001) == 0x35
        assert emu.read_mem(zp_crsr_vis) == 0x01
        assert emu.read_mem(zp_ndx) == 0x01
        assert emu.read_mem(zp_lstx) == 0x21
        assert emu.read_mem(zp_time) == 0x01

    def test_irq_entry_linked_body_uses_hardware_return_contract(self) -> None:
        """irq_entry must select KERNAL+I/O and return through RTI."""
        body = _linked_bytes(_load_symbol_address("irq_entry"), 96)
        rti_offset = body.find(b"\x40")

        assert b"\xa9\x36\x85\x01" in body, "irq_entry must select $01=$36"
        assert rti_offset >= 0, "irq_entry must return with RTI"
        assert b"\x60" not in body[: rti_offset + 1], "RTS is not valid for IRQ entry"

    def test_irq_kernal_helpers_call_rom_vectors_directly(self) -> None:
        """IRQ helpers must not enter the serialized foreground KERNAL bridge."""
        udtim_body = _linked_bytes(_load_symbol_address("irq_update_jiffy"), 4)
        scnkey_body = _linked_bytes(_load_symbol_address("irq_scan_keyboard"), 4)

        assert udtim_body == b"\x20\xea\xff\x60"
        assert scnkey_body == b"\x20\x9f\xff\x60"
