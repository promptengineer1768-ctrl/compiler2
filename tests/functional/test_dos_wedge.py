"""Functional tests for development DOS wedge dispatch."""

from __future__ import annotations

import json
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

RECORD_ADDR = 0xCE00


def _address(symbol: str) -> int:
    """Resolve a linked routine or exported state address."""
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    return int(data["routines"][symbol]["address"].removeprefix("$"), 16)


def _emulator() -> Any:
    """Load the production compiler image into a local emulator."""
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
    return emu


def _run(emu: Any, symbol: str, command: int = 0) -> Any:
    """Invoke a wedge routine with the shared command record."""
    emu.set_a(command)
    emu.set_x(RECORD_ADDR & 0xFF)
    emu.set_y(RECORD_ADDR >> 8)
    emu.execute(_address(symbol), 3000)
    return emu.get_state()


@pytest.mark.functional
@pytest.mark.local
@pytest.mark.parametrize(
    ("command", "routine"),
    [
        (0, "wedge_directory"),
        (2, "wedge_load_absolute"),
        (1, "wedge_status_or_command"),
    ],
    ids=["directory", "absolute-load", "status"],
)
def test_development_wedge_paths(command: int, routine: str) -> None:
    """Directory, absolute load, and status forms reach their runtime paths."""
    emu = _emulator()
    emu.write_mem_range(RECORD_ADDR, b"TEST\x00")
    dispatched = _run(emu, "wedge_dispatch_development", command)
    assert (dispatched.p & 1) == 0
    state = _run(emu, routine, command)
    assert (state.p & 1) == 0
    assert emu.read_mem(_address("wedge_last_command")) == command


@pytest.mark.functional
@pytest.mark.local
def test_directory_entry_formatting_is_bounded() -> None:
    """Directory text is copied into a bounded runtime output record."""
    emu = _emulator()
    entry = b'10 "COMPILER" PRG\x00'
    emu.write_mem_range(RECORD_ADDR, entry)
    state = _run(emu, "wedge_format_directory")
    assert (state.p & 1) == 0
    assert emu.read_mem(_address("wedge_output_length")) == len(entry) - 1
    output = bytes(
        emu.read_mem(_address("wedge_output_buffer") + index)
        for index in range(len(entry) - 1)
    )
    assert output == entry[:-1]
