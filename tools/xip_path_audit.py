"""Audit production assembly paths for expansion-native XIP entries.

The placement policy is the authority for the target execution location.  This
module deliberately does not infer that a ``src/geoasm`` source file executes
from geoRAM merely because a sidecar contains a copy of its linked bytes.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_CALL = re.compile(r"^\s*(?:jsr|jmp)\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE)


def _load_object(path: Path) -> dict[str, Any]:
    """Load one JSON object from ``path``.

    Args:
        path: JSON file to load.

    Returns:
        Parsed JSON object.

    Raises:
        ValueError: The file does not contain a JSON object.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def expansion_xip_entries(policy_path: Path) -> dict[str, dict[str, Any]]:
    """Return target expansion-XIP entries keyed by routine name.

    Args:
        policy_path: Checked-in placement-policy JSON file.

    Returns:
        Placement-policy records whose target is ``expansion_xip``.

    Raises:
        ValueError: The policy has no list-valued ``routines`` collection or
            includes malformed/duplicate routine records.
    """
    records = _load_object(policy_path).get("routines")
    if not isinstance(records, list):
        raise ValueError("placement policy must contain a routines list")
    entries: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("placement policy routine records must be objects")
        name = record.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("placement policy routine record is missing name")
        if name in entries:
            raise ValueError(f"placement policy contains duplicate routine {name}")
        if record.get("target_placement") == "expansion_xip":
            entries[name] = record
    return entries


def page_bound_xip_entries(policy_path: Path) -> dict[str, dict[str, Any]]:
    """Return expansion-XIP entries that already have a dedicated geoRAM page.

    Unported ``expansion_xip`` targets may still execute from a normal-RAM
    body while their call-path migration is incomplete.  Once a routine is
    page-bound (``xip_page`` set in the placement inventory / ABI manifest),
    its public symbol links at ``$DE00`` and every production ``jsr``/``jmp``
    must enter through the resident gate instead.

    Args:
        policy_path: Checked-in placement-policy JSON file.

    Returns:
        Subset of :func:`expansion_xip_entries` with an explicit ``xip_page``.
    """
    return {
        name: record
        for name, record in expansion_xip_entries(policy_path).items()
        if record.get("xip_page") is not None
    }


def direct_xip_calls(source_root: Path, policy_path: Path) -> list[str]:
    """Find direct production calls to page-bound expansion-native entries.

    Cross-page XIP calls must go through the generated resident dispatcher or
    gate.  Calling the linked ``$DE00`` window by its public entry symbol is
    therefore always a violation for page-bound routines, irrespective of
    whether the caller happens to live under ``src/resident`` or
    ``src/geoasm``.

    Args:
        source_root: Production source directory to inspect.
        policy_path: Checked-in placement-policy JSON file.

    Returns:
        Sorted ``path:line: opcode target`` violations.
    """
    targets = set(page_bound_xip_entries(policy_path))
    violations: list[str] = []
    for source in sorted(source_root.rglob("*.asm")):
        for line_number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), 1
        ):
            code = line.split(";", maxsplit=1)[0]
            match = _CALL.match(code)
            if match is None:
                continue
            target = match.group(1)
            if target in targets:
                opcode = code.strip().split(maxsplit=1)[0].lower()
                violations.append(
                    f"{source}:{line_number}: direct {opcode} to expansion_xip "
                    f"routine {target}"
                )
    return violations


def missing_xip_directory_entries(
    policy_path: Path, routine_directory_path: Path
) -> list[str]:
    """Find conforming XIP entries absent from the generated geoRAM directory.

    Entries still labelled ``migration_required`` intentionally remain visible
    debt during the RED phase.  Once an entry is marked conforming, a geoRAM
    page/offset/address record is mandatory and a normal-RAM mirror cannot
    satisfy this check.

    Args:
        policy_path: Checked-in placement-policy JSON file.
        routine_directory_path: Generated routine directory JSON file.

    Returns:
        Sorted placement-contract violations.
    """
    directory = _load_object(routine_directory_path).get("routines")
    if not isinstance(directory, dict):
        raise ValueError("routine directory must contain a routines object")
    errors: list[str] = []
    for name, record in expansion_xip_entries(policy_path).items():
        if record.get("conformance") != "conforming":
            continue
        generated = directory.get(name)
        if not isinstance(generated, dict) or generated.get("layer") != "georam":
            errors.append(
                f"{name}: conforming expansion_xip routine lacks geoRAM entry"
            )
            continue
        missing = [
            field
            for field in ("block", "page", "offset", "address")
            if field not in generated
        ]
        if missing:
            errors.append(
                f"{name}: conforming expansion_xip routine geoRAM entry is missing "
                f"{', '.join(missing)}"
            )
    return sorted(errors)


def missing_reu_dual_records(
    policy_path: Path,
    routine_directory_path: Path,
    reu_layout_path: Path,
) -> list[str]:
    """Find geoRAM-placed expansion_xip entries without a dual REU record.

    Dual records are required even while REU DMA-to-XIP execution is not live
    (RREU-5.17 / T14.2).  A record that claims live execution under a patch-only
    layout is also a violation.

    Args:
        policy_path: Checked-in placement-policy JSON file.
        routine_directory_path: Generated routine directory JSON file.
        reu_layout_path: Generated REU layout contract.

    Returns:
        Sorted dual-record violations.
    """
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import generate_expansion_contracts as expansion_contracts

    directory = _load_object(routine_directory_path).get("routines")
    if not isinstance(directory, dict):
        raise ValueError("routine directory must contain a routines object")
    reu_layout = _load_object(reu_layout_path)
    dual_records = reu_layout.get("routine_records")
    if not isinstance(dual_records, list):
        raise ValueError("reu layout must contain a routine_records list")
    by_name: dict[str, dict[str, Any]] = {}
    for record in dual_records:
        if not isinstance(record, dict):
            continue
        name = record.get("routine_name")
        if isinstance(name, str) and name:
            by_name[name] = record

    errors: list[str] = []
    for name, policy in expansion_xip_entries(policy_path).items():
        generated = directory.get(name)
        # Only require dual records once a geoRAM page placement exists.
        if not isinstance(generated, dict) or generated.get("layer") != "georam":
            if policy.get("conformance") == "conforming":
                errors.append(
                    f"{name}: expansion_xip routine lacks geoRAM placement for "
                    "dual REU record"
                )
            continue
        try:
            expected = expansion_contracts.dual_routine_record(
                routine_id=int(generated["id"]),
                routine_name=name,
                block=int(generated["block"]),
                page=int(generated["page"]),
                entry_offset=int(generated["offset"]),
                window_address=str(generated["address"]),
            )
        except (KeyError, TypeError, ValueError):
            errors.append(f"{name}: geoRAM placement is incomplete for dual REU record")
            continue
        actual = by_name.get(name)
        if actual != expected:
            errors.append(
                f"{name}: missing or mismatched ABI-compatible REU dual record"
            )
            continue
        reu_half = actual.get("reu") if isinstance(actual, dict) else None
        if (
            not isinstance(reu_half, dict)
            or reu_half.get("execution_status")
            != expansion_contracts.EXECUTION_NOT_LIVE
        ):
            errors.append(
                f"{name}: REU dual record must remain not_live while patch-only"
            )
    return sorted(errors)
