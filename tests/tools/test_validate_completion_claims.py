"""Tests for the completion-claim reconciliation release gate."""

from __future__ import annotations

import json
import re
from pathlib import Path

from validate_completion_claims import validate, validate_ledger

ROOT = Path(__file__).resolve().parents[2]


def _ledger(status: str, evidence_status: str) -> dict[str, object]:
    """Return a minimal valid ledger for one claim."""
    return {
        "schema_version": 1,
        "claims": [
            {
                "id": "CCL-TEST",
                "scope": "T0.1",
                "claim": "test claim",
                "status": status,
                "requirements": ["R1"],
                "evidence": [
                    {
                        "kind": "build",
                        "path": "build/compiler.bin",
                        "status": evidence_status,
                        "reason": "test evidence",
                    }
                ],
                "affected_task_sections": ["T0.1"],
            }
        ],
    }


def test_complete_claim_rejects_stale_evidence() -> None:
    """A claimed completion cannot coexist with stale production evidence."""
    assert validate_ledger(_ledger("complete", "stale")) == [
        "CCL-TEST: complete claim has unusable evidence"
    ]


def test_invalidated_claim_requires_failed_evidence() -> None:
    """Invalidation records must preserve the concrete failure evidence."""
    assert validate_ledger(_ledger("invalidated", "current")) == [
        "CCL-TEST: invalidated claim lacks failed evidence"
    ]


def test_invalidated_claim_rejects_passing_traceability(tmp_path: Path) -> None:
    """Traceability cannot claim passing while its audit claim is invalidated."""
    ledger = tmp_path / "ledger.json"
    traceability = tmp_path / "traceability.json"
    ledger.write_text(json.dumps(_ledger("invalidated", "failing")), encoding="utf-8")
    traceability.write_text(
        json.dumps({"records": [{"id": "R1", "status": "passing"}]}),
        encoding="utf-8",
    )
    assert validate(ledger, traceability) == [
        "CCL-TEST: traceability R1 is passing despite invalidated evidence"
    ]


def test_audit_targets_are_specific_in_progress_task_markers() -> None:
    """Every ledger-targeted behavioral claim has a reviewed ``[~]`` marker."""
    ledger = json.loads(
        (ROOT / "manifests" / "completion_claim_ledger.json").read_text(
            encoding="utf-8"
        )
    )
    section = ""
    statuses: dict[tuple[str, str], str] = {}
    for line in (ROOT / "TASKS.md").read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^### (T\d+\.\d+)", line)
        if heading:
            section = heading.group(1)
        task = re.match(r"^- \[([^]])\] (.+)$", line)
        if task:
            statuses[(section, task.group(2))] = task.group(1)
    for claim in ledger["claims"]:
        for item in claim.get("invalidated_checklist_items", []):
            assert statuses[(item["section"], item["task"])] == "~"
