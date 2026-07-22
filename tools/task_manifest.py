"""Generate task checklists from, and validate them against, a JSON manifest.

The manifest owns every rendered checkbox, its status, and the evidence needed
to support a completion claim.  Markdown is deliberately a generated view: it
remains pleasant to read, but must never be edited to change task state.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
from pathlib import Path
from typing import Any, Sequence

TASK_RE = re.compile(r"^(?P<indent>\s*)- \[(?P<status>[ x~!\-])\] (?P<text>.+)$")
HEADING_RE = re.compile(
    r"^### (?P<section>T\d+(?:\.\d+)?|RT\d+(?:\.\d+)?|R\d+(?:\.\d+)?)\b"
)
PATH_RE = re.compile(r"`([^`]+)`")
VALID_STATUSES = {" ", "x", "~", "!", "-"}
PASSING_EVIDENCE = {"passing", "present", "complete"}
FAILING_EVIDENCE = {"failing", "missing", "stale", "skipped", "invalidated"}


def _task_id(document: str, section: str, number: int) -> str:
    """Return a stable task identifier for a document checkbox."""
    return f"{document.removesuffix('.md')}:{section or 'preamble'}:{number:03d}"


def _legacy_evidence(text: str, root: Path) -> list[dict[str, str]]:
    """Recover only objective legacy artifact evidence from a task sentence."""
    if not text.startswith(("Create ", "Generate ")):
        return []
    paths = [
        value.rstrip("/\\")
        for value in PATH_RE.findall(text)
        if ("/" in value or "\\" in value or "." in value)
        and " " not in value
        and not value.startswith("$")
    ]
    if not paths:
        return []
    evidence = []
    for value in paths:
        candidate = root / value
        if not candidate.exists() or (
            candidate.is_file() and not candidate.stat().st_size
        ):
            return []
        evidence.append(
            {
                "kind": "artifact",
                "target": value,
                "status": "present",
                "claim": f"Required artifact `{value}` exists and is nonempty.",
            }
        )
    return evidence


def _task_trace(section: str, document: str) -> tuple[list[str], list[str]]:
    """Return conservative requirement and design anchors for one task section."""
    if document == "REU_TASKS.md" or section.startswith("RT"):
        return ["RREU-*", "R8*", "R13*", "R14"], ["REU_DESIGN.md", "DESIGN.md#8"]
    phase = section.split(".", maxsplit=1)[0]
    mapping = {
        "T0": (["R12.1", "R14"], ["DESIGN.md#13", "DESIGN.md#15"]),
        "T1": (["R3*", "R13*", "R14"], ["DESIGN.md#3", "DESIGN.md#14", "DESIGN.md#15"]),
        "T2": (["R8*", "R9", "R10"], ["DESIGN.md#8", "DESIGN.md#9", "DESIGN.md#10"]),
        "T3": (["R7*", "R8*"], ["DESIGN.md#7", "DESIGN.md#8"]),
        "T4": (["R4", "R5"], ["DESIGN.md#4", "DESIGN.md#5"]),
        "T5": (["R6*", "R7*"], ["DESIGN.md#6", "DESIGN.md#7"]),
        "T6": (["R3*", "R6*", "R12"], ["DESIGN.md#3", "DESIGN.md#6", "DESIGN.md#12"]),
        "T7": (["R6*", "R11*"], ["DESIGN.md#6", "DESIGN.md#11"]),
        "T8": (["R4", "R9", "R10"], ["DESIGN.md#4", "DESIGN.md#9", "DESIGN.md#10"]),
        "T9": (
            ["R2*", "R8*", "RREU-*"],
            ["DESIGN.md#1", "DESIGN.md#8", "REU_DESIGN.md#8"],
        ),
        "T10": (
            ["R7*", "R12.1", "R13*"],
            ["DESIGN.md#7", "DESIGN.md#13", "DESIGN.md#14"],
        ),
        "T11": (["R3*", "R13*"], ["DESIGN.md#3", "DESIGN.md#14"]),
        "T12": (["R7*", "R11*"], ["DESIGN.md#7", "DESIGN.md#11"]),
        "T13": (["R13*"], ["DESIGN.md#14"]),
        "T14": (
            [
                "R1",
                "R2*",
                "R3*",
                "R6*",
                "R7*",
                "R8*",
                "R9",
                "R10",
                "R11*",
                "R12*",
                "R13*",
                "R14",
                "RREU-*",
            ],
            ["DESIGN.md#8", "DESIGN.md#15", "REU_DESIGN.md"],
        ),
    }
    return mapping.get(phase, (["R14"], ["DESIGN.md#15"]))


def import_document(path: Path, invalidated: set[tuple[str, str]]) -> dict[str, Any]:
    """Import one Markdown task document into a lossless render template."""
    section = ""
    task_number = 0
    template: list[dict[str, str]] = []
    tasks: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            section = heading.group("section")
        match = TASK_RE.match(line)
        if match is None:
            template.append({"text": line})
            continue
        task_number += 1
        task_id = _task_id(path.name, section, task_number)
        template.append({"task_id": task_id})
        text = match.group("text")
        evidence = _legacy_evidence(text, path.parent)
        status = match.group("status")
        # Legacy checkmarks are not proof.  Retain only reproducible structural
        # claims; every other old completion waits for explicit evidence.
        if status == "x" and not evidence:
            status = "~"
        if (section, text) in invalidated:
            status = "~"
            evidence.append(
                {
                    "kind": "claim_ledger",
                    "target": "manifests/completion_claim_ledger.json",
                    "status": "invalidated",
                    "claim": "The conformance ledger explicitly invalidates this claim.",
                }
            )
        requirements, design_refs = _task_trace(section, path.name)
        tasks.append(
            {
                "id": task_id,
                "section": section or None,
                "text": text,
                "status": status,
                "requirements": requirements,
                "design_refs": design_refs,
                "evidence": evidence,
            }
        )
    return {"path": path.name, "template": template, "tasks": tasks}


def import_manifest(paths: Sequence[Path], ledger_path: Path) -> dict[str, Any]:
    """Build the initial canonical manifest from legacy Markdown task lists."""
    invalidated: set[tuple[str, str]] = set()
    if ledger_path.exists():
        for claim in json.loads(ledger_path.read_text(encoding="utf-8")).get(
            "claims", []
        ):
            for item in claim.get("invalidated_checklist_items", []):
                invalidated.add((item["section"], item["task"]))
    documents = [import_document(path, invalidated) for path in paths]
    return {
        "schema_version": 1,
        "purpose": "Canonical task state, evidence, and Markdown render templates.",
        "status_legend": {
            " ": "not_started",
            "~": "in_progress",
            "x": "complete",
            "-": "blocked",
            "!": "skipped",
        },
        "documents": documents,
    }


def load_manifest(path: Path) -> dict[str, Any]:
    """Load a task manifest and require a JSON object."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("task manifest must contain a JSON object")
    return data


def _render_document(document: dict[str, Any]) -> str:
    """Render one document from its canonical template and tasks."""
    tasks = {task["id"]: task for task in document["tasks"]}
    lines: list[str] = []
    for item in document["template"]:
        if "text" in item:
            lines.append(item["text"])
            continue
        task = tasks[item["task_id"]]
        lines.append(f"- [{task['status']}] {task['text']}")
    return "\n".join(lines) + "\n"


def render(manifest: dict[str, Any], root: Path) -> None:
    """Write each user-readable task document from the manifest."""
    for document in manifest["documents"]:
        (root / document["path"]).write_text(
            _render_document(document), encoding="utf-8"
        )


def validate(manifest: dict[str, Any], root: Path) -> list[str]:
    """Return schema, evidence, and rendered-view consistency errors."""
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("task manifest schema_version must be 1")
    seen: set[str] = set()
    requirement_patterns: list[str] = []
    for document in manifest.get("documents", []):
        if not isinstance(document.get("path"), str):
            errors.append("task document is missing path")
            continue
        tasks = document.get("tasks")
        if not isinstance(tasks, list):
            errors.append(f"{document['path']}: tasks must be a list")
            continue
        task_ids = set()
        for task in tasks:
            task_id = task.get("id")
            if not isinstance(task_id, str) or not task_id:
                errors.append(f"{document['path']}: task missing id")
                continue
            if task_id in seen:
                errors.append(f"duplicate task id {task_id}")
            seen.add(task_id)
            task_ids.add(task_id)
            if task.get("status") not in VALID_STATUSES:
                errors.append(f"{task_id}: invalid status")
            for field in ("requirements", "design_refs"):
                value = task.get(field)
                if not isinstance(value, list) or not all(
                    isinstance(item, str) and item for item in value
                ):
                    errors.append(f"{task_id}: missing {field}")
            requirement_patterns.extend(task.get("requirements", []))
            for reference in task.get("design_refs", []):
                design_path = root / reference.split("#", maxsplit=1)[0]
                if not design_path.is_file():
                    errors.append(f"{task_id}: missing design reference {reference}")
            evidence = task.get("evidence")
            if not isinstance(evidence, list):
                errors.append(f"{task_id}: evidence must be a list")
                continue
            statuses = set()
            for record in evidence:
                if not isinstance(record, dict) or not all(
                    isinstance(record.get(field), str) and record[field]
                    for field in ("kind", "target", "status", "claim")
                ):
                    errors.append(f"{task_id}: invalid evidence record")
                    continue
                statuses.add(record["status"])
            if task.get("status") == "x" and not evidence:
                errors.append(f"{task_id}: complete task has no evidence")
            if task.get("status") == "x" and statuses & FAILING_EVIDENCE:
                errors.append(f"{task_id}: complete task has failing evidence")
            if (
                task.get("status") == "x"
                and not (statuses & PASSING_EVIDENCE)
                and not (statuses & FAILING_EVIDENCE)
            ):
                errors.append(f"{task_id}: complete task lacks passing evidence")
        template_ids = {
            item["task_id"]
            for item in document.get("template", [])
            if "task_id" in item
        }
        if template_ids != task_ids:
            errors.append(f"{document['path']}: template/task id mismatch")
        rendered = _render_document(document)
        path = root / document["path"]
        if not path.exists() or path.read_text(encoding="utf-8") != rendered:
            errors.append(f"{document['path']}: generated view is stale")
    trace_path = root / "manifests" / "traceability.json"
    if trace_path.is_file():
        trace_data = json.loads(trace_path.read_text(encoding="utf-8"))
        trace_ids: set[str] = set()
        for record in trace_data.get("records", []):
            if isinstance(record, dict) and isinstance(record.get("id"), str):
                trace_ids.add(record["id"])
        for requirement_id in sorted(trace_ids):
            if not any(
                fnmatch.fnmatchcase(requirement_id, pattern)
                for pattern in requirement_patterns
            ):
                errors.append(f"{requirement_id}: has no owning task")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    """Import, render, or validate the canonical task manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("import", "render", "validate"))
    parser.add_argument("--manifest", type=Path, default=Path("manifests/tasks.json"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--documents", nargs="*", default=["TASKS.md", "REU_TASKS.md"])
    parser.add_argument(
        "--ledger", type=Path, default=Path("manifests/completion_claim_ledger.json")
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "import":
        manifest = import_manifest(
            [root / value for value in args.documents], root / args.ledger
        )
        args.manifest.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return 0
    manifest = load_manifest(args.manifest)
    if args.command == "render":
        render(manifest, root)
        return 0
    errors = validate(manifest, root)
    if errors:
        print("Task-manifest validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Task-manifest validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
