"""System tests for size budget validation (T10.3).

Tests verify resident and geoRAM budgets are within limits.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.system
class TestResidentBudget:
    """Resident byte budget tests."""

    def test_resident_size_report_exists(self) -> None:
        """Resident size report must exist after build."""
        path = ROOT / "build" / "size_report.json"
        if not path.exists():
            pytest.skip("build/size_report.json not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_resident_bytes_within_limit(self) -> None:
        """Resident bytes must be within budget."""
        path = ROOT / "build" / "size_report.json"
        if not path.exists():
            pytest.skip("build/size_report.json not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Check if resident bytes are within reasonable limit
        if "resident_bytes" in data:
            assert data["resident_bytes"] < 8192  # 8KB max


@pytest.mark.system
class TestGeoRamBudget:
    """geoRAM page budget tests."""

    def test_georam_pages_report_exists(self) -> None:
        """geoRAM pages report must exist after build."""
        path = ROOT / "build" / "size_report.json"
        if not path.exists():
            pytest.skip("build/size_report.json not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_georam_pages_within_limit(self) -> None:
        """geoRAM pages must be within budget."""
        path = ROOT / "build" / "size_report.json"
        if not path.exists():
            pytest.skip("build/size_report.json not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Check if geoRAM pages are within reasonable limit
        if "georam_pages" in data:
            assert data["georam_pages"] < 256  # 256 pages max (16KB)


@pytest.mark.system
class TestCompileBudget:
    """Standalone COMPILE budget tests."""

    def test_compile_bin_exists(self) -> None:
        """build/compile.bin must exist after extraction."""
        path = ROOT / "build" / "compile.bin"
        if not path.exists():
            pytest.skip("build/compile.bin not found (run extract_segments.py)")
        assert path.exists()
        assert path.stat().st_size > 0

    def test_compile_bin_within_limit(self) -> None:
        """compile.bin must be within budget."""
        path = ROOT / "build" / "compile.bin"
        if not path.exists():
            pytest.skip("build/compile.bin not found")
        # Fully rounded custom math keeps the standalone payload below 24 KiB.
        assert path.stat().st_size < 24576


@pytest.mark.system
class TestSizeHistory:
    """Commit-keyed size trend and resident placement evidence."""

    def test_size_history_tracks_current_build(self) -> None:
        """The build records resident, geoRAM, and compile sizes by commit."""
        data = json.loads((ROOT / "build" / "size_history.json").read_text())
        assert data
        assert {"commit", "resident_bytes", "georam_pages", "compile_bytes"} <= data[
            -1
        ].keys()

    def test_resident_hot_paths_have_call_graph_evidence(self) -> None:
        """Resident-placement candidates include purpose and incoming calls."""
        data = json.loads((ROOT / "build" / "size_report.json").read_text())
        assert data["resident_hot_paths"]
        assert all(
            {"name", "incoming_calls", "reason"} <= record.keys()
            for record in data["resident_hot_paths"]
        )

    def test_profile_guided_optimization_evidence_is_recorded(self) -> None:
        """T12.2 has explicit call-frequency and resident-placement evidence."""
        data = json.loads((ROOT / "build" / "size_report.json").read_text())
        profile = data["profile_guided_optimization"]
        assert profile["runtime_call_frequency"]
        assert all(
            {"name", "layer", "incoming_calls"} <= record.keys()
            for record in profile["runtime_call_frequency"]
        )
        assert isinstance(profile["moves_to_georam"], list)
        assert profile["resident_budget"]["within_limit"] is True
        benchmark = profile["phase1_for_benchmark"]
        assert benchmark["limit_jiffies"] == 60
        assert benchmark["status"] == "pass"
        assert benchmark["measured_jiffies"] < 60
        assert benchmark["within_limit"] is True
        assert benchmark["regression_gate"].endswith("test_e2e_basicv2_statements.py")
