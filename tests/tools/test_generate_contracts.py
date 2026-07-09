"""Tests for tools/generate_contracts.py — ABI, arena, command, and format exports.

Covers: contract generation outputs including runtime_abi.json, arena_layout.json,
production_entries.json, test_entries.json, and keyword_lookup_report.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import generate_contracts

MANIFESTS_DIR = Path(__file__).resolve().parents[2] / "manifests"


def _require_manifest(name: str) -> None:
    if not (MANIFESTS_DIR / name).exists():
        pytest.skip(f"Manifest {name} not present; T0.2 prerequisite unmet")


class TestGenerateRuntimeAbi:
    """Tests that runtime_abi.json is generated from manifests/runtime_abi.json."""

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        _require_manifest("runtime_abi.json")
        generate_contracts.generate_runtime_abi(
            str(MANIFESTS_DIR / "runtime_abi.json"), str(tmp_path)
        )
        out = tmp_path / "runtime_abi.json"
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_output_has_entries_key(self, tmp_path: Path) -> None:
        _require_manifest("runtime_abi.json")
        generate_contracts.generate_runtime_abi(
            str(MANIFESTS_DIR / "runtime_abi.json"), str(tmp_path)
        )
        out = tmp_path / "runtime_abi.json"
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "entries" in data


class TestGenerateArenaLayout:
    """Tests that arena_layout.json is generated from manifests/arenas.json."""

    def test_output_contains_arenas(self, tmp_path: Path) -> None:
        _require_manifest("arenas.json")
        generate_contracts.generate_arena_layout(
            str(MANIFESTS_DIR / "arenas.json"), str(tmp_path)
        )
        out = tmp_path / "arena_layout.json"
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "arenas" in data

    def test_capacity_pages_present(self, tmp_path: Path) -> None:
        _require_manifest("arenas.json")
        generate_contracts.generate_arena_layout(
            str(MANIFESTS_DIR / "arenas.json"), str(tmp_path)
        )
        out = tmp_path / "arena_layout.json"
        data = json.loads(out.read_text(encoding="utf-8"))
        for arena in data["arenas"]:
            assert (
                "capacity_pages" in arena
            ), f"Arena {arena.get('name')} missing capacity_pages"

    def test_program_staging_contract_and_generated_count(self, tmp_path: Path) -> None:
        """Generation exposes the dedicated whole-program staging arena."""
        _require_manifest("arenas.json")
        generate_contracts.generate_arena_layout(
            str(MANIFESTS_DIR / "arenas.json"), str(tmp_path)
        )
        data = json.loads((tmp_path / "arena_layout.json").read_text(encoding="utf-8"))
        staging = next(
            arena for arena in data["arenas"] if arena["name"] == "program_staging"
        )
        assert staging == {
            "name": "program_staging",
            "type_code": 9,
            "capacity_pages": 128,
        }
        include = (tmp_path / "arena_layout.inc").read_text(encoding="utf-8")
        assert "ARENA_COUNT = 9" in include
        assert "ARENA_TYPE_PROGRAM_STAGING = 9" in include
        assert "ARENA_MIN_PAGES_PROGRAM_STAGING = 128" in include


class TestGenerateKeywordLookup:
    """Tests that keyword_lookup_report.json is generated from manifests/commands.json."""

    def test_output_has_keywords(self, tmp_path: Path) -> None:
        _require_manifest("commands.json")
        generate_contracts.generate_command_tables(
            str(MANIFESTS_DIR / "commands.json"), str(tmp_path)
        )
        out = tmp_path / "keyword_lookup_report.json"
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "keywords" in data

    def test_all_keywords_are_strings(self, tmp_path: Path) -> None:
        _require_manifest("commands.json")
        generate_contracts.generate_command_tables(
            str(MANIFESTS_DIR / "commands.json"), str(tmp_path)
        )
        out = tmp_path / "keyword_lookup_report.json"
        data = json.loads(out.read_text(encoding="utf-8"))
        for kw in data["keywords"]:
            assert isinstance(kw, str), f"Keyword entry is not a string: {kw!r}"


class TestProductionAndTestEntries:
    """Tests for production_entries.json and test_entries.json generation."""

    def test_production_entries_generated(self, tmp_path: Path) -> None:
        routines_path = MANIFESTS_DIR / "routines.json"
        if not routines_path.exists():
            pytest.skip("routines.json not present")
        generate_contracts.generate_entry_manifests(str(routines_path), str(tmp_path))
        out = tmp_path / "production_entries.json"
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "production_entries" in data

    def test_test_entries_generated(self, tmp_path: Path) -> None:
        routines_path = MANIFESTS_DIR / "routines.json"
        if not routines_path.exists():
            pytest.skip("routines.json not present")
        generate_contracts.generate_entry_manifests(str(routines_path), str(tmp_path))
        out = tmp_path / "test_entries.json"
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "test_entries" in data
