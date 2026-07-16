"""System contract tests for the generated memory map."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPILER_MAP = ROOT / "build" / "compiler.map"
ZP_ALLOCATION = ROOT / "build" / "zp_allocation.json"
ZP_MANIFEST = ROOT / "manifests" / "zero_page.json"


def _load_text(path: Path) -> str:
    if not path.exists():
        pytest.skip(f"{path.name} not found")
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        pytest.skip(f"{path.name} not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _parse_segments(map_text: str) -> list[dict[str, Any]]:
    lines = map_text.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("Name") and "Start" in line and "End" in line
        ),
        None,
    )
    if header_index is None:
        pytest.fail("compiler.map does not contain a Segment list block")
    segments: list[dict[str, Any]] = []
    segment_re = re.compile(
        r"^(?P<name>[A-Z0-9_]+)\s+"
        r"(?P<start>[0-9A-F]{6})\s+"
        r"(?P<end>[0-9A-F]{6})\s+"
        r"(?P<size>[0-9A-F]{6})\s+"
        r"(?P<align>[0-9A-F]+)$"
    )
    for line in lines[header_index + 2 :]:
        stripped = line.strip()
        if not stripped:
            break
        if stripped.startswith("Exports list") or stripped.startswith("Imports list"):
            break
        match = segment_re.match(stripped)
        if match is None:
            continue
        segments.append(
            {
                "name": match.group("name"),
                "start": int(match.group("start"), 16),
                "end": int(match.group("end"), 16),
                "size": int(match.group("size"), 16),
            }
        )
    if not segments:
        pytest.fail("No linker segments parsed from compiler.map")
    return segments


@pytest.mark.system
@pytest.mark.static
@pytest.mark.smoke
class TestGeneratedMemoryMap:
    """Cross-artifact checks for the generated linked image layout."""

    def test_segments_are_sorted_and_non_overlapping(self) -> None:
        """Segments must appear in ascending order and not overlap."""
        segments = _parse_segments(_load_text(COMPILER_MAP))
        previous_end = -1
        previous_name = "<start>"
        for segment in segments:
            assert segment["start"] > previous_end, (
                f"{segment['name']} starts at {segment['start']:04X}, "
                f"overlapping {previous_name} ending at {previous_end:04X}"
            )
            previous_end = int(segment["end"])
            previous_name = str(segment["name"])

    def test_code_segment_stays_out_of_io_and_vector_space(self) -> None:
        """Loader-resident payload stays below I/O; cold high code avoids vectors."""
        segments = _parse_segments(_load_text(COMPILER_MAP))
        # Edit/compile-only cold code lives in RAM_HIGH ($E000+) per
        # tools/linker_config.py and docs/MEMORY_BUDGETS.md: HIBASIC plus
        # EDITOR(_PINNED)/WEDGE/COMPRESSOR. GeoRAM XIP pages link at the
        # $DE00 window into georam.bin and are not loader-resident payload.
        cold_high = {
            "HIBASIC",
            "EDITOR_PINNED",
            "EDITOR",
            "WEDGE",
            "COMPRESSOR",
        }
        payload_segments = []
        for segment in segments:
            name = str(segment["name"])
            start = int(segment["start"])
            end = int(segment["end"])
            assert end < 0xFFF9
            if name.startswith("GEORAM_PAGE") or start == 0xDE00:
                continue
            if name in cold_high or start >= 0xE000:
                # Named cold-high segments and any other RAM_HIGH placement.
                assert start >= 0xE000
                continue
            payload_segments.append(segment)
        assert payload_segments
        highest_payload_end = max(int(segment["end"]) for segment in payload_segments)
        assert highest_payload_end < 0xD000

    def test_zero_page_allocation_starts_at_reserved_base(self) -> None:
        """The generated zero-page allocation uses the reserved page only."""
        allocation = _load_json(ZP_ALLOCATION)
        manifest = _load_json(ZP_MANIFEST)
        widths = {node["name"]: node["size"] for node in manifest.get("nodes", [])}
        zp_region = next(
            region
            for region in _load_json(ROOT / "manifests" / "linker_policy.json")[
                "memory_areas"
            ]
            if region["name"] == "ZP"
        )
        starts = []
        ends = []
        addresses: set[int] = set()
        for name, raw in allocation.get("allocation", {}).items():
            assert isinstance(raw, str) and raw.startswith("$")
            start = int(raw[1:], 16)
            starts.append(start)
            ends.append(start + widths[name] - 1)
            addresses.update(range(start, start + widths[name]))
        assert starts
        assert min(starts) >= zp_region["start"]
        assert max(ends) < zp_region["start"] + zp_region["size"]
        assert 0x0000 not in addresses
        assert 0x0001 not in addresses

    def test_resident_editor_scratch_does_not_alias_georam_mirror(self) -> None:
        """Resident line capture must preserve the persistent GeoRAM mirror."""
        data = _load_json(ZP_ALLOCATION)
        allocation = {
            name: int(address.removeprefix("$"), 16)
            for name, address in data["allocation"].items()
        }
        manifest = _load_json(ZP_MANIFEST)
        sizes = {node["name"]: node["size"] for node in manifest["nodes"]}
        mirror = {"zp_gr_block", "zp_gr_page", "zp_gr_ctx_sp", "zp_gr_call_id"}
        gate_callers = {
            "zp_linebuf",
            "zp_line_len",
            "zp_quotemode",
            "zp_crsr_x",
            "zp_crsr_y",
            "zp_crsr_vis",
            "zp_src",
            "zp_dest",
            "zp_stmt_arg",
            "zp_stmt_op",
            "zp_tmp1",
            "zp_tmp2",
            "zp_tmp3",
            "zp_tmp4",
        }

        def occupied(name: str) -> set[int]:
            return set(range(allocation[name], allocation[name] + sizes[name]))

        for editor_name in gate_callers:
            for mirror_name in mirror:
                assert occupied(editor_name).isdisjoint(
                    occupied(mirror_name)
                ), f"{editor_name} aliases persistent {mirror_name}"

    def test_break_stop_flag_does_not_alias_error_number(self) -> None:
        """BREAK must preserve STOP state while publishing ERR_OK."""
        allocation = _load_json(ZP_ALLOCATION)["allocation"]
        assert allocation["zp_stop_flag"] != allocation["zp_errnum"]
