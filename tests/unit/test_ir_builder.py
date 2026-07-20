"""Unit tests for the geoasm intermediate-representation builder."""

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
    C64Emu6502 = None

IR_END = 0x00
IR_STMT = 0x01
IR_EXPR = 0x02
IR_VAR_REF = 0x03
IR_ARRAY_REF = 0x04
IR_STRING_REF = 0x05
IR_BRANCH = 0x06
IR_LOOP = 0x07
IR_LITERAL_INT = 0x08
IR_LITERAL_FLOAT = 0x09
IR_LITERAL_STR = 0x0A


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


GEORAM_WINDOW = 0xDE00
GEORAM_PAGE = 0xDFFE
GEORAM_BLOCK = 0xDFFF


def _routine_record(symbol: str) -> dict[str, object]:
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    return data["routines"][symbol]


def _symbol_address(symbol: str) -> int:
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(rf"\bal\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}\b", labels)
    if match is not None:
        return int(match.group(1), 16)
    raw = _routine_record(symbol)["address"]
    assert isinstance(raw, str) and raw.startswith("$")
    return int(raw[1:], 16)


def _run_paged(emu: C64Emu6502, symbol: str) -> None:
    """Bank in the routine's geoRAM page and execute it at the $DE00 window.

    The IR emitters take A/X/Y as record payload, so they cannot be reached
    through the id-in-A group gate. Instead the routine's own page/block is
    selected via the real geoRAM registers and the window is executed with the
    caller's A/X/Y intact, exactly as production geoasm code reaches them once
    banked in.
    """
    record = _routine_record(symbol)
    assert record.get("layer") == "georam", f"{symbol} is not a geoRAM routine"
    assert int(record["offset"]) == 0
    saved = emu.get_state()
    emu.write_mem(GEORAM_BLOCK, int(record["block"]) & 0xFF)
    emu.write_mem(GEORAM_PAGE, int(record["page"]) & 0xFF)
    emu.set_a(saved.a)
    emu.set_x(saved.x)
    emu.set_y(saved.y)
    emu.execute(GEORAM_WINDOW, 5000)


def _new_emu() -> C64Emu6502:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
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
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    _run_paged(emu, "ir_init")
    return emu


def _emit(emu: C64Emu6502, name: str, payload: tuple[int, int, int]) -> None:
    emu.set_a(payload[0])
    emu.set_x(payload[1])
    emu.set_y(payload[2])
    _run_paged(emu, name)


def _records(emu: C64Emu6502) -> bytes:
    length = emu.read_mem(_symbol_address("ir_buffer_len"))
    start = _symbol_address("ir_buffer")
    return emu.read_mem_range(start, start + length - 1) if length else b""


@pytest.mark.unit
@pytest.mark.local
class TestIrBuilder:
    """IR emission behavior tests."""

    @pytest.mark.callable_coverage("ir_finish_line", executor="execute")
    @pytest.mark.callable_coverage("ir_emit_stmt", executor="execute")
    @pytest.mark.callable_coverage("ir_emit_expr", executor="execute")
    def test_init_statement_expression_and_finish(self) -> None:
        emu = _new_emu()
        assert _records(emu) == b""

        _emit(emu, "ir_emit_stmt", (0x11, 0x22, 0x33))
        _emit(emu, "ir_emit_expr", (0x44, 0x55, 0x66))
        _run_paged(emu, "ir_finish_line")

        assert _records(emu) == bytes(
            [
                IR_STMT,
                0x11,
                0x22,
                0x33,
                IR_EXPR,
                0x44,
                0x55,
                0x66,
                IR_END,
                0,
                0,
                0,
            ]
        )

    @pytest.mark.parametrize(
        ("name", "opcode"),
        [
            ("ir_emit_var_ref", IR_VAR_REF),
            ("ir_emit_array_ref", IR_ARRAY_REF),
            ("ir_emit_string_ref", IR_STRING_REF),
            ("ir_emit_branch", IR_BRANCH),
            ("ir_emit_loop", IR_LOOP),
            ("ir_emit_literal_int", IR_LITERAL_INT),
            ("ir_emit_literal_float", IR_LITERAL_FLOAT),
            ("ir_emit_literal_str", IR_LITERAL_STR),
        ],
    )
    def test_each_ir_emission_operation(self, name: str, opcode: int) -> None:
        emu = _new_emu()
        _emit(emu, name, (0xA1, 0xB2, 0xC3))
        assert _records(emu) == bytes([opcode, 0xA1, 0xB2, 0xC3])

    @pytest.mark.callable_coverage("ir_init", executor="execute")
    @pytest.mark.callable_coverage("ir_emit_branch", executor="execute")
    def test_init_resets_existing_records(self) -> None:
        emu = _new_emu()
        _emit(emu, "ir_emit_branch", (1, 2, 3))
        assert _records(emu)
        _run_paged(emu, "ir_init")
        assert _records(emu) == b""

    @pytest.mark.callable_coverage("ir_get_buf_ptr", executor="execute")
    @pytest.mark.callable_coverage("ir_emit_stmt", executor="execute")
    def test_get_buf_ptr_tracks_current_write_position(self) -> None:
        """ir_get_buf_ptr returns the address following the last real record."""
        emu = _new_emu()
        _emit(emu, "ir_emit_stmt", (1, 2, 3))
        _run_paged(emu, "ir_get_buf_ptr")
        state = emu.get_state()
        assert state.x | (state.y << 8) == _symbol_address("ir_buffer") + 4
