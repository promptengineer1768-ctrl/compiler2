"""System contracts for additive Backend-framework adoption."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT / "src"))

from backend_framework.basic_return import (  # noqa: E402
    validate_basic_return,
)
from backend_framework.locks import (  # noqa: E402
    verify_lock,
)
from backend_framework.low_memory import (  # noqa: E402
    LowMemoryRegion,
    plan_low_memory,
)
from backend_framework.validation.manifests import (  # noqa: E402
    validate_manifest,
)

ADOPTED = (
    "target-profile.json",
    "low-memory-c64.json",
    "low-memory-plus4.json",
    "basic-return-c64.json",
    "basic-return-plus4.json",
)


def _load(name: str) -> dict[str, Any]:
    """Load one adopted Backend manifest."""
    value = json.loads((ROOT / "manifests" / "backend" / name).read_text("utf-8"))
    assert isinstance(value, dict)
    return value


def _regions(profile: dict[str, Any]) -> tuple[LowMemoryRegion, ...]:
    """Convert a shared low-memory profile to Backend planner records."""
    return tuple(
        LowMemoryRegion(
            str(region["id"]),
            int(region["start"]),
            int(region["end"]),
            frozenset(str(item) for item in region["reserve_when"]),
            str(region["restore"]),
        )
        for region in profile["regions"]
    )


@pytest.mark.system
@pytest.mark.smoke
def test_backend_revision_and_adopted_inputs_are_locked() -> None:
    """The sibling revision and every adopted input must match the lock."""
    lock = _load("backend.lock.json")
    assert lock["framework_revision"] == "9283738083403e3f4282a99a0b47c096d552ee45"
    verify_lock(lock, ROOT)
    assert set(lock["inputs"]) == {f"manifests/backend/{name}" for name in ADOPTED}


@pytest.mark.system
@pytest.mark.parametrize("name", ADOPTED)
def test_adopted_backend_manifests_satisfy_sibling_schemas(name: str) -> None:
    """Consumer profiles remain valid under the pinned shared schemas."""
    validate_manifest(ROOT / "manifests" / "backend" / name)


@pytest.mark.system
def test_machine_low_memory_ownership_is_explicit_and_nonportable() -> None:
    """C64 reclamation is bounded while Plus/4 remains conservative."""
    c64 = _load("low-memory-c64.json")
    c64_plan = plan_low_memory(
        active_features=frozenset(c64["active_features"]),
        regions=_regions(c64),
    )
    assert c64_plan.free == ((0x0334, 0x03FF), (0x07E8, 0x07F7))
    plus4 = _load("low-memory-plus4.json")
    plus4_plan = plan_low_memory(
        active_features=frozenset(plus4["active_features"]),
        regions=_regions(plus4),
    )
    assert plus4_plan.free == ()
    assert plus4["extensions"]["machine"] == "plus4"


@pytest.mark.system
@pytest.mark.parametrize(
    ("name", "target"),
    (
        ("basic-return-c64.json", "c64_basic_v2"),
        ("basic-return-plus4.json", "plus4_basic_v35_reference"),
    ),
)
def test_basic_return_adapters_follow_common_order(name: str, target: str) -> None:
    """Machine adapters preserve the framework's ordered handoff semantics."""
    profile = _load(name)
    plan = validate_basic_return(target, tuple(profile["steps"]))
    assert plan.target == target


@pytest.mark.system
def test_profiles_do_not_claim_unimplemented_smc_or_plus4_production() -> None:
    """The adoption slice distinguishes contracts from implemented paths."""
    target = _load("target-profile.json")
    assert target["dispatch"]["backend"] == "non_smc"
    assert target["extensions"]["smc_adoption"].startswith("requires_")
    plus4_return = _load("basic-return-plus4.json")
    assert plus4_return["extensions"]["production_target"] is False
