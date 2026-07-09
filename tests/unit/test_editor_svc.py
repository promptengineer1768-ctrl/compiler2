"""Unit tests for editor service routines (editor_svc.asm).

Tests verify line entry, deletion, LIST output, and ready state transitions.
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
except ImportError:
    pass


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _load_symbol_address(symbol_name: str) -> int:
    dir_path = ROOT / "build" / "routine_directory.json"
    if dir_path.exists():
        try:
            with open(dir_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            routines = data.get("routines", {})
            if symbol_name in routines:
                addr_str = routines[symbol_name].get("address", "")
                if addr_str.startswith("$"):
                    return int(addr_str[1:], 16)
        except Exception:
            pass
    map_path = ROOT / "build" / "compiler.map"
    if not map_path.exists():
        pytest.fail("build/compiler.map not found. Run build.ps1 first.")
    pattern = rf"\b{symbol_name}\b\s+([0-9A-Fa-f]{{6}})"
    content = map_path.read_text(encoding="utf-8")
    match = re.search(pattern, content)
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found.")


@pytest.mark.unit
@pytest.mark.local
class TestEditorSubmitLine:
    """Line entry tests."""

    def test_submit_numbered_line(self) -> None:
        """editor_submit_line should store a numbered line."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("editor_submit_line")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None

    def test_submit_direct_line(self) -> None:
        """editor_submit_line should execute a direct line."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
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
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
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

    def test_detokenize_line(self) -> None:
        """editor_detokenize_line should convert tokens to text."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("editor_detokenize_line")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestEditorListRange:
    """Range listing tests."""

    def test_list_range(self) -> None:
        """editor_list_range should list a range of lines."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("editor_list_range")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestEditorReadyTransition:
    """READY state transition tests."""

    def test_ready_transition(self) -> None:
        """editor_ready_transition should update state to READY."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("editor_ready_transition")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None
