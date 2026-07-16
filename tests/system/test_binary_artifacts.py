"""System tests for binary artifacts and D64 packaging (T9.4).

Tests verify D64 contents, PRG headers, and binary artifact sizes.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from package_d64 import (
    validate_d64,
    validate_dual_d64_release,
    validate_prg_header,
    validate_reu_patch,
)
from populate_georam import COLD_SEGMENTS

ROOT = Path(__file__).resolve().parents[2]
C1541 = (
    ROOT.parent
    / "tools"
    / "vice-mcp"
    / "dist"
    / "HeadlessVICE-windows-x86_64"
    / "c1541.exe"
)


@pytest.mark.system
class TestD64Contents:
    """D64 contents validation tests."""

    def test_d64_exists(self) -> None:
        """build/compiler.d64 must exist after packaging."""
        path = ROOT / "build" / "compiler.d64"
        if not path.exists():
            pytest.skip("build/compiler.d64 not found (run package_d64.py)")
        assert path.exists()
        assert path.stat().st_size > 0

    def test_d64_standard_size(self) -> None:
        """D64 must be the standard 35-track image size."""
        path = ROOT / "build" / "compiler.d64"
        if not path.exists():
            pytest.skip("build/compiler.d64 not found")
        assert path.stat().st_size == 174848

    def test_d64_uses_lowercase_release_names(self) -> None:
        """Release directory names are dual-device basicv3 + georam + reu."""
        path = ROOT / "build" / "compiler.d64"
        if not path.exists():
            pytest.skip("build/compiler.d64 not found")
        manifest = validate_d64(str(path))
        assert manifest["disk_title"] == "compiler2"
        assert manifest.get("valid") is True
        files = manifest["files"]
        assert [entry["name"] for entry in files] == ["basicv3", "georam", "reu"]
        assert all(entry["type"] == "PRG" for entry in files)
        assert 1 <= files[0]["size_sectors"] <= 100
        assert 8 <= files[1]["size_sectors"] <= 259
        assert 1 <= files[2]["size_sectors"] <= 16

    def test_dual_d64_release_headers_and_sizes(self) -> None:
        """Host sidecars and D64 satisfy dual-device header/size contracts."""
        d64 = ROOT / "build" / "compiler.d64"
        basicv3 = ROOT / "build" / "basicv3.prg"
        georam = ROOT / "build" / "georam.bin"
        reu = ROOT / "build" / "reu.bin"
        missing = [p for p in (d64, basicv3, georam, reu) if not p.exists()]
        if missing:
            pytest.skip(f"release artifacts missing: {missing}")
        assert validate_dual_d64_release(d64, basicv3, georam, reu) == []
        assert validate_prg_header(str(basicv3)) == []
        assert validate_reu_patch(reu) == []
        assert georam.stat().st_size >= 65538
        assert d64.stat().st_size == 174848

    def test_d64_georam_is_exact_packaged_sidecar(self, tmp_path: Path) -> None:
        """The D64 georam file exactly matches the selected build sidecar."""
        if not C1541.is_file():
            pytest.skip("c1541 is not installed")
        disk = ROOT / "build" / "compiler.d64"
        extracted = tmp_path / "georam.prg"
        subprocess.run(
            [
                str(C1541),
                "-attach",
                str(disk),
                "-read",
                "georam",
                str(extracted),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        compressed = ROOT / "build" / "GEORAM_compressed.prg"
        raw = ROOT / "build" / "georam.bin"
        actual = extracted.read_bytes()
        candidates = []
        if compressed.exists():
            candidates.append(compressed.read_bytes())
        if raw.exists():
            candidates.append(raw.read_bytes())
        assert candidates
        assert actual in candidates
        if actual[:6] == b"\x00\xdeCGS1":
            assert compressed.exists()
        else:
            assert actual[:2] == b"\x00\xde"
            assert len(actual) == 65538


@pytest.mark.system
class TestPrgHeader:
    """PRG header validation tests."""

    def test_basicv3_prg_exists(self) -> None:
        """build/basicv3.prg must exist."""
        path = ROOT / "build" / "basicv3.prg"
        if not path.exists():
            pytest.skip("build/basicv3.prg not found")
        assert path.exists()

    def test_basicv3_prg_load_address(self) -> None:
        """basicv3.prg must load at BASIC start ($0801)."""
        path = ROOT / "build" / "basicv3.prg"
        if not path.exists():
            pytest.skip("build/basicv3.prg not found")
        data = path.read_bytes()
        assert len(data) >= 2
        load_addr = data[0] | (data[1] << 8)
        assert load_addr == 0x0801

    def test_basicv3_prg_basic_loader(self) -> None:
        """basicv3.prg must contain the one-line BASIC SYS2061 loader."""
        path = ROOT / "build" / "basicv3.prg"
        if not path.exists():
            pytest.skip("build/basicv3.prg not found")
        data = path.read_bytes()
        assert data[2:14] == bytes(
            [
                0x0B,
                0x08,
                0xEA,
                0x07,
                0x9E,
                0x32,
                0x30,
                0x36,
                0x31,
                0x00,
                0x00,
                0x00,
            ]
        )

    def test_georam_bin_exists(self) -> None:
        """build/georam.bin must exist."""
        path = ROOT / "build" / "georam.bin"
        if not path.exists():
            pytest.skip("build/georam.bin not found")
        assert path.exists()

    def test_georam_bin_size(self) -> None:
        """georam.bin must contain a fake PRG header and 64KB payload."""
        path = ROOT / "build" / "georam.bin"
        if not path.exists():
            pytest.skip("build/georam.bin not found")
        assert path.stat().st_size >= 65538
        data = path.read_bytes()
        assert data[:2] == b"\x00\xde"

    def test_georam_payload_contains_linked_cold_bytes(self) -> None:
        """geoRAM contains linked cold/compiler bytes, not fill-only padding."""
        map_text = (ROOT / "build" / "compiler.map").read_text()
        matches = {
            match.group(1): (int(match.group(2), 16), int(match.group(3), 16))
            for match in re.finditer(
                r"^([A-Z0-9_]+)\s+([0-9A-Fa-f]{6})\s+"
                r"[0-9A-Fa-f]{6}\s+([0-9A-Fa-f]{6})",
                map_text,
                re.MULTILINE,
            )
        }
        compiler = (ROOT / "build" / "compiler.bin").read_bytes()
        load_address = int.from_bytes(compiler[:2], "little")
        hibasic = (ROOT / "build" / "hibasic.bin").read_bytes()
        linked_parts = []
        for name in COLD_SEGMENTS:
            start, size = matches[name]
            # Cold segments may be placed in RAM_HIGH ($E000+) / hibasic.bin.
            if start >= 0xE000 or name == "HIBASIC":
                offset = start - 0xE000
                linked_parts.append(hibasic[offset : offset + size])
            else:
                offset = 2 + start - load_address
                linked_parts.append(compiler[offset : offset + size])
        linked = b"".join(linked_parts)
        payload = (ROOT / "build" / "georam.bin").read_bytes()[2:]
        common = min(len(linked), len(payload))
        matching = sum(
            1 for left, right in zip(payload[:common], linked[:common]) if left == right
        )
        assert matching >= common // 2
        assert len(set(payload[:common])) >= 3
        assert sum(value != 0 for value in payload) >= 10_000
        assert payload[:common] != bytes(common)

    def test_georam_directory_points_at_installed_routine_bytes(self) -> None:
        """Generated routine directory entries must match installed geoRAM bytes."""
        directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
        target = directory["routines"]["wedge_parse"]
        lbl_text = (ROOT / "build" / "compiler.lbl").read_text()
        match = re.search(r"^al\s+([0-9A-Fa-f]{6})\s+\.wedge_parse$", lbl_text, re.M)
        assert match is not None
        linked_address = int(match.group(1), 16)
        compiler = (ROOT / "build" / "compiler.bin").read_bytes()
        load_address = int.from_bytes(compiler[:2], "little")
        hibasic = (ROOT / "build" / "hibasic.bin").read_bytes()
        if linked_address >= 0xE000:
            linked_bytes = hibasic[
                linked_address - 0xE000 : linked_address - 0xE000 + 16
            ]
        else:
            linked_offset = 2 + linked_address - load_address
            linked_bytes = compiler[linked_offset : linked_offset + 16]
        assert len(linked_bytes) == 16

        payload = (ROOT / "build" / "georam.bin").read_bytes()[2:]
        georam_offset = (target["block"] * 64 + target["page"]) * 256 + target["offset"]
        assert payload[georam_offset : georam_offset + 16] == linked_bytes


@pytest.mark.system
class TestBinaryArtifacts:
    """Binary artifact validation tests."""

    def test_compiler_bin_exists(self) -> None:
        """build/compiler.bin must exist."""
        path = ROOT / "build" / "compiler.bin"
        if not path.exists():
            pytest.skip("build/compiler.bin not found")
        assert path.exists()
        assert path.stat().st_size > 0

    def test_compiler_bin_prg_header(self) -> None:
        """compiler.bin must have PRG header."""
        path = ROOT / "build" / "compiler.bin"
        if not path.exists():
            pytest.skip("build/compiler.bin not found")
        data = path.read_bytes()
        assert len(data) >= 2
        load_addr = data[0] | (data[1] << 8)
        # Load address should be reasonable (not zero)
        assert load_addr > 0

    def test_segments_directory_exists(self) -> None:
        """build/segments/ directory must exist."""
        path = ROOT / "build" / "segments"
        if not path.exists():
            pytest.skip("build/segments/ not found")
        assert path.is_dir()
