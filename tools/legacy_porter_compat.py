"""Read-only compatibility audit for the legacy geoRAM automatic porter.

This tool deliberately never invokes the legacy porter or consumes its generated
assembly.  It records whether a candidate porter offers reusable annotation
parsing while rejecting policies that would silently retain Compiler 2 routines
in normal RAM.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


_ABI_PATTERN = re.compile(r";\s*GEORAM-ABI:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
_POLICY_MARKERS = {
    "force_port": re.compile(r"\bkForcePort\b"),
    "force_fallback": re.compile(r"\bkForceFallback\b"),
    "ram_fallback_output": re.compile(r"\bGenerateRamFallbackFile\b"),
    "page_limit_pruning": re.compile(r"\bpage_limit_pruned\b"),
}


@dataclass(frozen=True)
class LegacyPorterAudit:
    """Compatibility result for one legacy porter source file."""

    annotation_syntax: tuple[str, ...]
    annotation_protocol_supported: bool
    prohibited_policies: tuple[str, ...]
    reusable_for_annotations_only: bool


def audit_legacy_porter(source: str) -> LegacyPorterAudit:
    """Audit legacy porter source without running or transforming it.

    Args:
        source: Complete text of the candidate automatic-porter source.

    Returns:
        A compatibility result.  A porter is reusable only for annotation
        discovery when it exposes ``GEORAM-ABI`` parsing and has no policy that
        forces a routine into, or generates, normal-RAM fallback code.
    """
    annotations = tuple(sorted(set(_ABI_PATTERN.findall(source))))
    prohibited = tuple(
        name for name, marker in _POLICY_MARKERS.items() if marker.search(source)
    )
    return LegacyPorterAudit(
        annotation_syntax=annotations,
        annotation_protocol_supported="GEORAM-ABI" in source,
        prohibited_policies=prohibited,
        reusable_for_annotations_only="GEORAM-ABI" in source and not prohibited,
    )


def main() -> None:
    """Write a deterministic JSON audit for a legacy porter source file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="legacy porter source to inspect")
    parser.add_argument("--output", type=Path, required=True, help="JSON report path")
    args = parser.parse_args()
    audit = audit_legacy_porter(args.source.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(asdict(audit), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
