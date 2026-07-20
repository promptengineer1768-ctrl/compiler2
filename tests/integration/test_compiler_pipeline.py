"""Integration tests for the eight-boundary compiler coordinator."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None

RECORD_SIZE = 6
SOURCE_HANDLE = 0xC900
REPLAY_ADDR = 0xC900
GEORAM_PAGE = 0xDFFE
GEORAM_BLOCK = 0xDFFF


def _dll_path() -> Path:
    """Return the emulator library used by local assembly tests."""
    for name in ("emu6502.dll", "msys-emu6502.dll"):
        path = TOOLS_ROOT / name
        if path.exists():
            return path
    pytest.skip("Emulator DLL not found in tools folder.")


def _address(symbol: str) -> int:
    """Resolve a linked routine or exported data address."""
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(
        rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}$",
        labels,
        re.MULTILINE,
    )
    if match:
        return int(match.group(1), 16)
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    return int(data["routines"][symbol]["address"].removeprefix("$"), 16)


def _load_binary(emu: Any) -> None:
    """Load the linked compiler, the geoRAM overlay, and the RAM_HIGH image."""
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    image = (ROOT / "build" / "georam.bin").read_bytes()
    assert image[:2] == b"\x00\xde"
    emu.set_georam_enabled(True)
    backing_size = len(emu.export_georam())
    payload_bytes = image[2:]
    assert backing_size >= len(payload_bytes)
    emu.load_georam(payload_bytes + bytes(backing_size - len(payload_bytes)))
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    # The eight-boundary coordinator calls into RAM_HIGH cold code (HIBASIC /
    # EDITOR / WEDGE / COMPRESSOR) during compilation, so install it.
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())


def _routine_record(symbol: str) -> dict[str, Any]:
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record: dict[str, Any] = data["routines"][symbol]
    return record


def _emulator() -> Any:
    """Load the current linked compiler into a fresh emulator."""
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    _load_binary(emu)
    emu.write_mem_range(SOURCE_HANDLE, b"10 PRINT 1+2*3\x00")
    return emu


def _run(emu: Any, symbol: str, a: int = 0, handle: int = SOURCE_HANDLE) -> Any:
    """Invoke one pipeline routine through its production execution layer."""
    record = _routine_record(symbol)
    if record["layer"] == "georam":
        if a:
            assert int(record["offset"]) == 0
            emu.write_mem(GEORAM_BLOCK, int(record["block"]))
            emu.write_mem(GEORAM_PAGE, int(record["page"]))
            emu.set_a(a)
            entry = 0xDE00
        else:
            routine_id = int(record["id"])
            assert 0x100 <= routine_id < 0x200
            emu.set_a(routine_id & 0xFF)
            entry = _address("georam_call_group_n_xy")
    else:
        emu.set_a(a)
        entry = _address(symbol)
    emu.set_x(handle & 0xFF)
    emu.set_y(handle >> 8)
    emu.execute(entry, 8_000_000)
    return emu.get_state()


def _records(emu: Any, count: int) -> bytes:
    """Read serialized pipeline boundary records."""
    base = _address("pipeline_boundary_records")
    return bytes(emu.read_mem(base + offset) for offset in range(count * RECORD_SIZE))


@pytest.mark.integration
@pytest.mark.local
def test_compile_line_runs_boundaries_one_through_seven() -> None:
    """Per-line compilation stops before publication boundary eight."""
    emu = _emulator()
    state = _run(emu, "pipeline_compile_line")
    assert (state.p & 1) == 0
    assert emu.read_mem(_address("pipeline_boundary_count")) == 7
    records = _records(emu, 7)
    assert records[1::RECORD_SIZE] == bytes(range(1, 8))
    assert set(records[0::RECORD_SIZE]) == {1}
    code_len = emu.read_mem(_address("codegen_buffer_len"))
    code = emu.read_mem_range(
        _address("codegen_buffer"), _address("codegen_buffer") + code_len - 1
    )
    # Empty/default IR still ends with RTS; bare PRINT path may emit a value
    # print sequence before the newline.
    assert code[-1] == 0x60
    newline = _address("io_print_newline")
    assert bytes([0x20, newline & 0xFF, newline >> 8]) in code


@pytest.mark.integration
@pytest.mark.local
@pytest.mark.smoke
def test_compile_program_traverses_all_eight_boundaries() -> None:
    """Whole-program compilation reaches installed-image boundary eight."""
    emu = _emulator()
    state = _run(emu, "pipeline_compile_program")
    assert (state.p & 1) == 0
    assert emu.read_mem(_address("pipeline_boundary_count")) == 8
    records = _records(emu, 8)
    assert records[1::RECORD_SIZE] == bytes(range(1, 9))
    assert set(records[4::RECORD_SIZE]) == {2}


@pytest.mark.integration
@pytest.mark.local
def test_serialized_boundary_round_trips_through_validator() -> None:
    """A versioned boundary record passes deterministic replay validation."""
    emu = _emulator()
    state = _run(emu, "pipeline_serialize_boundary", a=5)
    assert (state.p & 1) == 0
    record = _records(emu, 1)
    emu.write_mem_range(REPLAY_ADDR, record)
    state = _run(emu, "pipeline_validate_boundary", a=5, handle=REPLAY_ADDR)
    assert (state.p & 1) == 0


@pytest.mark.integration
@pytest.mark.local
def test_validator_rejects_corrupt_checksum() -> None:
    """Replay validation rejects a record changed after serialization."""
    emu = _emulator()
    _run(emu, "pipeline_serialize_boundary", a=3)
    record = bytearray(_records(emu, 1))
    record[5] ^= 0x80
    emu.write_mem_range(REPLAY_ADDR, bytes(record))
    state = _run(emu, "pipeline_validate_boundary", a=3, handle=REPLAY_ADDR)
    assert (state.p & 1) == 1


@pytest.mark.integration
@pytest.mark.local
def test_failure_is_phase_local_and_transactional() -> None:
    """Failure reporting records context without replacing boundary output."""
    emu = _emulator()
    _run(emu, "pipeline_compile_line")
    before = _records(emu, 7)
    state = _run(emu, "pipeline_report_failure", a=4, handle=0x1251)
    assert (state.p & 1) == 1
    assert emu.read_mem(_address("pipeline_failure_phase")) == 4
    assert emu.read_mem(_address("pipeline_failure_code")) == 0x12
    assert _records(emu, 7) == before
