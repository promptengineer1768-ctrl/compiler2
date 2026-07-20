"""System contracts for the expansion-native routine placement policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
ROUTINES_PATH = ROOT / "manifests" / "routines.json"
POLICY_PATH = ROOT / "manifests" / "placement_policy.json"
SCHEMA_PATH = ROOT / "manifests" / "placement_policy.schema.json"
ALLOWED_PLACEMENTS = {
    "resident_pinned",
    "loader",
    "runtime_abi",
    "compiled_code",
    "expansion_xip",
}
REQUIRED_FIELDS = {
    "routine_id",
    "name",
    "module",
    "current_placement",
    "target_placement",
    "classification",
    "conformance",
    "porting_strategy",
    "normative_anchor",
    "evidence",
    "verification",
    "notes",
}
NORMAL_RAM_ACCOUNTABILITY_FIELDS = {
    "normal_ram_reason",
    "normal_ram_byte_cost",
    "normal_ram_byte_cost_basis",
    "owner",
    "review_test",
}
CURRENT_PLACEMENT_BY_LAYER = {
    "resident": "resident_pinned",
    "arena": "resident_pinned",
    "loader": "loader",
    "runtime": "runtime_abi",
    "geoasm": "expansion_xip",
}


def _load(path: Path) -> dict[str, Any]:
    """Load a JSON object from a checked-in manifest."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.mark.system
@pytest.mark.static
class TestExpansionPlacementPolicy:
    """Prevent unclassified routines and undocumented placement drift."""

    def test_inventory_covers_each_routine_id_exactly_once(self) -> None:
        """The ABI manifest and policy inventory have identical routine identities."""
        routine_manifest = _load(ROUTINES_PATH)
        policy = _load(POLICY_PATH)
        source = routine_manifest["routines"]
        entries = policy["routines"]
        expected = {
            (index, routine["name"], routine["module"])
            for index, routine in enumerate(source)
        }
        actual = {
            (entry["routine_id"], entry["name"], entry["module"])
            for entry in entries
        }
        assert len(entries) == len(actual)
        assert actual == expected

    def test_checked_in_schema_names_the_policy_contract(self) -> None:
        """The inventory format is explicit rather than an undocumented JSON shape."""
        schema = _load(SCHEMA_PATH)
        assert schema["title"] == "Compiler 2 routine placement policy"
        assert set(schema["$defs"]["placement"]["enum"]) == ALLOWED_PLACEMENTS
        assert set(schema["properties"]["routines"]["items"]["required"]) == REQUIRED_FIELDS

    def test_inventory_records_complete_evidence_for_each_routine(self) -> None:
        """Every classification states target, current state, authority, and proof."""
        for entry in _load(POLICY_PATH)["routines"]:
            assert REQUIRED_FIELDS <= entry.keys(), entry["name"]
            assert entry["target_placement"] in ALLOWED_PLACEMENTS
            assert entry["current_placement"] in ALLOWED_PLACEMENTS
            assert entry["classification"] == entry["target_placement"]
            for field in ("normative_anchor", "evidence", "verification", "notes"):
                assert isinstance(entry[field], str) and entry[field].strip(), entry["name"]

    def test_current_placement_is_derived_from_the_actual_manifest_layer(self) -> None:
        """The inventory cannot pretend resident code already executes in geoRAM."""
        routines = _load(ROUTINES_PATH)["routines"]
        entries = {entry["routine_id"]: entry for entry in _load(POLICY_PATH)["routines"]}
        for routine_id, routine in enumerate(routines):
            assert entries[routine_id]["current_placement"] == CURRENT_PLACEMENT_BY_LAYER[
                routine["layer"]
            ]

    def test_normal_ram_targets_have_concrete_accountability(self) -> None:
        """Every retained normal-RAM target declares cost, rationale, owner, and review."""
        placeholders = {"", "n/a", "none", "tbd", "todo", "unknown"}
        for entry in _load(POLICY_PATH)["routines"]:
            if entry["target_placement"] == "expansion_xip":
                continue
            assert NORMAL_RAM_ACCOUNTABILITY_FIELDS <= entry.keys(), entry["name"]
            assert entry["normal_ram_byte_cost"] > 0, entry["name"]
            for field in (
                "normal_ram_reason",
                "normal_ram_byte_cost_basis",
                "owner",
                "review_test",
            ):
                value = entry[field]
                assert isinstance(value, str) and value.strip().lower() not in placeholders
                assert value.strip(), entry["name"]

    def test_migration_debt_is_explicit_and_not_an_exception(self) -> None:
        """Current normal-RAM compiler code remains visible until its XIP migration lands."""
        for entry in _load(POLICY_PATH)["routines"]:
            mismatch = entry["current_placement"] != entry["target_placement"]
            assert (entry["conformance"] == "migration_required") == mismatch
            if mismatch:
                if entry["target_placement"] == "expansion_xip":
                    assert entry["porting_strategy"] in {"repack", "split", "xip_rewrite"}
                    assert "dispatcher" in entry["notes"].lower()
                else:
                    assert entry["porting_strategy"] == "relocate"
