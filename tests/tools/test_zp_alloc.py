"""Tests for tools/zp_alloc.py — zero-page graph-coloring allocator.

Covers: manifest loading, address-range parsing, interference edge building,
graph coloring, equates emission, and output file generation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# Allow importing tools/ from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import zp_alloc

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_MANIFEST: dict[str, Any] = {
    "fixed_reservations": [
        {"address": "$00-$01", "symbol": "CPU_PORT", "size": 2, "notes": "CPU port"},
        {"address": "$90", "symbol": "ST_REG", "size": 1, "notes": "ST register"},
    ],
    "kernal_bridge_zp": [],
    "nodes": [
        {
            "name": "tmp0",
            "size": 1,
            "domain": "scratch",
            "notes": "temp",
            "lifetimes": [{"routine": "foo", "phase": "a"}],
        },
        {
            "name": "tmp1",
            "size": 1,
            "domain": "scratch",
            "notes": "temp",
            "lifetimes": [{"routine": "bar", "phase": "b"}],
        },
        {
            "name": "shared",
            "size": 1,
            "domain": "scratch",
            "notes": "shared",
            "lifetimes": [
                {"routine": "foo", "phase": "a"},
                {"routine": "bar", "phase": "b"},
            ],
        },
    ],
}


@pytest.fixture()
def manifest_file(tmp_path: Path) -> Path:
    """Writes a minimal zero_page.json and returns its path."""
    p = tmp_path / "zero_page.json"
    p.write_text(json.dumps(MINIMAL_MANIFEST), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestParseAddressRange:
    """Tests for zp_alloc.parse_address_range."""

    def test_single_address(self) -> None:
        assert zp_alloc.parse_address_range("$90") == {0x90}

    def test_range(self) -> None:
        assert zp_alloc.parse_address_range("$A0-$A2") == {0xA0, 0xA1, 0xA2}

    def test_single_zero(self) -> None:
        assert zp_alloc.parse_address_range("$00") == {0x00}


class TestLoadManifest:
    """Tests for zp_alloc.load_manifest."""

    def test_loads_fixed_reservations(self, manifest_file: Path) -> None:
        fixed, _, nodes = zp_alloc.load_manifest(str(manifest_file))
        assert len(fixed) == 2

    def test_loads_nodes(self, manifest_file: Path) -> None:
        _, _, nodes = zp_alloc.load_manifest(str(manifest_file))
        assert len(nodes) == 3
        assert any(n["name"] == "tmp0" for n in nodes)

    def test_missing_file_raises(self) -> None:
        with pytest.raises((FileNotFoundError, OSError)):
            zp_alloc.load_manifest("/nonexistent/zero_page.json")


class TestInterferenceGraph:
    """Tests that interference edges are built correctly from shared lifetimes."""

    def test_same_routine_phase_interferes(self) -> None:
        """Nodes with overlapping routine+phase share an interference edge."""
        nodes = [
            {
                "name": "a",
                "size": 1,
                "domain": "x",
                "notes": "",
                "lifetimes": [{"routine": "r", "phase": "p"}],
            },
            {
                "name": "b",
                "size": 1,
                "domain": "y",
                "notes": "",
                "lifetimes": [{"routine": "r", "phase": "p"}],
            },
        ]
        graph = zp_alloc.build_interference_graph(nodes)
        assert "b" in graph["a"] or "a" in graph["b"]

    def test_disjoint_lifetimes_no_edge(self) -> None:
        """Nodes with non-overlapping lifetimes do not interfere."""
        nodes = [
            {
                "name": "a",
                "size": 1,
                "domain": "x",
                "notes": "",
                "lifetimes": [{"routine": "r1", "phase": "p1"}],
            },
            {
                "name": "b",
                "size": 1,
                "domain": "y",
                "notes": "",
                "lifetimes": [{"routine": "r2", "phase": "p2"}],
            },
        ]
        graph = zp_alloc.build_interference_graph(nodes)
        assert "b" not in graph.get("a", set())
        assert "a" not in graph.get("b", set())


class TestColorGraph:
    """Tests that the graph-coloring allocator produces a valid ZP coloring."""

    def test_two_non_interfering_nodes_allocated(self) -> None:
        nodes = [
            {
                "name": "a",
                "size": 1,
                "domain": "x",
                "notes": "",
                "alignment": 1,
                "lifetimes": [{"routine": "r1", "phase": "p1"}],
            },
            {
                "name": "b",
                "size": 1,
                "domain": "y",
                "notes": "",
                "alignment": 1,
                "lifetimes": [{"routine": "r2", "phase": "p2"}],
            },
        ]
        graph = zp_alloc.build_interference_graph(nodes)
        allocation = zp_alloc.color_graph(nodes, graph, reserved_addresses=set())
        assert "a" in allocation
        assert "b" in allocation

    def test_interfering_nodes_get_distinct_addresses(self) -> None:
        nodes = [
            {
                "name": "a",
                "size": 1,
                "domain": "x",
                "notes": "",
                "alignment": 1,
                "lifetimes": [{"routine": "r", "phase": "p"}],
            },
            {
                "name": "b",
                "size": 1,
                "domain": "x",
                "notes": "",
                "alignment": 1,
                "lifetimes": [{"routine": "r", "phase": "p"}],
            },
        ]
        graph = zp_alloc.build_interference_graph(nodes)
        allocation = zp_alloc.color_graph(nodes, graph, reserved_addresses=set())
        assert allocation["a"] != allocation["b"]

    def test_all_addresses_in_zp_range(self) -> None:
        nodes = [
            {
                "name": "v",
                "size": 1,
                "domain": "d",
                "notes": "",
                "alignment": 1,
                "lifetimes": [{"routine": "r", "phase": "p"}],
            }
        ]
        graph = zp_alloc.build_interference_graph(nodes)
        allocation = zp_alloc.color_graph(nodes, graph, reserved_addresses=set())
        addr = allocation["v"]
        assert 0x02 <= addr <= 0xFF


class TestOutputGeneration:
    """Tests that generate_output writes expected output files."""

    def test_zp_symbols_inc_generated(
        self, manifest_file: Path, tmp_path: Path
    ) -> None:
        """zp_symbols.inc is created and contains address equates."""
        fixed, bridge, nodes = zp_alloc.load_manifest(str(manifest_file))
        reserved: set[int] = set()
        for r in fixed:
            reserved |= zp_alloc.parse_address_range(r["address"])
        graph = zp_alloc.build_interference_graph(nodes)
        allocation = zp_alloc.color_graph(nodes, graph, reserved_addresses=reserved)
        zp_alloc.generate_output(allocation, fixed, bridge, nodes, graph, str(tmp_path))
        inc_path = tmp_path / "zp_symbols.inc"
        assert inc_path.exists()
        content = inc_path.read_text(encoding="utf-8")
        assert "=" in content
        protected = (tmp_path / "zp_protected_ranges.inc").read_text(encoding="utf-8")
        assert "compiler_zp_protected_range_count" in protected
        assert ".byte" in protected

    def test_zp_allocation_json_valid(
        self, manifest_file: Path, tmp_path: Path
    ) -> None:
        """zp_allocation.json is valid JSON with 'valid' and 'allocation' keys."""
        fixed, bridge, nodes = zp_alloc.load_manifest(str(manifest_file))
        reserved: set[int] = set()
        for r in fixed:
            reserved |= zp_alloc.parse_address_range(r["address"])
        graph = zp_alloc.build_interference_graph(nodes)
        allocation = zp_alloc.color_graph(nodes, graph, reserved_addresses=reserved)
        zp_alloc.generate_output(allocation, fixed, bridge, nodes, graph, str(tmp_path))
        json_path = tmp_path / "zp_allocation.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data.get("valid") is True
        assert "allocation" in data


class TestValidation:
    """Direct negative coverage for allocation and ABI validators."""

    def test_validate_no_overlap_reports_live_and_reserved_conflicts(self) -> None:
        """Overlapping live ranges and reserved bytes are both rejected."""
        nodes = [
            {"name": "left", "size": 2},
            {"name": "right", "size": 2},
        ]
        errors = zp_alloc.validate_no_overlap(
            {"left": 0x10, "right": 0x11},
            nodes,
            {"left": {"right"}, "right": {"left"}},
            {0x10},
        )
        assert errors == [
            "left overlaps reserved address(es) $10",
            "live nodes left and right overlap",
        ]

    def test_validate_contracts_reports_undeclared_symbols(self) -> None:
        """Routine ZP reads and writes must resolve to declared symbols."""
        routines = [
            {
                "name": "sample",
                "zp_read": ["known", "missing_read"],
                "zp_write": ["missing_write"],
            }
        ]
        errors = zp_alloc.validate_contracts(
            {"known": 0x20},
            routines,
            [],
            [],
        )
        assert errors == [
            "sample.zp_read references undeclared missing_read",
            "sample.zp_write references undeclared missing_write",
        ]
