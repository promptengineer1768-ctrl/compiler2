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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None  # type: ignore[misc, assignment]

from tests.kernal_stubs import install_kernal_stubs  # noqa: E402

RECORD_ADDR = 0xCE00


def _address(symbol: str) -> int:
    """Resolve a linked routine or exported state address from labels preferred."""
    lbl = ROOT / "build" / "compiler.lbl"
    if lbl.exists():
        import re

        match = re.search(
            rf"^\s*al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}\s*$",
            lbl.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
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
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
        emu.write_mem(0x0001, 0x35)
    if hasattr(emu, "set_georam_enabled"):
        emu.set_georam_enabled(True)
    if hasattr(emu, "set_sp"):
        emu.set_sp(0xFF)
    setattr(emu, "_compiler2_real_bytes_only", True)
    install_kernal_stubs(emu)
    emu.write_mem(0xBA, 8)
    return emu


def _run(emu: Any, symbol: str, command: int = 0, text: bytes = b"TEST\x00") -> Any:
    """Invoke a wedge routine with the shared command record."""
    emu.write_mem_range(RECORD_ADDR, text if text.endswith(b"\x00") else text + b"\x00")
    # EOF after open so streaming handlers return without spinning.
    emu.write_mem(0x90, 0x40)
    emu.set_a(command)
    emu.set_x(RECORD_ADDR & 0xFF)
    emu.set_y(RECORD_ADDR >> 8)
    emu.execute(_address(symbol), 50_000)
    return emu.get_state()


@pytest.mark.functional
@pytest.mark.local
@pytest.mark.parametrize(
    ("command", "routine", "text"),
    [
        (0, "wedge_directory", b"$\x00"),
        (2, "wedge_load_absolute", b"/FILE\x00"),
        (1, "wedge_status_or_command", b"@\x00"),
        (3, "wedge_stream_seq", b"!README\x00"),
    ],
    ids=["directory", "absolute-load", "status", "stream"],
)
def test_development_wedge_paths(command: int, routine: str, text: bytes) -> None:
    """Directory, load, status, and stream forms reach their runtime paths."""
    emu = _emulator()
    dispatched = _run(emu, "wedge_dispatch_development", command, text)
    assert (dispatched.p & 1) == 0
    assert emu.read_mem(_address("wedge_last_command")) == command
    state = _run(emu, routine, command, text)
    assert (state.p & 1) == 0
    assert emu.read_mem(_address("wedge_last_command")) == command


@pytest.mark.functional
@pytest.mark.local
def test_directory_entry_formatting_is_bounded() -> None:
    """Directory text is copied into a bounded runtime output record."""
    emu = _emulator()
    entry = b'10 "COMPILER" PRG\x00'
    state = _run(emu, "wedge_format_directory", text=entry)
    assert (state.p & 1) == 0
    assert emu.read_mem(_address("wedge_output_length")) == len(entry) - 1
    output = bytes(
        emu.read_mem(_address("wedge_output_buffer") + index)
        for index in range(len(entry) - 1)
    )
    assert output == entry[:-1]


@pytest.mark.functional
@pytest.mark.local
def test_device_selection_propagates_to_fa() -> None:
    """@9 updates the stock current-device byte shared with LOAD/SAVE/COMPILE."""
    emu = _emulator()
    _run(emu, "wedge_status_or_command", command=1, text=b"@9\x00")
    assert emu.read_mem(0xBA) == 9
    assert emu.read_mem(_address("wedge_current_device")) == 9


@pytest.mark.functional
@pytest.mark.local
def test_parse_then_dispatch_directory() -> None:
    """Development parse + dispatch handles bare $ end-to-end."""
    emu = _emulator()
    emu.write_mem_range(RECORD_ADDR, b"$\x00")
    emu.write_mem(0x90, 0x40)
    emu.set_x(RECORD_ADDR & 0xFF)
    emu.set_y(RECORD_ADDR >> 8)
    emu.execute(_address("wedge_run_development"), 50_000)
    assert (emu.get_state().p & 1) == 0
    assert emu.read_mem(_address("wedge_last_command")) == 0
