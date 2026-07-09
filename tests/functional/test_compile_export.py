"""Functional contracts for the source-free COMPILE export.

These tests deliberately inspect the product of the real production path.  A
missing ``COMPILED.PRG`` is a failure: record validators are unit-testable, but
they are not a substitute for a linker and an exported program.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PRG = ROOT / "build" / "COMPILED.PRG"
EXPECTED_STUB = bytes(
    (
        0x0B,
        0x08,  # next BASIC line: $080B
        0xEA,
        0x07,  # line 2026
        0x9E,  # SYS
        *b"2061",
        0,
        0,
        0,
    )
)


def _export() -> bytes:
    """Return the production COMPILE artifact, failing when none was emitted."""
    assert PRG.is_file(), (
        "the production COMPILE path did not emit build/COMPILED.PRG; "
        "record validation alone is not a COMPILE implementation"
    )
    payload = PRG.read_bytes()
    assert len(payload) >= 2 + len(EXPECTED_STUB) + 1
    return payload


@pytest.mark.functional
@pytest.mark.local
@pytest.mark.smoke
def test_compile_produces_canonical_stock_prg() -> None:
    """The real export has the stock load address and exact loader line."""
    payload = _export()
    assert payload[:2] == b"\x01\x08"
    assert payload[2 : 2 + len(EXPECTED_STUB)] == EXPECTED_STUB
    assert payload[2 + len(EXPECTED_STUB)] != 0, "native entry is empty"
    assert 0x0801 + len(payload) - 2 <= 0xD000


@pytest.mark.functional
@pytest.mark.local
def test_compile_export_is_source_free_and_not_development_image() -> None:
    """The artifact contains neither tokenized source nor installer messages."""
    payload = _export()
    upper = payload.upper()
    for forbidden in (
        b"GEORAM DETECTED",
        b"GEORAM NOT DETECTED",
        b"BASIC 3 COMPILER",
    ):
        assert forbidden not in upper

    # A second linked BASIC line would make LIST expose source beyond the stub.
    assert payload[2:14] == EXPECTED_STUB
    assert payload[2:14].count(b"\x9e") == 1


@pytest.mark.functional
@pytest.mark.local
def test_compile_token_has_a_real_export_dispatch_path() -> None:
    """COMPILE dispatch must call the export orchestrator, not only record token 207."""
    source = (ROOT / "src" / "geoasm" / "direct_dispatch.asm").read_text(
        encoding="utf-8"
    )
    assert re.search(r"^\.import\s+export_compile_command\b", source, re.MULTILINE)
    command = source[source.index("direct_execute_command:") :]
    assert re.search(r"\bjsr\s+export_compile_command\b", command)


@pytest.mark.functional
@pytest.mark.local
def test_compile_export_contains_standalone_shell_contract() -> None:
    """The linked image carries the source-free shell's observable literals."""
    payload = _export()
    for literal in (b"2026 SYS2061\x8d", b"PRINT", b"CONT", b"LIST"):
        assert literal in payload
