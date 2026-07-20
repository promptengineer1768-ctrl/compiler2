"""Tests for E2E preflight and watchdog evidence tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import e2e_evidence


def test_preflight_rejects_missing_release_artifacts(tmp_path: Path) -> None:
    """An E2E attempt cannot start without a manifest-backed release disk."""
    errors = e2e_evidence.release_preflight(tmp_path)
    assert any("build manifest is missing" in error for error in errors)
    assert any("release disk is missing" in error for error in errors)


def test_watchdog_writes_output_for_completed_command(tmp_path: Path) -> None:
    """Successful host commands retain stdout and return status in debug data."""
    result = e2e_evidence.run_with_watchdog(
        [sys.executable, "-c", "print('ready')"],
        timeout_seconds=5,
        diagnostic_dir=tmp_path,
        label="completed",
    )
    report = json.loads((tmp_path / "completed-watchdog.json").read_text())
    assert result.timed_out is False
    assert result.returncode == 0
    assert report["stdout"].strip() == "ready"


def test_watchdog_kills_timeout_and_retains_diagnostics(tmp_path: Path) -> None:
    """A hung command is killed and recorded as a failure, never a skip."""
    result = e2e_evidence.run_with_watchdog(
        [sys.executable, "-c", "import time; time.sleep(3)"],
        timeout_seconds=0.05,
        diagnostic_dir=tmp_path,
        label="timeout",
    )
    report = json.loads((tmp_path / "timeout-watchdog.json").read_text())
    assert result.timed_out is True
    assert result.returncode is None
    assert report["timed_out"] is True


def test_watchdog_rejects_unsafe_label(tmp_path: Path) -> None:
    """Diagnostic filenames cannot escape their designated debug directory."""
    with pytest.raises(ValueError, match="label"):
        e2e_evidence.run_with_watchdog(
            [sys.executable, "-c", "pass"],
            timeout_seconds=1,
            diagnostic_dir=tmp_path,
            label="../escape",
        )
