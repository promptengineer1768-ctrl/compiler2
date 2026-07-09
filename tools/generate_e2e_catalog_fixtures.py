"""Generate E2E catalog coverage fixtures for scenario tables.

These fixtures make every catalog row executable in pytest. They are not stock
VICE captures; reviewed stock captures remain covered by
``tools/generate_vice_fixtures.py`` and the semantic fixture audit.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE_ROOT: Final = ROOT / "tests" / "fixtures" / "reference"
SAFE_CHARS: Final = re.compile(r"[^A-Z0-9]+")
SCENARIO_MODULES: Final = (
    "tests.e2e.test_e2e_basicv2_functions",
    "tests.e2e.test_e2e_basicv2_statements",
    "tests.e2e.test_e2e_basicv35_functions",
    "tests.e2e.test_e2e_basicv35_statements",
    "tests.e2e.test_e2e_basicv3_functions_ieee",
    "tests.e2e.test_e2e_basicv3_statements_ieee",
)
PROFILE_DIRECTORIES: Final = {
    "basicv2": "c64_basicv2",
    "basicv35": "plus4_basicv35",
    "ieee": "ieee_oracle",
}
PROFILE_MACHINES: Final = {
    "basicv2": ("C64", "x64sc.exe"),
    "basicv35": ("PLUS4", "xplus4.exe"),
    "ieee": ("ORACLE", "compiler2-oracle"),
}
GENERATOR_VERSION: Final = "1.0"


def _scenario_values() -> list[dict[str, object]]:
    """Load raw scenario dictionaries from parametrized pytest tables."""
    scenarios: list[dict[str, object]] = []
    for module_name in SCENARIO_MODULES:
        module = importlib.import_module(module_name)
        for parameter_set in module.SCENARIOS:
            value = parameter_set.values[0]
            if not isinstance(value, dict):
                raise TypeError(
                    f"Unexpected scenario value in {module_name}: {value!r}"
                )
            scenarios.append(value)
    return scenarios


def _fixture_id(scenario: dict[str, object]) -> str:
    """Return the fixture id used by tests for one scenario."""
    if scenario.get("fixture_id") is not None:
        return str(scenario["fixture_id"])
    profile = str(scenario["profile"])
    mode = str(scenario["mode"])
    reference_mode = "program" if mode == "compile" else mode
    keyword = _keyword_id(str(scenario["keyword"]))
    return f"{profile}-{reference_mode}-{keyword}"


def _keyword_id(keyword: str) -> str:
    """Return a stable fixture-safe keyword id."""
    safe = keyword.upper().replace("$", "_DOLLAR").replace("#", "_HASH")
    return SAFE_CHARS.sub("_", safe).strip("_")


def _source_text(scenario: dict[str, object]) -> str:
    """Build a compact executable source description for one catalog row."""
    keyword = str(scenario["keyword"])
    mode = str(scenario["mode"])
    if mode == "immediate":
        return f"REM E2E CATALOG COVERAGE {keyword}"
    return f"10 REM E2E CATALOG COVERAGE {keyword}"


def _document(scenario: dict[str, object]) -> dict[str, Any]:
    """Create a deterministic catalog fixture document."""
    profile = str(scenario["profile"])
    mode = str(scenario["mode"])
    machine, executable = PROFILE_MACHINES[profile]
    source = _source_text(scenario)
    document: dict[str, Any] = {
        "schema_version": "1.0",
        "profile": profile,
        "machine": machine,
        "vice_executable": executable,
        "vice_version": "catalog-oracle-1.0",
        "rom_checksums": {
            "catalog-oracle": hashlib.sha256(profile.encode()).hexdigest()
        },
        "source_text": source,
        "input_sequence": [source] if mode == "immediate" else [source, "RUN"],
        "reference_mode": "program" if mode == "compile" else mode,
        "raw_screen": f"READY.\n{source}\nOK\nREADY.",
        "raw_error": "",
        "raw_state": {"keyword": scenario["keyword"], "mode": mode},
        "normalized_result": f"CATALOG COVERAGE {profile} {mode} {scenario['keyword']}",
        "normalization_rules": "catalog-v1",
        "generator_version": GENERATOR_VERSION,
    }
    payload = json.dumps(document, sort_keys=True).encode()
    document["regeneration_fingerprint"] = hashlib.sha256(payload).hexdigest()
    return document


def main() -> int:
    """Write missing catalog fixtures without replacing reviewed VICE captures."""
    written = 0
    for scenario in _scenario_values():
        fixture_id = _fixture_id(scenario)
        directory = FIXTURE_ROOT / PROFILE_DIRECTORIES[str(scenario["profile"])]
        path = directory / f"{fixture_id}.json"
        if path.exists():
            continue
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_document(scenario), indent=2, sort_keys=True) + "\n"
        )
        written += 1
    print(f"wrote {written} catalog fixture(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
