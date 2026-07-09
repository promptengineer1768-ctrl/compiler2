"""Real-byte unit tests for the GeoRAM page allocator."""

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

REQUEST_ADDR = 0xC000
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


def _execute(emu: C64Emu6502, routine: str) -> bool:
    emu.execute(_load_symbol_address(routine), MAX_CYCLES)
    return bool(int(emu.get_state().p) & 0x01)


def _request(
    emu: C64Emu6502, count: int, *, alignment: int = 1, owner: int = 1
) -> tuple[int, int, bool]:
    emu.write_mem_range(
        REQUEST_ADDR,
        bytes(
            [
                count & 0xFF,
                (count >> 8) & 0xFF,
                alignment & 0xFF,
                (alignment >> 8) & 0xFF,
                owner & 0xFF,
            ]
        ),
    )
    emu.set_x(REQUEST_ADDR & 0xFF)
    emu.set_y(REQUEST_ADDR >> 8)
    failed = _execute(emu, "page_alloc")
    state = emu.get_state()
    return int(state.x), int(state.y), failed


def _free(emu: C64Emu6502, handle: tuple[int, int]) -> bool:
    emu.set_x(handle[0])
    emu.set_y(handle[1])
    return _execute(emu, "page_free")


def _query(emu: C64Emu6502, routine: str) -> int:
    assert not _execute(emu, routine)
    state = emu.get_state()
    return int(state.x) | (int(state.y) << 8)


@pytest.mark.unit
@pytest.mark.local
class TestGeoramPageAlloc:
    """Bitmap, fragmentation, bounds, and handle-integrity coverage."""

    def test_init_count_largest_and_arbitrary_free(self) -> None:
        """Initialization exposes all 2,048 pages and frees non-LIFO extents."""
        emu = _new_emulator()
        assert not _execute(emu, "page_alloc_init")
        assert _query(emu, "page_alloc_count") == 2048
        assert _query(emu, "page_alloc_largest") == 2048

        first = _request(emu, 3)
        middle = _request(emu, 4)
        last = _request(emu, 5)
        assert not first[2] and not middle[2] and not last[2]
        assert _query(emu, "page_alloc_count") == 2036

        assert not _free(emu, middle[:2])
        replacement = _request(emu, 4)
        assert not replacement[2]
        tail = _request(emu, 2036)
        assert not tail[2], "first-fit must reuse the interior four-page hole"
        assert _query(emu, "page_alloc_count") == 0
        assert _query(emu, "page_alloc_largest") == 0

    def test_alignment_changes_fragmentation_shape(self) -> None:
        """Power-of-two alignment leaves the expected leading gap."""
        emu = _new_emulator()
        assert not _execute(emu, "page_alloc_init")
        assert not _request(emu, 1)[2]
        assert not _request(emu, 1, alignment=8)[2]
        assert _query(emu, "page_alloc_count") == 2046
        assert _query(emu, "page_alloc_largest") == 2039

    @pytest.mark.parametrize(
        ("count", "alignment", "owner"),
        [(0, 1, 1), (1, 0, 1), (1, 3, 1), (1, 1, 0)],
        ids=["zero-count", "zero-alignment", "non-power-two", "zero-owner"],
    )
    def test_invalid_requests_fail(
        self, count: int, alignment: int, owner: int
    ) -> None:
        """Malformed request descriptors must not consume capacity."""
        emu = _new_emulator()
        assert not _execute(emu, "page_alloc_init")
        assert _request(emu, count, alignment=alignment, owner=owner)[2]
        assert _query(emu, "page_alloc_count") == 2048

    def test_generation_rejects_stale_and_double_free_handles(self) -> None:
        """A freed slot cannot be reused through an older generation handle."""
        emu = _new_emulator()
        assert not _execute(emu, "page_alloc_init")
        slot, generation, failed = _request(emu, 2, owner=4)
        assert not failed
        assert not _free(emu, (slot, generation))
        assert _free(emu, (slot, generation))

        new_slot, new_generation, failed = _request(emu, 2, owner=5)
        assert not failed
        assert new_slot == slot
        assert new_generation != generation
        assert _free(emu, (slot, generation))
        assert not _free(emu, (new_slot, new_generation))

    def test_check_in_range_validates_live_handle(self) -> None:
        """Bounds checks accept live extents and reject stale handles."""
        emu = _new_emulator()
        assert not _execute(emu, "page_alloc_init")
        slot, generation, failed = _request(emu, 2048, owner=8)
        assert not failed
        emu.set_x(slot)
        emu.set_y(generation)
        assert not _execute(emu, "page_check_in_range")
        assert not _free(emu, (slot, generation))
        emu.set_x(slot)
        emu.set_y(generation)
        assert _execute(emu, "page_check_in_range")

    def test_clear_extent_zeroes_pages_and_restores_selection(self) -> None:
        """Extent clearing uses the real GeoRAM window and preserves its caller."""
        emu = _new_emulator()
        emu.set_georam_enabled(True)
        emu.write_mem(0x0001, 0x35)
        assert not _execute(emu, "page_alloc_init")
        slot, generation, failed = _request(emu, 1, owner=3)
        assert not failed

        emu.set_a(0)
        emu.set_x(0)
        assert not _execute(emu, "georam_select")
        emu.write_mem_range(0xDE00, b"DIRTY")
        emu.set_a(3)
        emu.set_x(2)
        assert not _execute(emu, "georam_select")

        emu.set_x(slot)
        emu.set_y(generation)
        assert not _execute(emu, "page_clear_extent")
        assert emu.read_mem(0xDFFF) == 2
        assert emu.read_mem(0xDFFE) == 3

        emu.set_a(0)
        emu.set_x(0)
        assert not _execute(emu, "georam_select")
        assert emu.read_mem_range(0xDE00, 0xDE04) == b"\x00" * 5
