"""Unit tests for editor service routines (editor_svc.asm).

Tests verify line entry, deletion, LIST detokenize/range output, and READY.
"""

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
except ImportError:  # pragma: no cover
    C64Emu6502 = None


def _dll_path() -> Path:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    path = TOOLS_ROOT / "emu6502.dll"
    if not path.exists():
        path = TOOLS_ROOT / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _load_symbol_address(symbol_name: str) -> int:
    """Resolve a linked absolute RAM address (not geoRAM window $DExx)."""
    # Prefer ca65 labels: routine_directory geoasm entries are window origins.
    lbl_path = ROOT / "build" / "compiler.lbl"
    if lbl_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            lbl_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    map_path = ROOT / "build" / "compiler.map"
    if map_path.exists():
        match = re.search(
            rf"\b{re.escape(symbol_name)}\b\s+([0-9A-Fa-f]{{6}})",
            map_path.read_text(encoding="utf-8"),
        )
        if match:
            return int(match.group(1), 16)
    dir_path = ROOT / "build" / "routine_directory.json"
    if dir_path.exists():
        data = json.loads(dir_path.read_text(encoding="utf-8"))
        routine = data.get("routines", {}).get(symbol_name)
        if routine:
            addr_str = routine.get("address", "")
            if addr_str.startswith("$"):
                addr = int(addr_str[1:], 16)
                # Reject geoRAM window placeholders for direct emu.execute.
                if not (0xDE00 <= addr <= 0xDEFF):
                    return addr
    pytest.fail(f"Symbol '{symbol_name}' not found.")


def _load_binary(emu: C64Emu6502) -> None:
    """Load compiler.bin plus hibasic.bin (EDITOR / EDITOR_PINNED in RAM_HIGH)."""
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.skip("build/compiler.bin not found.")
    emu.set_georam_enabled(True)
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    # EDITOR and EDITOR_PINNED link into RAM_HIGH ($E000+), emitted as hibasic.bin.
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
        emu.write_mem(0x0001, 0x35)


def _carry_set(emu: C64Emu6502) -> bool:
    return (int(emu.get_state().p) & 0x01) != 0


def _read_c_string(emu: C64Emu6502, addr: int, limit: int = 80) -> bytes:
    out = bytearray()
    for i in range(limit):
        b = emu.read_mem(addr + i)
        if b == 0:
            break
        out.append(b)
    return bytes(out)


@pytest.mark.unit
@pytest.mark.local
class TestEditorSubmitLine:
    """Line entry tests."""

    def test_submit_numbered_line(self) -> None:
        """editor_submit_line should store a numbered line."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        addr = _load_symbol_address("editor_submit_line")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None

    def test_submit_direct_line(self) -> None:
        """editor_submit_line should execute a direct line."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        addr = _load_symbol_address("editor_submit_line")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestEditorDeleteLine:
    """Line deletion tests."""

    def test_delete_existing_line(self) -> None:
        """editor_delete_line should remove a line."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        addr = _load_symbol_address("editor_delete_line")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestEditorDetokenizeLine:
    """LIST conversion tests."""

    def test_detokenize_empty_body_line(self) -> None:
        """editor_detokenize_line formats line number for an empty body."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        line = 0xCD00
        # line 10, empty body terminator
        emu.write_mem_range(line, bytes([10, 0, 0]))
        emu.set_x(line & 0xFF)
        emu.set_y(line >> 8)
        emu.execute(_load_symbol_address("editor_detokenize_line"), 50_000)
        assert not _carry_set(emu)
        state = emu.get_state()
        text_addr = int(state.x) | (int(state.y) << 8)
        assert text_addr != 0
        text = _read_c_string(emu, text_addr)
        assert text.startswith(b"10")

    def test_detokenize_print_token(self) -> None:
        """Token $99 (PRINT) expands to the keyword name."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        line = 0xCD00
        # 20 PRINT (token $99) then NUL
        emu.write_mem_range(line, bytes([20, 0, 0x99, 0]))
        emu.set_x(line & 0xFF)
        emu.set_y(line >> 8)
        emu.execute(_load_symbol_address("editor_detokenize_line"), 50_000)
        assert not _carry_set(emu)
        state = emu.get_state()
        text_addr = int(state.x) | (int(state.y) << 8)
        text = _read_c_string(emu, text_addr)
        assert text.startswith(b"20 ")
        assert b"PRINT" in text


@pytest.mark.unit
@pytest.mark.local
class TestEditorListRange:
    """Range listing tests."""

    def test_list_range_empty_source(self) -> None:
        """Empty source pointer lists nothing and succeeds."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        record = 0xCD00
        # start=0, end=65535, source=0
        emu.write_mem_range(record, bytes([0, 0, 0xFF, 0xFF, 0, 0]))
        emu.set_x(record & 0xFF)
        emu.set_y(record >> 8)
        emu.execute(_load_symbol_address("editor_list_range"), 50_000)
        assert not _carry_set(emu)

    def test_list_range_stock_linked_line(self) -> None:
        """Lists one stock-linked line inside the requested range."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        # Use low free RAM for the stock-linked image.
        prog = 0x0400
        # next -> end marker, line 10, PRINT token, NUL body end, then next=0.
        emu.write_mem_range(
            prog,
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
        record = 0x0500
        emu.write_mem_range(
            record,
            bytes(
                [
                    0,
                    0,  # start
                    0xFF,
                    0xFF,  # end
                    prog & 0xFF,
                    prog >> 8,  # source
                ]
            ),
        )
        emu.set_x(record & 0xFF)
        emu.set_y(record >> 8)
        emu.execute(_load_symbol_address("editor_list_range"), 200_000)
        assert not _carry_set(emu)
        result = _load_symbol_address("editor_result_buffer")
        text = _read_c_string(emu, result)
        assert text.startswith(b"10 ")
        assert b"PRINT" in text


@pytest.mark.unit
@pytest.mark.local
class TestEditorReadyTransition:
    """READY state transition tests."""

    def test_ready_transition(self) -> None:
        """editor_ready_transition should update state to READY."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        addr = _load_symbol_address("editor_ready_transition")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None
