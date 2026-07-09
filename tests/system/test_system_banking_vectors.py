"""System contract tests for banking policy and hardware vectors."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
LINKER_POLICY = ROOT / "manifests" / "linker_policy.json"
COMPILER_BIN = ROOT / "build" / "compiler.bin"
COMPILER_LBL = ROOT / "build" / "compiler.lbl"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        pytest.skip(f"{path.name} not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


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
class TestBankingPolicy:
    """The CPU-port banking policy is pinned to the stock-compatible values."""

    def test_cpu_port_values_are_pinned(self) -> None:
        """Policy values must match the project-wide banking contract."""
        policy = _load_json(LINKER_POLICY)
        banking = policy.get("banking_policy", {})
        assert banking["default_cpu_port_val"] == 53
        assert banking["all_ram_cpu_port_val"] == 52
        assert banking["kernal_rom_visible_val"] == 55

    def test_high_memory_vector_area_is_reserved(self) -> None:
        """The top-of-memory tail remains reserved for NMI/RESET/IRQ vectors."""
        policy = _load_json(LINKER_POLICY)
        vectors = next(
            area for area in policy.get("memory_areas", []) if area["name"] == "VECTORS"
        )
        assert vectors["start"] == 0xFFFA
        assert vectors["size"] == 6


@pytest.mark.system
@pytest.mark.static
class TestVectorAndEntryContracts:
    """PRG header and exported entry labels stay aligned with the map."""

    def test_prg_header_loads_at_basic_origin(self) -> None:
        """The packaged PRG header must point at the BASIC start address."""
        data = COMPILER_BIN.read_bytes()
        assert len(data) >= 2
        load_address = data[0] | (data[1] << 8)
        assert load_address == 0x0801

    def test_entry_labels_match_the_linked_start_addresses(self) -> None:
        """The label file keeps the public start addresses stable."""
        labels = _parse_labels(COMPILER_LBL.read_text(encoding="utf-8"))
        assert labels["compiler2_entry"] == 0x0801
        assert labels["loader_entry"] == 0x080D

    def test_no_label_resides_in_reserved_vector_tail(self) -> None:
        """The generated label file must not place runtime code in $FFF9-$FFFF."""
        labels = _parse_labels(COMPILER_LBL.read_text(encoding="utf-8"))
        reserved = [
            name for name, address in labels.items() if 0xFFF9 <= address <= 0xFFFF
        ]
        assert reserved == []
