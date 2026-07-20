"""Reject completion claims whose recorded production evidence is not usable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

INVALID_EVIDENCE = {"stale", "skipped", "missing", "failing"}
COMPLETE_STATUSES = {"passing", "complete"}


def load_json(path: Path) -> dict[str, Any]:
    """Load one JSON object with a useful error for callers."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_ledger(ledger: dict[str, Any]) -> list[str]:
    """Validate the ledger shape and invalidated-claim evidence."""
    errors: list[str] = []
    if ledger.get("schema_version") != 1:
        errors.append("completion claim ledger schema_version must be 1")
    claims = ledger.get("claims")
    if not isinstance(claims, list) or not claims:
        return errors + ["completion claim ledger must contain claims"]
    seen: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("completion claim must be an object")
            continue
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not claim_id:
            errors.append("completion claim is missing id")
        elif claim_id in seen:
            errors.append(f"duplicate completion claim id {claim_id}")
        else:
            seen.add(claim_id)
        for field in ("scope", "claim", "status"):
            if not isinstance(claim.get(field), str) or not claim[field]:
                errors.append(f"{claim_id}: missing {field}")
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{claim_id}: missing evidence")
            continue
        statuses = []
        for item in evidence:
            if not isinstance(item, dict) or not all(
                isinstance(item.get(field), str) and item[field]
                for field in ("kind", "path", "status", "reason")
            ):
                errors.append(f"{claim_id}: invalid evidence record")
                continue
            statuses.append(item["status"])
        if claim.get("status") == "invalidated" and not (
            set(statuses) & INVALID_EVIDENCE
        ):
            errors.append(f"{claim_id}: invalidated claim lacks failed evidence")
        if (
            claim.get("status") in COMPLETE_STATUSES
            and set(statuses) & INVALID_EVIDENCE
        ):
            errors.append(f"{claim_id}: complete claim has unusable evidence")
    return errors


def validate_traceability(
    ledger: dict[str, Any], traceability: dict[str, Any]
) -> list[str]:
    """Reject passing trace records covered by an invalidated audit claim."""
    statuses = {
        record.get("id"): record.get("status")
        for record in traceability.get("records", [])
        if isinstance(record, dict)
    }
    errors: list[str] = []
    for claim in ledger.get("claims", []):
        if not isinstance(claim, dict) or claim.get("status") != "invalidated":
            continue
        for requirement in claim.get("requirements", []):
            if statuses.get(requirement) in COMPLETE_STATUSES:
                errors.append(
                    f"{claim.get('id')}: traceability {requirement} is "
                    f"{statuses[requirement]} despite invalidated evidence"
                )
    return errors


def validate(ledger_path: Path, traceability_path: Path) -> list[str]:
    """Return all release-blocking completion-claim errors."""
    ledger = load_json(ledger_path)
    errors = validate_ledger(ledger)
    if errors:
        return errors
    return validate_traceability(ledger, load_json(traceability_path))


def main(argv: Sequence[str] | None = None) -> int:
    """Validate completion claims and return nonzero for release blockers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger", type=Path, default=Path("manifests/completion_claim_ledger.json")
    )
    parser.add_argument(
        "--traceability", type=Path, default=Path("manifests/traceability.json")
    )
    args = parser.parse_args(argv)
    errors = validate(args.ledger, args.traceability)
    if errors:
        print("Completion-claim validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Completion-claim validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
