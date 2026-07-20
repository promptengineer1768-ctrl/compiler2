"""Unit tests for arena-backed transactional program storage."""

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
PROGRAM_INPUT_ARENA = 8
LINE_INPUT_ARENA = 6
ARENA_GENERATION = 1


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
    pytest.fail(f"Symbol {symbol_name!r} not found in linked outputs.")


GEORAM_WINDOW = 0xDE00
GEORAM_PAGE = 0xDFFE
GEORAM_BLOCK = 0xDFFF


def _load_binary(emu: C64Emu6502) -> None:
    """Load the real linked compiler plus the geoRAM image and enable geoRAM."""
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_address = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_address, payload[2:])
    georam_path = ROOT / "build" / "georam.bin"
    if not georam_path.exists():
        pytest.fail("build/georam.bin not found. Run build.ps1 first.")
    image = georam_path.read_bytes()
    assert image[:2] == b"\x00\xde"
    emu.set_georam_enabled(True)
    backing_size = len(emu.export_georam())
    payload_bytes = image[2:]
    assert backing_size >= len(payload_bytes)
    emu.load_georam(payload_bytes + bytes(backing_size - len(payload_bytes)))


def _load_routine_record(symbol: str) -> dict[str, object]:
    """Return the routine_directory.json entry for one routine."""
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    record = data["routines"][symbol]
    assert isinstance(record, dict)
    return record


def _run_paged(emu: C64Emu6502, routine: str, *, x: int, y: int) -> None:
    """Reach a geoRAM routine through the production XY XIP gate.

    The program-store transaction routines take their pointer arguments in
    X/Y and leave the caller's X/Y (or a returned descriptor) intact, with A
    free. They are geoRAM-paged overlays (offset 0) that also select arena
    data pages during execution, so they must be entered through the real XIP
    gate, which maps the code page, preserves the callee carry, and safely
    restores the window -- exactly as production geoasm code reaches them.

    Routine IDs below 256 take the group-0 gate (A=id); IDs 256..511 take the
    group-n gate (A=low byte of id), which indexes the group-1 directory.
    """
    record = _load_routine_record(routine)
    assert record.get("layer") == "georam", f"{routine} is not a geoRAM routine"
    routine_id_obj = record["id"]
    assert isinstance(routine_id_obj, int)
    routine_id = routine_id_obj
    assert routine_id < 0x200
    if routine_id < 0x100:
        gate = "georam_call_group_0_xy"
        emu.set_a(routine_id & 0xFF)
    else:
        gate = "georam_call_group_n_xy"
        emu.set_a(routine_id & 0xFF)
    emu.set_x(x)
    emu.set_y(y)
    emu.execute(_load_symbol_address(gate), MAX_CYCLES)


def _call(emu: C64Emu6502, routine: str, *, a: int = 0, x: int = 0, y: int = 0) -> bool:
    """Execute one production routine and return its carry status.

    geoRAM-paged overlays are reached through the production group-0 XY XIP
    gate (A=routine id, X/Y=args); non-paged routines run at their linked
    address. The gate preserves the callee carry and any descriptor returned
    in X/Y for geoRAM routines.
    """
    record = _load_routine_record(routine)
    if record.get("layer") == "georam":
        _run_paged(emu, routine, x=x, y=y)
    else:
        emu.set_a(a)
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
    arena: int,
    start_page: int = 0,
    generation: int = ARENA_GENERATION,
) -> None:
    """Write one PS descriptor and its complete arena payload."""
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


def _write_put_request(
    emu: C64Emu6502, address: int, transaction: int, line_descriptor: int
) -> None:
    """Write a PP transaction-plus-line request descriptor."""
    emu.write_mem_range(
        address,
        b"PP"
        + transaction.to_bytes(2, "little")
        + line_descriptor.to_bytes(2, "little")
        + b"\x00\x00",
    )


def _write_delete_request(
    emu: C64Emu6502, address: int, transaction: int, line_number: int
) -> None:
    """Write a PD transaction-plus-line-number request descriptor."""
    emu.write_mem_range(
        address,
        b"PD"
        + transaction.to_bytes(2, "little")
        + line_number.to_bytes(2, "little")
        + b"\x00\x00",
    )


def _new_emulator() -> C64Emu6502:
    """Create an initialized emulator with all typed arenas."""
    emu = C64Emu6502(lib_path=_dll_path())
    _load_binary(emu)
    assert not _call(emu, "arena_init_all")
    return emu


@pytest.mark.unit
@pytest.mark.local
class TestProgramStore:
    """Real-byte coverage for arena transactions and atomic publication."""

    def test_replace_from_load_publishes_multi_page_arena_program(self) -> None:
        """LOAD publishes a cloned arena root without a one-byte size ceiling."""
        emu = _new_emulator()
        source = 0xC000
        lines = [
            (line * 10, bytes([0x99]) + bytes([64 + line]) * 90) for line in range(1, 9)
        ]
        payload = _normalized_program(lines)
        assert len(payload) > 700
        _write_stream(emu, source, payload, arena=PROGRAM_INPUT_ARENA)

        assert not _call(
            emu,
            "program_replace_from_load",
            x=source & 0xFF,
            y=source >> 8,
        )
        state = emu.get_state()
        published = int(state.x) | (int(state.y) << 8)
        assert published == _load_symbol_address("__program_store_published")
        assert _read_stream(emu, published) == payload
        assert emu.read_mem(published + 4) == 1

    def test_begin_clones_root_and_abort_preserves_published_bytes(self) -> None:
        """Abort invalidates staging and leaves the published root unchanged."""
        emu = _new_emulator()
        source = 0xC000
        payload = _normalized_program([(10, b"\x99\x31")])
        _write_stream(emu, source, payload, arena=PROGRAM_INPUT_ARENA)
        assert not _call(
            emu,
            "program_replace_from_load",
            x=source & 0xFF,
            y=source >> 8,
        )
        published = _load_symbol_address("__program_store_published")
        before_header = bytes(emu.read_mem(published + index) for index in range(8))
        before_payload = _read_stream(emu, published)

        assert not _call(emu, "program_tx_begin")
        state = emu.get_state()
        transaction = int(state.x) | (int(state.y) << 8)
        assert bytes(emu.read_mem(transaction + index) for index in range(2)) == b"PT"
        assert not _call(
            emu,
            "program_tx_abort",
            x=transaction & 0xFF,
            y=transaction >> 8,
        )
        assert bytes(emu.read_mem(published + index) for index in range(8)) == (
            before_header
        )
        assert _read_stream(emu, published) == before_payload
        assert _call(
            emu,
            "program_tx_abort",
            x=transaction & 0xFF,
            y=transaction >> 8,
        )

    def test_put_replace_delete_and_commit_publish_sorted_program(self) -> None:
        """PP/PD requests edit staging and commit one normalized sorted root."""
        emu = _new_emulator()
        empty = 0xC000
        _write_stream(
            emu,
            empty,
            _normalized_program([]),
            arena=PROGRAM_INPUT_ARENA,
        )
        assert not _call(
            emu,
            "program_replace_from_load",
            x=empty & 0xFF,
            y=empty >> 8,
        )
        assert not _call(emu, "program_tx_begin")
        state = emu.get_state()
        transaction = int(state.x) | (int(state.y) << 8)

        request = 0xC100
        line_descriptor = 0xC120
        edits = [
            (20, b"\x99\x32", 0),
            (10, b"\x99\x31", 1),
            (10, b"\x99\x33", 2),
        ]
        for line_number, body, start_page in edits:
            _write_stream(
                emu,
                line_descriptor,
                _normalized_program([(line_number, body)]),
                arena=LINE_INPUT_ARENA,
                start_page=start_page,
            )
            _write_put_request(emu, request, transaction, line_descriptor)
            assert not _call(
                emu,
                "program_tx_put_line",
                x=request & 0xFF,
                y=request >> 8,
            )

        _write_delete_request(emu, request, transaction, 20)
        assert not _call(
            emu,
            "program_tx_delete_line",
            x=request & 0xFF,
            y=request >> 8,
        )
        assert not _call(
            emu,
            "program_tx_commit",
            x=transaction & 0xFF,
            y=transaction >> 8,
        )
        state = emu.get_state()
        published = int(state.x) | (int(state.y) << 8)
        assert _read_stream(emu, published) == _normalized_program([(10, b"\x99\x33")])

    def test_forged_or_stale_transaction_cannot_publish(self) -> None:
        """Identity, state, and base-generation checks guard publication."""
        emu = _new_emulator()
        source = 0xC000
        payload = _normalized_program([(10, b"\x80")])
        _write_stream(emu, source, payload, arena=PROGRAM_INPUT_ARENA)
        assert not _call(
            emu,
            "program_replace_from_load",
            x=source & 0xFF,
            y=source >> 8,
        )
        published = _load_symbol_address("__program_store_published")
        before = _read_stream(emu, published)
        assert not _call(emu, "program_tx_begin")
        state = emu.get_state()
        transaction = int(state.x) | (int(state.y) << 8)

        assert _call(emu, "program_tx_commit", x=0, y=0)
        assert _read_stream(emu, published) == before
        assert not _call(
            emu,
            "program_tx_abort",
            x=transaction & 0xFF,
            y=transaction >> 8,
        )
        assert _call(
            emu,
            "program_tx_commit",
            x=transaction & 0xFF,
            y=transaction >> 8,
        )
        assert _read_stream(emu, published) == before

    def test_invalid_load_or_edit_preserves_published_root(self) -> None:
        """Malformed normalized records fail before root publication."""
        emu = _new_emulator()
        source = 0xC000
        baseline = _normalized_program([(10, b"\x99")])
        _write_stream(emu, source, baseline, arena=PROGRAM_INPUT_ARENA)
        assert not _call(
            emu,
            "program_replace_from_load",
            x=source & 0xFF,
            y=source >> 8,
        )
        published = _load_symbol_address("__program_store_published")

        malformed = b"\x05\x00\x0a\x00\x99\x01\x00\x00"
        _write_stream(emu, source, malformed, arena=PROGRAM_INPUT_ARENA)
        assert _call(
            emu,
            "program_replace_from_load",
            x=source & 0xFF,
            y=source >> 8,
        )
        assert _read_stream(emu, published) == baseline

        assert not _call(emu, "program_tx_begin")
        state = emu.get_state()
        transaction = int(state.x) | (int(state.y) << 8)
        request = 0xC100
        line_descriptor = 0xC120
        _write_stream(
            emu,
            line_descriptor,
            malformed,
            arena=LINE_INPUT_ARENA,
        )
        _write_put_request(emu, request, transaction, line_descriptor)
        assert _call(
            emu,
            "program_tx_put_line",
            x=request & 0xFF,
            y=request >> 8,
        )
        assert _read_stream(emu, published) == baseline
