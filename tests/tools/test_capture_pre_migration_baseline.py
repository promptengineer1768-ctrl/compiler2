"""Tests for pre-migration baseline capture evidence."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import capture_pre_migration_baseline as baseline


def _write_ready_workspace(root: Path) -> Path:
    """Create a minimal, internally consistent workspace and artifact set."""
    (root / "src").mkdir(parents=True)
    (root / "manifests").mkdir()
    (root / "tools").mkdir()
    (root / "docs").mkdir()
    (root / "src" / "main.asm").write_text("; source\n", encoding="utf-8")
    build = root / "build"
    build.mkdir()
    names = baseline.REQUIRED_ARTIFACTS[1:]
    for name in names:
        (build / name).write_bytes(name.encode("ascii"))
    (build / "size_report.json").write_text(
        json.dumps(
            {
                "resident_within_limit": True,
                "georam_within_limit": True,
                "compile_within_limit": True,
            }
        ),
        encoding="utf-8",
    )
    records = {
        name: {
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for name in names
        for path in [build / name]
    }
    (build / "build_manifest.json").write_text(
        json.dumps({"artifacts": records}), encoding="utf-8"
    )
    return build


def test_capture_reports_ready_consistent_artifacts(tmp_path: Path) -> None:
    """A complete matching artifact set is usable when sources predate it."""
    build = _write_ready_workspace(tmp_path)
    report = baseline.capture(tmp_path)
    assert report["status"] == "ready"
    assert report["artifact_integrity"]["mismatched"] == []
    assert report["size_report"]["status"] == "valid"
    assert report["keyword_matrix"]["status"] == "missing"
    assert report["e2e_execution"]["status"] == "not_captured"
    assert build.is_dir()


def test_capture_reports_missing_required_artifacts(tmp_path: Path) -> None:
    """Missing release artifacts cannot silently become a baseline."""
    _write_ready_workspace(tmp_path)
    (tmp_path / "build" / "compiler.d64").unlink()
    report = baseline.capture(tmp_path)
    assert report["status"] == "missing"
    assert "compiler.d64" in report["artifact_integrity"]["missing"]


def test_capture_reports_checksum_drift_as_unbuildable(tmp_path: Path) -> None:
    """A changed artifact is rejected even if every required filename exists."""
    _write_ready_workspace(tmp_path)
    (tmp_path / "build" / "compiler.bin").write_bytes(b"changed")
    report = baseline.capture(tmp_path)
    assert report["status"] == "unbuildable"
    assert "compiler.bin: size" in report["artifact_integrity"]["mismatched"]
    assert "compiler.bin: sha256" in report["artifact_integrity"]["mismatched"]


def test_capture_reports_source_newer_than_manifest_as_stale(tmp_path: Path) -> None:
    """A build older than a tracked source is not a usable migration baseline."""
    build = _write_ready_workspace(tmp_path)
    manifest = build / "build_manifest.json"
    source = tmp_path / "src" / "main.asm"
    later = manifest.stat().st_mtime_ns + 1_000_000
    os.utime(source, ns=(later, later))
    report = baseline.capture(tmp_path)
    assert report["status"] == "stale"
    assert report["source_freshness"]["status"] == "stale"
