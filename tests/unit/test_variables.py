"""Unit tests for typed variable descriptors."""

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
KIND_FLOAT = 2
KIND_STRING = 3
STORAGE_DIRECT = 0
STORAGE_ARENA = 1
SCALAR_ARENA = 3
STRING_ARENA = 5
ARENA_GENERATION = 1


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


def _write_descriptor(
    emu: C64Emu6502,
    address: int,
    *,
    kind: int,
    storage: int = STORAGE_DIRECT,
    cell: int = 0,
    arena: int = SCALAR_ARENA,
    arena_generation: int = ARENA_GENERATION,
    page: int = 0,
    offset: int = 0,
    descriptor_generation: int = 1,
    reserved: int = 0,
) -> None:
    """Write one 12-byte VD variable descriptor."""
    if storage == STORAGE_DIRECT:
        tail = cell.to_bytes(2, "little") + b"\x00\x00\x00\x00"
    else:
        tail = bytes([arena, arena_generation, page, offset, 0, 0])
    emu.write_mem_range(
        address,
        b"VD" + bytes([kind, descriptor_generation, storage, reserved]) + tail,
    )


def _write_int_store(
    emu: C64Emu6502, address: int, descriptor: int, value: int
) -> None:
    """Write one typed integer-store request."""
    emu.write_mem_range(
        address,
        b"VI" + descriptor.to_bytes(2, "little") + value.to_bytes(2, "little"),
    )


def _write_float_store(emu: C64Emu6502, address: int, descriptor: int) -> None:
    """Write one typed float-store request."""
    emu.write_mem_range(address, b"VF" + descriptor.to_bytes(2, "little") + b"\x00\x00")


def _write_string_store(
    emu: C64Emu6502, address: int, descriptor: int, source_sd: int
) -> None:
    """Write one typed variable string-copy request."""
    emu.write_mem_range(
        address,
        b"VS" + descriptor.to_bytes(2, "little") + source_sd.to_bytes(2, "little"),
    )


def _allocate_string(emu: C64Emu6502, descriptor: int, length: int) -> None:
    """Allocate one canonical SD through the production string runtime."""
    request = 0xCCC0
    emu.write_mem_range(
        request, b"SA" + descriptor.to_bytes(2, "little") + bytes([length])
    )
    assert not _call(emu, "str_alloc", x=request & 0xFF, y=request >> 8)


def _select_page(
    emu: C64Emu6502,
    page: int,
    *,
    arena: int,
    generation: int = ARENA_GENERATION,
) -> None:
    """Select one arena-relative page through production code."""
    assert not _call(emu, "arena_select_page", a=page, x=arena, y=generation)


@pytest.mark.unit
@pytest.mark.local
class TestVariables:
    """Real-byte coverage for variable descriptor helpers."""

    def test_set_type_updates_valid_descriptor_and_rejects_unknown_kind(self) -> None:
        """var_set_type validates the VD before changing its canonical kind."""
        emu = _new_emulator()
        descriptor = 0xCC00
        _write_descriptor(emu, descriptor, kind=KIND_INT, cell=0x3800)
        assert not _call(
            emu,
            "var_set_type",
            a=KIND_FLOAT,
            x=descriptor & 0xFF,
            y=descriptor >> 8,
        )
        assert emu.read_mem(descriptor + 2) == KIND_FLOAT
        assert _call(
            emu, "var_set_type", a=0x7F, x=descriptor & 0xFF, y=descriptor >> 8
        )
        assert emu.read_mem(descriptor + 2) == KIND_FLOAT

    def test_direct_int_descriptor_load_store_and_type_rejection(self) -> None:
        """Integer helpers use typed VD/VI records, not raw pointer records."""
        emu = _new_emulator()
        descriptor = 0xCC00
        request = 0xCC10
        cell = 0x3800
        _write_descriptor(emu, descriptor, kind=KIND_INT, cell=cell)
        emu.write_mem_range(cell, b"\x34\x12")

        assert not _call(emu, "var_resolve", x=descriptor & 0xFF, y=descriptor >> 8)
        state = emu.get_state()
        assert (int(state.x), int(state.y)) == (cell & 0xFF, cell >> 8)

        assert not _call(emu, "var_load_int", x=descriptor & 0xFF, y=descriptor >> 8)
        state = emu.get_state()
        assert (int(state.x), int(state.y)) == (0x34, 0x12)

        _write_int_store(emu, request, descriptor, 0x5678)
        assert not _call(emu, "var_store_int", x=request & 0xFF, y=request >> 8)
        assert bytes(emu.read_mem(cell + index) for index in range(2)) == b"\x78\x56"

        emu.write_mem(descriptor + 2, KIND_FLOAT)
        assert _call(emu, "var_load_int", x=descriptor & 0xFF, y=descriptor >> 8)

    def test_arena_backed_float_descriptor_validates_generation(self) -> None:
        """Arena-backed descriptors validate the scalar arena handle before use."""
        emu = _new_emulator()
        descriptor = 0xCC00
        request = 0xCC10
        _write_descriptor(
            emu,
            descriptor,
            kind=KIND_FLOAT,
            storage=STORAGE_ARENA,
            arena=SCALAR_ARENA,
            page=1,
            offset=7,
        )
        _select_page(emu, 1, arena=SCALAR_ARENA)
        for offset, value in enumerate([0x81, 0x40, 0x00, 0x00, 0x00]):
            emu.write_mem(0xDE07 + offset, value)

        assert not _call(emu, "var_load_float", x=descriptor & 0xFF, y=descriptor >> 8)
        zp_fac1 = _load_zp_address("zp_fac1")
        assert [emu.read_mem(zp_fac1 + index) for index in range(5)] == [
            0x81,
            0x40,
            0x00,
            0x00,
            0x00,
        ]

        for offset, value in enumerate([0x82, 0x20, 0x10, 0x08, 0x04]):
            emu.write_mem(zp_fac1 + offset, value)
        _write_float_store(emu, request, descriptor)
        assert not _call(emu, "var_store_float", x=request & 0xFF, y=request >> 8)
        _select_page(emu, 1, arena=SCALAR_ARENA)
        assert [emu.read_mem(0xDE07 + index) for index in range(5)] == [
            0x82,
            0x20,
            0x10,
            0x08,
            0x04,
        ]

        emu.write_mem(descriptor + 7, 0x7F)
        assert _call(emu, "var_load_float", x=descriptor & 0xFF, y=descriptor >> 8)

    def test_string_descriptor_load_store_and_zero_length(self) -> None:
        """String variables own canonical SD copies and release replaced values."""
        emu = _new_emulator()
        descriptor = 0xCC00
        request = 0xCC10
        cell = 0x3900
        source = 0x3A00
        empty = 0x3B00
        stale = 0x3C00
        _write_descriptor(emu, descriptor, kind=KIND_STRING, cell=cell)
        _allocate_string(emu, source, 3)
        _allocate_string(emu, empty, 0)
        emu.write_mem_range(cell, bytes(emu.read_mem(empty + i) for i in range(12)))

        _write_string_store(emu, request, descriptor, source)
        assert not _call(emu, "var_store_string", x=request & 0xFF, y=request >> 8)
        source_sd = bytes(emu.read_mem(source + i) for i in range(12))
        stored_sd = bytes(emu.read_mem(cell + i) for i in range(12))
        assert stored_sd[:6] == source_sd[:6]
        assert stored_sd[6:12] != source_sd[6:12]

        assert not _call(emu, "var_load_string", x=descriptor & 0xFF, y=descriptor >> 8)
        state = emu.get_state()
        staged = int(state.x) | (int(state.y) << 8)
        assert int(state.a) == 3
        assert bytes(emu.read_mem(staged + i) for i in range(12)) == stored_sd

        emu.write_mem_range(stale, stored_sd)
        _write_string_store(emu, request, descriptor, empty)
        assert not _call(emu, "var_store_string", x=request & 0xFF, y=request >> 8)
        assert bytes(emu.read_mem(cell + i) for i in range(12))[3] == 0
        assert _call(emu, "str_len", x=stale & 0xFF, y=stale >> 8)

    def test_descriptor_shape_and_stale_handles_are_rejected(self) -> None:
        """Malformed descriptors fail instead of resolving accidental raw pointers."""
        emu = _new_emulator()
        descriptor = 0xCC00
        _write_descriptor(emu, descriptor, kind=KIND_INT, cell=0x3800)

        emu.write_mem(descriptor, ord("X"))
        assert _call(emu, "var_resolve", x=descriptor & 0xFF, y=descriptor >> 8)
        emu.write_mem(descriptor, ord("V"))

        emu.write_mem(descriptor + 3, 0)
        assert _call(emu, "var_resolve", x=descriptor & 0xFF, y=descriptor >> 8)
        emu.write_mem(descriptor + 3, 1)

        emu.write_mem(descriptor + 5, 1)
        assert _call(emu, "var_resolve", x=descriptor & 0xFF, y=descriptor >> 8)
        emu.write_mem(descriptor + 5, 0)

        emu.write_mem(descriptor + 4, 0x7F)
        assert _call(emu, "var_resolve", x=descriptor & 0xFF, y=descriptor >> 8)

    @pytest.mark.parametrize(
        ("kind", "valid_offset", "invalid_offset"),
        [
            pytest.param(KIND_INT, 0xFE, 0xFF, id="int"),
            pytest.param(KIND_FLOAT, 0xFB, 0xFC, id="float"),
            pytest.param(KIND_STRING, 0xF4, 0xF5, id="string"),
        ],
    )
    def test_arena_payload_must_fit_inside_georam_page(
        self, kind: int, valid_offset: int, invalid_offset: int
    ) -> None:
        """Typed arena cells may not spill out of the $DE00 geoRAM window."""
        emu = _new_emulator()
        descriptor = 0xCC00
        _write_descriptor(
            emu,
            descriptor,
            kind=kind,
            storage=STORAGE_ARENA,
            arena=SCALAR_ARENA,
            page=2,
            offset=valid_offset,
        )

        assert not _call(emu, "var_resolve", x=descriptor & 0xFF, y=descriptor >> 8)

        emu.write_mem(descriptor + 9, invalid_offset)
        assert _call(emu, "var_resolve", x=descriptor & 0xFF, y=descriptor >> 8)

    def test_promote_and_coerce_report_loss_or_unsupported_targets(self) -> None:
        """Coercion succeeds only for supported lossless conversions."""
        emu = _new_emulator()
        zp_fac1 = _load_zp_address("zp_fac1")

        assert not _call(emu, "var_promote_to_float", x=0x34, y=0x12)
        assert any(emu.read_mem(zp_fac1 + offset) for offset in range(5))

        assert not _call(emu, "var_coerce", a=KIND_FLOAT)
        assert not _call(emu, "var_coerce", a=KIND_INT)
        state = emu.get_state()
        assert (int(state.x), int(state.y)) == (0x34, 0x12)

        for offset, value in enumerate([0x81, 0x40, 0x00, 0x00, 0x00]):
            emu.write_mem(zp_fac1 + offset, value)
        assert _call(emu, "var_coerce", a=KIND_INT)
        assert _call(emu, "var_coerce", a=0x7F)
