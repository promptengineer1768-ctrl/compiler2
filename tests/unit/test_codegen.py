"""Unit tests for the geoasm code generator."""

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
    C64Emu6502 = None

EMITTERS = [
    ("codegen_emit_stmt", 0x01),
    ("codegen_emit_for_fast", 0x02),
    ("codegen_emit_for_generic", 0x03),
    ("codegen_emit_do_fast", 0x04),
    ("codegen_emit_do_generic", 0x05),
    ("codegen_emit_if", 0x06),
    ("codegen_emit_gosub", 0x07),
    ("codegen_emit_return", 0x08),
    ("codegen_emit_on", 0x09),
    ("codegen_emit_print", 0x0A),
    ("codegen_emit_input", 0x0B),
    ("codegen_emit_let", 0x0C),
    ("codegen_emit_dim", 0x0D),
    ("codegen_emit_data", 0x0E),
    ("codegen_emit_exit", 0x0F),
    ("codegen_emit_read", 0x10),
]


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _symbol_address(symbol: str) -> int:
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(
        rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}$",
        labels,
        re.MULTILINE,
    )
    if match:
        return int(match.group(1), 16)
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    raw = data["routines"][symbol]["address"]
    assert raw.startswith("$")
    return int(raw[1:], 16)


def _new_emu() -> C64Emu6502:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    setattr(emu, "_compiler2_real_bytes_only", True)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    georam = (ROOT / "build" / "georam.bin").read_bytes()
    assert georam[:2] == b"\x00\xde"
    emu.set_georam_enabled(True)
    emu.load_georam(georam[2:])
    _execute_routine(emu, "codegen_init")
    return emu


def _execute_routine(emu: C64Emu6502, symbol: str, cycles: int = 10_000) -> None:
    """Execute one selected geoRAM routine through its real RTS."""
    emu.execute_rts(_symbol_address(symbol), cycles)


@pytest.mark.unit
@pytest.mark.local
class TestCodegen:
    """Code emission behavior tests."""

    @pytest.mark.parametrize(("name", "opcode"), EMITTERS)
    def test_each_codegen_operation_emits_executable_6502(
        self, name: str, opcode: int
    ) -> None:
        emu = _new_emu()
        emu.set_a(0x21)
        emu.set_x(0x43)
        emu.set_y(0x65)
        emu.execute(_symbol_address(name), 1000)
        emu.execute(_symbol_address("codegen_finish_line"), 1000)
        emu.execute(_symbol_address("codegen_buffer"), 1000)
        state = emu.get_state()
        assert (state.a, state.x, state.y) == (0x21, 0x43, 0x65)

    def test_finish_and_init_reset(self) -> None:
        emu = _new_emu()
        emu.execute(_symbol_address("codegen_emit_return"), 1000)
        emu.execute(_symbol_address("codegen_finish_line"), 1000)
        code_address = _address = _symbol_address("codegen_buffer")
        emu.execute(code_address, 1000)
        state = emu.get_state()
        assert state.a == 0
        assert state.x == 0
        assert state.y == 0

        emu.execute(_symbol_address("codegen_init"), 1000)
        emu.execute(_symbol_address("codegen_finish_line"), 1000)
        emu.set_a(0x11)
        emu.set_x(0x22)
        emu.set_y(0x33)
        emu.execute(code_address, 1000)
        state = emu.get_state()
        assert (state.a, state.x, state.y) == (0x11, 0x22, 0x33)

    def test_get_code_ptr_returns_executable_buffer(self) -> None:
        """codegen_get_code_ptr returns the real native scratch buffer address."""
        emu = _new_emu()
        emu.execute(_symbol_address("codegen_get_code_ptr"), 1000)
        state = emu.get_state()
        assert state.x | (state.y << 8) == _symbol_address("codegen_buffer")

    def test_relocation_records_fixup_and_init_clears_it(self) -> None:
        """codegen_emit_reloc appends typed addresses to the linker fixup list."""
        emu = _new_emu()
        emu.set_a(3)
        emu.set_x(0x34)
        emu.set_y(0x12)
        _execute_routine(emu, "codegen_emit_reloc")
        assert emu.read_mem(_symbol_address("codegen_reloc_count")) == 1
        table = _symbol_address("codegen_reloc_table")
        assert emu.read_mem_range(table, table + 2) == bytes([3, 0x34, 0x12])
        _execute_routine(emu, "codegen_init")
        assert emu.read_mem(_symbol_address("codegen_reloc_count")) == 0
