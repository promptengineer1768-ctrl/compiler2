"""Generate the trusted, fail-closed Backend skeleton review snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from backend_framework.skeletons import render_skeletons, write_skeletons

ROOT = Path(__file__).resolve().parents[1]
ROUTINES_PATH = ROOT / "manifests" / "routines.json"
PROFILE_PATH = ROOT / "manifests" / "backend" / "skeleton-profile.json"
SNAPSHOT_ROOT = ROOT / "generated" / "backend-skeletons"


def _values(value: object) -> list[str]:
    """Convert one descriptive ABI field to the Backend string-list form."""
    text = str(value).strip()
    if not text or text.lower() == "none" or text in {"-", "—"}:
        return []
    return [text]


def build_profile(inventory: dict[str, Any]) -> dict[str, Any]:
    """Derive the complete Backend profile from the authoritative inventory."""
    routines: list[dict[str, Any]] = []
    for source in inventory["routines"]:
        name = str(source["name"])
        zero_page = [f"read:{item}" for item in source["zp_read"]]
        zero_page.extend(f"write:{item}" for item in source["zp_write"])
        routines.append(
            {
                "id": name,
                "source": str(source["module"]),
                "entry": name,
                "language": "ca65",
                "visibility": str(source["visibility"]),
                "calling_convention": {
                    "inputs": _values(source["inputs"]),
                    "outputs": _values(source["outputs"]),
                    "clobbers": _values(source["clobbers"]),
                    "flags": [
                        f"return_kind:{source['return_kind']}",
                        f"stack_delta:{source['stack_delta']}",
                        f"preserves:{source['preserves']}",
                        f"irq_safe:{str(source['irq_safe']).lower()}",
                        f"irq_masked_ok:{str(source['irq_masked_ok']).lower()}",
                    ],
                    "zero_page": zero_page,
                    "side_effects": _values(source["side_effects"]),
                },
                "contract": str(source["purpose"]).strip()
                or f"Authoritative ABI contract for {name}",
                "requirements": ["REQ-SKELETON-001"],
                "design_refs": ["SKELETON.md", "manifests/routines.json"],
                "tests": ["backend_skeleton_contract"],
            }
        )
    return {
        "$schema": "../../../backend/schemas/skeleton-profile.schema.json",
        "schema_epoch": 1,
        "consumer": "compiler2",
        "generated_by": "trusted",
        "design_inputs": [
            "REQUIREMENTS.md",
            "REU_REQUIREMENTS.md",
            "DESIGN.md",
            "REU_DESIGN.md",
            "SKELETON.md",
            "manifests/routines.json",
            "docs/COMPILER_ARCHITECTURE.md",
            "docs/CONTROL_FLOW.md",
            "docs/GENERATED_REFERENCE.md",
        ],
        "routines": routines,
    }


def _profile_text(profile: dict[str, Any]) -> str:
    """Return the canonical serialized profile."""
    return json.dumps(profile, indent=2, ensure_ascii=False) + "\n"


def check_snapshot(profile: dict[str, Any]) -> list[str]:
    """Return differences between derived contracts and tracked outputs."""
    errors: list[str] = []
    if not PROFILE_PATH.is_file() or PROFILE_PATH.read_text("utf-8") != _profile_text(
        profile
    ):
        errors.append(f"stale generated profile: {PROFILE_PATH.relative_to(ROOT)}")
    rendered = render_skeletons(profile)
    expected = {SNAPSHOT_ROOT / relative: body for relative, body in rendered.items()}
    actual = set(SNAPSHOT_ROOT.rglob("*.asm")) if SNAPSHOT_ROOT.is_dir() else set()
    if actual != set(expected):
        errors.append("generated skeleton module set does not match the profile")
    for path, body in expected.items():
        if not path.is_file() or path.read_text("utf-8") != body:
            errors.append(f"stale generated skeleton: {path.relative_to(ROOT)}")
    return errors


def generate_snapshot(profile: dict[str, Any]) -> None:
    """Write a new profile and isolated snapshot without replacing outputs."""
    if SNAPSHOT_ROOT.exists():
        raise FileExistsError(f"refusing to replace snapshot: {SNAPSHOT_ROOT}")
    PROFILE_PATH.write_text(_profile_text(profile), encoding="utf-8")
    write_skeletons(profile, SNAPSHOT_ROOT)


def refresh_snapshot(profile: dict[str, Any]) -> None:
    """Refresh only the already-owned derived files in the isolated snapshot."""
    rendered = render_skeletons(profile)
    expected = {SNAPSHOT_ROOT / relative for relative in rendered}
    actual = set(SNAPSHOT_ROOT.rglob("*.asm"))
    if actual != expected:
        raise ValueError("refusing to refresh a snapshot with a different module set")
    PROFILE_PATH.write_text(_profile_text(profile), encoding="utf-8")
    for relative, body in rendered.items():
        (SNAPSHOT_ROOT / relative).write_text(body, encoding="utf-8")


def main() -> int:
    """Generate a new snapshot or verify the checked-in deterministic result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    inventory = json.loads(ROUTINES_PATH.read_text(encoding="utf-8"))
    profile = build_profile(inventory)
    if args.check and args.refresh:
        parser.error("--check and --refresh are mutually exclusive")
    if args.check:
        errors = check_snapshot(profile)
        for error in errors:
            print(error)
        return int(bool(errors))
    if args.refresh:
        refresh_snapshot(profile)
    else:
        generate_snapshot(profile)
    print(
        f"Generated {len(profile['routines'])} routines in "
        f"{len(render_skeletons(profile))} shadow modules."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
