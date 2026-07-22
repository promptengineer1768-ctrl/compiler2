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

DEFAULT_TOOLS_ROOT = Path(r"C:\Users\me\Documents\Coding Projects\tools")
FINAL_ARTIFACT_NAMES = (
    "compiler.bin",
    "georam.bin",
    "reu.bin",
    "basicv3.prg",
    "compiler.map",
    "compiler.lbl",
    "compiler.d64",
    "loader_manifest.json",
    "reu_loader_manifest.json",
    "routine_directory.json",
    "overlay_directory.json",
    "reu_layout.json",
    "arena_layout.json",
    "runtime_abi.json",
    "production_entries.json",
    "test_entries.json",
    "zp_allocation.json",
    "size_report.json",
    "keyword_lookup_report.json",
    "requirements_matrix.json",
    "requirements_matrix.md",
    "API.md",
    "MAP.md",
)


def _load_json(path: str) -> dict[str, Any]:
    """Load one JSON object from disk."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_input_paths(project_root: Path) -> list[Path]:
    """Return the complete, deterministic set of production build inputs."""
    paths: set[Path] = set()
    for root, pattern in (
        (project_root / "manifests", "*.json"),
        (project_root / "src", "*.asm"),
        (project_root / "tools", "*.py"),
        (project_root / "docs", "*.md"),
    ):
        if root.is_dir():
            paths.update(path for path in root.rglob(pattern) if path.is_file())
    paths.update(
        path
        for path in (
            project_root / "build.ps1",
            project_root / "REQUIREMENTS.md",
            project_root / "DESIGN.md",
            project_root / "REU_REQUIREMENTS.md",
            project_root / "REU_DESIGN.md",
        )
        if path.is_file()
    )
    return sorted(paths, key=lambda path: path.relative_to(project_root).as_posix())


def build_input_records(project_root: Path | None = None) -> dict[str, str]:
    """Return checksums for every source input that can affect a release."""
    root = (project_root or Path.cwd()).resolve()
    return {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in _build_input_paths(root)
    }


def _read_tool_version(executable: Path) -> str:
    """Return one checked executable version string."""
    result = subprocess.run(
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        raise RuntimeError(f"{executable.name} --version exited {result.returncode}")
    if not output:
        raise RuntimeError(f"{executable.name} --version returned no version string")
    return output


def configured_tool_versions() -> dict[str, str]:
    """Return actual versions for the configured production toolchain."""
    ca65 = Path(os.environ.get("COMPILER2_CA65", DEFAULT_TOOLS_ROOT / "ca65.exe"))
    ld65 = Path(os.environ.get("COMPILER2_LD65", DEFAULT_TOOLS_ROOT / "ld65.exe"))
    return {
        "ca65": _read_tool_version(ca65),
        "ld65": _read_tool_version(ld65),
        "python": sys.version.split()[0],
    }


def _artifact_records(build_dir: Path) -> dict[str, dict[str, int | str]]:
    """Return deterministic size and checksum records for final artifacts."""
    records: dict[str, dict[str, int | str]] = {}
    for name in FINAL_ARTIFACT_NAMES:
        path = build_dir / name
        if path.is_file():
            records[name] = {
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
    missing_references = [name for name in ("API.md", "MAP.md") if name not in records]
    if missing_references:
        raise FileNotFoundError(
            "missing required generated reference(s): " + ", ".join(missing_references)
        )
    return records


def validate_required_release_artifacts(build_dir: Path) -> list[str]:
    """Return errors for any deterministic final release artifact that is absent."""
    return [
        f"required release artifact is missing: {name}"
        for name in FINAL_ARTIFACT_NAMES
        if not (build_dir / name).is_file()
    ]


def build_manifest_data(
    build_dir: Path,
    *,
    tool_versions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build the final reproducibility manifest from current artifacts."""
    versions = dict(tool_versions or configured_tool_versions())
    artifacts = _artifact_records(build_dir)
    source_inputs = build_input_records()
    artifact_checksums = {
        name: str(record["sha256"]) for name, record in artifacts.items()
    }
    fingerprint = compute_build_fingerprint(versions, artifact_checksums)
    return {
        "schema_version": 1,
        "valid": True,
        "fingerprint": fingerprint,
        "compiler2_version": "1.0",
        "source_inputs": source_inputs,
        "toolchain": {
            name: {"version": version} for name, version in sorted(versions.items())
        },
        "artifacts": artifacts,
    }


def write_build_manifest(build_dir: Path) -> dict[str, Any]:
    """Write and return the final reproducibility manifest."""
    data = build_manifest_data(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "build_manifest.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return data


def validate_build_manifest(path: str) -> list[str]:
    """Validate tool versions, fingerprint, and recorded artifact checksums."""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        return [f"build manifest is missing: {path}"]
    try:
        manifest = _load_json(path)
        actual_versions = configured_tool_versions()
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]

    errors: list[str] = []
    toolchain = manifest.get("toolchain")
    if not isinstance(toolchain, dict):
        errors.append("build manifest omits toolchain versions")
        toolchain = {}
    for name, actual in sorted(actual_versions.items()):
        record = toolchain.get(name)
        if not isinstance(record, dict) or record.get("version") != actual:
            errors.append(f"build manifest {name} version does not match current tool")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("build manifest omits artifact checksums")
        artifacts = {}
    build_dir = manifest_path.parent
    actual_checksums: dict[str, str] = {}
    for name, record in sorted(artifacts.items()):
        artifact_path = build_dir / name
        if not artifact_path.is_file():
            errors.append(f"recorded artifact is missing: {name}")
            continue
        if not isinstance(record, dict):
            errors.append(f"artifact record is invalid: {name}")
            continue
        size = artifact_path.stat().st_size
        checksum = _sha256_file(artifact_path)
        actual_checksums[name] = checksum
        if record.get("size") != size:
            errors.append(f"artifact size differs from manifest: {name}")
        if record.get("sha256") != checksum:
            errors.append(f"artifact checksum differs from manifest: {name}")
    for name in ("API.md", "MAP.md"):
        if name not in artifacts:
            errors.append(f"build manifest omits required reference: {name}")

    recorded_inputs = manifest.get("source_inputs")
    if not isinstance(recorded_inputs, dict):
        errors.append("build manifest omits source-input checksums")
    elif recorded_inputs != build_input_records():
        errors.append("build artifacts are stale relative to current source inputs")

    expected_fingerprint = compute_build_fingerprint(actual_versions, actual_checksums)
    if manifest.get("fingerprint") != expected_fingerprint:
        errors.append("build fingerprint differs from current inputs and artifacts")
    return errors


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
                # Pending measurements may legitimately report null.  Only an
                # explicit false is a hard budget failure.
                if key in {"within_limit", "compile_within_limit"} and child is False:
                    errors.add(f"budget gate {child_path} is not true")
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(report, "")
    # Top-level compile and resident budget booleans remain mandatory gates.
    for key in ("resident_within_limit", "compile_within_limit", "georam_within_limit"):
        if key in report and report[key] is not True:
            errors.add(f"budget gate {key} is not true")
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

    backend_errors = validate_backend_adoption(Path.cwd())
    if backend_errors:
        for error in backend_errors:
            print(f"Error: {error}")
        return False

    return True


def validate_backend_adoption(project_root: Path) -> list[str]:
    """Validate the pinned sibling Backend contracts and consumer lock.

    Args:
        project_root: Compiler 2 repository root.

    Returns:
        Human-readable validation errors; empty when every contract is current.
    """
    backend_root = project_root.parent / "backend"
    package_root = backend_root / "src"
    if not package_root.is_dir():
        return [f"pinned Backend package is missing: {package_root}"]
    package_text = str(package_root)
    if package_text not in sys.path:
        sys.path.insert(0, package_text)

    try:
        from backend_framework.errors import BackendError  # type: ignore[import-untyped]
        from backend_framework.locks import verify_lock  # type: ignore[import-untyped]
        from backend_framework.validation.manifests import (  # type: ignore[import-untyped]
            validate_manifest,
        )
    except ImportError as error:
        return [f"pinned Backend package cannot be imported: {error}"]

    manifest_root = project_root / "manifests" / "backend"
    lock_path = manifest_root / "backend.lock.json"
    adopted_paths = (
        lock_path,
        manifest_root / "target-profile.json",
        manifest_root / "low-memory-c64.json",
        manifest_root / "low-memory-plus4.json",
        manifest_root / "basic-return-c64.json",
        manifest_root / "basic-return-plus4.json",
    )
    errors: list[str] = []
    for path in adopted_paths:
        try:
            validate_manifest(path)
        except (BackendError, OSError, ValueError) as error:
            errors.append(f"Backend manifest {path.name} is invalid: {error}")
    if errors:
        return errors

    lock = _load_json(str(lock_path))
    try:
        verify_lock(lock, project_root)
    except (BackendError, OSError, ValueError) as error:
        errors.append(f"Backend consumer lock verification failed: {error}")

    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=backend_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        errors.append(f"pinned Backend revision cannot be read: {error}")
    else:
        expected = lock.get("framework_revision")
        if revision != expected:
            errors.append(
                f"pinned Backend revision differs: expected {expected}, got {revision}"
            )
    return errors


def compute_build_fingerprint(
    tool_versions: Mapping[str, str] | None = None,
    artifact_checksums: Mapping[str, str] | None = None,
) -> str:
    """Compute a reproducibility hash covering inputs, tools, and artifacts.

    Returns:
        SHA-256 fingerprint string.
    """
    h = hashlib.sha256()
    for name, checksum in sorted(build_input_records().items()):
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update(checksum.encode("ascii"))
        h.update(b"\0")
    for name, version in sorted((tool_versions or {}).items()):
        h.update(f"tool:{name}\0{version}\0".encode())
    for name, checksum in sorted((artifact_checksums or {}).items()):
        h.update(f"artifact:{name}\0{checksum}\0".encode())
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


def validate_dual_d64_artifacts(
    build_dir: str | Path = "build",
) -> list[str]:
    """Validate dual-device D64 packaging (basicv3 + georam + reu).

    Args:
        build_dir: Build output directory containing release artifacts.

    Returns:
        Deterministic list of packaging/validation errors (empty when valid).
    """
    # Local import keeps validate_build importable before tools/ is on sys.path
    # in callers that only need schema checks.
    from package_d64 import validate_dual_d64_release

    root = Path(build_dir)
    return validate_dual_d64_release(
        root / "compiler.d64",
        basicv3_path=root / "basicv3.prg",
        georam_path=root / "georam.bin",
        reu_path=root / "reu.bin",
    )


def validate_georam_image_budget(size_report_path: str) -> list[str]:
    """Hard-fail when the geoRAM-canonical image exceeds 512 KiB (2048 pages).

    End-to-end gate over ``size_report.json`` produced by
    ``generate_build_reports``. Larger detected devices may only add dynamic
    storage; the base image must always fit 512 KiB (REQUIREMENTS §8.1 /
    DESIGN2 §1).

    Args:
        size_report_path: Path to the generated size report.

    Returns:
        Deterministic list of budget errors (empty when within limit).
    """
    errors: list[str] = []
    path = Path(size_report_path)
    if not path.exists():
        return [f"size report missing for geoRAM budget check: {size_report_path}"]
    report = _load_json(str(path))

    page_limit = report.get("georam_page_limit", 2048)
    byte_limit = report.get("georam_byte_limit", 512 * 1024)
    pages = report.get("georam_pages")
    georam_bytes = report.get("georam_bytes")

    if not isinstance(page_limit, int) or page_limit <= 0:
        errors.append(f"size_report.georam_page_limit is invalid: {page_limit!r}")
        page_limit = 2048
    if not isinstance(byte_limit, int) or byte_limit <= 0:
        errors.append(f"size_report.georam_byte_limit is invalid: {byte_limit!r}")
        byte_limit = 512 * 1024

    if not isinstance(pages, int):
        errors.append("size_report.georam_pages is missing or not an integer")
    elif pages > page_limit:
        errors.append(
            f"geoRAM image exceeds 512 KiB budget: {pages} pages > {page_limit} limit"
        )

    if georam_bytes is not None:
        if not isinstance(georam_bytes, int):
            errors.append("size_report.georam_bytes is not an integer")
        elif georam_bytes > byte_limit:
            errors.append(
                f"geoRAM image exceeds 512 KiB budget: {georam_bytes} bytes > "
                f"{byte_limit} limit"
            )

    if report.get("georam_within_limit") is not True:
        errors.append("size_report.georam_within_limit is not true (512 KiB hard fail)")

    # Cross-check the on-disk image when present so a stale report cannot
    # hide an oversize artifact.
    georam_bin = path.parent / "georam.bin"
    if georam_bin.exists():
        raw = georam_bin.read_bytes()
        payload = (
            len(raw) - 2
            if len(raw) >= 2 and raw[0] == 0x00 and raw[1] == 0xDE
            else len(raw)
        )
        if payload > byte_limit:
            errors.append(
                f"georam.bin payload exceeds 512 KiB budget: {payload} bytes > "
                f"{byte_limit} limit"
            )
        image_pages = (payload + 255) // 256
        if image_pages > page_limit:
            errors.append(
                f"georam.bin exceeds page budget: {image_pages} pages > "
                f"{page_limit} limit"
            )

    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for error in errors:
        if error not in seen:
            seen.add(error)
            ordered.append(error)
    return ordered


def validate_xip_path_contracts(
    *,
    source_root: str | Path = "src",
    policy_path: str | Path = "manifests/placement_policy.json",
    routine_directory_path: str | Path = "build/routine_directory.json",
) -> list[str]:
    """Validate expansion-native call paths and conforming directory coverage.

    Runs the production XIP-path auditor in read-only mode: direct ``jsr``/``jmp``
    into ``expansion_xip`` symbols are rejected, and every policy entry marked
    ``conforming`` must have a generated geoRAM directory record.  Validation
    never rewrites or re-signs fingerprints or manifests.

    Args:
        source_root: Production assembly tree to scan for direct calls.
        policy_path: Checked-in placement-policy JSON.
        routine_directory_path: Generated geoRAM routine directory.

    Returns:
        Deterministic list of XIP-path contract errors (empty when valid).
    """
    # Local import keeps validate_build importable when only schema checks run.
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    from xip_path_audit import direct_xip_calls, missing_xip_directory_entries

    errors: list[str] = []
    try:
        errors.extend(direct_xip_calls(Path(source_root), Path(policy_path)))
        errors.extend(
            missing_xip_directory_entries(
                Path(policy_path), Path(routine_directory_path)
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"XIP path audit failed: {error}")
    return errors


def validate_expansion_contracts(build_dir: str | Path = "build") -> list[str]:
    """Validate generated geoRAM and REU release-contract agreement.

    The shipped REU artifact remains a patch-only sidecar: live ``overlays`` and
    ``slot_classes`` must stay empty and ``implementation_status`` must stay
    ``patch_only_no_reu_xip_overlays``.  Dual ``routine_records`` are required
    for every linked geoRAM page so REU placement can be audited without
    claiming DMA-to-XIP execution is live.

    Args:
        build_dir: Release output directory.

    Returns:
        Deterministic contract errors, or an empty list when the artifacts
        accurately describe the linked and packaged release.
    """
    # Import locally so the validator and generator stay in lockstep without
    # forcing a package install for every build-tool invocation.
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import generate_expansion_contracts as expansion_contracts

    root = Path(build_dir)
    required = {
        "routine directory": root / "routine_directory.json",
        "REU loader manifest": root / "reu_loader_manifest.json",
        "overlay directory": root / "overlay_directory.json",
        "REU layout": root / "reu_layout.json",
    }
    errors = [
        f"{name} is missing: {path}"
        for name, path in required.items()
        if not path.is_file()
    ]
    if errors:
        return errors
    try:
        routine_document = _load_json(str(required["routine directory"]))
        reu_manifest = _load_json(str(required["REU loader manifest"]))
        overlay = _load_json(str(required["overlay directory"]))
        reu_layout = _load_json(str(required["REU layout"]))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"expansion contract is invalid: {error}"]

    routines = routine_document.get("routines")
    if not isinstance(routines, dict):
        return ["linked routine directory routines must be an object"]
    expected_records: list[dict[str, Any]] = []
    expected_dual: list[dict[str, Any]] = []
    for name, record in sorted(routines.items(), key=lambda item: int(item[1]["id"])):
        if not isinstance(record, dict) or record.get("layer") != "georam":
            continue
        try:
            block = int(record["block"])
            page = int(record["page"])
            entry_offset = int(record["offset"])
            window_address = str(record["address"])
            routine_id = int(record["id"])
            expected_records.append(
                {
                    "routine_id": routine_id,
                    "routine_name": str(name),
                    "block": block,
                    "page": page,
                    "entry_offset": entry_offset,
                    "window_address": window_address,
                }
            )
            expected_dual.append(
                expansion_contracts.dual_routine_record(
                    routine_id=routine_id,
                    routine_name=str(name),
                    block=block,
                    page=page,
                    entry_offset=entry_offset,
                    window_address=window_address,
                )
            )
        except (KeyError, TypeError, ValueError):
            errors.append(f"linked geoRAM routine has incomplete placement: {name}")

    if overlay.get("backend") != "georam":
        errors.append("overlay directory backend is not georam")
    if overlay.get("routines") != expected_records:
        errors.append("overlay directory differs from linked geoRAM routine placements")
    if overlay.get("routine_count") != len(expected_records):
        errors.append(
            "overlay directory routine count disagrees with linked placements"
        )
    if overlay.get("routine_directory_sha256") != _sha256_file(
        required["routine directory"]
    ):
        errors.append("overlay directory routine-directory checksum is stale")

    if reu_manifest.get("kind") != "reu_patch":
        errors.append("REU loader manifest is not a reu_patch document")
    if reu_layout.get("backend") != "reu_patch_only":
        errors.append("REU layout backend does not describe the shipped patch")
    if (
        reu_layout.get("implementation_status")
        != expansion_contracts.IMPLEMENTATION_STATUS
    ):
        errors.append("REU layout does not disclose patch-only implementation")
    if reu_layout.get("source_georam_sha256") != reu_manifest.get("georam_sha256"):
        errors.append("REU layout source geoRAM checksum disagrees with REU patch")
    if reu_layout.get("slot_classes") != [] or reu_layout.get("overlays") != []:
        errors.append("patch-only REU layout must not advertise executable overlays")

    dual_records = reu_layout.get("routine_records")
    if not isinstance(dual_records, list):
        errors.append("REU layout routine_records must be a list")
    elif dual_records != expected_dual:
        errors.append(
            "REU layout routine_records disagree with linked geoRAM dual placements"
        )
    if reu_layout.get("routine_record_count") != len(expected_dual):
        errors.append(
            "REU layout routine_record_count disagrees with dual placements"
        )

    if isinstance(dual_records, list):
        for record in dual_records:
            if not isinstance(record, dict):
                errors.append("REU dual routine record is not an object")
                continue
            reu_half = record.get("reu")
            if not isinstance(reu_half, dict):
                errors.append(
                    f"REU dual record missing reu half: {record.get('routine_name')}"
                )
                continue
            if reu_half.get("execution_status") != expansion_contracts.EXECUTION_NOT_LIVE:
                errors.append(
                    "patch-only REU dual record claims live execution: "
                    f"{record.get('routine_name')}"
                )
            if reu_half.get("slot_class") != expansion_contracts.PRIMARY_XIP_SLOT_CLASS:
                errors.append(
                    "REU dual record has unexpected slot class: "
                    f"{record.get('routine_name')}"
                )
            if reu_half.get("image_length") != expansion_contracts.PAGE_BYTES:
                errors.append(
                    "REU dual record page image length is not 256: "
                    f"{record.get('routine_name')}"
                )

    planned = reu_layout.get("planned_slot_classes")
    expected_planned = [
        {
            "slot_class": expansion_contracts.PRIMARY_XIP_SLOT_CLASS,
            "origin": expansion_contracts.PRIMARY_XIP_SLOT_ORIGIN,
            "capacity_bytes": expansion_contracts.PAGE_BYTES,
            "execution_status": expansion_contracts.EXECUTION_NOT_LIVE,
        }
    ]
    if planned != expected_planned:
        errors.append(
            "REU layout planned_slot_classes must document the non-live primary "
            "XIP miss slot"
        )
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
    errors.extend(validate_expansion_contracts("build"))
    errors.extend(validate_xip_path_contracts())
    return errors


def _extract_normative_requirement_ids(paths: Sequence[Path]) -> set[str]:
    """Extract stable trace IDs from normative requirement headings."""
    requirement_ids: set[str] = set()
    numbered_heading = re.compile(r"^#{2,6}\s+(\d+(?:\.\d+)*)\b")
    reu_heading = re.compile(r"^#{2,6}\s+(RREU-\d+)\b")
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if match := reu_heading.match(line):
                requirement_ids.add(match.group(1))
            elif path.name == "REQUIREMENTS.md" and (
                match := numbered_heading.match(line)
            ):
                section = match.group(1)
                if section != "1":
                    requirement_ids.add(f"R{section}")
    return requirement_ids


def _trace_matrix_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical generated-matrix view of one trace record."""
    projected = {
        "id": record["id"],
        "ears": record["ears"],
        "source_section": record["source_section"],
        "design_section": record["design_section"],
        "implementation": record["implementation"],
        "tests": record["tests"],
        "status": record["status"],
    }
    if "reference_fixture_provenance" in record:
        projected["reference_fixture_provenance"] = record[
            "reference_fixture_provenance"
        ]
    return projected


def validate_traceability(
    trace_path: str,
    matrix_path: str,
    requirement_paths: Sequence[str] = (
        "REQUIREMENTS.md",
        "REU_REQUIREMENTS.md",
    ),
    project_root: str = ".",
) -> list[str]:
    """Validate complete normative trace coverage and the generated matrix.

    Args:
        trace_path: Traceability manifest path, relative to ``project_root``.
        matrix_path: Generated requirements matrix path.
        requirement_paths: Normative requirement document paths.
        project_root: Project root used to resolve every contract path.

    Returns:
        Human-readable validation errors. An empty list means valid.
    """
    root = Path(project_root)
    trace_file = root / trace_path
    matrix_file = root / matrix_path
    normative_paths = [root / path for path in requirement_paths]
    errors: list[str] = []

    for path in normative_paths:
        if not path.is_file():
            errors.append(f"Normative requirement source is missing: {path}")
    if errors:
        return errors
    if not trace_file.is_file():
        return [f"Traceability manifest is missing: {trace_file}"]

    try:
        trace = _load_json(str(trace_file))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"Traceability manifest is invalid: {error}"]

    expected_sources = [Path(path).as_posix() for path in requirement_paths]
    if trace.get("requirement_sources") != expected_sources:
        errors.append(
            "Traceability requirement_sources must name both normative documents: "
            f"{expected_sources}"
        )

    raw_records = trace.get("records")
    if not isinstance(raw_records, list):
        return errors + ["Traceability records must be a list"]
    records = [record for record in raw_records if isinstance(record, dict)]
    if len(records) != len(raw_records):
        errors.append("Every traceability record must be a JSON object")

    record_ids = [str(record.get("id", "")) for record in records]
    duplicate_ids = sorted(
        requirement_id
        for requirement_id in set(record_ids)
        if record_ids.count(requirement_id) > 1
    )
    if duplicate_ids:
        errors.append(f"Duplicate traceability IDs: {duplicate_ids}")

    expected_ids = _extract_normative_requirement_ids(normative_paths)
    traced_ids = set(record_ids)
    missing_ids = sorted(expected_ids - traced_ids)
    unknown_ids = sorted(traced_ids - expected_ids)
    if missing_ids:
        errors.append(
            f"Normative requirement sections lack trace records: {missing_ids}"
        )
    if unknown_ids:
        errors.append(f"Trace records use unknown requirement IDs: {unknown_ids}")

    required_fields = (
        "id",
        "ears",
        "source_section",
        "design_section",
        "implementation",
        "tests",
        "status",
    )
    allowed_statuses = {
        "planned",
        "implemented",
        "unsupported",
        "not-applicable",
        "passing",
    }
    mapped_tests: dict[str, set[str]] = {}
    for record in records:
        requirement_id = str(record.get("id", "<missing-id>"))
        missing_fields = [field for field in required_fields if not record.get(field)]
        if missing_fields:
            errors.append(
                f"Requirement {requirement_id} lacks fields: {missing_fields}"
            )
            continue
        if " shall " not in f" {str(record['ears']).lower()} ":
            errors.append(
                f"Requirement {requirement_id} is not an EARS shall statement"
            )
        if record["status"] not in allowed_statuses:
            errors.append(
                f"Requirement {requirement_id} has invalid status {record['status']}"
            )

        expected_source = (
            "REU_REQUIREMENTS.md"
            if requirement_id.startswith("RREU-")
            else "REQUIREMENTS.md"
        )
        if not str(record["source_section"]).startswith(f"{expected_source}#"):
            errors.append(
                f"Requirement {requirement_id} has invalid source_section "
                f"{record['source_section']}"
            )

        for field in ("source_section", "design_section", "implementation"):
            relative_path = str(record[field]).split("#", maxsplit=1)[0]
            if not (root / relative_path).exists():
                errors.append(
                    f"Requirement {requirement_id} {field} path is missing: "
                    f"{relative_path}"
                )
        provenance = record.get("reference_fixture_provenance")
        if provenance and not (root / str(provenance)).is_dir():
            errors.append(
                f"Requirement {requirement_id} fixture provenance is missing: "
                f"{provenance}"
            )

        tests = record["tests"]
        if not isinstance(tests, list) or not all(
            isinstance(test, str) and test for test in tests
        ):
            errors.append(
                f"Requirement {requirement_id} tests must be non-empty strings"
            )
            continue
        for test_name in tests:
            mapped_tests.setdefault(test_name, set()).add(requirement_id)

    if not matrix_file.is_file():
        return errors + [f"Generated requirements matrix is missing: {matrix_file}"]
    try:
        matrix = _load_json(str(matrix_file))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return errors + [f"Generated requirements matrix is invalid: {error}"]

    expected_records = [_trace_matrix_record(record) for record in records]
    if matrix.get("mapped_requirements") != expected_records:
        errors.append(
            "Generated requirements matrix is stale relative to trace records"
        )
    inverse_rows = {
        str(row.get("test")): set(row.get("requirements", []))
        for row in matrix.get("mapped_tests", [])
        if isinstance(row, dict)
    }
    if inverse_rows != mapped_tests:
        errors.append("Generated matrix test-to-requirement index is stale")
    if matrix.get("requirements_count") != len(records):
        errors.append("Generated matrix requirement count is stale")
    if matrix.get("tests_count") != len(mapped_tests):
        errors.append("Generated matrix test count is stale")
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

    if option == "--traceability":
        ok = _report_errors(
            validate_traceability(
                "manifests/traceability.json",
                "build/requirements_matrix.json",
            ),
            "Requirements traceability matrix validated successfully.",
        )
        raise SystemExit(0 if ok else 1)

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

    if option == "--xip-path":
        ok = _report_errors(
            validate_xip_path_contracts(),
            "XIP path contracts validated successfully.",
        )
        raise SystemExit(0 if ok else 1)

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
        errors.extend(validate_dual_d64_artifacts("build"))
        errors.extend(
            validate_generated_reference(
                "build/API.md",
                "build/MAP.md",
                "build/production_entries.json",
            )
        )
        errors.extend(validate_build_manifest("build/build_manifest.json"))
        errors.extend(validate_required_release_artifacts(Path("build")))
        ok = _report_errors(errors, "All build contracts validated successfully.")
        raise SystemExit(0 if ok else 1)

    if option == "--write-manifest":
        manifest_data = write_build_manifest(Path("build"))
        print(f"Build manifest written. Fingerprint: {manifest_data['fingerprint']}")
        return

    if option is not None:
        print(f"Error: unknown validation option: {option}")
        raise SystemExit(2)

    # Validation is deliberately read-only.  A stale artifact must be rebuilt,
    # never re-signed by a validation command.
    errors = validate_build_manifest("build/build_manifest.json")
    ok = _report_errors(errors, "Build manifest validated successfully.")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
