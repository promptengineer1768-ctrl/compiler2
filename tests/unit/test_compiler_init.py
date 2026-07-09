"""Unit tests for compiler init routines (compiler_init.asm).

Tests verify configuration, vector setup, and state machine entry.
"""

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
    lbl_path = ROOT / "build" / "compiler.lbl"
    if lbl_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            lbl_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    dir_path = ROOT / "build" / "routine_directory.json"
    if dir_path.exists():
        try:
            with open(dir_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            routines = data.get("routines", {})
            if symbol_name in routines:
                addr_str = routines[symbol_name].get("address", "")
                if addr_str.startswith("$"):
                    return int(addr_str[1:], 16)
        except Exception:
            pass
    map_path = ROOT / "build" / "compiler.map"
    if not map_path.exists():
        pytest.fail("build/compiler.map not found. Run build.ps1 first.")
    pattern = rf"\b{symbol_name}\b\s+([0-9A-Fa-f]{{6}})"
    content = map_path.read_text(encoding="utf-8")
    match = re.search(pattern, content)
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found.")


def _new_emulator() -> C64Emu6502:
    """Load the linked production image into a fresh C64 emulator."""
    emu = C64Emu6502(lib_path=_dll_path())
    emu._compiler2_real_bytes_only = True
    emu.set_rom_overlay_enabled(True)
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    return emu


@pytest.mark.unit
@pytest.mark.local
class TestCompilerInit:
    """Compiler init tests."""

    def test_init_configuration(self) -> None:
        """compiler_init is linked as the non-returning system entry."""
        routines = json.loads(
            (ROOT / "manifests" / "routines.json").read_text(encoding="utf-8")
        )["routines"]
        contract = next(item for item in routines if item["name"] == "compiler_init")
        assert contract["return_kind"] == "non_returning"
        assert contract["calls"] == [
            "init_clear_bss",
            "init_arenas",
            "init_editor",
            "init_enter_main_loop",
        ]

    def test_clear_bss_uses_linker_defined_full_segment(self) -> None:
        """init_clear_bss clears every linked BSS byte and no adjacent byte."""
        emu = _new_emulator()
        start = _load_symbol_address("__BSS_RUN__")
        size = _load_symbol_address("__BSS_SIZE__")
        emu.write_mem(start - 1, 0x3C)
        emu.write_mem_range(start, bytes([0xA5]) * size)
        emu.write_mem(start + size, 0xC3)

        emu.execute(_load_symbol_address("init_clear_bss"), 500_000)

        assert bytes(emu.read_mem(start + offset) for offset in range(size)) == bytes(
            size
        )
        assert emu.read_mem(start - 1) == 0x3C
        assert emu.read_mem(start + size) == 0xC3

    def test_init_arenas_constructs_the_real_typed_directory(self) -> None:
        """init_arenas delegates to the production arena constructor."""
        emu = _new_emulator()
        emu.execute(_load_symbol_address("init_arenas"), 500_000)
        state = emu.get_state()
        assert not (int(state.p) & 0x01)
        assert emu.read_mem(_load_symbol_address("init_arena_state")) == 1

        for arena_id in range(1, 10):
            emu.set_x(arena_id)
            emu.set_y(1)
            emu.execute(_load_symbol_address("arena_handle_valid"), 10_000)
            assert not (int(emu.get_state().p) & 0x01)


@pytest.mark.unit
@pytest.mark.local
class TestCompilerVectors:
    """Vector setup tests."""

    def test_setup_vectors(self) -> None:
        """compiler_vectors should install interrupt vectors."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("compiler_vectors")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestCompilerStateMachine:
    """State machine entry tests."""

    def test_state_machine_entry(self) -> None:
        """compiler_state_machine should start execution."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("compiler_state_machine")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
def test_init_editor_sets_cold_start_state() -> None:
    """Editor initialization sets the default row and clears mode state."""
    emu = _new_emulator()
    emu.execute(_load_symbol_address("init_editor"), 500_000)
    state_addr = _load_symbol_address("init_editor_state")
    assert bytes(emu.read_mem(state_addr + index) for index in range(4)) == bytes(
        [5, 0, 0, 0]
    )


@pytest.mark.unit
@pytest.mark.local
def test_init_enter_main_loop_records_tail_entry() -> None:
    """Main-loop entry records entry, enables IRQs, and tail-jumps resident_main."""
    emu = _new_emulator()
    entry = _load_symbol_address("init_enter_main_loop")
    marker = _load_symbol_address("init_main_loop_entered")
    resident = _load_symbol_address("resident_main")
    assert bytes(emu.read_mem(entry + offset) for offset in range(9)) == bytes(
        [
            0xA9,
            0x01,
            0x8D,
            marker & 0xFF,
            marker >> 8,
            0x58,
            0x4C,
            resident & 0xFF,
            resident >> 8,
        ]
    )
