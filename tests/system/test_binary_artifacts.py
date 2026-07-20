"""System tests for binary artifacts and D64 packaging (T9.4).

Tests verify D64 contents, PRG headers, and binary artifact sizes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from package_d64 import (
    _d64_offset,
    validate_d64,
    validate_dual_d64_release,
    validate_prg_header,
    validate_reu_patch,
    resolve_c1541,
)

ROOT = Path(__file__).resolve().parents[2]


def _configured_c1541() -> Path | None:
    """Return the optional explicitly configured vice-next disk utility."""
    selected = os.environ.get("VICE_C1541")
    return Path(selected) if selected else None


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
        names = [entry["name"] for entry in files]
        assert "basicv3" in names
        assert "georam" in names
        assert "reu" in names
        assert all(entry["type"] == "PRG" for entry in files)
        # basicv3 is the always-mapped resident loader; georam is the 64 KiB
        # sidecar; reu is the small patch. Bounds follow D64_SECTOR_BOUNDS.
        assert 1 <= files[0]["size_sectors"] <= 250
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
        c1541 = _configured_c1541()
        if c1541 is None:
            pytest.skip("optional VICE_C1541 is not configured")
        assert c1541.is_file(), "configured VICE_C1541 must be a real file"
        disk = ROOT / "build" / "compiler.d64"
        extracted = tmp_path / "georam.prg"
        subprocess.run(
            [
                str(c1541),
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


def test_c1541_resolution_uses_only_explicit_vice_next_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Packaging chooses direct D64 output unless VICE_C1541 names a file."""
    monkeypatch.delenv("VICE_C1541", raising=False)
    assert resolve_c1541() == ""
    configured = tmp_path / "c1541.exe"
    configured.write_bytes(b"tool")
    monkeypatch.setenv("VICE_C1541", str(configured))
    assert resolve_c1541() == str(configured)
    monkeypatch.setenv("VICE_C1541", str(tmp_path / "missing.exe"))
    with pytest.raises(FileNotFoundError, match="VICE_C1541"):
        resolve_c1541()


def test_direct_d64_builder_preserves_free_bam_sectors_for_device_writes() -> None:
    """Release D64 must advertise free sectors so KERNAL SAVE can persist."""
    disk = ROOT / "build" / "compiler.d64"
    if not disk.exists():
        pytest.skip("build/compiler.d64 not found")
    data = disk.read_bytes()
    bam = _d64_offset(18, 0)
    # Track 35 is unused by the release payload and must be writable.  The
    # BAM's first byte for that track is its available-sector count; its next
    # three bytes are the low-bit-first free-sector bitmap.
    track_35_bam = bam + 4 + (35 - 1) * 4
    track_35_free_count = data[track_35_bam]
    assert track_35_free_count == 17
    assert data[track_35_bam + 1 : track_35_bam + 4] == b"\xff\xff\x01"


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

    def test_basicv3_prg_contains_post_init_ready_banner(self) -> None:
        """Cold-init status text must ship in the resident loader PRG."""
        path = ROOT / "build" / "basicv3.prg"
        if not path.exists():
            pytest.skip("build/basicv3.prg not found")
        assert b"BASIC V3 READY\x8d" in path.read_bytes()

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

    def test_georam_page_image_contains_linked_routine_bytes(self) -> None:
        """The generated page image contains linked routine bytes, not fill padding.

        Phase 14 places every expansion routine at a generated geoRAM block/page
        offset (see ``routine_directory.json``). This checks that the installed
        ``wedge_parse`` bytes at that generated placement are real routine code
        (non-uniform, non-zero) and that the page model addresses the image.
        """
        directory = json.loads(
            (ROOT / "build" / "routine_directory.json").read_text()
        )
        target = directory["routines"]["wedge_parse"]
        payload = (ROOT / "build" / "georam.bin").read_bytes()[2:]
        georam_offset = (target["block"] * 64 + target["page"]) * 256 + target["offset"]
        # The routine directory must land inside the installed 64 KiB image.
        assert georam_offset + 16 <= len(payload)
        routine_bytes = payload[georam_offset : georam_offset + 16]
        # The page image must not be a uniform fill at the routine placement.
        assert len(set(routine_bytes)) >= 3
        assert sum(value != 0 for value in routine_bytes) >= 8
        # The overall image must contain real linked content, not zeros/fill.
        assert len(set(payload[: 32 * 1024])) >= 3
        assert sum(value != 0 for value in payload) >= 10_000
        assert payload != bytes(len(payload))


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
