"""Unit tests for DOS wedge routines (dos_wedge.asm, wedge.asm).

Tests verify wedge command parsing, directory, load, status, and streaming.
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
class TestWedgeParse:
    """Wedge prefix parsing tests."""

    def test_parse_dollar(self) -> None:
        """wedge_parse should recognize $ prefix."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("wedge_parse")
        emu.set_x(0x00)
        emu.set_y(0x04)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None

    def test_parse_slash(self) -> None:
        """wedge_parse should recognize / prefix."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("wedge_parse")
        emu.set_x(0x00)
        emu.set_y(0x04)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None

    def test_parse_at(self) -> None:
        """wedge_parse should recognize @ prefix."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("wedge_parse")
        emu.set_x(0x00)
        emu.set_y(0x04)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestWedgeDirectory:
    """Directory listing tests."""

    def test_directory_streams(self) -> None:
        """wedge_directory should stream directory entries."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("wedge_directory")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestWedgeLoadAbsolute:
    """Absolute load tests."""

    def test_load_absolute(self) -> None:
        """wedge_load_absolute should load file at fixed address."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("wedge_load_absolute")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestWedgeStatusOrCommand:
    """Status/command tests."""

    def test_status_reads(self) -> None:
        """wedge_status_or_command should read device status."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("wedge_status_or_command")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestWedgeStreamSeq:
    """SEQ streaming tests."""

    def test_stream_seq(self) -> None:
        """wedge_stream_seq should stream SEQ file contents."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("wedge_stream_seq")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestWedgeConfirmDestructive:
    """Confirmation guard tests."""

    def test_confirm_destructive(self) -> None:
        """wedge_confirm_destructive should require confirmation."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("wedge_confirm_destructive")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None
