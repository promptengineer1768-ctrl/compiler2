"""Schema and semantic checks for stock VICE reference fixtures."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "reference"
sys.path.insert(0, str(ROOT / "tools"))

from generate_vice_fixtures import normalize_screen  # noqa: E402

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
STOCK_PROFILE_CONTRACTS = {
    "c64_basicv2": {
        "count": 105,
        "modes": {"immediate": 47, "program": 58},
        "vice_version": "3.10",
        "rom_checksums": {
            "basic-901226-01.bin": "89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d",
            "chargen-901225-01.bin": "fd0d53b8480e86163ac98998976c72cc58d5dd8eb824ed7b829774e74213b420",
            "kernal-901227-03.bin": "83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721",
        },
    },
    "plus4_basicv35": {
        "count": 40,
        "modes": {"immediate": 8, "program": 32},
        "vice_version": "3.10",
        "rom_checksums": {
            "3plus1-317053-01.bin": "628eb4b01b8701e6fc5bd4b7e9e6573deae47e0b0f8b150b4022596501d5131d",
            "3plus1-317054-01.bin": "2e83bfdfd93a2d9e8adfe4bb302869a30eac12015f6b41302c9d1ed3bb83de16",
            "basic-318006-01.bin": "cbf0c4dec44e3e203beaf09690e5c7f859b0eca164e789884161c8cb0e596567",
            "kernal-318004-05.bin": "1f07270c43fc84d1556978e5bb3a6b08aa7b1253f2e46d1a452c89c972ae506b",
        },
    },
}


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


@pytest.mark.parametrize("directory", sorted(STOCK_PROFILE_CONTRACTS))
def test_stock_profile_fixture_corpus_is_complete(directory: str) -> None:
    """Each stock profile retains its reviewed fixture count and mode coverage."""
    contract = STOCK_PROFILE_CONTRACTS[directory]
    documents = [
        _load_fixture(path)
        for path in sorted((FIXTURE_ROOT / directory).glob("*.json"))
    ]
    mode_counts = {
        mode: sum(document["reference_mode"] == mode for document in documents)
        for mode in ("immediate", "program")
    }
    assert len(documents) == contract["count"]
    assert mode_counts == contract["modes"]
    assert {document["vice_version"] for document in documents} == {
        contract["vice_version"]
    }
    assert {document["normalization_rules"] for document in documents} == {"screen-v1"}
    assert all(
        document["rom_checksums"] == contract["rom_checksums"] for document in documents
    )


@pytest.mark.parametrize("directory", sorted(STOCK_PROFILE_CONTRACTS))
def test_stock_profile_normalized_results_replay(directory: str) -> None:
    """Stored stock results are exactly reproducible from raw VICE screens."""
    for path in sorted((FIXTURE_ROOT / directory).glob("*.json")):
        document = _load_fixture(path)
        source_lines = tuple(str(document["source_text"]).splitlines())
        assert (
            normalize_screen(document["raw_screen"], source_lines)
            == document["normalized_result"]
        ), path.name


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
