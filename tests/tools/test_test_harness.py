"""Tests for tools/test_harness.py — requirements traceability matrix generator.

Covers: traceability manifest loading, matrix generation, and output structure.
"""

from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import test_harness

MANIFESTS_DIR = Path(__file__).resolve().parents[2] / "manifests"
TRACE_PATH = MANIFESTS_DIR / "traceability.json"


MINIMAL_TRACE: dict[str, Any] = {
    "records": [
        {
            "id": "REQ-001",
            "ears": "When a program line number is stored, the system shall accept values 0 through 63999.",
            "source_section": "REQUIREMENTS.md#3.1",
            "design_section": "docs/BASIC_COMPATIBILITY_LIMITS.md#line-numbers",
            "implementation": "src/geoasm/program_codec.asm",
            "tests": [
                "basicv2-program-line_number-63999",
                "basicv2-program-line_number-64000-syntax_error",
            ],
            "status": "pending",
        }
    ]
}


@pytest.fixture()
def trace_file(tmp_path: Path) -> Path:
    p = tmp_path / "traceability.json"
    p.write_text(json.dumps(MINIMAL_TRACE), encoding="utf-8")
    return p


class TestGenerateRequirementsMatrix:
    """Tests for test_harness.generate_requirements_matrix."""

    def test_json_output_created(self, trace_file: Path, tmp_path: Path) -> None:
        out_json = tmp_path / "requirements_matrix.json"
        out_md = tmp_path / "requirements_matrix.md"
        test_harness.generate_requirements_matrix(
            str(trace_file), str(out_json), str(out_md)
        )
        assert out_json.exists()

    def test_md_output_created(self, trace_file: Path, tmp_path: Path) -> None:
        out_json = tmp_path / "requirements_matrix.json"
        out_md = tmp_path / "requirements_matrix.md"
        test_harness.generate_requirements_matrix(
            str(trace_file), str(out_json), str(out_md)
        )
        assert out_md.exists()

    def test_json_contains_requirement_count(
        self, trace_file: Path, tmp_path: Path
    ) -> None:
        out_json = tmp_path / "requirements_matrix.json"
        out_md = tmp_path / "requirements_matrix.md"
        test_harness.generate_requirements_matrix(
            str(trace_file), str(out_json), str(out_md)
        )
        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert data["requirements_count"] == 1

    def test_json_contains_inverse_test_index(
        self, trace_file: Path, tmp_path: Path
    ) -> None:
        out_json = tmp_path / "requirements_matrix.json"
        out_md = tmp_path / "requirements_matrix.md"
        test_harness.generate_requirements_matrix(
            str(trace_file), str(out_json), str(out_md)
        )
        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert data["tests_count"] == 2
        assert data["mapped_tests"] == [
            {
                "test": "basicv2-program-line_number-63999",
                "requirements": ["REQ-001"],
            },
            {
                "test": "basicv2-program-line_number-64000-syntax_error",
                "requirements": ["REQ-001"],
            },
        ]

    def test_json_preserves_requirement_source(
        self, trace_file: Path, tmp_path: Path
    ) -> None:
        """The generated matrix retains the normative source link."""
        out_json = tmp_path / "requirements_matrix.json"
        out_md = tmp_path / "requirements_matrix.md"
        test_harness.generate_requirements_matrix(
            str(trace_file), str(out_json), str(out_md)
        )
        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert data["mapped_requirements"][0]["source_section"] == (
            "REQUIREMENTS.md#3.1"
        )

    def test_md_contains_header(self, trace_file: Path, tmp_path: Path) -> None:
        out_json = tmp_path / "requirements_matrix.json"
        out_md = tmp_path / "requirements_matrix.md"
        test_harness.generate_requirements_matrix(
            str(trace_file), str(out_json), str(out_md)
        )
        content = out_md.read_text(encoding="utf-8")
        assert "# Requirements Traceability Matrix" in content
        assert "Source Section" in content

    def test_md_contains_requirement_id(self, trace_file: Path, tmp_path: Path) -> None:
        out_json = tmp_path / "requirements_matrix.json"
        out_md = tmp_path / "requirements_matrix.md"
        test_harness.generate_requirements_matrix(
            str(trace_file), str(out_json), str(out_md)
        )
        content = out_md.read_text(encoding="utf-8")
        assert "REQ-001" in content

    def test_md_contains_inverse_test_index(
        self, trace_file: Path, tmp_path: Path
    ) -> None:
        out_json = tmp_path / "requirements_matrix.json"
        out_md = tmp_path / "requirements_matrix.md"
        test_harness.generate_requirements_matrix(
            str(trace_file), str(out_json), str(out_md)
        )
        content = out_md.read_text(encoding="utf-8")
        assert "## Test-to-Requirement Index" in content
        assert "`basicv2-program-line_number-63999`" in content

    def test_missing_trace_file_is_silent(self, tmp_path: Path) -> None:
        """generate_requirements_matrix returns silently when trace file absent."""
        out_json = tmp_path / "requirements_matrix.json"
        out_md = tmp_path / "requirements_matrix.md"
        test_harness.generate_requirements_matrix(
            str(tmp_path / "nonexistent.json"), str(out_json), str(out_md)
        )
        # Should not raise; outputs simply not created
        assert not out_json.exists()

    def test_real_traceability_manifest(self, tmp_path: Path) -> None:
        if not TRACE_PATH.exists():
            pytest.skip("traceability.json not present; T0.2 prerequisite unmet")
        out_json = tmp_path / "requirements_matrix.json"
        out_md = tmp_path / "requirements_matrix.md"
        test_harness.generate_requirements_matrix(
            str(TRACE_PATH), str(out_json), str(out_md)
        )
        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert data["requirements_count"] >= 1


def test_collect_assembly_entries_reports_uncovered(tmp_path: Path) -> None:
    """Production and test-only callables form one unique coverage matrix."""
    production = tmp_path / "production.json"
    production.write_text(
        json.dumps(
            {
                "production_entries": [
                    {"name": "public_call", "module": "src/public.asm"}
                ]
            }
        ),
        encoding="utf-8",
    )
    test_entries = tmp_path / "test.json"
    test_entries.write_text(
        json.dumps(
            {"test_entries": [{"name": "private_call", "module": "src/private.asm"}]}
        ),
        encoding="utf-8",
    )
    matrix = test_harness.collect_assembly_entries(
        str(production), str(test_entries), {"public_call"}
    )
    assert matrix["uncovered"] == ["private_call"]


def test_replay_boundary_rejects_corruption(tmp_path: Path) -> None:
    """Boundary replay verifies the canonical serialized-state checksum."""
    state = {"phase": 3, "generation": 7}
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    boundary = tmp_path / "boundary.json"
    boundary.write_text(
        json.dumps(
            {"version": 1, "state": state, "crc32": f"{zlib.crc32(encoded):08x}"}
        ),
        encoding="utf-8",
    )
    assert test_harness.replay_boundary(str(boundary)) == state
    boundary.write_text(
        json.dumps({"version": 1, "state": state, "crc32": "00000000"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="checksum"):
        test_harness.replay_boundary(str(boundary))


def test_validate_callable_coverage_writes_honest_matrix(tmp_path: Path) -> None:
    """Coverage report counts callables and exposes every missing unit test."""
    production = tmp_path / "production.json"
    production.write_text(
        json.dumps(
            {
                "production_entries": [
                    {"name": "covered_call", "module": "src/a.asm"},
                    {"name": "missing_call", "module": "src/b.asm"},
                ]
            }
        ),
        encoding="utf-8",
    )
    test_entries = tmp_path / "test.json"
    test_entries.write_text(json.dumps({"test_entries": []}), encoding="utf-8")
    unit_dir = tmp_path / "unit"
    unit_dir.mkdir()
    (unit_dir / "test_a.py").write_text(
        'def test_a():\n    address = "covered_call"\n', encoding="utf-8"
    )
    output = tmp_path / "coverage.json"
    report = test_harness.validate_callable_coverage(
        str(production), str(test_entries), str(unit_dir), str(output)
    )
    assert report["total_routines"] == 2
    assert report["covered_routines"] == 1
    assert report["uncovered_routines"] == ["missing_call"]
    assert json.loads(output.read_text(encoding="utf-8")) == report
