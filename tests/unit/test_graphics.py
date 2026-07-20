"""Unit tests for graphics routines (graphics.asm).

Covers bitmap mode entry/exit, screen-matrix copy through the RAM-under-I/O
gate, and pixel/matrix bounds validation per docs/GRAPHICS_MEMORY.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502, StopCondition
except ImportError:
    pass

# Workspace after linked image end (~$CED2); safe for test records/buffers.
PLAN_ADDR = 0xCF00
RECORD_ADDR = 0xCF10
DESC_ADDR = 0xCF20
SRC_ADDR = 0xCF40

VIC_D011 = 0xD011
VIC_D016 = 0xD016
VIC_D018 = 0xD018
VIC_D020 = 0xD020
VIC_D021 = 0xD021
CIA2_PRA = 0xDD00
CIA2_DDRA = 0xDD02
CPU_PORT = 0x0001
MATRIX_BASE = 0xDC00


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _load_symbol_address(symbol_name: str) -> int:
    """Resolve a linked symbol address from labels, routine dir, or map."""
    labels = ROOT / "build" / "compiler.lbl"
    if labels.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)

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


def _load_binary(emu: C64Emu6502) -> None:
    """Install compiler image, HIBASIC high RAM, and enable geoRAM for reserve."""
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
    if hasattr(emu, "set_georam_enabled"):
        emu.set_georam_enabled(True)
    georam_path = ROOT / "build" / "georam.bin"
    if not georam_path.exists():
        pytest.fail("build/georam.bin not found. Run build.ps1 first.")
    image = georam_path.read_bytes()
    assert image[:2] == b"\x00\xde"
    backing_size = len(emu.export_georam())
    assert backing_size >= len(image) - 2
    emu.load_georam(image[2:] + bytes(backing_size - (len(image) - 2)))
    emu.write_mem(CPU_PORT, 0x35)
    emu.write_mem(0x0000, 0x2F)
    # Unit calls below use the production group-1 XIP gate.
    emu.execute(_load_symbol_address("ctx_init"), 5_000_000)


def _page_bound_xip_page(symbol: str) -> int | None:
    """Return explicit xip_page for a page-bound body, else None."""
    routines = json.loads((ROOT / "manifests" / "routines.json").read_text())[
        "routines"
    ]
    for routine in routines:
        if routine.get("name") == symbol and routine.get("xip_page") is not None:
            return int(routine["xip_page"])
    return None


def _run(emu: C64Emu6502, symbol: str, cycles: int = 200_000) -> int:
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record = directory.get("routines", {}).get(symbol)
    # Only page-bound XIP bodies execute at $DE00; unported geoasm entries may
    # still have a directory record while the real body remains in low RAM.
    if (
        isinstance(record, dict)
        and record.get("layer") == "georam"
        and _page_bound_xip_page(symbol) is not None
    ):
        routine_id = int(record["id"])
        assert 0x100 <= routine_id <= 0x1FF
        # The XY gate leaves X/Y as supplied by the test and gets the routine
        # ID in A, exactly like a production caller.
        emu.set_a(routine_id & 0xFF)
        rc = emu.execute(_load_symbol_address("georam_call_group_n_xy"), cycles)
        assert rc == StopCondition.RTS, f"{symbol} XIP gate did not RTS (rc={rc})"
        return cast(int, rc)
    rc = emu.execute(_load_symbol_address(symbol), cycles)
    assert rc == StopCondition.RTS, f"{symbol} did not RTS (rc={rc})"
    return cast(int, rc)


def _write_plan(emu: C64Emu6502, mode: int) -> None:
    emu.write_mem(PLAN_ADDR, mode & 0xFF)


def _write_transfer(emu: C64Emu6502, src: int, dest: int, length: int) -> None:
    emu.write_mem(RECORD_ADDR + 0, src & 0xFF)
    emu.write_mem(RECORD_ADDR + 1, (src >> 8) & 0xFF)
    emu.write_mem(RECORD_ADDR + 2, dest & 0xFF)
    emu.write_mem(RECORD_ADDR + 3, (dest >> 8) & 0xFF)
    emu.write_mem(RECORD_ADDR + 4, length & 0xFF)
    emu.write_mem(RECORD_ADDR + 5, (length >> 8) & 0xFF)


def _write_descriptor(emu: C64Emu6502, kind: int, x: int, y: int) -> None:
    emu.write_mem(DESC_ADDR + 0, kind & 0xFF)
    emu.write_mem(DESC_ADDR + 1, x & 0xFF)
    emu.write_mem(DESC_ADDR + 2, (x >> 8) & 0xFF)
    emu.write_mem(DESC_ADDR + 3, y & 0xFF)


def _vic_bank(emu: C64Emu6502) -> int:
    return cast(int, emu.read_mem(CIA2_PRA)) & 0x03


def _read_under_io(emu: C64Emu6502, start: int, length: int) -> bytes:
    """Read RAM under the I/O window with $01 temporarily set to all-RAM."""
    emu.write_mem(CPU_PORT, 0x30)
    if hasattr(emu, "_compiler2_under_io"):
        # Drop host shadow so production gate writes in the emu are visible.
        hidden = getattr(emu, "_compiler2_under_io")
        for addr in range(start, start + length):
            hidden.pop(addr, None)
    data = emu.read_mem_range(start, start + length - 1)
    emu.write_mem(CPU_PORT, 0x35)
    return cast(bytes, data)


@pytest.mark.unit
@pytest.mark.local
class TestGraphicsEnter:
    """Bitmap mode entry tests."""

    def test_enter_bitmap_mode(self) -> None:
        """graphics_enter selects VIC bank 3, $D018=$78, and bitmap control."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)

        # Stock-like pre-state: bank 0, text pointers, text mode
        emu.write_mem(CIA2_DDRA, 0x3F)
        emu.write_mem(CIA2_PRA, 0xC7)  # bank bits %11
        emu.write_mem(VIC_D011, 0x1B)
        emu.write_mem(VIC_D016, 0xC8)
        emu.write_mem(VIC_D018, 0x17)

        _write_plan(emu, mode=0)  # hires
        emu.set_x(PLAN_ADDR & 0xFF)
        emu.set_y((PLAN_ADDR >> 8) & 0xFF)
        _run(emu, "graphics_enter", cycles=300_000)

        assert (emu.get_state().p & 0x01) == 0, "enter must clear carry"
        assert emu.read_mem(CPU_PORT) == 0x35
        assert _vic_bank(emu) == 0x00, "must select VIC bank 3"
        assert emu.read_mem(VIC_D018) == 0x78
        assert emu.read_mem(VIC_D011) == 0x3B
        assert (emu.read_mem(VIC_D016) & 0x10) == 0, "hires clears MCM"
        assert emu.read_mem(_load_symbol_address("graphics_mode")) == 0
        assert emu.read_mem(_load_symbol_address("graphics_active")) == 1
        ceiling = _load_symbol_address("graphics_dynamic_ceiling")
        assert emu.read_mem(ceiling) == 0xFF
        assert emu.read_mem(ceiling + 1) == 0xDB

    def test_enter_multicolor_sets_mcm(self) -> None:
        """Multicolor plan mode sets $D016 multicolor bit."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.write_mem(CIA2_DDRA, 0x3F)
        emu.write_mem(CIA2_PRA, 0xC7)
        _write_plan(emu, mode=1)
        emu.set_x(PLAN_ADDR & 0xFF)
        emu.set_y((PLAN_ADDR >> 8) & 0xFF)
        _run(emu, "graphics_enter", cycles=300_000)

        assert (emu.get_state().p & 0x01) == 0
        assert emu.read_mem(VIC_D018) == 0x78
        assert (emu.read_mem(VIC_D016) & 0x10) != 0
        assert emu.read_mem(_load_symbol_address("graphics_mode")) == 1

    def test_enter_rejects_bad_mode(self) -> None:
        """Unsupported plan mode returns illegal quantity with carry set."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        _write_plan(emu, mode=2)
        emu.set_x(PLAN_ADDR & 0xFF)
        emu.set_y((PLAN_ADDR >> 8) & 0xFF)
        _run(emu, "graphics_enter", cycles=10_000)

        assert (emu.get_state().p & 0x01) == 1
        assert emu.get_state().a == 0x0E  # ERR_ILLEGAL_QUANTITY
        assert emu.read_mem(CPU_PORT) == 0x35


@pytest.mark.unit
@pytest.mark.local
class TestGraphicsExit:
    """Text mode restore tests."""

    def test_exit_bitmap_mode(self) -> None:
        """graphics_exit restores stock text mode, colors, bank, and ceiling."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)

        # Simulate active bitmap state
        emu.write_mem(CIA2_DDRA, 0x3F)
        emu.write_mem(CIA2_PRA, 0xC4)  # bank 3
        emu.write_mem(VIC_D011, 0x3B)
        emu.write_mem(VIC_D016, 0xD8)
        emu.write_mem(VIC_D018, 0x78)
        emu.write_mem(VIC_D020, 0x06)
        emu.write_mem(VIC_D021, 0x06)
        emu.write_mem(_load_symbol_address("graphics_mode"), 1)
        emu.write_mem(_load_symbol_address("graphics_active"), 1)
        ceiling = _load_symbol_address("graphics_dynamic_ceiling")
        emu.write_mem(ceiling, 0xFF)
        emu.write_mem(ceiling + 1, 0xDB)

        emu.set_a(0)
        _run(emu, "graphics_exit", cycles=10_000)

        assert emu.read_mem(CPU_PORT) == 0x35
        assert emu.read_mem(VIC_D011) == 0x1B
        assert emu.read_mem(VIC_D018) == 0x17
        assert emu.read_mem(VIC_D016) == 0xC8
        assert emu.read_mem(VIC_D020) == 0x00
        assert emu.read_mem(VIC_D021) == 0x0E
        assert _vic_bank(emu) == 0x03, "must restore VIC bank 0"
        assert emu.read_mem(_load_symbol_address("graphics_mode")) == 0
        assert emu.read_mem(_load_symbol_address("graphics_active")) == 0
        assert emu.read_mem(ceiling) == 0xF9
        assert emu.read_mem(ceiling + 1) == 0xFF


@pytest.mark.unit
@pytest.mark.local
class TestGraphicsMatrixCopy:
    """Screen matrix copy tests."""

    def test_matrix_copy(self) -> None:
        """graphics_matrix_copy writes the matrix via RAM-under-I/O and restores $01."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)

        length = 100
        pattern = bytes(((i * 3) + 0xA5) & 0xFF for i in range(length))
        emu.write_mem_range(SRC_ADDR, pattern)

        _write_transfer(emu, SRC_ADDR, MATRIX_BASE, length)
        emu.set_x(RECORD_ADDR & 0xFF)
        emu.set_y((RECORD_ADDR >> 8) & 0xFF)
        _run(emu, "graphics_matrix_copy", cycles=100_000)

        assert (emu.get_state().p & 0x01) == 0
        assert emu.read_mem(CPU_PORT) == 0x35
        assert _read_under_io(emu, MATRIX_BASE, length) == pattern

    def test_matrix_copy_full_1000_chunked(self) -> None:
        """Full 1000-byte matrix transfer stays in bounds and restores mapping."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)

        length = 1000
        pattern = bytes((i & 0xFF) for i in range(length))
        emu.write_mem_range(SRC_ADDR, pattern)
        _write_transfer(emu, SRC_ADDR, MATRIX_BASE, length)
        emu.set_x(RECORD_ADDR & 0xFF)
        emu.set_y((RECORD_ADDR >> 8) & 0xFF)
        _run(emu, "graphics_matrix_copy", cycles=500_000)

        assert (emu.get_state().p & 0x01) == 0
        assert emu.read_mem(CPU_PORT) == 0x35
        assert _read_under_io(emu, MATRIX_BASE, length) == pattern
        # Last matrix byte is $DFE7
        assert _read_under_io(emu, 0xDFE7, 1) == bytes([pattern[-1]])

    def test_matrix_copy_rejects_overflow(self) -> None:
        """Destination past $DFE7 is rejected with illegal quantity."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        _write_transfer(emu, SRC_ADDR, 0xDFE0, 16)  # ends at $DFEF
        emu.set_x(RECORD_ADDR & 0xFF)
        emu.set_y((RECORD_ADDR >> 8) & 0xFF)
        _run(emu, "graphics_matrix_copy", cycles=10_000)

        assert (emu.get_state().p & 0x01) == 1
        assert emu.get_state().a == 0x0E
        assert emu.read_mem(CPU_PORT) == 0x35


@pytest.mark.unit
@pytest.mark.local
class TestGraphicsValidateBounds:
    """Bounds validation tests."""

    def test_validate_bounds(self) -> None:
        """In-range pixel at (0,16) is accepted."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        _write_descriptor(emu, kind=0, x=0, y=0x10)
        emu.set_x(DESC_ADDR & 0xFF)
        emu.set_y((DESC_ADDR >> 8) & 0xFF)
        _run(emu, "graphics_validate_bounds", cycles=5_000)

        assert (emu.get_state().p & 0x01) == 0
        assert emu.read_mem(CPU_PORT) == 0x35

    def test_validate_pixel_corners(self) -> None:
        """Top-left and bottom-right pixels are valid; one past is not."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        for x, y, expect_c in (
            (0, 0, 0),
            (319, 199, 0),
            (320, 0, 1),
            (0, 200, 1),
            (319, 200, 1),
        ):
            _write_descriptor(emu, kind=0, x=x, y=y)
            emu.set_x(DESC_ADDR & 0xFF)
            emu.set_y((DESC_ADDR >> 8) & 0xFF)
            _run(emu, "graphics_validate_bounds", cycles=5_000)
            carry = emu.get_state().p & 0x01
            assert carry == expect_c, f"pixel ({x},{y}) carry={carry}"
            assert emu.read_mem(CPU_PORT) == 0x35

    def test_validate_matrix_cell(self) -> None:
        """Matrix cells accept 0..39 / 0..24 only."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        for x, y, expect_c in (
            (0, 0, 0),
            (39, 24, 0),
            (40, 0, 1),
            (0, 25, 1),
        ):
            _write_descriptor(emu, kind=1, x=x, y=y)
            emu.set_x(DESC_ADDR & 0xFF)
            emu.set_y((DESC_ADDR >> 8) & 0xFF)
            _run(emu, "graphics_validate_bounds", cycles=5_000)
            assert (emu.get_state().p & 0x01) == expect_c
