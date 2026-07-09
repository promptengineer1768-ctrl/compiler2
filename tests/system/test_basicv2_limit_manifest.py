"""Coverage and provenance contracts for BASIC V2 compatibility limits."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = ROOT / "docs" / "BASIC_COMPATIBILITY_LIMITS.md"
MANIFEST = ROOT / "tests" / "e2e" / "cases" / "basicv2_limits.yaml"
C64ROM = ROOT.parent / "c64rom"


def _load() -> dict[str, object]:
    """Load the compatibility manifest as a mapping."""
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _document_areas() -> set[str]:
    """Extract normative BASIC V2 contract row names."""
    text = DOCUMENT.read_text(encoding="utf-8")
    section = text.split("## BASIC V2 Contracts", 1)[1].split(
        "## BASIC 3.5 Contracts", 1
    )[0]
    return {
        columns[1].strip()
        for line in section.splitlines()
        if line.startswith("|")
        and not line.startswith("|---")
        and (columns := line.split("|"))[1].strip() != "Area"
    }


@pytest.mark.system
@pytest.mark.static
def test_every_documented_limit_row_has_cases_and_local_provenance() -> None:
    """Every normative row maps to cases and an existing c64rom source."""
    data = _load()
    areas = data["contract_areas"]
    cases = data["cases"]
    assert isinstance(areas, dict)
    assert isinstance(cases, list)
    assert {record["document_area"] for record in areas.values()} == _document_areas()
    case_areas = {case["area"] for case in cases}
    assert case_areas == set(areas)
    for record in areas.values():
        source = str(record["source_ref"]).split(":", 1)[0].split(",", 1)[0]
        assert (C64ROM / source).is_file(), source
        assert record["feature_group"]


@pytest.mark.system
@pytest.mark.static
def test_limit_case_schema_ids_and_pending_status_are_authoritative() -> None:
    """Cases have stable identities, expectations, and explicit VICE status."""
    data = _load()
    cases = data["cases"]
    assert isinstance(cases, list)
    ids = [str(case["id"]) for case in cases]
    assert len(ids) == 48
    assert len(set(ids)) == len(ids)
    assert all(
        re.fullmatch(r"basicv2-(immediate|program|compile)-[A-Za-z0-9_-]+", case_id)
        for case_id in ids
    )
    for case in cases:
        assert case["profile"] == "basicv2"
        assert case["mode"] in {"immediate", "program", "compile"}
        assert case["vice_pending"] is True
        assert bool(case.get("expect_ok")) != ("expect_error" in case)
        assert str(case["source_note"]).strip()


@pytest.mark.system
@pytest.mark.static
def test_limit_manifest_contains_required_edge_families() -> None:
    """The manifest covers every explicitly named edge family."""
    cases = _load()["cases"]
    assert isinstance(cases, list)
    areas = {case["area"] for case in cases}
    assert {
        "line_number",
        "variable_name",
        "string_length",
        "arrays",
        "load_save_device",
        "logical_files",
        "open_device",
        "filename",
        "data_input",
    } <= areas
