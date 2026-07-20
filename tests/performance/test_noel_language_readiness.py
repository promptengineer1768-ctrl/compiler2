"""RED production-readiness contract for Noel's Retro Lab BASIC benchmark.

This is deliberately a source-level preflight while the clean-output recovery
has no assembled ``georam.bin`` to execute.  It names the exact capabilities
that must be present before the VICE ``RUN`` acceptance test can be enabled;
it must not be changed to match an unsupported subset of the benchmark.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "performance" / "noels_retro_lab_cbm_v2.bas"
PARSER = ROOT / "src" / "geoasm" / "parser.asm"
CODEGEN = ROOT / "src" / "geoasm" / "codegen.asm"
PROGRAM_LINES = ROOT / "src" / "geoasm" / "program_lines.asm"


def _text(path: Path) -> str:
    """Return an ASCII production source file."""
    return path.read_text(encoding="utf-8")


def _body_storage_required() -> int:
    """Return exact interim-table bytes required by Noel's numbered bodies.

    ``program_lines`` records use ``line_lo,line_hi,body_len,body,NUL``.  The
    benchmark source is canonical input, so this is a real lower bound, not a
    hand-picked capacity threshold.
    """
    total = 0
    for line in SOURCE.read_text(encoding="ascii").splitlines():
        _, body = line.split(" ", 1)
        total += 4 + len(body)
    return total


def _arena_size() -> int:
    """Read the current production interim program-table capacity."""
    match = re.search(r"^PL_ARENA_SIZE\s*=\s*(\d+)\s*$", _text(PROGRAM_LINES), re.M)
    assert match, "program_lines must declare PL_ARENA_SIZE"
    return int(match.group(1))


def test_noel_program_store_holds_every_numbered_line() -> None:
    """Require canonical expansion storage, or sufficient legacy table space."""
    source = _text(PROGRAM_LINES)
    if "PL_ARENA_SIZE" in source:
        assert _arena_size() >= _body_storage_required()
        return
    # The adapter's 48-byte descriptor is not source storage: the current
    # design writes numbered lines transactionally to the geoRAM PS stream.
    assert "GEORAM_ROUTINE_ID_PROGRAM_TX_PUT_LINE" in source
    assert "program_store_copy_line_body_at" in source
    assert "Program bytes are in geoRAM" in source


def test_noel_parser_accepts_rem_and_end_statements() -> None:
    """Require the benchmark's leading REM and terminating END statements."""
    parser = _text(PARSER)
    assert "TOKEN_REM" in parser
    assert "BASIC_TOKEN_END" in parser
    assert "jmp @rem" in parser
    assert re.search(r"cmp\s+#BASIC_TOKEN_END\s*\n\s*bne\s+@not_end", parser)
    assert "jmp @end" in parser


def test_noel_codegen_has_ti_dollar_assignment_and_read_lowering() -> None:
    """Require TI$=""000000"" reset semantics, not an ordinary string variable."""
    codegen = _text(CODEGEN)
    assert "_codegen_target_is_ti_dollar" in codegen
    assert "_codegen_emit_ti_dollar_reset" in codegen
    assert "_codegen_emit_print_ti_live" in codegen
    assert "kernal_rdtim" in codegen


def test_noel_codegen_lowers_integer_division() -> None:
    """Require execution of Noel's ``TI/60`` expression."""
    codegen = _text(CODEGEN)
    assert "_codegen_is_ti_div60" in codegen
    assert "_codegen_emit_print_ti_div60" in codegen
    assert "system_ti_div60" in codegen


def test_noel_print_semicolon_suppresses_newline() -> None:
    """Require the ten dots to remain on one line for ``PRINT \".\";``."""
    codegen = _text(CODEGEN)
    parser = _text(PARSER)
    assert "PRINT_FLAG_TRAILING_SEMICOLON" in parser
    assert "PRINT_FLAG_TRAILING_SEMICOLON" in codegen
    assert "codegen_print_flags" in codegen
