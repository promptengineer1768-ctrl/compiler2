"""System contracts for compressed Compiler 2 and CGS1 sidecar artifacts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build"
COMPRESSOR_ROOT = ROOT.parent / "compressor"
COMPRESSOR = COMPRESSOR_ROOT / "build" / "lzss_compressor.exe"
UNPACKER = COMPRESSOR_ROOT / "build" / "lzss_unpacker.exe"


def _regenerate_compressed_artifacts() -> None:
    """Build fresh compressor artifacts from the current linked images."""
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_compressor_artifacts.py"),
            "--root",
            str(ROOT),
            "--build-dir",
            str(BUILD.relative_to(ROOT)),
            "--compressor-root",
            str(COMPRESSOR_ROOT),
        ],
        check=True,
        cwd=ROOT,
    )


@pytest.mark.system
@pytest.mark.local
def test_compressor_configs_and_staged_segment_exist() -> None:
    """The compressed build emits both configs and the exact staged payload."""
    assert (BUILD / "georam_stream.cfg").is_file()
    assert (BUILD / "compressor_layout.cfg").is_file()
    staged = BUILD / "segments" / "compiler_main.bin"
    assert staged.read_bytes() == (BUILD / "compile.bin").read_bytes()
    assert "georam_stream" in (BUILD / "georam_stream.cfg").read_text()


@pytest.mark.system
@pytest.mark.local
def test_cgs1_header_and_manifest_describe_sidecar() -> None:
    """The geoRAM sidecar has a fake PRG header before CGS1 metadata."""
    sidecar = BUILD / "GEORAM_compressed.prg"
    data = sidecar.read_bytes()
    assert data[:2] == b"\x00\xde"
    assert data[2:6] == b"CGS1"
    metadata = json.loads((BUILD / "GEORAM_compressed.json").read_text())
    record = metadata["sidecars"][0]
    assert record["destination_kind"] == "georam"
    assert record["unpacked_size"] == (BUILD / "georam.bin").stat().st_size - 2
    assert record["packed_size"] == sidecar.stat().st_size - 2


@pytest.mark.system
@pytest.mark.static
def test_cgs1_directory_precedes_all_chunk_payloads() -> None:
    """Every 23-byte chunk record precedes the first compressed stream."""
    data = (BUILD / "GEORAM_compressed.prg").read_bytes()
    metadata = json.loads((BUILD / "GEORAM_compressed.json").read_text())
    chunks = metadata["sidecars"][0]["chunks"]
    chunk_count = int.from_bytes(data[8:10], "little")
    first_payload = 2 + 28 + chunk_count * 23
    assert chunk_count == len(chunks)
    assert first_payload == 2 + chunks[0]["packed_offset"]
    for current, following in zip(chunks, chunks[1:], strict=False):
        assert (
            current["packed_offset"] + current["packed_size"]
            == following["packed_offset"]
        )


@pytest.mark.system
@pytest.mark.static
def test_stream_reader_parses_directory_before_payload_and_avoids_kernal_zp() -> None:
    """The reader honors CGS1 framing without state in KERNAL-clobbered ZP."""
    source = (ROOT / "src" / "loader" / "georam_stream_reader.asm").read_text()
    assert source.index("@directory_loop:") < source.index("@payload_loop:")
    assert "gsrc_chunk_blocks" in source
    assert "gsrc_remain_lo = gsrc_state + 0" in source
    assert "gsrc_remain_lo = zp_georam_stream" not in source


@pytest.mark.system
@pytest.mark.static
def test_stream_reader_uses_directory_size_without_a_payload_prefix() -> None:
    """The reader starts LZSS at the CGS1 payload, not a phantom chunk header."""
    source = (ROOT / "src" / "loader" / "georam_stream_reader.asm").read_text()
    directory = source[
        source.index("@directory_loop:") : source.index("@payload_start:")
    ]
    decompressor = source[source.index("_gsrc_decompress_chunk:") :]
    prologue = decompressor.split("@main_loop:", maxsplit=1)[0]
    assert "gsrc_chunk_unpacked_lo" in directory
    assert "gsrc_chunk_unpacked_hi" in directory
    assert "lda gsrc_chunk_unpacked_lo,x" in prologue
    assert "lda gsrc_chunk_unpacked_hi,x" in prologue
    assert "jsr _gsrc_read_byte" not in prologue


@pytest.mark.system
@pytest.mark.local
def test_compressed_georam_sidecar_round_trip(tmp_path: Path) -> None:
    """A freshly generated sidecar decodes to the exact geoRAM payload."""
    if not COMPRESSOR.exists() or not UNPACKER.exists():
        pytest.skip("compressor tools are not installed")
    _regenerate_compressed_artifacts()
    sidecar = BUILD / "GEORAM_compressed.prg"
    metadata = json.loads((BUILD / "GEORAM_compressed.json").read_text())
    assert Path(metadata["sidecars"][0]["path"]).resolve() == sidecar.resolve()
    headerless = tmp_path / "GEORAM_headerless.prg"
    headerless.write_bytes(sidecar.read_bytes()[2:])
    subprocess.run(
        [
            str(UNPACKER),
            "--decompress-sidecar",
            str(headerless),
            str(tmp_path),
            "--bin",
        ],
        check=True,
        cwd=ROOT,
    )
    outputs = list(tmp_path.glob("*.bin"))
    assert len(outputs) == 1
    actual = outputs[0].read_bytes()
    expected = (BUILD / "georam.bin").read_bytes()[2:]
    assert hashlib.sha256(actual).digest() == hashlib.sha256(expected).digest()
    assert actual == expected


@pytest.mark.system
@pytest.mark.local
def test_compressed_georam_sidecar_is_smaller() -> None:
    """Compression produces a sidecar smaller than the raw geoRAM payload."""
    sidecar = BUILD / "GEORAM_compressed.prg"
    assert sidecar.stat().st_size > 2
    assert sidecar.stat().st_size < (BUILD / "georam.bin").stat().st_size
