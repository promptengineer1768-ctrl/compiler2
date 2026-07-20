"""Tests for guarded clean build-output preparation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from build_output import prepare_clean_output


def test_prepare_clean_output_removes_only_explicit_output(tmp_path: Path) -> None:
    """A clean build removes stale output while preserving source siblings."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "src.asm").write_text("source", encoding="utf-8")
    output = project / "build" / "old.bin"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"stale")

    result = prepare_clean_output(project, Path("build"))

    assert result == project / "build"
    assert not output.exists()
    assert (result / "obj").is_dir()
    assert (result / "listings").is_dir()
    assert (project / "src.asm").read_text(encoding="utf-8") == "source"


def test_prepare_clean_output_refuses_project_root(tmp_path: Path) -> None:
    """The cleanup guard cannot delete the repository root."""
    with pytest.raises(ValueError, match="project root"):
        prepare_clean_output(tmp_path, tmp_path)


def test_prepare_clean_output_refuses_outside_project(tmp_path: Path) -> None:
    """The cleanup guard cannot delete a sibling directory."""
    outside = tmp_path.parent / "outside-output"
    outside.mkdir(exist_ok=True)
    (outside / "keep").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="inside project root"):
        prepare_clean_output(tmp_path, outside)
    assert (outside / "keep").exists()
