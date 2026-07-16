"""Unit tests for compressor integration routines (compressor.asm).

Tests verify RLE/LZ77 compression and streaming CGS1 decompression write
real output and reject bad input.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_CANDIDATES = (
    ROOT.parent / "tools",
    Path(r"C:\Users\me\Documents\Coding Projects\tools"),
)
for _tools in TOOLS_CANDIDATES:
    if str(_tools) not in sys.path:
        sys.path.insert(0, str(_tools))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:  # pragma: no cover - environment-specific
    C64Emu6502 = None  # type: ignore[misc, assignment]


def _dll_path() -> Path:
    for tools in TOOLS_CANDIDATES:
        for name in ("emu6502.dll", "msys-emu6502.dll"):
            path = tools / name
            if path.exists():
                return path
    pytest.skip("Emulator DLL not found in tools folder.")


def _require_emu() -> type:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    return C64Emu6502


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
    if not map_path.exists():
        pytest.fail("build/compiler.map not found. Run build.ps1 first.")
    pattern = rf"\b{symbol_name}\b\s+([0-9A-Fa-f]{{6}})"
    content = map_path.read_text(encoding="utf-8")
    match = re.search(pattern, content)
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found.")


def _zp_georam_stream() -> int:
    """Return the allocated base of zp_georam_stream from generated symbols."""
    symbols = (ROOT / "build" / "zp_symbols.inc").read_text(encoding="utf-8")
    match = re.search(r"^zp_georam_stream\s*=\s*\$([0-9A-Fa-f]+)$", symbols, re.M)
    if not match:
        pytest.fail("zp_georam_stream missing from build/zp_symbols.inc")
    return int(match.group(1), 16)


def _load_binary(emu: Any) -> None:
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    # COMPRESSOR (and other cold helpers) link into HIBASIC at $E000+.
    hibasic_path = ROOT / "build" / "hibasic.bin"
    if hibasic_path.exists():
        emu.write_mem_range(0xE000, hibasic_path.read_bytes())
    # ALL_RAM so $E000+ HIBASIC image is visible (not KERNAL ROM).
    emu.write_mem(0x0001, 0x30)
    # Stepped mapped execution keeps normal-RAM stores visible to read_mem.
    emu.set_georam_enabled(True)


def _cgs1_rle(unpacked: bytes) -> bytes:
    body = bytearray()
    i = 0
    while i < len(unpacked):
        value = unpacked[i]
        count = 1
        while (
            i + count < len(unpacked)
            and unpacked[i + count] == value
            and count < 255
        ):
            count += 1
        body.append(count)
        body.append(value)
        i += count
    return (
        b"CGS1"
        + bytes([1, 0, len(unpacked) & 0xFF, (len(unpacked) >> 8) & 0xFF])
        + bytes(body)
    )


@pytest.mark.unit
@pytest.mark.local
class TestRleCompression:
    """RLE compression tests."""

    def test_rle_compress_writes_count_value_pairs(self) -> None:
        """compressor_rle must emit (count, value) pairs into the out buffer."""
        emu_cls = _require_emu()
        dll = _dll_path()
        emu = emu_cls(lib_path=dll)
        _load_binary(emu)
        src = 0x6000
        data = bytes([0xAA, 0xAA, 0xAA, 0xBB, 0xBB])
        emu.write_mem_range(src, data)
        emu.set_x(src & 0xFF)
        emu.set_y((src >> 8) & 0xFF)
        emu.set_a(len(data))
        emu.execute(_load_symbol_address("compressor_rle"), 50_000)
        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert state.a == 4  # (3,AA) (2,BB)
        out = _load_symbol_address("compressor_out_buffer")
        assert emu.read_mem(out + 0) == 3
        assert emu.read_mem(out + 1) == 0xAA
        assert emu.read_mem(out + 2) == 2
        assert emu.read_mem(out + 3) == 0xBB
        assert emu.read_mem(_load_symbol_address("compressor_out_length")) == 4

    def test_rle_rejects_zero_length(self) -> None:
        """compressor_rle fails cleanly on A=0."""
        emu_cls = _require_emu()
        dll = _dll_path()
        emu = emu_cls(lib_path=dll)
        _load_binary(emu)
        emu.set_x(0x00)
        emu.set_y(0x60)
        emu.set_a(0)
        emu.execute(_load_symbol_address("compressor_rle"), 10_000)
        assert emu.get_state().p & 0x01


@pytest.mark.unit
@pytest.mark.local
class TestLz77Compression:
    """LZ77 / literal-pack tests."""

    def test_lz77_compress_writes_literal_token(self) -> None:
        """compressor_lz77 must write a literal token plus payload bytes."""
        emu_cls = _require_emu()
        dll = _dll_path()
        emu = emu_cls(lib_path=dll)
        _load_binary(emu)
        src = 0x6000
        data = bytes([0x10, 0x20, 0x30])
        emu.write_mem_range(src, data)
        emu.set_x(src & 0xFF)
        emu.set_y((src >> 8) & 0xFF)
        emu.set_a(len(data))
        emu.execute(_load_symbol_address("compressor_lz77"), 50_000)
        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert state.a == 4  # token + 3 bytes
        out = _load_symbol_address("compressor_out_buffer")
        assert emu.read_mem(out) == 2  # length-1
        assert bytes(emu.read_mem_range(out + 1, out + 3)) == data


@pytest.mark.unit
@pytest.mark.local
class TestStreamingDecompression:
    """Streaming CGS1 decompression tests."""

    def test_stream_decompress_round_trip(self) -> None:
        """compressor_stream expands CGS1/RLE into the output buffer."""
        emu_cls = _require_emu()
        dll = _dll_path()
        emu = emu_cls(lib_path=dll)
        _load_binary(emu)
        # Force default dest (compressor_out_buffer) via zero zp_cgs_dst.
        base = _zp_georam_stream()
        emu.write_mem(base + 2, 0)
        emu.write_mem(base + 3, 0)
        payload = bytes([7, 7, 7, 8, 9, 9])
        stream = _cgs1_rle(payload)
        stream_addr = 0x6000
        emu.write_mem_range(stream_addr, stream)
        emu.set_x(stream_addr & 0xFF)
        emu.set_y((stream_addr >> 8) & 0xFF)
        emu.execute(_load_symbol_address("compressor_stream"), 50_000)
        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert state.a == len(payload)
        out = _load_symbol_address("compressor_out_buffer")
        assert bytes(emu.read_mem_range(out, out + len(payload) - 1)) == payload

    def test_stream_rejects_bad_header(self) -> None:
        """Bad magic must set carry."""
        emu_cls = _require_emu()
        dll = _dll_path()
        emu = emu_cls(lib_path=dll)
        _load_binary(emu)
        stream_addr = 0x6000
        emu.write_mem_range(stream_addr, b"BAD!\x01\x00\x01\x00\x01\x00")
        emu.set_x(stream_addr & 0xFF)
        emu.set_y((stream_addr >> 8) & 0xFF)
        emu.execute(_load_symbol_address("compressor_stream"), 20_000)
        assert emu.get_state().p & 0x01

    def test_loader_decompression_uses_compressor_stream(self) -> None:
        """loader_decompression must decompress the same CGS1/RLE body."""
        emu_cls = _require_emu()
        dll = _dll_path()
        emu = emu_cls(lib_path=dll)
        _load_binary(emu)
        base = _zp_georam_stream()
        emu.write_mem(base + 2, 0)
        emu.write_mem(base + 3, 0)
        payload = bytes([1, 1, 2, 2, 2])
        stream = _cgs1_rle(payload)
        stream_addr = 0x6100
        emu.write_mem_range(stream_addr, stream)
        emu.set_x(stream_addr & 0xFF)
        emu.set_y((stream_addr >> 8) & 0xFF)
        emu.execute(_load_symbol_address("loader_decompression"), 50_000)
        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert state.a == len(payload)
        out = _load_symbol_address("compressor_out_buffer")
        assert bytes(emu.read_mem_range(out, out + len(payload) - 1)) == payload
