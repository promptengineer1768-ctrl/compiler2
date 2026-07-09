"""Tests for tools/linker_config.py — ld65 config file generator.

Covers: policy manifest loading, segment and banking emission, output structure,
and vector address assertions.
"""

from __future__ import annotations


import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import linker_config

MANIFESTS_DIR = Path(__file__).resolve().parents[2] / "manifests"
POLICY_PATH = MANIFESTS_DIR / "linker_policy.json"


def _require_policy() -> None:
    if not POLICY_PATH.exists():
        pytest.skip("linker_policy.json not present; T0.2 prerequisite unmet")


class TestLoadPolicy:
    """Tests for linker_config.load_linker_policy."""

    def test_loads_memory_areas(self) -> None:
        _require_policy()
        policy = linker_config.load_linker_policy(str(POLICY_PATH))
        assert "memory_areas" in policy or "fixed_areas" in policy

    def test_missing_raises(self) -> None:
        with pytest.raises((FileNotFoundError, OSError)):
            linker_config.load_linker_policy("/nonexistent/linker_policy.json")


class TestConfigGeneration:
    """Tests for linker_config.generate_cfg."""

    def test_produces_nonempty_cfg(self, tmp_path: Path) -> None:
        _require_policy()
        policy = linker_config.load_linker_policy(str(POLICY_PATH))
        content = linker_config.generate_cfg(policy, num_georam_pages=4)
        assert len(content.strip()) > 0

    def test_cfg_contains_memory_section(self, tmp_path: Path) -> None:
        _require_policy()
        policy = linker_config.load_linker_policy(str(POLICY_PATH))
        content = linker_config.generate_cfg(policy, num_georam_pages=4)
        assert "MEMORY" in content

    def test_cfg_contains_segments_section(self, tmp_path: Path) -> None:
        _require_policy()
        policy = linker_config.load_linker_policy(str(POLICY_PATH))
        content = linker_config.generate_cfg(policy, num_georam_pages=4)
        assert "SEGMENTS" in content

    def test_zp_segment_present(self, tmp_path: Path) -> None:
        _require_policy()
        policy = linker_config.load_linker_policy(str(POLICY_PATH))
        content = linker_config.generate_cfg(policy, num_georam_pages=4)
        assert "ZEROPAGE" in content or "ZP" in content

    def test_georam_pages_in_output(self, tmp_path: Path) -> None:
        _require_policy()
        policy = linker_config.load_linker_policy(str(POLICY_PATH))
        content = linker_config.generate_cfg(policy, num_georam_pages=2)
        assert "GEORAM0" in content and "GEORAM1" in content

    def test_protected_ranges_follow_linker_policy(self) -> None:
        """POKE protection constants must derive from the canonical RAM policy."""
        policy = linker_config.load_linker_policy(str(POLICY_PATH))
        content = linker_config.render_protected_ranges(policy)
        assert "compiler_protected_start = $0801" in content
        assert "compiler_protected_end = $D000" in content
        assert "compiler_high_guard_start = $FFF9" in content


class TestConfigFileWrite:
    """Tests that generate_cfg output can be written to disk."""

    def test_write_to_file(self, tmp_path: Path) -> None:
        _require_policy()
        policy = linker_config.load_linker_policy(str(POLICY_PATH))
        content = linker_config.generate_cfg(policy, num_georam_pages=4)
        out = tmp_path / "compiler.cfg"
        out.write_text(content, encoding="utf-8")
        assert out.exists()
        assert out.stat().st_size > 0


class TestPolicyValidation:
    """Negative coverage for overlap and vector policy contracts."""

    def test_validate_no_overlap_rejects_memory_collision(self) -> None:
        policy = {
            "memory_areas": [
                {"name": "A", "start": 0x1000, "size": 0x100},
                {"name": "B", "start": 0x1080, "size": 0x100},
            ],
            "fixed_segments": [],
        }
        assert linker_config.validate_no_overlap(policy) == [
            "memory areas A and B overlap at $1080-$10FF"
        ]

    def test_validate_vectors_rejects_shifted_reservation(self) -> None:
        policy = {
            "memory_areas": [{"name": "VECTORS", "start": 0xFFF8, "size": 8}],
            "fixed_segments": [
                {
                    "name": "VECTORS",
                    "memory_area": "VECTORS",
                    "start": 0xFFF8,
                    "max_size": 8,
                }
            ],
        }
        assert linker_config.validate_vectors(policy) == [
            "VECTORS memory area must cover $FFFA-$FFFF",
            "VECTORS segment must map exactly to $FFFA-$FFFF",
        ]

    def test_checked_in_policy_is_valid(self) -> None:
        policy = linker_config.load_linker_policy(str(POLICY_PATH))
        assert linker_config.validate_no_overlap(policy) == []
        assert linker_config.validate_vectors(policy) == []

    def test_write_config_normalizes_line_endings(self, tmp_path: Path) -> None:
        output = tmp_path / "nested" / "compiler.cfg"
        linker_config.write_config("A\r\nB\rC\n", str(output))
        assert output.read_bytes() == b"A\nB\nC\n"
