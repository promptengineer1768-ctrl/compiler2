"""Unit tests for inspection shell routines (inspection.asm).

Tests verify the source-free REPL for standalone COMPILE exports, including
grammar validation, variable printing, and command execution.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    pass

from tests.kernal_stubs import install_kernal_stubs  # noqa: E402


def _load_zp_address(name: str) -> int:
    """Load zero-page symbol address from allocation."""
    path = ROOT / "build" / "zp_allocation.json"
    if not path.exists():
        pytest.fail("build/zp_allocation.json not found. Run build.ps1 first.")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    addr_str = data.get("allocation", {}).get(name, "")
    if addr_str.startswith("$"):
        return int(addr_str[1:], 16)
    pytest.fail(f"Zero page symbol '{name}' not found in allocation.")


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _load_symbol_address(symbol_name: str) -> int:
    """Load symbol address from compiler.map or routine_directory.json."""
    lbl_path = ROOT / "build" / "compiler.lbl"
    if lbl_path.exists():
        lbl_match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            lbl_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if lbl_match:
            return int(lbl_match.group(1), 16)

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
        pytest.fail(
            f"build/compiler.map not found. Run build.ps1 first. Missing: {symbol_name}"
        )

    pattern = rf"\b{symbol_name}\b\s+([0-9A-Fa-f]{{6}})"
    content = map_path.read_text(encoding="utf-8")
    match = re.search(pattern, content)
    if match:
        return int(match.group(1), 16)

    pytest.fail(
        f"Symbol '{symbol_name}' not found in compiler.map or routine directory."
    )


def _new_emu() -> C64Emu6502:
    """Load the linked compiler image into a fresh emulator."""
    emu = C64Emu6502(lib_path=_dll_path())
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
    emu.set_georam_enabled(True)
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    if hasattr(emu, "set_sp"):
        emu.set_sp(0xFF)
    install_kernal_stubs(emu)
    return emu


def _linked_bytes(symbol_name: str, length: int) -> bytes:
    """Read linked compiler/HIBASIC bytes for a symbol body."""
    address = _load_symbol_address(symbol_name)
    if address >= 0xE000:
        hibasic = (ROOT / "build" / "hibasic.bin").read_bytes()
        start = address - 0xE000
        if start < 0 or start + length > len(hibasic):
            pytest.fail(f"Symbol {symbol_name!r} is outside build/hibasic.bin.")
        return hibasic[start : start + length]
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    start = address - load_addr + 2
    if start < 2 or start + length > len(payload):
        pytest.fail(f"Symbol {symbol_name!r} is outside build/compiler.bin.")
    return payload[start : start + length]


def _carry_is_set(emu: C64Emu6502) -> bool:
    """Return whether carry is set after a routine call."""
    return bool(int(emu.get_state().p) & 0x01)


def _parse_command(source: bytes) -> bool:
    """Return True when inspect_parse_command accepts source."""
    emu = _new_emu()
    buffer = 0x0400
    emu.write_mem_range(buffer, source + b"\x00")
    emu.set_x(buffer & 0xFF)
    emu.set_y(buffer >> 8)
    emu.execute(_load_symbol_address("inspect_parse_command"), 10000)
    return not _carry_is_set(emu)


@pytest.mark.unit
@pytest.mark.local
class TestInspectParseCommand:
    """Grammar validation tests for inspection shell."""

    @pytest.mark.parametrize(
        "source",
        [
            b"?A",
            b"PRINT A",
            b"CONT",
            b"LIST",
            b"RUN",
            b'LOAD "X"',
            b'SAVE "X"',
            b'VERIFY "X"',
            b"CLR",
            b"$",
            b"/FILE",
            b"@",
            b"!README",
            b"   PRINT A",
        ],
        ids=[
            "question",
            "print",
            "cont",
            "list",
            "run",
            "load",
            "save",
            "verify",
            "clr",
            "dir",
            "slash-load",
            "status",
            "stream",
            "leading-spaces",
        ],
    )
    def test_parse_accepts_standalone_shell_commands(self, source: bytes) -> None:
        """inspect_parse_command accepts the source-free shell command set."""
        assert _parse_command(source)

    @pytest.mark.parametrize(
        "source",
        [
            b"",
            b"10 PRINT A",
            b"A=1",
            b"PRINT A=1",
            b"POKE 53280,0",
            b"GOTO 10",
            b"PR A",
            b"LOOP",
        ],
        ids=[
            "empty",
            "numbered-line",
            "assignment",
            "print-assignment",
            "poke",
            "goto",
            "abbreviated-print",
            "unsupported-l",
        ],
    )
    def test_parse_rejects_source_editing_and_arbitrary_basic(
        self, source: bytes
    ) -> None:
        """inspect_parse_command rejects source editing and arbitrary BASIC."""
        assert not _parse_command(source)


@pytest.mark.unit
@pytest.mark.local
class TestInspectPrintVar:
    """Variable printing tests for inspection shell."""

    def test_print_var_resolves_and_prints(self) -> None:
        """inspect_print_var resolves a real integer VD and formats its value."""
        emu = _new_emu()
        descriptor = 0xC900
        cell = 0xC920
        emu.write_mem_range(
            descriptor,
            b"VD" + bytes((1, 1, 0, 0, cell & 0xFF, cell >> 8, 0, 0, 0, 0)),
        )
        emu.write_mem_range(cell, b"\x2a\x00")
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)

        emu.execute(_load_symbol_address("inspect_print_var"), 100000)

        assert not _carry_is_set(emu)
        output = _load_symbol_address("kernal_output_byte")
        # The formatter emits a trailing field separator after the digits.
        assert emu.read_mem(output) == ord(" ")

    def test_print_string_var(self) -> None:
        """inspect_print_string_var rejects a non-string VD."""
        emu = _new_emu()
        descriptor = 0xC900
        cell = 0xC920
        emu.write_mem_range(
            descriptor,
            b"VD" + bytes((1, 1, 0, 0, cell & 0xFF, cell >> 8, 0, 0, 0, 0)),
        )
        emu.write_mem_range(cell, b"\x2a\x00")
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)

        emu.execute(_load_symbol_address("inspect_print_string_var"), 10000)

        assert _carry_is_set(emu)

    @pytest.mark.parametrize(
        ("command", "name", "suffix"),
        [(b"?A", b"A", 0), (b"PRINT AB$", b"AB", ord("$"))],
        ids=["question-numeric", "print-string"],
    )
    def test_textual_operand_resolves_linked_symbol(
        self, command: bytes, name: bytes, suffix: int
    ) -> None:
        """The standalone shell resolves source text through its linked table."""
        emu = _new_emu()
        text, table, descriptor = 0x0400, 0x0500, 0xC900
        padded = name + b"\x00" * (2 - len(name))
        emu.write_mem_range(text, command + b"\x00")
        emu.write_mem_range(
            table,
            padded + bytes((suffix, descriptor & 0xFF, descriptor >> 8, 0)),
        )
        table_slot = _load_symbol_address("inspect_symbol_table")
        emu.write_mem(table_slot, table & 0xFF)
        emu.write_mem(table_slot + 1, table >> 8)
        emu.write_mem(_load_symbol_address("inspect_symbol_count"), 1)
        emu.set_x(text & 0xFF)
        emu.set_y(text >> 8)

        emu.execute(_load_symbol_address("inspect_resolve_operand"), 10_000)

        state = emu.get_state()
        assert not _carry_is_set(emu)
        assert (state.x | (state.y << 8)) == descriptor

    def test_textual_operand_rejects_unlinked_or_compound_term(self) -> None:
        """Unknown names and compound expressions never become arbitrary pointers."""
        emu = _new_emu()
        text = 0x0400
        emu.write_mem_range(text, b"?A+1\x00")
        emu.set_x(text & 0xFF)
        emu.set_y(text >> 8)
        emu.execute(_load_symbol_address("inspect_resolve_operand"), 10_000)
        assert _carry_is_set(emu)


@pytest.mark.unit
@pytest.mark.local
class TestInspectCont:
    """CONT statement tests for inspection shell."""

    def test_cont_restores_continuation(self) -> None:
        """inspect_cont should restore compiled continuation state."""
        emu = _new_emu()
        continuation = 0xC900
        emu.write_mem_range(continuation, b"C\x2a\x78\x56" + bytes(35))
        emu.set_x(continuation & 0xFF)
        emu.set_y(continuation >> 8)
        emu.execute(_load_symbol_address("ctrl_stop"), 10000)
        assert not _carry_is_set(emu)

        emu.set_x(continuation & 0xFF)
        emu.set_y(continuation >> 8)
        emu.execute(_load_symbol_address("inspect_cont"), 10000)

        assert not _carry_is_set(emu)
        assert (emu.get_state().x, emu.get_state().y) == (0x78, 0x56)

    def test_cont_rejects_unpublished_handle(self) -> None:
        """inspect_cont propagates ctrl_cont validation failures."""
        emu = _new_emu()
        emu.set_x(0)
        emu.set_y(0xC9)
        emu.execute(_load_symbol_address("inspect_cont"), 10000)
        assert _carry_is_set(emu)


@pytest.mark.unit
@pytest.mark.local
class TestInspectListLoader:
    """LIST command tests for inspection shell."""

    def test_list_loader_prints_sys(self) -> None:
        """inspect_list_loader should print '2026 SYS2061'."""
        body = _linked_bytes("inspect_list_loader", 12)
        assert body[0] == 0xA2  # LDX #<SYS_MSG
        assert body[2] == 0xA0  # LDY #>SYS_MSG
        message = body[1] | (body[3] << 8)
        payload = (ROOT / "build" / "compiler.bin").read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        offset = message - load_addr + 2
        assert payload[offset : offset + 13] == b"2026 SYS2061\x8d"

        emu = _new_emu()
        emu.execute(_load_symbol_address("inspect_list_loader"), 10000)
        assert not _carry_is_set(emu)
        output = _load_symbol_address("kernal_output_byte")
        assert emu.read_mem(output) == 0x0D


@pytest.mark.unit
@pytest.mark.local
class TestInspectRun:
    """RUN command tests for inspection shell."""

    def test_run_enters_compiled_image(self) -> None:
        """inspect_run should reinitialize and enter current compiled image."""
        emu = _new_emu()
        entry = 0xC900
        marker = 0xC910
        # LDA #$A5; STA marker; CLC; RTS
        emu.write_mem_range(entry, bytes((0xA9, 0xA5, 0x8D, 0x10, 0xC9, 0x18, 0x60)))
        entry_slot = _load_symbol_address("inspect_program_entry")
        emu.write_mem(entry_slot, entry & 0xFF)
        emu.write_mem(entry_slot + 1, entry >> 8)

        emu.execute(_load_symbol_address("inspect_run"), 10_000)

        assert emu.read_mem(marker) == 0xA5
        assert not _carry_is_set(emu)

    def test_run_rejects_export_without_linked_entry(self) -> None:
        """RUN fails instead of jumping through a missing linker entry."""
        emu = _new_emu()
        entry_slot = _load_symbol_address("inspect_program_entry")
        emu.write_mem(entry_slot, 0)
        emu.write_mem(entry_slot + 1, 0)
        emu.execute(_load_symbol_address("inspect_run"), 10_000)
        assert _carry_is_set(emu)


@pytest.mark.unit
@pytest.mark.local
class TestInspectLoadSave:
    """LOAD/SAVE/VERIFY command tests for inspection shell."""

    def test_load_uses_kernal(self) -> None:
        """inspect_load delegates the validated RL record to rio_load."""
        body = _linked_bytes("inspect_load", 3)
        assert body[0] == 0x4C
        assert body[1] | (body[2] << 8) == _load_symbol_address("rio_load")

    def test_save_uses_kernal(self) -> None:
        """inspect_save delegates the validated RS record to rio_save."""
        body = _linked_bytes("inspect_save", 3)
        assert body[0] == 0x4C
        assert body[1] | (body[2] << 8) == _load_symbol_address("rio_save")

    def test_verify_uses_runtime_io(self) -> None:
        """inspect_verify delegates the validated RL record to rio_verify."""
        body = _linked_bytes("inspect_verify", 3)
        assert body[0] == 0x4C
        assert body[1] | (body[2] << 8) == _load_symbol_address("rio_verify")


@pytest.mark.unit
@pytest.mark.local
class TestInspectClr:
    """CLR command tests for inspection shell."""

    def test_clr_clears_state(self) -> None:
        """inspect_clr should clear variables, arrays, strings, frames."""
        emu = _new_emu()
        continuation = 0x1800
        emu.write_mem_range(continuation, b"C\x2a\x78\x56" + bytes(35))
        emu.set_x(continuation & 0xFF)
        emu.set_y(continuation >> 8)
        emu.execute(_load_symbol_address("ctrl_stop"), 10000)
        assert emu.read_mem(_load_zp_address("zp_stop_flag")) == 1

        emu.execute(_load_symbol_address("inspect_clr"), 10000)

        assert not _carry_is_set(emu)
        assert emu.read_mem(_load_zp_address("zp_stop_flag")) == 0
        assert emu.read_mem(_load_zp_address("zp_cont_handle")) == 0
        assert emu.read_mem(_load_zp_address("zp_cont_handle") + 1) == 0
        assert emu.read_mem(_load_zp_address("zp_gr_ctx_sp")) == 0
        emu.set_a(0xF8)
        emu.execute(_load_symbol_address("fp_get_flags"), 10000)
        assert emu.get_state().a == 0


@pytest.mark.unit
@pytest.mark.local
class TestInspectWedge:
    """Wedge command tests for inspection shell."""

    @pytest.mark.parametrize(
        ("command", "kind"),
        [(b"$", 0), (b"/FILE", 2), (b"@", 1), (b"!README", 3)],
        ids=["directory", "load", "status", "stream"],
    )
    def test_wedge_dispatches_prefix(self, command: bytes, kind: int) -> None:
        """inspect_wedge should call standalone wedge service."""
        emu = _new_emu()
        record = 0xC800
        emu.write_mem_range(record, command + b"\x00")
        # EOF after open so directory/status/stream handlers return cleanly.
        emu.write_mem(0x90, 0x40)
        emu.write_mem(0xBA, 8)
        emu.set_x(record & 0xFF)
        emu.set_y(record >> 8)
        emu.execute(_load_symbol_address("inspect_wedge"), 50_000)

        assert not _carry_is_set(emu)
        assert emu.read_mem(_load_symbol_address("wedge_last_command")) == kind

    def test_wedge_device_selection_updates_kernal_fa(self) -> None:
        """@10 changes the same current-device byte used by LOAD and COMPILE."""
        emu = _new_emu()
        record = 0xC800
        emu.write_mem_range(record, b"@10\x00")
        emu.write_mem(0xBA, 8)
        emu.set_x(record & 0xFF)
        emu.set_y(record >> 8)
        emu.execute(_load_symbol_address("inspect_wedge"), 50_000)
        assert not _carry_is_set(emu)
        assert emu.read_mem(0xBA) == 10
