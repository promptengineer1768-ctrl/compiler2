"""System contracts for additive Backend-framework adoption."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(os.environ.get("COMPILER2_BACKEND_ROOT", ROOT.parent / "backend"))
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
from backend_framework.math import select_math  # noqa: E402
from backend_framework.numeric_types import promoted_type  # noqa: E402
from backend_framework.validation.manifests import (  # noqa: E402
    validate_manifest,
)
from tools.generate_backend_skeleton_snapshot import (  # noqa: E402
    build_profile,
    check_snapshot,
)

ADOPTED = (
    "target-profile.json",
    "low-memory-c64.json",
    "low-memory-plus4.json",
    "basic-return-c64.json",
    "basic-return-plus4.json",
    "math-profile.json",
    "numeric-type-profile.json",
    "build-profile.json",
    "documentation-profile.json",
    "distribution-profile.json",
    "skeleton-profile.json",
    "readiness.json",
    "testing-profile.json",
    "adoption-tasks.json",
)
LOCKED = ADOPTED + ("skeleton-readiness.json",)


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


def _run_adoption_adapter(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the project-owned Backend adapter through its production CLI."""
    return subprocess.run(
        [sys.executable, "tools/backend_adoption.py", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.system
def test_backend_build_adapter_plans_the_canonical_release_dag() -> None:
    """Backend planning preserves validation, build, test, and package order."""
    result = _run_adoption_adapter("plan", "distribution")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "target": "distribution",
        "steps": [
            "validate_manifests",
            "build_release",
            "test_system",
            "prepare_distribution",
        ],
    }


@pytest.mark.system
def test_backend_generated_documentation_is_current_and_traceable() -> None:
    """The production adapter checks every declared generated document."""
    result = _run_adoption_adapter("documentation", "--check")
    assert result.returncode == 0, result.stderr


@pytest.mark.system
def test_backend_distribution_is_current_hashed_and_reproducible() -> None:
    """The production adapter verifies the declared end-user archive twice."""
    result = _run_adoption_adapter("distribution", "--check-reproducible")
    assert result.returncode == 0, result.stderr


@pytest.mark.system
@pytest.mark.smoke
def test_backend_revision_and_adopted_inputs_are_locked() -> None:
    """The sibling revision and every adopted input must match the lock."""
    lock = _load("backend.lock.json")
    assert lock["framework_revision"] == "b6c5d2d3d6565ff0e9e0cc1aa26458e1d3197ee0"
    verify_lock(lock, ROOT)
    assert set(lock["inputs"]) == {f"manifests/backend/{name}" for name in LOCKED}


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


@pytest.mark.system
def test_numeric_tags_are_preserved_and_new_ieee_provider_remains_planned() -> None:
    """INT1/2/3 stay stable while nc256 replacement retains its proof gate."""
    types = _load("numeric-type-profile.json")
    assert promoted_type(types, "int1", "int2") == "int2"
    assert {item["id"]: item["tag"] for item in types["types"]} == {
        "int1": 1,
        "int2": 2,
        "int3": 3,
        "float": 4,
    }
    catalog = json.loads(
        (BACKEND_ROOT / "manifests/math-catalog.json").read_text("utf-8")
    )
    selected = select_math(catalog, _load("math-profile.json"))
    assert {item.provider for item in selected} == {"arithmetic"}
    assert _load("math-profile.json")["extensions"]["migration"].startswith(
        "floatlib nc256 deprecated"
    )


@pytest.mark.system
def test_backend_skeleton_contract() -> None:
    """The tracked review snapshot exactly mirrors every authoritative routine."""
    profile = _load("skeleton-profile.json")
    readiness = _load("skeleton-readiness.json")
    inventory = json.loads((ROOT / "manifests/routines.json").read_text("utf-8"))
    assert profile["generated_by"] == "trusted"
    assert profile == build_profile(inventory)
    assert check_snapshot(profile) == []
    assert readiness["routine_inventory"]["record_count"] == len(inventory["routines"])
    assert len(profile["routines"]) == 405
    assert {item["id"] for item in profile["routines"]} == {
        item["name"] for item in inventory["routines"]
    }
    assert all(
        item["tests"] == ["backend_skeleton_contract"] for item in profile["routines"]
    )
    snapshot = ROOT / "generated/backend-skeletons"
    modules = tuple(snapshot.rglob("*.asm"))
    generated = "".join(path.read_text("utf-8") for path in modules)
    assert len(modules) == len({item["module"] for item in inventory["routines"]})
    assert generated.count(".proc ") == 405
    assert generated.count('.error "skeleton requires implementation"') == 405
    assert readiness["generation_policy"]["task_order"] == "final"
    assert readiness["generation_policy"]["overwrite_existing_source"] is False
    assert readiness["generation_policy"]["snapshot_root"] == (
        "generated/backend-skeletons"
    )
    assert "generated/backend-skeletons" not in json.dumps(_load("build-profile.json"))
    tasks = _load("adoption-tasks.json")["tasks"]
    assert tasks[-1]["id"] == "backend.skeleton_generation_final"
    assert tasks[-1]["execution_tier"] == "trusted"
    assert tasks[-1]["depends_on"] == ["backend.skeleton_acceptance"]
    assert tasks[-1]["status"] == "complete"


@pytest.mark.system
def test_remote_ci_pins_actions_and_publishes_all_proof_artifacts() -> None:
    """Remote proof exposes binaries, docs, distribution, and reports."""
    workflow = (ROOT / ".github/workflows/backend-consumer-ci.yml").read_text("utf-8")
    assert "b6c5d2d3d6565ff0e9e0cc1aa26458e1d3197ee0" in workflow
    assert "cc7c9c22c739326d5f6727c3b08300850a79b2c9" in workflow
    assert "@v" not in workflow
    for artifact in (
        "compiler2-binaries",
        "compiler2-documentation",
        "compiler2-distribution",
        "compiler2-test-reports",
    ):
        assert f"name: {artifact}" in workflow
    assert "--junitxml=build/test-reports/system.xml" in workflow
    assert "runs-on: ubuntu-latest" in workflow
    assert "working-directory: compiler2" in workflow
    assert "path: compiler2" in workflow
    assert "path: backend" in workflow
    assert "path: tools/vice-next-mcp" in workflow
    assert "COMPILER2_BACKEND_ROOT: ${{ github.workspace }}/backend" in workflow
    assert "compiler2/build/test-reports/**" in workflow
    assert "token: ${{ secrets.BACKEND_READ_TOKEN }}" in workflow
    assert "ci-summary.json" in workflow
    assert "Initialize machine-readable reports" in workflow
    assert workflow.count("if: always()") >= 6
    assert "pyyaml" in workflow
    assert (
        "31eebade4c55bb4f9bda7ecb17f35f868c6c2cfceeea86b59ef777c2e25684a2" in workflow
    )
    assert "v3.10-instrumented-20260718-full.4" in workflow
    assert "xvfb" in workflow.lower()
    assert "DISPLAY=:99" in workflow
    assert "tests/system/test_backend_adoption.py" in workflow
    assert "-SkipViceBenchmarks" in workflow
    assert "CC65_REVISION: a29ce64fb51c97b7dda58dc5818f8c64b6b6f3ce" in workflow
    assert "git -C ../cc65 checkout --detach $env:CC65_REVISION" in workflow


@pytest.mark.system
def test_build_stops_before_task_validation_if_manifest_validation_fails() -> None:
    """The first validator cannot have its failure masked by the second."""
    build = (ROOT / "build.ps1").read_text("utf-8")
    manifests = build.index("tools/validate_build.py --manifests")
    manifest_guard = build.index("Build manifest validation failed", manifests)
    tasks = build.index("tools/task_manifest.py validate")
    assert manifests < manifest_guard < tasks


@pytest.mark.system
def test_remote_build_can_separate_unsupported_vice_measurement() -> None:
    """Linux packaging may omit measurement but cannot invent a passing result."""
    build = (ROOT / "build.ps1").read_text("utf-8")
    assert "[switch]$SkipViceBenchmarks" in build
    assert "if ($SkipViceBenchmarks)" in build
    assert "--measure-native-fixture" in build
    assert "--require-measured" not in build
