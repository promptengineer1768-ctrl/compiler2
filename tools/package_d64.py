"""D64 packaging tool for Compiler 2.

Creates D64 disk images using VICE c1541 tool or fallback to direct write.
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def build_d64(
    c1541_path: str,
    basicv3_path: str,
    georam_path: str,
    output_path: str,
) -> None:
    """Create a D64 disk image using c1541 tool.

    Args:
        c1541_path: Path to c1541 executable.
        basicv3_path: Path to BASICV3.PRG.
        georam_path: Path to GEORAM PRG sidecar.
        output_path: Output D64 path.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Use c1541 if path provided
    if c1541_path:
        _build_with_c1541(
            Path(c1541_path),
            basicv3_path,
            georam_path,
            output_path,
        )
    else:
        # Fallback: create D64 directly
        _build_direct(basicv3_path, georam_path, output_path)


def _build_with_c1541(
    c1541: Path,
    basicv3_path: str,
    georam_path: str,
    output_path: str,
) -> None:
    """Build D64 using VICE c1541 tool."""
    cmd = [str(c1541)]

    # Format the disk
    cmd.extend(["-format", "compiler2,00", "d64", output_path])

    # Write BASICV3.PRG if it exists
    if basicv3_path and Path(basicv3_path).exists():
        cmd.extend(["-write", basicv3_path, "basicv3"])

    # Write GEORAM as a PRG with a fake $DE00 load header.
    if georam_path and Path(georam_path).exists():
        cmd.extend(["-write", georam_path, "georam"])
    subprocess.run(cmd, check=True, capture_output=True)


def _build_direct(
    basicv3_path: str,
    georam_path: str,
    output_path: str,
) -> None:
    """Build D64 directly without c1541."""
    # Standard 35-track D64 uses variable sectors per track.
    d64_size = 174848

    d64_data = bytearray(d64_size)

    # BAM (track 18 sector 0) and first directory sector (track 18 sector 1).
    bam_offset = _d64_offset(18, 0)
    d64_data[bam_offset] = 0x12
    d64_data[bam_offset + 1] = 0x01
    d64_data[bam_offset + 2] = 0x41
    # PETSCII $41-$5A renders as lowercase in a shifted directory listing.
    disk_name = b"COMPILER2"
    d64_data[bam_offset + 0x90 : bam_offset + 0xA0] = disk_name + b"\xa0" * (
        16 - len(disk_name)
    )
    d64_data[bam_offset + 0xA2 : bam_offset + 0xA4] = b"00"

    dir_offset = _d64_offset(18, 1)
    d64_data[dir_offset] = 0
    d64_data[dir_offset + 1] = 0xFF
    entry_offset = 0
    next_track = 1
    next_sector = 0

    # Add BASICV3.PRG
    if basicv3_path and Path(basicv3_path).exists():
        data = Path(basicv3_path).read_bytes()
        start_track, start_sector, sector_count, next_track, next_sector = (
            _write_prg_data(d64_data, data, next_track, next_sector)
        )
        _add_entry(
            d64_data,
            dir_offset + 2 + entry_offset,
            "BASICV3",
            "PRG",
            start_track,
            start_sector,
            sector_count,
        )
        entry_offset += 32

    # Add GEORAM PRG sidecar.
    if georam_path and Path(georam_path).exists():
        data = Path(georam_path).read_bytes()
        start_track, start_sector, sector_count, next_track, next_sector = (
            _write_prg_data(d64_data, data, next_track, next_sector)
        )
        _add_entry(
            d64_data,
            dir_offset + 2 + entry_offset,
            "GEORAM",
            "PRG",
            start_track,
            start_sector,
            sector_count,
        )
        entry_offset += 32

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(bytes(d64_data))


def _d64_offset(track: int, sector: int) -> int:
    """Return byte offset for a 1-based track and 0-based sector."""
    sectors_by_track = [21] * 17 + [19] * 7 + [18] * 6 + [17] * 5
    if track < 1 or track > len(sectors_by_track):
        raise ValueError(f"Invalid D64 track: {track}")
    sectors = sectors_by_track[track - 1]
    if sector < 0 or sector >= sectors:
        raise ValueError(f"Invalid D64 sector {sector} for track {track}")
    return (sum(sectors_by_track[: track - 1]) + sector) * 256


def _next_data_sector(track: int, sector: int) -> tuple[int, int]:
    """Return the next usable data sector, skipping the directory track."""
    sectors_by_track = [21] * 17 + [19] * 7 + [18] * 6 + [17] * 5
    sector += 1
    while track <= len(sectors_by_track):
        if track == 18:
            track += 1
            sector = 0
            continue
        if sector < sectors_by_track[track - 1]:
            return track, sector
        track += 1
        sector = 0
    raise ValueError("D64 image has no free sectors for file payload")


def _write_prg_data(
    d64: bytearray, data: bytes, track: int, sector: int
) -> tuple[int, int, int, int, int]:
    """Write a PRG sector chain and return start/count/next free sector."""
    chunks = [data[start : start + 254] for start in range(0, len(data), 254)]
    if not chunks:
        chunks = [b""]
    start_track, start_sector = track, sector
    current_track, current_sector = track, sector
    for index, chunk in enumerate(chunks):
        offset = _d64_offset(current_track, current_sector)
        if index == len(chunks) - 1:
            d64[offset] = 0
            d64[offset + 1] = len(chunk) + 1
            next_track, next_sector = _next_data_sector(current_track, current_sector)
        else:
            next_track, next_sector = _next_data_sector(current_track, current_sector)
            d64[offset] = next_track
            d64[offset + 1] = next_sector
        d64[offset + 2 : offset + 2 + len(chunk)] = chunk
        current_track, current_sector = next_track, next_sector
    return start_track, start_sector, len(chunks), current_track, current_sector


def _add_entry(
    d64: bytearray,
    offset: int,
    name: str,
    ext: str,
    track: int,
    sector: int,
    size_sectors: int,
) -> None:
    """Add directory entry."""
    d64[offset] = 0x82 if ext == "PRG" else 0x81
    d64[offset + 1] = track
    d64[offset + 2] = sector
    for i in range(16):
        d64[offset + 3 + i] = ord(name[i]) if i < len(name) else 0xA0
    d64[offset + 28] = size_sectors & 0xFF
    d64[offset + 29] = (size_sectors >> 8) & 0xFF


def validate_d64(d64_path: str) -> dict[str, Any]:
    """Validate D64 contents and return manifest."""
    path = Path(d64_path)
    if not path.exists():
        raise FileNotFoundError(f"D64 not found: {d64_path}")

    data = path.read_bytes()
    expected = 174848
    if len(data) != expected:
        raise ValueError(f"Invalid D64 size: {len(data)}")

    # Track 18 sector 1 follows tracks 1-17 (21 sectors each).
    bam_offset = _d64_offset(18, 0)
    dir_offset = ((17 * 21) + 1) * 256
    disk_title = _decode_petscii_name(data[bam_offset + 0x90 : bam_offset + 0xA0])
    files = []
    for i in range(8):
        off = dir_offset + 2 + i * 32
        if data[off] == 0:
            continue
        type_code = data[off] & 0x07
        file_type = {1: "SEQ", 2: "PRG"}.get(type_code, "OTHER")
        name = _decode_petscii_name(data[off + 3 : off + 19])
        size = data[off + 28] | (data[off + 29] << 8)
        files.append({"name": name, "type": file_type, "size_sectors": size})

    return {
        "d64_path": d64_path,
        "total_size": len(data),
        "disk_title": disk_title,
        "files": files,
    }


def validate_prg_header(prg_path: str) -> list[str]:
    """Validate the canonical `$0801` BASIC loader header.

    Args:
        prg_path: Path to the uncompressed BASICV3 PRG.

    Returns:
        A list of deterministic validation errors, empty when valid.
    """
    path = Path(prg_path)
    if not path.exists():
        return [f"PRG not found: {prg_path}"]
    data = path.read_bytes()
    expected_loader = bytes(
        [
            0x01,
            0x08,
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
    if len(data) < len(expected_loader):
        return [f"PRG is truncated: expected at least {len(expected_loader)} bytes"]
    if data[:2] != b"\x01\x08":
        return ["PRG load address is not $0801"]
    if data[: len(expected_loader)] != expected_loader:
        return ["PRG loader is not canonical `2026 SYS2061`"]
    return []


def _decode_petscii_name(raw: bytes) -> str:
    """Decode the directory-visible case of a padded PETSCII name."""
    result = []
    for value in raw:
        if value == 0xA0:
            break
        if 0x41 <= value <= 0x5A:
            result.append(chr(value + 0x20))
        elif 0x61 <= value <= 0x7A:
            result.append(chr(value - 0x20))
        else:
            result.append(chr(value & 0x7F))
    return "".join(result)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("c1541_path", nargs="?", default=None)
    parser.add_argument("basicv3_path", nargs="?", default=None)
    parser.add_argument("georam_path", nargs="?", default=None)
    parser.add_argument("output_path", nargs="?", default=None)
    args = parser.parse_args()

    build_dir = ROOT / "build"
    basicv3_path = (
        Path(args.basicv3_path) if args.basicv3_path else build_dir / "basicv3.prg"
    )
    georam_path = (
        Path(args.georam_path) if args.georam_path else build_dir / "georam.bin"
    )
    output_path = (
        Path(args.output_path) if args.output_path else build_dir / "compiler.d64"
    )

    # Find c1541
    c1541_path = (
        None
        if args.c1541_path in (None, "", "null", "$null", "auto")
        else args.c1541_path
    )
    if c1541_path is None:
        for search in [
            ROOT.parent
            / "tools"
            / "vice-mcp"
            / "dist"
            / "HeadlessVICE-windows-x86_64"
            / "c1541.exe",
            ROOT.parent
            / "tools"
            / "vice-mcp"
            / "dist"
            / "HeadlessVICE-windows_x86_64"
            / "c1541.exe",
            Path("C:/Program Files/VICE/tools/c1541.exe"),
            Path("C:/Program Files (x86)/VICE/tools/c1541.exe"),
            Path("C:/Users/me/tools/c1541.exe"),
        ]:
            if search.exists():
                c1541_path = str(search)
                break

    if c1541_path is None:
        c1541_path = "c1541"

    # Create placeholders if needed
    if not basicv3_path.exists():
        print(f"Creating placeholder: {basicv3_path}")
        basicv3_path.parent.mkdir(parents=True, exist_ok=True)
        basicv3_path.write_bytes(struct.pack("<H", 0x080D) + b"\x00" * 32)

    if not georam_path.exists():
        print(f"Creating placeholder: {georam_path}")
        georam_path.parent.mkdir(parents=True, exist_ok=True)
        georam_path.write_bytes(struct.pack("<H", 0xDE00) + b"\x00" * 65536)

    print(f"Building D64: {output_path}")
    try:
        build_d64(
            c1541_path,
            str(basicv3_path),
            str(georam_path),
            str(output_path),
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        print(f"c1541 failed, using direct build: {e}")
        _build_direct(
            str(basicv3_path),
            str(georam_path),
            str(output_path),
        )

    # Validate
    manifest = validate_d64(str(output_path))
    print(f"D64 created: {manifest['total_size']} bytes")
    for f in manifest["files"]:
        print(f"  {f['name']}.{f['type']}: {f['size_sectors']} sectors")

    # Save manifest
    manifest_path = output_path.with_suffix(".json")
    with open(manifest_path, "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, indent=2)
    print(f"Manifest saved: {manifest_path}")


if __name__ == "__main__":
    main()
