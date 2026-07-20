"""Integration tests for the arena-backed program lifecycle."""

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

MAX_CYCLES = 8_000_000
INPUT_ARENA = 8
LINE_ARENA = 6
ARENA_GENERATION = 1
NOEL_SOURCE = ROOT / "tests" / "performance" / "noels_retro_lab_cbm_v2.bas"


def _dll_path() -> Path:
    """Return the local C64 emulator binding DLL."""
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _load_symbol_address(symbol_name: str) -> int:
    """Resolve one linked production symbol."""
    labels = ROOT / "build" / "compiler.lbl"
    if labels.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    directory = ROOT / "build" / "routine_directory.json"
    if directory.exists():
        try:
            data = json.loads(directory.read_text(encoding="utf-8"))
            routine = data.get("routines", {}).get(symbol_name)
            if routine:
                address = routine.get("address", "")
                if isinstance(address, str) and address.startswith("$"):
                    return int(address[1:], 16)
        except (json.JSONDecodeError, OSError):
            pass
    pytest.fail(f"Symbol {symbol_name!r} not found.")


def _load_binary(emu: C64Emu6502) -> None:
    """Load the real linked compiler, the geoRAM overlay, and enable it."""
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_address = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_address, payload[2:])
    image = (ROOT / "build" / "georam.bin").read_bytes()
    assert image[:2] == b"\x00\xde"
    emu.set_georam_enabled(True)
    backing_size = len(emu.export_georam())
    payload_bytes = image[2:]
    assert backing_size >= len(payload_bytes)
    emu.load_georam(payload_bytes + bytes(backing_size - len(payload_bytes)))
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)


def _routine_record(routine: str) -> dict[str, object]:
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    return data["routines"][routine]


def _run_paged(emu: C64Emu6502, routine: str, *, x: int, y: int) -> None:
    """Reach a geoRAM routine through the production XY XIP gate.

    Routines with id<256 take the group-0 gate (A=id); ids 256..511 take the
    group-n gate (A=low byte of id), which indexes the group-1 directory.
    """
    record = _routine_record(routine)
    assert record.get("layer") == "georam", f"{routine} is not a geoRAM routine"
    routine_id = int(record["id"])  # type: ignore[arg-type]
    assert routine_id < 0x200
    if routine_id < 0x100:
        gate = "georam_call_group_0_xy"
    else:
        gate = "georam_call_group_n_xy"
    emu.set_a(routine_id & 0xFF)
    emu.set_x(x)
    emu.set_y(y)
    emu.execute(_load_symbol_address(gate), MAX_CYCLES)


def _call(emu: C64Emu6502, routine: str, *, x: int = 0, y: int = 0) -> bool:
    """Execute one production routine and return its carry status."""
    record = _routine_record(routine)
    if record.get("layer") == "georam":
        _run_paged(emu, routine, x=x, y=y)
    else:
        emu.set_x(x)
        emu.set_y(y)
        emu.execute(_load_symbol_address(routine), MAX_CYCLES)
    return bool(int(emu.get_state().p) & 1)


def _select_page(
    emu: C64Emu6502,
    relative_page: int,
    *,
    arena: int,
    generation: int = ARENA_GENERATION,
) -> None:
    """Select one arena-relative page through the production gate."""
    emu.set_a(relative_page)
    assert not _call(emu, "arena_select_page", x=arena, y=generation)


def _write_stream(
    emu: C64Emu6502,
    descriptor: int,
    payload: bytes,
    *,
    arena: int,
    start_page: int = 0,
    generation: int = ARENA_GENERATION,
) -> None:
    """Write one PS descriptor and its arena payload."""
    assert len(payload) <= 0xFFFF
    emu.write_mem_range(
        descriptor,
        b"PS"
        + len(payload).to_bytes(2, "little")
        + bytes([arena, generation, start_page, 0]),
    )
    for index, value in enumerate(payload):
        page, offset = divmod(index, 256)
        if offset == 0:
            _select_page(
                emu,
                start_page + page,
                arena=arena,
                generation=generation,
            )
        emu.write_mem(0xDE00 + offset, value)


def _read_stream(emu: C64Emu6502, descriptor: int) -> bytes:
    """Read a complete PS payload through production arena selection."""
    header = bytes(emu.read_mem(descriptor + index) for index in range(8))
    assert header[:2] == b"PS"
    assert header[7] == 0
    length = int.from_bytes(header[2:4], "little")
    result = bytearray()
    for index in range(length):
        page, offset = divmod(index, 256)
        if offset == 0:
            _select_page(
                emu,
                header[6] + page,
                arena=header[4],
                generation=header[5],
            )
        result.append(emu.read_mem(0xDE00 + offset))
    return bytes(result)


def _stock_program(lines: list[tuple[int, bytes]]) -> bytes:
    """Build a canonical stock BASIC V2 PRG payload."""
    result = bytearray(b"\x01\x08")
    address = 0x0801
    for line_number, body in lines:
        address += 2 + 2 + len(body) + 1
        result += address.to_bytes(2, "little")
        result += line_number.to_bytes(2, "little")
        result += body + b"\x00"
    result += b"\x00\x00"
    return bytes(result)


def _normalized_program(lines: list[tuple[int, bytes]]) -> bytes:
    """Build sorted normalized records plus the zero-length terminator."""
    result = bytearray()
    for line_number, body in lines:
        record_length = 2 + len(body) + 1
        result += record_length.to_bytes(2, "little")
        result += line_number.to_bytes(2, "little")
        result += body + b"\x00"
    result += b"\x00\x00"
    return bytes(result)


def _extended_program(body: bytes) -> bytes:
    """Build a canonical C2P1 envelope around a normalized body."""
    checksum = sum(body) & 0xFF
    return (
        b"C2P1"
        + bytes([1, 1, len(body) & 0xFF, len(body) >> 8, checksum, 0])
        + bytes(6)
        + body
    )


def _write_put_request(
    emu: C64Emu6502, address: int, transaction: int, line_descriptor: int
) -> None:
    """Write a PP request descriptor."""
    emu.write_mem_range(
        address,
        b"PP"
        + transaction.to_bytes(2, "little")
        + line_descriptor.to_bytes(2, "little")
        + b"\x00\x00",
    )


@pytest.mark.integration
@pytest.mark.local
class TestProgramLifecycle:
    """Integration coverage for codec and store routines."""

    def test_extended_decode_store_and_encode_round_trip(self) -> None:
        """C2P1 data crosses the normalized program-store boundary intact."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")

        logical = _normalized_program(
            [(10, bytes([0x99, ord("1")])), (20, bytes([0x80]))]
        )
        descriptor = 0xC300
        _write_stream(
            emu,
            descriptor,
            _extended_program(logical),
            arena=INPUT_ARENA,
        )

        assert not _call(
            emu,
            "program_decode_extended",
            x=descriptor & 0xFF,
            y=descriptor >> 8,
        )
        decoded = int(emu.get_state().x) | (int(emu.get_state().y) << 8)
        assert _read_stream(emu, decoded) == logical

        assert not _call(
            emu,
            "program_replace_from_load",
            x=decoded & 0xFF,
            y=decoded >> 8,
        )
        published = _load_symbol_address("__program_store_published")
        assert _read_stream(emu, published) == logical

        assert not _call(
            emu,
            "program_encode_extended",
            x=published & 0xFF,
            y=published >> 8,
        )
        encoded = int(emu.get_state().x) | (int(emu.get_state().y) << 8)
        assert _read_stream(emu, encoded) == _extended_program(logical)

    def test_decode_store_edit_and_encode_round_trip(self) -> None:
        """Stock input decodes to normalized store state and exports canonically."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")

        stock_descriptor = 0xC000
        raw_payload = _stock_program(
            [(10, bytes([0x99, ord("1")])), (20, bytes([0x80]))]
        )
        _write_stream(emu, stock_descriptor, raw_payload, arena=INPUT_ARENA)

        assert not _call(
            emu,
            "program_decode_stock",
            x=stock_descriptor & 0xFF,
            y=stock_descriptor >> 8,
        )
        decoded = int(emu.get_state().x) | (int(emu.get_state().y) << 8)
        decoded_payload = _normalized_program(
            [(10, bytes([0x99, ord("1")])), (20, bytes([0x80]))]
        )
        assert _read_stream(emu, decoded) == decoded_payload

        assert not _call(
            emu,
            "program_replace_from_load",
            x=decoded & 0xFF,
            y=decoded >> 8,
        )
        published = _load_symbol_address("__program_store_published")
        assert _read_stream(emu, published) == decoded_payload

        assert not _call(emu, "program_tx_begin")
        transaction = int(emu.get_state().x) | (int(emu.get_state().y) << 8)
        request = 0xC100
        line_descriptor = 0xC120
        _write_stream(
            emu,
            line_descriptor,
            _normalized_program([(15, bytes([0x99, ord("2")]))]),
            arena=LINE_ARENA,
        )
        _write_put_request(emu, request, transaction, line_descriptor)
        assert not _call(
            emu,
            "program_tx_put_line",
            x=request & 0xFF,
            y=request >> 8,
        )
        assert not _call(
            emu,
            "program_tx_commit",
            x=transaction & 0xFF,
            y=transaction >> 8,
        )

        edited_payload = _normalized_program(
            [
                (10, bytes([0x99, ord("1")])),
                (15, bytes([0x99, ord("2")])),
                (20, bytes([0x80])),
            ]
        )
        assert _read_stream(emu, published) == edited_payload

        assert not _call(
            emu,
            "program_encode_stock",
            x=published & 0xFF,
            y=published >> 8,
        )
        encoded = int(emu.get_state().x) | (int(emu.get_state().y) << 8)
        assert _read_stream(emu, encoded) == _stock_program(
            [
                (10, bytes([0x99, ord("1")])),
                (15, bytes([0x99, ord("2")])),
                (20, bytes([0x80])),
            ]
        )

    def test_noel_sized_stored_program_publishes_in_expansion_arena(self) -> None:
        """A 224-byte entered-source program has no EDITOR_PINNED capacity limit.

        The stored source is represented by the canonical normalized PS stream
        and is published through the production transaction boundary.  This is
        deliberately larger than the retired 48-byte interim editor table.
        """
        source_lines = NOEL_SOURCE.read_bytes().splitlines(keepends=True)
        assert sum(len(line) for line in source_lines) == 224
        normalized_lines: list[tuple[int, bytes]] = []
        for raw_line in source_lines:
            line_number, separator, body = raw_line.rstrip(b"\r\n").partition(b" ")
            assert separator == b" "
            normalized_lines.append((int(line_number), body + b"\x00"))
        logical = _normalized_program(normalized_lines)
        assert len(logical) > 48

        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")

        descriptor = 0xC300
        _write_stream(emu, descriptor, logical, arena=INPUT_ARENA)
        assert not _call(
            emu,
            "program_replace_from_load",
            x=descriptor & 0xFF,
            y=descriptor >> 8,
        )

        published = _load_symbol_address("__program_store_published")
        assert _read_stream(emu, published) == logical
