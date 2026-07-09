"""Unit tests for compiler diagnostic formatting."""

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

SOURCE_ADDR = 0xCC00
READ_HELPER_ADDR = 0xC700


def _constant(name: str) -> int:
    """Resolve an assembly constant from the shared constants include."""
    constants = (ROOT / "src" / "common" / "constants.asm").read_text(encoding="utf-8")
    prefix = f"{name}"
    for line in constants.splitlines():
        if line.startswith(prefix):
            return int(line.split("=")[1].strip().removeprefix("$"), 16)
    raise AssertionError(f"missing constant: {name}")


def _address(symbol: str) -> int:
    """Resolve a linked routine or exported data address."""
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(
        rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}$",
        labels,
        re.MULTILINE,
    )
    if match is not None:
        return int(match.group(1), 16)
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    return int(data["routines"][symbol]["address"].removeprefix("$"), 16)


def _emulator() -> Any:
    """Return an emulator loaded with the compiler image."""
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    dll = next(
        (
            path
            for path in (TOOLS_ROOT / "emu6502.dll", TOOLS_ROOT / "msys-emu6502.dll")
            if path.exists()
        ),
        None,
    )
    if dll is None:
        pytest.skip("Emulator DLL not found in tools folder.")
    emu = C64Emu6502(lib_path=dll)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu._compiler2_real_bytes_only = True
    return emu


def _run(emu: Any, symbol: str, a: int, carry: bool = False) -> Any:
    """Invoke one diagnostic routine with source pointer and carry input."""
    emu.set_a(a)
    emu.set_x(SOURCE_ADDR & 0xFF)
    emu.set_y(SOURCE_ADDR >> 8)
    state = emu.get_state()
    emu.set_p((state.p | 1) if carry else (state.p & ~1))
    emu.execute(_address(symbol), 2000)
    return emu.get_state()


def _read(emu: Any, symbol: str, count: int) -> bytes:
    """Read bytes from an exported diagnostic buffer through CPU-visible RAM."""
    base = _address(symbol)
    return bytes(_cpu_read(emu, base + index) for index in range(count))


def _cpu_read(emu: Any, address: int) -> int:
    """Read CPU-visible RAM through a tiny LDA/RTS helper."""
    emu.write_mem_range(
        READ_HELPER_ADDR,
        bytes([0xAD, address & 0xFF, address >> 8, 0x60]),
    )
    emu.execute(READ_HELPER_ADDR, 20)
    return int(emu.get_state().a)


@pytest.mark.unit
@pytest.mark.local
def test_format_error_records_severity_code_and_source() -> None:
    """Errors preserve their code and source location in a stable record."""
    emu = _emulator()
    _run(emu, "diag_format_error", a=1)
    assert _read(emu, "diag_record", 4) == bytes([0, 1, 0x00, 0xCC])


@pytest.mark.unit
@pytest.mark.local
def test_format_warning_is_nonfatal_and_distinct() -> None:
    """Warnings use a distinct severity without setting carry."""
    emu = _emulator()
    state = _run(emu, "diag_format_warning", a=7)
    assert _read(emu, "diag_record", 2) == bytes([1, 7])
    assert (state.p & 1) == 0


@pytest.mark.unit
@pytest.mark.local
def test_source_context_is_bounded_and_tracks_cursor() -> None:
    """Context extraction copies source text without exceeding 32 bytes."""
    emu = _emulator()
    source = b'PRINT "LONG CONTEXT FOR A DIAGNOSTIC MESSAGE"\x00'
    emu.write_mem_range(SOURCE_ADDR, source)
    _run(emu, "diag_format_source_context", a=8)
    assert _cpu_read(emu, _address("diag_context_length")) == 32
    assert _read(emu, "diag_context_buffer", 32) == source[:32]
    assert _cpu_read(emu, _address("diag_record") + 4) == 8


@pytest.mark.unit
@pytest.mark.local
def test_print_error_emits_formatted_output_operation() -> None:
    """Printing emits the formatted context and terminates its output line."""
    emu = _emulator()
    emu.write_mem_range(SOURCE_ADDR, b"PRINT 1\x00")
    _run(emu, "diag_format_error", a=0x2A)
    _run(emu, "diag_format_source_context", a=3)
    _run(emu, "diag_print_error", a=0)
    _run(emu, "diag_print_error", a=0)
    assert _cpu_read(emu, _address("diag_print_count")) == 2
    assert _cpu_read(emu, _address("kernal_output_byte")) == 0x0D


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.parametrize(
    ("kernal_error", "expected"),
    [
        (4, _constant("ERR_FILE_NOT_FOUND")),
        (5, _constant("ERR_DEVICE_NOT_PRESENT")),
        (6, _constant("ERR_NOT_INPUT_FILE")),
        (0xFF, _constant("ERR_FILE_OPEN")),
    ],
)
def test_kernal_error_translation(kernal_error: int, expected: int) -> None:
    """KERNAL failures map to stable Compiler 2 error codes."""
    emu = _emulator()
    state = _run(emu, "diag_error_from_kernal", a=kernal_error, carry=True)
    assert state.a == expected
    assert (state.p & 1) == 1


@pytest.mark.unit
@pytest.mark.local
def test_kernal_success_maps_to_ok() -> None:
    """A clear KERNAL carry maps to ERR_OK and remains successful."""
    emu = _emulator()
    state = _run(emu, "diag_error_from_kernal", a=5, carry=False)
    assert state.a == 0
    assert (state.p & 1) == 0
