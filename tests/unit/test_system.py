"""Unit tests for system runtime helpers (system.asm)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from tests.kernal_stubs import install_kernal_stubs

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
PROJECT_TOOLS_ROOT = ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
if str(PROJECT_TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_TOOLS_ROOT))

from numeric.c64float import from_float  # noqa: E402

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
    emu.set_georam_enabled(True)
    payload = (_artifact_root() / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    hibasic = _artifact_root() / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
    # The IO_COLD runtime helpers (fre_init/fre_query/...) link from
    # build/iobasic.bin at $D000 via the production linker config. They must be
    # present in the $D000 window so the runtime routines are real, executable
    # bytes rather than unmapped RAM.
    iobasic = _artifact_root() / "iobasic.bin"
    if iobasic.exists():
        emu.write_mem_range(0xD000, iobasic.read_bytes())
    # ALL_RAM ($01=$30): HIBASIC at $E000+ and the IOBASIC overlay at $D000
    # are both plain RAM, so every runtime routine is reachable.
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x30)
    install_kernal_stubs(emu)


def _load_symbol_address(symbol_name: str) -> int:
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


def _load_map_address(symbol_name: str) -> int:
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
    pytest.fail(f"Label '{symbol_name}' not found.")


def _load_zp_address(symbol_name: str) -> int:
    """Return one generated zero-page allocation."""
    data = json.loads(
        (_artifact_root() / "zp_allocation.json").read_text(encoding="utf-8")
    )
    raw = data["allocation"].get(symbol_name)
    if raw is not None:
        return int(raw[1:], 16)
    symbols = (_artifact_root() / "zp_symbols.inc").read_text(encoding="utf-8")
    match = re.search(
        rf"^{re.escape(symbol_name)}\s*=\s*\$([0-9A-Fa-f]+)$", symbols, re.M
    )
    assert match is not None
    return int(match.group(1), 16)


def _carry_is_set(emu: C64Emu6502) -> bool:
    return (int(emu.get_state().p) & 0x01) != 0


def _carry_is_clear(emu: C64Emu6502) -> bool:
    return (int(emu.get_state().p) & 0x01) == 0


@pytest.mark.unit
@pytest.mark.local
class TestSystem:
    """Runtime system helper tests."""

    def test_peek_poke_sys_usr_wait(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        peek_addr = _load_symbol_address("system_peek")
        poke_addr = _load_symbol_address("system_poke")
        sys_addr = _load_symbol_address("system_sys")
        usr_addr = _load_symbol_address("system_usr")
        wait_addr = _load_symbol_address("system_wait")
        last_sys = _load_map_address("system_last_sys")

        emu.write_mem(0x0400, 0x5A)
        emu.set_x(0x00)
        emu.set_y(0x04)
        emu.execute(peek_addr, 10000)
        assert emu.get_state().a == 0x5A

        emu.set_a(0xA5)
        emu.set_x(0x00)
        emu.set_y(0x04)
        emu.execute(poke_addr, 10000)
        assert emu.read_mem(0x0400) == 0xA5
        assert _carry_is_clear(emu)

        # High-guard vector tail is protected; ordinary image RAM is not.
        protected_address = 0xFFF9
        protected_original = emu.read_mem(protected_address)
        emu.set_a(0x99)
        emu.set_x(protected_address & 0xFF)
        emu.set_y(protected_address >> 8)
        emu.execute(poke_addr, 10000)
        assert emu.read_mem(protected_address) == protected_original
        assert _carry_is_set(emu)

        # Standalone code range remains user-writable (narrow control-plane).
        image_addr = 0x0801
        emu.set_a(0x5A)
        emu.set_x(image_addr & 0xFF)
        emu.set_y(image_addr >> 8)
        emu.execute(poke_addr, 10000)
        assert emu.read_mem(image_addr) == 0x5A
        assert _carry_is_clear(emu)

        emu.write_mem(0x0340, 0)
        emu.write_mem_range(0x0330, b"\xee\x40\x03\x60")
        emu.set_x(0x30)
        emu.set_y(0x03)
        emu.execute(sys_addr, 10000)
        assert emu.read_mem(last_sys) == 0x30
        assert emu.read_mem(last_sys + 1) == 0x03
        assert emu.read_mem(0x0340) == 1
        assert _carry_is_clear(emu)

        fac = _load_zp_address("zp_fac1")
        emu.write_mem(fac, 9)
        emu.write_mem_range(0x0310, b"\x4c\x30\x03")
        emu.write_mem_range(0x0330, bytes([0xEE, fac, 0x00, 0x60]))
        emu.execute(usr_addr, 10000)
        assert emu.read_mem(fac) == 10
        assert _carry_is_clear(emu)
        emu.write_mem(0x0400, 0x80)
        emu.write_mem_range(0x0350, b"SW\x00\x04\x80\x00")
        emu.set_x(0x50)
        emu.set_y(0x03)
        emu.execute(wait_addr, 10000)
        assert _carry_is_clear(emu)

        emu.write_mem(0x0400, 0x80)
        emu.write_mem_range(0x0350, b"SW\x00\x04\x80\x80")
        emu.write_mem(_load_zp_address("zp_stkey"), 0)
        emu.set_x(0x50)
        emu.set_y(0x03)
        emu.execute(wait_addr, 10000)
        assert _carry_is_set(emu)

    def test_ti_clock_and_string_helpers(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        ti_load = _load_symbol_address("system_ti_load")
        ti_store = _load_symbol_address("system_ti_store")
        ti_string_load = _load_symbol_address("system_ti_string_load")
        ti_string_store = _load_symbol_address("system_ti_string_store")
        ti_clock = _load_zp_address("zp_time")
        emu.execute(_load_symbol_address("arena_init_all"), 100_000)
        descriptor = 0x0600
        request = 0x0620
        buffer = 0x0640
        emu.write_mem_range(descriptor, bytes(12))

        initial = (12 * 3600 + 34 * 60 + 56) * 60
        emu.set_a(initial & 0xFF)
        emu.set_x((initial >> 8) & 0xFF)
        emu.set_y((initial >> 16) & 0xFF)
        emu.execute(ti_store, 10000)
        emu.execute(ti_load, 10000)
        fac = _load_zp_address("zp_fac1")
        assert emu.read_mem_range(fac, fac + 4) == from_float(float(initial)).to_bytes()

        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)
        emu.execute(ti_string_load, 100_000)
        assert _carry_is_clear(emu)
        emu.write_mem_range(
            request,
            b"SE"
            + descriptor.to_bytes(2, "little")
            + buffer.to_bytes(2, "little")
            + b"\x06",
        )
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)
        emu.execute(_load_symbol_address("str_export_bytes"), 100_000)
        assert emu.get_state().a == 6
        assert emu.read_mem_range(buffer, buffer + 5) == b"123456"

        emu.write_mem_range(buffer, b"235959")
        emu.write_mem_range(
            request,
            b"SB"
            + descriptor.to_bytes(2, "little")
            + buffer.to_bytes(2, "little")
            + b"\x06",
        )
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)
        emu.execute(_load_symbol_address("str_from_bytes"), 100_000)
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)
        emu.execute(ti_string_store, 100_000)
        expected = (23 * 3600 + 59 * 60 + 59) * 60
        assert emu.read_mem(ti_clock + 2) == (expected & 0xFF)
        assert emu.read_mem(ti_clock + 1) == ((expected >> 8) & 0xFF)
        assert emu.read_mem(ti_clock) == ((expected >> 16) & 0xFF)
        assert _carry_is_clear(emu)

        before = bytes(emu.read_mem(ti_clock + offset) for offset in range(3))
        emu.write_mem_range(buffer, b"240000")
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)
        emu.execute(_load_symbol_address("str_from_bytes"), 100_000)
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)
        emu.execute(ti_string_store, 100_000)
        assert _carry_is_set(emu)
        assert bytes(emu.read_mem(ti_clock + offset) for offset in range(3)) == before

    @pytest.mark.parametrize(
        ("address", "protected"),
        [
            (0x0800, False),
            (0x0001, False),
            (0x0002, True),
            (0x001D, True),
            (0x001E, False),
            (0x0801, False),
            (0xC800, False),
            (0xCFFF, False),
            (0xCE00, False),
            (0xD000, False),
            (0xFFF8, False),
            (0xFFF9, True),
            (0xFFFF, True),
        ],
        ids=[
            "below-image",
            "cpu-port",
            "compiler-zp-first",
            "compiler-zp-last",
            "after-compiler-zp",
            "image-first-writable",
            "hot-slot-writable",
            "image-last-writable",
            "ce00-without-xip",
            "io-first",
            "below-high-guard",
            "high-guard-first",
            "vector-last",
        ],
    )
    def test_poke_uses_generated_protected_boundaries(
        self, address: int, protected: bool
    ) -> None:
        """POKE uses narrow control-plane: ZP + high guard; not blanket image."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        original = emu.read_mem(address)
        emu.set_a(original ^ 0xFF)
        emu.set_x(address & 0xFF)
        emu.set_y(address >> 8)
        emu.execute(_load_symbol_address("system_poke"), 10000)
        assert _carry_is_set(emu) is protected
        if protected:
            assert emu.read_mem(address) == original
        else:
            assert emu.read_mem(address) == (original ^ 0xFF)

    def test_poke_protects_ce00_when_reu_xip_active(self) -> None:
        """$CE00 is protected only while reu_xip_active is set."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        xip = _load_map_address("reu_xip_active")
        poke = _load_symbol_address("system_poke")
        target = 0xCE40
        original = emu.read_mem(target)

        emu.write_mem(xip, 1)
        emu.set_a(original ^ 0xFF)
        emu.set_x(target & 0xFF)
        emu.set_y(target >> 8)
        emu.execute(poke, 10000)
        assert _carry_is_set(emu)
        assert emu.read_mem(target) == original

        emu.write_mem(xip, 0)
        emu.set_a(original ^ 0xFF)
        emu.set_x(target & 0xFF)
        emu.set_y(target >> 8)
        emu.execute(poke, 10000)
        assert _carry_is_clear(emu)
        assert emu.read_mem(target) == (original ^ 0xFF)

    def test_fre_profile_expansion_and_export(self) -> None:
        """fre_query reports expansion page free vs export free bytes."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        fac = _load_zp_address("zp_fac1")
        fre_query = _load_symbol_address("fre_query")
        fre_set_profile = _load_symbol_address("fre_set_profile")
        fre_set_export = _load_symbol_address("fre_set_export_bytes")

        emu.execute(_load_symbol_address("fre_init"), 10000)
        emu.execute(_load_symbol_address("page_alloc_init"), 100_000)
        emu.execute(fre_query, 100_000)
        assert _carry_is_clear(emu)
        # 2048 free pages * 256 = 524288 → float exponent/mantissa non-zero.
        assert emu.read_mem(fac) != 0

        emu.set_a(0)
        emu.execute(fre_set_profile, 10000)
        emu.set_a(0x10)
        emu.set_x(0x27)
        emu.set_y(0x00)  # 10000 bytes
        emu.execute(fre_set_export, 10000)
        emu.execute(fre_query, 100_000)
        assert _carry_is_clear(emu)
        assert emu.read_mem_range(fac, fac + 4) == from_float(10000.0).to_bytes()
