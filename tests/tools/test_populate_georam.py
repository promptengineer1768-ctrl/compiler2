"""Tests for materializing linked cold/compiler bytes into geoRAM."""

from __future__ import annotations

from pathlib import Path

import pytest

from populate_georam import COLD_SEGMENTS, populate


def _map_text(start: int, size: int) -> str:
    """Return map rows for every required cold segment."""
    rows = []
    address = start
    for name in COLD_SEGMENTS:
        segment_start = 0xE000 if name == "HIBASIC" else address
        rows.append(
            f"{name:<20} {segment_start:06X}  {segment_start + size - 1:06X}  "
            f"{size:06X}  00001"
        )
        if name != "HIBASIC":
            address += size
    return "\n".join(rows) + "\n"


def test_populate_preserves_all_linked_cold_bytes(tmp_path: Path) -> None:
    """The output contains every cold segment followed by zero padding."""
    map_path = tmp_path / "compiler.map"
    map_path.write_text(_map_text(0x0810, 4))
    normal_segment_count = len(COLD_SEGMENTS) - 1
    linked = bytes(range(1, normal_segment_count * 4 + 1))
    hibasic = bytes(range(0xA1, 0xA5))
    compiler_path = tmp_path / "compiler.bin"
    compiler_path.write_bytes(b"\x01\x08" + b"\x00" * 15 + linked)
    (tmp_path / "hibasic.bin").write_bytes(hibasic)
    output_path = tmp_path / "georam.bin"

    populate(map_path, compiler_path, output_path)

    output = output_path.read_bytes()
    assert output[:2] == b"\x00\xde"
    hibasic_index = COLD_SEGMENTS.index("HIBASIC") * 4
    expected = linked[:hibasic_index] + hibasic + linked[hibasic_index:]
    assert output[2 : 2 + len(expected)] == expected
    assert output[2 + len(expected) :] == bytes(65536 - len(expected))


def test_populate_rejects_fill_only_payload(tmp_path: Path) -> None:
    """Uniform linker fill cannot silently become a release image."""
    map_path = tmp_path / "compiler.map"
    map_path.write_text(_map_text(0x0801, 4))
    compiler_path = tmp_path / "compiler.bin"
    compiler_path.write_bytes(b"\x01\x08" + b"\xea" * (4 * len(COLD_SEGMENTS)))
    (tmp_path / "hibasic.bin").write_bytes(b"\xea" * 4)

    with pytest.raises(ValueError, match="fill-only"):
        populate(map_path, compiler_path, tmp_path / "georam.bin")


def test_populate_overlays_directory_routine_bytes(tmp_path: Path) -> None:
    """Directory-placed routines are installed at generated geoRAM offsets."""
    map_path = tmp_path / "compiler.map"
    map_path.write_text(_map_text(0x0810, 4))
    linked = bytearray(range(1, len(COLD_SEGMENTS) * 4 + 1))
    (tmp_path / "hibasic.bin").write_bytes(b"\x61\x62\x63\x64")
    routine = b"\xa9\x42\xa2\x24\xa0\x11\x18\x60"
    compiler_path = tmp_path / "compiler.bin"
    compiler_path.write_bytes(b"\x01\x08" + b"\x00" * 15 + linked + routine)
    label_address = 0x0810 + len(linked)
    labels_path = tmp_path / "compiler.lbl"
    labels_path.write_text(f"al {label_address:06X} .wedge_parse\n")
    directory_path = tmp_path / "routine_directory.json"
    directory_path.write_text("""
{
  "routines": {
    "wedge_parse": {
      "layer": "georam",
      "block": 0,
      "page": 2,
      "offset": 16
    }
  }
}
""")
    output_path = tmp_path / "georam.bin"

    populate(map_path, compiler_path, output_path, labels_path, directory_path)

    payload = output_path.read_bytes()[2:]
    destination = 2 * 256 + 16
    assert payload[destination : destination + len(routine)] == routine
