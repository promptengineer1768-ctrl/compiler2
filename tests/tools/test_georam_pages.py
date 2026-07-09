"""Tests for tools/georam_pages.py — geoRAM page placement and call directory.

Covers: manifest loading, page assignment, boundary enforcement ($DEFF),
unique ID validation, and output file generation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import georam_pages

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_ROUTINES: dict[str, Any] = {
    "routines": [
        {
            "name": "tokenize",
            "layer": "georam",
            "size_ceiling": 64,
            "visibility": "public",
            "purpose": "Tokenize a BASIC line",
            "inputs": "A=len, XY=ptr",
            "outputs": "C=error flag",
            "clobbers": "A,X,Y",
            "return_kind": "rts",
        },
        {
            "name": "detokenize",
            "layer": "georam",
            "size_ceiling": 48,
            "visibility": "public",
            "purpose": "Detokenize a stored line",
            "inputs": "A=len, XY=ptr",
            "outputs": "C=error flag",
            "clobbers": "A,X,Y",
            "return_kind": "rts",
        },
    ]
}


@pytest.fixture()
def routines_file(tmp_path: Path) -> Path:
    """Writes a minimal routines.json and returns its path."""
    p = tmp_path / "routines.json"
    p.write_text(json.dumps(MINIMAL_ROUTINES), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestLoadRoutines:
    """Tests for georam_pages.load_routine_manifest."""

    def test_loads_georam_routines(self, routines_file: Path) -> None:
        routines = georam_pages.load_routine_manifest(str(routines_file))
        georam = [r for r in routines if r.get("layer") == "georam"]
        assert len(georam) == 2

    def test_missing_file_raises(self) -> None:
        with pytest.raises((FileNotFoundError, OSError)):
            georam_pages.load_routine_manifest("/nonexistent/routines.json")


class TestPageAssignment:
    """Tests for georam_pages.assign_page_placement."""

    def test_routines_placed_within_page(self, routines_file: Path) -> None:
        routines = georam_pages.load_routine_manifest(str(routines_file))
        _, placement = georam_pages.assign_page_placement(routines)
        for name, (block, page, offset) in placement.items():
            r = next(r for r in routines if r["name"] == name)
            size = r.get("size_ceiling", 256)
            assert (
                offset + size <= 256
            ), f"Routine {name} crosses page boundary: offset={offset:#04x} size={size}"

    def test_all_ids_unique(self, routines_file: Path) -> None:
        routines = georam_pages.load_routine_manifest(str(routines_file))
        routines, id_map = georam_pages.generate_routine_ids(routines)
        ids = list(id_map.values())
        assert len(ids) == len(set(ids)), "Duplicate routine IDs detected"

    def test_addresses_start_in_de00_window(self, routines_file: Path) -> None:
        routines = georam_pages.load_routine_manifest(str(routines_file))
        _, placement = georam_pages.assign_page_placement(routines)
        for name, (block, page, offset) in placement.items():
            addr = 0xDE00 + offset
            assert (
                0xDE00 <= addr <= 0xDEFF
            ), f"Routine {name} offset {offset:#04x} places address outside window"

    def test_geoasm_layer_is_placed_in_georam(self) -> None:
        """The manifest's geoasm service layer is physical geoRAM code."""
        routines = [
            {
                "name": "tokenize",
                "layer": "geoasm",
                "size_ceiling": 64,
                "visibility": "public",
            }
        ]
        _, placement = georam_pages.assign_page_placement(routines)
        assert "tokenize" in placement

    def test_duplicate_routine_names_are_rejected(self) -> None:
        """Names are directory keys and therefore must be globally unique."""
        routines = [
            {"name": "same", "layer": "resident"},
            {"name": "same", "layer": "geoasm"},
        ]
        with pytest.raises(ValueError, match="Duplicate routine name"):
            georam_pages.generate_routine_ids(routines)


class TestBoundaryEnforcement:
    """Boundary enforcement: routines must fit within a single geoRAM page window."""

    def test_large_routine_starts_new_page(self) -> None:
        """A routine that would overflow must be placed on the next page."""
        routines = [
            {
                "name": "big",
                "layer": "georam",
                "size_ceiling": 200,
                "visibility": "public",
            },
            {
                "name": "also_big",
                "layer": "georam",
                "size_ceiling": 200,
                "visibility": "public",
            },
        ]
        _, placement = georam_pages.assign_page_placement(routines)
        _, p_big, _ = placement["big"]
        _, p_also, _ = placement["also_big"]
        # They cannot both fit on the same page (200+200 > 256)
        assert p_big != p_also

    def test_validate_no_cross_boundary_passes(self, routines_file: Path) -> None:
        routines = georam_pages.load_routine_manifest(str(routines_file))
        _, placement = georam_pages.assign_page_placement(routines)
        assert georam_pages.validate_no_cross_boundary(placement, routines) is True


def test_validate_linked_placement_accepts_current_build() -> None:
    """Linked labels, placement ceilings, and directory checksum agree."""
    root = Path(__file__).resolve().parents[2]
    assert (
        georam_pages.validate_linked_placement(
            str(root / "manifests" / "routines.json"),
            str(root / "build" / "routine_directory.json"),
            str(root / "build" / "compiler.lbl"),
            str(root / "build" / "compiler.map"),
        )
        == []
    )


def test_validate_linked_placement_detects_directory_corruption(
    tmp_path: Path,
) -> None:
    """Directory checksum validation detects placement byte drift."""
    root = Path(__file__).resolve().parents[2]
    source = root / "build" / "routine_directory.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    record = next(
        record
        for record in data["routines"].values()
        if record.get("layer") == "georam"
    )
    record["page"] = (int(record["page"]) + 1) % 64
    corrupted = tmp_path / "routine_directory.json"
    corrupted.write_text(json.dumps(data), encoding="utf-8")
    errors = georam_pages.validate_linked_placement(
        str(root / "manifests" / "routines.json"),
        str(corrupted),
        str(root / "build" / "compiler.lbl"),
        str(root / "build" / "compiler.map"),
    )
    assert "routine directory CRC32 does not match generated tables" in errors


class TestOutputFiles:
    """Tests for georam_pages.generate_call_directory output."""

    def test_routine_directory_json_valid(
        self, routines_file: Path, tmp_path: Path
    ) -> None:
        routines = georam_pages.load_routine_manifest(str(routines_file))
        routines, placement = georam_pages.assign_page_placement(routines)
        routines, _ = georam_pages.generate_routine_ids(routines)
        georam_pages.generate_call_directory(routines, placement, str(tmp_path))
        out = tmp_path / "routine_directory.json"
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "routines" in data

    def test_georam_pages_inc_generated(
        self, routines_file: Path, tmp_path: Path
    ) -> None:
        routines = georam_pages.load_routine_manifest(str(routines_file))
        routines, placement = georam_pages.assign_page_placement(routines)
        routines, _ = georam_pages.generate_routine_ids(routines)
        georam_pages.generate_call_directory(routines, placement, str(tmp_path))
        inc_path = tmp_path / "georam_pages.inc"
        assert inc_path.exists()
        content = inc_path.read_text(encoding="utf-8")
        assert content.strip() != ""
        assert "georam_group_0_blocks:" in content
        assert "georam_group_0_pages:" in content
        assert "georam_group_0_offsets:" in content
        assert content.count(".byte") >= 3
