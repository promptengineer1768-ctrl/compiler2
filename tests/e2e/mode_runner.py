"""Shared E2E mode runner for BASIC compatibility limit tests.

Loads test cases from basicv2_limits.yaml and provides a unified interface
for running them through different execution modes (immediate, program, compile).

This module is the shared entry point for T1.0 E2E mode runner integration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from tests.e2e.reference_fixtures import load_reference

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIMITS_YAML = PROJECT_ROOT / "tests" / "e2e" / "cases" / "basicv2_limits.yaml"


# ---------------------------------------------------------------------------
# Case loader
# ---------------------------------------------------------------------------


def load_cases(
    profile: Optional[str] = None,
    mode: Optional[str] = None,
    area: Optional[str] = None,
    vice_pending: Optional[bool] = None,
) -> list[dict[str, Any]]:
    """Load test cases from basicv2_limits.yaml with optional filtering.

    Args:
        profile: Filter by profile (e.g., 'basicv2', 'basicv35').
        mode: Filter by mode (e.g., 'immediate', 'program', 'compile').
        area: Filter by contract area (e.g., 'line_number', 'variable_name').
        vice_pending: Filter by VICE pending status.

    Returns:
        List of matching test case dictionaries.
    """
    if not LIMITS_YAML.exists():
        return []

    with LIMITS_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    cases: list[dict[str, Any]] = data.get("cases", [])

    if profile is not None:
        cases = [c for c in cases if c.get("profile") == profile]
    if mode is not None:
        cases = [c for c in cases if c.get("mode") == mode]
    if area is not None:
        cases = [c for c in cases if c.get("area") == area]
    if vice_pending is not None:
        cases = [c for c in cases if c.get("vice_pending") == vice_pending]

    return cases


def get_case_by_id(case_id: str) -> Optional[dict[str, Any]]:
    """Get a single test case by its unique ID.

    Args:
        case_id: The unique case identifier.

    Returns:
        The case dictionary if found, None otherwise.
    """
    cases = load_cases()
    for case in cases:
        if case.get("id") == case_id:
            return case
    return None


# ---------------------------------------------------------------------------
# Mode runners
# ---------------------------------------------------------------------------


class ModeRunner:
    """Base class for E2E mode runners."""

    def __init__(self, mode: str) -> None:
        """Initialize the runner.

        Args:
            mode: The execution mode (immediate, program, compile).
        """
        self.mode = mode

    def run_case(self, case: dict[str, Any]) -> dict[str, Any]:
        """Run a single test case and return results.

        Args:
            case: The test case dictionary.

        Returns:
            Dictionary with 'passed', 'actual', and 'expected' keys.
        """
        raise NotImplementedError("Subclasses must implement run_case")


class ImmediateModeRunner(ModeRunner):
    """Runner for immediate mode execution."""

    def __init__(self) -> None:
        """Initialize immediate mode runner."""
        super().__init__("immediate")

    def run_case(self, case: dict[str, Any]) -> dict[str, Any]:
        """Run an immediate mode case.

        Args:
            case: The test case dictionary.

        Returns:
            Dictionary with execution results.
        """
        return _run_fixture_case(case, self.mode)


class ProgramModeRunner(ModeRunner):
    """Runner for program mode execution."""

    def __init__(self) -> None:
        """Initialize program mode runner."""
        super().__init__("program")

    def run_case(self, case: dict[str, Any]) -> dict[str, Any]:
        """Run a program mode case.

        Args:
            case: The test case dictionary.

        Returns:
            Dictionary with execution results.
        """
        return _run_fixture_case(case, self.mode)


class CompileModeRunner(ModeRunner):
    """Runner for compile mode execution."""

    def __init__(self) -> None:
        """Initialize compile mode runner."""
        super().__init__("compile")

    def run_case(self, case: dict[str, Any]) -> dict[str, Any]:
        """Run a compile mode case.

        Args:
            case: The test case dictionary.

        Returns:
            Dictionary with execution results.
        """
        return _run_fixture_case(case, self.mode)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_expected(case: dict[str, Any]) -> str:
    """Extract expected result from a case.

    Args:
        case: The test case dictionary.

    Returns:
        String describing the expected outcome.
    """
    if "expect_error" in case:
        return f"ERROR: {case['expect_error']}"
    if case.get("expect_ok"):
        return "OK"
    if "expected_result" in case:
        return str(case["expected_result"])
    return "UNKNOWN"


def _run_fixture_case(case: dict[str, Any], mode: str) -> dict[str, Any]:
    """Evaluate one mode case against its immutable VICE observation.

    Args:
        case: E2E case carrying profile and fixture provenance.
        mode: Compiler execution mode under test.

    Returns:
        Passed/actual/expected result record.
    """
    expected = _get_expected(case)
    fixture_id = case.get("fixture_id")
    profile = str(case.get("profile", "basicv2"))
    if case.get("vice_pending", fixture_id is None) or fixture_id is None:
        return {
            "passed": None,
            "actual": "SKIPPED: VICE fixture pending",
            "expected": expected,
        }
    fixture = load_reference(profile, str(fixture_id))
    reference_mode = str(fixture["reference_mode"])
    accepted_modes = {mode}
    if mode == "compile":
        accepted_modes.add("program")
    if reference_mode not in accepted_modes:
        return {
            "passed": False,
            "actual": f"FIXTURE MODE: {reference_mode}",
            "expected": expected,
        }
    actual = str(fixture["normalized_result"])
    if "expect_error" in case:
        wanted = str(case["expect_error"]).upper()
        passed = wanted in actual.upper() or wanted in str(fixture["raw_error"]).upper()
    elif case.get("expect_ok"):
        passed = bool(actual) and " ERROR" not in actual.upper()
    elif "expected_result" in case:
        passed = actual == str(case["expected_result"])
    else:
        passed = bool(actual)
    return {"passed": passed, "actual": actual, "expected": expected}


def get_runner_for_mode(mode: str) -> ModeRunner:
    """Get the appropriate runner for a given mode.

    Args:
        mode: The execution mode string.

    Returns:
        The appropriate ModeRunner instance.

    Raises:
        ValueError: If mode is not recognized.
    """
    runners = {
        "immediate": ImmediateModeRunner,
        "program": ProgramModeRunner,
        "compile": CompileModeRunner,
    }
    runner_cls = runners.get(mode)
    if runner_cls is None:
        raise ValueError(f"Unknown mode: {mode}. Valid modes: {list(runners.keys())}")
    return runner_cls()


def run_all_cases(
    profile: Optional[str] = None,
    mode: Optional[str] = None,
    area: Optional[str] = None,
    vice_pending: Optional[bool] = None,
) -> list[dict[str, Any]]:
    """Run all matching cases and return results.

    Args:
        profile: Filter by profile.
        mode: Filter by mode.
        area: Filter by area.
        vice_pending: Filter by VICE pending status.

    Returns:
        List of result dictionaries with case ID and execution results.
    """
    cases = load_cases(profile=profile, mode=mode, area=area, vice_pending=vice_pending)
    results = []
    for case in cases:
        runner = get_runner_for_mode(case.get("mode", "immediate"))
        result = runner.run_case(case)
        result["case_id"] = case.get("id")
        results.append(result)
    return results
