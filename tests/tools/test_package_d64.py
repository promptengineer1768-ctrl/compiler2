"""Tests for tools/package_d64.py — dual-device D64 packager and REU patch."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import package_d64


def test_validate_prg_header_accepts_canonical_loader(tmp_path: Path) -> None:
    """The PRG validator accepts the production fallback loader."""
    payload = tmp_path / "compile.bin"
    payload.write_bytes(b"\xea")
    prg = tmp_path / "basicv3.prg"
    from prepare_compressor_segments import build_simple_prg

    build_simple_prg(str(payload), str(prg))
    assert package_d64.validate_prg_header(str(prg)) == []


def test_validate_prg_header_rejects_wrong_load_address(tmp_path: Path) -> None:
    """The PRG validator rejects a non-$0801 artifact."""
    prg = tmp_path / "bad.prg"
    prg.write_bytes(b"\x00\x20" + b"\x00" * 20)
    assert package_d64.validate_prg_header(str(prg)) == [
        "PRG load address is not $0801"
    ]


def test_build_reu_patch_envelope_pairs_with_georam(tmp_path: Path) -> None:
    """REU patch records GEORAM fingerprint and omits geoRAM capacity."""
    georam = tmp_path / "georam.bin"
    georam.write_bytes(b"\x00\xde" + b"\x11\x22\x33\x44" * 16)
    reu = tmp_path / "reu.bin"

    manifest = package_d64.build_reu_patch(georam, reu)

    assert reu.exists()
    assert package_d64.validate_reu_patch(reu) == []
    assert manifest["magic"] == "C2RP"
    assert manifest["min_reu_capacity_kib"] == 512
    assert manifest["has_georam_capacity_field"] is False
    assert "georam_capacity" not in manifest
    assert len(manifest["georam_sha256"]) == 64
    loader = json.loads((tmp_path / "reu_loader_manifest.json").read_text())
    assert loader["georam_sha256"] == manifest["georam_sha256"]
    data = reu.read_bytes()
    assert data[:4] == b"C2RP"


def test_validate_reu_patch_rejects_corrupt_crc(tmp_path: Path) -> None:
    """CRC mismatch is a hard validation failure."""
    georam = tmp_path / "georam.bin"
    georam.write_bytes(b"\x00\xde" + b"\xaa" * 32)
    reu = tmp_path / "reu.bin"
    package_d64.build_reu_patch(georam, reu)
    raw = bytearray(reu.read_bytes())
    raw[-1] ^= 0xFF
    reu.write_bytes(raw)
    assert any("CRC" in err for err in package_d64.validate_reu_patch(reu))


class TestBuildD64:
    """Tests for package_d64.build_d64."""

    def test_calls_c1541_format(self, tmp_path: Path) -> None:
        """build_d64 invokes c1541 with the -format subcommand."""
        fake_c1541 = str(tmp_path / "c1541.exe")
        basicv3 = tmp_path / "basicv3.prg"
        basicv3.write_bytes(b"\x01\x08" + b"\xea" * 32)
        georam = tmp_path / "georam.bin"
        georam.write_bytes(b"\x00" * 64)
        reu = tmp_path / "reu.bin"
        package_d64.build_reu_patch(georam, reu)
        out_d64 = str(tmp_path / "compiler.d64")

        calls: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:
            calls.append(cmd)
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=fake_run):
            package_d64.build_d64(
                fake_c1541, str(basicv3), str(georam), out_d64, str(reu)
            )

        assert any(
            "-format" in cmd for cmd in calls
        ), "Expected c1541 -format call; got: " + str(calls)
        assert any("compiler2,00" in cmd for cmd in calls)
        assert any("basicv3" in cmd for cmd in calls)
        assert any("georam" in cmd for cmd in calls)
        assert any("reu" in cmd for cmd in calls)
        assert all("GEORAM" not in cmd for cmd in calls)

    def test_c1541_path_does_not_unlink_existing_output(self, tmp_path: Path) -> None:
        """c1541 should own formatting so open D64 handles do not block unlink."""
        fake_c1541 = str(tmp_path / "c1541.exe")
        basicv3 = tmp_path / "basicv3.prg"
        basicv3.write_bytes(b"\x01\x08" + b"\xea" * 32)
        georam = tmp_path / "georam.bin"
        georam.write_bytes(b"\x00\xde" + b"\x00" * 64)
        reu = tmp_path / "reu.bin"
        package_d64.build_reu_patch(georam, reu)
        out_d64 = tmp_path / "compiler.d64"
        out_d64.write_bytes(b"existing")

        with patch.object(Path, "unlink") as unlink:
            with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                package_d64.build_d64(
                    fake_c1541,
                    str(basicv3),
                    str(georam),
                    str(out_d64),
                    str(reu),
                )

        unlink.assert_not_called()

    def test_direct_build_records_dual_sidecars(self, tmp_path: Path) -> None:
        """Fallback D64 manifests basicv3, georam, and reu as PRG files."""
        basicv3 = tmp_path / "basicv3.prg"
        basicv3.write_bytes(b"\x01\x08" + b"\xea" * 32)
        georam = tmp_path / "georam.bin"
        georam.write_bytes(b"\x00\xde" + b"\x00" * 64)
        reu = tmp_path / "reu.bin"
        package_d64.build_reu_patch(georam, reu)
        out_d64 = tmp_path / "compiler.d64"

        package_d64.build_d64("", str(basicv3), str(georam), str(out_d64), str(reu))

        manifest = package_d64.validate_d64(str(out_d64))
        assert manifest["disk_title"] == "compiler2"
        names = [item["name"] for item in manifest["files"]]
        assert names == ["basicv3", "georam", "reu"]
        assert all(item["type"] == "PRG" for item in manifest["files"])

    def test_direct_build_auto_generates_reu_patch(self, tmp_path: Path) -> None:
        """Omitting reu_path still produces a dual-device D64 with REU."""
        basicv3 = tmp_path / "basicv3.prg"
        basicv3.write_bytes(b"\x01\x08" + b"\xea" * 32)
        georam = tmp_path / "georam.bin"
        georam.write_bytes(b"\x00\xde" + b"\x55" * 64)
        out_d64 = tmp_path / "compiler.d64"

        package_d64.build_d64("", str(basicv3), str(georam), str(out_d64))

        assert (tmp_path / "reu.bin").exists()
        manifest = package_d64.validate_d64(str(out_d64))
        assert [item["name"] for item in manifest["files"]] == [
            "basicv3",
            "georam",
            "reu",
        ]

    def test_direct_build_writes_prg_sector_chain(self, tmp_path: Path) -> None:
        """Fallback D64 data sectors contain the exact PRG payload."""
        basicv3 = tmp_path / "basicv3.prg"
        basicv3.write_bytes(b"\x01\x08" + b"\xea" * 32)
        georam = tmp_path / "georam.bin"
        payload = b"\x00\xdeCGS1" + bytes(range(128))
        georam.write_bytes(payload)
        reu = tmp_path / "reu.bin"
        package_d64.build_reu_patch(georam, reu)
        out_d64 = tmp_path / "compiler.d64"

        package_d64.build_d64("", str(basicv3), str(georam), str(out_d64), str(reu))

        data = out_d64.read_bytes()
        dir_offset = package_d64._d64_offset(18, 1)
        georam_entry = dir_offset + 2 + 32
        track = data[georam_entry + 1]
        sector = data[georam_entry + 2]
        offset = package_d64._d64_offset(track, sector)
        used = data[offset + 1] - 1
        assert data[offset] == 0
        assert data[offset + 2 : offset + 2 + used] == payload

    def test_skips_basicv3_write_when_absent(self, tmp_path: Path) -> None:
        """build_d64 skips the -write basicv3 call when the PRG does not exist."""
        fake_c1541 = str(tmp_path / "c1541.exe")
        georam = tmp_path / "georam.bin"
        georam.write_bytes(b"\x00" * 64)
        reu = tmp_path / "reu.bin"
        package_d64.build_reu_patch(georam, reu)
        out_d64 = str(tmp_path / "compiler.d64")

        calls: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:
            calls.append(cmd)
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=fake_run):
            package_d64.build_d64(
                fake_c1541,
                str(tmp_path / "nonexistent.prg"),
                str(georam),
                out_d64,
                str(reu),
            )

        write_calls = [c for c in calls if "-write" in c and "basicv3" in c]
        assert len(write_calls) == 0

    def test_raises_on_c1541_failure(self, tmp_path: Path) -> None:
        """build_d64 propagates CalledProcessError when c1541 exits non-zero."""
        fake_c1541 = str(tmp_path / "c1541.exe")
        out_d64 = str(tmp_path / "compiler.d64")

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "c1541"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                package_d64.build_d64(fake_c1541, "", "", out_d64)
