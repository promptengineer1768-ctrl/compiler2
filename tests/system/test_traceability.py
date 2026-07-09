"""System contract tests for requirement traceability.

Ensures every requirement in manifests/traceability.json maps to at least one
valid test, and that all mapped tests exist in the test suites.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRACE_JSON = PROJECT_ROOT / "manifests" / "traceability.json"
LIMITS_YAML = PROJECT_ROOT / "tests" / "e2e" / "cases" / "basicv2_limits.yaml"
MATRIX_JSON = PROJECT_ROOT / "build" / "requirements_matrix.json"


def _discover_python_tests() -> set[str]:
    """Scans tests/ directory for test class and function names."""
    test_names: set[str] = set()
    test_dir = PROJECT_ROOT / "tests"
    if not test_dir.exists():
        return test_names

    # Simple regex to find test functions and classes
    func_pattern = re.compile(r"^\s*def\s+(test_[a-zA-Z0-9_]+)\s*\(")
    class_pattern = re.compile(r"^\s*class\s+(Test[a-zA-Z0-9_]+)\b")

    for root, _, files in os.walk(test_dir):
        for file in files:
            if file.endswith(".py") and file.startswith("test_"):
                # Also count the test module filename itself
                test_names.add(file[:-3])
                path = Path(root) / file
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            m_func = func_pattern.match(line)
                            if m_func:
                                test_names.add(m_func.group(1))
                            m_class = class_pattern.match(line)
                            if m_class:
                                test_names.add(m_class.group(1))
                except OSError:
                    pass
    return test_names


def _discover_yaml_cases() -> set[str]:
    """Loads E2E limit case IDs from basicv2_limits.yaml."""
    case_ids: set[str] = set()
    if LIMITS_YAML.exists():
        try:
            with open(LIMITS_YAML, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            for c in data.get("cases", []):
                if "id" in c:
                    case_ids.add(c["id"])
        except Exception:
            pass
    return case_ids


@pytest.mark.system
@pytest.mark.static
class TestTraceability:
    """Traceability manifest verification tests."""

    def test_traceability_manifest_exists(self) -> None:
        """traceability.json must exist."""
        assert TRACE_JSON.exists(), f"traceability.json not found at {TRACE_JSON}"

    def test_traceability_manifest_is_valid_json(self) -> None:
        """traceability.json must parse as valid JSON."""
        with open(TRACE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "records" in data
        assert isinstance(data["records"], list)

    def test_requirements_to_tests_mapping(self) -> None:
        """Every requirement maps to at least one test, and those tests exist."""
        with open(TRACE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        records = data.get("records", [])
        assert len(records) > 0, "No records found in traceability.json"

        py_tests = _discover_python_tests()
        yaml_cases = _discover_yaml_cases()
        all_known_tests = py_tests | yaml_cases

        missing_mappings = []
        invalid_tests = []

        for r in records:
            req_id = r.get("id", "<no-id>")
            tests = r.get("tests", [])

            if not tests:
                missing_mappings.append(req_id)
                continue

            for t in tests:
                # We accept exact match or substrings to support flexible mapping
                if not any(t in kt or kt in t for kt in all_known_tests):
                    invalid_tests.append((req_id, t))

        assert not missing_mappings, f"Requirements without tests: {missing_mappings}"
        assert (
            not invalid_tests
        ), f"Referenced tests not found in test suite: {invalid_tests}"

    def test_tests_to_requirements_mapping(self) -> None:
        """Every mapped test has an inverse requirement index entry."""
        with open(TRACE_JSON, "r", encoding="utf-8") as f:
            trace = json.load(f)
        with open(MATRIX_JSON, "r", encoding="utf-8") as f:
            matrix = json.load(f)

        expected: dict[str, set[str]] = {}
        for record in trace.get("records", []):
            for test_name in record.get("tests", []):
                expected.setdefault(str(test_name), set()).add(str(record["id"]))

        inverse = {
            str(row["test"]): set(row["requirements"])
            for row in matrix.get("mapped_tests", [])
        }

        assert expected, "Traceability manifest has no mapped tests"
        assert inverse == expected
