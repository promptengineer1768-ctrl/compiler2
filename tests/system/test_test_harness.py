"""System tests for test harness validation (T10.4).

Tests verify coverage matrix and callable entry point coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.system
class TestCoverageMatrix:
    """Coverage matrix validation tests."""

    def test_coverage_report_exists(self) -> None:
        """Coverage report must exist after build."""
        path = ROOT / "build" / "test_coverage.json"
        assert path.exists()

    def test_coverage_report_valid_json(self) -> None:
        """Coverage report must be valid JSON."""
        path = ROOT / "build" / "test_coverage.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)


@pytest.mark.system
class TestCallableCoverage:
    """Callable entry point coverage tests."""

    def test_routine_directory_exists(self) -> None:
        """Routine directory must exist for coverage check."""
        path = ROOT / "build" / "routine_directory.json"
        assert path.exists()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "routines" in data

    def test_all_routines_have_tests(self) -> None:
        """Each public routine should have at least one test."""
        dir_path = ROOT / "build" / "routine_directory.json"
        assert dir_path.exists()
        with open(dir_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        routines = data.get("routines", {})
        assert isinstance(routines, dict)
        coverage = json.loads(
            (ROOT / "build" / "test_coverage.json").read_text(encoding="utf-8")
        )
        assert coverage["total_routines"] == len(coverage["entries"])
        assert coverage["uncovered_routines"] == []
        assert coverage["covered_routines"] == coverage["total_routines"]
