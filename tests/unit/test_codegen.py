"""Unit tests for the geoasm code generator."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from tests.kernal_stubs import install_kernal_stubs

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

IR_END = 0x00
IR_STMT = 0x01
STMT_END = 0x06
STMT_PRINT = 0x01
STMT_LET = 0x04
IR_LITERAL_STR = 0x0A
IR_LITERAL_FLOAT = 0x09
IR_VAR_REF = 0x03
IR_EXPR = 0x02
PRINT_FLAG_TRAILING_SEMICOLON = 0x01


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


def _zp_address(symbol: str) -> int:
    """Read one generated zero-page symbol without hard-coding its address."""
    text = (ROOT / "build" / "zp_symbols.inc").read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(symbol)}\s*=\s*\$([0-9A-Fa-f]+)$", text, re.M)
    assert match, f"missing generated ZP symbol {symbol}"
    return int(match.group(1), 16)


def _new_emu() -> C64Emu6502:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    # EDITOR / HIBASIC link into RAM_HIGH ($E000+). The native codegen helpers
    # (_codegen_emit_end and friends) live there, so the overlay must be present
    # for codegen_emit_ir to lower statements through the real production path.
    hibasic = ROOT / "build" / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    georam = (ROOT / "build" / "georam.bin").read_bytes()
    assert georam[:2] == b"\x00\xde"
    emu.set_georam_enabled(True)
    emu.load_georam(georam[2:])
    install_kernal_stubs(emu)
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

    def test_end_lowers_to_an_executable_program_stop_latch(self) -> None:
        """END must stop stored RUN after its generated bytes execute."""
        emu = _new_emu()
        ir = _symbol_address("ir_buffer")
        emu.write_mem_range(ir, bytes((IR_STMT, STMT_END, 0, 0, IR_END, 0, 0, 0)))
        emu.write_mem(_symbol_address("ir_buffer_len"), 8)
        emu.write_mem(_symbol_address("codegen_program_stop"), 0)
        _execute_routine(emu, "codegen_emit_ir")
        emu.execute(_symbol_address("codegen_buffer"), 1000)
        assert emu.read_mem(_symbol_address("codegen_program_stop")) == 1

    def test_ti_dollar_midnight_reset_executes_through_kernal_settim(self) -> None:
        """TI$=""000000"" must reset the live KERNAL clock at RUN time."""
        emu = _new_emu()
        source = 0x0500
        emu.write_mem_range(source, b'TI$="000000"\x00')
        emu.write_mem(_symbol_address("pipeline_source_lo"), source & 0xFF)
        emu.write_mem(_symbol_address("pipeline_source_hi"), source >> 8)
        ir = _symbol_address("ir_buffer")
        emu.write_mem_range(
            ir,
            bytes(
                (
                    IR_LITERAL_STR,
                    5,
                    6,
                    0,
                    IR_STMT,
                    STMT_LET,
                    0,
                    3,
                    IR_END,
                    0,
                    0,
                    0,
                )
            ),
        )
        emu.write_mem(_symbol_address("ir_buffer_len"), 12)
        emu.write_mem(0x00A0, 0x12)
        emu.write_mem(0x00A1, 0x34)
        emu.write_mem(0x00A2, 0x56)
        _execute_routine(emu, "codegen_emit_ir")
        emu.execute(_symbol_address("codegen_buffer"), 10_000)
        assert emu.read_mem_range(0x00A0, 0x00A2) == b"\x00\x00\x00"

    def test_print_ti_emits_runtime_rdtime_call(self) -> None:
        """PRINT TI must read the time in generated code, not during compile."""
        emu = _new_emu()
        source = 0x0500
        emu.write_mem_range(source, b"PRINT TI\x00")
        emu.write_mem(_symbol_address("pipeline_source_lo"), source & 0xFF)
        emu.write_mem(_symbol_address("pipeline_source_hi"), source >> 8)
        ir = _symbol_address("ir_buffer")
        emu.write_mem_range(
            ir,
            bytes(
                (
                    IR_VAR_REF,
                    6,
                    2,
                    0,
                    IR_STMT,
                    STMT_PRINT,
                    0,
                    0,
                    IR_END,
                    0,
                    0,
                    0,
                )
            ),
        )
        emu.write_mem(_symbol_address("ir_buffer_len"), 12)
        _execute_routine(emu, "codegen_emit_ir")
        size = emu.read_mem(_symbol_address("codegen_buffer_len"))
        image = emu.read_mem_range(
            _symbol_address("codegen_buffer"),
            _symbol_address("codegen_buffer") + size - 1,
        )
        rdtime = _symbol_address("kernal_rdtim")
        assert bytes((0x20, rdtime & 0xFF, rdtime >> 8)) in image

    def test_print_ti_div_60_executes_the_live_division_lowering(self) -> None:
        """The Noel TI/60 shape must use the shared runtime clock divider."""
        emu = _new_emu()
        source = 0x0500
        emu.write_mem_range(source, b"PRINT TI/60\x00")
        emu.write_mem(_symbol_address("pipeline_source_lo"), source & 0xFF)
        emu.write_mem(_symbol_address("pipeline_source_hi"), source >> 8)
        ir = _symbol_address("ir_buffer")
        emu.write_mem_range(
            ir,
            bytes(
                (
                    IR_VAR_REF,
                    6,
                    2,
                    0,
                    IR_LITERAL_FLOAT,
                    9,
                    2,
                    0,
                    IR_EXPR,
                    ord("/"),
                    3,
                    0,
                    IR_STMT,
                    STMT_PRINT,
                    0,
                    0,
                    IR_END,
                    0,
                    0,
                    0,
                )
            ),
        )
        emu.write_mem(_symbol_address("ir_buffer_len"), 20)
        emu.write_mem(0x00A0, 0)
        emu.write_mem(0x00A1, 0)
        emu.write_mem(0x00A2, 120)
        _execute_routine(emu, "codegen_emit_ir")
        emu.execute(_symbol_address("codegen_buffer"), 10_000)
        zp_fac1 = _zp_address("zp_fac1")
        assert emu.read_mem_range(zp_fac1, zp_fac1 + 1) == b"\x02\x00"

    def test_print_semicolon_omits_newline_from_generated_bytes(self) -> None:
        """PRINT "."; must emit output without a trailing newline call."""
        emu = _new_emu()
        source = 0x0500
        emu.write_mem_range(source, b'PRINT ".";\x00')
        emu.write_mem(_symbol_address("pipeline_source_lo"), source & 0xFF)
        emu.write_mem(_symbol_address("pipeline_source_hi"), source >> 8)
        ir = _symbol_address("ir_buffer")
        emu.write_mem_range(
            ir,
            bytes(
                (
                    IR_LITERAL_STR,
                    7,
                    1,
                    0,
                    IR_STMT,
                    STMT_PRINT,
                    0,
                    PRINT_FLAG_TRAILING_SEMICOLON,
                    IR_END,
                    0,
                    0,
                    0,
                )
            ),
        )
        emu.write_mem(_symbol_address("ir_buffer_len"), 12)
        _execute_routine(emu, "codegen_emit_ir")
        size = emu.read_mem(_symbol_address("codegen_buffer_len"))
        image = emu.read_mem_range(
            _symbol_address("codegen_buffer"),
            _symbol_address("codegen_buffer") + size - 1,
        )
        newline = _symbol_address("io_print_newline")
        assert bytes((0x20, newline & 0xFF, newline >> 8)) not in image


@pytest.mark.unit
@pytest.mark.local
class TestCodegenArithmeticFolding:
    """Constant folding of *, /, +, - through the real postfix evaluator."""

    def _fold(self, expr: str, ir: bytes, source_len: int) -> C64Emu6502 | None:
        """Emit ``PRINT <expr>`` from hand-built postfix IR and return the emu."""
        emu = _new_emu()
        source = 0x0500
        text = f"PRINT {expr}".encode("ascii") + b"\x00"
        emu.write_mem_range(source, text)
        emu.write_mem(_symbol_address("pipeline_source_lo"), source & 0xFF)
        emu.write_mem(_symbol_address("pipeline_source_hi"), source >> 8)
        ir_addr = _symbol_address("ir_buffer")
        emu.write_mem_range(ir_addr, ir)
        emu.write_mem(_symbol_address("ir_buffer_len"), len(ir))
        _execute_routine(emu, "codegen_emit_ir")
        return emu

    def _folded_value(self, emu: C64Emu6502) -> int:
        """Read the 16-bit integer literal a folded PRINT loads into FAC."""
        size = emu.read_mem(_symbol_address("codegen_buffer_len"))
        base = _symbol_address("codegen_buffer")
        code = emu.read_mem_range(base, base + size - 1)
        # A folded integer print begins: LDA #lo ; STA fac_lo ; LDA #hi ; STA fac_hi
        assert code[0] == 0xA9 and code[2] == 0x85
        assert code[4] == 0xA9 and code[6] == 0x85
        return int(code[1] | (code[5] << 8))

    @staticmethod
    def _lit(start: int, length: int) -> bytes:
        return bytes((IR_LITERAL_FLOAT, start, length, 0))

    @staticmethod
    def _op(char: str) -> bytes:
        return bytes((IR_EXPR, ord(char), 3, 0))

    def test_multiply_folds_two_times_three_to_six(self) -> None:
        """2*3 must fold to 6, not silently drop the multiply operator."""
        # source: "PRINT 2*3" -> '2'@6, '3'@8
        ir = (
            self._lit(6, 1)
            + self._lit(8, 1)
            + self._op("*")
            + bytes((IR_STMT, STMT_PRINT, 0, 0))
            + bytes((IR_END, 0, 0, 0))
        )
        emu = self._fold("2*3", ir, 9)
        assert emu is not None
        assert self._folded_value(emu) == 6

    def test_multiply_respects_precedence_one_plus_two_times_three(self) -> None:
        """1+2*3 must fold to 7 (multiply binds tighter than add)."""
        # source: "PRINT 1+2*3" -> '1'@6, '2'@8, '3'@10 ; postfix 1 2 3 * +
        ir = (
            self._lit(6, 1)
            + self._lit(8, 1)
            + self._lit(10, 1)
            + self._op("*")
            + self._op("+")
            + bytes((IR_STMT, STMT_PRINT, 0, 0))
            + bytes((IR_END, 0, 0, 0))
        )
        emu = self._fold("1+2*3", ir, 11)
        assert emu is not None
        assert self._folded_value(emu) == 7

    def test_multiply_produces_16bit_result(self) -> None:
        """200*3 must fold to 600, exercising the high byte of the product."""
        # source: "PRINT 200*3" -> "200"@6..8, '3'@10
        ir = (
            self._lit(6, 3)
            + self._lit(10, 1)
            + self._op("*")
            + bytes((IR_STMT, STMT_PRINT, 0, 0))
            + bytes((IR_END, 0, 0, 0))
        )
        emu = self._fold("200*3", ir, 11)
        assert emu is not None
        assert self._folded_value(emu) == 600

    def test_divide_folds_twelve_over_four_to_three(self) -> None:
        """12/4 must fold to 3 through the general integer divide."""
        # source: "PRINT 12/4" -> "12"@6..7, '4'@9
        ir = (
            self._lit(6, 2)
            + self._lit(9, 1)
            + self._op("/")
            + bytes((IR_STMT, STMT_PRINT, 0, 0))
            + bytes((IR_END, 0, 0, 0))
        )
        emu = self._fold("12/4", ir, 10)
        assert emu is not None
        assert self._folded_value(emu) == 3

    def test_divide_truncates_toward_zero(self) -> None:
        """13/4 must fold to the integer quotient 3 (remainder discarded)."""
        # source: "PRINT 13/4" -> "13"@6..7, '4'@9
        ir = (
            self._lit(6, 2)
            + self._lit(9, 1)
            + self._op("/")
            + bytes((IR_STMT, STMT_PRINT, 0, 0))
            + bytes((IR_END, 0, 0, 0))
        )
        emu = self._fold("13/4", ir, 10)
        assert emu is not None
        assert self._folded_value(emu) == 3
