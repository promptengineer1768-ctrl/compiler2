"""Tests for tools/validate_build.py — manifest and build integrity checks.

Covers: manifest presence, JSON validity, fingerprint generation, and
reporting structure.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import validate_build

MANIFESTS_DIR = Path(__file__).resolve().parents[2] / "manifests"
REQUIRED_MANIFESTS = [
    "zero_page.json",
    "routines.json",
    "arenas.json",
    "commands.json",
    "program_formats.json",
    "linker_policy.json",
    "runtime_abi.json",
    "traceability.json",
]


class TestValidateManifests:
    """Tests for validate_build.validate_manifests."""

    def test_passes_with_real_manifests(self) -> None:
        missing = [m for m in REQUIRED_MANIFESTS if not (MANIFESTS_DIR / m).exists()]
        if missing:
            pytest.skip(f"Manifests not yet created: {missing}")
        assert validate_build.validate_manifests() is True

    def test_fails_when_manifest_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """validate_manifests returns False when a manifest file is absent."""
        # Patch os.path.exists to simulate a missing file
        original_exists = __import__("os").path.exists

        def fake_exists(path: str) -> bool:
            if "zero_page.json" in path:
                return False
            return bool(original_exists(path))

        monkeypatch.setattr("os.path.exists", fake_exists)
        result = validate_build.validate_manifests()
        assert result is False

    def test_fails_on_invalid_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """validate_manifests returns False for malformed JSON."""
        bad_manifest = tmp_path / "zero_page.json"
        bad_manifest.write_text("{bad json", encoding="utf-8")

        original_exists = __import__("os").path.exists

        def fake_exists(path: str) -> bool:
            if "zero_page.json" in path:
                return True
            return bool(original_exists(path))

        original_open = open

        @contextmanager
        def _open_bad_manifest(*args: Any, **kwargs: Any) -> Iterator[TextIOWrapper]:
            with bad_manifest.open(*args, **kwargs) as fp:
                yield fp

        def fake_open(path: str, *args: Any, **kwargs: Any) -> object:
            if "zero_page.json" in str(path):
                return _open_bad_manifest(*args, **kwargs)
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr("builtins.open", fake_open)
        monkeypatch.setattr("os.path.exists", fake_exists)
        result = validate_build.validate_manifests()
        assert result is False


class TestComputeFingerprint:
    """Tests for validate_build.compute_build_fingerprint."""

    def test_returns_nonempty_string(self) -> None:
        fp = validate_build.compute_build_fingerprint()
        assert isinstance(fp, str)
        assert len(fp) > 0

    def test_fingerprint_is_hex(self) -> None:
        fp = validate_build.compute_build_fingerprint()
        # MD5 hex digest is 32 lowercase hex chars
        assert all(c in "0123456789abcdef" for c in fp)

    def test_deterministic_for_same_inputs(self) -> None:
        fp1 = validate_build.compute_build_fingerprint()
        fp2 = validate_build.compute_build_fingerprint()
        assert fp1 == fp2


class TestCrossArtifactValidators:
    """Direct coverage for generated contract validators."""

    def test_checked_in_generated_contracts_are_consistent(self) -> None:
        root = Path(__file__).resolve().parents[2]
        assert (
            validate_build.validate_routine_directory(
                str(root / "manifests" / "routines.json"),
                str(root / "build" / "routine_directory.json"),
            )
            == []
        )
        assert (
            validate_build.validate_arena_layout(
                str(root / "manifests" / "arenas.json"),
                str(root / "build" / "arena_layout.json"),
            )
            == []
        )
        assert (
            validate_build.validate_zp_allocation(
                str(root / "manifests" / "zero_page.json"),
                str(root / "build" / "zp_allocation.json"),
            )
            == []
        )
        assert (
            validate_build.validate_size_report(
                str(root / "build" / "size_report.json")
            )
            == []
        )
        assert (
            validate_build.validate_program_formats(
                str(root / "manifests" / "program_formats.json")
            )
            == []
        )
        assert (
            validate_build.validate_runtime_abi(
                str(root / "manifests" / "runtime_abi.json"),
                str(root / "build" / "runtime_abi.json"),
            )
            == []
        )
        assert (
            validate_build.validate_keyword_lookup(
                str(root / "manifests" / "commands.json"),
                str(root / "build" / "keyword_lookup_report.json"),
            )
            == []
        )
        assert (
            validate_build.validate_generated_reference(
                str(root / "build" / "API.md"),
                str(root / "build" / "MAP.md"),
                str(root / "build" / "production_entries.json"),
            )
            == []
        )

    def test_runtime_abi_validator_rejects_drift(self, tmp_path: Path) -> None:
        source = tmp_path / "source.json"
        generated = tmp_path / "generated.json"
        source.write_text(json.dumps({"entries": [{"name": "one"}]}), encoding="utf-8")
        generated.write_text(
            json.dumps({"entries": [{"name": "two"}]}), encoding="utf-8"
        )
        assert validate_build.validate_runtime_abi(str(source), str(generated)) == [
            "generated runtime ABI differs from manifest"
        ]

    def test_stale_generated_validator_detects_newer_input(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / "output"
        source = tmp_path / "source"
        source.write_text("input", encoding="utf-8")
        output.write_text("output", encoding="utf-8")
        output_time = output.stat().st_mtime_ns
        os.utime(source, ns=(output_time + 1_000_000, output_time + 1_000_000))
        assert validate_build.validate_no_stale_generated(
            {str(output): [str(source)]}
        ) == [f"generated output {output} is stale relative to {source}"]
