"""System contract tests for E2E compatibility-limit coverage.

Asserts that every contract area listed in docs/BASIC_COMPATIBILITY_LIMITS.md
has at least one named case in tests/e2e/cases/basicv2_limits.yaml, and that
every YAML case carries the required fields.

These tests are intentionally STATIC — they parse documents, not the runtime.
They run without VICE and without 6502 execution.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml  # PyYAML; available via: pip install pyyaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIMITS_DOC = PROJECT_ROOT / "docs" / "BASIC_COMPATIBILITY_LIMITS.md"
LIMITS_YAML = PROJECT_ROOT / "tests" / "e2e" / "cases" / "basicv2_limits.yaml"

# ---------------------------------------------------------------------------
# Required fields per case in the YAML
# ---------------------------------------------------------------------------

REQUIRED_CASE_FIELDS = frozenset(
    {"id", "area", "profile", "mode", "description", "source_note", "vice_pending"}
)

# Every case must have exactly one of these outcome fields.
OUTCOME_FIELDS = frozenset({"expect_ok", "expect_error"})

# ---------------------------------------------------------------------------
# Area names extracted from the LIMITS doc table
# Sourced from the | Area | column of the BASIC V2 Contracts table.
# ---------------------------------------------------------------------------

# These must match the `area:` values used in basicv2_limits.yaml.
REQUIRED_AREAS = [
    "line_number",
    "line_record",
    "screen_editor",
    "line_payload",
    "variable_name",
    "variable_type",
    "reserved_name",
    "string_length",
    "integer_range",
    "byte_argument",
    "address_argument",
    "arrays",
    "logical_files",
    "load_save_device",
    "open_device",
    "filename",
    "data_input",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_yaml() -> list[dict[str, Any]]:
    """Loads and parses basicv2_limits.yaml, returning the cases list."""
    if not LIMITS_YAML.exists():
        pytest.fail(
            f"basicv2_limits.yaml not found at {LIMITS_YAML}. "
            "T1.0 RED phase: create the file before the coverage test can pass."
        )
    with LIMITS_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    cases: list[dict[str, Any]] = data.get("cases", [])
    return cases


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.system
@pytest.mark.static
class TestLimitsYamlStructure:
    """Structural validity of basicv2_limits.yaml."""

    def test_yaml_is_parseable(self) -> None:
        """YAML file parses without errors."""
        cases = _load_yaml()
        assert isinstance(cases, list), "Expected top-level 'cases' key to be a list"

    def test_at_least_one_case(self) -> None:
        """The manifest contains at least one case."""
        cases = _load_yaml()
        assert len(cases) > 0, "basicv2_limits.yaml has no cases"

    def test_all_case_ids_are_unique(self) -> None:
        """All case IDs must be unique."""
        cases = _load_yaml()
        ids = [c["id"] for c in cases if "id" in c]
        assert len(ids) == len(
            set(ids)
        ), f"Duplicate case IDs: {[i for i in ids if ids.count(i) > 1]}"

    @pytest.mark.parametrize("field", sorted(REQUIRED_CASE_FIELDS))
    def test_all_cases_have_required_field(self, field: str) -> None:
        """Every case must carry the required field."""
        cases = _load_yaml()
        missing = [c.get("id", "<no id>") for c in cases if field not in c]
        assert not missing, f"Cases missing required field '{field}': {missing}"

    def test_all_cases_have_outcome_field(self) -> None:
        """Every case must declare expect_ok or expect_error (but not both)."""
        cases = _load_yaml()
        violations: list[str] = []
        for c in cases:
            has = OUTCOME_FIELDS & set(c.keys())
            if len(has) != 1:
                violations.append(
                    f"{c.get('id', '<no id>')}: outcome fields present={has}"
                )
        assert (
            not violations
        ), "Cases must have exactly one of expect_ok / expect_error:\n" + "\n".join(
            violations
        )

    def test_all_case_ids_follow_naming_convention(self) -> None:
        """IDs must match: <profile>-<mode>-<area>-<description>."""
        pattern = re.compile(
            r"^basicv[23][.5]*-[a-z_]+-[a-z_]+-[a-zA-Z_0-9][a-zA-Z_0-9-]*$"
        )
        cases = _load_yaml()
        bad = [c["id"] for c in cases if "id" in c and not pattern.match(c["id"])]
        assert not bad, f"Case IDs not matching naming convention: {bad}"

    def test_vice_pending_is_boolean(self) -> None:
        """vice_pending must be a boolean."""
        cases = _load_yaml()
        bad = [
            c.get("id", "<no id>")
            for c in cases
            if "vice_pending" in c and not isinstance(c["vice_pending"], bool)
        ]
        assert not bad, f"vice_pending must be bool; bad cases: {bad}"


@pytest.mark.system
@pytest.mark.static
class TestCompatibilityLimitsCoverage:
    """Every contract area from BASIC_COMPATIBILITY_LIMITS.md has >= 1 YAML case."""

    def _covered_areas(self) -> set[str]:
        cases = _load_yaml()
        return {c["area"] for c in cases if "area" in c}

    @pytest.mark.parametrize("area", REQUIRED_AREAS)
    def test_area_has_at_least_one_case(self, area: str) -> None:
        """Each required area has at least one case in basicv2_limits.yaml."""
        covered = self._covered_areas()
        assert area in covered, (
            f"Compatibility-limit area '{area}' has no E2E case in basicv2_limits.yaml. "
            "Add at least one case with area: {area!r}."
        )

    def test_no_unknown_areas(self) -> None:
        """All areas in the YAML are known required areas (catches typos)."""
        covered = self._covered_areas()
        unknown = covered - set(REQUIRED_AREAS)
        assert not unknown, (
            f"Unknown area values in basicv2_limits.yaml: {unknown}. "
            "Add to REQUIRED_AREAS in this test or fix the YAML."
        )


@pytest.mark.system
@pytest.mark.static
class TestCompatibilityLimitsDocAligned:
    """The YAML case count and area coverage align with the limits doc."""

    def test_limits_doc_exists(self) -> None:
        assert (
            LIMITS_DOC.exists()
        ), f"BASIC_COMPATIBILITY_LIMITS.md not found at {LIMITS_DOC}"

    def test_yaml_covers_all_doc_areas(self) -> None:
        """All REQUIRED_AREAS are represented (integration of doc + yaml check)."""
        cases = _load_yaml()
        covered = {c["area"] for c in cases if "area" in c}
        missing = set(REQUIRED_AREAS) - covered
        assert (
            not missing
        ), f"Areas in REQUIRED_AREAS not covered in basicv2_limits.yaml: {missing}"
