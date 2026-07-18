"""Populate the release geoRAM image from linked cold/compiler segments."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Minimum release pad (legacy 64 KiB image) and hard capacity ceiling
# (REQUIREMENTS §8.1: base image must fully fit in 512 KiB / 2048 pages).
GEORAM_MIN_PAYLOAD_SIZE = 65536
GEORAM_MAX_PAYLOAD_SIZE = 512 * 1024
GEORAM_MAX_PAGES = 2048
GEORAM_PAGE_SIZE = 256
GEORAM_LOAD_ADDRESS = b"\x00\xde"
COLD_SEGMENTS = (
    "COMPILER",
    "EDITOR",
    "COMPRESSOR",
    "GRAPHICS",
    "RUNTIME",
    "GEOASM",
    "HIBASIC",
    "CODE",
    "RODATA",
)
SEGMENT_RE = re.compile(
    r"^([A-Z0-9_]+)\s+([0-9A-Fa-f]{6})\s+" r"([0-9A-Fa-f]{6})\s+([0-9A-Fa-f]{6})",
    re.MULTILINE,
)
LABEL_RE = re.compile(r"^al\s+([0-9A-Fa-f]{6})\s+\.([A-Za-z0-9_]+)$", re.MULTILINE)

# Backward-compatible alias used by older tests/callers.
GEORAM_PAYLOAD_SIZE = GEORAM_MIN_PAYLOAD_SIZE


def payload_size_for(content_length: int) -> int:
    """Return padded payload size for content, enforcing the 512 KiB ceiling.

    Args:
        content_length: Occupied payload bytes before padding.

    Returns:
        Padded size in bytes (page-aligned, at least ``GEORAM_MIN_PAYLOAD_SIZE``).

    Raises:
        ValueError: When content exceeds the 512 KiB / 2048-page budget.
    """
    if content_length > GEORAM_MAX_PAYLOAD_SIZE:
        raise ValueError(
            f"geoRAM image exceeds 512 KiB budget: {content_length} bytes > "
            f"{GEORAM_MAX_PAYLOAD_SIZE} limit ({GEORAM_MAX_PAGES} pages)"
        )
    pages = (content_length + GEORAM_PAGE_SIZE - 1) // GEORAM_PAGE_SIZE
    if pages > GEORAM_MAX_PAGES:
        raise ValueError(
            f"geoRAM image exceeds 2048 pages: {pages} pages > {GEORAM_MAX_PAGES}"
        )
    padded = max(GEORAM_MIN_PAYLOAD_SIZE, pages * GEORAM_PAGE_SIZE)
    if padded > GEORAM_MAX_PAYLOAD_SIZE:
        raise ValueError(
            f"geoRAM image exceeds 512 KiB budget after padding: {padded} bytes"
        )
    return padded


def _read_labels(labels_path: Path) -> dict[str, int]:
    """Return ca65 label addresses keyed by symbol name."""
    if not labels_path.exists():
        raise FileNotFoundError(f"label file not found: {labels_path}")
    return {
        match.group(2): int(match.group(1), 16)
        for match in LABEL_RE.finditer(labels_path.read_text(encoding="utf-8"))
    }


def _overlay_directory_routines(
    payload: bytearray,
    compiler: bytes,
    load_address: int,
    labels_path: Path,
    routine_directory_path: Path,
    hibasic: bytes = b"",
) -> int:
    """Overlay linked routine bytes at their generated geoRAM placements.

    Linked labels may live in the normal-RAM compiler PRG ($0801+) or in the
    HIBASIC image ($E000+) when cold segments are placed in RAM_HIGH.

    Returns:
        Highest exclusive payload offset written by an overlay.
    """
    if not routine_directory_path.exists():
        raise FileNotFoundError(
            f"routine directory not found: {routine_directory_path}"
        )
    labels = _read_labels(labels_path)
    directory = json.loads(routine_directory_path.read_text(encoding="utf-8"))
    max_end = 0
    for name, record in directory.get("routines", {}).items():
        if record.get("layer") != "georam":
            continue
        if name not in labels:
            raise ValueError(f"linked label missing for geoRAM routine: {name}")
        block = int(record["block"])
        page = int(record["page"])
        offset = int(record["offset"])
        destination = (block * 64 + page) * 256 + offset
        if destination >= GEORAM_MAX_PAYLOAD_SIZE:
            raise ValueError(
                f"geoRAM placement outside 512 KiB budget for {name}: "
                f"offset {destination}"
            )
        address = labels[name]
        if address >= 0xE000:
            source = address - 0xE000
            if source < 0 or source >= len(hibasic):
                raise ValueError(f"linked label for {name} falls outside hibasic image")
            source_image = hibasic
        else:
            source = 2 + address - load_address
            if source < 2 or source >= len(compiler):
                raise ValueError(
                    f"linked label for {name} falls outside compiler image"
                )
            source_image = compiler
        length = min(
            256 - offset,
            GEORAM_MAX_PAYLOAD_SIZE - destination,
            len(source_image) - source,
        )
        end = destination + length
        if end > len(payload):
            raise ValueError(
                f"geoRAM placement for {name} exceeds allocated payload "
                f"({end} > {len(payload)})"
            )
        payload[destination : destination + length] = source_image[
            source : source + length
        ]
        max_end = max(max_end, end)
    return max_end


def populate(
    map_path: Path,
    compiler_path: Path,
    output_path: Path,
    labels_path: Path | None = None,
    routine_directory_path: Path | None = None,
    hibasic_path: Path | None = None,
) -> None:
    """Write linked cold/compiler bytes into a padded geoRAM PRG.

    The image is padded to at least 64 KiB and hard-fails if content or
    directory placements would exceed 512 KiB / 2048 pages
    (REQUIREMENTS §8.1).

    Args:
        map_path: ld65 map containing the required segment ranges.
        compiler_path: PRG containing the linked normal-RAM image.
        output_path: Destination geoRAM PRG.
        labels_path: Optional ca65 label file for directory overlays.
        routine_directory_path: Optional routine directory for overlays.
        hibasic_path: Optional HIBASIC binary (defaults beside compiler).
    """
    matches = {
        match.group(1): (int(match.group(2), 16), int(match.group(4), 16))
        for match in SEGMENT_RE.finditer(map_path.read_text(encoding="utf-8"))
    }
    missing = [name for name in COLD_SEGMENTS if name not in matches]
    if missing:
        raise ValueError(f"linker map lacks cold segments: {', '.join(missing)}")

    compiler = compiler_path.read_bytes()
    if len(compiler) < 2:
        raise ValueError("compiler image has no PRG load address")
    load_address = int.from_bytes(compiler[:2], "little")
    hibasic = b""
    if hibasic_path is None:
        hibasic_path = compiler_path.with_name("hibasic.bin")
    if hibasic_path.exists():
        hibasic = hibasic_path.read_bytes()
    linked = bytearray()
    for name in COLD_SEGMENTS:
        start, size = matches[name]
        # Segments linked into RAM_HIGH ($E000+) are materialized in hibasic.bin
        # (HIBASIC, and cold EDITOR/WEDGE/COMPRESSOR/GRAPHICS when placed there).
        if start >= 0xE000 or name == "HIBASIC":
            first = start - 0xE000
            last = first + size
            if first < 0 or last > len(hibasic):
                raise ValueError(f"linked {name} segment falls outside hibasic image")
            linked.extend(hibasic[first:last])
        else:
            first = 2 + start - load_address
            last = first + size
            if first < 2 or last > len(compiler):
                raise ValueError(f"linked {name} segment falls outside compiler image")
            linked.extend(compiler[first:last])
    if not linked or len(set(linked)) < 3:
        raise ValueError("linked cold payload is empty or fill-only")
    if len(linked) > GEORAM_MAX_PAYLOAD_SIZE:
        raise ValueError(
            f"linked cold payload exceeds 512 KiB geoRAM budget: "
            f"{len(linked)} bytes > {GEORAM_MAX_PAYLOAD_SIZE}"
        )

    # Directory overlays may land beyond the linear cold pack; size the
    # payload for the higher of linear content and max placement end.
    provisional_size = payload_size_for(len(linked))
    if labels_path is not None and routine_directory_path is not None:
        # Probe max placement so we allocate enough room before overlaying.
        directory = json.loads(routine_directory_path.read_text(encoding="utf-8"))
        max_end = len(linked)
        for name, record in directory.get("routines", {}).items():
            if record.get("layer") != "georam":
                continue
            block = int(record["block"])
            page = int(record["page"])
            # Assume up to a full page remainder for sizing.
            end = (block * 64 + page) * 256 + 256
            if end > GEORAM_MAX_PAYLOAD_SIZE:
                raise ValueError(
                    f"geoRAM placement for {name} exceeds 512 KiB budget "
                    f"(end={end})"
                )
            max_end = max(max_end, end)
        provisional_size = payload_size_for(max_end)

    payload = bytearray(provisional_size)
    payload[: len(linked)] = linked
    if labels_path is not None and routine_directory_path is not None:
        _overlay_directory_routines(
            payload,
            compiler,
            load_address,
            labels_path,
            routine_directory_path,
            hibasic=hibasic,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(GEORAM_LOAD_ADDRESS + payload)


def main() -> None:
    """Populate the build geoRAM image."""
    parser = argparse.ArgumentParser()
    parser.add_argument("map_path", type=Path)
    parser.add_argument("compiler_path", type=Path)
    parser.add_argument("output_path", type=Path)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--routine-directory", type=Path)
    args = parser.parse_args()
    populate(
        args.map_path,
        args.compiler_path,
        args.output_path,
        args.labels,
        args.routine_directory,
        None,
    )


if __name__ == "__main__":
    main()
