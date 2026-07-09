"""Tests for tools/prepare_compressor_segments.py — fallback PRG builder.

Covers: load-address prepending and output file creation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import prepare_compressor_segments


def test_stage_segments_writes_payload_and_deterministic_layout(
    compile_bin: Path, tmp_path: Path
) -> None:
    """Compression staging preserves bytes and records their exact size."""
    segments = tmp_path / "segments"
    layout = tmp_path / "compressor_layout.cfg"
    prepare_compressor_segments.stage_segments(
        str(compile_bin), str(segments), str(layout)
    )
    assert (segments / "compiler_main.bin").read_bytes() == compile_bin.read_bytes()
    content = layout.read_text(encoding="utf-8")
    assert content.startswith("entry = $080D\nentry_mode = jmp\n")
    assert (
        f"segment = compiler_main, bin, "
        f"{(segments / 'compiler_main.bin').as_posix()}, $080D\n" in content
    )


@pytest.fixture()
def compile_bin(tmp_path: Path) -> Path:
    p = tmp_path / "compile.bin"
    p.write_bytes(b"\xea" * 64)  # 64 NOP bytes as payload
    return p


class TestBuildSimplePrg:
    """Tests for prepare_compressor_segments.build_simple_prg."""

    def test_output_starts_with_load_address(
        self, compile_bin: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "basicv3.prg"
        prepare_compressor_segments.build_simple_prg(str(compile_bin), str(out))
        data = out.read_bytes()
        assert data[0] == 0x01
        assert data[1] == 0x08

    def test_output_contains_basic_loader(
        self, compile_bin: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "basicv3.prg"
        prepare_compressor_segments.build_simple_prg(str(compile_bin), str(out))
        data = out.read_bytes()
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

    def test_payload_appended_after_load_address(
        self, compile_bin: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "basicv3.prg"
        prepare_compressor_segments.build_simple_prg(str(compile_bin), str(out))
        data = out.read_bytes()
        assert data[14:] == b"\xea" * 64

    def test_output_file_created(self, compile_bin: Path, tmp_path: Path) -> None:
        out = tmp_path / "basicv3.prg"
        prepare_compressor_segments.build_simple_prg(str(compile_bin), str(out))
        assert out.exists()

    def test_missing_input_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            prepare_compressor_segments.build_simple_prg(
                str(tmp_path / "nonexistent.bin"),
                str(tmp_path / "out.prg"),
            )
