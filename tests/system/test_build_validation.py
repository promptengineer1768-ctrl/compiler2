"""System tests for build validation (T10.1).

Tests verify toolchain versions, manifest schemas, and cross-artifact consistency.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.system
@pytest.mark.smoke
class TestToolchainVersions:
    """Tool version validation tests."""

    def test_ca65_exists(self) -> None:
        """ca65 assembler must exist."""
        ca65_path = ROOT.parent / "tools" / "ca65.exe"
        if not ca65_path.exists():
            ca65_path = ROOT / "tools" / "ca65.exe"
        if not ca65_path.exists():
            pytest.skip("ca65.exe not found")
        assert ca65_path.exists()

    def test_ld65_exists(self) -> None:
        """ld65 linker must exist."""
        ld65_path = ROOT.parent / "tools" / "ld65.exe"
        if not ld65_path.exists():
            ld65_path = ROOT / "tools" / "ld65.exe"
        if not ld65_path.exists():
            pytest.skip("ld65.exe not found")
        assert ld65_path.exists()


@pytest.mark.system
class TestManifestSchemas:
    """Manifest schema validation tests."""

    def test_routines_json_valid(self) -> None:
        """routines.json must be valid JSON."""
        path = ROOT / "manifests" / "routines.json"
        if not path.exists():
            pytest.skip("manifests/routines.json not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_zero_page_json_valid(self) -> None:
        """zero_page.json must be valid JSON."""
        path = ROOT / "manifests" / "zero_page.json"
        if not path.exists():
            pytest.skip("manifests/zero_page.json not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_arenas_json_valid(self) -> None:
        """arenas.json must be valid JSON."""
        path = ROOT / "manifests" / "arenas.json"
        if not path.exists():
            pytest.skip("manifests/arenas.json not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_runtime_abi_json_valid(self) -> None:
        """runtime_abi.json must be valid JSON."""
        path = ROOT / "manifests" / "runtime_abi.json"
        if not path.exists():
            pytest.skip("manifests/runtime_abi.json not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)


@pytest.mark.system
class TestBuildArtifacts:
    """Build artifact validation tests."""

    def test_compiler_bin_exists(self) -> None:
        """build/compiler.bin must exist after build."""
        path = ROOT / "build" / "compiler.bin"
        if not path.exists():
            pytest.skip("build/compiler.bin not found (run build.ps1 first)")
        assert path.exists()
        assert path.stat().st_size > 0

    def test_compiler_map_exists(self) -> None:
        """build/compiler.map must exist after build."""
        path = ROOT / "build" / "compiler.map"
        if not path.exists():
            pytest.skip("build/compiler.map not found (run build.ps1 first)")
        assert path.exists()

    def test_compiler_lbl_exists(self) -> None:
        """build/compiler.lbl must exist after build."""
        path = ROOT / "build" / "compiler.lbl"
        if not path.exists():
            pytest.skip("build/compiler.lbl not found (run build.ps1 first)")
        assert path.exists()

    def test_zp_symbols_inc_exists(self) -> None:
        """build/zp_symbols.inc must exist."""
        path = ROOT / "build" / "zp_symbols.inc"
        if not path.exists():
            pytest.skip("build/zp_symbols.inc not found")
        assert path.exists()

    def test_routine_directory_exists(self) -> None:
        """build/routine_directory.json must exist."""
        path = ROOT / "build" / "routine_directory.json"
        if not path.exists():
            pytest.skip("build/routine_directory.json not found")
        assert path.exists()

    def test_manifest_records_toolchain_and_reference_checksums(self) -> None:
        """The final manifest binds tool versions and generated references."""
        manifest = json.loads(
            (ROOT / "build" / "build_manifest.json").read_text(encoding="utf-8")
        )

        toolchain = manifest["toolchain"]
        assert "V2.19" in toolchain["ca65"]["version"]
        assert "V2.19" in toolchain["ld65"]["version"]

        artifacts = manifest["artifacts"]
        for name in ("API.md", "MAP.md"):
            payload = (ROOT / "build" / name).read_bytes()
            assert artifacts[name]["size"] == len(payload)
            assert artifacts[name]["sha256"] == hashlib.sha256(payload).hexdigest()


@pytest.mark.system
class TestSizeReport:
    """Size report validation tests."""

    def test_size_report_exists(self) -> None:
        """build/size_report.json must exist after build."""
        path = ROOT / "build" / "size_report.json"
        if not path.exists():
            pytest.skip("build/size_report.json not found (run build.ps1 first)")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "resident_bytes" in data or "segments" in data
