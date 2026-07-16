"""Generates the ld65 configuration file from policy plus generated segments.

Loads policy manifests and dynamic page counts, verifies memory vector invariants,
and writes build/compiler.cfg.
"""

import json
import os
from typing import Any, Dict, List


def load_linker_policy(policy_path: str) -> Dict[str, Any]:
    """Loads the linker policy from JSON.

    Args:
        policy_path: Path to linker_policy.json.

    Returns:
        Policy dictionary.
    """
    with open(policy_path, "r", encoding="utf-8") as f:
        result: Dict[str, Any] = json.load(f)
        return result


def validate_no_overlap(policy: Dict[str, Any]) -> List[str]:
    """Validate memory areas and explicitly placed fixed segments.

    Args:
        policy: Linker policy dictionary.

    Returns:
        Deterministically ordered overlap and bounds errors.
    """
    errors: List[str] = []
    areas = policy.get("memory_areas", [])
    ranges = sorted(
        (
            int(area["start"]),
            int(area["start"]) + int(area["size"]) - 1,
            str(area["name"]),
        )
        for area in areas
    )
    for index, (start, end, name) in enumerate(ranges):
        if start < 0 or end > 0xFFFF or end < start:
            errors.append(
                f"memory area {name} has invalid range ${start:04X}-${end:04X}"
            )
        if index:
            previous_start, previous_end, previous_name = ranges[index - 1]
            if start <= previous_end:
                errors.append(
                    f"memory areas {previous_name} and {name} overlap at "
                    f"${start:04X}-${min(end, previous_end):04X}"
                )
            assert previous_start <= start

    by_name = {str(area["name"]): area for area in areas}
    placed: Dict[str, List[tuple[int, int, str]]] = {}
    for segment in policy.get("fixed_segments", []):
        area_name = str(segment["memory_area"])
        area = by_name.get(area_name)
        if area is None:
            errors.append(
                f"segment {segment['name']} references unknown area {area_name}"
            )
            continue
        if "start" not in segment:
            continue
        start = int(segment["start"])
        end = start + int(segment["max_size"]) - 1
        area_start = int(area["start"])
        area_end = area_start + int(area["size"]) - 1
        if start < area_start or end > area_end:
            errors.append(
                f"segment {segment['name']} range ${start:04X}-${end:04X} "
                f"falls outside {area_name}"
            )
        placed.setdefault(area_name, []).append((start, end, str(segment["name"])))
    for entries in placed.values():
        entries.sort()
        for previous, current in zip(entries, entries[1:]):
            if current[0] <= previous[1]:
                errors.append(
                    f"segments {previous[2]} and {current[2]} overlap at "
                    f"${current[0]:04X}-${min(previous[1], current[1]):04X}"
                )
    return sorted(errors)


def validate_vectors(policy: Dict[str, Any]) -> List[str]:
    """Validate the six-byte hardware vector reservation.

    Args:
        policy: Linker policy dictionary.

    Returns:
        Vector placement errors, empty when valid.
    """
    errors: List[str] = []
    vector_areas = [
        area for area in policy.get("memory_areas", []) if area.get("name") == "VECTORS"
    ]
    if len(vector_areas) != 1:
        return ["linker policy must define exactly one VECTORS memory area"]
    area = vector_areas[0]
    if int(area["start"]) != 0xFFFA or int(area["size"]) != 6:
        errors.append("VECTORS memory area must cover $FFFA-$FFFF")
    vector_segments = [
        segment
        for segment in policy.get("fixed_segments", [])
        if segment.get("name") == "VECTORS"
    ]
    if len(vector_segments) != 1:
        errors.append("linker policy must define exactly one VECTORS segment")
    else:
        segment = vector_segments[0]
        if (
            segment.get("memory_area") != "VECTORS"
            or int(segment.get("start", -1)) != 0xFFFA
            or int(segment.get("max_size", -1)) != 6
        ):
            errors.append("VECTORS segment must map exactly to $FFFA-$FFFF")
    return errors


def merge_generated_segments(policy: Dict[str, Any], num_georam_pages: int) -> str:
    """Generates ld65 configuration file content.

    Args:
        policy: Linker policy dictionary.
        num_georam_pages: Number of geoRAM pages to define.

    Returns:
        String content of the linker config.
    """
    lines = [
        "# Auto-generated ld65 configuration for Compiler 2",
        "# Do not edit manually.",
        "",
        "MEMORY {",
    ]

    # Add memory areas from policy
    for area in policy.get("memory_areas", []):
        # Format start and size as hex
        start_hex = f"${area['start']:04X}"
        size_hex = f"${area['size']:04X}"
        if area["name"] == "RAM":
            file_part = ", file = %O"
        elif area["name"] == "RAM_HIGH":
            file_part = ', file = "build/hibasic.bin"'
        else:
            file_part = ""
        lines.append(
            f"    {area['name']}: start = {start_hex}, size = {size_hex}, type = {area['type']}{file_part};"
        )

    # Add geoRAM pages memories
    for i in range(num_georam_pages):
        lines.append(
            f'    GEORAM{i}: start = $DE00, size = $0100, type = rw, file = "build/georam.bin", fill = yes, fillval = $EA;'
        )

    lines.append("}")
    lines.append("")
    lines.append("SEGMENTS {")

    # Add segments from policy and the production module segments used by src/.
    lines.append("    ZEROPAGE: load = ZP, type = zp;")
    for seg in policy.get("fixed_segments", []):
        if seg["name"] == "LOADER":
            lines.append("    LOADER: load = RAM, type = ro, start = $0801;")
        elif seg["name"] == "RESIDENT":
            lines.append("    RESIDENT: load = RAM, type = ro;")
        elif seg["name"] == "COMPILER_BSS":
            lines.append(
                "    COMPILER_BSS: load = RAM, type = rw, define = yes, optional = yes;"
            )
        elif seg["name"] == "VECTORS":
            lines.append("    VECTORS: load = VECTORS, type = ro, optional = yes;")

    # Editor/wedge/compressor may live in HIBASIC high-RAM ($E000+) to free
    # $0801-$CFFF headroom. GRAPHICS must stay in low RAM: it remains
    # executable while $E000-$FF3F is the bitmap (docs/GRAPHICS_MEMORY.md).
    lines.extend(
        [
            "    BSS: load = RAM, type = rw, define = yes;",
            "    GRAPHICS_STATE: load = RAM, type = rw;",
            "    COMPILER_INIT: load = RAM, type = ro;",
            "    COMPILER: load = RAM, type = ro;",
            "    GRAPHICS: load = RAM, type = ro;",
            "    RUNTIME: load = RAM, type = ro;",
            "    GEOASM: load = RAM, type = ro;",
            "    CODE: load = RAM, type = ro;",
            "    RODATA: load = RAM, type = ro;",
            "    EDITOR_PINNED: load = RAM_HIGH, type = rw, define = yes;",
            "    HIBASIC: load = RAM_HIGH, type = ro, define = yes;",
            "    EDITOR: load = RAM_HIGH, type = ro;",
            "    WEDGE: load = RAM_HIGH, type = ro;",
            "    COMPRESSOR: load = RAM_HIGH, type = ro, define = yes;",
        ]
    )

    # Add geoRAM segment mapping
    for i in range(num_georam_pages):
        lines.append(
            f"    GEORAM_PAGE_{i}: load = GEORAM{i}, type = ro, optional = yes;"
        )

    lines.append("}")
    return "\n".join(lines) + "\n"


def generate_cfg(policy: Dict[str, Any], num_georam_pages: int) -> str:
    """Compatibility wrapper for the generated-segment merger."""
    return merge_generated_segments(policy, num_georam_pages)


def write_config(content: str, output_path: str) -> None:
    """Write a deterministic UTF-8/LF linker configuration.

    Args:
        content: Rendered ld65 configuration.
        output_path: Destination path.
    """
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as output:
        output.write(content.replace("\r\n", "\n").replace("\r", "\n"))


def render_protected_ranges(policy: Dict[str, Any]) -> str:
    """Render assembly constants for linker-policy-owned protected storage.

    Args:
        policy: Validated linker policy dictionary.

    Returns:
        Deterministic ca65 include text using exclusive end addresses.
    """
    areas = {str(area["name"]): area for area in policy["memory_areas"]}
    ram = areas["RAM"]
    ram_start = int(ram["start"])
    ram_end = ram_start + int(ram["size"])
    return (
        "; Auto-generated from manifests/linker_policy.json.\n"
        "; Do not edit manually. End addresses are exclusive.\n"
        f"compiler_protected_start = ${ram_start:04X}\n"
        f"compiler_protected_end = ${ram_end:04X}\n"
        "compiler_high_guard_start = $FFF9\n"
    )


def main() -> None:
    """Main execution block."""
    policy_path = "manifests/linker_policy.json"
    routine_dir_path = "build/routine_directory.json"
    output_cfg = "build/compiler.cfg"

    policy = load_linker_policy(policy_path)
    errors = validate_no_overlap(policy) + validate_vectors(policy)
    if errors:
        raise ValueError("; ".join(errors))

    # Determine required geoRAM pages from routine directory
    num_pages = 32  # Default page pool
    if os.path.exists(routine_dir_path):
        with open(routine_dir_path, "r", encoding="utf-8") as f:
            rdata = json.load(f)
        max_page = -1
        for name, r in rdata.get("routines", {}).items():
            if r.get("layer") == "georam" and "page" in r:
                max_page = max(max_page, r["page"])
        if max_page != -1:
            # Need at least max_page + 1 pages
            num_pages = max(num_pages, max_page + 1)

    cfg_content = merge_generated_segments(policy, num_pages)
    write_config(cfg_content, output_cfg)
    write_config(render_protected_ranges(policy), "build/protected_ranges.inc")

    print(f"Linker configuration generated successfully with {num_pages} geoRAM pages.")


if __name__ == "__main__":
    main()
