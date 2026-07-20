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

MAX_CYCLES = 8_000_000


def _dll_path() -> Path:
    """Return the local C64 emulator binding DLL."""
    for name in ("emu6502.dll", "msys-emu6502.dll"):
        path = TOOLS_ROOT / name
        if path.exists():
            return path
    pytest.skip("Emulator DLL not found in tools folder.")


def _address(symbol: str) -> int:
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(rf"\bal\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}\b", labels)
    if match is not None:
        return int(match.group(1), 16)
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    return int(data["routines"][symbol]["address"][1:], 16)


def _load_binary(emu: C64Emu6502) -> None:
    """Load the real linked compiler plus the geoRAM overlay and enable it."""
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
    # Code generation lowers IR into RAM_HIGH cold code (HIBASIC / EDITOR /
    # WEDGE / COMPRESSOR) during compilation, so install the overlay image.
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())


def _call(
    emu: C64Emu6502,
    symbol: str,
    *,
    a: int = 0,
    x: int = 0,
    y: int = 0,
    cycles: int = 20_000,
) -> None:
    """Execute one production routine at its linked real-byte address.

    The compiler's geoasm routines all resolve to linked trampoline addresses
    in compiler.lbl; those trampolines bank the routine's geoRAM page and jump
    to the $DE00 window, so executing at the linked address drives the real
    production path with the caller's registers intact.
    """
    emu.set_a(a)
    emu.set_x(x)
    emu.set_y(y)
    emu.execute(_address(symbol), cycles)


@pytest.mark.integration
@pytest.mark.local
def test_statement_ir_flows_into_codegen_stream() -> None:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    _load_binary(emu)

    _call(emu, "ir_init")
    _call(emu, "ir_emit_stmt", a=0x11, x=0x22, y=0x33)

    ir = emu.read_mem_range(_address("ir_buffer"), _address("ir_buffer") + 3)
    assert ir == bytes([0x01, 0x11, 0x22, 0x33])

    _call(emu, "codegen_init")
    _call(emu, "codegen_emit_stmt", a=ir[1], x=ir[2], y=ir[3])
    _call(emu, "codegen_finish_line")

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
    emu = C64Emu6502(lib_path=_dll_path())
    _load_binary(emu)

    source = 0xC900
    emu.write_mem_range(source, b"10 PRINT 1+2*3\x00")
    _call(emu, "parse_line", x=source & 0xFF, y=source >> 8)
    assert (emu.get_state().p & 1) == 0

    ir_length = emu.read_mem(_address("ir_buffer_len"))
    ir = emu.read_mem_range(
        _address("ir_buffer"), _address("ir_buffer") + ir_length - 1
    )
    assert ir[-8:] == bytes([0x01, 0x01, 0, 0, 0x00, 0, 0, 0])

    # codegen_emit_ir resolves literal source spans through pipeline_source.
    emu.write_mem(_address("pipeline_source_lo"), source & 0xFF)
    emu.write_mem(_address("pipeline_source_hi"), source >> 8)
    _call(emu, "codegen_emit_ir")
    code_length = emu.read_mem(_address("codegen_buffer_len"))
    code = emu.read_mem_range(
        _address("codegen_buffer"), _address("codegen_buffer") + code_length - 1
    )
    # 1+2*3 respects precedence and is constant-folded to 7 by the codegen
    # expression evaluator, then lowered to a PRINT of that integer literal.
    print_value = _address("io_print_value")
    print_newline = _address("io_print_newline")
    assert code == bytes(
        [
            0xA9,
            0x07,
            0x85,
            0x02,  # LDA #<7 ; STA fac_lo
            0xA9,
            0x00,
            0x85,
            0x03,  # LDA #>7 ; STA fac_hi
            0xA9,
            0x02,  # LDA #kind(int)
            0x20,
            print_value & 0xFF,
            print_value >> 8,  # JSR io_print_value
            0x20,
            print_newline & 0xFF,
            print_newline >> 8,  # JSR io_print_newline
            0x60,  # RTS
        ]
    )
