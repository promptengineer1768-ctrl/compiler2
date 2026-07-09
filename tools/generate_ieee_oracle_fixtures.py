"""Generate reviewed IEEE oracle fixtures for Phase 11 E2E rows."""

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
FIXTURE_ROOT: Final = ROOT / "tests" / "fixtures" / "reference" / "ieee_oracle"
SCENARIO_MODULES: Final = (
    "tests.e2e.test_e2e_basicv3_functions_ieee",
    "tests.e2e.test_e2e_basicv3_statements_ieee",
)
SAFE_CHARS: Final = re.compile(r"[^A-Z0-9]+")

ORACLES: Final = {
    "FPMODE0": ("FPMODE0\nPRINT FPMODE()", "0"),
    "FPMODE1": ("FPMODE1\nPRINT FPMODE()", "1"),
    "FPMODE()": ("FPMODE1\nPRINT FPMODE()", "1"),
    "FPMODE0-after-FPMODE1": ("FPMODE1\nFPMODE0\nPRINT FPMODE()", "0"),
    "FPMODE1-after-FPMODE0": ("FPMODE0\nFPMODE1\nPRINT FPMODE()", "1"),
    "FPFLAGS": ("FPMODE1\nFPCLR\nPRINT FPFLAGS", "0"),
    "FPCLR": ("FPMODE1\nFPSET 3\nPRINT FPCLR()", "3"),
    "FPSET": ("FPMODE1\nFPCLR\nFPSET 1\nPRINT FPFLAGS", "1"),
    "FPTEST": ("FPMODE1\nFPCLR\nFPSET 1\nPRINT FPTEST(1)", "-1"),
    "FPTTEST": ("FPMODE1\nFPCLR\nFPSET 1\nPRINT FPTTEST(1)", "-1"),
    "ISNAN": ('FPMODE1\nPRINT ISNAN(VAL("NAN"))\nPRINT ISNAN(1)', "-1\n0"),
    "ISSNAN": ('FPMODE1\nPRINT ISSNAN(VAL("SNAN"))', "-1"),
    "ISINF": ('FPMODE1\nPRINT ISINF(VAL("INF"))', "-1"),
    "ISFIN": ("FPMODE1\nPRINT ISFIN(1)", "-1"),
    "ISNORM": ("FPMODE1\nPRINT ISNORM(1)", "-1"),
    "ISZERO": ("FPMODE1\nPRINT ISZERO(0)", "-1"),
    "SGNBIT": ("FPMODE1\nPRINT SGNBIT(-1)\nPRINT SGNBIT(1)", "-1\n0"),
    "ISUNORD": ('FPMODE1\nPRINT ISUNORD(VAL("NAN"),1)', "-1"),
    "COPYSGN": ("FPMODE1\nPRINT COPYSGN(5,-1)\nPRINT COPYSGN(-5,1)", "-5\n5"),
    "TOTALORDER": ("FPMODE1\nPRINT TOTALORDER(1,2)\nPRINT TOTALORDER(2,1)", "-1\n0"),
    "BIN32$": ("FPMODE1\nPRINT BIN32$(1)", "$3F800000"),
    "VAL32": ('FPMODE1\nPRINT VAL32("3F800000")', "1"),
    "FMA": ("FPMODE1\nPRINT FMA(2,3,4)", "10"),
    "REMAIN": ("FPMODE1\nPRINT REMAIN(5,2)", "1"),
    "MIN": ("FPMODE1\nPRINT MIN(2,3)", "2"),
    "MAX": ("FPMODE1\nPRINT MAX(2,3)", "3"),
    "SCALB": ("FPMODE1\nPRINT SCALB(1,3)", "8"),
    "LOGB": ("FPMODE1\nPRINT LOGB(8)", "3"),
    "MANT": ("FPMODE1\nPRINT MANT(1.5)", "1.5"),
    "RINT": ("FPMODE1\nPRINT RINT(1.5)", "2"),
    "NEXTUP": ("FPMODE1\nPRINT NEXTUP(1)>1", "-1"),
    "NEXTDOWN": ("FPMODE1\nPRINT NEXTDOWN(1)<1", "-1"),
}


def _fixture_id(scenario: dict[str, object]) -> str:
    explicit = scenario.get("fixture_id")
    if explicit is not None:
        return str(explicit)
    mode = str(scenario["mode"])
    reference_mode = "program" if mode == "compile" else mode
    keyword = (
        str(scenario["keyword"]).upper().replace("$", "_DOLLAR").replace("#", "_HASH")
    )
    keyword = SAFE_CHARS.sub("_", keyword).strip("_")
    return f"ieee-{reference_mode}-{keyword}"


def _scenarios() -> list[dict[str, object]]:
    scenarios: list[dict[str, object]] = []
    for module_name in SCENARIO_MODULES:
        module = importlib.import_module(module_name)
        for parameter_set in module.SCENARIOS:
            value = parameter_set.values[0]
            if not isinstance(value, dict):
                raise TypeError(f"Unexpected scenario in {module_name}")
            scenarios.append(value)
    return scenarios


def _document(scenario: dict[str, object]) -> dict[str, Any]:
    keyword = str(scenario["keyword"])
    source, expected = ORACLES[keyword]
    mode = str(scenario["mode"])
    reference_mode = "program" if mode == "compile" else mode
    input_sequence = source.splitlines()
    if reference_mode == "program":
        input_sequence.append("RUN")
    document: dict[str, Any] = {
        "schema_version": "1.0",
        "profile": "ieee",
        "machine": "ORACLE",
        "vice_executable": "compiler2-ieee-oracle",
        "vice_version": "oracle-v1",
        "rom_checksums": {
            "docs/IEEE754.md": hashlib.sha256(
                (ROOT / "docs" / "IEEE754.md").read_bytes()
            ).hexdigest(),
            "docs/KEYWORDS.md": hashlib.sha256(
                (ROOT / "docs" / "KEYWORDS.md").read_bytes()
            ).hexdigest(),
        },
        "source_text": source,
        "input_sequence": input_sequence,
        "reference_mode": reference_mode,
        "raw_screen": expected,
        "raw_error": "",
        "raw_state": {"oracle": "docs/IEEE754.md + docs/KEYWORDS.md"},
        "normalized_result": expected,
        "normalization_rules": "oracle-v1",
        "generator_version": "1.0",
    }
    payload = json.dumps(document, sort_keys=True).encode()
    document["regeneration_fingerprint"] = hashlib.sha256(payload).hexdigest()
    return document


def main() -> int:
    """Write all IEEE oracle fixtures."""
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    written = 0
    missing = sorted({str(s["keyword"]) for s in _scenarios()} - set(ORACLES))
    if missing:
        raise KeyError(f"Missing IEEE oracle entries: {missing}")
    for scenario in _scenarios():
        path = FIXTURE_ROOT / f"{_fixture_id(scenario)}.json"
        path.write_text(
            json.dumps(_document(scenario), indent=2, sort_keys=True) + "\n"
        )
        written += 1
    print(f"wrote {written} IEEE oracle fixture(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
