"""Extracts file-backed RAM segments from the linked binary.

Parses the linker map, extracts resident/loader segment ranges, and writes
the payload to build/compile.bin.
"""

import os
import re
import sys
from typing import Any, Dict, List

# Segments that live only on expansion (or RAM_HIGH) and must not be folded
# into the low-RAM compile.bin span. RUNTIME/GEOASM/CODE/RODATA are
# intentionally *not* listed: they are linked at absolute low-RAM addresses
# and must be present in the installed PRG so absolute JSRs from the resident
# editor and from geoRAM XIP entry stubs reach the real compile/print/wedge
# graph. Pure expansion-only cold packs (EDITOR/HIBASIC/etc.) stay excluded.
GEORAM_BACKED_SEGMENTS = {
    "COMPILER",
    "EDITOR",
    "COMPRESSOR",
    "GRAPHICS",
    "HIBASIC",
}

# Segments placed in RAM_HIGH ($E000+, hibasic.bin) must not be folded into the
# low-RAM compile.bin span extracted from compiler.bin.
RAM_HIGH_SEGMENTS = {
    "EDITOR_PINNED",
    "HIBASIC",
    "EDITOR",
    "WEDGE",
    "COMPRESSOR",
}
RAM_HIGH_START = 0xE000


def parse_segments(map_path: str) -> List[Dict[str, Any]]:
    """Parses segments from the linker map file.

    Args:
        map_path: Path to compiler.map.

    Returns:
        List of segment dictionaries containing name, start, size, and type.
    """
    segments: List[Dict[str, Any]] = []
    if not os.path.exists(map_path):
        return segments

    with open(map_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Look for segment list section in map file
    # Segment list format in cc65/ld65 map files usually has:
    # Name                   Start     End       Size      Align
    # ---------------------------------------------------------
    # RESIDENT               000801    001A23    001223    00001
    pattern = re.compile(
        r"^([A-Z0-9_]+)\s+([0-9A-Fa-f]{6})\s+([0-9A-Fa-f]{6})\s+([0-9A-Fa-f]{6})",
        re.MULTILINE,
    )
    for match in pattern.finditer(content):
        name = match.group(1)
        start = int(match.group(2), 16)
        end = int(match.group(3), 16)
        size = int(match.group(4), 16)

        # Skip ZP and BSS segments (non-file backed)
        if name in ("ZEROPAGE", "COMPILER_BSS", "BSS"):
            continue

        segments.append({"name": name, "start": start, "end": end, "size": size})

    return segments


def extract_payload(
    binary_path: str, segments: List[Dict[str, Any]], output_path: str
) -> None:
    """Extracts segments from the full compiler.bin binary.

    Args:
        binary_path: Path to full linker compiler.bin.
        segments: Parsed segments metadata.
        output_path: Path to save the extracted payload.
    """
    if not os.path.exists(binary_path):
        raise FileNotFoundError(f"Source binary not found: {binary_path}")

    with open(binary_path, "rb") as f:
        full_data = f.read()

    if len(full_data) < 2:
        raise ValueError("Compiler PRG is missing its load address")
    load_address = full_data[0] | (full_data[1] << 8)

    ram_segments = [
        segment
        for segment in segments
        if "GEORAM_PAGE" not in segment["name"]
        and segment["name"] not in ("ZEROPAGE", "VECTORS")
        and segment["name"] not in GEORAM_BACKED_SEGMENTS
        and segment["name"] not in RAM_HIGH_SEGMENTS
        # HIBASIC / RAM_HIGH ($E000+) is a separate ld65 output (hibasic.bin).
        and int(segment["start"]) < RAM_HIGH_START
        and int(segment["end"]) < RAM_HIGH_START
    ]
    if not ram_segments:
        raise ValueError("Linker map contains no file-backed RAM segments")

    # Preserve linked address gaps, including BSS/no-load reservations. Absolute
    # calls remain valid only when bytes after a gap retain their linked address.
    start = min(segment["start"] for segment in ram_segments)
    end = max(segment["end"] for segment in ram_segments)
    first = 2 + start - load_address
    last = 2 + end - load_address + 1
    if first < 2 or last > len(full_data):
        raise ValueError("Linked RAM span falls outside compiler.bin")
    payload = bytearray(full_data[first:last])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(payload)


def validate_payload(
    binary_path: str,
    segments: List[Dict[str, Any]],
    payload_path: str,
) -> List[str]:
    """Validate an extracted payload against its linked RAM span.

    Args:
        binary_path: Compiler PRG containing the linked image.
        segments: Parsed linker segment records.
        payload_path: Extracted payload to validate.

    Returns:
        A list of deterministic validation errors, empty when valid.
    """
    if not os.path.exists(binary_path):
        return [f"source binary not found: {binary_path}"]
    if not os.path.exists(payload_path):
        return [f"payload not found: {payload_path}"]
    ram_segments = [
        segment
        for segment in segments
        if "GEORAM_PAGE" not in segment["name"]
        and segment["name"] not in ("ZEROPAGE", "VECTORS")
        and segment["name"] not in GEORAM_BACKED_SEGMENTS
        and segment["name"] not in RAM_HIGH_SEGMENTS
        and int(segment["start"]) < RAM_HIGH_START
        and int(segment["end"]) < RAM_HIGH_START
    ]
    if not ram_segments:
        return ["linker map contains no file-backed RAM segments"]
    with open(binary_path, "rb") as source_file:
        source = source_file.read()
    if len(source) < 2:
        return ["compiler PRG is missing its load address"]
    load_address = source[0] | (source[1] << 8)
    start = min(int(segment["start"]) for segment in ram_segments)
    end = max(int(segment["end"]) for segment in ram_segments)
    first = 2 + start - load_address
    last = 2 + end - load_address + 1
    if first < 2 or last > len(source):
        return ["linked RAM span falls outside compiler.bin"]
    with open(payload_path, "rb") as payload_file:
        actual = payload_file.read()
    expected = source[first:last]
    if actual != expected:
        return [
            f"payload bytes differ: expected {len(expected)} bytes, "
            f"found {len(actual)}"
        ]
    return []


def main() -> None:
    """Main execution of the segments extraction tool."""
    if len(sys.argv) < 4:
        # Default fallback locations
        map_path = "build/compiler.map"
        binary_path = "build/compiler.bin"
        output_path = "build/compile.bin"
    else:
        map_path = sys.argv[1]
        binary_path = sys.argv[2]
        output_path = sys.argv[3]

    if not os.path.exists(map_path) or not os.path.exists(binary_path):
        print("Warning: Map or binary not found. Skipping segment extraction.")
        return

    segments = parse_segments(map_path)
    extract_payload(binary_path, segments, output_path)
    errors = validate_payload(binary_path, segments, output_path)
    if errors:
        raise ValueError("; ".join(errors))
    print("Segments extracted successfully.")


if __name__ == "__main__":
    main()
