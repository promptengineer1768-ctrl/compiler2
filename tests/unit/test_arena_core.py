"""Real-byte tests for the typed GeoRAM arena directory."""

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

MAX_CYCLES = 500_000


def _dll_path() -> Path:
    path = TOOLS_ROOT / "emu6502.dll"
    if not path.exists():
        path = TOOLS_ROOT / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _load_symbol_address(symbol_name: str) -> int:
    directory = ROOT / "build" / "routine_directory.json"
    if directory.exists():
        data = json.loads(directory.read_text(encoding="utf-8"))
        routine = data.get("routines", {}).get(symbol_name)
        if routine:
            address = routine.get("address", "")
            if isinstance(address, str) and address.startswith("$"):
                return int(address[1:], 16)
    labels = ROOT / "build" / "compiler.lbl"
    if labels.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found in linked labels.")


def _new_emulator() -> C64Emu6502:
    emu = C64Emu6502(lib_path=_dll_path())
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_address = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_address, payload[2:])
    return emu


def _execute(
    emu: C64Emu6502,
    routine: str,
    *,
    a: int | None = None,
    x: int | None = None,
    y: int | None = None,
) -> tuple[int, int, bool]:
    if a is not None:
        emu.set_a(a)
    if x is not None:
        emu.set_x(x)
    if y is not None:
        emu.set_y(y)
    emu.execute(_load_symbol_address(routine), MAX_CYCLES)
    state = emu.get_state()
    return int(state.x), int(state.y), bool(int(state.p) & 0x01)


def _assert_valid(emu: C64Emu6502, handle: tuple[int, int]) -> None:
    _, _, failed = _execute(emu, "arena_handle_valid", x=handle[0], y=handle[1])
    assert not failed


@pytest.mark.unit
@pytest.mark.local
class TestGeoramArenaCore:
    """Lifecycle, directory, integrity, and generation tests."""

    def test_arena_init_all_constructs_manifest_directory(self) -> None:
        """Cold start creates all nine typed arenas and reserves 752 pages."""
        emu = _new_emulator()
        _, _, failed = _execute(emu, "arena_init_all")
        assert not failed
        for arena_id in range(1, 10):
            _assert_valid(emu, (arena_id, 1))
            _, _, failed = _execute(emu, "arena_check_integrity", x=arena_id, y=1)
            assert not failed

        free_lo, free_hi, failed = _execute(emu, "page_alloc_count")
        assert not failed
        assert free_lo | (free_hi << 8) == 1296

    def test_program_staging_arena_owns_full_whole_program_capacity(self) -> None:
        """The dedicated staging arena exposes all 128 reserved pages."""
        emu = _new_emulator()
        emu.set_georam_enabled(True)
        assert not _execute(emu, "arena_init_all")[2]

        assert not _execute(emu, "arena_select_page", a=127, x=9, y=1)[2]
        emu.write_mem(0xDEFF, 0xA9)
        assert emu.read_mem(0xDEFF) == 0xA9
        assert _execute(emu, "arena_select_page", a=128, x=9, y=1)[2]

    def test_single_create_destroy_and_generation_reuse(self) -> None:
        """Destroy frees pages and prevents stale handles after slot reuse."""
        emu = _new_emulator()
        _execute(emu, "__arena_core_init")
        arena_id, generation, failed = _execute(emu, "arena_create", a=4, x=64, y=0)
        assert not failed
        assert (arena_id, generation) == (4, 1)
        _assert_valid(emu, (arena_id, generation))

        _, _, failed = _execute(emu, "arena_create", a=4, x=64, y=0)
        assert failed, "an arena type may own only one directory entry"

        _, _, failed = _execute(emu, "arena_destroy", x=arena_id, y=generation)
        assert not failed
        _, _, failed = _execute(emu, "arena_handle_valid", x=arena_id, y=generation)
        assert failed
        free_lo, free_hi, failed = _execute(emu, "page_alloc_count")
        assert not failed
        assert free_lo | (free_hi << 8) == 2048

        arena_id2, generation2, failed = _execute(emu, "arena_create", a=4, x=64, y=0)
        assert not failed
        assert arena_id2 == arena_id
        assert generation2 != generation

    def test_reset_and_explicit_invalidation_reject_old_handles(self) -> None:
        """Each logical reset advances only the selected arena generation."""
        emu = _new_emulator()
        emu.set_georam_enabled(True)
        emu.write_mem(0x0001, 0x35)
        assert not _execute(emu, "arena_init_all")[2]

        assert not _execute(emu, "georam_select", a=0, x=0)[2]
        emu.write_mem_range(0xDE00, b"DIRTY")
        assert not _execute(emu, "georam_select", a=7, x=1)[2]

        arena_id, generation, failed = _execute(emu, "arena_reset", x=1, y=1)
        assert not failed
        assert (arena_id, generation) == (1, 2)
        assert _execute(emu, "arena_handle_valid", x=1, y=1)[2]
        _assert_valid(emu, (1, 2))
        _assert_valid(emu, (2, 1))
        assert emu.read_mem(0xDFFF) == 1
        assert emu.read_mem(0xDFFE) == 7
        assert not _execute(emu, "georam_select", a=0, x=0)[2]
        assert emu.read_mem_range(0xDE00, 0xDE04) == b"\x00" * 5

        arena_id, generation, failed = _execute(
            emu, "arena_invalidate_generation", x=1, y=2
        )
        assert not failed
        assert (arena_id, generation) == (1, 3)
        assert _execute(emu, "arena_get_handle", x=1, y=2)[2]
        assert not _execute(emu, "arena_get_handle", x=1, y=3)[2]

    def test_get_handle_resolves_offset_to_backing_extent(self) -> None:
        """Arena-relative page offsets resolve to allocator extent handles."""
        emu = _new_emulator()
        assert not _execute(emu, "__arena_core_init")[2]
        arena_id, generation, failed = _execute(emu, "arena_create", a=4, x=2, y=0)
        assert not failed

        slot, slot_generation, failed = _execute(
            emu, "arena_get_handle", a=1, x=arena_id, y=generation
        )
        assert not failed
        assert slot != arena_id
        assert slot_generation == 1

        _, _, failed = _execute(emu, "arena_get_handle", a=2, x=arena_id, y=generation)
        assert failed

    def test_select_page_maps_arena_relative_pages_and_checks_bounds(self) -> None:
        """Arena-relative selections map distinct pages without exposing addresses."""
        emu = _new_emulator()
        emu.set_georam_enabled(True)
        assert not _execute(emu, "__arena_core_init")[2]
        arena_id, generation, failed = _execute(emu, "arena_create", a=1, x=2, y=0)
        assert not failed

        assert not _execute(emu, "arena_select_page", a=0, x=arena_id, y=generation)[2]
        emu.write_mem(0xDE00, 0x41)
        assert not _execute(emu, "arena_select_page", a=1, x=arena_id, y=generation)[2]
        emu.write_mem(0xDE00, 0x42)
        assert not _execute(emu, "arena_select_page", a=0, x=arena_id, y=generation)[2]
        assert emu.read_mem(0xDE00) == 0x41
        assert _execute(emu, "arena_select_page", a=2, x=arena_id, y=generation)[2]

    def test_integrity_detects_canary_and_checksum_damage(self) -> None:
        """Directory corruption is rejected without affecting another arena."""
        emu = _new_emulator()
        assert not _execute(emu, "arena_init_all")[2]
        canary_base = _load_symbol_address("__arena_core_canary")
        emu.write_mem(canary_base + 3, 0x00)
        assert _execute(emu, "arena_check_integrity", x=3, y=1)[2]
        _assert_valid(emu, (2, 1))

    def test_directory_generation_tracks_mutations(self) -> None:
        """Global directory generation advances on reset and destroy."""
        emu = _new_emulator()
        assert not _execute(emu, "arena_init_all")[2]
        low, high, failed = _execute(emu, "__arena_core_generation")
        assert not failed and (low | (high << 8)) == 1
        assert not _execute(emu, "arena_reset", x=8, y=1)[2]
        low, high, _ = _execute(emu, "__arena_core_generation")
        assert low | (high << 8) == 2
        assert not _execute(emu, "arena_destroy", x=8, y=2)[2]
        low, high, _ = _execute(emu, "__arena_core_generation")
        assert low | (high << 8) == 3
