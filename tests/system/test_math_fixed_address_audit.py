"""System audit for math code fixed-address independence."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MATH_SOURCES = (
    ROOT / "src" / "geoasm" / "math_trans.asm",
    ROOT / "src" / "geoasm" / "math_trig.asm",
)

LEGACY_ROM_ADDRESSES = {
    "$B6E0",
    "$B849",
    "$B850",
    "$B867",
    "$B903",
    "$B9EA",
    "$BA28",
    "$BB0F",
    "$BBA2",
    "$BBD4",
    "$BBFC",
    "$BC1B",
    "$BC39",
    "$BC93",
    "$BE28",
    "$BF71",
}
LEGACY_ZP_ADDRESSES = {
    "$53",
    "$54",
    "$55",
    "$56",
    "$5D",
    "$5E",
    "$5F",
    "$60",
    "$61",
    "$62",
    "$63",
    "$64",
    "$65",
    "$66",
    "$67",
    "$68",
    "$69",
    "$6A",
}


@pytest.mark.system
def test_georam_math_sources_do_not_reference_legacy_rom_or_zp_addresses() -> None:
    """Ported math sources must use Compiler 2 symbols instead of ROM addresses."""
    forbidden = LEGACY_ROM_ADDRESSES | LEGACY_ZP_ADDRESSES
    assignment = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*(\$[0-9A-Fa-f]{2,4})")
    absolute_use = re.compile(
        r"\b(?:jsr|jmp|lda|ldx|ldy|sta|stx|sty)\s+(\$[0-9A-Fa-f]{2,4})\b", re.IGNORECASE
    )
    violations: list[str] = []
    for source in MATH_SOURCES:
        for line_no, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), 1
        ):
            code = line.split(";", maxsplit=1)[0]
            matches = []
            if found := assignment.search(code):
                matches.append(found.group(1))
            matches.extend(absolute_use.findall(code))
            for match in matches:
                if match.upper() in forbidden:
                    violations.append(f"{source.relative_to(ROOT)}:{line_no}: {match}")
    assert violations == []
