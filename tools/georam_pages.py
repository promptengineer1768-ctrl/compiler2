"""geoRAM page placement, routine IDs, and call directory generation.

Packs routines into geoRAM pages, assigns routine IDs, and generates index tables.
"""

import json
import os
import re
import zlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

GEORAM_CODE_LAYERS = frozenset({"georam", "geoasm"})
MISSING_DIRECTORY_BYTE = 0xFF


def _constant_name(name: str) -> str:
    """Return an assembly-safe uppercase constant suffix for a routine name."""
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def is_georam_routine(routine: Dict[str, Any]) -> bool:
    """Return whether a routine is physically installed in geoRAM.

    Args:
        routine: Routine manifest record.

    Returns:
        True for explicit geoRAM and geoRAM-service (geoasm) routines.
    """
    return routine.get("layer") in GEORAM_CODE_LAYERS


def load_routine_manifest(manifest_path: str) -> List[Dict[str, Any]]:
    """Loads public/test routines from the manifest.

    Args:
        manifest_path: Path to routines.json.

    Returns:
        List of routine dictionaries.
    """
    with open(manifest_path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    result: List[Dict[str, Any]] = data.get("routines", [])
    return result


def assign_page_placement(
    routines: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Tuple[int, int, int]]]:
    """Packs georam layer routines into 256-byte pages without boundary crossing.

    Args:
        routines: List of all routines.

    Returns:
        A tuple containing:
        - List of updated routines.
        - Dict mapping routine name to (block, page, offset).
    """
    georam_routines = [r for r in routines if is_georam_routine(r)]

    placement: Dict[str, Tuple[int, int, int]] = {}
    reserved: set[Tuple[int, int]] = set()

    # Page-bound assembly sources declare their physical page explicitly.  The
    # call directory must follow that physical placement, not the incidental
    # order in routines.json (which changes whenever a non-XIP record is
    # inserted ahead of an existing XIP routine).
    for r in georam_routines:
        explicit_page = r.get("xip_page")
        if explicit_page is None:
            continue
        block = int(r.get("xip_block", 0))
        page = int(explicit_page)
        offset = int(r.get("xip_offset", 0))
        if block < 0 or not 0 <= page < 64 or not 0 <= offset < 256:
            raise ValueError(f"Routine {r['name']} has invalid explicit XIP placement")
        if offset + int(r.get("size_ceiling", 256)) > 256:
            raise ValueError(f"Routine {r['name']} explicit XIP placement crosses page")
        key = (block, page)
        if key in reserved:
            raise ValueError(f"Duplicate explicit XIP page {block}:{page}")
        reserved.add(key)
        placement[r["name"]] = (block, page, offset)

    current_block = 0
    current_page = 0
    current_offset = 0

    for r in georam_routines:
        if r["name"] in placement:
            continue
        size = r.get("size_ceiling", 256)
        if size > 256:
            raise ValueError(
                f"Routine {r['name']} size ceiling {size} exceeds page size 256"
            )

        # If it doesn't fit on the current page, move to the next page.
        # Explicit reservations are skipped so an automatically placed body
        # can never overwrite a hand-bound XIP page.
        if current_offset + size > 256 or (current_block, current_page) in reserved:
            current_offset = 0
            current_page += 1
            if current_page >= 64:
                current_page = 0
                current_block += 1

        while (current_block, current_page) in reserved:
            current_page += 1
            if current_page >= 64:
                current_page = 0
                current_block += 1

        placement[r["name"]] = (current_block, current_page, current_offset)
        current_offset += size

    return routines, placement


def generate_routine_ids(
    routines: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Assigns sequential unique IDs to all routines.

    Args:
        routines: List of routines.

    Returns:
        A tuple of (updated routines list, map of routine name to ID).
    """
    id_map: Dict[str, int] = {}
    for idx, r in enumerate(routines):
        if r["name"] in id_map:
            raise ValueError(f"Duplicate routine name: {r['name']}")
        r["id"] = idx
        id_map[r["name"]] = idx
    return routines, id_map


def generate_call_directory(
    routines: List[Dict[str, Any]],
    placement: Dict[str, Tuple[int, int, int]],
    output_dir: str,
) -> None:
    """Generates the routine_directory.json and include files for assembly.

    Args:
        routines: All routines.
        placement: Routine page placements.
        output_dir: Target output directory.
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. build/routine_directory.json
    directory_data: Dict[str, Any] = {
        "manifest_version": "1.0",
        "routines": {},
    }

    for r in routines:
        name = r["name"]
        if is_georam_routine(r) and name in placement:
            b, p, o = placement[name]
            directory_data["routines"][name] = {
                "id": r["id"],
                "layer": "georam",
                "logical_layer": r.get("layer"),
                "block": b,
                "page": p,
                "offset": o,
                "address": f"${0xDE00 + o:04X}",
            }
        else:
            directory_data["routines"][name] = {
                "id": r["id"],
                "layer": r.get("layer", "resident"),
                "address": r.get("address", "dynamic"),
            }

    with open(
        os.path.join(output_dir, "routine_directory.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(directory_data, f, indent=2)

    # 2. build/georam_pages.inc for assembly
    inc_lines = [
        "; Auto-generated geoRAM routine lookup tables",
        "; Do not edit manually.",
        "",
    ]

    # Filter geoRAM routines only.
    georam_only = [r for r in routines if is_georam_routine(r)]
    georam_only.sort(key=lambda x: x["id"])

    inc_lines.append(f"GEORAM_ROUTINE_COUNT = {len(georam_only)}")
    for routine in georam_only:
        inc_lines.append(
            f"GEORAM_ROUTINE_ID_{_constant_name(str(routine['name']))} = {routine['id']}"
        )
    inc_lines.append("")

    group_count = (len(routines) + 255) // 256
    directory_bytes = bytearray()
    by_id = {r["id"]: r for r in georam_only}
    for group in range(group_count):
        tables: list[tuple[str, list[int]]] = []
        for table_name, tuple_index in (("blocks", 0), ("pages", 1), ("offsets", 2)):
            values: list[int] = []
            for index in range(256):
                directory_routine = by_id.get(group * 256 + index)
                if directory_routine is None:
                    values.append(MISSING_DIRECTORY_BYTE)
                else:
                    values.append(placement[directory_routine["name"]][tuple_index])
            tables.append((table_name, values))

        for table_name, values in tables:
            inc_lines.append(f"georam_group_{group}_{table_name}:")
            for start in range(0, 256, 16):
                encoded = ", ".join(
                    f"${value:02X}" for value in values[start : start + 16]
                )
                inc_lines.append(f"    .byte {encoded}")
            inc_lines.append("")
            directory_bytes.extend(values)

    directory_crc32 = zlib.crc32(directory_bytes)
    directory_xor = 0
    for value in directory_bytes:
        directory_xor ^= value
    directory_data["directory"] = {
        "group_count": group_count,
        "missing_byte": MISSING_DIRECTORY_BYTE,
        "crc32": f"{directory_crc32:08x}",
        "xor8": f"{directory_xor:02x}",
    }
    inc_lines.extend(
        [
            f"GEORAM_DIRECTORY_GROUP_COUNT = {group_count}",
            f"GEORAM_DIRECTORY_XOR8 = ${directory_xor:02X}",
            f"GEORAM_DIRECTORY_CRC32_0 = ${directory_crc32 & 0xFF:02X}",
            f"GEORAM_DIRECTORY_CRC32_1 = ${(directory_crc32 >> 8) & 0xFF:02X}",
            f"GEORAM_DIRECTORY_CRC32_2 = ${(directory_crc32 >> 16) & 0xFF:02X}",
            f"GEORAM_DIRECTORY_CRC32_3 = ${(directory_crc32 >> 24) & 0xFF:02X}",
            "",
        ]
    )

    with open(os.path.join(output_dir, "georam_pages.inc"), "w", encoding="utf-8") as f:
        f.write("\n".join(inc_lines) + "\n")

    # Rewrite after directory metadata has been computed.
    with open(
        os.path.join(output_dir, "routine_directory.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(directory_data, f, indent=2)


def generate_test_exports(routines: List[Dict[str, Any]], output_dir: str) -> None:
    """Generates test-only entry exports for internal routines.

    Args:
        routines: List of routines.
        output_dir: Target output directory.
    """
    inc_lines = [
        "; Auto-generated test exports",
        "; Do not edit manually.",
        "",
    ]
    for r in routines:
        if r.get("visibility") == "test_only":
            inc_lines.append(f".export {r['name']}")

    with open(os.path.join(output_dir, "test_exports.inc"), "w", encoding="utf-8") as f:
        f.write("\n".join(inc_lines) + "\n")


def validate_no_cross_boundary(
    placement: Dict[str, Tuple[int, int, int]], routines: List[Dict[str, Any]]
) -> bool:
    """Ensures no routine crosses the page window boundary.

    Args:
        placement: Placements dictionary.
        routines: Routines list.

    Returns:
        True if valid.
    """
    for name, (_, _, o) in placement.items():
        r = next(rt for rt in routines if rt["name"] == name)
        size = r.get("size_ceiling", 256)
        if o + size > 256:
            return False
    return True


def validate_linked_placement(
    routines_path: str,
    directory_path: str,
    labels_path: str,
    map_path: str,
) -> List[str]:
    """Validate linked labels against generated geoRAM placements.

    Args:
        routines_path: Authoritative routine manifest.
        directory_path: Generated routine directory.
        labels_path: ld65 label file.
        map_path: ld65 map file proving a linked image exists.

    Returns:
        Deterministically ordered placement, size, and checksum errors.
    """
    errors: set[str] = set()
    if not Path(map_path).exists() or "Segment list:" not in Path(map_path).read_text(
        encoding="utf-8"
    ):
        errors.add("linked map is missing its segment list")
    map_text = Path(map_path).read_text(encoding="utf-8")
    linked_pages = {
        int(match.group(1)): int(match.group(2), 16)
        for match in re.finditer(
            r"^\s*GEORAM_PAGE_(\d+)\s+Offs=[0-9A-Fa-f]+\s+Size=([0-9A-Fa-f]+)",
            map_text,
            re.MULTILINE,
        )
    }
    routines = load_routine_manifest(routines_path)
    directory_data = json.loads(Path(directory_path).read_text(encoding="utf-8"))
    directory = directory_data.get("routines", {})
    label_pattern = re.compile(r"^\s*al\s+([0-9A-Fa-f]{6})\s+\.(\S+)\s*$", re.MULTILINE)
    labels = {
        match.group(2): int(match.group(1), 16)
        for match in label_pattern.finditer(
            Path(labels_path).read_text(encoding="utf-8")
        )
    }
    for routine in routines:
        name = str(routine["name"])
        record = directory.get(name)
        if record is None:
            errors.add(f"routine directory is missing {name}")
            continue
        if not is_georam_routine(routine):
            continue
        if name not in labels:
            errors.add(f"linked label is missing for geoRAM routine {name}")
        try:
            block = int(record["block"])
            page = int(record["page"])
            offset = int(record["offset"])
        except (KeyError, TypeError, ValueError):
            errors.add(f"geoRAM routine {name} has incomplete placement")
            continue
        ceiling = int(routine.get("size_ceiling", 256))
        if block < 0 or not 0 <= page < 64 or not 0 <= offset < 256:
            errors.add(f"geoRAM routine {name} placement is out of range")
        if offset + ceiling > 256:
            errors.add(f"geoRAM routine {name} crosses the $DEFF boundary")
        if record.get("address") != f"${0xDE00 + offset:04X}":
            errors.add(f"geoRAM routine {name} window address disagrees with offset")
        # Every XIP routine has the same linked mirror address ($DE00), so
        # label subtraction across routines measures page aliases rather than
        # routine size.  Validate the linker-owned physical page segment
        # instead.  Page-bound routines occupy offset zero exclusively.
        page_size = linked_pages.get(page)
        # Migration-debt entries can remain in the generated directory before
        # their source body has a GEORAM_PAGE segment.  Their policy audit owns
        # that distinction; this linker check only validates physical pages
        # that the current artifact actually contains.
        if page_size is not None and offset == 0 and page_size > ceiling:
            errors.add(
                f"linked geoRAM page {page} size {page_size} exceeds ceiling {ceiling} for {name}"
            )

    group_count = int(directory_data.get("directory", {}).get("group_count", 0))
    missing = int(
        directory_data.get("directory", {}).get("missing_byte", MISSING_DIRECTORY_BYTE)
    )
    directory_bytes = bytearray()
    by_id = {
        int(record["id"]): record
        for record in directory.values()
        if record.get("layer") == "georam"
    }
    for group in range(group_count):
        for field in ("block", "page", "offset"):
            for index in range(256):
                record = by_id.get(group * 256 + index)
                directory_bytes.append(
                    missing if record is None else int(record[field])
                )
    metadata = directory_data.get("directory", {})
    if f"{zlib.crc32(directory_bytes):08x}" != metadata.get("crc32"):
        errors.add("routine directory CRC32 does not match generated tables")
    xor8 = 0
    for value in directory_bytes:
        xor8 ^= value
    if f"{xor8:02x}" != metadata.get("xor8"):
        errors.add("routine directory XOR8 does not match generated tables")
    return sorted(errors)


def main() -> None:
    """Main execution of the page placement generation tool."""
    manifest_path = "manifests/routines.json"
    output_dir = "build"

    routines = load_routine_manifest(manifest_path)
    routines, placement = assign_page_placement(routines)
    routines, id_map = generate_routine_ids(routines)

    if not validate_no_cross_boundary(placement, routines):
        raise ValueError("Some routines cross page boundaries!")

    generate_call_directory(routines, placement, output_dir)
    generate_test_exports(routines, output_dir)
    print("geoRAM page placement completed successfully.")


if __name__ == "__main__":
    main()
