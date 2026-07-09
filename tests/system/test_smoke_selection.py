"""System contracts for the stable smoke-test selection."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _collect() -> tuple[str, ...]:
    """Collect smoke node IDs in deterministic pytest order."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "--collect-only",
            "-q",
            "-m",
            "smoke",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(
        line
        for line in result.stdout.splitlines()
        if line.startswith("tests/") or line.startswith("tests\\")
    )


@pytest.mark.system
@pytest.mark.static
def test_smoke_collection_is_stable_and_covers_critical_layers() -> None:
    """Repeated collection is stable and spans every required test layer."""
    first = _collect()
    second = _collect()
    assert first == second
    assert first
    required = ("unit", "integration", "functional", "system", "e2e", "hardware")
    assert all(
        any(f"tests/{category}/" in node.replace("\\", "/") for node in first)
        for category in required
    )


@pytest.mark.system
def test_smoke_selection_completes_under_thirty_two_minutes() -> None:
    """Smoke includes the real IEC loader path while remaining bounded."""
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-m", "smoke"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=1920,
    )
    elapsed = time.perf_counter() - started
    assert result.returncode == 0, result.stdout + result.stderr
    assert elapsed < 1920
