"""Tests for tools/extract_segments.py — map-file segment extractor.

Covers: map-file parsing, segment boundary extraction, and payload writing.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import extract_segments

# ld65 map format: 6-digit hex columns for Start, End, Size, Align
SAMPLE_MAP = """\
Segment list:
-------------
Name                   Start     End       Size      Align
------------------------------------------------------------
CODE                  001000    0010FF    000100    000001
DATA                  001100    00117F    000080    000001
BSS                   001180    0011FF    000080    000001
"""


@pytest.fixture()
def map_file(tmp_path: Path) -> Path:
    p = tmp_path / "compiler.map"
    p.write_text(SAMPLE_MAP, encoding="utf-8")
    return p


@pytest.fixture()
def bin_file(tmp_path: Path) -> Path:
    # 512-byte binary payload (base at $0801)
    p = tmp_path / "compiler.bin"
    p.write_bytes(b"\x01\x08" + bytes(range(256)) * 2)
    return p


class TestParseMapSegments:
    """Tests for extract_segments.parse_segments."""

    def test_parses_code_segment(self, map_file: Path) -> None:
        segments = extract_segments.parse_segments(str(map_file))
        names = [s["name"] for s in segments]
        assert "CODE" in names

    def test_code_start_end(self, map_file: Path) -> None:
        segments = extract_segments.parse_segments(str(map_file))
        code = next(s for s in segments if s["name"] == "CODE")
        assert code["start"] == 0x001000
        assert code["end"] == 0x0010FF

    def test_all_three_segments_found(self, map_file: Path) -> None:
        segments = extract_segments.parse_segments(str(map_file))
        names = {s["name"] for s in segments}
        # BSS is filtered out by extract_segments; CODE and DATA must be present
        assert "CODE" in names
        assert "DATA" in names

    def test_missing_map_returns_empty(self) -> None:
        # parse_segments returns [] for missing files (not a raise)
        segments = extract_segments.parse_segments("/nonexistent/compiler.map")
        assert segments == []


class TestExtractPayload:
    """Tests for extract_segments.extract_payload."""

    def test_output_created(self, bin_file: Path, tmp_path: Path) -> None:
        # Provide a minimal segment list pointing into our binary
        segments = [{"name": "RESIDENT", "start": 0x0801, "end": 0x0880, "size": 0x80}]
        out = tmp_path / "compile.bin"
        extract_segments.extract_payload(str(bin_file), segments, str(out))
        assert out.exists()

    def test_missing_binary_raises(self, tmp_path: Path) -> None:
        segments = [{"name": "CODE", "start": 0x0801, "end": 0x0900, "size": 0x10}]
        out = tmp_path / "compile.bin"
        with pytest.raises(FileNotFoundError):
            extract_segments.extract_payload(
                str(tmp_path / "nonexistent.bin"), segments, str(out)
            )

    def test_preserves_linked_gaps_between_segments(self, tmp_path: Path) -> None:
        """Absolute addresses after a no-load gap remain at their linked offset."""
        binary = tmp_path / "compiler.bin"
        payload = bytearray(b"\xea" * 0x40)
        payload[0:2] = b"\x11\x22"
        payload[0x20:0x22] = b"\x33\x44"
        binary.write_bytes(b"\x01\x08" + payload)
        segments = [
            {"name": "LOADER", "start": 0x0801, "end": 0x0802, "size": 2},
            {"name": "RESIDENT", "start": 0x0821, "end": 0x0822, "size": 2},
        ]
        output = tmp_path / "compile.bin"

        extract_segments.extract_payload(str(binary), segments, str(output))

        extracted = output.read_bytes()
        assert len(extracted) == 0x22
        assert extracted[:2] == b"\x11\x22"
        assert extracted[0x20:0x22] == b"\x33\x44"
        assert extracted[2:0x20] == b"\xea" * 0x1E

    def test_excludes_georam_backed_cold_segments(self, tmp_path: Path) -> None:
        """Cold overlay bytes belong in georam.bin, not the RAM payload PRG."""
        binary = tmp_path / "compiler.bin"
        payload = bytearray(b"\xea" * 0x500)
        payload[0x000:0x002] = b"\x11\x22"
        payload[0x100:0x102] = b"\x33\x44"
        payload[0x300:0x302] = b"\x55\x66"
        binary.write_bytes(b"\x01\x08" + payload)
        segments = [
            {"name": "LOADER", "start": 0x0801, "end": 0x0802, "size": 2},
            {"name": "RESIDENT", "start": 0x0901, "end": 0x0902, "size": 2},
            {"name": "GEOASM", "start": 0x0B01, "end": 0x0B02, "size": 2},
        ]
        output = tmp_path / "compile.bin"

        extract_segments.extract_payload(str(binary), segments, str(output))

        extracted = output.read_bytes()
        assert len(extracted) == 0x102
        assert extracted[:2] == b"\x11\x22"
        assert extracted[0x100:0x102] == b"\x33\x44"
        assert b"\x55\x66" not in extracted

    def test_validate_payload_detects_byte_drift(self, tmp_path: Path) -> None:
        """Validation rejects an extraction that differs from linked bytes."""
        binary = tmp_path / "compiler.bin"
        binary.write_bytes(b"\x01\x08\x11\x22")
        output = tmp_path / "compile.bin"
        output.write_bytes(b"\x11\x23")
        segments = [{"name": "RESIDENT", "start": 0x0801, "end": 0x0802, "size": 2}]
        assert extract_segments.validate_payload(
            str(binary), segments, str(output)
        ) == ["payload bytes differ: expected 2 bytes, found 2"]

    def test_validate_payload_accepts_exact_extraction(self, tmp_path: Path) -> None:
        """Validation accepts the exact linked RAM span."""
        binary = tmp_path / "compiler.bin"
        binary.write_bytes(b"\x01\x08\x11\x22")
        output = tmp_path / "compile.bin"
        output.write_bytes(b"\x11\x22")
        segments = [{"name": "RESIDENT", "start": 0x0801, "end": 0x0802, "size": 2}]
        assert (
            extract_segments.validate_payload(str(binary), segments, str(output)) == []
        )
