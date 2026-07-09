"""Loader and schema validation for immutable stock VICE observations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, cast

ROOT: Final = Path(__file__).resolve().parents[1] / "fixtures" / "reference"
PROFILE_DIRECTORIES: Final = {
    "basicv2": "c64_basicv2",
    "basicv35": "plus4_basicv35",
    "ieee": "ieee_oracle",
}
REQUIRED_FIELDS: Final = {
    "schema_version",
    "profile",
    "machine",
    "vice_executable",
    "vice_version",
    "rom_checksums",
    "source_text",
    "input_sequence",
    "reference_mode",
    "raw_screen",
    "raw_error",
    "raw_state",
    "normalized_result",
    "normalization_rules",
    "generator_version",
    "regeneration_fingerprint",
}


def load_reference(profile: str, fixture_id: str) -> dict[str, Any]:
    """Load and validate one checked-in stock observation."""
    directory = PROFILE_DIRECTORIES[profile]
    path = ROOT / directory / f"{fixture_id}.json"
    data = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise ValueError(f"{path} is missing fixture fields: {sorted(missing)}")
    if data["profile"] != profile:
        raise ValueError(
            f"{path} has profile {data['profile']!r}, expected {profile!r}"
        )
    return data
