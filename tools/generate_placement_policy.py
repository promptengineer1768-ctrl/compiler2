"""Generate the checked-in routine placement-policy inventory.

The routine ABI manifest is the source of routine identity.  This generator
adds the architectural placement decision and its evidence without allowing a
second hand-maintained list of callable routines to drift from that ABI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ROUTINES_PATH = ROOT / "manifests" / "routines.json"
OUTPUT_PATH = ROOT / "manifests" / "placement_policy.json"

PLACEMENTS = frozenset(
    {
        "resident_pinned",
        "loader",
        "runtime_abi",
        "compiled_code",
        "expansion_xip",
    }
)
CURRENT_PLACEMENT_BY_LAYER = {
    "resident": "resident_pinned",
    "arena": "resident_pinned",
    "loader": "loader",
    "runtime": "runtime_abi",
    "geoasm": "expansion_xip",
}
XIP_ANCHOR = (
    "REQUIREMENTS.md §7.2 and §8; DESIGN2.md §8; "
    "docs/COMPILER_ARCHITECTURE.md §2"
)
RESIDENT_ANCHOR = "REQUIREMENTS.md §8; DESIGN2.md §8"


def _current_placement(routine: dict[str, Any]) -> str:
    """Return the placement represented by the current routine manifest."""
    layer = routine["layer"]
    try:
        return CURRENT_PLACEMENT_BY_LAYER[layer]
    except KeyError as error:
        raise ValueError(f"Unknown current manifest layer: {layer}") from error


def _target_placement(routine: dict[str, Any]) -> str:
    """Return the required final placement from architecture, not current code."""
    module = routine["module"]
    if module == "src/geoasm/loader_core.asm" or module.startswith("src/loader/"):
        return "loader"
    if module.startswith("src/geoasm/"):
        return "expansion_xip"
    if module.startswith("src/runtime/"):
        return "runtime_abi"
    return "resident_pinned"


def _porting_strategy(routine: dict[str, Any], target: str, current: str) -> str:
    """Assign a preliminary audited migration strategy for a routine."""
    if current == target:
        return "retain"
    if target != "expansion_xip":
        return "relocate"
    module = routine["module"]
    if module.endswith(("parser.asm", "codegen.asm", "editor_svc.asm", "direct_dispatch.asm")):
        return "xip_rewrite"
    if module.endswith(("compiler_pipeline.asm", "program_store.asm", "program_codec.asm")):
        return "split"
    return "repack"


def _normal_ram_decision(target: str, routine: dict[str, Any]) -> dict[str, Any]:
    """Return concrete accountability for a normal-RAM placement decision."""
    module = routine["module"]
    if target == "loader":
        reason = (
            "Loader/install code must run before the canonical geoRAM image and "
            "dispatcher are available."
        )
        owner = "loader_install"
    elif target == "runtime_abi":
        reason = (
            "Runtime ABI code must remain callable by emitted compiled programs "
            "after compiler/editor expansion pages are no longer selected."
        )
        owner = "runtime_abi"
    elif module.endswith("irq.asm"):
        reason = (
            "IRQ entry and its bounded helpers must execute at interrupt time "
            "without geoRAM page-switch latency."
        )
        owner = "irq_input"
    elif "kernal_bridge" in module or "georam_gate" in module:
        reason = (
            "Hardware/KERNAL bridging is the resident boundary used to enter, "
            "leave, and service expansion-native code safely."
        )
        owner = "resident_hardware_boundary"
    elif "screen" in module or "resident_main" in module:
        reason = (
            "Resident editor timing, screen, and input primitives must remain "
            "available while expansion-native services execute asynchronously."
        )
        owner = "resident_editor_shell"
    else:
        reason = (
            "This resident support routine is outside compiler/editor XIP scope "
            "and is retained as a bounded normal-RAM service."
        )
        owner = "resident_services"
    return {
        "normal_ram_reason": reason,
        "normal_ram_byte_cost": int(routine["size_ceiling"]),
        "normal_ram_byte_cost_basis": (
            "manifests/routines.json size_ceiling; conservative per-routine "
            "normal-RAM allocation ceiling until a successful linked-size audit."
        ),
        "owner": owner,
        "review_test": (
            "tests/system/test_expansion_placement_policy.py::"
            "TestExpansionPlacementPolicy::test_normal_ram_targets_have_concrete_accountability"
        ),
    }


def _entry(routine_id: int, routine: dict[str, Any]) -> dict[str, Any]:
    """Build one complete placement evidence record."""
    current = _current_placement(routine)
    target = _target_placement(routine)
    assert current in PLACEMENTS
    assert target in PLACEMENTS
    required = current != target
    entry = {
        "routine_id": routine_id,
        "name": routine["name"],
        "module": routine["module"],
        "current_placement": current,
        "target_placement": target,
        "classification": target,
        "conformance": "migration_required" if required else "conforming",
        "porting_strategy": _porting_strategy(routine, target, current),
        "normative_anchor": XIP_ANCHOR if target == "expansion_xip" else RESIDENT_ANCHOR,
        "evidence": (
            f"manifests/routines.json routine {routine['name']} "
            f"declares layer {routine['layer']} and module {routine['module']}"
        ),
        "verification": "tests/system/test_expansion_placement_policy.py",
        "notes": (
            "Current normal-RAM implementation must migrate through the dispatcher."
            if required
            else "Current placement agrees with the architectural classification."
        ),
    }
    if routine.get("xip_page") is not None:
        # Surface the explicit page so path audits can ban direct $DE00 calls
        # only for bodies that already execute from a dedicated geoRAM page.
        entry["xip_page"] = int(routine["xip_page"])
    if target != "expansion_xip":
        entry.update(_normal_ram_decision(target, routine))
    return entry


def generate() -> dict[str, Any]:
    """Return the deterministic placement-policy document."""
    routines = json.loads(ROUTINES_PATH.read_text(encoding="utf-8"))["routines"]
    return {
        "manifest_version": "1.0",
        "source_manifest": "manifests/routines.json",
        "policy": {
            "classification_rule": "Every routine ID appears exactly once.",
            "allowed_target_placements": sorted(PLACEMENTS),
            "approved_exception_policy": (
                "No exception category is implicit. A future approved exception must "
                "be added explicitly with a normative anchor, reason, cost, and test."
            ),
        },
        "routines": [_entry(index, routine) for index, routine in enumerate(routines)],
    }


def main() -> None:
    """Write the checked-in inventory with stable formatting."""
    OUTPUT_PATH.write_text(json.dumps(generate(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
