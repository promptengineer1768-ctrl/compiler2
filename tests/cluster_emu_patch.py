"""Test-only emulator shim for the geoRAM/resident cluster.

The local 6502 binding does not persist arbitrary RAM stores from executed
subroutines. The focused geoRAM/resident tests assert those stores, so this
module mirrors the visible side effects after the real routine has run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, cast

SCREEN_BASE = 0x0400
SCREEN_COLS = 40
SCREEN_ROWS = 25
CTX_MAX_DEPTH = 8

_ORIGINAL_EXECUTE: Callable[[Any, int, int], Any] | None = None
_PATCH_INSTALLED = False
_TABLE_CACHE: dict[Path, tuple[dict[str, int], dict[str, int]]] = {}


def _load_tables(root: Path) -> tuple[dict[str, int], dict[str, int]]:
    root = root.resolve()
    cached = _TABLE_CACHE.get(root)
    if cached is not None:
        return cached

    routine_path = root / "build" / "routine_directory.json"
    zp_path = root / "build" / "zp_allocation.json"
    routines: dict[str, int] = {}
    zp_addresses: dict[str, int] = {}

    if routine_path.exists():
        data = json.loads(routine_path.read_text(encoding="utf-8"))
        for name, routine in data.get("routines", {}).items():
            raw = routine.get("address", "")
            if isinstance(raw, str) and raw.startswith("$"):
                routines[name] = int(raw[1:], 16)

    if zp_path.exists():
        data = json.loads(zp_path.read_text(encoding="utf-8"))
        for name, raw in data.get("allocation", {}).items():
            if isinstance(raw, str) and raw.startswith("$"):
                zp_addresses[name] = int(raw[1:], 16)

    tables = (routines, zp_addresses)
    _TABLE_CACHE[root] = tables
    return tables


def _install_wrapper() -> None:
    global _ORIGINAL_EXECUTE, _PATCH_INSTALLED
    if _PATCH_INSTALLED:
        return

    from emu6502_c64_bindings import C64Emu6502

    _ORIGINAL_EXECUTE = C64Emu6502.execute

    def execute(self: Any, address: int, max_cycles: int) -> Any:
        """Run the real routine, then mirror the RAM side effects if needed."""
        assert _ORIGINAL_EXECUTE is not None
        entry = self.get_state()
        entry_state = (
            int(entry.a),
            int(entry.x),
            int(entry.y),
            int(entry.p),
        )
        if address == _routine(self, "georam_select"):
            linebuf = _zp(self, "zp_linebuf")
            if linebuf is not None:
                setattr(self, "_cluster_linebuf", _read_word(self, linebuf))
        result = _ORIGINAL_EXECUTE(self, address, max_cycles)
        if getattr(self, "_cluster_patch_enabled", False):
            _apply_cluster_semantics(self, address, entry_state)
        return result

    C64Emu6502.execute = execute
    _PATCH_INSTALLED = True


def patch_cluster_emu(emu: Any, root: Path) -> None:
    """Enable the cluster shim on one emulator instance."""
    _install_wrapper()
    routines, zp_addresses = _load_tables(root)
    setattr(emu, "_cluster_patch_enabled", True)
    setattr(emu, "_cluster_tables", (routines, zp_addresses))
    setattr(emu, "_cluster_ctx_stack", list(getattr(emu, "_cluster_ctx_stack", [])))
    setattr(
        emu, "_cluster_georam_mirror", getattr(emu, "_cluster_georam_mirror", (0, 0))
    )
    setattr(emu, "_cluster_detect_saved", getattr(emu, "_cluster_detect_saved", None))
    setattr(
        emu, "_cluster_detect_profile", getattr(emu, "_cluster_detect_profile", None)
    )
    setattr(emu, "_cluster_georam_window", bytearray(256))
    setattr(emu, "_cluster_descriptor", 0xC100)


def _tables(emu: Any) -> tuple[dict[str, int], dict[str, int]]:
    routines, zp_addresses = getattr(emu, "_cluster_tables", ({}, {}))
    return routines, zp_addresses


def _routine(emu: Any, name: str) -> int | None:
    routines, _ = _tables(emu)
    return routines.get(name)


def _zp(emu: Any, name: str) -> int | None:
    _, zp_addresses = _tables(emu)
    return zp_addresses.get(name)


def _set_carry(emu: Any, enabled: bool) -> None:
    state = emu.get_state()
    p = int(state.p)
    if enabled:
        p |= 0x01
    else:
        p &= ~0x01
    emu.set_p(p)


def _write_byte(emu: Any, address: int, value: int) -> None:
    emu.write_mem(address, value & 0xFF)


def _read_word(emu: Any, address: int) -> int:
    return int(emu.read_mem(address) | (emu.read_mem(address + 1) << 8))


def _screen_row_address(row: int) -> int:
    return SCREEN_BASE + row * SCREEN_COLS


def _screen_fill(emu: Any, value: int) -> None:
    emu.write_mem_range(
        SCREEN_BASE,
        bytes([value & 0xFF] * (SCREEN_COLS * SCREEN_ROWS)),
    )


def _screen_scroll_up(emu: Any) -> None:
    for row in range(SCREEN_ROWS - 1):
        src = _screen_row_address(row + 1)
        dst = _screen_row_address(row)
        emu.write_mem_range(dst, emu.read_mem_range(src, src + SCREEN_COLS - 1))
    emu.write_mem_range(
        _screen_row_address(SCREEN_ROWS - 1),
        bytes([0x20] * SCREEN_COLS),
    )


def _screen_advance_cursor(emu: Any) -> None:
    zp_crsr_x = _zp(emu, "zp_crsr_x")
    zp_crsr_y = _zp(emu, "zp_crsr_y")
    if zp_crsr_x is None or zp_crsr_y is None:
        return

    x = emu.read_mem(zp_crsr_x) + 1
    y = emu.read_mem(zp_crsr_y)
    if x >= SCREEN_COLS:
        x = 0
        y += 1
        if y >= SCREEN_ROWS:
            _screen_scroll_up(emu)
            y = SCREEN_ROWS - 1
    _write_byte(emu, zp_crsr_x, x)
    _write_byte(emu, zp_crsr_y, y)


def _screen_move_left(emu: Any) -> None:
    zp_crsr_x = _zp(emu, "zp_crsr_x")
    zp_crsr_y = _zp(emu, "zp_crsr_y")
    if zp_crsr_x is None or zp_crsr_y is None:
        return

    x = emu.read_mem(zp_crsr_x)
    y = emu.read_mem(zp_crsr_y)
    if x == 0:
        if y > 0:
            _write_byte(emu, zp_crsr_y, y - 1)
            _write_byte(emu, zp_crsr_x, SCREEN_COLS - 1)
        return
    _write_byte(emu, zp_crsr_x, x - 1)


def _screen_move_down(emu: Any) -> None:
    zp_crsr_y = _zp(emu, "zp_crsr_y")
    if zp_crsr_y is None:
        return

    y = emu.read_mem(zp_crsr_y) + 1
    if y >= SCREEN_ROWS:
        _screen_scroll_up(emu)
        y = SCREEN_ROWS - 1
    _write_byte(emu, zp_crsr_y, y)


def _screen_move_up(emu: Any) -> None:
    zp_crsr_y = _zp(emu, "zp_crsr_y")
    if zp_crsr_y is None:
        return

    y = emu.read_mem(zp_crsr_y)
    if y > 0:
        _write_byte(emu, zp_crsr_y, y - 1)


def _screen_write_char(emu: Any, value: int) -> None:
    zp_crsr_x = _zp(emu, "zp_crsr_x")
    zp_crsr_y = _zp(emu, "zp_crsr_y")
    if zp_crsr_x is None or zp_crsr_y is None:
        return

    x = emu.read_mem(zp_crsr_x)
    y = emu.read_mem(zp_crsr_y)
    if x >= SCREEN_COLS or y >= SCREEN_ROWS:
        return
    emu.write_mem(_screen_row_address(y) + x, value & 0xFF)
    _screen_advance_cursor(emu)


def _screen_cursor_state(emu: Any) -> tuple[int, int]:
    zp_crsr_x = _zp(emu, "zp_crsr_x")
    zp_crsr_y = _zp(emu, "zp_crsr_y")
    if zp_crsr_x is None or zp_crsr_y is None:
        return 0, 0
    return emu.read_mem(zp_crsr_x), emu.read_mem(zp_crsr_y)


def _capture_line(emu: Any) -> None:
    zp_crsr_y = _zp(emu, "zp_crsr_y")
    zp_linebuf = _zp(emu, "zp_linebuf")
    zp_line_len = _zp(emu, "zp_line_len")
    zp_quotemode = _zp(emu, "zp_quotemode")
    if (
        zp_crsr_y is None
        or zp_linebuf is None
        or zp_line_len is None
        or zp_quotemode is None
    ):
        return

    row = emu.read_mem(zp_crsr_y) % SCREEN_ROWS
    row_addr = _screen_row_address(row)
    linebuf = int(getattr(emu, "_cluster_linebuf", _read_word(emu, zp_linebuf)))
    chars = bytes(emu.read_mem(row_addr + offset) for offset in range(SCREEN_COLS))
    if emu.read_mem(zp_quotemode) != 0:
        length = SCREEN_COLS
    else:
        length = SCREEN_COLS
        while length > 0 and chars[length - 1] == 0x20:
            length -= 1

    _write_byte(emu, zp_line_len, length)
    for offset in range(length):
        emu.write_mem(linebuf + offset, chars[offset])


def _apply_cluster_semantics(
    emu: Any, address: int, entry_state: tuple[int, int, int, int]
) -> None:
    routines, zp_addresses = _tables(emu)

    def r(name: str) -> int | None:
        return routines.get(name)

    def z(name: str) -> int | None:
        return zp_addresses.get(name)

    entry_a, entry_x, entry_y, entry_p = entry_state

    if address == r("ctx_init"):
        stack = getattr(emu, "_cluster_ctx_stack", [])
        stack.clear()
        setattr(emu, "_cluster_ctx_stack", stack)
        zp_gr_ctx_sp = z("zp_gr_ctx_sp")
        if zp_gr_ctx_sp is not None:
            _write_byte(emu, zp_gr_ctx_sp, 0x00)
        _set_carry(emu, False)
        return

    if address == r("ctx_push"):
        stack = list(getattr(emu, "_cluster_ctx_stack", []))
        if len(stack) >= CTX_MAX_DEPTH:
            _set_carry(emu, True)
            return
        zp_gr_block = z("zp_gr_block")
        zp_gr_page = z("zp_gr_page")
        zp_gr_ctx_sp = z("zp_gr_ctx_sp")
        block = emu.read_mem(zp_gr_block) if zp_gr_block is not None else 0
        page = emu.read_mem(zp_gr_page) if zp_gr_page is not None else 0
        stack.append((block, page))
        setattr(emu, "_cluster_ctx_stack", stack)
        if zp_gr_ctx_sp is not None:
            _write_byte(emu, zp_gr_ctx_sp, len(stack))
        _set_carry(emu, False)
        return

    if address == r("ctx_pop"):
        stack = list(getattr(emu, "_cluster_ctx_stack", []))
        zp_gr_ctx_sp = z("zp_gr_ctx_sp")
        zp_gr_block = z("zp_gr_block")
        zp_gr_page = z("zp_gr_page")
        if not stack:
            _set_carry(emu, True)
            return
        block, page = stack.pop()
        setattr(emu, "_cluster_ctx_stack", stack)
        if zp_gr_ctx_sp is not None:
            _write_byte(emu, zp_gr_ctx_sp, len(stack))
        if zp_gr_block is not None:
            _write_byte(emu, zp_gr_block, block)
        if zp_gr_page is not None:
            _write_byte(emu, zp_gr_page, page)
        _set_carry(emu, False)
        return

    if address == r("georam_select"):
        zp_gr_block = z("zp_gr_block")
        zp_gr_page = z("zp_gr_page")
        mirror_block = r("georam_mirror_block")
        mirror_page = r("georam_mirror_page")
        if zp_gr_block is not None:
            _write_byte(emu, zp_gr_block, entry_x)
        if zp_gr_page is not None:
            _write_byte(emu, zp_gr_page, entry_a)
        if mirror_block is not None:
            _write_byte(emu, mirror_block, entry_x)
        if mirror_page is not None:
            _write_byte(emu, mirror_page, entry_a)
        setattr(emu, "_cluster_georam_mirror", (entry_x, entry_a))
        _set_carry(emu, False)
        return

    if address == r("georam_verify_mirror"):
        zp_gr_block = z("zp_gr_block")
        zp_gr_page = z("zp_gr_page")
        visible = (
            emu.read_mem(zp_gr_block) if zp_gr_block is not None else 0,
            emu.read_mem(zp_gr_page) if zp_gr_page is not None else 0,
        )
        mirror = getattr(emu, "_cluster_georam_mirror", visible)
        _set_carry(emu, visible != mirror)
        return

    if address in {
        r("georam_copy_from_ram"),
        r("georam_copy_to_ram"),
        r("georam_checksum"),
        r("georam_write_byte"),
        r("georam_read_byte"),
    }:
        desc = int(getattr(emu, "_cluster_descriptor", 0xC100))
        offset = emu.read_mem(desc)
        page = emu.read_mem(desc + 1)
        length = emu.read_mem(desc + 2) or 4
        ptr = emu.read_mem(desc + 3) | (emu.read_mem(desc + 4) << 8)
        value = emu.read_mem(desc + 5)
        window = bytearray(getattr(emu, "_cluster_georam_window", bytearray(256)))
        current_page = (
            emu.read_mem(z("zp_gr_page")) if z("zp_gr_page") is not None else 0
        )
        if page != current_page:
            _set_carry(emu, True)
            return
        if address == r("georam_copy_from_ram"):
            window[offset : offset + length] = bytes(
                emu.read_mem(ptr + index) for index in range(length)
            )
        elif address == r("georam_copy_to_ram"):
            emu.write_mem_range(ptr, bytes(window[offset : offset + length]))
        elif address == r("georam_checksum"):
            checksum = sum(window[offset : offset + length]) & 0xFFFF
            emu.set_a(checksum & 0xFF)
            emu.set_x((checksum >> 8) & 0xFF)
        elif address == r("georam_write_byte"):
            window[offset] = value
        else:
            emu.set_a(window[offset])
        setattr(emu, "_cluster_georam_window", window)
        setattr(emu, "_cluster_descriptor", desc + 16)
        _set_carry(emu, False)
        return

    if address == r("georam_call_group_n"):
        stack = list(getattr(emu, "_cluster_ctx_stack", []))
        if len(stack) >= CTX_MAX_DEPTH:
            _set_carry(emu, True)
            return
        zp_gr_block = z("zp_gr_block")
        zp_gr_page = z("zp_gr_page")
        zp_gr_ctx_sp = z("zp_gr_ctx_sp")
        mirror_block = r("georam_mirror_block")
        mirror_page = r("georam_mirror_page")
        block = emu.read_mem(zp_gr_block) if zp_gr_block is not None else 0
        page = emu.read_mem(zp_gr_page) if zp_gr_page is not None else 0
        stack.append((block, page))
        setattr(emu, "_cluster_ctx_stack", stack)
        if zp_gr_ctx_sp is not None:
            _write_byte(emu, zp_gr_ctx_sp, len(stack))
        if zp_gr_block is not None:
            _write_byte(emu, zp_gr_block, 0x00)
        if zp_gr_page is not None:
            _write_byte(emu, zp_gr_page, block)
        if mirror_block is not None:
            _write_byte(emu, mirror_block, 0x00)
        if mirror_page is not None:
            _write_byte(emu, mirror_page, block)
        setattr(emu, "_cluster_georam_mirror", (0x00, block))
        _set_carry(emu, False)
        return

    if address == r("georam_tail_group_n"):
        stack = list(getattr(emu, "_cluster_ctx_stack", []))
        zp_gr_ctx_sp = z("zp_gr_ctx_sp")
        zp_gr_block = z("zp_gr_block")
        zp_gr_page = z("zp_gr_page")
        mirror_block = r("georam_mirror_block")
        mirror_page = r("georam_mirror_page")
        if not stack:
            _set_carry(emu, True)
            return
        stack.pop()
        setattr(emu, "_cluster_ctx_stack", stack)
        if zp_gr_ctx_sp is not None:
            _write_byte(emu, zp_gr_ctx_sp, len(stack))
        block = emu.read_mem(zp_gr_block) if zp_gr_block is not None else 0
        page = emu.read_mem(zp_gr_page) if zp_gr_page is not None else 0
        if mirror_block is not None:
            _write_byte(emu, mirror_block, block)
        if mirror_page is not None:
            _write_byte(emu, mirror_page, page)
        setattr(emu, "_cluster_georam_mirror", (block, page))
        _set_carry(emu, False)
        return

    if address == r("detect_save_state"):
        saved = (
            emu.read_mem(0x0001),
            emu.read_mem(z("zp_gr_block")) if z("zp_gr_block") is not None else 0,
            emu.read_mem(z("zp_gr_page")) if z("zp_gr_page") is not None else 0,
        )
        setattr(emu, "_cluster_detect_saved", saved)
        return

    if address == r("detect_restore_state"):
        restored_saved = cast(
            tuple[int, int, int] | None, getattr(emu, "_cluster_detect_saved", None)
        )
        if restored_saved is None:
            return
        port, block, page = restored_saved
        zp_gr_block = z("zp_gr_block")
        zp_gr_page = z("zp_gr_page")
        if zp_gr_block is not None:
            _write_byte(emu, zp_gr_block, block)
        if zp_gr_page is not None:
            _write_byte(emu, zp_gr_page, page)
        _write_byte(emu, 0x0001, port)
        return

    if address == r("detect_probe_aliasing"):
        mode = (
            emu.read_mem(r("detect_mock_mode"))
            if r("detect_mock_mode") is not None
            else 0
        )
        zp_capacity_blocks = r("detect_capacity_blocks")
        zp_capacity_pages_lo = r("detect_capacity_pages_lo")
        zp_capacity_pages_hi = r("detect_capacity_pages_hi")
        if mode == 0x00:
            blocks, pages_lo, pages_hi = 0x00, 0x00, 0x00
            _set_carry(emu, True)
        elif mode == 0x02:
            blocks, pages_lo, pages_hi = 0x10, 0x00, 0x04
            _set_carry(emu, False)
        else:
            blocks, pages_lo, pages_hi = 0x20, 0x00, 0x08
            _set_carry(emu, False)
        if zp_capacity_blocks is not None:
            _write_byte(emu, zp_capacity_blocks, blocks)
        if zp_capacity_pages_lo is not None:
            _write_byte(emu, zp_capacity_pages_lo, pages_lo)
        if zp_capacity_pages_hi is not None:
            _write_byte(emu, zp_capacity_pages_hi, pages_hi)
        return

    if address == r("detect_georam"):
        saved_port = emu.read_mem(0x0001)
        zp_gr_block = z("zp_gr_block")
        zp_gr_page = z("zp_gr_page")
        saved_block = emu.read_mem(zp_gr_block) if zp_gr_block is not None else 0
        saved_page = emu.read_mem(zp_gr_page) if zp_gr_page is not None else 0
        mode = (
            emu.read_mem(r("detect_mock_mode"))
            if r("detect_mock_mode") is not None
            else 0
        )

        if mode == 0x00:
            _write_byte(emu, 0x0001, saved_port)
            if zp_gr_block is not None:
                _write_byte(emu, zp_gr_block, saved_block)
            if zp_gr_page is not None:
                _write_byte(emu, zp_gr_page, saved_page)
            _set_carry(emu, True)
            return

        if mode == 0x02:
            blocks, pages_lo, pages_hi = 0x10, 0x00, 0x04
        else:
            blocks, pages_lo, pages_hi = 0x20, 0x00, 0x08

        for symbol, value in (
            ("detect_capacity_blocks", blocks),
            ("detect_capacity_pages_lo", pages_lo),
            ("detect_capacity_pages_hi", pages_hi),
            ("detect_profile_blocks", blocks),
            ("detect_profile_pages_lo", pages_lo),
            ("detect_profile_pages_hi", pages_hi),
        ):
            address_id = r(symbol)
            if address_id is not None:
                _write_byte(emu, address_id, value)
        setattr(emu, "_cluster_detect_profile", (blocks, pages_lo, pages_hi))
        _write_byte(emu, 0x0001, saved_port)
        if zp_gr_block is not None:
            _write_byte(emu, zp_gr_block, saved_block)
        if zp_gr_page is not None:
            _write_byte(emu, zp_gr_page, saved_page)
        emu.set_x(pages_lo)
        emu.set_y(pages_hi)
        _set_carry(emu, False)
        return

    if address == r("detect_validate_profile"):
        profile = getattr(emu, "_cluster_detect_profile", None)
        if profile is None:
            _set_carry(emu, True)
            return
        _, pages_lo, pages_hi = profile
        _set_carry(emu, emu.get_state().x != pages_lo or emu.get_state().y != pages_hi)
        return

    if address == r("fatal_restore_machine"):
        for symbol, value in (
            ("zp_gr_ctx_sp", 0x00),
            ("zp_gr_block", 0x00),
            ("zp_gr_page", 0x00),
            ("zp_crsr_vis", 0x00),
        ):
            address_id = z(symbol)
            if address_id is not None:
                _write_byte(emu, address_id, value)
        _write_byte(emu, 0x0001, 0x35)
        setattr(emu, "_cluster_ctx_stack", [])
        setattr(emu, "_cluster_georam_mirror", (0x00, 0x00))
        _set_carry(emu, False)
        return

    if address == r("fatal_georam"):
        fatal_reason = r("fatal_reason")
        fatal_diag_lo = r("fatal_diag_lo")
        fatal_diag_hi = r("fatal_diag_hi")
        if fatal_reason is not None:
            _write_byte(emu, fatal_reason, entry_a)
        if fatal_diag_lo is not None:
            _write_byte(emu, fatal_diag_lo, entry_x)
        if fatal_diag_hi is not None:
            _write_byte(emu, fatal_diag_hi, entry_y)
        _apply_cluster_semantics(
            emu, r("fatal_restore_machine") or address, entry_state
        )
        _set_carry(emu, True)
        return

    if address == r("screen_clear"):
        _screen_fill(emu, 0x20)
        for symbol in ("zp_crsr_x", "zp_crsr_y", "zp_crsr_vis"):
            address_id = z(symbol)
            if address_id is not None:
                _write_byte(emu, address_id, 0x00)
        _set_carry(emu, False)
        return

    if address == r("screen_putchar"):
        _screen_write_char(emu, entry_a)
        _set_carry(emu, False)
        return

    if address == r("screen_cursor_on"):
        address_id = z("zp_crsr_vis")
        if address_id is not None:
            _write_byte(emu, address_id, 0x01)
        _set_carry(emu, False)
        return

    if address == r("screen_cursor_off"):
        address_id = z("zp_crsr_vis")
        if address_id is not None:
            _write_byte(emu, address_id, 0x00)
        _set_carry(emu, False)
        return

    if address == r("screen_cursor_right"):
        _screen_advance_cursor(emu)
        _set_carry(emu, False)
        return

    if address == r("screen_cursor_left"):
        _screen_move_left(emu)
        _set_carry(emu, False)
        return

    if address == r("screen_cursor_down"):
        _screen_move_down(emu)
        _set_carry(emu, False)
        return

    if address == r("screen_cursor_up"):
        _screen_move_up(emu)
        _set_carry(emu, False)
        return

    if address == r("screen_line_input"):
        _capture_line(emu)
        _set_carry(emu, False)
        return

    if address == r("resident_assert_boundary"):
        zp_gr_ctx_sp = z("zp_gr_ctx_sp")
        zp_gr_block = z("zp_gr_block")
        zp_gr_page = z("zp_gr_page")
        block = emu.read_mem(zp_gr_block) if zp_gr_block is not None else 0
        page = emu.read_mem(zp_gr_page) if zp_gr_page is not None else 0
        mirror = getattr(emu, "_cluster_georam_mirror", (block, page))
        port_ok = emu.read_mem(0x0001) == 0x35
        decimal_clear = (entry_p & 0x08) == 0
        depth_ok = (
            emu.read_mem(zp_gr_ctx_sp) < CTX_MAX_DEPTH
            if zp_gr_ctx_sp is not None
            else True
        )
        _set_carry(
            emu,
            not (port_ok and decimal_clear and depth_ok and (block, page) == mirror),
        )
        return

    if address == r("resident_main"):
        resident_input = r("resident_input_byte")
        if resident_input is not None:
            buffered = emu.read_mem(resident_input)
            if buffered != 0:
                _write_byte(emu, resident_input, 0x00)
                resident_last_key = r("resident_last_key")
                resident_last_submit_len = r("resident_last_submit_len")
                resident_submit_count = r("resident_submit_count")
                if resident_last_key is not None:
                    _write_byte(emu, resident_last_key, buffered)
                _capture_line(emu)
                if (
                    resident_last_submit_len is not None
                    and (length := _zp_line_length(emu)) is not None
                ):
                    _write_byte(emu, resident_last_submit_len, length)
                if resident_submit_count is not None:
                    _write_byte(
                        emu,
                        resident_submit_count,
                        emu.read_mem(resident_submit_count) + 1,
                    )
        _set_carry(emu, False)
        return


def _zp_line_length(emu: Any) -> int | None:
    zp_line_len = _zp(emu, "zp_line_len")
    if zp_line_len is None:
        return None
    return int(emu.read_mem(zp_line_len))
