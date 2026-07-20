"""Tests for the read-only legacy automatic-porter compatibility audit."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from legacy_porter_compat import audit_legacy_porter


def test_annotation_only_porter_is_identified_as_reusable() -> None:
    """An annotation parser with no RAM-retention policy is safe to study."""
    audit = audit_legacy_porter('; GEORAM-ABI: preserves=A,X,Y\n')

    assert audit.annotation_syntax == ("preserves=A,X,Y",)
    assert audit.annotation_protocol_supported is True
    assert audit.prohibited_policies == ()
    assert audit.reusable_for_annotations_only is True


def test_ram_fallback_porter_is_rejected_even_with_annotations() -> None:
    """Compiler 2 must not adopt legacy normal-RAM fallback behavior."""
    source = """
    ; GEORAM-ABI: fallthrough_to=next
    const std::set<std::string> kForceFallback = {};
    std::string GenerateRamFallbackFile();
    """

    audit = audit_legacy_porter(source)

    assert audit.reusable_for_annotations_only is False
    assert audit.prohibited_policies == ("force_fallback", "ram_fallback_output")


def test_actual_legacy_porter_is_annotation_only_incompatible() -> None:
    """The companion porter is evidence for annotation grammar, not production use."""
    legacy = (
        Path(__file__).resolve().parents[3]
        / "compiler"
        / "tools"
        / "cpp"
        / "georam_batch_port.cpp"
    )
    if not legacy.exists():
        return

    audit = audit_legacy_porter(legacy.read_text(encoding="utf-8"))

    assert audit.annotation_protocol_supported is True
    assert {"force_port", "force_fallback", "ram_fallback_output"} <= set(
        audit.prohibited_policies
    )
    assert audit.reusable_for_annotations_only is False
