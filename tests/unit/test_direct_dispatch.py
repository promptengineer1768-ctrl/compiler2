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
INPUT_ADDR = 0x0500
READ_HELPER_ADDR = 0x0600
TOKEN_QUIT = 211
STOCK_READY = 0xE386
CPU_PORT_STOCK = 0x37


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
    ignored_jsr_targets: tuple[int, ...] = ()
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
@pytest.mark.parametrize(
    "token", [138, 155, 162, 147, 149, 148, 154, 206, 212, TOKEN_QUIT]
)
def test_classify_direct_only_commands(token: int) -> None:
    """Generated direct-only commands use the command dispatcher."""
    _, state = _execute("direct_classify", token)
    assert state.a == DIRECT_COMMAND
    assert (state.p & 1) == 0


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.parametrize("token", [134, 136, 137, 141, 150, 153, 158, 151])
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
    emu, state = _execute("direct_execute_command", 156)
    assert (state.p & 1) == 0
    assert emu.read_mem(_state_address("direct_last_path")) == DIRECT_COMMAND
    assert emu.read_mem(_state_address("direct_last_token")) == 156
    assert emu.read_mem(_state_address("direct_last_ptr")) == (INPUT_ADDR & 0xFF)
    assert emu.read_mem(_state_address("direct_last_ptr") + 1) == (INPUT_ADDR >> 8)


def _linked_resident_bytes(address: int, length: int) -> bytes:
    """Return linked compiler.bin bytes for a resident absolute address."""
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    offset = 2 + address - load_addr
    return payload[offset : offset + length]


def _georam_routine_bytes(symbol: str, length: int) -> bytes:
    """Return installed geoRAM page bytes for a cold geoasm routine."""
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record = data["routines"][symbol]
    block = int(record["block"])
    page = int(record["page"])
    page_offset = int(record.get("offset", 0))
    georam = (ROOT / "build" / "georam.bin").read_bytes()
    assert georam[:2] == b"\x00\xde"
    destination = (block * 64 + page) * 256 + page_offset
    start = 2 + destination
    return georam[start : start + length]


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.smoke
def test_execute_command_quit_soft_reset() -> None:
    """QUIT records dispatch and follows the locked soft-reset leave sequence.

    ``quit_to_stock`` is non-returning (resets SP, banks stock, JMP READY), so
    the RTS-oriented unit harness cannot execute it end-to-end. Cover the
    production path by checking the geoRAM dispatcher JMP, the locked resident
    body, and the returning CLR/vector helpers.
    """
    quit_addr = _state_address("quit_to_stock")
    dispatch = _georam_routine_bytes("direct_execute_command", 96)
    # cmp #TOKEN_QUIT / beq @quit ... jmp quit_to_stock
    assert bytes([0xC9, TOKEN_QUIT]) in dispatch
    assert bytes([0x4C, quit_addr & 0xFF, quit_addr >> 8]) in dispatch

    quit_body = _linked_resident_bytes(quit_addr, 48)
    vectors_restore = _state_address("vectors_restore")
    nmi_invalidate = _state_address("nmi_invalidate_cont")
    quit_clr = _state_address("quit_explicit_clr")
    assert quit_body[0:2] == bytes([0x78, 0xD8])  # sei / cld
    assert bytes([0xA2, 0xFF, 0x9A]) in quit_body  # ldx #$FF / txs
    assert bytes([0xA9, 0x35, 0x85, 0x01]) in quit_body  # project map
    assert bytes([0x20, vectors_restore & 0xFF, vectors_restore >> 8]) in quit_body
    assert bytes([0x20, nmi_invalidate & 0xFF, nmi_invalidate >> 8]) in quit_body
    assert bytes([0x20, quit_clr & 0xFF, quit_clr >> 8]) in quit_body
    assert bytes([0xA9, CPU_PORT_STOCK, 0x85, 0x01]) in quit_body
    assert bytes([0x4C, STOCK_READY & 0xFF, STOCK_READY >> 8]) in quit_body

    # Returning helpers: vector restore + explicit CLR (keep program).
    emu = _emulator("direct_execute_command")
    emu.write_mem(0x0314, 0x11)
    emu.write_mem(0x0315, 0x22)
    emu.write_mem(0x0318, 0x33)
    emu.write_mem(0x0319, 0x44)
    emu.write_mem(_state_address("vectors_prior_irq"), 0x31)
    emu.write_mem(_state_address("vectors_prior_irq") + 1, 0xEA)
    emu.write_mem(_state_address("vectors_prior_nmi"), 0x47)
    emu.write_mem(_state_address("vectors_prior_nmi") + 1, 0xFE)
    emu.write_mem(_state_address("vectors_installed"), 1)
    emu.execute_rts(_state_address("vectors_restore"), 10_000)
    assert emu.read_mem(0x0314) == 0x31
    assert emu.read_mem(0x0315) == 0xEA
    assert emu.read_mem(0x0318) == 0x47
    assert emu.read_mem(0x0319) == 0xFE
    assert emu.read_mem(_state_address("vectors_installed")) == 0

    emu.write_mem(0x002B, 0x01)
    emu.write_mem(0x002C, 0x08)
    emu.write_mem(0x002D, 0x10)
    emu.write_mem(0x002E, 0x08)
    emu.write_mem(0x002F, 0x99)
    emu.write_mem(0x0030, 0x09)
    emu.write_mem(0x0031, 0xAA)
    emu.write_mem(0x0032, 0x09)
    emu.write_mem(0x0037, 0x00)
    emu.write_mem(0x0038, 0xA0)
    emu.execute_rts(_state_address("quit_explicit_clr"), 10_000)
    assert emu.read_mem(0x002D) == 0x10
    assert emu.read_mem(0x002E) == 0x08
    assert emu.read_mem(0x002F) == 0x10
    assert emu.read_mem(0x0030) == 0x08
    assert emu.read_mem(0x0031) == 0x10
    assert emu.read_mem(0x0032) == 0x08
    assert emu.read_mem(0x0033) == 0x00
    assert emu.read_mem(0x0034) == 0xA0
    assert emu.read_mem(0x0016) == 0x19


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
