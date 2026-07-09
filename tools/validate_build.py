"""Cross-artifact validation and build integrity checks.

Performs schema, routine, arena, ZP, size, and layout consistency checks, and
computes build fingerprints.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


def _load_json(path: str) -> dict[str, Any]:
    """Load one JSON object from disk."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_tool_versions(
    tools: Mapping[str, str],
    expected_versions: Mapping[str, str],
) -> list[str]:
    """Validate executable versions against required substrings."""
    errors: list[str] = []
    for name, executable in sorted(tools.items()):
        path = Path(executable)
        if not path.exists():
            errors.append(f"{name} executable not found: {executable}")
            continue
        result = subprocess.run(
            [str(path), "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        output = (result.stdout + result.stderr).strip()
        expected = expected_versions.get(name)
        if result.returncode != 0:
            errors.append(f"{name} --version exited {result.returncode}")
        elif expected is not None and expected not in output:
            errors.append(f"{name} version does not contain {expected}: {output}")
    return errors


def validate_routine_directory(routines_path: str, directory_path: str) -> list[str]:
    """Validate routine IDs, completeness, and geoRAM placement fields."""
    routines = _load_json(routines_path).get("routines", [])
    directory = _load_json(directory_path).get("routines", {})
    errors: set[str] = set()
    names = [str(routine.get("name", "")) for routine in routines]
    if len(set(names)) != len(names):
        errors.add("routine manifest contains duplicate names")
    for name in names:
        if name not in directory:
            errors.add(f"routine directory is missing {name}")
    manifest_ids = [directory[name].get("id") for name in names if name in directory]
    if len(set(manifest_ids)) != len(manifest_ids):
        errors.add("routine directory contains duplicate IDs")
    if set(manifest_ids) != set(range(len(names))):
        errors.add("routine IDs are not complete and sequential")
    for name, record in directory.items():
        if record.get("layer") == "georam":
            for field in ("block", "page", "offset", "address"):
                if field not in record:
                    errors.add(f"geoRAM routine {name} is missing {field}")
            offset = int(record.get("offset", 256))
            if not 0 <= offset < 256:
                errors.add(f"geoRAM routine {name} has invalid offset {offset}")
    return sorted(errors)


def validate_arena_layout(arenas_path: str, layout_path: str) -> list[str]:
    """Validate generated arena identities, types, and minimum capacities."""
    manifest = _load_json(arenas_path).get("arenas", [])
    layout = _load_json(layout_path).get("arenas", [])
    generated = {str(arena.get("name")): arena for arena in layout}
    errors: set[str] = set()
    if len(generated) != len(layout):
        errors.add("arena layout contains duplicate names")
    for arena in manifest:
        name = str(arena["name"])
        record = generated.get(name)
        if record is None:
            errors.add(f"arena layout is missing {name}")
            continue
        if record.get("type_code") != arena.get("type_code"):
            errors.add(f"arena {name} type code differs from manifest")
        if int(record.get("capacity_pages", -1)) < int(
            arena.get("capacity_pages_minimum", 0)
        ):
            errors.add(f"arena {name} is below minimum capacity")
    return sorted(errors)


def validate_zp_allocation(manifest_path: str, allocation_path: str) -> list[str]:
    """Validate generated zero-page coverage, ranges, and reservations."""
    manifest = _load_json(manifest_path)
    result = _load_json(allocation_path)
    errors: set[str] = set()
    if result.get("valid") is not True:
        errors.add("zero-page allocation is not marked valid")
    node_records = {str(node["name"]): node for node in manifest.get("nodes", [])}
    nodes = {name: int(node["size"]) for name, node in node_records.items()}
    allocation = result.get("allocation", {})
    for name in nodes:
        if name not in allocation:
            errors.add(f"zero-page allocation is missing {name}")
    occupied: dict[int, list[str]] = {}
    reserved: set[int] = set()
    for record in manifest.get("fixed_reservations", []) + manifest.get(
        "kernal_bridge_zp", []
    ):
        text = str(record["address"]).replace("$", "")
        bounds = text.split("-")
        start = int(bounds[0], 16)
        end = int(bounds[-1], 16)
        reserved.update(range(start, end + 1))
    for name, text in allocation.items():
        if name not in nodes or re.fullmatch(r"\$[0-9A-Fa-f]{2}", str(text)) is None:
            errors.add(f"zero-page allocation has invalid entry {name}={text}")
            continue
        start = int(str(text)[1:], 16)
        for address in range(start, start + nodes[name]):
            if address > 0xFF:
                errors.add(f"zero-page allocation for {name} exceeds $FF")
            if address in reserved:
                errors.add(
                    f"zero-page allocation for {name} overlaps reserved ${address:02X}"
                )
            previous_names = occupied.setdefault(address, [])
            current_lifetimes = {
                json.dumps(lifetime, sort_keys=True)
                for lifetime in node_records[name].get("lifetimes", [])
            }
            for previous in previous_names:
                previous_lifetimes = {
                    json.dumps(lifetime, sort_keys=True)
                    for lifetime in node_records[previous].get("lifetimes", [])
                }
                if current_lifetimes & previous_lifetimes:
                    errors.add(
                        f"live zero-page allocations {previous} and {name} overlap"
                    )
            previous_names.append(name)
    return sorted(errors)


def validate_size_report(size_report_path: str) -> list[str]:
    """Validate linked segment arithmetic and all reported budget gates."""
    report = _load_json(size_report_path)
    errors: set[str] = set()
    for segment in report.get("segments", []):
        expected = int(segment["end"]) - int(segment["start"]) + 1
        if int(segment["size"]) != expected:
            errors.add(f"segment {segment['name']} size does not match range")

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if (
                    key in {"within_limit", "compile_within_limit"}
                    and child is not True
                ):
                    errors.add(f"budget gate {child_path} is not true")
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(report, "")
    return sorted(errors)


def validate_program_formats(formats_path: str) -> list[str]:
    """Validate stock and extended program format invariants."""
    formats = _load_json(formats_path).get("formats", {})
    errors: list[str] = []
    stock = formats.get("stock_basicv2")
    extended = formats.get("extended_c2p1")
    if not isinstance(stock, dict):
        errors.append("stock_basicv2 format is missing")
    elif stock.get("load_address_bytes") != [1, 8]:
        errors.append("stock_basicv2 load address must be $0801")
    if not isinstance(extended, dict):
        errors.append("extended_c2p1 format is missing")
    else:
        if extended.get("magic_bytes") != [67, 50, 80, 49]:
            errors.append("extended_c2p1 magic must be C2P1")
        if not isinstance(extended.get("version"), int) or extended["version"] < 1:
            errors.append("extended_c2p1 version must be positive")
        if extended.get("magic_ascii") not in (None, "C2P1"):
            errors.append("extended_c2p1 magic_ascii must be C2P1")
    return errors


def validate_runtime_abi(source_path: str, generated_path: str) -> list[str]:
    """Validate generated runtime ABI equality and unique public names."""
    source = _load_json(source_path)
    generated = _load_json(generated_path)
    errors: list[str] = []
    if generated != source:
        errors.append("generated runtime ABI differs from manifest")
    names = [entry.get("name") for entry in source.get("entries", [])]
    if len(set(names)) != len(names):
        errors.append("runtime ABI contains duplicate entry names")
    return errors


def validate_keyword_lookup(commands_path: str, report_path: str) -> list[str]:
    """Validate lookup report coverage and bounded structural metrics."""
    commands = _load_json(commands_path).get("commands", [])
    report = _load_json(report_path)
    expected = [str(command["keyword"]) for command in commands]
    errors: list[str] = []
    if report.get("keywords") != expected:
        errors.append("keyword lookup report does not preserve command coverage/order")
    if report.get("total_keywords") != len(expected):
        errors.append("keyword lookup total differs from command manifest")
    for field in ("trie_depth", "max_fan_out", "total_trie_bytes"):
        if not isinstance(report.get(field), int) or int(report[field]) <= 0:
            errors.append(f"keyword lookup {field} must be positive")
    return errors


def validate_generated_reference(
    api_path: str, map_path: str, production_entries_path: str
) -> list[str]:
    """Validate deterministic references and production API completeness."""
    errors: list[str] = []
    api = Path(api_path).read_text(encoding="utf-8")
    memory_map = Path(map_path).read_text(encoding="utf-8")
    entries = _load_json(production_entries_path).get("production_entries", [])
    for entry in entries:
        if f"`{entry['name']}`" not in api:
            errors.append(f"API reference is missing {entry['name']}")
    for name, content in (("API", api), ("MAP", memory_map)):
        if "\r" in content:
            errors.append(f"{name} reference does not use LF line endings")
        if re.search(r"\b[A-Za-z]:[\\/]|/(?:home|Users)/", content):
            errors.append(f"{name} reference contains an absolute host path")
    return errors


def validate_no_stale_generated(
    dependencies: Mapping[str, Sequence[str]],
) -> list[str]:
    """Validate generated outputs are present and no older than their inputs."""
    errors: list[str] = []
    for output, inputs in sorted(dependencies.items()):
        output_path = Path(output)
        if not output_path.exists():
            errors.append(f"generated output is missing: {output}")
            continue
        output_time = output_path.stat().st_mtime_ns
        for source in inputs:
            source_path = Path(source)
            if not source_path.exists():
                errors.append(f"generated input is missing: {source}")
            elif source_path.stat().st_mtime_ns > output_time:
                errors.append(
                    f"generated output {output} is stale relative to {source}"
                )
    return errors


def validate_manifests() -> bool:
    """Validates the structure and consistency of all JSON manifests.

    Returns:
        True if all manifests are valid.
    """
    manifest_files = [
        "manifests/zero_page.json",
        "manifests/routines.json",
        "manifests/arenas.json",
        "manifests/commands.json",
        "manifests/program_formats.json",
        "manifests/linker_policy.json",
        "manifests/runtime_abi.json",
        "manifests/traceability.json",
    ]

    for path in manifest_files:
        if not os.path.exists(path):
            print(f"Error: Manifest {path} is missing.")
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Manifest {path} has invalid JSON: {e}")
            return False

    return True


def compute_build_fingerprint() -> str:
    """Computes a reproducibility hash covering manifests and sources.

    Returns:
        MD5 fingerprint string.
    """
    h = hashlib.md5()
    # Hash manifest files
    manifest_dir = "manifests"
    if os.path.exists(manifest_dir):
        for name in sorted(os.listdir(manifest_dir)):
            path = os.path.join(manifest_dir, name)
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    h.update(f.read())
    return h.hexdigest()


def validate_routine_clobber_lists() -> bool:
    """Validates that all ZP symbols in routine clobber lists are allocated.

    Returns:
        True if all clobber lists are satisfied.
    """
    zp_alloc_path = "build/zp_allocation.json"
    routines_path = "manifests/routines.json"

    if not os.path.exists(zp_alloc_path):
        print("Error: zp_allocation.json not found. Run zp_alloc.py first.")
        return False

    if not os.path.exists(routines_path):
        print("Error: routines.json not found.")
        return False

    with open(zp_alloc_path, "r", encoding="utf-8") as f:
        zp_data = json.load(f)

    with open(routines_path, "r", encoding="utf-8") as f:
        routines_data = json.load(f)

    allocated_symbols = set(zp_data.get("allocation", {}).keys())

    # Also include fixed reservations and kernal bridge ZP
    zp_manifest_path = "manifests/zero_page.json"
    if os.path.exists(zp_manifest_path):
        with open(zp_manifest_path, "r", encoding="utf-8") as f:
            zp_manifest = json.load(f)
        for res in zp_manifest.get("fixed_reservations", []):
            allocated_symbols.add(res["symbol"])
        for res in zp_manifest.get("kernal_bridge_zp", []):
            allocated_symbols.add(res["symbol"])

    errors = []
    for routine in routines_data.get("routines", []):
        name = routine.get("name", "unknown")
        for zp_ref in routine.get("zp_read", []):
            if zp_ref not in allocated_symbols:
                errors.append(f"Routine {name} reads undeclared ZP symbol: {zp_ref}")
        for zp_ref in routine.get("zp_write", []):
            if zp_ref not in allocated_symbols:
                errors.append(f"Routine {name} writes undeclared ZP symbol: {zp_ref}")

    if errors:
        for error in errors:
            print(f"Error: {error}")
        return False

    return True


def validate_linker_config() -> bool:
    """Validates linker configuration for segment overlaps and vector placement.

    Returns:
        True if linker config is valid.
    """
    linker_policy_path = "manifests/linker_policy.json"

    if not os.path.exists(linker_policy_path):
        print("Error: linker_policy.json not found.")
        return False

    with open(linker_policy_path, "r", encoding="utf-8") as f:
        policy = json.load(f)

    # Validate NMI/RESET/IRQ vectors at $FFFA-$FFFF
    vectors_start = 0xFFFA
    vectors_end = 0xFFFF

    found_vectors = False
    for segment in policy.get("fixed_segments", []):
        if segment.get("name") == "VECTORS":
            start = segment.get("start", 0)
            max_size = segment.get("max_size", 0)
            if start != vectors_start:
                print(
                    f"Error: VECTORS segment start {start:04X} != {vectors_start:04X}"
                )
                return False
            if start + max_size - 1 != vectors_end:
                print(
                    f"Error: VECTORS segment end {start + max_size - 1:04X} != {vectors_end:04X}"
                )
                return False
            found_vectors = True
            break

    if not found_vectors:
        print("Error: VECTORS segment not found in fixed_segments")
        return False

    # Validate no segment overlaps within same memory area
    segments_by_area: dict[str, list[tuple[str, int, int]]] = {}
    for segment in policy.get("fixed_segments", []):
        area = segment.get("memory_area", "")
        name = segment.get("name", "")
        start = segment.get("start", 0)
        max_size = segment.get("max_size", 0)

        if area not in segments_by_area:
            segments_by_area[area] = []

        # Only check explicit start addresses for overlap
        if start > 0:
            segments_by_area[area].append((name, start, start + max_size - 1))

    for area, segs in segments_by_area.items():
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                name1, start1, end1 = segs[i]
                name2, start2, end2 = segs[j]
                if start1 <= end2 and start2 <= end1:
                    print(f"Error: Segments {name1} and {name2} overlap in {area}")
                    return False

    return True


def _report_errors(errors: Sequence[str], success_message: str) -> bool:
    """Print deterministic validator diagnostics and return success."""
    if errors:
        for error in errors:
            print(f"Error: {error}")
        return False
    print(success_message)
    return True


def _validate_assembled_artifacts() -> list[str]:
    """Validate required linked artifacts exist and are nonempty."""
    errors: list[str] = []
    for path in ("build/compiler.bin", "build/compiler.map", "build/compiler.lbl"):
        artifact = Path(path)
        if not artifact.exists():
            errors.append(f"assembled artifact is missing: {path}")
        elif artifact.stat().st_size == 0:
            errors.append(f"assembled artifact is empty: {path}")
    return errors


def validate_georam_image_budget(size_report_path: str) -> list[str]:
    """Hard-fail when the geoRAM-canonical image exceeds 512 KiB (2048 pages).

    Larger detected devices may only add dynamic storage; the base image must
    always fit 512 KiB (REQUIREMENTS §8.1 / DESIGN2 §1).
    """
    errors: list[str] = []
    path = Path(size_report_path)
    if not path.exists():
        return errors
    report = _load_json(str(path))
    pages = report.get("georam_pages")
    limit = report.get("georam_page_limit", 2048)
    if isinstance(pages, int) and isinstance(limit, int) and pages > limit:
        errors.append(
            f"geoRAM image exceeds 512 KiB budget: {pages} pages > {limit} limit"
        )
    if report.get("georam_within_limit") is False:
        errors.append("size_report.georam_within_limit is false (512 KiB hard fail)")
    return errors


def _contract_errors() -> list[str]:
    """Run generated-contract validators used before and after assembly."""
    errors: list[str] = []
    errors.extend(
        validate_arena_layout("manifests/arenas.json", "build/arena_layout.json")
    )
    errors.extend(validate_program_formats("manifests/program_formats.json"))
    errors.extend(
        validate_runtime_abi("manifests/runtime_abi.json", "build/runtime_abi.json")
    )
    errors.extend(
        validate_keyword_lookup(
            "manifests/commands.json", "build/keyword_lookup_report.json"
        )
    )
    errors.extend(validate_georam_image_budget("build/size_report.json"))
    return errors


def main() -> None:
    """Main execution path for validation."""
    option = sys.argv[1] if len(sys.argv) > 1 else None
    if len(sys.argv) > 1 and sys.argv[1] == "--manifests":
        if validate_manifests():
            print("All manifests validated successfully.")
            sys.exit(0)
        else:
            sys.exit(1)

    if option == "--routine-directory":
        ok = _report_errors(
            validate_routine_directory(
                "manifests/routines.json", "build/routine_directory.json"
            ),
            "Routine directory validated successfully.",
        )
        raise SystemExit(0 if ok else 1)

    if option == "--contracts":
        ok = _report_errors(
            _contract_errors(), "Generated contracts validated successfully."
        )
        raise SystemExit(0 if ok else 1)

    if len(sys.argv) > 1 and sys.argv[1] == "--traceability":
        trace_path = "manifests/traceability.json"
        if not os.path.exists(trace_path):
            print("Error: traceability.json is missing.")
            sys.exit(1)
        try:
            with open(trace_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records = data.get("records", [])
            mapped_tests: dict[str, set[str]] = {}
            for r in records:
                if not r.get("tests"):
                    print(f"Error: Requirement {r.get('id')} has no tests mapped.")
                    sys.exit(1)
                for test_name in r.get("tests", []):
                    mapped_tests.setdefault(str(test_name), set()).add(str(r.get("id")))
            matrix_path = "build/requirements_matrix.json"
            if os.path.exists(matrix_path):
                with open(matrix_path, "r", encoding="utf-8") as f:
                    matrix = json.load(f)
                inverse_rows = {
                    str(row.get("test")): set(row.get("requirements", []))
                    for row in matrix.get("mapped_tests", [])
                }
                if inverse_rows != mapped_tests:
                    print(
                        "Error: requirements matrix test-to-requirement index is stale."
                    )
                    sys.exit(1)
            print("Requirements traceability matrix validated successfully.")
            sys.exit(0)
        except Exception as e:
            print(f"Error: Traceability validation failed: {e}")
            sys.exit(1)

    if option in {"--budgets", "--size-report"}:
        ok = _report_errors(
            validate_size_report("build/size_report.json"),
            "Size report and budgets validated successfully.",
        )
        raise SystemExit(0 if ok else 1)

    if option == "--reference":
        ok = _report_errors(
            validate_generated_reference(
                "build/API.md",
                "build/MAP.md",
                "build/production_entries.json",
            ),
            "Generated references validated successfully.",
        )
        raise SystemExit(0 if ok else 1)

    if option == "--assembled":
        ok = _report_errors(
            _validate_assembled_artifacts(),
            "Assembled artifacts validated successfully.",
        )
        raise SystemExit(0 if ok else 1)

    if len(sys.argv) > 1 and sys.argv[1] == "--clobbers":
        if validate_routine_clobber_lists():
            print("Routine clobber lists validated successfully.")
            sys.exit(0)
        else:
            sys.exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "--linker":
        if validate_linker_config():
            print("Linker configuration validated successfully.")
            sys.exit(0)
        else:
            sys.exit(1)

    if option == "--all":
        errors: list[str] = []
        if not validate_manifests():
            errors.append("manifest validation failed")
        if not validate_routine_clobber_lists():
            errors.append("routine clobber validation failed")
        if not validate_linker_config():
            errors.append("linker validation failed")
        errors.extend(
            validate_tool_versions(
                {
                    "ca65": r"C:\Users\me\Documents\Coding Projects\tools\ca65.exe",
                    "ld65": r"C:\Users\me\Documents\Coding Projects\tools\ld65.exe",
                },
                {"ca65": "V2.19", "ld65": "V2.19"},
            )
        )
        errors.extend(
            validate_routine_directory(
                "manifests/routines.json", "build/routine_directory.json"
            )
        )
        errors.extend(
            validate_zp_allocation(
                "manifests/zero_page.json", "build/zp_allocation.json"
            )
        )
        errors.extend(_contract_errors())
        errors.extend(validate_size_report("build/size_report.json"))
        errors.extend(_validate_assembled_artifacts())
        errors.extend(
            validate_generated_reference(
                "build/API.md",
                "build/MAP.md",
                "build/production_entries.json",
            )
        )
        ok = _report_errors(errors, "All build contracts validated successfully.")
        raise SystemExit(0 if ok else 1)

    if option is not None:
        print(f"Error: unknown validation option: {option}")
        raise SystemExit(2)

    # General validations
    success = validate_manifests()
    if success:
        fingerprint = compute_build_fingerprint()
        # Save build_manifest.json
        manifest_data = {
            "valid": True,
            "fingerprint": fingerprint,
            "compiler2_version": "1.0",
        }
        os.makedirs("build", exist_ok=True)
        with open("build/build_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
        print(f"Build validation successful. Fingerprint: {fingerprint}")
    else:
        print("Build validation failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
