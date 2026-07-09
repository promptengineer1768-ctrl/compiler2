"""Graph-color normal-RAM work areas from explicit lifetime manifests."""

import json
from pathlib import Path
from typing import Any


def allocate(data: dict[str, Any]) -> dict[str, int]:
    """Allocate nodes into one bounded region using lifetime interference."""
    nodes = data["nodes"]
    limit = int(data["region"]["size"])
    result: dict[str, int] = {}
    by_name = {str(node["name"]): node for node in nodes}
    for node in sorted(nodes, key=lambda item: (-int(item["size"]), str(item["name"]))):
        name = str(node["name"])
        size = int(node["size"])
        alignment = int(node.get("alignment", 1))
        lifetimes = set(map(str, node["lifetimes"]))
        for offset in range(0, limit - size + 1):
            if offset % alignment:
                continue
            end = offset + size
            conflict = False
            for other, other_offset in result.items():
                other_node = by_name[other]
                if not lifetimes.intersection(map(str, other_node["lifetimes"])):
                    continue
                other_end = other_offset + int(other_node["size"])
                if offset < other_end and other_offset < end:
                    conflict = True
                    break
            if not conflict:
                result[name] = offset
                break
        else:
            raise ValueError(f"cannot allocate workarea node {name} ({size} bytes)")
    return result


def generate(manifest: Path, output_dir: Path) -> None:
    """Generate assembler offsets and an auditable allocation report."""
    data = json.loads(manifest.read_text(encoding="utf-8"))
    allocation = allocate(data)
    output_dir.mkdir(parents=True, exist_ok=True)
    lines = ["; Auto-generated normal-RAM workarea offsets.", "; Do not edit."]
    for name, offset in sorted(allocation.items()):
        lines.append(f"workarea_{name} = ${offset:04X}")
    lines.append(f"compiler_workarea_size = {int(data['region']['size'])}")
    (output_dir / "workarea_symbols.inc").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    report = {"valid": True, "region": data["region"], "allocation": allocation}
    (output_dir / "workarea_allocation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    """Generate the project workarea allocation."""
    generate(Path("manifests/workareas.json"), Path("build"))


if __name__ == "__main__":
    main()
