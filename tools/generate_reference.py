"""Generates deterministic API.md and MAP.md reference documents.

Consumes validated compiler manifests and map files, checks calling conventions,
and writes build reference reports.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

import test_harness


def load_reference_inputs(
    routines_path: str,
    zp_alloc_path: str,
    routine_dir_path: str,
) -> dict[str, Any]:
    """Load the structured inputs required by the reference renderer.

    Args:
        routines_path: Routine ABI manifest.
        zp_alloc_path: Generated zero-page allocation.
        routine_dir_path: Generated routine placement directory.

    Returns:
        Normalized reference model.
    """
    paths = {
        "routines": Path(routines_path),
        "zero_page": Path(zp_alloc_path),
        "routine_directory": Path(routine_dir_path),
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "missing reference input(s): " + ", ".join(sorted(missing))
        )
    model = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in paths.items()
    }
    errors = validate_reference_model(model)
    if errors:
        raise ValueError("; ".join(errors))
    return model


def validate_reference_model(model: dict[str, Any]) -> list[str]:
    """Validate uniqueness and cross-contract reference inputs.

    Args:
        model: Normalized structured reference model.

    Returns:
        Deterministically ordered validation errors.
    """
    errors: set[str] = set()
    routines = model.get("routines", {}).get("routines", [])
    routine_names = [str(record.get("name", "")) for record in routines]
    if len(set(routine_names)) != len(routine_names):
        errors.add("routine manifest contains duplicate names")
    if any(not name for name in routine_names):
        errors.add("routine manifest contains an empty name")

    allocation_data = model.get("zero_page", {})
    if allocation_data.get("valid") is not True:
        errors.add("zero-page allocation is not valid")
    for name, address in allocation_data.get("allocation", {}).items():
        if (
            not isinstance(address, str)
            or re.fullmatch(r"\$[0-9A-Fa-f]{2}", address) is None
        ):
            errors.add(f"zero-page symbol {name} has invalid address {address}")

    directory = model.get("routine_directory", {}).get("routines", {})
    ids = [record.get("id") for record in directory.values()]
    if len(set(ids)) != len(ids):
        errors.add("routine directory contains duplicate IDs")
    for name in routine_names:
        if name not in directory:
            errors.add(f"routine directory is missing {name}")
    for name, record in directory.items():
        if record.get("layer") == "georam":
            for field in ("block", "page", "offset", "address"):
                if field not in record:
                    errors.add(f"geoRAM routine {name} is missing {field}")
    return sorted(errors)


def write_deterministic(content: str, output_path: str) -> None:
    """Write stable UTF-8/LF text while rejecting volatile host data.

    Args:
        content: Rendered Markdown.
        output_path: Destination path.
    """
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    volatile_patterns = (
        r"\b[A-Za-z]:[\\/]",
        r"/(?:home|Users)/[^/\s]+/",
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
    )
    if any(re.search(pattern, normalized) for pattern in volatile_patterns):
        raise ValueError("generated reference contains volatile host data")
    if not normalized.endswith("\n"):
        normalized += "\n"
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as output:
        output.write(normalized)


def generate_api(routines_path: str, output_api: str) -> None:
    """Generates the API.md file documenting production entry points.

    Args:
        routines_path: Path to routines.json.
        output_api: Target API.md path.
    """
    if not os.path.exists(routines_path):
        return

    with open(routines_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    routines = data.get("routines", [])
    prod_routines = [r for r in routines if r.get("visibility") == "public"]

    md_lines = [
        "# Compiler 2 API Reference",
        "",
        "This document describes the production entry points for Compiler 2.",
        "",
        "| Name | Layer | Purpose | Inputs | Outputs | Clobbers | Return Kind |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in prod_routines:
        md_lines.append(
            f"| `{r['name']}` | {r.get('layer', 'resident')} | {r.get('purpose', '')} | {r.get('inputs', '')} | {r.get('outputs', '')} | {r.get('clobbers', '')} | {r.get('return_kind', 'rts')} |"
        )

    os.makedirs(os.path.dirname(output_api), exist_ok=True)
    with open(output_api, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")


def generate_map(zp_alloc_path: str, routine_dir_path: str, output_map: str) -> None:
    """Generates the MAP.md file documenting zero-page and geoRAM memory maps.

    Args:
        zp_alloc_path: Path to zp_allocation.json.
        routine_dir_path: Path to routine_directory.json.
        output_map: Target MAP.md path.
    """
    md_lines = [
        "# Compiler 2 Memory Map",
        "",
        "## Zero-Page Allocation",
        "",
        "| Variable | Address |",
        "|---|---|",
    ]

    if os.path.exists(zp_alloc_path):
        with open(zp_alloc_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        allocation = data.get("allocation", {})
        for name, addr in sorted(allocation.items()):
            md_lines.append(f"| `{name}` | `{addr}` |")

    md_lines.extend(
        [
            "",
            "## geoRAM Page Placement Map",
            "",
            "| Routine | Address | Block | Page | Offset |",
            "|---|---|---|---|---|",
        ]
    )

    if os.path.exists(routine_dir_path):
        with open(routine_dir_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        routines = data.get("routines", {})
        for name, r in sorted(routines.items()):
            if r.get("layer") == "georam":
                md_lines.append(
                    f"| `{name}` | `{r['address']}` | {r['block']} | {r['page']} | {r['offset']} |"
                )

    os.makedirs(os.path.dirname(output_map), exist_ok=True)
    with open(output_map, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")


def main() -> None:
    """Main execution of reference generator."""
    routines_path = "manifests/routines.json"
    zp_alloc_path = "build/zp_allocation.json"
    routine_dir_path = "build/routine_directory.json"

    output_api = "build/API.md"
    output_map = "build/MAP.md"

    generate_api(routines_path, output_api)
    generate_map(zp_alloc_path, routine_dir_path, output_map)
    test_harness.generate_requirements_matrix(
        "manifests/traceability.json",
        "build/requirements_matrix.json",
        "build/requirements_matrix.md",
    )
    print("Deterministic references API.md and MAP.md generated successfully.")


if __name__ == "__main__":
    main()
