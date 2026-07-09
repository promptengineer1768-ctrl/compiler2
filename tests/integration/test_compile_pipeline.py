"""Integration coverage for IR-to-code emission."""

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


def _address(symbol: str) -> int:
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(rf"\bal\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}\b", labels)
    if match is not None:
        return int(match.group(1), 16)
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    return int(data["routines"][symbol]["address"][1:], 16)


@pytest.mark.integration
@pytest.mark.local
def test_statement_ir_flows_into_codegen_stream() -> None:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    dll = ROOT.parent / "tools" / "emu6502.dll"
    if not dll.exists():
        dll = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not dll.exists():
        pytest.skip("Emulator DLL not found")

    emu = C64Emu6502(lib_path=dll)
    setattr(emu, "_compiler2_real_bytes_only", True)
    emu.set_georam_enabled(True)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    emu.write_mem_range(payload[0] | (payload[1] << 8), payload[2:])

    emu.execute(_address("ir_init"), 1000)
    emu.set_a(0x11)
    emu.set_x(0x22)
    emu.set_y(0x33)
    emu.execute(_address("ir_emit_stmt"), 1000)

    ir = emu.read_mem_range(_address("ir_buffer"), _address("ir_buffer") + 3)
    assert ir == bytes([0x01, 0x11, 0x22, 0x33])

    emu.execute(_address("codegen_init"), 1000)
    emu.set_a(ir[1])
    emu.set_x(ir[2])
    emu.set_y(ir[3])
    emu.execute(_address("codegen_emit_stmt"), 1000)
    emu.execute(_address("codegen_finish_line"), 1000)

    length = emu.read_mem(_address("codegen_buffer_len"))
    code = emu.read_mem_range(
        _address("codegen_buffer"), _address("codegen_buffer") + length - 1
    )
    assert code == bytes([0xA9, 0x11, 0xA2, 0x22, 0xA0, 0x33, 0x60])
    emu.execute(_address("codegen_buffer"), 1000)
    state = emu.get_state()
    assert (state.a, state.x, state.y) == (0x11, 0x22, 0x33)


@pytest.mark.integration
@pytest.mark.local
def test_source_flows_through_tokenizer_parser_ir_and_codegen() -> None:
    """The production frontend materializes IR consumed by code generation."""
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    dll = next(
        (
            path
            for path in (
                ROOT.parent / "tools" / "emu6502.dll",
                ROOT.parent / "tools" / "msys-emu6502.dll",
            )
            if path.exists()
        ),
        None,
    )
    if dll is None:
        pytest.skip("Emulator DLL not found")

    emu = C64Emu6502(lib_path=dll)
    setattr(emu, "_compiler2_real_bytes_only", True)
    emu.set_georam_enabled(True)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    emu.write_mem_range(payload[0] | (payload[1] << 8), payload[2:])
    source = 0xC900
    emu.write_mem_range(source, b"10 PRINT 1+2*3\x00")
    emu.set_x(source & 0xFF)
    emu.set_y(source >> 8)
    emu.execute(_address("parse_line"), 20_000)
    assert (emu.get_state().p & 1) == 0

    ir_length = emu.read_mem(_address("ir_buffer_len"))
    ir = emu.read_mem_range(
        _address("ir_buffer"), _address("ir_buffer") + ir_length - 1
    )
    assert ir[-8:] == bytes([0x01, 0x01, 0, 0, 0x00, 0, 0, 0])

    emu.execute(_address("codegen_emit_ir"), 5000)
    code_length = emu.read_mem(_address("codegen_buffer_len"))
    code = emu.read_mem_range(
        _address("codegen_buffer"), _address("codegen_buffer") + code_length - 1
    )
    assert code == bytes([0xA9, 0x01, 0xA2, 0, 0xA0, 0, 0x60])
    emu.execute(_address("codegen_buffer"), 1000)
    state = emu.get_state()
    assert (state.a, state.x, state.y) == (0x01, 0, 0)
