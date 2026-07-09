"""Tests for generated loader and size reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import generate_build_reports


def test_parse_segments_reads_ld65_table(tmp_path: Path) -> None:
    """The parser extracts exact hexadecimal segment bounds."""
    map_path = tmp_path / "compiler.map"
    map_path.write_text(
        "Segment list:\n-------------\nName Start End Size Align\n"
        "LOADER 000801 0008FF 0000FF 00001\n\nExports list by name:\n",
        encoding="ascii",
    )
    assert generate_build_reports.parse_segments(map_path) == [
        {"name": "LOADER", "start": 0x0801, "end": 0x08FF, "size": 0xFF, "align": 1}
    ]


def test_current_reports_have_explicit_passing_budgets() -> None:
    """Current linked artifacts generate complete, passing budget records."""
    root = Path(__file__).resolve().parents[2]
    loader, sizes = generate_build_reports.generate(root / "build")
    assert loader["load_address"] == 0x0801
    assert loader["entry_address"] == 0x080D
    assert sizes["resident_within_limit"] is True
    assert sizes["georam_within_limit"] is True
    assert sizes["compile_within_limit"] is True
    assert isinstance(sizes["resident_delta_bytes"], int)
    assert isinstance(sizes["georam_page_delta"], int)
    assert sizes["resident_hot_paths"]
    benchmark = sizes["profile_guided_optimization"]["phase1_for_benchmark"]
    assert benchmark["name"] == "phase1-compiled-for-next"
    assert benchmark["limit_jiffies"] == 60
    assert benchmark["status"] in {"pending", "pass", "fail"}
    assert benchmark["within_limit"] is not True or benchmark["measured_jiffies"] < 60
    assert json.dumps(loader)
