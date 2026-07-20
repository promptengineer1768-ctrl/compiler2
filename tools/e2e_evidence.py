"""Preflight release artifacts and retain bounded E2E watchdog evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import validate_build


@dataclass(frozen=True)
class WatchdogResult:
    """One bounded child-process observation retained for audit."""

    command: tuple[str, ...]
    elapsed_seconds: float
    returncode: int | None
    timed_out: bool
    stdout: str
    stderr: str
    diagnostic_path: str


def release_preflight(build_dir: Path) -> list[str]:
    """Return release-artifact freshness failures before E2E starts.

    The check is read-only and delegates checksum, source-input, toolchain, and
    required-artifact validation to the build-manifest contract.  In
    particular, an old D64 must never be accepted merely because it exists.

    Args:
        build_dir: Directory containing the release build manifest and D64.

    Returns:
        Deterministic errors; an empty list means the release is eligible for
        execution (not that its behavior has passed E2E).
    """
    errors = validate_build.validate_build_manifest(
        str(build_dir / "build_manifest.json")
    )
    disk = build_dir / "compiler.d64"
    if not disk.is_file():
        errors.append(f"E2E release disk is missing: {disk}")
    elif disk.stat().st_size == 0:
        errors.append(f"E2E release disk is empty: {disk}")
    return errors


def run_with_watchdog(
    command: Sequence[str],
    *,
    timeout_seconds: float,
    diagnostic_dir: Path,
    label: str = "e2e",
    cwd: Path | None = None,
) -> WatchdogResult:
    """Run an E2E command with a hard timeout and durable diagnostics.

    Args:
        command: Direct executable argv; shell evaluation is never used.
        timeout_seconds: Positive wall-clock timeout.
        diagnostic_dir: Destination under ``debug/`` for the JSON observation.
        label: Stable diagnostic filename component.
        cwd: Optional child working directory.

    Returns:
        Captured process result. Timeout is represented in the result rather
        than silently converted to a passing/skipped execution.
    """
    if not command:
        raise ValueError("watchdog command must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("watchdog timeout_seconds must be positive")
    if not label.replace("_", "").replace("-", "").isalnum():
        raise ValueError("watchdog label must contain only letters, digits, '-' or '_'")

    started = time.monotonic()
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()
    elapsed = time.monotonic() - started

    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    destination = diagnostic_dir / f"{label}-watchdog.json"
    result = WatchdogResult(
        command=tuple(command),
        elapsed_seconds=elapsed,
        returncode=None if timed_out else process.returncode,
        timed_out=timed_out,
        stdout=stdout,
        stderr=stderr,
        diagnostic_path=str(destination),
    )
    destination.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Run release preflight or a bounded external E2E command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--debug-dir", type=Path, default=Path("debug") / "e2e")
    parser.add_argument("--label", default="e2e")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    errors = release_preflight(args.build_dir)
    if args.preflight or not args.command:
        for error in errors:
            print(f"Error: {error}")
        return 0 if not errors else 1
    if errors:
        for error in errors:
            print(f"Error: {error}")
        return 1
    if args.timeout is None:
        parser.error("--timeout is required when running a command")
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    result = run_with_watchdog(
        command,
        timeout_seconds=args.timeout,
        diagnostic_dir=args.debug_dir,
        label=args.label,
    )
    print(result.diagnostic_path)
    return 1 if result.timed_out or result.returncode != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
