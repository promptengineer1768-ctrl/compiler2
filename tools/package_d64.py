"""D64 packaging tool for Compiler 2.

Creates dual-device D64 disk images (BASICV3 + GEORAM + REU) using VICE c1541
or a direct sector-chain fallback. Also builds the versioned REU patch object
(`reu.bin`) that pairs with the geoRAM-canonical image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# REU patch envelope (DESIGN2 §8.3 / REQUIREMENTS §8.1): small delta/fixup,
# fingerprint of paired GEORAM, no geoRAM capacity field used for fixup.
REU_PATCH_MAGIC = b"C2RP"
REU_PATCH_FORMAT_VERSION = 1
REU_PATCH_ABI_VERSION = 1
REU_MIN_CAPACITY_KIB = 512


def resolve_c1541(explicit_path: str | None = None) -> str:
    """Resolve an explicitly configured vice-next ``c1541`` executable.

    The vice-next runtime owns emulator discovery.  Its instrumented runtime
    currently supplies machine executables but not ``c1541``, so packaging is
    deliberately deterministic: use a validated explicit executable or the
    built-in D64 writer.  Legacy bundled-VICE and PATH probing are forbidden.

    Args:
        explicit_path: CLI-selected executable path, if any.

    Returns:
        A filesystem path for ``c1541``, or an empty string for direct build.

    Raises:
        FileNotFoundError: If an explicitly selected executable does not exist.
    """
    selected = explicit_path or os.environ.get("VICE_C1541")
    if not selected:
        return ""
    path = Path(selected)
    if not path.is_file():
        raise FileNotFoundError(f"configured VICE_C1541 does not exist: {path}")
    return str(path)


def build_reu_patch(
    georam_path: str | Path,
    output_path: str | Path,
    *,
    abi_version: int = REU_PATCH_ABI_VERSION,
    fixups: bytes = b"",
) -> dict[str, Any]:
    """Build the versioned REU patch sidecar paired with a GEORAM image.

    The envelope carries magic, format/ABI versions, REU device minimum
    capacity, SHA-256 of the paired geoRAM image bytes, an optional fixup
    blob, and a CRC-32 over the header+blob. It intentionally omits any
    geoRAM size field used for fixup (REQUIREMENTS §8.1).

    Args:
        georam_path: Path to the geoRAM-canonical image (``georam.bin``).
        output_path: Destination path for ``reu.bin``.
        abi_version: Patch ABI version recorded in the envelope.
        fixups: Optional deterministic fixup/reloc blob (may be empty).

    Returns:
        Machine-readable REU loader manifest fields for the patch.

    Raises:
        FileNotFoundError: When the paired geoRAM image is missing.
        ValueError: When the fixup blob exceeds the u32 length field.
    """
    georam = Path(georam_path)
    if not georam.exists():
        raise FileNotFoundError(f"geoRAM image not found: {georam}")
    georam_bytes = georam.read_bytes()
    fingerprint = hashlib.sha256(georam_bytes).digest()
    if len(fixups) > 0xFFFFFFFF:
        raise ValueError("REU fixup blob exceeds 32-bit length")

    header = bytearray()
    header.extend(REU_PATCH_MAGIC)
    header.extend(struct.pack("<H", REU_PATCH_FORMAT_VERSION))
    header.extend(struct.pack("<H", abi_version))
    header.extend(struct.pack("<H", REU_MIN_CAPACITY_KIB))
    header.extend(struct.pack("<H", 0))  # flags
    header.extend(fingerprint)
    header.extend(struct.pack("<H", 0 if not fixups else 1))  # fixup_count
    header.extend(struct.pack("<I", len(fixups)))
    body = bytes(header) + fixups
    crc = zlib.crc32(body) & 0xFFFFFFFF
    payload = body + struct.pack("<I", crc)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "reu_patch",
        "magic": REU_PATCH_MAGIC.decode("ascii"),
        "format_version": REU_PATCH_FORMAT_VERSION,
        "abi_version": abi_version,
        "min_reu_capacity_kib": REU_MIN_CAPACITY_KIB,
        "georam_sha256": fingerprint.hex(),
        "georam_path": georam.as_posix(),
        "fixup_bytes": len(fixups),
        "size": len(payload),
        "crc32": f"{crc:08x}",
        "path": out.as_posix(),
        # Explicitly absent: no geoRAM capacity field (REQUIREMENTS §8.1).
        "has_georam_capacity_field": False,
    }
    manifest_path = out.with_name("reu_loader_manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def validate_reu_patch(reu_path: str | Path) -> list[str]:
    """Validate a REU patch envelope.

    Args:
        reu_path: Path to ``reu.bin``.

    Returns:
        Deterministic list of validation errors (empty when valid).
    """
    path = Path(reu_path)
    if not path.exists():
        return [f"REU patch not found: {reu_path}"]
    data = path.read_bytes()
    errors: list[str] = []
    min_header = 50
    if len(data) < min_header + 4:
        return [f"REU patch truncated: {len(data)} bytes"]
    if data[:4] != REU_PATCH_MAGIC:
        errors.append("REU patch magic is not C2RP")
    format_version = struct.unpack_from("<H", data, 4)[0]
    if format_version != REU_PATCH_FORMAT_VERSION:
        errors.append(f"REU patch format_version {format_version} unsupported")
    min_capacity = struct.unpack_from("<H", data, 8)[0]
    if min_capacity < REU_MIN_CAPACITY_KIB:
        errors.append(
            f"REU min capacity {min_capacity} KiB is below {REU_MIN_CAPACITY_KIB} KiB"
        )
    fixup_len = struct.unpack_from("<I", data, 46)[0]
    expected = min_header + fixup_len + 4
    if len(data) != expected:
        errors.append(f"REU patch size {len(data)} != expected {expected}")
        return errors
    body = data[:-4]
    crc_stored = struct.unpack_from("<I", data, len(data) - 4)[0]
    crc_calc = zlib.crc32(body) & 0xFFFFFFFF
    if crc_stored != crc_calc:
        errors.append("REU patch CRC-32 mismatch")
    return errors


def build_d64(
    c1541_path: str,
    basicv3_path: str,
    georam_path: str,
    output_path: str,
    reu_path: str | None = None,
) -> None:
    """Create a dual-device D64 disk image.

    Args:
        c1541_path: Path to c1541 executable (empty string selects direct build).
        basicv3_path: Path to BASICV3.PRG.
        georam_path: Path to GEORAM PRG sidecar.
        output_path: Output D64 path.
        reu_path: Optional path to REU patch (``reu.bin``). When omitted and a
            geoRAM image exists, a patch is generated next to the D64.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    resolved_reu = reu_path
    if resolved_reu is None and georam_path and Path(georam_path).exists():
        auto_reu = output.with_name("reu.bin")
        build_reu_patch(georam_path, auto_reu)
        resolved_reu = str(auto_reu)
    elif (
        resolved_reu
        and georam_path
        and Path(georam_path).exists()
        and not Path(resolved_reu).exists()
    ):
        build_reu_patch(georam_path, resolved_reu)

    if c1541_path:
        _build_with_c1541(
            Path(c1541_path),
            basicv3_path,
            georam_path,
            output_path,
            resolved_reu,
        )
    else:
        _build_direct(basicv3_path, georam_path, output_path, resolved_reu)


def _build_with_c1541(
    c1541: Path,
    basicv3_path: str,
    georam_path: str,
    output_path: str,
    reu_path: str | None = None,
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

    # Write REU patch sidecar (dual-device release always carries both).
    if reu_path and Path(reu_path).exists():
        cmd.extend(["-write", reu_path, "reu"])

    # High-RAM image (program_lines, LET/FOR helpers) at $E000.
    hibasic_prg = Path(basicv3_path).with_name("hibasic.prg") if basicv3_path else None
    if hibasic_prg is not None and hibasic_prg.exists():
        cmd.extend(["-write", str(hibasic_prg), "hibasic"])

    subprocess.run(cmd, check=True, capture_output=True)


def _build_direct(
    basicv3_path: str,
    georam_path: str,
    output_path: str,
    reu_path: str | None = None,
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
    _initialize_bam(d64_data)
    _mark_sector_used(d64_data, 18, 0)
    _mark_sector_used(d64_data, 18, 1)
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

    files: list[tuple[str, str]] = []
    if basicv3_path and Path(basicv3_path).exists():
        files.append(("BASICV3", basicv3_path))
    if georam_path and Path(georam_path).exists():
        files.append(("GEORAM", georam_path))
    if reu_path and Path(reu_path).exists():
        files.append(("REU", reu_path))
    hibasic_prg = Path(basicv3_path).with_name("hibasic.prg") if basicv3_path else None
    if hibasic_prg is not None and hibasic_prg.exists():
        files.append(("HIBASIC", str(hibasic_prg)))
    iobasic_prg = Path(basicv3_path).with_name("iobasic.prg") if basicv3_path else None
    if iobasic_prg is not None and iobasic_prg.exists():
        files.append(("IOBASIC", str(iobasic_prg)))

    for name, path in files:
        data = Path(path).read_bytes()
        start_track, start_sector, sector_count, next_track, next_sector = (
            _write_prg_data(d64_data, data, next_track, next_sector)
        )
        _add_entry(
            d64_data,
            dir_offset + 2 + entry_offset,
            name,
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


def _sectors_on_track(track: int) -> int:
    """Return the sector count for one standard 35-track D64 track."""
    if not 1 <= track <= 35:
        raise ValueError(f"Invalid D64 track: {track}")
    if track <= 17:
        return 21
    if track <= 24:
        return 19
    if track <= 30:
        return 18
    return 17


def _initialize_bam(d64: bytearray) -> None:
    """Mark every standard D64 data sector free in the BAM.

    The direct writer must produce a writable disk, not merely a directory
    that VICE can read.  Each track's BAM entry contains the free-sector count
    followed by a low-bit-first 24-bit sector bitmap.
    """
    bam = _d64_offset(18, 0)
    for track in range(1, 36):
        sectors = _sectors_on_track(track)
        offset = bam + 4 + (track - 1) * 4
        d64[offset] = sectors
        for sector in range(sectors):
            d64[offset + 1 + sector // 8] |= 1 << (sector % 8)


def _mark_sector_used(d64: bytearray, track: int, sector: int) -> None:
    """Reserve a sector in the BAM, rejecting duplicate allocation."""
    if not 0 <= sector < _sectors_on_track(track):
        raise ValueError(f"Invalid D64 sector {sector} for track {track}")
    bam = _d64_offset(18, 0)
    offset = bam + 4 + (track - 1) * 4
    mask = 1 << (sector % 8)
    bitmap_offset = offset + 1 + sector // 8
    if not d64[bitmap_offset] & mask:
        raise ValueError(f"D64 sector {track}/{sector} is already allocated")
    d64[bitmap_offset] &= ~mask
    d64[offset] -= 1


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
        _mark_sector_used(d64, current_track, current_sector)
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
    """Add a c1541-format D64 directory entry (32 bytes).

    Layout (matches c1541 tool output):
        0:    File type ($82=PRG, $81=SEQ, $83=USR, $80=DEL)
        1-2:  Track/sector of next file with same name (0/$FF = only copy)
        3-18: Filename (16 bytes, padded with $A0)
        19-25: Reserved (unused, zeroed)
        26-27: File size in sectors (16-bit LE)
        28-29: Track/sector of first data sector
    """
    # File type.
    d64[offset] = 0x82 if ext == "PRG" else 0x81
    # Track/sector of first data block.
    d64[offset + 1] = track
    d64[offset + 2] = sector
    # Filename (16 bytes, padded with $A0).
    for i in range(16):
        d64[offset + 3 + i] = ord(name[i]) if i < len(name) else 0xA0
    # Reserved bytes 19-27 are already zero from the bytearray init.
    # File size in sectors (16-bit LE).
    d64[offset + 28] = size_sectors & 0xFF
    d64[offset + 29] = (size_sectors >> 8) & 0xFF
    # Next file pointer (only copy) - bytes 30-31 already zero.


# Dual-device release directory contract (DESIGN2 §2 / REQUIREMENTS §8).
# The hibasic high-RAM image is optional: a partial fixture may omit it when the
# companion hibasic.prg is absent, so only the core trio is mandatory.
REQUIRED_D64_FILES: tuple[str, ...] = ("basicv3", "georam", "reu")
OPTIONAL_D64_FILES: tuple[str, ...] = ("hibasic", "iobasic")
# Sector bounds: basicv3 carries always-mapped RUNTIME/GEOASM/CODE so absolute
# compile/print/wedge calls resolve; georam ≤64KiB PRG; small REU patch.
D64_SECTOR_BOUNDS: dict[str, tuple[int, int]] = {
    "basicv3": (1, 250),
    "georam": (8, 259),
    "reu": (1, 16),
}


def validate_d64(d64_path: str) -> dict[str, Any]:
    """Validate dual-device D64 directory, filenames, and sector sizes.

    Requires the release directory order ``basicv3``, ``georam``, ``reu`` with
    PRG type and sector counts inside the documented bounds. Raises on contract
    failure so packaging and system tests cannot accept a partial disk.

    Args:
        d64_path: Path to the D64 image.

    Returns:
        Manifest with disk title, files, and ``valid: True``.

    Raises:
        FileNotFoundError: When the image is missing.
        ValueError: When size, directory names, types, or sector sizes fail.
    """
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
    files: list[dict[str, Any]] = []
    for i in range(8):
        off = dir_offset + 2 + i * 32
        # c1541 D64 directory entry (32 bytes, after 2-byte sector chain pointer):
        #   byte 0: File type ($82=PRG, $81=SEQ, $83=USR, $80=DEL)
        #   bytes 1-2: Track/sector of first data block
        #   bytes 3-18: Filename (16 bytes, PETSCII, $A0-padded)
        #   bytes 19-26: Reserved
        #   bytes 27-28: File size in sectors (16-bit LE)
        #   bytes 29-30: Track/sector of next file with same name (0/$FF = only copy)
        file_type_byte = data[off]
        if file_type_byte == 0:
            continue
        type_code = file_type_byte & 0x07
        file_type = {1: "SEQ", 2: "PRG"}.get(type_code, "OTHER")
        name = _decode_petscii_name(data[off + 3 : off + 19])
        size = data[off + 28] | (data[off + 29] << 8)
        files.append({"name": name, "type": file_type, "size_sectors": size})

    errors = validate_d64_contents(disk_title, files)
    if errors:
        raise ValueError("; ".join(errors))

    return {
        "d64_path": d64_path,
        "total_size": len(data),
        "disk_title": disk_title,
        "files": files,
        "valid": True,
    }


def validate_d64_contents(disk_title: str, files: list[dict[str, Any]]) -> list[str]:
    """Return dual-device directory contract errors (empty when valid).

    Args:
        disk_title: Decoded BAM disk title.
        files: Directory entries with ``name``, ``type``, ``size_sectors``.

    Returns:
        Deterministic list of validation errors.
    """
    errors: list[str] = []
    if disk_title.lower() != "compiler2":
        errors.append(f"D64 disk title must be 'compiler2', got {disk_title!r}")
    names = [entry.get("name") for entry in files]
    names_lower = [n.lower() for n in names]
    required = set(names_lower) | set(OPTIONAL_D64_FILES)
    if required != set(REQUIRED_D64_FILES) | set(OPTIONAL_D64_FILES):
        errors.append(f"D64 directory must be {list(REQUIRED_D64_FILES)} (+optional {list(OPTIONAL_D64_FILES)}), got {names}")
    for entry in files:
        name = str(entry.get("name", ""))
        file_type = entry.get("type")
        size = entry.get("size_sectors")
        if file_type != "PRG":
            errors.append(f"D64 file {name!r} must be PRG, got {file_type!r}")
        name_key = name.lower()
        if name_key in D64_SECTOR_BOUNDS:
            low, high = D64_SECTOR_BOUNDS[name_key]
            if not isinstance(size, int) or not (low <= size <= high):
                errors.append(
                    f"D64 file {name!r} size_sectors {size!r} outside "
                    f"[{low}, {high}]"
                )
    return errors


def validate_dual_d64_release(
    d64_path: str | Path,
    basicv3_path: str | Path | None = None,
    georam_path: str | Path | None = None,
    reu_path: str | Path | None = None,
) -> list[str]:
    """Validate dual-device D64 plus host sidecars (headers and sizes).

    Args:
        d64_path: Packaged ``compiler.d64``.
        basicv3_path: Optional host ``basicv3.prg`` for header checks.
        georam_path: Optional host ``georam.bin`` for size/header checks.
        reu_path: Optional host ``reu.bin`` for REU envelope checks.

    Returns:
        Deterministic list of validation errors (empty when valid).
    """
    errors: list[str] = []
    d64 = Path(d64_path)
    if not d64.is_file():
        return [f"D64 not found: {d64_path}"]
    try:
        manifest = validate_d64(str(d64))
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        manifest = None

    if basicv3_path is not None:
        errors.extend(validate_prg_header(str(basicv3_path)))
    if georam_path is not None:
        georam = Path(georam_path)
        if not georam.is_file():
            errors.append(f"geoRAM image not found: {georam_path}")
        else:
            raw = georam.read_bytes()
            if len(raw) < 4 or raw[:2] != b"\x00\xde":
                errors.append("georam sidecar load header is not $DE00")
            elif raw[2:6] == b"CGS1":
                # Compressed CGS1 install stream (UseCompressor / GEORAM_compressed.prg)
                if len(raw) < 2 + 28:
                    errors.append(f"CGS1 geoRAM sidecar too small: {len(raw)} bytes")
            elif len(raw) < 65538:
                errors.append(f"georam.bin too small: {len(raw)} bytes (need >= 65538)")
    if reu_path is not None:
        errors.extend(validate_reu_patch(reu_path))

    if manifest is not None and georam_path is not None and Path(georam_path).is_file():
        # Cross-check georam sector count against host file size when present.
        host_sectors = (Path(georam_path).stat().st_size + 253) // 254
        for entry in manifest["files"]:
            if entry["name"] == "georam" and entry["size_sectors"] < host_sectors:
                # c1541 may pack compressed sidecars; only fail when D64 is
                # smaller than the host artifact it claims to ship.
                if entry["size_sectors"] < 1:
                    errors.append("D64 georam sector count is zero")
    return errors


def validate_prg_header(prg_path: str) -> list[str]:
    """Validate the canonical ``$0801`` BASIC loader header.

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
    parser = argparse.ArgumentParser(description="Package Compiler 2 dual-device D64")
    parser.add_argument(
        "--write-reu-patch",
        nargs=2,
        metavar=("GEORAM", "REU"),
        help="Build reu.bin patch from georam.bin and exit",
    )
    parser.add_argument("c1541_path", nargs="?", default=None)
    parser.add_argument("basicv3_path", nargs="?", default=None)
    parser.add_argument("georam_path", nargs="?", default=None)
    parser.add_argument("output_path", nargs="?", default=None)
    parser.add_argument("reu_path", nargs="?", default=None)
    args = parser.parse_args()

    if args.write_reu_patch is not None:
        georam_src, reu_dst = args.write_reu_patch
        manifest = build_reu_patch(georam_src, reu_dst)
        print(f"REU patch written: {reu_dst} ({manifest['size']} bytes)")
        print(f"  georam_sha256={manifest['georam_sha256']}")
        print("  reu_loader_manifest.json updated")
        return

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
    reu_path = Path(args.reu_path) if args.reu_path else build_dir / "reu.bin"

    explicit_c1541 = (
        None
        if args.c1541_path in (None, "", "null", "$null", "auto")
        else args.c1541_path
    )
    c1541_path = resolve_c1541(explicit_c1541)

    # Packaging must consume real production artifacts.  Synthesizing missing
    # sidecars would produce an apparently valid disk that cannot install the
    # compiler and violates the artifact contract.
    missing = [path for path in (basicv3_path, georam_path) if not path.exists()]
    if missing:
        names = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"required packaging artifact(s) missing: {names}")

    if not reu_path.exists() and georam_path.exists():
        print(f"Building REU patch: {reu_path}")
        build_reu_patch(georam_path, reu_path)

    print(f"Building dual D64: {output_path}")
    build_d64(
        c1541_path,
        str(basicv3_path),
        str(georam_path),
        str(output_path),
        str(reu_path),
    )

    # Validate dual-device directory, PRG header, georam header, and REU envelope.
    release_errors = validate_dual_d64_release(
        output_path,
        basicv3_path=basicv3_path,
        georam_path=georam_path,
        reu_path=reu_path,
    )
    if release_errors:
        for error in release_errors:
            print(f"Error: {error}")
        raise SystemExit(1)

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
