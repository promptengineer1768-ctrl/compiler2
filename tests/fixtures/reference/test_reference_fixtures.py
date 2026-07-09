"""Schema and semantic checks for stock VICE reference fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "reference"

REQUIRED_FIELDS = {
    "schema_version",
    "profile",
    "machine",
    "vice_executable",
    "vice_version",
    "rom_checksums",
    "source_text",
    "input_sequence",
    "reference_mode",
    "raw_screen",
    "raw_error",
    "raw_state",
    "normalized_result",
    "normalization_rules",
    "generator_version",
    "regeneration_fingerprint",
}

EXPECTED_RESULTS = {
    "basicv2-immediate-PRINT": "OK",
    "basicv2-immediate-SGN": "-1",
    "basicv2-program-ASC": 'LOAD"*",8,1\nSEARCHING FOR *\nLOADING\n193',
    "basicv2-program-FOR": 'LOAD"*",8,1\nSEARCHING FOR *\nLOADING\n1\n2\n3',
    "basicv2-program-GOTO": 'LOAD"*",8,1\nSEARCHING FOR *\nLOADING\nOK',
    "basicv2-program-SPC": 'LOAD"*",8,1\nSEARCHING FOR *\nLOADING\nA B',
    "basicv35-immediate-BASIC3_5": ('LOAD"*",8,1\nSEARCHING FOR *\nLOADING\n3.5'),
    "basicv35-immediate-DO": 'LOAD"*",8,1\nSEARCHING FOR *\nLOADING',
    "basicv35-program-EXIT_DO": 'LOAD"*",8,1\nSEARCHING FOR *\nLOADING\nOK',
    "basicv35-program-LOOP": 'LOAD"*",8,1\nSEARCHING FOR *\nLOADING\n1\n2\n3',
    "basicv35-program-UNTIL": 'LOAD"*",8,1\nSEARCHING FOR *\nLOADING\n1\n2',
    "basicv35-program-WHILE": 'LOAD"*",8,1\nSEARCHING FOR *\nLOADING\n1\n2',
}
STOCK_FIXTURE_IDS = set(EXPECTED_RESULTS)


def _fixture_paths() -> list[Path]:
    """Return all checked-in stock fixture documents."""
    return sorted(FIXTURE_ROOT.glob("*/*.json"))


def _load_fixture(path: Path) -> dict[str, Any]:
    """Load one fixture JSON document."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda path: path.stem)
def test_reference_fixture_schema(path: Path) -> None:
    """Each fixture records the full VICE observation schema."""
    data = _load_fixture(path)
    assert REQUIRED_FIELDS <= data.keys()
    assert data["schema_version"] == "1.0"
    assert data["generator_version"] == "1.0"
    assert data["reference_mode"] in {"immediate", "program"}
    assert isinstance(data["raw_state"], dict)
    assert data["normalization_rules"] in {"screen-v1", "catalog-v1", "oracle-v1"}


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda path: path.stem)
def test_reference_fixture_profile_matches_directory(path: Path) -> None:
    """Fixture profile and machine metadata must match its storage bucket."""
    data = _load_fixture(path)
    if path.parent.name == "c64_basicv2":
        assert data["profile"] == "basicv2"
        assert data["machine"] == "C64"
        assert data["vice_executable"] == "x64sc.exe"
    elif path.parent.name == "plus4_basicv35":
        assert data["profile"] == "basicv35"
        assert data["machine"] == "PLUS4"
        assert data["vice_executable"] == "xplus4.exe"
    elif path.parent.name == "ieee_oracle":
        assert data["profile"] == "ieee"
        assert data["machine"] == "ORACLE"
        assert data["vice_executable"] in {
            "compiler2-oracle",
            "compiler2-ieee-oracle",
        }
    else:
        pytest.fail(f"Unexpected fixture directory: {path.parent.name}")


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda path: path.stem)
def test_reference_fixture_rom_checksums_are_sha256(path: Path) -> None:
    """ROM provenance is recorded as exact SHA-256 hashes."""
    data = _load_fixture(path)
    checksums = data["rom_checksums"]
    assert isinstance(checksums, dict)
    assert checksums
    for digest in checksums.values():
        assert isinstance(digest, str)
        assert len(digest) == 64
        assert all(char in "0123456789abcdef" for char in digest)


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda path: path.stem)
def test_reference_fixture_fingerprint_matches_payload(path: Path) -> None:
    """The regeneration fingerprint covers the fixture payload."""
    data = _load_fixture(path)
    stored = data.pop("regeneration_fingerprint")
    payload = json.dumps(data, sort_keys=True).encode()
    assert stored == hashlib.sha256(payload).hexdigest()


def test_reference_fixture_catalog_is_complete() -> None:
    """The checked-in fixture set matches the current generated case catalog."""
    fixture_ids = {path.stem for path in _fixture_paths()}
    assert STOCK_FIXTURE_IDS <= fixture_ids


def test_basicv2_reference_fixtures_are_real_vice_captures() -> None:
    """BASIC V2 fixtures must be reviewed VICE observations, not catalog stubs."""
    placeholders = [
        path.name
        for path in (FIXTURE_ROOT / "c64_basicv2").glob("*.json")
        if _load_fixture(path)["normalization_rules"] == "catalog-v1"
    ]
    assert placeholders == []


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda path: path.stem)
def test_reference_fixture_semantics_match_catalog(path: Path) -> None:
    """Stock observations match the reviewed source-derived case expectations."""
    data = _load_fixture(path)
    if path.stem in EXPECTED_RESULTS:
        assert data["normalized_result"] == EXPECTED_RESULTS[path.stem]
    else:
        assert data["normalized_result"] or data["raw_state"].get(
            "no_semantic_output"
        ), "fixture must have semantic output or explicit no-output provenance"
