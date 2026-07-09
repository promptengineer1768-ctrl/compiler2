"""Tests for the Phase 1 FOR/NEXT benchmark report tool."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import phase1_for_benchmark

ROOT = Path(__file__).resolve().parents[2]


def test_evaluate_measurement_requires_strictly_less_than_limit() -> None:
    """The hard acceptance target is less than 60 jiffies."""
    passing = phase1_for_benchmark.evaluate_measurement(59)
    failing = phase1_for_benchmark.evaluate_measurement(60)
    assert passing["status"] == "pass"
    assert passing["within_limit"] is True
    assert failing["status"] == "fail"
    assert failing["within_limit"] is False


def test_pending_result_is_not_a_pass() -> None:
    """An unmeasured benchmark must remain explicitly pending."""
    result = phase1_for_benchmark.evaluate_measurement(None)
    assert result["status"] == "pending"
    assert result["measured_jiffies"] is None
    assert result["within_limit"] is None
    assert "no stock-loadable compiled PRG" in result["reason"]


def test_parse_jiffies_from_screen_uses_final_integer() -> None:
    """The screen parser extracts the final printed jiffy value."""
    screen = """
        **** COMMODORE 64 BASIC V2 ****
        READY.
        RUN
        47
        READY.
    """
    assert phase1_for_benchmark.parse_jiffies_from_screen(screen) == 47


def test_parse_jiffies_from_screen_rejects_missing_count() -> None:
    """A capture without a printed integer is not a benchmark measurement."""
    with pytest.raises(ValueError, match="no printed jiffy count"):
        phase1_for_benchmark.parse_jiffies_from_screen("READY.")


def test_native_fixture_has_basic_loader_and_entry() -> None:
    """The native fixture is a stock-loadable SYS2061 PRG."""
    prg = phase1_for_benchmark.build_native_fixture_prg()
    assert prg[:2] == b"\x01\x08"
    assert prg[2:14] == bytes(
        [0x0C, 0x08, 0xEA, 0x07, 0x9E, 0x32, 0x30, 0x36, 0x31, 0x00, 0x00, 0x00]
    )
    # Native code begins at $080D with JSR RDTIM.
    assert prg[14:17] == bytes([0x20, 0xDE, 0xFF])


def test_cli_writes_pending_report_and_require_measured_fails(tmp_path: Path) -> None:
    """The CLI records pending status and fails strict measured mode."""
    output_path = tmp_path / "phase1_for_benchmark.json"
    command = [
        sys.executable,
        str(ROOT / "tools" / "phase1_for_benchmark.py"),
        "--json-out",
        str(output_path),
        "--require-measured",
    ]
    result = subprocess.run(command, cwd=ROOT, check=False)
    assert result.returncode == 1
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["status"] == "pending"
    assert data["within_limit"] is None


def test_cli_can_parse_screen_capture(tmp_path: Path) -> None:
    """A decoded VICE screen capture can become a measured report."""
    screen_path = tmp_path / "screen.txt"
    output_path = tmp_path / "phase1_for_benchmark.json"
    screen_path.write_text("RUN\n59\nREADY.\n", encoding="utf-8")
    command = [
        sys.executable,
        str(ROOT / "tools" / "phase1_for_benchmark.py"),
        "--screen-text",
        str(screen_path),
        "--json-out",
        str(output_path),
        "--require-measured",
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["status"] == "pass"
    assert data["measured_jiffies"] == 59


def test_cli_preserves_existing_measurement(tmp_path: Path) -> None:
    """A normal build refresh must not erase an existing measurement."""
    output_path = tmp_path / "phase1_for_benchmark.json"
    phase1_for_benchmark.write_result(
        output_path,
        phase1_for_benchmark.evaluate_measurement(12),
    )
    command = [
        sys.executable,
        str(ROOT / "tools" / "phase1_for_benchmark.py"),
        "--json-out",
        str(output_path),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["status"] == "pass"
    assert data["measured_jiffies"] == 12
