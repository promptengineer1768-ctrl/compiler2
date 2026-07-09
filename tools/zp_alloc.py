"""Zero-page graph-coloring allocator for Compiler 2.

Loads zero-page node manifests, builds interference graph, colors the graph
to assign ZP addresses, and generates equates/reports.
"""

import json
import os
from typing import Any, Dict, FrozenSet, List, Set, Tuple


def load_manifest(
    manifest_path: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Loads the zero-page manifest.

    Args:
        manifest_path: Path to zero_page.json.

    Returns:
        A tuple of (fixed_reservations, kernal_bridge_zp, nodes).
    """
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return (
        data.get("fixed_reservations", []),
        data.get("kernal_bridge_zp", []),
        data.get("nodes", []),
    )


def parse_address_range(address_str: str) -> Set[int]:
    """Parses a C64 address range string (e.g. '$A0-$A2' or '$90') to a set of ints.

    Args:
        address_str: Hex range string.

    Returns:
        Set of integer addresses.
    """
    if "-" in address_str:
        parts = address_str.split("-")
        start = int(parts[0].replace("$", ""), 16)
        end = int(parts[1].replace("$", ""), 16)
        return set(range(start, end + 1))
    else:
        val = int(address_str.replace("$", ""), 16)
        return {val}


def build_interference_graph(nodes: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
    """Builds the interference adjacency list for nodes.

    Args:
        nodes: List of node dictionaries.

    Returns:
        A dictionary mapping node name to a set of interfering node names.
    """
    adj: Dict[str, Set[str]] = {node["name"]: set() for node in nodes}
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            n1 = nodes[i]
            n2 = nodes[j]

            # Convert lifetime records to frozensets so they are hashable
            # Handle both string lifetimes and dict lifetimes
            def _lt_to_frozenset(lt: Any) -> FrozenSet[Any]:
                if isinstance(lt, dict):
                    return frozenset(lt.items())
                return frozenset([lt])

            lt1 = {_lt_to_frozenset(lt) for lt in n1["lifetimes"]}
            lt2 = {_lt_to_frozenset(lt) for lt in n2["lifetimes"]}

            # Interfere if they share any lifetime record
            if lt1 & lt2:
                adj[n1["name"]].add(n2["name"])
                adj[n2["name"]].add(n1["name"])
    return adj


def color_graph(
    nodes: List[Dict[str, Any]],
    interference: Dict[str, Set[str]],
    reserved_addresses: Set[int],
) -> Dict[str, int]:
    """Colors the graph using a greedy/DSATUR coloring algorithm.

    Args:
        nodes: List of node dictionaries.
        interference: Adjacency list of interfering node names.
        reserved_addresses: Set of addresses that cannot be used.

    Returns:
        A dictionary mapping node name to colored ZP address.
    """
    # Sort nodes by size descending, then by number of interferences descending
    # to prioritize hard-to-place nodes.
    sorted_nodes = sorted(
        nodes,
        key=lambda n: (n["size"], len(interference[n["name"]])),
        reverse=True,
    )

    allocation: Dict[str, int] = {}

    for node in sorted_nodes:
        name = node["name"]
        size = node["size"]
        alignment = node.get("alignment", 1)

        # Find the first available ZP address ($02-$FF) that:
        # 1. Fits the size.
        # 2. Satisfies alignment.
        # 3. Does not overlap with reserved addresses.
        # 4. Does not overlap with any allocated interfering nodes.
        allocated_addr = -1
        for addr in range(2, 256 - size + 1):
            if addr % alignment != 0:
                continue

            # Check overlap with reserved addresses
            candidate_bytes = set(range(addr, addr + size))
            if candidate_bytes.intersection(reserved_addresses):
                continue

            # Check overlap with allocated interfering nodes
            conflict = False
            for other_name in interference[name]:
                if other_name in allocation:
                    other_addr = allocation[other_name]
                    other_size = next(
                        n["size"] for n in nodes if n["name"] == other_name
                    )
                    other_bytes = set(range(other_addr, other_addr + other_size))
                    if candidate_bytes.intersection(other_bytes):
                        conflict = True
                        break

            if not conflict:
                allocated_addr = addr
                break

        if allocated_addr == -1:
            raise ValueError(f"Failed to allocate ZP node: {name} (size {size})")

        allocation[name] = allocated_addr

    return allocation


def validate_no_overlap(
    allocation: Dict[str, int],
    nodes: List[Dict[str, Any]],
    interference: Dict[str, Set[str]],
    reserved_addresses: Set[int],
) -> List[str]:
    """Validate allocated ranges against reservations and live neighbors.

    Args:
        allocation: Node names mapped to starting zero-page addresses.
        nodes: Zero-page node records containing byte sizes.
        interference: Live-range adjacency by node name.
        reserved_addresses: Addresses unavailable to dynamic nodes.

    Returns:
        Deterministically ordered human-readable conflict descriptions.
    """
    errors: Set[str] = set()
    sizes = {str(node["name"]): int(node["size"]) for node in nodes}
    unknown = sorted(set(allocation) - set(sizes))
    errors.update(f"allocation references unknown node {name}" for name in unknown)

    ranges: Dict[str, Set[int]] = {}
    for name, start in allocation.items():
        if name not in sizes:
            continue
        occupied = set(range(start, start + sizes[name]))
        ranges[name] = occupied
        if start < 2 or start + sizes[name] > 256:
            errors.add(
                f"{name} range ${start:02X}-${start + sizes[name] - 1:02X} "
                "is outside allocatable ZP"
            )
        reserved = sorted(occupied & reserved_addresses)
        if reserved:
            errors.add(
                f"{name} overlaps reserved address(es) "
                + ", ".join(f"${address:02X}" for address in reserved)
            )

    for name, neighbors in interference.items():
        if name not in ranges:
            if name in sizes:
                errors.add(f"node {name} has no allocation")
            continue
        for neighbor in neighbors:
            if neighbor not in ranges:
                if neighbor in sizes:
                    errors.add(f"node {neighbor} has no allocation")
                continue
            if ranges[name] & ranges[neighbor]:
                first, second = sorted((name, neighbor))
                errors.add(f"live nodes {first} and {second} overlap")

    return sorted(errors)


def validate_contracts(
    allocation: Dict[str, int],
    routines: List[Dict[str, Any]],
    fixed_res: List[Dict[str, Any]],
    kernal_zp: List[Dict[str, Any]],
) -> List[str]:
    """Validate every routine zero-page reference against declared symbols.

    Args:
        allocation: Dynamic zero-page symbol allocation.
        routines: Routine ABI records with ``zp_read`` and ``zp_write`` lists.
        fixed_res: Fixed zero-page reservation records.
        kernal_zp: KERNAL bridge zero-page records.

    Returns:
        Deterministically ordered missing-contract descriptions.
    """
    declared = set(allocation)
    declared.update(str(record["symbol"]) for record in fixed_res)
    declared.update(str(record["symbol"]) for record in kernal_zp)
    errors: Set[str] = set()
    for routine in routines:
        routine_name = str(routine.get("name", "<unnamed>"))
        for field in ("zp_read", "zp_write"):
            values = routine.get(field, [])
            if not isinstance(values, list):
                errors.add(f"{routine_name}.{field} must be a list")
                continue
            for symbol in values:
                if not isinstance(symbol, str) or symbol not in declared:
                    errors.add(f"{routine_name}.{field} references undeclared {symbol}")
    return sorted(errors)


def generate_output(
    allocation: Dict[str, int],
    fixed_res: List[Dict[str, Any]],
    kernal_zp: List[Dict[str, Any]],
    nodes: List[Dict[str, Any]],
    interference: Dict[str, Set[str]],
    output_dir: str,
) -> None:
    """Generateszp_symbols.inc, zp_allocation.json, .md, and .dot.

    Args:
        allocation: Colored node allocations.
        fixed_res: Fixed reservations list.
        kernal_zp: KERNAL bridge ZP list.
        nodes: Nodes list.
        interference: Interference graph.
        output_dir: Target output directory.
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. zp_symbols.inc
    inc_lines = [
        "; Auto-generated zero-page symbols for Compiler 2",
        "; Do not edit manually.",
        "",
    ]
    for res in fixed_res:
        addr = res["address"].split("-")[0]
        inc_lines.append(f"{res['symbol']} = {addr}")
    for res in kernal_zp:
        addr = res["address"].split("-")[0]
        inc_lines.append(f"{res['symbol']} = {addr}")
    inc_lines.append("")
    for name, addr in sorted(allocation.items()):
        inc_lines.append(f"{name} = ${addr:02X}")

    with open(os.path.join(output_dir, "zp_symbols.inc"), "w", encoding="utf-8") as f:
        f.write("\n".join(inc_lines) + "\n")

    # Project-owned dynamic ZP bytes are protected from compiled POKE. Emit
    # exact half-open ranges so future allocator gaps remain accessible.
    sizes = {str(node["name"]): int(node["size"]) for node in nodes}
    occupied: Set[int] = set()
    for name, addr in allocation.items():
        occupied.update(range(addr, addr + sizes[name]))
    ranges: List[Tuple[int, int]] = []
    for address in sorted(occupied):
        if not ranges or address != ranges[-1][1]:
            ranges.append((address, address + 1))
        else:
            ranges[-1] = (ranges[-1][0], address + 1)
    protected_lines = [
        "; Auto-generated project-owned zero-page protection ranges.",
        "; Each pair is start, exclusive end.",
        f"compiler_zp_protected_range_count = {len(ranges)}",
        ".macro emit_compiler_zp_protected_ranges",
    ]
    for start, end in ranges:
        protected_lines.append(f"    .byte ${start:02X}, ${end:02X}")
    protected_lines.extend([".endmacro", ""])
    with open(
        os.path.join(output_dir, "zp_protected_ranges.inc"),
        "w",
        encoding="utf-8",
    ) as f:
        f.write("\n".join(protected_lines))

    # 2. zp_allocation.json
    alloc_json = {
        "valid": True,
        "allocation": {name: f"${addr:02X}" for name, addr in allocation.items()},
    }
    with open(
        os.path.join(output_dir, "zp_allocation.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(alloc_json, f, indent=2)

    # 3. zp_allocation.md
    md_lines = [
        "# Zero-Page Allocation Report",
        "",
        "| Symbol | Address | Size | Source | Notes |",
        "|---|---|---|---|---|",
    ]
    for res in fixed_res:
        md_lines.append(
            f"| `{res['symbol']}` | `{res['address']}` | {res['size']} | Fixed | {res['notes']} |"
        )
    for res in kernal_zp:
        md_lines.append(
            f"| `{res['symbol']}` | `{res['address']}` | {res['size']} | KERNAL | {res['kernal_use']} |"
        )
    for name, addr in sorted(allocation.items()):
        node = next(n for n in nodes if n["name"] == name)
        md_lines.append(
            f"| `{name}` | `${addr:02X}` | {node['size']} | Dynamic | {node['notes']} |"
        )

    with open(os.path.join(output_dir, "zp_allocation.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    # 4. zp_interference.dot
    dot_lines = ["graph G {", '  node [shape=box, fontname="Courier"];']
    edges_seen: Set[Tuple[str, str]] = set()
    for src_name, neighbors in interference.items():
        for neighbor in neighbors:
            edge = tuple(sorted([src_name, neighbor]))
            # Type assertion check to satisfy type checker
            assert isinstance(edge, tuple) and len(edge) == 2
            if edge not in edges_seen:
                edges_seen.add((edge[0], edge[1]))
                dot_lines.append(f'  "{edge[0]}" -- "{edge[1]}";')
    dot_lines.append("}")

    with open(
        os.path.join(output_dir, "zp_interference.dot"), "w", encoding="utf-8"
    ) as f:
        f.write("\n".join(dot_lines) + "\n")


def main() -> None:
    """Main function to load manifests, run coloring, and generate outputs."""
    manifest_path = "manifests/zero_page.json"
    output_dir = "build"

    fixed_res, kernal_zp, nodes = load_manifest(manifest_path)

    # Compile reserved addresses
    reserved_addresses: Set[int] = set()
    for res in fixed_res:
        reserved_addresses.update(parse_address_range(res["address"]))
    for res in kernal_zp:
        reserved_addresses.update(parse_address_range(res["address"]))

    interference = build_interference_graph(nodes)
    allocation = color_graph(nodes, interference, reserved_addresses)
    overlap_errors = validate_no_overlap(
        allocation, nodes, interference, reserved_addresses
    )
    if overlap_errors:
        raise ValueError("; ".join(overlap_errors))

    with open("manifests/routines.json", "r", encoding="utf-8") as routine_file:
        routines = json.load(routine_file).get("routines", [])
    contract_errors = validate_contracts(allocation, routines, fixed_res, kernal_zp)
    if contract_errors:
        raise ValueError("; ".join(contract_errors))

    generate_output(allocation, fixed_res, kernal_zp, nodes, interference, output_dir)
    print("Zero-page allocation completed successfully.")


if __name__ == "__main__":
    main()
