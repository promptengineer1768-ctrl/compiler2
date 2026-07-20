"""Direct real-byte tests for IEEE state management routines."""

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


def _load_zp_address(name: str) -> int:
    """Load zero-page symbol address from allocation."""
    path = ROOT / "build" / "zp_allocation.json"
    if not path.exists():
        pytest.fail("build/zp_allocation.json not found. Run build.ps1 first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    addr_str = data.get("allocation", {}).get(name, "")
    if str(addr_str).startswith("$"):
        return int(addr_str[1:], 16)
    pytest.fail(f"Zero page symbol {name!r} not found in allocation.")


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


def _new_emu() -> C64Emu6502:
    """Load the linked compiler image into a fresh emulator."""
    emu = C64Emu6502(lib_path=_dll_path())
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
        emu.write_mem(0x0001, 0x35)
    emu.set_georam_enabled(True)
    if hasattr(emu, "set_sp"):
        emu.set_sp(0xFF)
    return emu


def _carry_is_set(emu: C64Emu6502) -> bool:
    """Return whether carry is set after a routine call."""
    return bool(int(emu.get_state().p) & 0x01)


def _fac1_bytes(emu: C64Emu6502) -> bytes:
    """Read the five generated FAC1 bytes."""
    base = _load_zp_address("zp_fac1")
    return bytes(emu.read_mem(base + offset) for offset in range(5))


def _linked_bytes(symbol_name: str, length: int) -> bytes:
    """Read linked compiler/HIBASIC bytes for a symbol body."""
    address = _load_symbol_address(symbol_name)
    if address >= 0xE000:
        hibasic = (ROOT / "build" / "hibasic.bin").read_bytes()
        start = address - 0xE000
        if start < 0 or start + length > len(hibasic):
            pytest.fail(f"Symbol {symbol_name!r} is outside build/hibasic.bin.")
        return hibasic[start : start + length]
    bin_path = ROOT / "build" / "compiler.bin"
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    start = address - load_addr + 2
    if start < 2 or start + length > len(payload):
        pytest.fail(f"Symbol {symbol_name!r} is outside build/compiler.bin.")
    return payload[start : start + length]


def _fp_flags_address() -> int:
    """Recover the private FP_FLAGS byte from the linked fp_get_flags body."""
    body = _linked_bytes("fp_get_flags", 3)
    if body[0] == 0x25:  # AND zero-page
        return body[1]
    if body[0] == 0x2D:  # AND absolute
        return body[1] | (body[2] << 8)
    pytest.fail("fp_get_flags no longer reads FP_FLAGS through AND memory.")


@pytest.mark.unit
@pytest.mark.local
class TestFpMode:
    """IEEE floating-point mode management tests."""

    def test_mode_defaults_sets_and_rejects_invalid_without_clobber(self) -> None:
        """Mode starts legacy, valid writes stick, invalid writes set carry."""
        emu = _new_emu()
        emu.execute(_load_symbol_address("fp_get_mode"), 10000)
        assert emu.get_state().a == 0

        emu.set_a(1)
        emu.execute(_load_symbol_address("fp_set_mode"), 10000)
        assert not _carry_is_set(emu)
        emu.execute(_load_symbol_address("fp_get_mode"), 10000)
        assert emu.get_state().a == 1

        emu.set_a(2)
        emu.execute(_load_symbol_address("fp_set_mode"), 10000)
        assert _carry_is_set(emu)
        emu.execute(_load_symbol_address("fp_get_mode"), 10000)
        assert emu.get_state().a == 1


@pytest.mark.unit
@pytest.mark.local
class TestFpFlags:
    """IEEE floating-point flag tests."""

    @pytest.mark.callable_coverage("fp_test_flags", executor="execute_rts")
    def test_flags_mask_clear_and_test(self) -> None:
        """Flag get, clear, and test operate through real mask paths."""
        emu = _new_emu()
        emu.set_a(0xF8)
        emu.execute(_load_symbol_address("fp_get_flags"), 10000)
        assert emu.get_state().a == 0

        flags = _fp_flags_address()
        emu.write_mem(flags, 0xA8)

        emu.set_a(0xF8)
        emu.execute(_load_symbol_address("fp_get_flags"), 10000)
        assert emu.get_state().a == 0xA8

        descriptor = 0x1000
        emu.write_mem(descriptor, 0x80)
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)
        emu.execute(_load_symbol_address("fp_test_flags"), 10000)
        assert emu.get_state().a == 1

        emu.set_a(0x80)
        emu.execute(_load_symbol_address("fp_clear_flags"), 10000)
        emu.set_a(0xF8)
        emu.execute(_load_symbol_address("fp_get_flags"), 10000)
        assert emu.get_state().a == 0x28

        emu.write_mem(descriptor, 0x80)
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)
        emu.execute(_load_symbol_address("fp_test_flags"), 10000)
        assert emu.get_state().a == 0


@pytest.mark.unit
@pytest.mark.local
class TestFpRounding:
    """IEEE floating-point rounding mode tests."""

    @pytest.mark.callable_coverage("fp_set_rounding", executor="execute_rts")
    def test_rounding_accepts_only_four_modes(self) -> None:
        """Rounding mode setter accepts 0..3 and rejects larger IDs."""
        emu = _new_emu()
        addr = _load_symbol_address("fp_set_rounding")
        for mode in (0, 1, 2, 3):
            emu.set_a(mode)
            emu.execute(addr, 10000)
            assert not _carry_is_set(emu)

        emu.set_a(4)
        emu.execute(addr, 10000)
        assert _carry_is_set(emu)


@pytest.mark.unit
@pytest.mark.local
class TestFpConstants:
    """IEEE floating-point constant loading tests."""

    @pytest.mark.parametrize(
        ("constant_id", "expected"),
        [
            (0, bytes([0xFF, 0x80, 0x00, 0x00, 0x00])),
            (1, bytes([0xFF, 0xC0, 0x00, 0x00, 0x00])),
            (2, bytes([0xFF, 0x80, 0x00, 0x00, 0x01])),
            (3, bytes(5)),
        ],
        ids=["inf", "qnan", "snan", "invalid-zero"],
    )
    @pytest.mark.callable_coverage("fp_load_constant", executor="execute_rts")
    def test_fp_load_constant_bytes(self, constant_id: int, expected: bytes) -> None:
        """fp_load_constant writes exact special-constant FAC1 bytes."""
        emu = _new_emu()
        emu.set_a(constant_id)
        emu.execute(_load_symbol_address("fp_load_constant"), 10000)
        assert _fac1_bytes(emu) == expected
