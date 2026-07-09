"""Tests for tools/generate_reference.py — API.md and MAP.md generator.

Covers: API table generation from routines.json, MAP table generation from
ZP allocation and routine directory, and output file creation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import generate_reference

MANIFESTS_DIR = Path(__file__).resolve().parents[2] / "manifests"
BUILD_DIR = Path(__file__).resolve().parents[2] / "build"


MINIMAL_ROUTINES: dict[str, Any] = {
    "routines": [
        {
            "name": "tokenize",
            "layer": "georam",
            "visibility": "public",
            "purpose": "Tokenize a BASIC line",
            "inputs": "A=len, XY=ptr",
            "outputs": "C=error flag",
            "clobbers": "A,X,Y",
            "return_kind": "rts",
        },
        {
            "name": "_internal_helper",
            "layer": "georam",
            "visibility": "private",
            "purpose": "Internal helper",
            "inputs": "",
            "outputs": "",
            "clobbers": "",
            "return_kind": "rts",
        },
    ]
}

MINIMAL_ZP_ALLOC: dict[str, Any] = {
    "valid": True,
    "allocation": {
        "tmp0": "$02",
        "tmp1": "$03",
    },
}

MINIMAL_ROUTINE_DIR: dict[str, Any] = {
    "routines": {
        "tokenize": {
            "id": 0,
            "layer": "georam",
            "address": "$DE00",
            "block": 0,
            "page": 0,
            "offset": 0,
            "size_bytes": 64,
            "routine_id": 0,
        },
        "_internal_helper": {
            "id": 1,
            "layer": "resident",
            "address": "$1000",
        },
    }
}


@pytest.fixture()
def routines_file(tmp_path: Path) -> Path:
    p = tmp_path / "routines.json"
    p.write_text(json.dumps(MINIMAL_ROUTINES), encoding="utf-8")
    return p


@pytest.fixture()
def zp_alloc_file(tmp_path: Path) -> Path:
    p = tmp_path / "zp_allocation.json"
    p.write_text(json.dumps(MINIMAL_ZP_ALLOC), encoding="utf-8")
    return p


@pytest.fixture()
def routine_dir_file(tmp_path: Path) -> Path:
    p = tmp_path / "routine_directory.json"
    p.write_text(json.dumps(MINIMAL_ROUTINE_DIR), encoding="utf-8")
    return p


class TestGenerateApi:
    """Tests for generate_reference.generate_api."""

    def test_api_md_created(self, routines_file: Path, tmp_path: Path) -> None:
        out = tmp_path / "API.md"
        generate_reference.generate_api(str(routines_file), str(out))
        assert out.exists()

    def test_api_md_contains_header(self, routines_file: Path, tmp_path: Path) -> None:
        out = tmp_path / "API.md"
        generate_reference.generate_api(str(routines_file), str(out))
        content = out.read_text(encoding="utf-8")
        assert "# Compiler 2 API Reference" in content

    def test_api_md_contains_public_entry(
        self, routines_file: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "API.md"
        generate_reference.generate_api(str(routines_file), str(out))
        content = out.read_text(encoding="utf-8")
        assert "tokenize" in content

    def test_api_md_excludes_private_entries(
        self, routines_file: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "API.md"
        generate_reference.generate_api(str(routines_file), str(out))
        content = out.read_text(encoding="utf-8")
        assert "_internal_helper" not in content

    def test_missing_routines_file_is_silent(self, tmp_path: Path) -> None:
        out = tmp_path / "API.md"
        generate_reference.generate_api(str(tmp_path / "nonexistent.json"), str(out))
        assert not out.exists()


class TestGenerateMap:
    """Tests for generate_reference.generate_map."""

    def test_map_md_created(
        self, zp_alloc_file: Path, routine_dir_file: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "MAP.md"
        generate_reference.generate_map(
            str(zp_alloc_file), str(routine_dir_file), str(out)
        )
        assert out.exists()

    def test_map_md_contains_zp_header(
        self, zp_alloc_file: Path, routine_dir_file: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "MAP.md"
        generate_reference.generate_map(
            str(zp_alloc_file), str(routine_dir_file), str(out)
        )
        content = out.read_text(encoding="utf-8")
        assert "Zero-Page Allocation" in content

    def test_map_md_contains_zp_variables(
        self, zp_alloc_file: Path, routine_dir_file: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "MAP.md"
        generate_reference.generate_map(
            str(zp_alloc_file), str(routine_dir_file), str(out)
        )
        content = out.read_text(encoding="utf-8")
        assert "tmp0" in content

    def test_map_md_contains_georam_section(
        self, zp_alloc_file: Path, routine_dir_file: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "MAP.md"
        generate_reference.generate_map(
            str(zp_alloc_file), str(routine_dir_file), str(out)
        )
        content = out.read_text(encoding="utf-8")
        assert "geoRAM" in content

    def test_missing_zp_alloc_still_writes_map(
        self, routine_dir_file: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "MAP.md"
        generate_reference.generate_map(
            str(tmp_path / "nonexistent.json"), str(routine_dir_file), str(out)
        )
        assert out.exists()


def test_load_reference_inputs_rejects_directory_gap(
    routines_file: Path, zp_alloc_file: Path, tmp_path: Path
) -> None:
    """The normalized model requires every manifest routine in the directory."""
    directory = tmp_path / "directory.json"
    directory.write_text(json.dumps({"routines": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing tokenize"):
        generate_reference.load_reference_inputs(
            str(routines_file), str(zp_alloc_file), str(directory)
        )


def test_validate_reference_model_accepts_minimal_contract() -> None:
    """A complete, unique minimal model passes validation."""
    model = {
        "routines": MINIMAL_ROUTINES,
        "zero_page": MINIMAL_ZP_ALLOC,
        "routine_directory": MINIMAL_ROUTINE_DIR,
    }
    assert generate_reference.validate_reference_model(model) == []


def test_write_deterministic_normalizes_and_rejects_host_paths(
    tmp_path: Path,
) -> None:
    """Reference output uses LF and cannot embed absolute host paths."""
    output = tmp_path / "reference.md"
    generate_reference.write_deterministic("alpha\r\nbeta", str(output))
    assert output.read_bytes() == b"alpha\nbeta\n"
    with pytest.raises(ValueError, match="volatile"):
        generate_reference.write_deterministic(
            "C:\\Users\\person\\artifact", str(output)
        )
