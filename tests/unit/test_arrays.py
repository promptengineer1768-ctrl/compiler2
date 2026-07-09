"""Unit tests for arena-backed array descriptors."""

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

MAX_CYCLES = 200_000
KIND_INT = 1
KIND_STRING = 3
ARRAY_ARENA = 4
ARENA_GENERATION = 1
DESCRIPTOR = 0xC000
REQUEST = 0xC100
SOURCE_SD = 0xC200
RESULT_SD = 0xC220
SECOND_SD = 0xC240


def _artifact_root() -> Path:
    """Return the active build output directory."""
    debug_root = ROOT / "debug" / "runtime_slice"
    return debug_root if debug_root.exists() else ROOT / "build"


def _dll_path() -> Path:
    """Return the local C64 emulator binding DLL."""
    for candidate in (
        ROOT.parent / "tools" / "emu6502.dll",
        ROOT.parent / "tools" / "msys-emu6502.dll",
    ):
        if candidate.exists():
            return candidate
    pytest.skip("Emulator DLL not found in tools folder.")


def _load_binary(emu: C64Emu6502) -> None:
    """Load the linked compiler image and enable geoRAM."""
    payload = (_artifact_root() / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.set_georam_enabled(True)


def _load_symbol_address(symbol_name: str) -> int:
    """Resolve one linked production symbol."""
    labels_path = _artifact_root() / "compiler.lbl"
    if labels_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    directory_path = _artifact_root() / "routine_directory.json"
    if directory_path.exists():
        data = json.loads(directory_path.read_text(encoding="utf-8"))
        routine = data.get("routines", {}).get(symbol_name)
        if routine:
            address = routine.get("address", "")
            if isinstance(address, str) and address.startswith("$"):
                return int(address[1:], 16)
    pytest.fail(f"Symbol {symbol_name!r} not found.")


def _load_zp_address(name: str) -> int:
    """Resolve one generated zero-page symbol."""
    data = json.loads(
        (ROOT / "build" / "zp_allocation.json").read_text(encoding="utf-8")
    )
    address = data.get("allocation", {}).get(name, "")
    if isinstance(address, str) and address.startswith("$"):
        return int(address[1:], 16)
    pytest.fail(f"Zero-page symbol {name!r} not found.")


def _call(emu: C64Emu6502, routine: str, *, a: int = 0, x: int = 0, y: int = 0) -> bool:
    """Execute one production routine and return its carry status."""
    emu.set_a(a)
    emu.set_x(x)
    emu.set_y(y)
    emu.execute_rts(_load_symbol_address(routine), MAX_CYCLES)
    return bool(int(emu.get_state().p) & 1)


def _new_emulator() -> C64Emu6502:
    """Create an initialized emulator with manifest-defined arenas."""
    emu = C64Emu6502(lib_path=_dll_path())
    _load_binary(emu)
    assert not _call(emu, "arena_init_all")
    return emu


def _write_dim_request(
    emu: C64Emu6502,
    address: int,
    *,
    descriptor: int,
    kind: int = KIND_INT,
    dimensions: int = 2,
    bound0: int = 1,
    bound1: int = 2,
) -> None:
    """Write an AM array DIM request."""
    if dimensions == 1:
        bound1 = 0
    emu.write_mem_range(
        address,
        b"AM"
        + descriptor.to_bytes(2, "little")
        + bytes([kind, dimensions])
        + b"\x00\x00"
        + bound0.to_bytes(2, "little")
        + bound1.to_bytes(2, "little")
        + b"\x00\x00",
    )


def _write_element_request(
    emu: C64Emu6502,
    address: int,
    *,
    magic: bytes,
    descriptor: int,
    sub0: int,
    sub1: int = 0,
    value: int = 0,
) -> None:
    """Write an AE or AS element request."""
    emu.write_mem_range(
        address,
        magic
        + descriptor.to_bytes(2, "little")
        + sub0.to_bytes(2, "little")
        + sub1.to_bytes(2, "little")
        + value.to_bytes(2, "little")
        + b"\x00\x00",
    )


def _make_character_string(emu: C64Emu6502, descriptor: int, value: int) -> None:
    """Create a canonical owned one-character SD through production STR code."""
    emu.write_mem_range(
        REQUEST, b"SH" + descriptor.to_bytes(2, "little") + bytes([value])
    )
    assert not _call(emu, "str_chr", x=REQUEST & 0xFF, y=REQUEST >> 8)


def _string_asc(emu: C64Emu6502, descriptor: int) -> int:
    """Return ASC for a canonical SD, asserting that ownership is live."""
    assert not _call(emu, "str_asc", x=descriptor & 0xFF, y=descriptor >> 8)
    return int(emu.get_state().a)


@pytest.mark.unit
@pytest.mark.local
class TestArrays:
    """Real-byte coverage for array descriptor helpers."""

    def test_check_bounds_accepts_last_element_and_rejects_limit(self) -> None:
        """arr_check_bounds implements the unsigned subscript/extent primitive."""
        emu = _new_emulator()
        assert not _call(emu, "arr_check_bounds", a=5, x=4, y=0)
        assert _call(emu, "arr_check_bounds", a=5, x=5, y=0)
        assert _call(emu, "arr_check_bounds", a=5, x=0, y=1)

    def test_dim_publishes_arena_descriptor_and_free_invalidates_it(self) -> None:
        """DIM creates an AD descriptor backed by the manifest array arena."""
        emu = _new_emulator()
        _write_dim_request(emu, REQUEST, descriptor=DESCRIPTOR, bound0=1, bound1=2)

        assert not _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)
        descriptor_bytes = bytes(
            emu.read_mem(DESCRIPTOR + index) for index in range(16)
        )
        assert descriptor_bytes[:8] == b"AD" + bytes(
            [KIND_INT, 1, 2, 2, ARRAY_ARENA, ARENA_GENERATION]
        )
        assert descriptor_bytes[9] == 1
        assert int.from_bytes(descriptor_bytes[10:12], "little") == 6
        assert int.from_bytes(descriptor_bytes[12:14], "little") == 1
        assert int.from_bytes(descriptor_bytes[14:16], "little") == 2

        assert not _call(emu, "arr_free", x=DESCRIPTOR & 0xFF, y=DESCRIPTOR >> 8)
        assert _call(emu, "arr_resolve_element", x=REQUEST & 0xFF, y=REQUEST >> 8)

    def test_two_dimensional_int_store_load_and_resolve_use_georam(self) -> None:
        """Element access resolves row-major offsets through arena selection."""
        emu = _new_emulator()
        _write_dim_request(emu, REQUEST, descriptor=DESCRIPTOR, bound0=1, bound1=2)
        assert not _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)

        _write_element_request(
            emu,
            REQUEST,
            magic=b"AS",
            descriptor=DESCRIPTOR,
            sub0=1,
            sub1=2,
            value=0x3456,
        )
        assert not _call(emu, "arr_store_element", x=REQUEST & 0xFF, y=REQUEST >> 8)

        _write_element_request(
            emu, REQUEST, magic=b"AE", descriptor=DESCRIPTOR, sub0=1, sub1=2
        )
        assert not _call(emu, "arr_resolve_element", x=REQUEST & 0xFF, y=REQUEST >> 8)
        state = emu.get_state()
        assert (int(state.x), int(state.y)) == (10, 0xDE)
        assert [emu.read_mem(0xDE0A), emu.read_mem(0xDE0B)] == [0x56, 0x34]

        _write_element_request(
            emu, REQUEST, magic=b"AE", descriptor=DESCRIPTOR, sub0=1, sub1=2
        )
        assert not _call(emu, "arr_load_element", x=REQUEST & 0xFF, y=REQUEST >> 8)
        state = emu.get_state()
        assert (int(state.x), int(state.y)) == (0x56, 0x34)

    def test_bounds_redim_and_malformed_descriptors_are_rejected(self) -> None:
        """Array helpers reject bad subscripts, redimension, and stale handles."""
        emu = _new_emulator()
        _write_dim_request(emu, REQUEST, descriptor=DESCRIPTOR, bound0=1, bound1=2)
        assert not _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)

        assert _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)
        assert _call(
            emu,
            "arr_redim",
            x=DESCRIPTOR & 0xFF,
            y=DESCRIPTOR >> 8,
        )

        _write_element_request(
            emu, REQUEST, magic=b"AE", descriptor=DESCRIPTOR, sub0=2, sub1=0
        )
        assert _call(emu, "arr_resolve_element", x=REQUEST & 0xFF, y=REQUEST >> 8)

        emu.write_mem(DESCRIPTOR + 6, 0x7F)
        _write_element_request(
            emu, REQUEST, magic=b"AE", descriptor=DESCRIPTOR, sub0=0, sub1=0
        )
        assert _call(emu, "arr_resolve_element", x=REQUEST & 0xFF, y=REQUEST >> 8)

        _write_dim_request(emu, REQUEST, descriptor=0xC040, bound0=1, bound1=2)
        assert not _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)
        emu.write_mem(0xC040 + 10, 5)
        _write_element_request(
            emu, REQUEST, magic=b"AE", descriptor=0xC040, sub0=0, sub1=0
        )
        assert _call(emu, "arr_resolve_element", x=REQUEST & 0xFF, y=REQUEST >> 8)

    def test_float_array_elements_copy_through_fac(self) -> None:
        """Float arrays store and load five-byte FAC payloads."""
        emu = _new_emulator()
        zp_fac1 = _load_zp_address("zp_fac1")
        _write_dim_request(
            emu, REQUEST, descriptor=DESCRIPTOR, kind=2, dimensions=1, bound0=1
        )
        assert not _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)

        for offset, value in enumerate([0x82, 0x20, 0x10, 0x08, 0x04]):
            emu.write_mem(zp_fac1 + offset, value)
        _write_element_request(emu, REQUEST, magic=b"AS", descriptor=DESCRIPTOR, sub0=1)
        assert not _call(emu, "arr_store_element", x=REQUEST & 0xFF, y=REQUEST >> 8)

        for offset in range(5):
            emu.write_mem(zp_fac1 + offset, 0)
        _write_element_request(emu, REQUEST, magic=b"AE", descriptor=DESCRIPTOR, sub0=1)
        assert not _call(emu, "arr_load_element", x=REQUEST & 0xFF, y=REQUEST >> 8)
        assert [emu.read_mem(zp_fac1 + offset) for offset in range(5)] == [
            0x82,
            0x20,
            0x10,
            0x08,
            0x04,
        ]

    def test_string_array_elements_copy_owned_canonical_descriptors(self) -> None:
        """String stores and loads create independent canonical SD ownership."""
        emu = _new_emulator()
        _write_dim_request(
            emu,
            REQUEST,
            descriptor=DESCRIPTOR,
            kind=KIND_STRING,
            dimensions=1,
            bound0=1,
        )
        assert not _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)

        assert emu.read_mem(DESCRIPTOR + 5) == 12
        _make_character_string(emu, SOURCE_SD, ord("A"))

        _write_element_request(
            emu,
            REQUEST,
            magic=b"AS",
            descriptor=DESCRIPTOR,
            sub0=1,
            value=SOURCE_SD,
        )
        assert not _call(emu, "arr_store_element", x=REQUEST & 0xFF, y=REQUEST >> 8)

        _write_element_request(
            emu,
            REQUEST,
            magic=b"AE",
            descriptor=DESCRIPTOR,
            sub0=1,
            value=RESULT_SD,
        )
        assert not _call(emu, "arr_load_element", x=REQUEST & 0xFF, y=REQUEST >> 8)
        assert bytes(emu.read_mem(RESULT_SD + offset) for offset in range(2)) == b"SD"
        assert _string_asc(emu, SOURCE_SD) == ord("A")
        assert _string_asc(emu, RESULT_SD) == ord("A")

        _make_character_string(emu, SECOND_SD, ord("B"))
        _write_element_request(
            emu,
            REQUEST,
            magic=b"AS",
            descriptor=DESCRIPTOR,
            sub0=1,
            value=SECOND_SD,
        )
        assert not _call(emu, "arr_store_element", x=REQUEST & 0xFF, y=REQUEST >> 8)
        assert _string_asc(emu, RESULT_SD) == ord("A")

        _write_element_request(
            emu,
            REQUEST,
            magic=b"AE",
            descriptor=DESCRIPTOR,
            sub0=1,
            value=RESULT_SD,
        )
        assert not _call(emu, "arr_load_element", x=REQUEST & 0xFF, y=REQUEST >> 8)
        assert _string_asc(emu, RESULT_SD) == ord("B")
        assert not _call(emu, "arr_free", x=DESCRIPTOR & 0xFF, y=DESCRIPTOR >> 8)
        assert _string_asc(emu, RESULT_SD) == ord("B")

    def test_float_element_crossing_page_boundary_round_trips(self) -> None:
        """Typed copies reselect geoRAM when an element spans two pages."""
        emu = _new_emulator()
        zp_fac1 = _load_zp_address("zp_fac1")
        _write_dim_request(
            emu, REQUEST, descriptor=DESCRIPTOR, kind=2, dimensions=1, bound0=51
        )
        assert not _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)
        expected = [0x84, 0x40, 0x20, 0x10, 0x08]
        for offset, value in enumerate(expected):
            emu.write_mem(zp_fac1 + offset, value)
        _write_element_request(
            emu, REQUEST, magic=b"AS", descriptor=DESCRIPTOR, sub0=51
        )
        assert not _call(emu, "arr_store_element", x=REQUEST & 0xFF, y=REQUEST >> 8)
        for offset in range(5):
            emu.write_mem(zp_fac1 + offset, 0)
        _write_element_request(
            emu, REQUEST, magic=b"AE", descriptor=DESCRIPTOR, sub0=51
        )
        assert not _call(emu, "arr_load_element", x=REQUEST & 0xFF, y=REQUEST >> 8)
        assert [emu.read_mem(zp_fac1 + offset) for offset in range(5)] == expected

    def test_page_allocator_prevents_overlap_and_reuses_freed_extent(self) -> None:
        """Distinct arrays own disjoint pages and free returns an extent."""
        emu = _new_emulator()
        second_descriptor = 0xC040
        _write_dim_request(
            emu, REQUEST, descriptor=DESCRIPTOR, dimensions=1, bound0=128
        )
        assert not _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)
        first_page = emu.read_mem(DESCRIPTOR + 8)
        assert emu.read_mem(DESCRIPTOR + 9) == 2

        _write_dim_request(
            emu, REQUEST, descriptor=second_descriptor, dimensions=1, bound0=128
        )
        assert not _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)
        second_page = emu.read_mem(second_descriptor + 8)
        assert second_page != first_page

        assert not _call(emu, "arr_free", x=DESCRIPTOR & 0xFF, y=DESCRIPTOR >> 8)
        _write_dim_request(
            emu, REQUEST, descriptor=DESCRIPTOR, dimensions=1, bound0=128
        )
        assert not _call(emu, "arr_dim", x=REQUEST & 0xFF, y=REQUEST >> 8)
        assert emu.read_mem(DESCRIPTOR + 8) == first_page
