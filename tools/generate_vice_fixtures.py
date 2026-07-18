"""Generate immutable stock BASIC semantic observations with VICE Next."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from vice_harness import MACHINES, VICE_ROOT, ViceMCP, ViceMachine, running_vice
from e2e_source_catalog import stock_source_case

ROOT: Final = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE_ROOT: Final = ROOT / "tests" / "fixtures" / "reference"
DEBUG_ROOT: Final = ROOT / "debug" / "vice_reference_prg"
SCHEMA_VERSION: Final = "1.0"
GENERATOR_VERSION: Final = "1.0"


@dataclass(frozen=True)
class FixtureCase:
    """One source program to observe on a stock BASIC interpreter."""

    case_id: str
    profile: str
    reference_mode: str
    source_lines: tuple[str, ...]
    interactive_input: tuple[str, ...] = ()


CASES: Final = (
    FixtureCase("basicv2-immediate-SGN", "basicv2", "immediate", ("PRINT SGN(-2)",)),
    FixtureCase("basicv2-program-ASC", "basicv2", "program", ('10 PRINT ASC("A")',)),
    FixtureCase(
        "basicv2-program-SPC", "basicv2", "program", ('10 PRINT "A";SPC(2);"B"',)
    ),
    FixtureCase("basicv2-immediate-PRINT", "basicv2", "immediate", ('PRINT "OK"',)),
    FixtureCase(
        "basicv2-program-FOR",
        "basicv2",
        "program",
        ("10 FOR I=1 TO 3:PRINT I:NEXT",),
    ),
    FixtureCase(
        "basicv2-program-GOTO",
        "basicv2",
        "program",
        ("10 GOTO 30", '20 PRINT "BAD"', '30 PRINT "OK"'),
    ),
    FixtureCase("basicv35-immediate-DO", "basicv35", "immediate", ("DO:EXIT:LOOP",)),
    FixtureCase(
        "basicv35-program-LOOP",
        "basicv35",
        "program",
        ("10 I=0:DO:I=I+1:PRINT I:LOOP WHILE I<3",),
    ),
    FixtureCase(
        "basicv35-program-EXIT_DO",
        "basicv35",
        "program",
        ('10 DO:PRINT "OK":EXIT:LOOP',),
    ),
    FixtureCase(
        "basicv35-immediate-BASIC3_5", "basicv35", "immediate", ('PRINT "3.5"',)
    ),
    FixtureCase(
        "basicv35-program-WHILE",
        "basicv35",
        "program",
        ("10 I=0:DO WHILE I<2:I=I+1:PRINT I:LOOP",),
    ),
    FixtureCase(
        "basicv35-program-UNTIL",
        "basicv35",
        "program",
        ("10 I=0:DO:I=I+1:PRINT I:LOOP UNTIL I=2",),
    ),
)
SCENARIO_MODULES: Final = (
    "tests.e2e.test_e2e_basicv2_functions",
    "tests.e2e.test_e2e_basicv2_statements",
    "tests.e2e.test_e2e_basicv35_functions",
    "tests.e2e.test_e2e_basicv35_statements",
)


def normalize_screen(screen: str, source_lines: tuple[str, ...]) -> str:
    """Remove blank rows, echoed input, banners, and READY prompts."""
    keep_numbered_echoes = any(line.strip().upper() == "LIST" for line in source_lines)
    echoes = {
        line.strip().upper()
        for line in source_lines
        if not (keep_numbered_echoes and re.match(r"^\d+\s+", line.strip()))
    } | {"RUN"}
    kept = []
    for line in screen.splitlines():
        normalized = re.sub(r"\s+", " ", line.strip().upper())
        if not normalized or normalized in echoes:
            continue
        if normalized.startswith(("**** COMMODORE", "COMMODORE BASIC")):
            continue
        if normalized == "3-PLUS-1 ON KEY F1":
            continue
        if normalized == "READY." or normalized.endswith(" BYTES FREE"):
            continue
        kept.append(normalized)
    return "\n".join(kept)


def rom_checksums(machine: ViceMachine) -> dict[str, str]:
    """Return SHA-256 identities for every ROM used by the selected machine."""
    directory = VICE_ROOT / machine.rom_directory
    return {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in machine.rom_files
    }


def _ping_metadata(result: object) -> dict[str, object]:
    """Decode metadata returned by ``vice.ping``."""
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list) and content:
            item = content[0]
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                decoded = json.loads(item["text"])
                if isinstance(decoded, dict):
                    return decoded
    raise TypeError(f"Unexpected VICE ping response: {result!r}")


def _petcat_version(profile: str) -> str:
    """Return the petcat BASIC dialect option for one profile."""
    return "2" if profile == "basicv2" else "3"


def _petcat_executable() -> Path:
    """Return the explicitly configured VICE Next PETCAT executable.

    The instrumented runtime supplies emulators but does not bundle PETCAT.
    Fixture generation therefore requires an explicit, auditable tool path
    instead of probing the retired runtime or host PATH.

    Returns:
        Existing PETCAT executable path.

    Raises:
        FileNotFoundError: If ``VICE_PETCAT`` is unset or names no file.
    """
    configured = os.environ.get("VICE_PETCAT")
    if not configured:
        raise FileNotFoundError(
            "VICE_PETCAT must name the PETCAT executable for fixture generation"
        )
    executable = Path(configured)
    if not executable.is_file():
        raise FileNotFoundError(f"configured VICE_PETCAT does not exist: {executable}")
    return executable


def _source_for_autostart(case: FixtureCase) -> tuple[str, ...]:
    """Return numbered BASIC source lines suitable for PRG autostart."""
    if case.reference_mode == "program":
        return tuple(_petcat_source_line(line) for line in case.source_lines)
    return tuple(
        f"{10 * (index + 1)} {_petcat_source_line(line)}"
        for index, line in enumerate(case.source_lines)
    )


def _petcat_source_line(line: str) -> str:
    """Lowercase BASIC outside quotes for petcat tokenization."""
    lowered = []
    in_quote = False
    for char in line:
        if char == '"':
            in_quote = not in_quote
            lowered.append(char)
        elif in_quote:
            lowered.append(char)
        else:
            lowered.append(char.lower())
    return "".join(lowered)


def _write_reference_prg(case: FixtureCase) -> Path:
    """Tokenize a fixture case into a temporary BASIC PRG."""
    DEBUG_ROOT.mkdir(parents=True, exist_ok=True)
    source_path = DEBUG_ROOT / f"{case.case_id}.bas"
    prg_path = DEBUG_ROOT / f"{case.case_id}.prg"
    petcat = _petcat_executable()
    source = "\n".join(_source_for_autostart(case)) + "\n"
    source_path.write_text(source, encoding="ascii")
    subprocess.run(
        [
            str(petcat),
            f"-w{_petcat_version(case.profile)}",
            "-f",
            "-o",
            str(prg_path),
            "--",
            str(source_path),
        ],
        check=True,
        cwd=petcat.parent,
    )
    return prg_path


def capture_case(case: FixtureCase, *, port: int) -> dict[str, object]:
    """Run one case in a fresh emulator and construct its fixture document."""
    machine = MACHINES[case.profile]
    commands = (
        list(case.source_lines) + ["RUN"]
        if case.reference_mode == "program"
        else list(case.source_lines)
    )
    prg_path = _write_reference_prg(case)
    with running_vice(machine, port=port) as vice:
        metadata = _ping_metadata(vice.call("vice.ping"))
        vice.wait_for_ready_screen(machine, timeout=10.0, settle_reads=1)
        _attach_scratch_disk_if_needed(vice, case)
        if case.reference_mode == "immediate":
            screen = _capture_direct_commands(vice, machine, case)
        else:
            vice.autostart(prg_path, run=True)
            if case.interactive_input:
                time.sleep(1.0)
                for line in case.interactive_input:
                    vice.type_text(line.rstrip("\r\n") + "\n")
            screen = vice.wait_for_ready_screen(machine, timeout=30.0)
    normalized = normalize_screen(screen, case.source_lines)
    raw_state: dict[str, object] = {}
    if not normalized:
        raw_state["no_semantic_output"] = True
    document: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "profile": case.profile,
        "machine": machine.machine,
        "vice_executable": machine.executable,
        "vice_version": metadata["version"],
        "rom_checksums": rom_checksums(machine),
        "source_text": "\n".join(case.source_lines),
        "input_sequence": commands + list(case.interactive_input),
        "reference_mode": case.reference_mode,
        "raw_screen": screen,
        "raw_error": next(
            (line for line in normalized.splitlines() if " ERROR" in line), ""
        ),
        "raw_state": raw_state,
        "normalized_result": normalized,
        "normalization_rules": "screen-v1",
        "generator_version": GENERATOR_VERSION,
    }
    fingerprint_source = json.dumps(document, sort_keys=True).encode()
    document["regeneration_fingerprint"] = hashlib.sha256(
        fingerprint_source
    ).hexdigest()
    return document


def _capture_direct_commands(
    vice: ViceMCP, machine: ViceMachine, case: FixtureCase
) -> str:
    """Capture immediate-mode commands through the keyboard path."""
    last_screen = ""
    for command in case.source_lines:
        if re.match(r"^\d+\s+", command):
            vice.type_text(command.rstrip("\r\n") + "\n")
            vice.call("vice.execution.run", timeout=1.0)
            time.sleep(0.75)
            last_screen = vice.screen_text(machine)
            continue
        timeout = 90.0 if _uses_device_8(command) else 30.0
        last_screen = vice.submit_command(machine, command, timeout=timeout)
        for line in case.interactive_input:
            vice.type_text(line.rstrip("\r\n") + "\n")
    return last_screen


def _attach_scratch_disk_if_needed(vice: ViceMCP, case: FixtureCase) -> None:
    """Attach a writable D64 when the source touches device 8."""
    if not any(_uses_device_8(line) for line in case.source_lines):
        return
    source_disk = ROOT / "build" / "compiler.d64"
    if not source_disk.exists():
        return
    scratch = ROOT / "debug" / f"{case.case_id}.d64"
    scratch.parent.mkdir(exist_ok=True)
    shutil.copy(source_disk, scratch)
    vice.call("vice.disk.attach", {"unit": 8, "path": str(scratch)}, timeout=10.0)
    vice.call("vice.execution.run", timeout=1.0)
    time.sleep(0.5)


def _uses_device_8(line: str) -> bool:
    """Return whether a BASIC source line references disk device 8."""
    return ",8" in line.replace(" ", "").upper()


def write_fixture(case: FixtureCase, document: dict[str, object]) -> Path:
    """Write one deterministic fixture and return its path."""
    directory = FIXTURE_ROOT / (
        "c64_basicv2" if case.profile == "basicv2" else "plus4_basicv35"
    )
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{case.case_id}.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return path


def scenario_cases() -> tuple[FixtureCase, ...]:
    """Build capture cases from the Phase 11 stock scenario tables."""
    cases: list[FixtureCase] = []
    seen: set[str] = set()
    for module_name in SCENARIO_MODULES:
        module = importlib.import_module(module_name)
        for parameter_set in module.SCENARIOS:
            scenario = parameter_set.values[0]
            if not isinstance(scenario, dict):
                raise TypeError(f"Unexpected scenario value in {module_name}")
            source = stock_source_case(
                str(scenario["profile"]),
                str(scenario["keyword"]),
                str(scenario["mode"]),
            )
            if source is None:
                continue
            case_id = _scenario_fixture_id(scenario)
            if case_id in seen:
                continue
            seen.add(case_id)
            cases.append(
                FixtureCase(
                    case_id,
                    str(scenario["profile"]),
                    source.reference_mode,
                    source.source_lines,
                    source.interactive_input,
                )
            )
    return tuple(cases)


def _scenario_fixture_id(scenario: dict[str, object]) -> str:
    """Return the fixture id used by a Phase 11 scenario."""
    if scenario.get("fixture_id") is not None:
        return str(scenario["fixture_id"])
    profile = str(scenario["profile"])
    mode = str(scenario["mode"])
    reference_mode = "program" if mode == "compile" else mode
    keyword = (
        str(scenario["keyword"]).upper().replace("$", "_DOLLAR").replace("#", "_HASH")
    )
    keyword = re.sub(r"[^A-Z0-9]+", "_", keyword).strip("_")
    return f"{profile}-{reference_mode}-{keyword}"


def main() -> int:
    """Generate selected stock fixtures."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=sorted(MACHINES))
    parser.add_argument("--case")
    parser.add_argument("--port", type=int, default=6510)
    parser.add_argument(
        "--from-e2e-scenarios",
        action="store_true",
        help="capture cases derived from Phase 11 stock E2E scenario tables",
    )
    args = parser.parse_args()
    source_cases = scenario_cases() if args.from_e2e_scenarios else CASES
    selected = [
        case
        for case in source_cases
        if (args.profile is None or case.profile == args.profile)
        and (args.case is None or case.case_id == args.case)
    ]
    if not selected:
        parser.error("no fixture cases matched")
    for case in selected:
        path = write_fixture(case, capture_case(case, port=args.port))
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
