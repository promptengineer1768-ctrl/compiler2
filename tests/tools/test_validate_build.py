"""Tests for tools/validate_build.py — manifest and build integrity checks.

Covers: manifest presence, JSON validity, fingerprint generation, and
reporting structure.
"""

from __future__ import annotations

import json
import hashlib
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


def test_traceability_rejects_missing_normative_section(tmp_path: Path) -> None:
    """Trace validation derives coverage from both normative source documents."""
    (tmp_path / "REQUIREMENTS.md").write_text(
        "# Requirements\n\n## 1. Status\n\n## 2. Product\n", encoding="utf-8"
    )
    (tmp_path / "REU_REQUIREMENTS.md").write_text(
        "# REU Requirements\n\n## RREU-1. Product\n", encoding="utf-8"
    )
    (tmp_path / "DESIGN2.md").write_text("# Design\n", encoding="utf-8")
    (tmp_path / "implementation.py").write_text("\n", encoding="utf-8")
    trace = {
        "requirement_sources": ["REQUIREMENTS.md", "REU_REQUIREMENTS.md"],
        "records": [
            {
                "id": "R2",
                "ears": "The system shall provide the product.",
                "source_section": "REQUIREMENTS.md#2",
                "design_section": "DESIGN2.md",
                "implementation": "implementation.py",
                "tests": ["test_product"],
                "status": "planned",
            }
        ],
    }
    (tmp_path / "traceability.json").write_text(json.dumps(trace), encoding="utf-8")
    (tmp_path / "requirements_matrix.json").write_text(json.dumps({}), encoding="utf-8")

    errors = validate_build.validate_traceability(
        "traceability.json",
        "requirements_matrix.json",
        project_root=str(tmp_path),
    )

    assert any("RREU-1" in error for error in errors)


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


class TestBuildManifest:
    """Tests for final toolchain and artifact provenance records."""

    def test_records_tool_versions_and_generated_reference_hashes(
        self, tmp_path: Path
    ) -> None:
        """Manifest data binds actual tools to both generated references."""
        api = tmp_path / "API.md"
        memory_map = tmp_path / "MAP.md"
        api.write_text("api\n", encoding="utf-8")
        memory_map.write_text("map\n", encoding="utf-8")
        versions = {"ca65": "ca65 V2.19", "ld65": "ld65 V2.19"}

        manifest = validate_build.build_manifest_data(tmp_path, tool_versions=versions)

        assert manifest["toolchain"]["ca65"]["version"] == "ca65 V2.19"
        assert manifest["toolchain"]["ld65"]["version"] == "ld65 V2.19"
        assert manifest["artifacts"]["API.md"] == {
            "size": len(api.read_bytes()),
            "sha256": hashlib.sha256(api.read_bytes()).hexdigest(),
        }
        assert manifest["artifacts"]["MAP.md"] == {
            "size": len(memory_map.read_bytes()),
            "sha256": hashlib.sha256(memory_map.read_bytes()).hexdigest(),
        }

    def test_missing_generated_reference_is_rejected(self, tmp_path: Path) -> None:
        """A final manifest cannot omit either generated reference."""
        (tmp_path / "API.md").write_text("api\n", encoding="utf-8")
        with pytest.raises(FileNotFoundError, match="MAP.md"):
            validate_build.build_manifest_data(
                tmp_path,
                tool_versions={"ca65": "ca65 V2.19", "ld65": "ld65 V2.19"},
            )

    def test_rejects_artifacts_when_a_source_input_changes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Validation rejects stale artifacts instead of re-signing them."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        source = tmp_path / "src" / "main.asm"
        source.write_text("nop\n", encoding="utf-8")
        (tmp_path / "build.ps1").write_text("# build\n", encoding="utf-8")
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "API.md").write_text("api\n", encoding="utf-8")
        (build_dir / "MAP.md").write_text("map\n", encoding="utf-8")
        versions = {"ca65": "ca65 V2.19", "ld65": "ld65 V2.19"}
        manifest = validate_build.build_manifest_data(build_dir, tool_versions=versions)
        (build_dir / "build_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        source.write_text("brk\n", encoding="utf-8")
        monkeypatch.setattr(
            validate_build, "configured_tool_versions", lambda: versions
        )

        errors = validate_build.validate_build_manifest(
            str(build_dir / "build_manifest.json")
        )

        assert "build artifacts are stale relative to current source inputs" in errors
        assert json.loads((build_dir / "build_manifest.json").read_text()) == manifest

    def test_validation_does_not_write_a_missing_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The normal validator is read-only when no release manifest exists."""
        monkeypatch.chdir(tmp_path)
        missing = tmp_path / "build" / "build_manifest.json"

        assert validate_build.validate_build_manifest(str(missing)) == [
            f"build manifest is missing: {missing}"
        ]
        assert not missing.exists()

    def test_required_release_artifacts_are_explicit(self, tmp_path: Path) -> None:
        """A release cannot silently omit a final artifact from the contract."""
        errors = validate_build.validate_required_release_artifacts(tmp_path)

        assert errors == [
            f"required release artifact is missing: {name}"
            for name in validate_build.FINAL_ARTIFACT_NAMES
        ]


class TestCrossArtifactValidators:
    """Direct coverage for generated contract validators."""

    def test_checked_in_generated_contracts_are_consistent(self) -> None:
        root = Path(__file__).resolve().parents[2]
        required = (
            "routine_directory.json",
            "arena_layout.json",
            "zp_allocation.json",
            "size_report.json",
            "API.md",
            "MAP.md",
            "production_entries.json",
        )
        if any(not (root / "build" / name).exists() for name in required):
            pytest.skip("complete build artifacts not present; run build.ps1 first")
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

    def test_expansion_contract_validator_rejects_fabricated_reu_overlay(
        self, tmp_path: Path
    ) -> None:
        """A patch-only release cannot claim an unshipped REU-native overlay."""
        import generate_expansion_contracts

        (tmp_path / "routine_directory.json").write_text(
            json.dumps(
                {
                    "routines": {
                        "xip": {
                            "id": 2,
                            "layer": "georam",
                            "block": 0,
                            "page": 1,
                            "offset": 0,
                            "address": "$DE00",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "reu_loader_manifest.json").write_text(
            json.dumps({"kind": "reu_patch", "georam_sha256": "abc"}),
            encoding="utf-8",
        )
        generate_expansion_contracts.write(tmp_path)
        assert validate_build.validate_expansion_contracts(tmp_path) == []
        layout_path = tmp_path / "reu_layout.json"
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        layout["overlays"] = [{"overlay_id": 1}]
        layout_path.write_text(json.dumps(layout), encoding="utf-8")

        assert validate_build.validate_expansion_contracts(tmp_path) == [
            "patch-only REU layout must not advertise executable overlays"
        ]

    def test_expansion_contract_validator_requires_dual_reu_records(
        self, tmp_path: Path
    ) -> None:
        """Every linked geoRAM page must have a planned dual REU record."""
        import generate_expansion_contracts

        (tmp_path / "routine_directory.json").write_text(
            json.dumps(
                {
                    "routines": {
                        "xip": {
                            "id": 2,
                            "layer": "georam",
                            "block": 0,
                            "page": 1,
                            "offset": 0,
                            "address": "$DE00",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "reu_loader_manifest.json").write_text(
            json.dumps({"kind": "reu_patch", "georam_sha256": "abc"}),
            encoding="utf-8",
        )
        generate_expansion_contracts.write(tmp_path)
        assert validate_build.validate_expansion_contracts(tmp_path) == []

        layout_path = tmp_path / "reu_layout.json"
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        layout["routine_records"] = []
        layout["routine_record_count"] = 0
        layout_path.write_text(json.dumps(layout), encoding="utf-8")
        errors = validate_build.validate_expansion_contracts(tmp_path)
        assert (
            "REU layout routine_records disagree with linked geoRAM dual placements"
            in errors
        )

        layout = json.loads((tmp_path / "reu_layout.json").read_text(encoding="utf-8"))
        # restore dual then claim live execution
        generate_expansion_contracts.write(tmp_path)
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        layout["routine_records"][0]["reu"]["execution_status"] = "live"
        layout_path.write_text(json.dumps(layout), encoding="utf-8")
        errors = validate_build.validate_expansion_contracts(tmp_path)
        assert any("claims live execution" in error for error in errors)

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

    def test_xip_path_contracts_flag_direct_calls_and_missing_pages(
        self, tmp_path: Path
    ) -> None:
        """XIP gates reject direct mirrors and conforming entries without pages."""
        source_root = tmp_path / "src"
        source_root.mkdir()
        (source_root / "caller.asm").write_text("jsr token_init\n", encoding="utf-8")
        policy_path = tmp_path / "policy.json"
        policy_path.write_text(
            json.dumps(
                {
                    "routines": [
                        {
                            "name": "token_init",
                            "target_placement": "expansion_xip",
                            "conformance": "conforming",
                            "xip_page": 2,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        directory_path = tmp_path / "directory.json"
        directory_path.write_text(json.dumps({"routines": {}}), encoding="utf-8")

        errors = validate_build.validate_xip_path_contracts(
            source_root=source_root,
            policy_path=policy_path,
            routine_directory_path=directory_path,
        )

        assert any(
            "direct jsr to expansion_xip routine token_init" in e for e in errors
        )
        assert any(
            "conforming expansion_xip routine lacks geoRAM entry" in e for e in errors
        )

    def test_xip_path_validation_is_read_only(self, tmp_path: Path) -> None:
        """Validate-only XIP checks must not rewrite policy or directory files."""
        source_root = tmp_path / "src"
        source_root.mkdir()
        (source_root / "caller.asm").write_text("rts\n", encoding="utf-8")
        policy = {
            "routines": [
                {
                    "name": "token_init",
                    "target_placement": "expansion_xip",
                    "conformance": "conforming",
                }
            ]
        }
        directory = {
            "routines": {
                "token_init": {
                    "layer": "georam",
                    "block": 0,
                    "page": 1,
                    "offset": 0,
                    "address": "$DE00",
                }
            }
        }
        policy_path = tmp_path / "policy.json"
        directory_path = tmp_path / "directory.json"
        policy_text = json.dumps(policy)
        directory_text = json.dumps(directory)
        policy_path.write_text(policy_text, encoding="utf-8")
        directory_path.write_text(directory_text, encoding="utf-8")

        assert (
            validate_build.validate_xip_path_contracts(
                source_root=source_root,
                policy_path=policy_path,
                routine_directory_path=directory_path,
            )
            == []
        )
        assert policy_path.read_text(encoding="utf-8") == policy_text
        assert directory_path.read_text(encoding="utf-8") == directory_text


class TestGeoramImageBudget:
    """REQUIREMENTS §8.1 hard-fail via size_report end-to-end."""

    def test_missing_size_report_is_hard_fail(self, tmp_path: Path) -> None:
        errors = validate_build.validate_georam_image_budget(
            str(tmp_path / "missing.json")
        )
        assert errors
        assert "missing" in errors[0]

    def test_passes_when_report_within_512kib(self, tmp_path: Path) -> None:
        report = tmp_path / "size_report.json"
        report.write_text(
            json.dumps(
                {
                    "georam_pages": 256,
                    "georam_page_limit": 2048,
                    "georam_bytes": 65536,
                    "georam_byte_limit": 524288,
                    "georam_within_limit": True,
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "georam.bin").write_bytes(b"\x00\xde" + b"\x00" * 65536)
        assert validate_build.validate_georam_image_budget(str(report)) == []

    def test_hard_fails_when_pages_exceed_limit(self, tmp_path: Path) -> None:
        report = tmp_path / "size_report.json"
        report.write_text(
            json.dumps(
                {
                    "georam_pages": 2049,
                    "georam_page_limit": 2048,
                    "georam_bytes": 524289,
                    "georam_byte_limit": 524288,
                    "georam_within_limit": False,
                }
            ),
            encoding="utf-8",
        )
        errors = validate_build.validate_georam_image_budget(str(report))
        assert any("pages" in err for err in errors)
        assert any("within_limit" in err for err in errors)

    def test_hard_fails_on_oversize_georam_bin_even_if_report_ok(
        self, tmp_path: Path
    ) -> None:
        report = tmp_path / "size_report.json"
        report.write_text(
            json.dumps(
                {
                    "georam_pages": 1,
                    "georam_page_limit": 2048,
                    "georam_bytes": 256,
                    "georam_byte_limit": 524288,
                    "georam_within_limit": True,
                }
            ),
            encoding="utf-8",
        )
        # 512 KiB + 1 payload after $DE00 header.
        (tmp_path / "georam.bin").write_bytes(b"\x00\xde" + b"\x00" * (512 * 1024 + 1))
        errors = validate_build.validate_georam_image_budget(str(report))
        assert any("georam.bin" in err and "512 KiB" in err for err in errors)
