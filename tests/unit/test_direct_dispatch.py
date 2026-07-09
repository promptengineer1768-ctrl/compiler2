"""Unit tests for immediate-mode direct dispatch."""

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

DIRECT_COMMAND = 0
DIRECT_TEMPORARY = 1
DIRECT_INVALID = 0xFF
INPUT_ADDR = 0xC800
READ_HELPER_ADDR = 0xC700


def _dll_path() -> Path:
    """Return the local emulator library path."""
    for name in ("emu6502.dll", "msys-emu6502.dll"):
        path = TOOLS_ROOT / name
        if path.exists():
            return path
    pytest.skip("Emulator DLL not found in tools folder.")


def _symbol_address(symbol: str) -> int:
    """Resolve a linked routine or data symbol."""
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    raw = data["routines"][symbol]["address"]
    return int(raw.removeprefix("$"), 16)


def _routine_location(symbol: str) -> tuple[int, int]:
    """Return the generated geoRAM block/page placement for a cold routine."""
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record = data["routines"][symbol]
    assert record["layer"] == "georam"
    return int(record["block"]), int(record["page"])


def _state_address(symbol: str) -> int:
    """Resolve linked resident state independently of cold routine placement."""
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(
        rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}$",
        labels,
        re.MULTILINE,
    )
    assert match is not None
    return int(match.group(1), 16)


def _emulator(routine: str) -> Any:
    """Load the current compiler and select one real geoRAM routine page."""
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    georam = (ROOT / "build" / "georam.bin").read_bytes()
    assert len(georam) == 65538
    assert georam[:2] == b"\x00\xde"
    emu.set_georam_enabled(True)
    emu.load_georam(georam[2:])
    block, page = _routine_location(routine)
    emu.write_mem(0xDFFF, block)
    emu.write_mem(0xDFFE, page)
    emu._compiler2_real_bytes_only = True
    return emu


def _execute(
    symbol: str,
    first_byte: int,
    payload: bytes = b"",
) -> tuple[Any, Any]:
    """Execute one direct-dispatch routine with an input record."""
    emu = _emulator(symbol)
    emu.write_mem_range(INPUT_ADDR, bytes([first_byte]) + payload)
    emu.set_x(INPUT_ADDR & 0xFF)
    emu.set_y(INPUT_ADDR >> 8)
    ignored_jsr_targets = ()
    if symbol == "direct_execute_temporary":
        ignored_jsr_targets = (_state_address("codegen_buffer"),)
    emu.execute_rts(
        _symbol_address(symbol),
        20_000,
        ignored_jsr_targets=ignored_jsr_targets,
    )
    return emu, emu.get_state()


def _cpu_read(emu: Any, address: int) -> int:
    """Read CPU-visible RAM through an assembled LDA/RTS helper."""
    emu.write_mem_range(
        READ_HELPER_ADDR,
        bytes([0xAD, address & 0xFF, address >> 8, 0x60]),
    )
    emu.execute(READ_HELPER_ADDR, 20)
    return int(emu.get_state().a)


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.smoke
@pytest.mark.parametrize(
    ("prefix", "kind"),
    [(ord("$"), 0), (ord("@"), 1), (ord("/"), 2), (ord("!"), 3)],
    ids=["directory", "status", "load", "stream"],
)
def test_probe_prefix_recognizes_wedge(prefix: int, kind: int) -> None:
    """Each wedge introducer is recognized before tokenization."""
    _, state = _execute("direct_probe_prefix", prefix)
    assert state.a == kind
    assert (state.p & 1) == 0


@pytest.mark.unit
@pytest.mark.local
def test_probe_prefix_leaves_normal_input_unclaimed() -> None:
    """Normal BASIC text is not consumed by the wedge front door."""
    _, state = _execute("direct_probe_prefix", ord("P"))
    assert state.a == DIRECT_INVALID
    assert (state.p & 1) == 0


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.parametrize("token", [138, 155, 147, 149, 150, 148, 154, 207, 205])
def test_classify_direct_only_commands(token: int) -> None:
    """Generated direct-only commands use the command dispatcher."""
    _, state = _execute("direct_classify", token)
    assert state.a == DIRECT_COMMAND
    assert (state.p & 1) == 0


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.parametrize("token", [134, 136, 137, 141, 153, 158, 151, 156, 206])
def test_classify_immediate_statements_as_temporary(token: int) -> None:
    """Statements legal in both modes use the temporary compiler path."""
    _, state = _execute("direct_classify", token)
    assert state.a == DIRECT_TEMPORARY
    assert (state.p & 1) == 0


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.parametrize("token", [128, 129, 131, 139, 0x7F])
def test_classify_rejects_program_only_or_unknown_tokens(token: int) -> None:
    """Program-only and unknown tokens are illegal direct forms."""
    _, state = _execute("direct_classify", token)
    assert state.a == DIRECT_INVALID
    assert (state.p & 1) == 1


@pytest.mark.unit
@pytest.mark.local
def test_execute_command_records_dispatch() -> None:
    """A direct command records the command path, token, and source pointer."""
    emu, state = _execute("direct_execute_command", 138)
    assert (state.p & 1) == 0
    assert emu.read_mem(_state_address("direct_last_path")) == DIRECT_COMMAND
    assert emu.read_mem(_state_address("direct_last_token")) == 138
    assert emu.read_mem(_state_address("direct_last_ptr")) == (INPUT_ADDR & 0xFF)
    assert emu.read_mem(_state_address("direct_last_ptr") + 1) == (INPUT_ADDR >> 8)


@pytest.mark.unit
@pytest.mark.local
def test_execute_temporary_advances_generation() -> None:
    """An immediate statement is compiled and runs as a disposable generation."""
    emu, state = _execute("direct_execute_temporary", 153, b"PRINT 1\x00")
    assert (state.p & 1) == 0
    assert emu.read_mem(_state_address("direct_last_path")) == DIRECT_TEMPORARY
    assert emu.read_mem(_state_address("direct_last_token")) == 153
    assert _cpu_read(emu, _state_address("direct_temporary_generation")) == 1
    code_length = _cpu_read(emu, _state_address("codegen_buffer_len"))
    code = bytes(
        _cpu_read(emu, _state_address("codegen_buffer") + index)
        for index in range(code_length)
    )
    assert code == bytes([0xA9, 1, 0xA2, 0, 0xA0, 0, 0x60])
    emu.execute_rts(_state_address("codegen_buffer"), 100)
    state = emu.get_state()
    assert (state.a, state.x, state.y) == (1, 0, 0)
