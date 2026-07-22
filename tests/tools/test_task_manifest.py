"""Tests for the canonical task-manifest workflow."""

from __future__ import annotations

from pathlib import Path

from task_manifest import import_manifest, render, validate


def test_manifest_renders_legacy_markdown_and_keeps_objective_evidence(
    tmp_path: Path,
) -> None:
    """Only an existing structural artifact survives legacy-status import."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "feature.asm").write_text("; feature\n", encoding="utf-8")
    tasks = tmp_path / "TASKS.md"
    tasks.write_text(
        "### T1.1 Feature\n"
        "- [x] Create `src/feature.asm`\n"
        "- [x] Implement `feature_entry`\n",
        encoding="utf-8",
    )
    (tmp_path / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
    manifest = import_manifest([tasks], tmp_path / "missing-ledger.json")

    entries = manifest["documents"][0]["tasks"]
    assert entries[0]["status"] == "x"
    assert entries[0]["evidence"][0]["kind"] == "artifact"
    assert entries[1]["status"] == "~"
    render(manifest, tmp_path)
    assert validate(manifest, tmp_path) == []


def test_complete_task_requires_passing_machine_readable_evidence(
    tmp_path: Path,
) -> None:
    """A complete claim is rejected without current, passing proof."""
    (tmp_path / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "documents": [
            {
                "path": "TASKS.md",
                "template": [{"task_id": "TASKS:T1.1:001"}],
                "tasks": [
                    {
                        "id": "TASKS:T1.1:001",
                        "section": "T1.1",
                        "text": "Implement `cursor_blink`",
                        "status": "x",
                        "requirements": ["R9"],
                        "design_refs": ["DESIGN.md#9"],
                        "evidence": [
                            {
                                "kind": "symbol",
                                "target": "src/editor.asm:cursor_blink",
                                "status": "failing",
                                "claim": "The public entry exists.",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    assert validate(manifest, tmp_path) == [
        "TASKS:T1.1:001: complete task has failing evidence",
        "TASKS.md: generated view is stale",
    ]


def test_manifest_requires_an_owning_task_for_every_trace_requirement(
    tmp_path: Path,
) -> None:
    """Traceability requirements cannot drift away from the task plan."""
    (tmp_path / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
    (tmp_path / "manifests").mkdir()
    (tmp_path / "manifests" / "traceability.json").write_text(
        '{"records":[{"id":"R8"}]}\n', encoding="utf-8"
    )
    manifest = {
        "schema_version": 1,
        "documents": [
            {
                "path": "TASKS.md",
                "template": [{"task_id": "TASKS:T1.1:001"}],
                "tasks": [
                    {
                        "id": "TASKS:T1.1:001",
                        "section": "T1.1",
                        "text": "Plan language work",
                        "status": " ",
                        "requirements": ["R3"],
                        "design_refs": ["DESIGN.md#3"],
                        "evidence": [],
                    }
                ],
            }
        ],
    }
    render(manifest, tmp_path)
    assert validate(manifest, tmp_path) == ["R8: has no owning task"]
