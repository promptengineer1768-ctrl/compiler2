"""Honesty contracts for Phase 11 language E2E completion."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Final, cast

import pytest

ROOT: Final = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
FIXTURE_ROOT: Final = ROOT / "tests" / "fixtures" / "reference"
SCENARIO_MODULES: Final = (
    "tests.e2e.test_e2e_basicv2_functions",
    "tests.e2e.test_e2e_basicv2_statements",
    "tests.e2e.test_e2e_basicv35_functions",
    "tests.e2e.test_e2e_basicv35_statements",
    "tests.e2e.test_e2e_basicv3_functions_ieee",
    "tests.e2e.test_e2e_basicv3_statements_ieee",
)
PROFILE_DIRECTORIES: Final = {
    "basicv2": "c64_basicv2",
    "basicv35": "plus4_basicv35",
    "ieee": "ieee_oracle",
}
STOCK_PROFILES: Final = {"basicv2", "basicv35"}


def _scenarios() -> list[dict[str, object]]:
    """Return every Phase 11 language scenario."""
    scenarios: list[dict[str, object]] = []
    for module_name in SCENARIO_MODULES:
        module = importlib.import_module(module_name)
        for parameter_set in module.SCENARIOS:
            value = parameter_set.values[0]
            assert isinstance(value, dict)
            scenarios.append(value)
    return scenarios


def _fixture_id(scenario: dict[str, object]) -> str:
    """Return the fixture id a scenario resolves to."""
    explicit = scenario.get("fixture_id")
    if explicit is not None:
        return str(explicit)
    from tests.e2e.scenario_fixtures import scenario_fixture_id

    return scenario_fixture_id(scenario)


def _fixture(scenario: dict[str, object]) -> dict[str, Any]:
    """Load the fixture for one scenario."""
    directory = PROFILE_DIRECTORIES[str(scenario["profile"])]
    path = FIXTURE_ROOT / directory / f"{_fixture_id(scenario)}.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _has_real_fixture(scenario: dict[str, object]) -> bool:
    """Return whether one scenario is backed by a real capture/oracle."""
    directory = PROFILE_DIRECTORIES[str(scenario["profile"])]
    path = FIXTURE_ROOT / directory / f"{_fixture_id(scenario)}.json"
    if not path.exists():
        return False
    data = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    return data.get("normalization_rules") != "catalog-v1"


@pytest.mark.system
@pytest.mark.static
def test_fixture_backed_language_cases_are_not_catalog_placeholders() -> None:
    """Rows marked complete must point at real captures or reviewed oracles."""
    complete = [case for case in _scenarios() if _has_real_fixture(case)]
    assert complete
    placeholder_ids = [
        _fixture_id(case)
        for case in complete
        if _fixture(case).get("normalization_rules") == "catalog-v1"
    ]
    assert (
        not placeholder_ids
    ), "Phase 11 fixture-backed cases cannot use catalog placeholders: " + ", ".join(
        placeholder_ids
    )


@pytest.mark.system
@pytest.mark.static
def test_phase11_language_completion_has_no_pending_rows() -> None:
    """Every Phase 11 language row is backed by a real capture or oracle."""
    pending = [case for case in _scenarios() if not _has_real_fixture(case)]
    assert not pending


@pytest.mark.system
@pytest.mark.static
def test_all_stock_language_rows_have_capture_sources() -> None:
    """Every stock pending row must be capturable by the VICE fixture tool."""
    from e2e_source_catalog import stock_source_case

    missing = [
        f"{case['profile']} {case['mode']} {case['keyword']}"
        for case in _scenarios()
        if case["profile"] in STOCK_PROFILES
        and stock_source_case(
            str(case["profile"]), str(case["keyword"]), str(case["mode"])
        )
        is None
    ]
    assert not missing
