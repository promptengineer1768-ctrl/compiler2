"""Shared fixture assertions for stock-observation-backed E2E scenarios."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest

from tests.e2e.reference_fixtures import load_reference

_SAFE_CHARS: Final = re.compile(r"[^A-Z0-9]+")
_ROOT: Final = Path(__file__).resolve().parents[1] / "fixtures" / "reference"
_PROFILE_DIRECTORIES: Final = {
    "basicv2": "c64_basicv2",
    "basicv35": "plus4_basicv35",
    "ieee": "ieee_oracle",
}


def scenario_fixture_id(scenario: dict[str, object]) -> str:
    """Return the checked-in fixture id for one E2E scenario."""
    fixture_id = scenario.get("fixture_id")
    if fixture_id is not None:
        return str(fixture_id)
    profile = str(scenario["profile"])
    mode = str(scenario["mode"])
    reference_mode = "program" if mode == "compile" else mode
    keyword = _keyword_id(str(scenario["keyword"]))
    return f"{profile}-{reference_mode}-{keyword}"


def _keyword_id(keyword: str) -> str:
    """Return a stable fixture-safe keyword id."""
    safe = keyword.upper().replace("$", "_DOLLAR").replace("#", "_HASH")
    return _SAFE_CHARS.sub("_", safe).strip("_")


def assert_fixture_backed(scenario: dict[str, object]) -> dict[str, Any]:
    """Assert that a scenario has executable fixture coverage."""
    profile = str(scenario["profile"])
    mode = str(scenario["mode"])
    fixture_id = scenario_fixture_id(scenario)
    path = _ROOT / _PROFILE_DIRECTORIES[profile] / f"{fixture_id}.json"
    if scenario.get("vice_pending") is True:
        if not path.exists():
            pytest.skip("VICE/reference fixture capture pending")
        pending_fixture = load_reference(profile, fixture_id)
        if pending_fixture["normalization_rules"] == "catalog-v1":
            pytest.skip("VICE/reference fixture capture pending")
    fixture = load_reference(profile, fixture_id)
    assert fixture["normalization_rules"] != "catalog-v1"
    reference_mode = str(fixture["reference_mode"])
    accepted_modes = {mode}
    if mode == "compile":
        accepted_modes.add("program")
    assert reference_mode in accepted_modes
    assert fixture["normalized_result"] or fixture["raw_state"].get(
        "no_semantic_output"
    )
    return fixture


def backed_scenario(
    profile: str,
    keyword: str,
    mode: str,
    *,
    fixture_id: str | None = None,
) -> dict[str, object]:
    """Build a scenario and mark it complete only for real fixtures."""
    scenario: dict[str, object] = {
        "profile": profile,
        "keyword": keyword,
        "mode": mode,
        "vice_pending": True,
    }
    if fixture_id is not None:
        scenario["fixture_id"] = fixture_id
    resolved = scenario_fixture_id(scenario)
    path = _ROOT / _PROFILE_DIRECTORIES[profile] / f"{resolved}.json"
    if path.exists():
        fixture = load_reference(profile, resolved)
        if fixture["normalization_rules"] != "catalog-v1":
            scenario["vice_pending"] = False
            scenario["fixture_id"] = resolved
    return scenario
