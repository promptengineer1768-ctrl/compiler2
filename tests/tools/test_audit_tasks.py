"""Tests for conservative TASKS.md completion auditing."""

from __future__ import annotations

import json
from pathlib import Path

from audit_tasks import audit, classify


def test_structural_task_requires_nonempty_named_artifact(tmp_path: Path) -> None:
    """Only an existing nonempty artifact proves a structural task complete."""
    artifact = tmp_path / "src" / "feature.asm"
    artifact.parent.mkdir()
    artifact.write_text("; implementation\n")
    assert classify("Create `src/feature.asm`", tmp_path)[0] == "x"
    assert classify("Create `src/missing.asm`", tmp_path)[0] == "~"


def test_behavioral_task_is_conservatively_in_progress(tmp_path: Path) -> None:
    """Symbol or test existence alone cannot prove behavioral completion."""
    assert classify("Implement `editor_submit_line`", tmp_path)[0] == "~"
    assert classify("Verify all functional tests pass", tmp_path)[0] == "~"


def test_audit_rewrites_and_reports_every_checkbox(tmp_path: Path) -> None:
    """Every checkbox receives one evidence record and an audited status."""
    artifact = tmp_path / "doc.md"
    artifact.write_text("content\n")
    tasks = tmp_path / "TASKS.md"
    tasks.write_text(
        "- [x] Create `doc.md`\n"
        "- [x] Implement the editor\n"
        "- [ ] Verify tests pass\n"
    )
    report_path = tmp_path / "audit.json"

    report = audit(tasks, report_path)

    assert report["task_count"] == 3
    assert report["complete"] == 1
    assert report["in_progress"] == 2
    assert tasks.read_text().splitlines() == [
        "- [x] Create `doc.md`",
        "- [~] Implement the editor",
        "- [~] Verify tests pass",
    ]
    saved = json.loads(report_path.read_text())
    assert len(saved["records"]) == 3
