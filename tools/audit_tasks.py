"""Conservatively audit TASKS.md completion claims against repository evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TASK_RE = re.compile(r"^(?P<prefix>- \[)(?P<status>[^]])(?P<suffix>\] )(?P<text>.+)$")
PATH_RE = re.compile(r"`([^`]+)`")
STRUCTURAL_PREFIXES = ("Create ", "Generate ")


def _artifact_paths(text: str, root: Path) -> list[Path]:
    """Return backtick-delimited repository paths named by a task."""
    paths = []
    for value in PATH_RE.findall(text):
        if "/" not in value and "\\" not in value and "." not in value:
            continue
        if value.startswith("$") or " " in value:
            continue
        candidate = root / value.rstrip("/\\")
        paths.append(candidate)
    return paths


def _path_evidence(path: Path) -> tuple[bool, str]:
    """Return whether one named artifact exists with substantive content."""
    if not path.exists():
        return False, f"missing {path}"
    if path.is_file() and path.stat().st_size == 0:
        return False, f"empty {path}"
    if path.is_dir() and not any(path.iterdir()):
        return False, f"empty directory {path}"
    return True, f"present {path}"


def classify(text: str, root: Path) -> tuple[str, list[str]]:
    """Classify one task as complete or in progress with evidence."""
    paths = _artifact_paths(text, root)
    structural = text.startswith(STRUCTURAL_PREFIXES) and bool(paths)
    if not structural:
        return "~", [
            "behavioral/semantic claim requires acceptance verification in a future goal"
        ]
    evidence = [_path_evidence(path) for path in paths]
    if all(result for result, _ in evidence):
        return "x", [message for _, message in evidence]
    return "~", [message for _, message in evidence]


def audit(tasks_path: Path, report_path: Path) -> dict[str, Any]:
    """Audit every checkbox, rewrite statuses, and save machine-readable evidence."""
    root = tasks_path.resolve().parent
    lines = tasks_path.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any]] = []
    rewritten = []
    for line_number, line in enumerate(lines, start=1):
        match = TASK_RE.match(line)
        if match is None:
            rewritten.append(line)
            continue
        status, evidence = classify(match.group("text"), root)
        rewritten.append(
            f"{match.group('prefix')}{status}{match.group('suffix')}"
            f"{match.group('text')}"
        )
        records.append(
            {
                "line": line_number,
                "task": match.group("text"),
                "previous_status": match.group("status"),
                "audited_status": status,
                "evidence": evidence,
            }
        )
    tasks_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
    report = {
        "task_count": len(records),
        "complete": sum(record["audited_status"] == "x" for record in records),
        "in_progress": sum(record["audited_status"] == "~" for record in records),
        "records": records,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    """Run the task audit."""
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks", type=Path, nargs="?", default=Path("TASKS.md"))
    parser.add_argument("--report", type=Path, default=Path("build/task_audit.json"))
    args = parser.parse_args()
    report = audit(args.tasks, args.report)
    print(
        f"Audited {report['task_count']} tasks: "
        f"{report['complete']} complete, {report['in_progress']} in progress."
    )


if __name__ == "__main__":
    main()
