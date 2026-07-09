"""Generates all non-ZP structured contracts before assembly.

Produces ABI, arena, command lookup trie, entry list, and program format contracts.
"""

import json
import os


def _asm_symbol(value: str) -> str:
    """Return a ca65-safe symbol suffix for a manifest keyword."""
    safe = []
    for char in value.upper():
        if char.isalnum():
            safe.append(char)
        elif char == "#":
            safe.append("HASH")
        elif char == "$":
            safe.append("DOLLAR")
        else:
            safe.append("_")
    return "_".join("".join(safe).split("_"))


def _abbreviation_minima(commands: list[dict[str, object]]) -> dict[str, int]:
    """Compute shortest unambiguous high-bit abbreviation length per keyword."""
    keywords = [str(command["keyword"]).upper() for command in commands]
    abbreviation_keywords = [
        keyword for keyword in keywords if not keyword.endswith("#")
    ]
    minima: dict[str, int] = {}
    for keyword in keywords:
        if keyword.endswith("#"):
            minima[keyword] = len(keyword)
            continue
        minimum = len(keyword)
        for length in range(2, len(keyword) + 1):
            prefix = keyword[:length]
            matches = [
                other for other in abbreviation_keywords if other.startswith(prefix)
            ]
            if matches == [keyword]:
                minimum = length
                break
        minima[keyword] = minimum
    return minima


def _token_byte(command: dict[str, object]) -> int:
    """Return the primary token byte for a command entry."""
    if "token_val" in command:
        return int(command["token_val"])  # type: ignore[arg-type]
    token_bytes = command.get("token_bytes")
    if isinstance(token_bytes, list) and token_bytes:
        return int(token_bytes[0])
    raise KeyError(f"command {command.get('keyword')!r} lacks token_val/token_bytes")


def _dialect_mask(command: dict[str, object]) -> str:
    """Return the assembler dialect mask expression for a command."""
    dialect = str(command.get("dialect", "BASIC2"))
    if dialect in ("gateway", "always", "BASIC3"):
        return "DIALECT_BASIC2 | DIALECT_BASIC35"
    if dialect == "BASIC35":
        return "DIALECT_BASIC35"
    return "DIALECT_BASIC2"


def generate_command_tables(commands_path: str, output_dir: str) -> None:
    """Generates keyword lookup tables, first-character index, and reports.

    Args:
        commands_path: Path to commands.json.
        output_dir: Target output directory.
    """
    with open(commands_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    commands = data.get("commands", [])
    # Letter-led keywords feed the first-character trie; operators/punctuation
    # still emit token symbols but are matched by dedicated scanner paths.
    letter_commands = [
        c
        for c in commands
        if str(c["keyword"])[:1].upper().isalpha()
    ]
    minima = _abbreviation_minima(letter_commands)
    sorted_commands = sorted(
        letter_commands,
        key=lambda c: (str(c["keyword"])[0].upper(), str(c["keyword"])),
    )
    max_depth = max((len(str(c["keyword"])) for c in letter_commands), default=0)
    first_counts = {chr(code): 0 for code in range(ord("A"), ord("Z") + 1)}
    for command in sorted_commands:
        first_counts[str(command["keyword"])[0].upper()] += 1
    max_fan_out = max(first_counts.values(), default=0)
    total_bytes = 26 * 2 + sum(5 + len(str(c["keyword"])) for c in sorted_commands)

    # Write keyword_lookup_report.json
    report_data = {
        "total_keywords": len(letter_commands),
        "total_manifest_entries": len(commands),
        "trie_depth": max_depth,
        "max_fan_out": max_fan_out,
        "total_trie_bytes": total_bytes,
        "worst_observed_transitions": max_depth,
        "keywords": [c["keyword"] for c in letter_commands],
        "abbreviations": {
            str(command["keyword"]): minima[str(command["keyword"]).upper()]
            for command in letter_commands
        },
        "first_character_counts": first_counts,
    }

    with open(
        os.path.join(output_dir, "keyword_lookup_report.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(report_data, f, indent=2)

    # Generate keyword_lookup.inc for assembly. The tokenizer consumes this table
    # directly, so keyword coverage and dialect gates are manifest-derived.
    inc_lines = [
        "; Auto-generated keyword lookup table and tokens",
        "; Do not edit manually.",
        "",
        f"KEYWORD_COUNT = {len(sorted_commands)}",
        "DIALECT_BASIC2 = $01",
        "DIALECT_BASIC35 = $02",
        ".export keyword_first_start, keyword_first_end",
        ".export keyword_count_value",
        ".export keyword_name_lo, keyword_name_hi, keyword_length",
        ".export keyword_abbrev_min, keyword_token, keyword_dialect, keyword_modes",
        "",
    ]
    for c in commands:
        inc_lines.append(
            f"BASIC_TOKEN_{_asm_symbol(str(c['keyword']))} = {_token_byte(c)}"
        )
    inc_lines.extend(
        [
            "",
            '.segment "GEOASM"',
            "",
            "keyword_count_value:",
            "    .byte KEYWORD_COUNT",
            "keyword_first_start:",
        ]
    )
    index = 0
    for code in range(ord("A"), ord("Z") + 1):
        inc_lines.append(f"    .byte {index}")
        index += first_counts[chr(code)]
    inc_lines.append("keyword_first_end:")
    index = 0
    for code in range(ord("A"), ord("Z") + 1):
        index += first_counts[chr(code)]
        inc_lines.append(f"    .byte {index}")
    inc_lines.extend(["", "keyword_name_lo:"])
    for idx, command in enumerate(sorted_commands):
        inc_lines.append(f"    .byte <keyword_name_{idx}")
    inc_lines.append("keyword_name_hi:")
    for idx, command in enumerate(sorted_commands):
        inc_lines.append(f"    .byte >keyword_name_{idx}")
    inc_lines.append("keyword_length:")
    for command in sorted_commands:
        inc_lines.append(f"    .byte {len(str(command['keyword']))}")
    inc_lines.append("keyword_abbrev_min:")
    for command in sorted_commands:
        inc_lines.append(f"    .byte {minima[str(command['keyword']).upper()]}")
    inc_lines.append("keyword_token:")
    for command in sorted_commands:
        inc_lines.append(f"    .byte {_token_byte(command)}")
    inc_lines.append("keyword_dialect:")
    for command in sorted_commands:
        inc_lines.append(f"    .byte {_dialect_mask(command)}")
    inc_lines.append("keyword_modes:")
    for command in sorted_commands:
        modes = command.get("modes", [])
        mode_mask = (1 if "program" in modes else 0) | (
            2 if "direct" in modes else 0
        )
        inc_lines.append(f"    .byte {mode_mask}")
    inc_lines.append("")
    for idx, command in enumerate(sorted_commands):
        chars = ", ".join(f"'{char}'" for char in str(command["keyword"]).upper())
        inc_lines.append(f"keyword_name_{idx}:")
        inc_lines.append(f"    .byte {chars}")

    with open(
        os.path.join(output_dir, "keyword_lookup.inc"), "w", encoding="utf-8"
    ) as f:
        f.write("\n".join(inc_lines) + "\n")


def generate_runtime_abi(abi_path: str, output_dir: str) -> None:
    """Generates the runtime ABI files.

    Args:
        abi_path: Path to runtime_abi.json.
        output_dir: Target output directory.
    """
    with open(abi_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Write build/runtime_abi.json
    with open(os.path.join(output_dir, "runtime_abi.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Generate runtime_abi.inc for assembly
    inc_lines = [
        "; Auto-generated runtime ABI entry constants",
        "; Do not edit manually.",
        "",
        "ABI_VERSION = 1",
        "",
    ]
    for idx, entry in enumerate(data.get("entries", [])):
        inc_lines.append(f"ABI_INDEX_{entry['name'].upper()} = {idx}")

    with open(os.path.join(output_dir, "runtime_abi.inc"), "w", encoding="utf-8") as f:
        f.write("\n".join(inc_lines) + "\n")


def generate_arena_layout(arenas_path: str, output_dir: str) -> None:
    """Generates the arena layout constants.

    Args:
        arenas_path: Path to arenas.json.
        output_dir: Target output directory.
    """
    with open(arenas_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Write build/arena_layout.json
    layout_data = {
        "manifest_version": "1.0",
        "arenas": [
            {
                "name": a["name"],
                "type_code": a["type_code"],
                "capacity_pages": a["capacity_pages_minimum"],
            }
            for a in data.get("arenas", [])
        ],
    }

    with open(
        os.path.join(output_dir, "arena_layout.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(layout_data, f, indent=2)

    # Generate arena_layout.inc for assembly
    inc_lines = [
        "; Auto-generated arena layout equates",
        "; Do not edit manually.",
        "",
        f"ARENA_COUNT = {len(data.get('arenas', []))}",
        "",
    ]
    for a in data.get("arenas", []):
        name_upper = a["name"].upper()
        inc_lines.append(f"ARENA_TYPE_{name_upper} = {a['type_code']}")
        inc_lines.append(
            f"ARENA_MIN_PAGES_{name_upper} = {a['capacity_pages_minimum']}"
        )

    with open(os.path.join(output_dir, "arena_layout.inc"), "w", encoding="utf-8") as f:
        f.write("\n".join(inc_lines) + "\n")


def generate_entry_manifests(routines_path: str, output_dir: str) -> None:
    """Generates the production and test entry manifests.

    Args:
        routines_path: Path to routines.json.
        output_dir: Target output directory.
    """
    with open(routines_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    routines = data.get("routines", [])

    prod_entries = [r for r in routines if r.get("visibility") == "public"]
    test_entries = [r for r in routines if r.get("visibility") == "test_only"]

    # Write build/production_entries.json
    with open(
        os.path.join(output_dir, "production_entries.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump({"production_entries": prod_entries}, f, indent=2)

    # Write build/test_entries.json
    with open(
        os.path.join(output_dir, "test_entries.json"), "w", encoding="utf-8"
    ) as f:
        json.dump({"test_entries": test_entries}, f, indent=2)


def generate_format_tables(formats_path: str, output_dir: str) -> None:
    """Generates format tables include file.

    Args:
        formats_path: Path to program_formats.json.
        output_dir: Target output directory.
    """
    with open(formats_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    formats = data.get("formats", {})

    inc_lines = [
        "; Auto-generated program format constants",
        "; Do not edit manually.",
        "",
    ]

    stock = formats.get("stock_basicv2", {})
    inc_lines.append(
        f"STOCK_BASICV2_LOAD_ADDR = {stock.get('default_load_address', 2049)}"
    )
    inc_lines.append(f"STOCK_BASICV2_MAX_LINE = {stock.get('max_line_length', 80)}")

    extended = formats.get("extended_c2p1", {})
    magic = extended.get("magic_bytes", [67, 50, 80, 49])
    # C2P1 = Compiler 2 Program v1 (distinct from CGS1 geoRAM install streams).
    inc_lines.append(f"C2P1_MAGIC_0 = {magic[0]}")
    inc_lines.append(f"C2P1_MAGIC_1 = {magic[1]}")
    inc_lines.append(f"C2P1_MAGIC_2 = {magic[2]}")
    inc_lines.append(f"C2P1_MAGIC_3 = {magic[3]}")
    # Legacy aliases removed; CGS1 remains geoRAM-stream only.

    with open(
        os.path.join(output_dir, "program_formats.inc"), "w", encoding="utf-8"
    ) as f:
        f.write("\n".join(inc_lines) + "\n")


def main() -> None:
    """Main execution entry point."""
    output_dir = "build"

    generate_command_tables("manifests/commands.json", output_dir)
    generate_runtime_abi("manifests/runtime_abi.json", output_dir)
    generate_arena_layout("manifests/arenas.json", output_dir)
    generate_entry_manifests("manifests/routines.json", output_dir)
    generate_format_tables("manifests/program_formats.json", output_dir)
    print("Contracts generation completed successfully.")


if __name__ == "__main__":
    main()
