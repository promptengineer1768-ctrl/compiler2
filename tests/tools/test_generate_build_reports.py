"""Tests for generated loader and size reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import generate_build_reports
import package_d64


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


def _write_minimal_build(build_dir: Path, *, georam_payload: int = 65536) -> None:
    """Create the minimum artifacts generate() needs."""
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "compiler.map").write_text(
        "Segment list:\n-------------\nName Start End Size Align\n"
        "LOADER 000801 0008FF 0000FF 00001\n"
        "RESIDENT 000900 0009FF 000100 00001\n\nExports list by name:\n",
        encoding="ascii",
    )
    (build_dir / "routine_directory.json").write_text(
        json.dumps(
            {
                "routines": {
                    "sample": {
                        "layer": "georam",
                        "block": 0,
                        "page": 1,
                        "offset": 0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (build_dir / "compile.bin").write_bytes(b"\x00" * 64)
    (build_dir / "basicv3.prg").write_bytes(b"\x01\x08" + b"\x00" * 14)
    (build_dir / "georam.bin").write_bytes(b"\x00\xde" + b"\x00" * georam_payload)
    package_d64.build_reu_patch(build_dir / "georam.bin", build_dir / "reu.bin")
    (build_dir / "compiler.d64").write_bytes(b"\x00" * 16)
    # routines.json is read from repo manifests; no need to stub.


def test_generate_reports_georam_budget_and_reu_artifact(tmp_path: Path) -> None:
    """Size report carries 512 KiB gates; loader lists reu.bin."""
    root = Path(__file__).resolve().parents[2]
    # generate() loads manifests/routines.json from build_dir.parent.
    build_dir = tmp_path / "build"
    # Point parent at real repo by using a nested path under repo? Simpler:
    # monkeypatch by writing into real structure is avoided — copy needed files.
    # generate uses build_dir.parent / "manifests" / "routines.json"
    # so build_dir must be under a tree that has manifests.
    build_dir = root / "build"
    # Use an isolated tmp tree with a manifests symlink/copy.
    workspace = tmp_path / "ws"
    (workspace / "manifests").mkdir(parents=True)
    routines = json.loads((root / "manifests" / "routines.json").read_text())
    (workspace / "manifests" / "routines.json").write_text(
        json.dumps(routines), encoding="utf-8"
    )
    build_dir = workspace / "build"
    _write_minimal_build(build_dir)

    loader, sizes = generate_build_reports.generate(build_dir)

    assert loader["load_address"] == 0x0801
    assert loader["entry_address"] == 0x080D
    assert "reu.bin" in loader["artifacts"]
    assert "georam.bin" in loader["artifacts"]
    assert sizes["georam_byte_limit"] == 512 * 1024
    assert sizes["georam_page_limit"] == 2048
    assert sizes["georam_bytes"] == 65536
    assert sizes["georam_pages"] >= 256
    assert sizes["georam_within_limit"] is True
    assert sizes["resident_within_limit"] is True
    assert sizes["compile_within_limit"] is True
    assert loader.get("reu_patch", {}).get("has_georam_capacity_field") is False


def test_generate_marks_oversize_georam_out_of_budget(tmp_path: Path) -> None:
    """An image over 512 KiB sets georam_within_limit false."""
    root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "ws"
    (workspace / "manifests").mkdir(parents=True)
    (workspace / "manifests" / "routines.json").write_text(
        (root / "manifests" / "routines.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    build_dir = workspace / "build"
    _write_minimal_build(build_dir, georam_payload=512 * 1024 + 256)

    _, sizes = generate_build_reports.generate(build_dir)

    assert sizes["georam_bytes"] == 512 * 1024 + 256
    assert sizes["georam_within_limit"] is False
    assert sizes["georam_pages"] > 2048


def test_current_reports_have_explicit_passing_budgets() -> None:
    """Current linked artifacts generate complete, passing budget records."""
    root = Path(__file__).resolve().parents[2]
    build_dir = root / "build"
    if not (build_dir / "compiler.map").exists():
        pytest.skip("build/ artifacts not present; run build.ps1 first")
    loader, sizes = generate_build_reports.generate(build_dir)
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
