"""Tests for truthful geoRAM/REU release contract generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import generate_expansion_contracts


def _write_inputs(build_dir: Path) -> None:
    """Write a minimal linked directory and packaged REU patch manifest."""
    build_dir.mkdir(exist_ok=True)
    (build_dir / "routine_directory.json").write_text(
        json.dumps(
            {
                "routines": {
                    "resident": {"id": 0, "layer": "resident", "address": "$080D"},
                    "xip": {
                        "id": 1,
                        "layer": "georam",
                        "block": 0,
                        "page": 7,
                        "offset": 3,
                        "address": "$DE03",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (build_dir / "reu_loader_manifest.json").write_text(
        json.dumps(
            {
                "kind": "reu_patch",
                "georam_sha256": "abc",
                "format_version": 1,
                "abi_version": 1,
                "min_reu_capacity_kib": 512,
                "fixup_bytes": 0,
                "crc32": "1234",
            }
        ),
        encoding="utf-8",
    )


def test_writes_linked_georam_records_and_truthful_patch_only_reu_layout(
    tmp_path: Path,
) -> None:
    """Generated release contracts dual-record REU without fabricating live overlays."""
    _write_inputs(tmp_path)

    generate_expansion_contracts.write(tmp_path)

    overlay = json.loads((tmp_path / "overlay_directory.json").read_text())
    reu = json.loads((tmp_path / "reu_layout.json").read_text())
    assert overlay["routine_count"] == 1
    assert overlay["routines"] == [
        {
            "routine_id": 1,
            "routine_name": "xip",
            "block": 0,
            "page": 7,
            "entry_offset": 3,
            "window_address": "$DE03",
        }
    ]
    assert reu["implementation_status"] == "patch_only_no_reu_xip_overlays"
    assert reu["backend"] == "reu_patch_only"
    assert reu["overlays"] == []
    assert reu["slot_classes"] == []
    assert reu["planned_slot_classes"] == [
        {
            "slot_class": "primary_xip_miss",
            "origin": "$CE00",
            "capacity_bytes": 256,
            "execution_status": "not_live",
        }
    ]
    assert reu["routine_record_count"] == 1
    assert reu["routine_records"] == [
        generate_expansion_contracts.dual_routine_record(
            routine_id=1,
            routine_name="xip",
            block=0,
            page=7,
            entry_offset=3,
            window_address="$DE03",
        )
    ]
    reu_half = reu["routine_records"][0]["reu"]
    assert reu_half["logical_page"] == 7
    assert reu_half["reu_start"] == 7 * 256
    assert reu_half["image_length"] == 256
    assert reu_half["execution_status"] == "not_live"


def test_dual_record_maps_block_page_to_linear_reu_start() -> None:
    """REU extent addresses follow geoRAM block*64+page packing."""
    record = generate_expansion_contracts.dual_routine_record(
        routine_id=9,
        routine_name="page",
        block=1,
        page=2,
        entry_offset=0,
        window_address="$DE00",
    )
    assert record["reu"]["logical_page"] == 64 + 2
    assert record["reu"]["reu_start"] == (64 + 2) * 256


def test_rejects_georam_record_without_physical_placement(tmp_path: Path) -> None:
    """An incomplete linked directory cannot become a plausible release contract."""
    _write_inputs(tmp_path)
    directory = json.loads((tmp_path / "routine_directory.json").read_text())
    del directory["routines"]["xip"]["page"]
    (tmp_path / "routine_directory.json").write_text(json.dumps(directory))

    with pytest.raises(ValueError, match="xip lacks a complete placement"):
        generate_expansion_contracts.generate(tmp_path)
