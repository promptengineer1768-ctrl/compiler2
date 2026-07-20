"""Unit tests for DOS wedge routines (dos_wedge.asm, wedge.asm).

Tests verify wedge command parsing, directory, load, status, streaming,
confirmation, and development dispatch through linked production bytes.
"""

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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None

from tests.kernal_stubs import install_kernal_stubs  # noqa: E402

# Keep command text out of:
# - screen RAM ($0400), where NULs are not stable under the local emu
# - the linked CODE/RODATA image ($0801..~$C263), which hosts the wedge core
# $C800 is in the disposable hot-page range and is free of production bytes.
RECORD_ADDR = 0xC800


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _load_symbol_address(symbol_name: str) -> int:
    """Resolve a non-XIP symbol from the label file or routine directory."""
    map_path = ROOT / "build" / "compiler.lbl"
    if map_path.exists():
        pattern = rf"^\s*al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}\s*$"
        content = map_path.read_text(encoding="utf-8")
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            return int(match.group(1), 16)
    dir_path = ROOT / "build" / "routine_directory.json"
    if dir_path.exists():
        data = json.loads(dir_path.read_text(encoding="utf-8"))
        routines = data.get("routines", {})
        if symbol_name in routines:
            addr_str = routines[symbol_name].get("address", "")
            if addr_str.startswith("$"):
                return int(addr_str[1:], 16)
    pytest.fail(f"Symbol '{symbol_name}' not found.")


def _new_emu() -> Any:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.skip("build/compiler.bin not found.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
        emu.write_mem(0x0001, 0x35)
    if hasattr(emu, "set_georam_enabled"):
        emu.set_georam_enabled(True)
    georam_path = ROOT / "build" / "georam.bin"
    if not georam_path.exists():
        pytest.fail("build/georam.bin not found. Run build.ps1 first.")
    georam_image = georam_path.read_bytes()
    assert georam_image[:2] == b"\x00\xde"
    # Preserve the emulator's configured capacity (the image only covers
    # installed pages) while making the actual linked XIP bytes executable.
    backing_size = len(emu.export_georam())
    image_payload = georam_image[2:]
    assert backing_size >= len(image_payload)
    emu.load_georam(image_payload + bytes(backing_size - len(image_payload)))
    if hasattr(emu, "set_sp"):
        emu.set_sp(0xFF)
    # Bypass conftest post-hooks so assertions observe real production side effects.
    install_kernal_stubs(emu)
    # The installed path initializes the geoRAM context stack before any
    # group-1 call.  These tests invoke the same gate directly.
    emu.execute(_load_symbol_address("ctx_init"), 50_000)
    # Default disk device used by SETLFS/LOAD/wedge.
    emu.write_mem(0xBA, 8)
    return emu


def _carry_set(emu: Any) -> bool:
    return bool(emu.get_state().p & 0x01)


def _write_command(emu: Any, text: bytes, addr: int = RECORD_ADDR) -> None:
    emu.write_mem_range(addr, text + b"\x00")


def _call(emu: Any, symbol: str, *, a: int = 0, x: int = 0, y: int = 0) -> Any:
    directory = ROOT / "build" / "routine_directory.json"
    if directory.exists():
        record = json.loads(directory.read_text(encoding="utf-8")).get(
            "routines", {}
        ).get(symbol)
        if isinstance(record, dict) and record.get("layer") == "georam":
            # Never execute $DE00 directly: only the gate selects the linked
            # page and restores the caller mapping after the XIP return.
            routine_id = int(record["id"])
            assert 0x100 <= routine_id <= 0x1FF
            emu.set_a(routine_id & 0xFF)
            emu.set_x(x)
            emu.set_y(y)
            emu.execute(_load_symbol_address("georam_call_group_n_xy"), 50_000)
            return emu.get_state()
    emu.set_a(a)
    emu.set_x(x)
    emu.set_y(y)
    emu.execute(_load_symbol_address(symbol), 50_000)
    return emu.get_state()


@pytest.mark.unit
@pytest.mark.local
class TestWedgeParse:
    """Wedge prefix parsing tests."""

    @pytest.mark.parametrize(
        ("text", "kind"),
        [
            (b"$", 0),
            (b"@$", 0),
            (b"@", 1),
            (b"@8", 1),
            (b"@10", 1),
            (b"/FILE", 2),
            (b'/"FILE"', 2),
            (b"!README", 3),
            (b"PRINT", 0xFF),
        ],
        ids=[
            "dollar",
            "at-dollar",
            "at",
            "at-device",
            "at-ten",
            "slash",
            "slash-quoted",
            "bang",
            "normal",
        ],
    )
    def test_parse_kinds(self, text: bytes, kind: int) -> None:
        """wedge_parse classifies each development prefix form."""
        emu = _new_emu()
        _write_command(emu, text)
        state = _call(emu, "wedge_parse", x=RECORD_ADDR & 0xFF, y=RECORD_ADDR >> 8)
        assert not _carry_set(emu)
        assert state.a == kind

    def test_parse_slash_requires_name(self) -> None:
        """Bare / is a syntax error."""
        emu = _new_emu()
        _write_command(emu, b"/")
        _call(emu, "wedge_parse", x=RECORD_ADDR & 0xFF, y=RECORD_ADDR >> 8)
        assert _carry_set(emu)

    def test_parse_bang_requires_name(self) -> None:
        """Bare ! is a syntax error."""
        emu = _new_emu()
        _write_command(emu, b"!")
        _call(emu, "wedge_parse", x=RECORD_ADDR & 0xFF, y=RECORD_ADDR >> 8)
        assert _carry_set(emu)


@pytest.mark.unit
@pytest.mark.local
class TestWedgeDispatchDevelopment:
    """Development dispatcher tests."""

    @pytest.mark.parametrize(
        ("kind", "text"),
        [
            (0, b"$"),
            (1, b"@"),
            (2, b"/FILE"),
            (3, b"!README"),
        ],
        ids=["directory", "status", "load", "stream"],
    )
    def test_dispatch_records_kind(self, kind: int, text: bytes) -> None:
        """wedge_dispatch_development routes each kind to its core handler."""
        emu = _new_emu()
        # EOF on first READST after open so directory/status/stream exit cleanly.
        emu.write_mem(0x90, 0x40)
        _write_command(emu, text)
        state = _call(
            emu,
            "wedge_dispatch_development",
            a=kind,
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert not _carry_set(emu)
        assert emu.read_mem(_load_symbol_address("wedge_last_command")) == kind
        assert state.a is not None

    def test_dispatch_rejects_invalid_kind(self) -> None:
        """Kinds outside 0..3 are syntax errors."""
        emu = _new_emu()
        _call(emu, "wedge_dispatch_development", a=4, x=0, y=0)
        assert _carry_set(emu)


@pytest.mark.unit
@pytest.mark.local
class TestWedgeDirectory:
    """Directory listing tests."""

    def test_directory_streams(self) -> None:
        """wedge_directory records the directory kind and returns cleanly."""
        emu = _new_emu()
        emu.write_mem(0x90, 0x40)
        _write_command(emu, b"$")
        _call(
            emu,
            "wedge_directory",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert not _carry_set(emu)
        assert emu.read_mem(_load_symbol_address("wedge_last_command")) == 0


@pytest.mark.unit
@pytest.mark.local
class TestWedgeLoadAbsolute:
    """Absolute load tests."""

    def test_load_absolute(self) -> None:
        """wedge_load_absolute performs SETNAM/SETLFS/LOAD for /name."""
        emu = _new_emu()
        _write_command(emu, b"/HELLO")
        _call(
            emu,
            "wedge_load_absolute",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert not _carry_set(emu)
        assert emu.read_mem(_load_symbol_address("wedge_last_command")) == 2
        # SETLFS: logical 1, device from $BA, secondary 1 (absolute).
        assert emu.read_mem(0xB8) == 1
        assert emu.read_mem(0xBA) == 8
        assert emu.read_mem(0xB9) == 1
        # SETNAM length is the bare name "HELLO".
        assert emu.read_mem(0xB7) == 5


@pytest.mark.unit
@pytest.mark.local
class TestWedgeStatusOrCommand:
    """Status/command tests."""

    def test_status_reads(self) -> None:
        """Bare @ opens the command channel and streams status."""
        emu = _new_emu()
        emu.write_mem(0x90, 0x40)
        _write_command(emu, b"@")
        _call(
            emu,
            "wedge_status_or_command",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert not _carry_set(emu)
        assert emu.read_mem(_load_symbol_address("wedge_last_command")) == 1

    def test_device_select_updates_fa(self) -> None:
        """@10 writes stock KERNAL fa at $BA."""
        emu = _new_emu()
        _write_command(emu, b"@10")
        _call(
            emu,
            "wedge_status_or_command",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert not _carry_set(emu)
        assert emu.read_mem(0xBA) == 10
        assert emu.read_mem(_load_symbol_address("wedge_current_device")) == 10

    def test_at_dollar_is_directory(self) -> None:
        """@$ is routed as a directory listing, not a command-channel name."""
        emu = _new_emu()
        emu.write_mem(0x90, 0x40)
        _write_command(emu, b"@$")
        _call(
            emu,
            "wedge_status_or_command",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert not _carry_set(emu)
        assert emu.read_mem(_load_symbol_address("wedge_last_command")) == 0

    def test_destructive_requires_confirmation(self) -> None:
        """Scratch forms without confirmation are declined."""
        emu = _new_emu()
        _write_command(emu, b"@S0:FILE")
        emu.write_mem(_load_symbol_address("wedge_destructive_confirmed"), 0)
        _call(
            emu,
            "wedge_status_or_command",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert _carry_set(emu)

    def test_destructive_proceeds_when_confirmed(self) -> None:
        """Scratch forms proceed when the confirmation flag is set."""
        emu = _new_emu()
        emu.write_mem(0x90, 0x40)
        _write_command(emu, b"@S0:FILE")
        emu.write_mem(_load_symbol_address("wedge_destructive_confirmed"), 1)
        _call(
            emu,
            "wedge_status_or_command",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert not _carry_set(emu)
        assert emu.read_mem(_load_symbol_address("wedge_destructive_confirmed")) == 0


@pytest.mark.unit
@pytest.mark.local
class TestWedgeStreamSeq:
    """SEQ streaming tests."""

    def test_stream_seq(self) -> None:
        """wedge_stream_seq records the stream kind and returns cleanly."""
        emu = _new_emu()
        emu.write_mem(0x90, 0x40)
        _write_command(emu, b"!README")
        _call(
            emu,
            "wedge_stream_seq",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert not _carry_set(emu)
        assert emu.read_mem(_load_symbol_address("wedge_last_command")) == 3


@pytest.mark.unit
@pytest.mark.local
class TestWedgeConfirmDestructive:
    """Confirmation guard tests."""

    def test_confirm_accepts_nonzero(self) -> None:
        """Nonzero confirmation byte accepts the destructive operation."""
        emu = _new_emu()
        _write_command(emu, b"\x01")
        _call(
            emu,
            "wedge_confirm_destructive",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert not _carry_set(emu)

    def test_confirm_declines_zero(self) -> None:
        """Zero confirmation byte declines the destructive operation."""
        emu = _new_emu()
        _write_command(emu, b"\x00")
        _call(
            emu,
            "wedge_confirm_destructive",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert _carry_set(emu)


@pytest.mark.unit
@pytest.mark.local
class TestWedgeFormatDirectory:
    """Bounded directory formatting tests."""

    def test_format_copies_entry(self) -> None:
        """wedge_format_directory copies entry text into the output buffer."""
        emu = _new_emu()
        entry = b'10 "COMPILER" PRG'
        _write_command(emu, entry)
        _call(
            emu,
            "wedge_format_directory",
            x=RECORD_ADDR & 0xFF,
            y=RECORD_ADDR >> 8,
        )
        assert not _carry_set(emu)
        assert emu.read_mem(_load_symbol_address("wedge_output_length")) == len(entry)
        out_base = _load_symbol_address("wedge_output_buffer")
        output = bytes(emu.read_mem(out_base + i) for i in range(len(entry)))
        assert output == entry
