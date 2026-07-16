"""Unit tests for the geoasm parser."""

from __future__ import annotations

import json
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

# Keep parser input below the linked image and outside the geoRAM window.  The
# production image may validly occupy normal RAM all the way through $CFFF.
SOURCE_ADDR = 0x0500

NODE_LINE = 0x01
NODE_STATEMENT = 0x02
NODE_EXPRESSION = 0x03
NODE_PRIMARY = 0x04
NODE_FUNCTION = 0x05
NODE_ARRAY_REF = 0x06

STMT_PRINT = 0x01
STMT_FOR = 0x02
STMT_GOSUB = 0x03
STMT_NONE = 0x00

FLAG_HAS_COMPARISON = 0x01
FLAG_TERM_PRECEDENCE = 0x02

IR_END = 0x00
IR_STMT = 0x01
IR_EXPR = 0x02
IR_VAR_REF = 0x03
IR_ARRAY_REF = 0x04
IR_BRANCH = 0x06
IR_LOOP = 0x07
IR_LITERAL_FLOAT = 0x09


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _symbol_address(symbol: str) -> int:
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    raw = data["routines"][symbol]["address"]
    assert raw.startswith("$")
    return int(raw[1:], 16)


def _state_address(symbol: str) -> int:
    return _symbol_address(symbol)


def _new_emu(source: bytes) -> C64Emu6502:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    setattr(emu, "_compiler2_real_bytes_only", True)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.set_georam_enabled(True)
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x30)
    emu.write_mem_range(SOURCE_ADDR, source + b"\x00")
    emu.set_x(SOURCE_ADDR & 0xFF)
    emu.set_y(SOURCE_ADDR >> 8)
    return emu


def _execute(emu: C64Emu6502, routine: str) -> bool:
    """Execute one real parser routine and return its carry/error result."""
    emu.execute(_symbol_address(routine), 5000)
    return bool(emu.get_state().p & 0x01)


def _parser_state(emu: C64Emu6502) -> tuple[int, int, int]:
    return (
        emu.read_mem(_state_address("parse_last_node")),
        emu.read_mem(_state_address("parse_last_stmt")),
        emu.read_mem(_state_address("parse_flags")),
    )


def _ir_records(emu: C64Emu6502) -> list[tuple[int, int, int, int]]:
    """Return the materialized four-byte IR records."""
    length = emu.read_mem(_state_address("ir_buffer_len"))
    start = _state_address("ir_buffer")
    raw = emu.read_mem_range(start, start + length - 1) if length else b""
    return [tuple(raw[offset : offset + 4]) for offset in range(0, length, 4)]


@pytest.mark.unit
@pytest.mark.local
class TestParser:
    """Parser behavior tests."""

    def test_line_and_statement_parsing(self) -> None:
        emu = _new_emu(b"10 PRINT A")
        assert not _execute(emu, "parse_line")
        assert _parser_state(emu) == (NODE_LINE, STMT_PRINT, 0)
        assert _ir_records(emu) == [
            (IR_VAR_REF, 9, 1, 0),
            (IR_STMT, STMT_PRINT, 0, 0),
            (IR_END, 0, 0, 0),
        ]

        for source, statement in (
            (b" print a", STMT_PRINT),
            (b"FOR I=1 TO 10 STEP 2", STMT_FOR),
            (b"GOSUB 100", STMT_GOSUB),
        ):
            emu = _new_emu(source)
            assert not _execute(emu, "parse_statement")
            assert _parser_state(emu) == (NODE_STATEMENT, statement, 0)

    @pytest.mark.parametrize(
        "source",
        (b"", b"10", b"10 FOO", b"PLOT 1", b"FORMAT A", b"GOTO 100"),
    )
    def test_statement_parser_rejects_unknown_or_incomplete_syntax(
        self, source: bytes
    ) -> None:
        emu = _new_emu(source)
        assert _execute(emu, "parse_line")
        assert _parser_state(emu)[1] == STMT_NONE

    def test_expression_precedence_and_comparison(self) -> None:
        emu = _new_emu(b"1+2*3")
        assert not _execute(emu, "parse_expression")
        assert _parser_state(emu) == (NODE_EXPRESSION, 0, FLAG_TERM_PRECEDENCE)
        assert _ir_records(emu) == [
            (IR_LITERAL_FLOAT, 0, 1, 0),
            (IR_LITERAL_FLOAT, 2, 1, 0),
            (IR_LITERAL_FLOAT, 4, 1, 0),
            (IR_EXPR, ord("*"), 3, 0),
            (IR_EXPR, ord("+"), 2, 0),
        ]

        emu = _new_emu(b"A<10")
        assert not _execute(emu, "parse_comparison")
        assert _parser_state(emu) == (NODE_EXPRESSION, 0, FLAG_HAS_COMPARISON)

        emu = _new_emu(b"(A+2)*-3>=B")
        assert not _execute(emu, "parse_expression")
        assert _parser_state(emu) == (
            NODE_EXPRESSION,
            0,
            FLAG_HAS_COMPARISON | FLAG_TERM_PRECEDENCE,
        )

    @pytest.mark.parametrize(
        "source",
        (
            b"",
            b"1+",
            b"*2",
            b"(1+2",
            b"1 2",
            b"A<B<C",
            b"1+)2(",
            b"1A",
            b"$",
            b"%",
            b".",
            b"A$%",
            b"1.2.3",
        ),
    )
    def test_expression_parser_rejects_malformed_input(self, source: bytes) -> None:
        emu = _new_emu(source)
        assert _execute(emu, "parse_expression")

    @pytest.mark.parametrize(
        ("routine", "source"),
        (
            ("parse_primary", b"1+2"),
            ("parse_factor", b"A*B"),
            ("parse_term", b"1+2"),
            ("parse_term", b"1<2"),
        ),
    )
    def test_precedence_entries_consume_exact_grammar_layer(
        self, routine: str, source: bytes
    ) -> None:
        """Specialized entries must not alias the full-expression parser."""
        emu = _new_emu(source)
        assert _execute(emu, routine)

    def test_function_array_for_and_gosub_parsing(self) -> None:
        emu = _new_emu(b"SIN(1)")
        assert not _execute(emu, "parse_function_call")
        assert _parser_state(emu) == (NODE_FUNCTION, 0, 0)
        assert _ir_records(emu)[-1][0] == IR_EXPR

        emu = _new_emu(b"A(1,2+3)")
        assert not _execute(emu, "parse_array_ref")
        assert _parser_state(emu) == (NODE_ARRAY_REF, 0, 0)
        assert _ir_records(emu)[-1][0] == IR_ARRAY_REF

        emu = _new_emu(b"FOR I=1 TO 10")
        assert not _execute(emu, "parse_for")
        assert _parser_state(emu) == (NODE_STATEMENT, STMT_FOR, 0)
        assert [record[0] for record in _ir_records(emu)[-2:]] == [
            IR_LOOP,
            IR_STMT,
        ]

        emu = _new_emu(b"GOSUB 100")
        assert not _execute(emu, "parse_gosub")
        assert _parser_state(emu) == (NODE_STATEMENT, STMT_GOSUB, 0)
        assert _ir_records(emu)[-2:] == [
            (IR_BRANCH, STMT_GOSUB, 100, 0),
            (IR_STMT, STMT_GOSUB, 0, 0),
        ]

    @pytest.mark.parametrize(
        ("routine", "source"),
        (
            ("parse_function_call", b"SIN 1"),
            ("parse_function_call", b"(1)"),
            ("parse_array_ref", b"A()"),
            ("parse_array_ref", b"A(1"),
            ("parse_for", b"FOR I=1"),
            ("parse_for", b"FOR =1 TO 2"),
            ("parse_for", b"FOR I=+ TO 2"),
            ("parse_for", b"FOR I=1 POTATO 2"),
            ("parse_for", b"FOR I=1 TO X STEP +"),
            ("parse_gosub", b"GOSUB"),
            ("parse_gosub", b"GOSUB A"),
            ("parse_gosub", b"GOSUB 64000"),
            ("parse_gosub", b"GOSUB 65536"),
        ),
    )
    def test_specialized_parsers_reject_malformed_syntax(
        self, routine: str, source: bytes
    ) -> None:
        emu = _new_emu(source)
        assert _execute(emu, routine)
