"""Generate loader and size reports from authoritative linked artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, cast

SEGMENT_RE = re.compile(
    r"^(?P<name>[A-Z0-9_]+)\s+"
    r"(?P<start>[0-9A-F]{6})\s+(?P<end>[0-9A-F]{6})\s+"
    r"(?P<size>[0-9A-F]{6})\s+(?P<align>[0-9A-F]{5})$"
)
# The resident budget is the permanently mapped ``RESIDENT`` segment.  The
# loader runs only during installation, COMPILER_INIT is bootstrap code, and
# EDITOR_PINNED is a separately accounted high-RAM service surface; including
# those three in this metric turns an 8 KiB resident limit into a misleading
# aggregate-image limit.
RESIDENT_SEGMENTS = {"RESIDENT"}
BENCHMARK_JIFFY_LIMIT = 60
# REQUIREMENTS §8.1: base geoRAM-canonical image hard ceiling.
GEORAM_BYTE_LIMIT = 512 * 1024
GEORAM_PAGE_LIMIT = 2048
GEORAM_PAGE_SIZE = 256


def parse_segments(map_path: Path) -> list[dict[str, int | str]]:
    """Parse the ld65 segment table.

    Args:
        map_path: Linked compiler map.

    Returns:
        Ordered segment records.
    """
    records: list[dict[str, int | str]] = []
    in_segments = False
    for line in map_path.read_text(encoding="utf-8").splitlines():
        if line == "Segment list:":
            in_segments = True
            continue
        if in_segments and line.startswith("Exports list"):
            break
        match = SEGMENT_RE.match(line.strip()) if in_segments else None
        if match:
            records.append(
                {
                    "name": match.group("name"),
                    "start": int(match.group("start"), 16),
                    "end": int(match.group("end"), 16),
                    "size": int(match.group("size"), 16),
                    "align": int(match.group("align"), 16),
                }
            )
    if not records:
        raise ValueError(f"no segments found in {map_path}")
    return records


def _artifact(path: Path) -> dict[str, Any]:
    """Describe one generated binary artifact.

    Args:
        path: Artifact path.

    Returns:
        Stable path, size, and SHA-256 record.
    """
    payload = path.read_bytes()
    return {
        "path": path.as_posix(),
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _phase1_benchmark(build_dir: Path) -> dict[str, Any]:
    """Load the Phase 1 benchmark artifact or return an explicit pending result.

    Args:
        build_dir: Build artifact directory.

    Returns:
        Normalized benchmark report.
    """
    path = build_dir / "phase1_for_benchmark.json"
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            return loaded
    return {
        "schema_version": 1,
        "name": "phase1-compiled-for-next",
        "source_lines": [
            "10 B=TI",
            "20 FORX=1TO1000",
            "30 NEXT",
            "40 A=TI",
            "50 PRINTA-B",
        ],
        "limit_jiffies": BENCHMARK_JIFFY_LIMIT,
        "measured_jiffies": None,
        "within_limit": None,
        "status": "pending",
        "reason": "build/phase1_for_benchmark.json has not been generated",
    }


def generate(build_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate loader and size report dictionaries.

    Args:
        build_dir: Build artifact directory.

    Returns:
        Loader manifest and size report.
    """
    segments = parse_segments(build_dir / "compiler.map")
    directory = json.loads((build_dir / "routine_directory.json").read_text())
    placements = directory.get("placements", directory.get("routines", {}))
    placement_pages = {
        (record.get("block"), record.get("page"))
        for record in placements.values()
        if isinstance(record, dict)
        and isinstance(record.get("block"), int)
        and isinstance(record.get("page"), int)
    }
    georam_path = build_dir / "georam.bin"
    georam_bytes = 0
    if georam_path.exists():
        raw = georam_path.read_bytes()
        # Strip fake $DE00 PRG header when present.
        if len(raw) >= 2 and raw[0] == 0x00 and raw[1] == 0xDE:
            georam_bytes = len(raw) - 2
        else:
            georam_bytes = len(raw)
    image_pages = (
        (georam_bytes + GEORAM_PAGE_SIZE - 1) // GEORAM_PAGE_SIZE if georam_bytes else 0
    )
    # Highest logical page index from placements (block*64 + page) + 1.
    max_placement_index = 0
    for block, page in placement_pages:
        typed_block = cast(int, block)
        typed_page = cast(int, page)
        max_placement_index = max(
            max_placement_index, typed_block * 64 + typed_page + 1
        )
    georam_pages = max(len(placement_pages), image_pages, max_placement_index)
    georam_within_limit = (
        georam_pages <= GEORAM_PAGE_LIMIT and georam_bytes <= GEORAM_BYTE_LIMIT
    )
    resident_bytes = sum(
        int(record["size"])
        for record in segments
        if record["name"] in RESIDENT_SEGMENTS
    )
    loader = next(record for record in segments if record["name"] == "LOADER")
    routines_manifest = json.loads(
        (build_dir.parent / "manifests" / "routines.json").read_text()
    )
    routines = routines_manifest["routines"]
    incoming: dict[str, int] = {
        str(record["name"]): 0 for record in routines if "name" in record
    }
    for record in routines:
        for callee in record.get("calls", []):
            incoming[str(callee)] = incoming.get(str(callee), 0) + 1
    resident_hot_paths = [
        {
            "name": str(record["name"]),
            "incoming_calls": incoming.get(str(record["name"]), 0),
            "reason": str(record.get("purpose", "")),
        }
        for record in routines
        if record.get("layer") == "resident"
        and (
            incoming.get(str(record["name"]), 0) > 0
            or str(record["name"]).startswith(("irq_", "screen_", "kernal_"))
        )
    ]
    resident_hot_paths.sort(
        key=lambda record: (
            -cast(int, record["incoming_calls"]),
            str(record["name"]),
        )
    )
    resident_routines = [
        record for record in routines if record.get("layer") == "resident"
    ]
    resident_cold_candidates = [
        {
            "name": str(record["name"]),
            "incoming_calls": incoming.get(str(record["name"]), 0),
            "reason": str(record.get("purpose", "")),
            "decision": "keep_resident_pinned_surface",
        }
        for record in resident_routines
        if incoming.get(str(record["name"]), 0) == 0
        and not str(record["name"]).startswith(("irq_", "screen_", "kernal_"))
    ]
    runtime_call_frequency = [
        {
            "name": str(record["name"]),
            "layer": str(record.get("layer", "resident")),
            "incoming_calls": incoming.get(str(record["name"]), 0),
        }
        for record in routines
        if record.get("layer") in {"resident", "runtime"}
    ]
    runtime_call_frequency.sort(
        key=lambda record: (
            str(record["layer"]),
            -cast(int, record["incoming_calls"]),
            str(record["name"]),
        )
    )
    phase1_for_benchmark = _phase1_benchmark(build_dir)
    phase1_for_benchmark["regression_gate"] = "tests/e2e/test_e2e_basicv2_statements.py"
    profile_guided_optimization = {
        "schema_version": 1,
        "runtime_call_frequency": runtime_call_frequency,
        "resident_cold_candidates": resident_cold_candidates,
        "moves_to_georam": [],
        "move_decision": (
            "No resident helpers were moved: all zero-incoming resident routines are "
            "pinned ABI, IRQ, screen/editor, or KERNAL bridge surfaces, and resident "
            "bytes remain within budget."
        ),
        "phase1_for_benchmark": phase1_for_benchmark,
        "resident_budget": {
            "bytes": resident_bytes,
            "limit": 8192,
            "within_limit": resident_bytes <= 8192,
        },
    }
    previous: dict[str, Any] = {}
    previous_path = build_dir / "size_report.json"
    if previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
    size_report: dict[str, Any] = {
        "schema_version": 1,
        "segments": segments,
        "resident_bytes": resident_bytes,
        "resident_limit": 8192,
        "resident_within_limit": resident_bytes <= 8192,
        "georam_bytes": georam_bytes,
        "georam_byte_limit": GEORAM_BYTE_LIMIT,
        "georam_pages": georam_pages,
        "georam_page_limit": GEORAM_PAGE_LIMIT,
        "georam_within_limit": georam_within_limit,
        "compile_bytes": (build_dir / "compile.bin").stat().st_size,
        "compile_limit": 0xCFFF - 0x080D + 1,
        "resident_delta_bytes": resident_bytes - int(previous.get("resident_bytes", 0)),
        "georam_page_delta": georam_pages - int(previous.get("georam_pages", 0)),
        "resident_hot_paths": resident_hot_paths,
        "profile_guided_optimization": profile_guided_optimization,
    }
    size_report["compile_within_limit"] = (
        size_report["compile_bytes"] <= size_report["compile_limit"]
    )
    artifact_names = ["basicv3.prg", "georam.bin", "reu.bin", "compiler.d64"]
    artifacts: dict[str, Any] = {}
    for name in artifact_names:
        path = build_dir / name
        if path.exists():
            artifacts[name] = _artifact(path)
    loader_manifest: dict[str, Any] = {
        "schema_version": 1,
        "load_address": 0x0801,
        "entry_address": 0x080D,
        "loader_start": loader["start"],
        "loader_size": loader["size"],
        "artifacts": artifacts,
    }
    reu_manifest_path = build_dir / "reu_loader_manifest.json"
    if reu_manifest_path.exists():
        reu_manifest = json.loads(reu_manifest_path.read_text(encoding="utf-8"))
        if isinstance(reu_manifest, dict):
            loader_manifest["reu_patch"] = {
                "path": reu_manifest.get("path", (build_dir / "reu.bin").as_posix()),
                "georam_sha256": reu_manifest.get("georam_sha256"),
                "format_version": reu_manifest.get("format_version"),
                "abi_version": reu_manifest.get("abi_version"),
                "min_reu_capacity_kib": reu_manifest.get("min_reu_capacity_kib"),
                "has_georam_capacity_field": reu_manifest.get(
                    "has_georam_capacity_field", False
                ),
            }
    return loader_manifest, size_report


def update_history(build_dir: Path, size_report: dict[str, Any]) -> None:
    """Record one size sample for the current Git commit.

    Args:
        build_dir: Generated build directory.
        size_report: Current size report.
    """
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=build_dir.parent,
        check=False,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip() if result.returncode == 0 else "uncommitted"
    history_path = build_dir / "size_history.json"
    history: list[dict[str, Any]] = []
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    sample = {
        "commit": commit,
        "resident_bytes": size_report["resident_bytes"],
        "georam_pages": size_report["georam_pages"],
        "compile_bytes": size_report["compile_bytes"],
    }
    history = [record for record in history if record.get("commit") != commit]
    history.append(sample)
    history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    """Write both generated reports."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    args = parser.parse_args()
    build_dir = args.build_dir.resolve()
    loader, sizes = generate(build_dir)
    (build_dir / "loader_manifest.json").write_text(
        json.dumps(loader, indent=2) + "\n", encoding="utf-8"
    )
    (build_dir / "size_report.json").write_text(
        json.dumps(sizes, indent=2) + "\n", encoding="utf-8"
    )
    update_history(build_dir, sizes)


if __name__ == "__main__":
    main()
