"""Populate the release geoRAM image from linked cold/compiler segments."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

GEORAM_PAYLOAD_SIZE = 65536
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
) -> None:
    """Overlay linked routine bytes at their generated geoRAM placements."""
    if not routine_directory_path.exists():
        raise FileNotFoundError(
            f"routine directory not found: {routine_directory_path}"
        )
    labels = _read_labels(labels_path)
    directory = json.loads(routine_directory_path.read_text(encoding="utf-8"))
    for name, record in directory.get("routines", {}).items():
        if record.get("layer") != "georam":
            continue
        if name not in labels:
            raise ValueError(f"linked label missing for geoRAM routine: {name}")
        block = int(record["block"])
        page = int(record["page"])
        offset = int(record["offset"])
        destination = (block * 64 + page) * 256 + offset
        if destination >= GEORAM_PAYLOAD_SIZE:
            raise ValueError(f"geoRAM placement outside payload for {name}")
        source = 2 + labels[name] - load_address
        if source < 2 or source >= len(compiler):
            raise ValueError(f"linked label for {name} falls outside compiler image")
        length = min(
            256 - offset, GEORAM_PAYLOAD_SIZE - destination, len(compiler) - source
        )
        payload[destination : destination + length] = compiler[source : source + length]


def populate(
    map_path: Path,
    compiler_path: Path,
    output_path: Path,
    labels_path: Path | None = None,
    routine_directory_path: Path | None = None,
    hibasic_path: Path | None = None,
) -> None:
    """Write linked cold/compiler bytes into a padded geoRAM PRG.

    Args:
        map_path: ld65 map containing the required segment ranges.
        compiler_path: PRG containing the linked normal-RAM image.
        output_path: Destination geoRAM PRG.
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
        if name == "HIBASIC":
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
    if len(linked) > GEORAM_PAYLOAD_SIZE:
        raise ValueError("linked cold payload exceeds 64 KiB geoRAM image")

    payload = bytearray(GEORAM_PAYLOAD_SIZE)
    payload[: len(linked)] = linked
    if labels_path is not None and routine_directory_path is not None:
        _overlay_directory_routines(
            payload, compiler, load_address, labels_path, routine_directory_path
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
