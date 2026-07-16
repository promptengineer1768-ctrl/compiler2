"""Integration test for the full geoRAM call cycle."""

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


def _load_georam_image(emu: C64Emu6502) -> None:
    """Load the built geoRAM PRG payload into the emulator backing store."""
    image_path = ROOT / "build" / "georam.bin"
    if not image_path.exists():
        pytest.fail("build/georam.bin not found. Run build.ps1 first.")
    image = image_path.read_bytes()
    assert image[:2] == b"\x00\xde"
    emu.load_georam(image[2:])


@pytest.mark.integration
@pytest.mark.local
@pytest.mark.smoke
class TestGeoramCycle:
    """Integration coverage for nested geoRAM selection."""

    def test_full_call_cycle_restores_the_caller_selection(self) -> None:
        """A directory-dispatched geoRAM call should restore selection and depth."""
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
        emu.set_a(target["page"])
        emu.set_x(target["block"])
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.write_mem_range(
            0xDE00 + target["offset"],
            bytes([0xA9, 0x5A, 0xA2, 0x34, 0xA0, 0x12, 0x18, 0x60]),
        )

        emu.set_a(0x01)
        emu.set_x(0x02)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.set_x(target_index)
        emu.execute(_load_symbol_address("georam_call_group_n"), 10_000)
        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert state.a == 0x5A
        assert state.x == 0x34
        assert state.y == 0x12
        assert emu.read_mem(zp_gr_ctx_sp) == 0x00
        assert emu.read_mem(zp_gr_block) == 0x02
        assert emu.read_mem(zp_gr_page) == 0x01
        assert emu.read_mem(0xDFFF) == 0x02
        assert emu.read_mem(0xDFFE) == 0x01

    def test_built_georam_image_executes_through_hardware_window(self) -> None:
        """The generated page image should contain executable linked routine bytes."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        _load_georam_image(emu)

        directory = json.loads(
            (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
        )
        target = directory["routines"]["wedge_parse"]

        # Use free high RAM above the linked normal-RAM image (RODATA ends
        # below $C800). wedge_parse requires a NUL-terminated direct-mode
        # buffer; bare "$" must not leave a non-zero trailing byte.
        command = 0xCF00
        emu.write_mem_range(command, bytes([ord("$"), 0x00]))
        emu.execute(_load_symbol_address("ctx_init"), 10_000)
        emu.set_a(target["page"])
        emu.set_x(target["block"])
        emu.execute(_load_symbol_address("georam_select"), 10_000)

        emu.set_x(command & 0xFF)
        emu.set_y((command >> 8) & 0xFF)
        emu.execute(0xDE00 + target["offset"], 10_000)

        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert state.a == 0x00
