"""System contract tests for linker policy and high-level layout."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
LINKER_POLICY = ROOT / "manifests" / "linker_policy.json"
COMPILER_MAP = ROOT / "build" / "compiler.map"
COMPILER_LBL = ROOT / "build" / "compiler.lbl"


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


def _parse_labels(lbl_text: str) -> dict[str, int]:
    labels: dict[str, int] = {}
    for line in lbl_text.splitlines():
        match = re.match(r"^al\s+([0-9A-F]{6})\s+\.(\S+)$", line.strip())
        if match is not None:
            labels[match.group(2)] = int(match.group(1), 16)
    return labels


@pytest.mark.system
@pytest.mark.static
@pytest.mark.smoke
class TestLinkerPolicy:
    """Policy file and generated-linker contract tests."""

    def test_memory_areas_are_canonical(self) -> None:
        """The linker policy reserves the canonical memory areas."""
        policy = _load_json(LINKER_POLICY)
        areas = policy.get("memory_areas", [])
        names = [area.get("name") for area in areas]
        assert names == ["ZP", "RAM", "IO", "RAM_HIGH", "VECTORS"]
        assert [area.get("start") for area in areas] == [
            0x0002,
            0x0801,
            0xD000,
            0xE000,
            0xFFFA,
        ]
        assert [area.get("size") for area in areas] == [254, 51199, 4096, 8184, 6]

    def test_fixed_segments_fit_declared_memory_areas(self) -> None:
        """Fixed segments must stay inside the declared memory policy."""
        policy = _load_json(LINKER_POLICY)
        areas = {area["name"]: area for area in policy.get("memory_areas", [])}
        fixed_segments = policy.get("fixed_segments", [])
        assert {segment["name"] for segment in fixed_segments} == {
            "LOADER",
            "RESIDENT",
            "COMPILER_BSS",
            "VECTORS",
        }

        loader = next(
            segment for segment in fixed_segments if segment["name"] == "LOADER"
        )
        assert loader["memory_area"] == "RAM"
        assert loader["start"] == areas["RAM"]["start"]
        assert loader["max_size"] == 256

        vectors = next(
            segment for segment in fixed_segments if segment["name"] == "VECTORS"
        )
        assert vectors["memory_area"] == "VECTORS"
        assert vectors["start"] == areas["VECTORS"]["start"]
        assert vectors["max_size"] == areas["VECTORS"]["size"]

    def test_banking_policy_values_are_canonical(self) -> None:
        """The CPU-port banking policy matches the stock-compatible mapping."""
        policy = _load_json(LINKER_POLICY)
        banking = policy.get("banking_policy", {})
        assert banking == {
            "default_cpu_port_val": 53,
            "all_ram_cpu_port_val": 52,
            "kernal_rom_visible_val": 55,
        }


@pytest.mark.system
@pytest.mark.static
class TestGeneratedLinkerOutputs:
    """Generated map and label artifacts stay aligned with policy."""

    def test_loader_segment_starts_at_program_origin(self) -> None:
        """The linked loader segment begins at the BASIC PRG load address."""
        map_text = COMPILER_MAP.read_text(encoding="utf-8")
        segments = _parse_segments(map_text)
        loader = next(segment for segment in segments if segment["name"] == "LOADER")
        resident = next(
            segment for segment in segments if segment["name"] == "RESIDENT"
        )
        assert loader["start"] == 0x0801
        assert loader["end"] < resident["start"]
        assert loader["size"] <= 0x0100

    def test_loader_entry_label_matches_exported_start(self) -> None:
        """The label file records the loader entry exported by the map."""
        labels = _parse_labels(COMPILER_LBL.read_text(encoding="utf-8"))
        assert labels["compiler2_entry"] == 0x0801
        assert labels["loader_entry"] == 0x080D
