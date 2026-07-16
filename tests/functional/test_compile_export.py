"""Functional contracts for the source-free COMPILE export.

These tests deliberately inspect the product of the real production path.  A
missing ``COMPILED.PRG`` is a failure: record validators are unit-testable, but
they are not a substitute for a linker and an exported program.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
PRG = ROOT / "build" / "COMPILED.PRG"
POLICY = ROOT / "manifests" / "linker_policy.json"
EXPORT_ASM = ROOT / "src" / "geoasm" / "compile_export.asm"
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None

COMPILE_TOKEN = 206
DIRECT_RECORD_ADDR = 0xC000
DIRECT_NAME_ADDR = 0xC100
READ_HELPER_ADDR = 0xC700
EXPECTED_STUB = bytes(
    (
        0x0B,
        0x08,  # next BASIC line: $080B
        0xEA,
        0x07,  # line 2026
        0x9E,  # SYS
        *b"2061",
        0,
        0,
        0,
    )
)


def _direct_command_emulator() -> tuple[Any, int]:
    """Load production artifacts and select the direct-command GeoRAM page."""
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    dll = next(
        (
            path
            for path in (TOOLS_ROOT / "emu6502.dll", TOOLS_ROOT / "msys-emu6502.dll")
            if path.exists()
        ),
        None,
    )
    if dll is None:
        pytest.skip("Emulator DLL not found in tools folder.")

    emulator = C64Emu6502(lib_path=dll)
    compiler = (ROOT / "build" / "compiler.bin").read_bytes()
    load_address = compiler[0] | (compiler[1] << 8)
    emulator.write_mem_range(load_address, compiler[2:])
    georam = (ROOT / "build" / "georam.bin").read_bytes()
    georam_payload = georam[2:] if georam[:2] == b"\x00\xde" else georam
    assert georam_payload
    directory = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    command = directory["routines"]["direct_execute_command"]
    assert command["layer"] == "georam"
    emulator.set_georam_enabled(True)
    emulator.load_georam(georam_payload)
    emulator.write_mem(0xDFFF, int(command["block"]))
    emulator.write_mem(0xDFFE, int(command["page"]))
    emulator.write_mem(0x0000, 0x2F)
    emulator.write_mem(0x0001, 0x35)
    emulator._compiler2_real_bytes_only = True
    return emulator, int(command["address"].removeprefix("$"), 16)


def _cpu_read(emulator: Any, address: int) -> int:
    """Read a CPU-visible byte through a tiny real-byte helper."""
    emulator.write_mem_range(
        READ_HELPER_ADDR,
        bytes((0xAD, address & 0xFF, address >> 8, 0x60)),
    )
    emulator.execute(READ_HELPER_ADDR, 20)
    return int(emulator.get_state().a)


def _export() -> bytes:
    """Return the production COMPILE artifact, failing when none was emitted."""
    assert PRG.is_file(), (
        "the production COMPILE path did not emit build/COMPILED.PRG; "
        "record validation alone is not a COMPILE implementation"
    )
    payload = PRG.read_bytes()
    assert len(payload) >= 2 + len(EXPECTED_STUB) + 1
    return payload


@pytest.mark.functional
@pytest.mark.local
@pytest.mark.smoke
def test_compile_produces_canonical_stock_prg() -> None:
    """The real export has the stock load address and exact loader line."""
    payload = _export()
    assert payload[:2] == b"\x01\x08"
    assert payload[2 : 2 + len(EXPECTED_STUB)] == EXPECTED_STUB
    assert payload[2 + len(EXPECTED_STUB)] != 0, "native entry is empty"
    assert 0x0801 + len(payload) - 2 <= 0xD000


@pytest.mark.functional
@pytest.mark.local
def test_compile_export_is_source_free_and_not_development_image() -> None:
    """The artifact contains neither tokenized source nor installer messages."""
    payload = _export()
    upper = payload.upper()
    for forbidden in (
        b"GEORAM DETECTED",
        b"GEORAM NOT DETECTED",
        b"BASIC 3 COMPILER",
    ):
        assert forbidden not in upper

    # A second linked BASIC line would make LIST expose source beyond the stub.
    assert payload[2:14] == EXPECTED_STUB
    assert payload[2:14].count(b"\x9e") == 1


@pytest.mark.functional
@pytest.mark.local
def test_compile_token_has_a_real_export_dispatch_path() -> None:
    """The real direct COMPILE entry hands its plan to the export transaction."""
    emulator, command_entry = _direct_command_emulator()
    name = b"OUTPUT"
    plan = bytearray((COMPILE_TOKEN,))
    plan += bytes(
        (
            ord("C"),
            ord("P"),
            DIRECT_NAME_ADDR & 0xFF,
            DIRECT_NAME_ADDR >> 8,
            len(name),
            10,
            0,
        )
    )
    plan += b"ED\x0fEL\x01"
    plan += b"EB" + b"".join(
        bytes((word & 0xFF, word >> 8)) for word in (0x0801, 0x2000, 0x0200, 0x0801)
    )
    plan += bytes(
        (
            ord("E"),
            ord("W"),
            DIRECT_NAME_ADDR & 0xFF,
            DIRECT_NAME_ADDR >> 8,
            len(name),
            10,
            0,
            0x01,
            0x08,
            0x00,
            0x20,
        )
    )
    assert len(plan) == 1 + 7 + 3 + 3 + 10 + 11
    emulator.write_mem_range(DIRECT_NAME_ADDR, name)
    emulator.write_mem_range(DIRECT_RECORD_ADDR, bytes(plan))
    emulator.set_x(DIRECT_RECORD_ADDR & 0xFF)
    emulator.set_y(DIRECT_RECORD_ADDR >> 8)
    emulator.execute(command_entry, 80_000)

    assert not (int(emulator.get_state().p) & 1)
    # CP begins immediately after the command token and becomes EO only when
    # direct_execute_command reaches the production export transaction.
    assert _cpu_read(emulator, DIRECT_RECORD_ADDR + 1) == ord("E")
    assert _cpu_read(emulator, DIRECT_RECORD_ADDR + 2) == ord("O")


@pytest.mark.functional
@pytest.mark.local
def test_compile_export_contains_standalone_shell_contract() -> None:
    """The linked image carries the source-free shell's observable literals."""
    payload = _export()
    for literal in (b"2026 SYS2061\x8d", b"PRINT", b"CONT", b"LIST"):
        assert literal in payload


@pytest.mark.functional
@pytest.mark.local
def test_export_budget_policy_is_soft_edge_triggered_in_production() -> None:
    """Production export module implements soft 80/100 warnings, not hard reject."""
    source = EXPORT_ASM.read_text(encoding="utf-8")
    assert "export_apply_soft_budgets" in source or "EXPORT_STATE_GE_80" in source
    assert "EXCEEDS STOCK RAM" in source
    assert "NEAR STOCK LIMIT" in source
    # Must not hard-reject solely for image_end past $D000.
    assert "hard-fail only invalid ranges" in source.lower() or (
        "oversize" in source.lower() and "allowed" in source.lower()
    )
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    assert b"EXCEEDS STOCK RAM" in payload
    assert b"NEAR STOCK LIMIT" in payload


@pytest.mark.functional
@pytest.mark.local
def test_export_layout_profiles_stock_vs_developer_in_policy_and_binary() -> None:
    """Dual layouts are declared in linker policy and implemented in production."""
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    profiles = {row["name"]: row for row in policy["export_layout_profiles"]}
    assert profiles["stock_compatible"]["ce00"] == "free"
    assert profiles["developer"]["ce00"] == "reserved"
    assert profiles["stock_compatible"]["hot_pages"] == "disposable"
    assert profiles["developer"]["hot_pages"] == "disposable"
    budget = policy["export_stock_budget"]
    assert budget["hard_reject_oversize"] is False
    assert budget["edge_triggered"] is True
    assert budget["image_base"] == 0x0801
    assert budget["image_end_exclusive"] == 0xD000
    assert budget["near_limit_end_exclusive"] == 0xA800

    source = EXPORT_ASM.read_text(encoding="utf-8")
    assert "EXPORT_LAYOUT_STOCK" in source
    assert "EXPORT_LAYOUT_DEVELOPER" in source
    assert "EXPORT_FLAG_CE00_RESERVED" in source
    # Hot pages must not be permanent reservations.
    assert "never permanent" in source.lower() or "Hot pages" in source

    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    for symbol in (
        "export_layout_profile",
        "export_layout_flags",
        "export_budget_state",
        "export_check_budgets",
        "export_compile_command",
    ):
        assert re.search(
            rf"^al\s+[0-9A-Fa-f]{{6}}\s+\.{symbol}$", labels, re.MULTILINE
        ), symbol
