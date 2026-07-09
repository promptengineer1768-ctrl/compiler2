"""Tests for preserving physical routine addresses after the staging link."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_georam_window_address_is_not_replaced_by_staging_label(
    tmp_path: Path,
) -> None:
    """A temporary RAM link must not corrupt a geoRAM directory entry."""
    labels = tmp_path / "compiler.lbl"
    labels.write_text(
        "al 004321 .tokenize\nal 001234 .resident_call\n", encoding="utf-8"
    )
    directory = tmp_path / "routine_directory.json"
    directory.write_text(
        json.dumps(
            {
                "routines": {
                    "tokenize": {
                        "id": 0,
                        "layer": "georam",
                        "address": "$DE40",
                    },
                    "resident_call": {
                        "id": 1,
                        "layer": "resident",
                        "address": "dynamic",
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    script = (
        Path(__file__).resolve().parents[2] / "tools" / "update_routine_addresses.py"
    )
    subprocess.run(
        [sys.executable, str(script), str(labels), str(directory)],
        check=True,
    )

    routines = json.loads(directory.read_text(encoding="utf-8"))["routines"]
    assert routines["tokenize"]["address"] == "$DE40"
    assert routines["resident_call"]["address"] == "$1234"
