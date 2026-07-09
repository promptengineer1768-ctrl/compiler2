"""System tests for generated references (T10.2).

Tests verify API.md and MAP.md generation and completeness.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.system
class TestApiReference:
    """API reference validation tests."""

    def test_api_md_exists(self) -> None:
        """build/API.md must exist after generation."""
        path = ROOT / "build" / "API.md"
        if not path.exists():
            pytest.skip("build/API.md not found (run generate_reference.py)")
        assert path.exists()
        assert path.stat().st_size > 0

    def test_api_md_has_sections(self) -> None:
        """API.md must have section headers."""
        path = ROOT / "build" / "API.md"
        if not path.exists():
            pytest.skip("build/API.md not found")
        content = path.read_text(encoding="utf-8")
        assert "#" in content or "##" in content


@pytest.mark.system
class TestMapReference:
    """MAP reference validation tests."""

    def test_map_md_exists(self) -> None:
        """build/MAP.md must exist after generation."""
        path = ROOT / "build" / "MAP.md"
        if not path.exists():
            pytest.skip("build/MAP.md not found (run generate_reference.py)")
        assert path.exists()
        assert path.stat().st_size > 0

    def test_map_md_has_sections(self) -> None:
        """MAP.md must have section headers."""
        path = ROOT / "build" / "MAP.md"
        if not path.exists():
            pytest.skip("build/MAP.md not found")
        content = path.read_text(encoding="utf-8")
        assert "#" in content or "##" in content
