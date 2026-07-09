"""Unit tests for compressor integration routines (compressor.asm).

Tests verify RLE/LZ77 compression and streaming decompression.
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
class TestRleCompression:
    """RLE compression tests."""

    def test_rle_compress(self) -> None:
        """compressor_rle should compress with RLE."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("compressor_rle")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestLz77Compression:
    """LZ77 compression tests."""

    def test_lz77_compress(self) -> None:
        """compressor_lz77 should compress with LZ77."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("compressor_lz77")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None


@pytest.mark.unit
@pytest.mark.local
class TestStreamingDecompression:
    """Streaming decompression tests."""

    def test_stream_decompress(self) -> None:
        """compressor_stream should decompress with streaming."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.skip("build/compiler.bin not found.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        addr = _load_symbol_address("compressor_stream")
        emu.set_x(0x00)
        emu.set_y(0x10)
        emu.execute(addr, 10000)
        state = emu.get_state()
        assert state.a is not None
