"""Tests for graph-colored normal-RAM workarea allocation."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import workarea_alloc  # noqa: E402


def test_disjoint_lifetimes_share_region() -> None:
    """Disjoint buffers color to the same bytes and reduce workarea size."""
    data = json.loads((ROOT / "manifests" / "workareas.json").read_text())
    allocation = workarea_alloc.allocate(data)
    assert allocation == {"io_input": 0, "io_output": 0}
    assert data["region"]["size"] < sum(node["size"] for node in data["nodes"])


def test_conflicting_lifetimes_do_not_overlap() -> None:
    """Buffers live in the same phase receive non-overlapping intervals."""
    data = {
        "region": {"size": 8},
        "nodes": [
            {"name": "a", "size": 4, "lifetimes": ["compile"]},
            {"name": "b", "size": 4, "lifetimes": ["compile"]},
        ],
    }
    assert workarea_alloc.allocate(data) == {"a": 0, "b": 4}


def test_exhaustion_is_rejected() -> None:
    """An undersized region fails rather than emitting an unsafe alias."""
    data = {
        "region": {"size": 4},
        "nodes": [
            {"name": "a", "size": 4, "lifetimes": ["run"]},
            {"name": "b", "size": 1, "lifetimes": ["run"]},
        ],
    }
    with pytest.raises(ValueError, match="cannot allocate"):
        workarea_alloc.allocate(data)
