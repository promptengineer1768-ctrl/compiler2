"""Project-owned adapter for the pinned Backend build and release graph."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
STEPS = (
    "validate_manifests",
    "build_release",
    "test_system",
    "prepare_distribution",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the adapter command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="show the ordered build graph")
    plan.add_argument("target", choices=("distribution",))
    run = subparsers.add_parser("run", help="execute the ordered build graph")
    run.add_argument("target", choices=("distribution",))
    documentation = subparsers.add_parser(
        "documentation", help="render or check every declared generated document"
    )
    documentation.add_argument("--check", action="store_true")
    distribution = subparsers.add_parser(
        "distribution", help="build the declared end-user distribution"
    )
    distribution.add_argument("--check-reproducible", action="store_true")
    return parser


def distribution_plan() -> dict[str, object]:
    """Return the canonical distribution dependency graph."""
    return {"target": "distribution", "steps": list(STEPS)}


def _run(command: Sequence[str]) -> None:
    """Run one production command and propagate failures."""
    subprocess.run(command, cwd=ROOT, check=True, shell=False)


def run_distribution() -> None:
    """Execute validation, release build, system tests, and packaging in order."""
    _run(("pwsh", "-File", "build.ps1", "-Validate", "-Python", sys.executable))
    _run(("pwsh", "-File", "build.ps1", "-Python", sys.executable))
    _run((sys.executable, "-m", "pytest", "tests/system", "-v"))
    _run(
        (
            sys.executable,
            "-m",
            "backend_framework.cli",
            "package-distribution",
            "manifests/backend/distribution-profile.json",
            "--root",
            str(ROOT),
        )
    )


def run_documentation(*, check: bool) -> None:
    """Render or check every document declared by the Backend profile."""
    profile = ROOT / "manifests/backend/documentation-profile.json"
    contents = json.loads(profile.read_text("utf-8"))
    for document in contents["documents"]:
        command = [
            sys.executable,
            "-m",
            "backend_framework.cli",
            "render-docs",
            str(profile),
            str(document["id"]),
            "--root",
            str(ROOT),
        ]
        if check:
            command.append("--check")
        _run(command)


def build_distribution(*, check_reproducible: bool) -> None:
    """Build the declared distribution and optionally verify reproducibility."""
    profile = "manifests/backend/distribution-profile.json"
    command = (
        sys.executable,
        "-m",
        "backend_framework.cli",
        "package-distribution",
        profile,
        "--root",
        str(ROOT),
    )
    _run(command)
    if check_reproducible:
        archive = ROOT / "build/distribution/compiler2/compiler2-readiness.zip"
        first = archive.read_bytes()
        _run(command)
        if archive.read_bytes() != first:
            raise RuntimeError("distribution archive is not byte-for-byte reproducible")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Backend adoption adapter."""
    args = build_parser().parse_args(argv)
    if args.command == "plan":
        print(json.dumps(distribution_plan()))
    elif args.command == "run":
        run_distribution()
    elif args.command == "documentation":
        run_documentation(check=args.check)
    else:
        build_distribution(check_reproducible=args.check_reproducible)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
