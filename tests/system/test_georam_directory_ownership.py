"""System contracts for the single resident geoRAM directory owner."""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "src" / "resident" / "georam_gate.asm"
WEDGE = ROOT / "src" / "geoasm" / "dos_wedge.asm"


@pytest.mark.system
@pytest.mark.static
def test_generated_georam_directory_is_owned_only_by_resident_gate() -> None:
    """An XIP caller imports IDs; it must not duplicate the 1.5 KiB directory."""
    gate = GATE.read_text(encoding="utf-8")
    wedge = WEDGE.read_text(encoding="utf-8")
    assert '.include "georam_pages.inc"' in gate
    assert '.include "georam_pages.inc"' not in wedge
    assert ".import GEORAM_ROUTINE_ID_WEDGE_PARSE" in wedge
    assert ".export GEORAM_ROUTINE_ID_WEDGE_PARSE" in gate
