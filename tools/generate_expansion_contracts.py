"""Generate release contracts for the installed geoRAM image and REU patch.

The shipped REU sidecar is still a versioned patch for the geoRAM-canonical
image; DMA-to-XIP overlay execution is not live.  The generated layout keeps
that limitation explicit while also emitting ABI-compatible dual GeoRAM/REU
*planned* records for every linked geoRAM page so dual-device placement can be
audited without fabricating executable REU overlays.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

# geoRAM packing: 64 pages per 16 KiB block, 256 bytes per page (docs/GEORAM_BANKING.md).
PAGES_PER_BLOCK = 64
PAGE_BYTES = 256

# DESIGN2 / REU_DESIGN revised model: REU DMA-copies the same 256-byte page
# into the primary miss slot at $CE00.  These are planned, not live.
PRIMARY_XIP_SLOT_CLASS = "primary_xip_miss"
PRIMARY_XIP_SLOT_ORIGIN = "$CE00"
EXECUTION_NOT_LIVE = "not_live"
IMPLEMENTATION_STATUS = "patch_only_no_reu_xip_overlays"


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest for one generated input."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logical_page(block: int, page: int) -> int:
    """Return the linear logical page index for a geoRAM block/page pair."""
    return int(block) * PAGES_PER_BLOCK + int(page)


def reu_start_for_page(block: int, page: int) -> int:
    """Return the REU byte start of the geoRAM-canonical page image."""
    return logical_page(block, page) * PAGE_BYTES


def dual_routine_record(
    *,
    routine_id: int,
    routine_name: str,
    block: int,
    page: int,
    entry_offset: int,
    window_address: str,
) -> dict[str, Any]:
    """Build one ABI-compatible dual GeoRAM/REU placement record.

    The REU half describes the planned page-DMA placement into the primary
    XIP miss slot.  ``execution_status`` is always ``not_live`` for patch-only
    releases so validators can reject fabricated live overlays.
    """
    page_index = logical_page(block, page)
    return {
        "routine_id": int(routine_id),
        "routine_name": str(routine_name),
        "return_kind": "rts",
        "georam": {
            "block": int(block),
            "page": int(page),
            "entry_offset": int(entry_offset),
            "window_address": str(window_address),
        },
        "reu": {
            "logical_page": page_index,
            "reu_start": page_index * PAGE_BYTES,
            "image_length": PAGE_BYTES,
            "entry_offset": int(entry_offset),
            "slot_class": PRIMARY_XIP_SLOT_CLASS,
            "slot_origin": PRIMARY_XIP_SLOT_ORIGIN,
            "execution_status": EXECUTION_NOT_LIVE,
        },
    }


def generate(build_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build geoRAM-directory and REU-layout contracts from release artifacts.

    Args:
        build_dir: Directory containing the linked routine directory and REU
            patch manifest.

    Returns:
        The overlay-directory and REU-layout JSON documents.

    Raises:
        FileNotFoundError: If a linked or packaged prerequisite is absent.
        ValueError: If a geoRAM routine lacks a complete physical placement.
    """
    routine_path = build_dir / "routine_directory.json"
    reu_manifest_path = build_dir / "reu_loader_manifest.json"
    if not routine_path.is_file():
        raise FileNotFoundError(f"linked routine directory is missing: {routine_path}")
    if not reu_manifest_path.is_file():
        raise FileNotFoundError(f"REU loader manifest is missing: {reu_manifest_path}")

    routine_document = json.loads(routine_path.read_text(encoding="utf-8"))
    raw_routines = routine_document.get("routines")
    if not isinstance(raw_routines, dict):
        raise ValueError("routine directory routines must be an object")

    georam_records: list[dict[str, Any]] = []
    dual_records: list[dict[str, Any]] = []
    for name, raw_record in sorted(
        raw_routines.items(), key=lambda item: int(item[1]["id"])
    ):
        if not isinstance(raw_record, dict) or raw_record.get("layer") != "georam":
            continue
        required = ("id", "block", "page", "offset", "address")
        if any(key not in raw_record for key in required):
            raise ValueError(f"geoRAM routine {name} lacks a complete placement")
        block = int(raw_record["block"])
        page = int(raw_record["page"])
        entry_offset = int(raw_record["offset"])
        window_address = str(raw_record["address"])
        routine_id = int(raw_record["id"])
        georam_records.append(
            {
                "routine_id": routine_id,
                "routine_name": str(name),
                "block": block,
                "page": page,
                "entry_offset": entry_offset,
                "window_address": window_address,
            }
        )
        dual_records.append(
            dual_routine_record(
                routine_id=routine_id,
                routine_name=str(name),
                block=block,
                page=page,
                entry_offset=entry_offset,
                window_address=window_address,
            )
        )

    reu_manifest = json.loads(reu_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(reu_manifest, dict) or reu_manifest.get("kind") != "reu_patch":
        raise ValueError("REU loader manifest is not a reu_patch document")

    overlay_directory = {
        "schema_version": 1,
        "backend": "georam",
        "routine_directory_sha256": _sha256(routine_path),
        "routine_count": len(georam_records),
        "routines": georam_records,
    }
    reu_layout = {
        "schema_version": 1,
        "backend": "reu_patch_only",
        "implementation_status": IMPLEMENTATION_STATUS,
        "notes": (
            "routine_records are planned dual GeoRAM/REU page placements derived "
            "from the linked geoRAM directory.  Live REU DMA-to-XIP overlay "
            "execution is not shipped; overlays and live slot_classes stay empty."
        ),
        "source_georam_sha256": reu_manifest.get("georam_sha256"),
        "patch": {
            "format_version": reu_manifest.get("format_version"),
            "abi_version": reu_manifest.get("abi_version"),
            "min_reu_capacity_kib": reu_manifest.get("min_reu_capacity_kib"),
            "fixup_bytes": reu_manifest.get("fixup_bytes"),
            "crc32": reu_manifest.get("crc32"),
        },
        "planned_slot_classes": [
            {
                "slot_class": PRIMARY_XIP_SLOT_CLASS,
                "origin": PRIMARY_XIP_SLOT_ORIGIN,
                "capacity_bytes": PAGE_BYTES,
                "execution_status": EXECUTION_NOT_LIVE,
            }
        ],
        # Live execution fields remain empty while the release is patch-only.
        "slot_classes": [],
        "overlays": [],
        "routine_records": dual_records,
        "routine_record_count": len(dual_records),
    }
    return overlay_directory, reu_layout


def write(build_dir: Path) -> None:
    """Write both expansion contracts into ``build_dir``."""
    overlay_directory, reu_layout = generate(build_dir)
    (build_dir / "overlay_directory.json").write_text(
        json.dumps(overlay_directory, indent=2) + "\n", encoding="utf-8"
    )
    (build_dir / "reu_layout.json").write_text(
        json.dumps(reu_layout, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    """Generate the two release expansion-contract artifacts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    args = parser.parse_args()
    write(args.build_dir)


if __name__ == "__main__":
    main()
