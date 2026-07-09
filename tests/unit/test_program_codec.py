"""Unit tests for program codec routines."""

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
                addr = routine.get("address", "")
                if isinstance(addr, str) and addr.startswith("$"):
                    return int(addr[1:], 16)
        except Exception:
            pass
    map_path = ROOT / "build" / "compiler.map"
    if not map_path.exists():
        pytest.fail("build/compiler.map not found. Run build.ps1 first.")
    content = map_path.read_text(encoding="utf-8")
    match = re.search(rf"\b{re.escape(symbol_name)}\b\s+([0-9A-Fa-f]{{6}})", content)
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found.")


def _load_binary(emu: C64Emu6502) -> None:
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.skip("build/compiler.bin not found.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.set_georam_enabled(True)


def _write_record(emu: C64Emu6502, address: int, payload: bytes) -> None:
    emu.write_mem(address, len(payload))
    emu.write_mem(address + 1, 0)
    emu.write_mem_range(address + 2, payload)


def _read_record(emu: C64Emu6502, address: int) -> bytes:
    length = emu.read_mem(address)
    return bytes(emu.read_mem(address + 2 + i) for i in range(length))


STREAM_MAGIC = b"PS"
STREAM_ARENA = 8
STREAM_GENERATION = 1


def _call(emu: C64Emu6502, routine: str, *, a: int = 0, x: int = 0, y: int = 0) -> bool:
    emu.set_a(a)
    emu.set_x(x)
    emu.set_y(y)
    emu.execute(_load_symbol_address(routine), 5_000_000)
    return bool(int(emu.get_state().p) & 1)


def _select_stream_page(
    emu: C64Emu6502,
    relative_page: int,
    *,
    arena: int = STREAM_ARENA,
    generation: int = STREAM_GENERATION,
) -> None:
    assert not _call(
        emu,
        "arena_select_page",
        a=relative_page,
        x=arena,
        y=generation,
    )


def _write_stream(
    emu: C64Emu6502,
    descriptor: int,
    payload: bytes,
    *,
    start_page: int = 0,
    arena: int = STREAM_ARENA,
    generation: int = STREAM_GENERATION,
) -> None:
    assert len(payload) <= 0xFFFF
    emu.write_mem_range(
        descriptor,
        STREAM_MAGIC
        + len(payload).to_bytes(2, "little")
        + bytes([arena, generation, start_page, 0]),
    )
    for index, value in enumerate(payload):
        page, offset = divmod(index, 256)
        if offset == 0:
            _select_stream_page(
                emu,
                start_page + page,
                arena=arena,
                generation=generation,
            )
        emu.write_mem(0xDE00 + offset, value)


def _read_stream(emu: C64Emu6502, descriptor: int) -> bytes:
    header = bytes(emu.read_mem(descriptor + index) for index in range(8))
    assert header[:2] == STREAM_MAGIC
    length = int.from_bytes(header[2:4], "little")
    result = bytearray()
    for index in range(length):
        page, offset = divmod(index, 256)
        if offset == 0:
            _select_stream_page(
                emu,
                header[6] + page,
                arena=header[4],
                generation=header[5],
            )
        result.append(emu.read_mem(0xDE00 + offset))
    return bytes(result)


def _stock_program(lines: list[tuple[int, bytes]]) -> bytes:
    """Build a canonical load-address-prefixed BASIC V2 program."""
    result = bytearray(b"\x01\x08")
    address = 0x0801
    for line_number, body in lines:
        next_address = address + 2 + 2 + len(body) + 1
        result += bytes(
            [
                next_address & 0xFF,
                next_address >> 8,
                line_number & 0xFF,
                line_number >> 8,
            ]
        )
        result += body + b"\x00"
        address = next_address
    result += b"\x00\x00"
    return bytes(result)


def _normalized_program(lines: list[tuple[int, bytes]]) -> bytes:
    """Build canonical internal 16-bit-length-prefixed logical line records."""
    result = bytearray()
    for line_number, body in lines:
        record_length = 2 + len(body) + 1
        result += record_length.to_bytes(2, "little")
        result += line_number.to_bytes(2, "little")
        result += body + b"\x00"
    result += b"\x00\x00"
    return bytes(result)


def _extended_program(body: bytes) -> bytes:
    """Build a canonical C2P1 envelope with an eight-bit body checksum."""
    checksum = sum(body) & 0xFF
    return (
        b"C2P1"
        + bytes([1, 1, len(body) & 0xFF, len(body) >> 8, checksum, 0])
        + bytes(6)
        + body
    )


@pytest.mark.unit
@pytest.mark.local
class TestProgramCodec:
    """program_codec.asm unit coverage."""

    def test_classify_stock_and_extended_records(self) -> None:
        """Classification should distinguish stock PRG and C2P1 records."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")

        stock_addr = 0xC000
        _write_stream(emu, stock_addr, bytes([0x01, 0x08, 0x00, 0x00]))
        assert not _call(
            emu, "program_classify_file", x=stock_addr & 0xFF, y=stock_addr >> 8
        )
        state = emu.get_state()
        assert state.a == 0
        assert (int(state.p) & 0x01) == 0

        extended_addr = 0xC100
        _write_stream(emu, extended_addr, _extended_program(b"test"))
        assert not _call(
            emu,
            "program_classify_file",
            x=extended_addr & 0xFF,
            y=extended_addr >> 8,
        )
        state = emu.get_state()
        assert state.a == 1
        assert (int(state.p) & 0x01) == 0

    def test_stock_and_extended_round_trip(self) -> None:
        """Encode and decode helpers should round-trip small records."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")

        stock_src = 0xC200
        stock_lines = [(10, bytes([0x99, ord("1")])), (20, bytes([0x80]))]
        stock_payload = _stock_program(stock_lines)
        _write_stream(emu, stock_src, stock_payload)
        assert not _call(
            emu, "program_decode_stock", x=stock_src & 0xFF, y=stock_src >> 8
        )
        state = emu.get_state()
        stock_decoded = state.x | (state.y << 8)
        assert stock_decoded == stock_src
        assert _read_stream(emu, stock_decoded) == _normalized_program(stock_lines)

        assert not _call(
            emu,
            "program_encode_stock",
            x=stock_decoded & 0xFF,
            y=stock_decoded >> 8,
        )
        state = emu.get_state()
        stock_encoded = state.x | (state.y << 8)
        assert stock_encoded == stock_src
        assert _read_stream(emu, stock_encoded) == stock_payload

        ext_src = 0xC300
        ext_payload = _extended_program(bytes([0xAA, 0xBB, 0xCC, 0xDD]))
        _write_stream(emu, ext_src, ext_payload)
        assert not _call(
            emu, "program_decode_extended", x=ext_src & 0xFF, y=ext_src >> 8
        )
        state = emu.get_state()
        ext_decoded = state.x | (state.y << 8)
        assert ext_decoded == ext_src
        assert _read_stream(emu, ext_decoded) == bytes([0xAA, 0xBB, 0xCC, 0xDD])

        assert not _call(
            emu,
            "program_encode_extended",
            x=ext_decoded & 0xFF,
            y=ext_decoded >> 8,
        )
        state = emu.get_state()
        ext_encoded = state.x | (state.y << 8)
        assert ext_encoded == ext_src
        encoded_payload = _read_stream(emu, ext_encoded)
        assert encoded_payload[:4] == b"C2P1"
        assert encoded_payload[4] == 0x01
        assert encoded_payload[16:] == bytes([0xAA, 0xBB, 0xCC, 0xDD])

    @pytest.mark.parametrize("format_name", ["stock", "extended"])
    def test_whole_program_stream_round_trip_spans_multiple_pages(
        self, format_name: str
    ) -> None:
        """Arena streams preserve programs spanning multiple GeoRAM pages."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")
        descriptor = 0xCA00
        if format_name == "stock":
            stock_lines = [
                (line * 10, bytes([0x99]) + bytes([64 + line]) * 59)
                for line in range(1, 7)
            ]
            body = _stock_program(stock_lines)
            decode, encode = "program_decode_stock", "program_encode_stock"
            decoded_expected = _normalized_program(stock_lines)
        else:
            decoded_expected = bytes(index & 0xFF for index in range(300))
            body = _extended_program(decoded_expected)
            decode, encode = "program_decode_extended", "program_encode_extended"
        assert len(body) > 253
        _write_stream(emu, descriptor, body)

        assert not _call(emu, decode, x=descriptor & 0xFF, y=descriptor >> 8)
        state = emu.get_state()
        decoded = int(state.x) | (int(state.y) << 8)
        assert _read_stream(emu, decoded) == decoded_expected

        assert not _call(emu, encode, x=decoded & 0xFF, y=decoded >> 8)
        state = emu.get_state()
        encoded = int(state.x) | (int(state.y) << 8)
        assert _read_stream(emu, encoded) == body

    @pytest.mark.parametrize(
        "payload",
        [
            _stock_program([(20, b"\x99"), (10, b"\x80")]),
            b"\x01\x08\x09\x08\x0a\x00\x99\x00\x00\x00",
            b"\x01\x08\x08\x08\x0a\x00\x99",
            b"\x01\x08\x00\x00\xaa",
        ],
        ids=["descending-lines", "bad-link", "missing-terminator", "trailing-data"],
    )
    def test_stock_decoder_rejects_structural_corruption(self, payload: bytes) -> None:
        """Import validates links, ordering, line terminators, and final marker."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")
        source = 0xC600
        _write_stream(emu, source, payload)
        emu.set_x(source & 0xFF)
        emu.set_y(source >> 8)
        emu.execute(_load_symbol_address("program_decode_stock"), 10_000)
        assert int(emu.get_state().p) & 0x01

    def test_stock_encoder_recomputes_every_link(self) -> None:
        """Export ignores stale imported links and emits canonical addresses."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")
        lines = [(10, b"\x99\x31"), (20, b"\x80")]
        canonical = _stock_program(lines)
        decoded = 0xC700
        _write_stream(emu, decoded, _normalized_program(lines))
        assert not _call(emu, "program_encode_stock", x=decoded & 0xFF, y=decoded >> 8)
        state = emu.get_state()
        encoded = int(state.x) | (int(state.y) << 8)
        assert not (int(state.p) & 0x01)
        assert encoded == decoded
        assert _read_stream(emu, encoded) == canonical

    def test_encode_clones_non_scratch_logical_program(self) -> None:
        """SAVE encoding never mutates the published logical-program arena."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")
        lines = [(10, b"\x99\x31"), (20, b"\x80")]
        logical = _normalized_program(lines)
        source = 0xC720
        _write_stream(emu, source, logical, arena=1)

        assert not _call(emu, "program_encode_stock", x=source & 0xFF, y=source >> 8)
        state = emu.get_state()
        encoded = int(state.x) | (int(state.y) << 8)
        assert encoded != source
        assert bytes(emu.read_mem(encoded + index) for index in range(2)) == b"PS"
        assert emu.read_mem(encoded + 4) == STREAM_ARENA
        assert _read_stream(emu, encoded) == _stock_program(lines)
        assert _read_stream(emu, source) == logical

    @pytest.mark.parametrize(
        "mutation",
        ["version", "abi", "length", "checksum", "reserved"],
    )
    def test_extended_decoder_rejects_header_corruption(self, mutation: str) -> None:
        """C2P1 import validates every versioned envelope integrity field."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")
        payload = bytearray(_extended_program(b"\xaa\xbb\xcc\xdd"))
        offsets = {"version": 4, "abi": 5, "length": 6, "checksum": 8, "reserved": 10}
        payload[offsets[mutation]] ^= 1
        source = 0xC800
        _write_stream(emu, source, bytes(payload))
        emu.set_x(source & 0xFF)
        emu.set_y(source >> 8)
        emu.execute(_load_symbol_address("program_decode_extended"), 10_000)
        assert int(emu.get_state().p) & 0x01

    def test_malformed_records_are_rejected(self) -> None:
        """Malformed stock and extended inputs should return carry set."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")

        malformed_stock = 0xC400
        _write_stream(emu, malformed_stock, bytes([0x00, 0x08, 0x10, 0x00]))
        assert _call(
            emu,
            "program_classify_file",
            x=malformed_stock & 0xFF,
            y=malformed_stock >> 8,
        )
        assert _call(
            emu,
            "program_decode_stock",
            x=malformed_stock & 0xFF,
            y=malformed_stock >> 8,
        )

        malformed_extended = 0xC500
        _write_stream(
            emu,
            malformed_extended,
            b"CGS0" + bytes([0x01, 0x01, 0x04, 0x00]) + bytes(8),
        )
        assert _call(
            emu,
            "program_decode_extended",
            x=malformed_extended & 0xFF,
            y=malformed_extended >> 8,
        )

    def test_removed_bounded_record_abi_is_rejected(self) -> None:
        """Codec entry points accept only arena-backed whole-program handles."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        source = 0xC900
        _write_record(emu, source, _stock_program([(10, b"\x99")]))

        for routine in (
            "program_classify_file",
            "program_decode_stock",
            "program_encode_stock",
            "program_decode_extended",
            "program_encode_extended",
        ):
            assert _call(emu, routine, x=source & 0xFF, y=source >> 8)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("magic", 0),
            ("generation", 0x7F),
            ("reserved", 1),
            ("extent", 0x81),
        ],
    )
    def test_malformed_stream_descriptors_are_rejected(
        self, field: str, value: int
    ) -> None:
        """Descriptor identity, generation, reserved byte, and extent are checked."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")
        descriptor = 0xCB00
        payload = _stock_program([(10, b"\x99")])
        _write_stream(emu, descriptor, payload)
        if field == "magic":
            emu.write_mem(descriptor, value)
        elif field == "generation":
            emu.write_mem(descriptor + 5, value)
        elif field == "reserved":
            emu.write_mem(descriptor + 7, value)
        else:
            emu.write_mem(descriptor + 2, 0)
            emu.write_mem(descriptor + 3, value)

        assert _call(
            emu,
            "program_classify_file",
            x=descriptor & 0xFF,
            y=descriptor >> 8,
        )

    def test_extended_empty_body_round_trip(self) -> None:
        """The 16-bit stream representation supports an empty C2P1 body."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        assert not _call(emu, "arena_init_all")
        descriptor = 0xCC00
        _write_stream(emu, descriptor, _extended_program(b""))

        assert not _call(
            emu,
            "program_decode_extended",
            x=descriptor & 0xFF,
            y=descriptor >> 8,
        )
        assert _read_stream(emu, descriptor) == b""
        assert not _call(
            emu,
            "program_encode_extended",
            x=descriptor & 0xFF,
            y=descriptor >> 8,
        )
        assert _read_stream(emu, descriptor) == _extended_program(b"")
