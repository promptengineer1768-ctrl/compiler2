"""Functional editor workflow tests against the linked compiler image."""

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

LINE_RECORD = 0xCD00
PROG_BASE = 0x0400
RANGE_RECORD = 0x0500


def _address(symbol: str) -> int:
    """Resolve a linked routine address."""
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


def _emulator() -> Any:
    """Load the production compiler image into the local C64 emulator."""
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
    emu.set_georam_enabled(True)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    # EDITOR / EDITOR_PINNED live in RAM_HIGH ($E000+), not compiler.bin.
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
        emu.write_mem(0x0000, 0x2F)
        emu.write_mem(0x0001, 0x35)
    # The editor services are geoRAM XIP overlays; install the sidecar image.
    _load_georam(emu)
    return emu


def _routine_record(symbol: str) -> dict[str, Any]:
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    return directory["routines"][symbol]


def _run_paged(emu: Any, symbol: str, *, x: int, y: int, cycles: int = 50_000) -> Any:
    """Reach a geoRAM routine through the production XY XIP gate.

    Routines with id<256 take the group-0 gate (A=id); ids 256..511 take the
    group-n gate (A=low byte of id), which indexes the group-1 directory.
    """
    record = _routine_record(symbol)
    assert record.get("layer") == "georam", f"{symbol} is not a geoRAM routine"
    routine_id = int(record["id"])
    assert routine_id < 0x200
    if routine_id < 0x100:
        gate = "georam_call_group_0_xy"
    else:
        gate = "georam_call_group_n_xy"
    emu.set_a(routine_id & 0xFF)
    emu.set_x(x)
    emu.set_y(y)
    emu.execute(_address(gate), cycles)
    return emu.get_state()


def _run(emu: Any, symbol: str, handle: int = LINE_RECORD, cycles: int = 50_000) -> Any:
    """Run an editor service through its real entry convention."""
    record = _routine_record(symbol)
    if record.get("layer") == "georam":
        return _run_paged(
            emu, symbol, x=handle & 0xFF, y=handle >> 8, cycles=cycles
        )
    emu.set_x(handle & 0xFF)
    emu.set_y(handle >> 8)
    emu.execute(_address(symbol), cycles)
    return emu.get_state()


def _run_xip_no_args(emu: Any, symbol: str, cycles: int = 50_000) -> Any:
    """Run an argument-free service through its real geoRAM XIP gate."""
    emu.execute(_address("ctx_init"), cycles)
    return _run_paged(emu, symbol, x=0, y=0, cycles=cycles)


def _carry_set(state: Any) -> bool:
    return (int(state.p) & 0x01) != 0


def _read_c_string(emu: Any, addr: int, limit: int = 80) -> bytes:
    out = bytearray()
    for i in range(limit):
        b = emu.read_mem(addr + i)
        if b == 0:
            break
        out.append(b)
    return bytes(out)


def _zp_address(name: str) -> int:
    """Resolve one generated production zero-page symbol."""
    symbols = (ROOT / "build" / "zp_symbols.inc").read_text(encoding="utf-8")
    match = re.search(
        rf"^{re.escape(name)}\s*=\s*\$([0-9A-Fa-f]+)$", symbols, re.MULTILINE
    )
    assert match is not None, name
    return int(match.group(1), 16)


def _load_georam(emu: Any) -> None:
    """Install the sidecar in the required 512 KiB geoRAM device image."""
    payload = (ROOT / "build" / "georam.bin").read_bytes()
    assert payload[:2] == b"\x00\xde"
    # The release sidecar carries linked pages, not a dump of every empty
    # page.  The arena manifest nevertheless allocates across the required
    # 512 KiB (32-block) device; loading only the compact sidecar causes the
    # emulator binding to expose no backing pages beyond its file length.
    image = payload[2:].ljust(512 * 1024, b"\x00")
    emu.load_georam(image)


@pytest.mark.functional
@pytest.mark.local
@pytest.mark.smoke
def test_full_editor_interaction() -> None:
    """Submit, detokenize, list range, delete, and return to READY."""
    emu = _emulator()

    # Canonical tokenized line: line 10, empty body.
    emu.write_mem_range(LINE_RECORD, bytes([10, 0, 0]))

    submit = _run(emu, "editor_submit_line")
    assert submit.a == 0
    assert not _carry_set(submit)

    listed = _run(emu, "editor_detokenize_line")
    assert not _carry_set(listed)
    text_addr = int(listed.x) | (int(listed.y) << 8)
    assert text_addr != 0
    text = _read_c_string(emu, text_addr)
    assert text.startswith(b"10")

    # Stock-linked program: 10 PRINT
    emu.write_mem_range(
        PROG_BASE,
        bytes(
            [
                0x07,
                0x04,  # next = $0407
                10,
                0,  # line number
                0x99,
                0,  # PRINT, end of line
                0,
                0,  # end of program
            ]
        ),
    )
    emu.write_mem_range(
        RANGE_RECORD,
        bytes(
            [
                0,
                0,  # start
                0xFF,
                0xFF,  # end
                PROG_BASE & 0xFF,
                PROG_BASE >> 8,
            ]
        ),
    )
    ranged = _run(emu, "editor_list_range", handle=RANGE_RECORD, cycles=200_000)
    assert not _carry_set(ranged)
    result = _address("editor_result_buffer")
    list_text = _read_c_string(emu, result)
    assert list_text.startswith(b"10 ")
    assert b"PRINT" in list_text

    deleted = _run_xip_no_args(emu, "editor_delete_line")
    assert not _carry_set(deleted)

    ready = _run_xip_no_args(emu, "editor_ready_transition")
    assert ready.a == ord("R")
    assert not _carry_set(ready)


@pytest.mark.functional
@pytest.mark.local
def test_numbered_line_submission_crosses_real_transaction_xip_pages() -> None:
    """A numbered editor line performs begin/put/commit through geoRAM gates."""
    emu = _emulator()
    _load_georam(emu)
    emu.execute(_address("ctx_init"), 20_000)
    # The transactional store owns the 128-page staging arena (type 9).
    # Initializing every manifest-defined arena clears their backing pages, so
    # the small generic editor-service budget is insufficient here.  A partial
    # initializer leaves the staging handle absent and makes the real XIP
    # transaction gate correctly reject the line.
    emu.execute(_address("arena_init_all"), 8_000_000)

    line_buffer = 0xC000
    emu.write_mem_range(line_buffer, b"10 PRINT 1")
    emu.write_mem(_zp_address("zp_linebuf"), line_buffer & 0xFF)
    emu.write_mem(_zp_address("zp_linebuf") + 1, line_buffer >> 8)
    emu.write_mem(_zp_address("zp_line_len"), len(b"10 PRINT 1"))
    emu.execute(_address("program_lines_put_linebuf"), 2_000_000)
    assert not _carry_set(emu.get_state())

    emu.execute(_address("program_lines_get_count"), 500_000)
    assert not _carry_set(emu.get_state())
    assert emu.get_state().a == 1
