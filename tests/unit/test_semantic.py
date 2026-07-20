"""Unit tests for geoasm token-stream semantic policy."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest

GEORAM_WINDOW = 0xDE00
GEORAM_PAGE = 0xDFFE
GEORAM_BLOCK = 0xDFFF

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None

# Keep test input above the linked image (currently ending below $C900).
SOURCE_ADDR = 0xC900
DIALECT_BASICV2 = 0
DIALECT_BASICV35 = 1
NUMERIC_FLOAT = 0
NUMERIC_INT_FAST = 1
ERR_NEXT_WITHOUT_FOR = 0x0A
ERR_SYNTAX = 0x0B

TOKEN_FOR = 129
TOKEN_NEXT = 130
TOKEN_PRINT = 153
TOKEN_RUN = 138
TOKEN_CLR = 156
TOKEN_NEW = 162
TOKEN_VERIFY = 149
TOKEN_LOAD = 147
TOKEN_SAVE = 148
TOKEN_CONT = 154
TOKEN_LIST = 155
TOKEN_DO = 200
TOKEN_LOOP = 201
TOKEN_WHILE = 253
TOKEN_BASIC3_5 = 212
TOKEN_BASIC2 = 212
TOKEN_COMPILE = 206
TOKEN_FPMODE0 = 254
TOKEN_FPMODE1 = 254


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _routine_record(symbol: str) -> dict[str, Any]:
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    return cast(dict[str, Any], data["routines"][symbol])


def _symbol_address(symbol: str) -> int:
    for line in (
        (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8").splitlines()
    ):
        fields = line.split()
        if len(fields) >= 3 and fields[2] == f".{symbol}":
            return int(fields[1], 16)
    raw = _routine_record(symbol)["address"]
    assert isinstance(raw, str) and raw.startswith("$")
    return int(raw[1:], 16)


def _new_emu(source: bytes = b"") -> C64Emu6502:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    georam_path = ROOT / "build" / "georam.bin"
    if not georam_path.exists():
        pytest.fail("build/georam.bin not found. Run build.ps1 first.")
    image = georam_path.read_bytes()
    assert image[:2] == b"\x00\xde"
    emu.set_georam_enabled(True)
    backing_size = len(emu.export_georam())
    payload_bytes = image[2:]
    assert backing_size >= len(payload_bytes)
    emu.load_georam(payload_bytes + bytes(backing_size - len(payload_bytes)))
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    emu.execute(_symbol_address("ctx_init"), 50_000)
    emu.write_mem_range(SOURCE_ADDR, source + b"\x00")
    return emu


def _carry_is_set(emu: C64Emu6502) -> bool:
    return (int(emu.get_state().p) & 0x01) != 0


def _call_source(emu: C64Emu6502, routine: str, cycles: int = 50_000) -> None:
    """Enter a geoRAM-paged semantic routine through the XY group gate.

    semantic_validate_line and semantic_classify_direct take X/Y as a source
    pointer and leave A free, so they are reached via the production id-in-A
    group gate which banks in the routine's page and preserves the callee carry.
    """
    record = _routine_record(routine)
    assert record.get("layer") == "georam", f"{routine} is not a geoRAM routine"
    routine_id = int(record["id"])
    assert routine_id < 0x100
    emu.set_a(routine_id & 0xFF)
    emu.set_x(SOURCE_ADDR & 0xFF)
    emu.set_y(SOURCE_ADDR >> 8)
    emu.execute(_symbol_address("georam_call_group_0_xy"), cycles)


def _run_paged(emu: C64Emu6502, routine: str, cycles: int = 5000) -> None:
    """Bank in the routine's geoRAM page and execute it at the $DE00 window.

    Routines that take A as an argument (or return A) cannot be entered through
    the id-in-A group gate, so the caller's A/X/Y are preserved while the
    routine's own block/page is selected via the real geoRAM registers.
    """
    record = _routine_record(routine)
    assert record.get("layer") == "georam", f"{routine} is not a geoRAM routine"
    assert int(record["offset"]) == 0
    saved = emu.get_state()
    emu.write_mem(GEORAM_BLOCK, int(record["block"]) & 0xFF)
    emu.write_mem(GEORAM_PAGE, int(record["page"]) & 0xFF)
    emu.set_a(saved.a)
    emu.set_x(saved.x)
    emu.set_y(saved.y)
    emu.execute(GEORAM_WINDOW, cycles)


def _generation(emu: C64Emu6502) -> int:
    address = _symbol_address("semantic_policy_generation")
    low = cast(int, emu.read_mem(address))
    high = cast(int, emu.read_mem(address + 1))
    return low | (high << 8)


@pytest.mark.unit
@pytest.mark.local
class TestSemantic:
    """Semantic policy behavior executed through linked assembly bytes."""

    @pytest.mark.callable_coverage("semantic_set_dialect", executor="execute")
    @pytest.mark.callable_coverage("semantic_check_for_dialect", executor="execute")
    def test_dialect_query_set_and_generation_invalidation(self) -> None:
        emu = _new_emu()
        _run_paged(emu, "semantic_check_for_dialect")
        assert emu.get_state().a == DIALECT_BASICV2
        assert not _carry_is_set(emu)
        initial = _generation(emu)

        emu.set_a(DIALECT_BASICV35)
        _run_paged(emu, "semantic_set_dialect")
        assert not _carry_is_set(emu)
        assert _generation(emu) == initial + 1
        _run_paged(emu, "semantic_check_for_dialect")
        assert emu.get_state().a == DIALECT_BASICV35

        emu.set_a(DIALECT_BASICV35)
        _run_paged(emu, "semantic_set_dialect")
        assert _generation(emu) == initial + 1

        emu.set_a(0xFF)
        _run_paged(emu, "semantic_set_dialect")
        assert _carry_is_set(emu)
        assert _generation(emu) == initial + 1

    @pytest.mark.callable_coverage("semantic_validate_dialect", executor="execute")
    @pytest.mark.callable_coverage("semantic_set_dialect", executor="execute")
    def test_keyword_token_is_checked_against_current_dialect(self) -> None:
        emu = _new_emu()
        for token in (TOKEN_PRINT, TOKEN_FOR):
            emu.set_a(token)
            _run_paged(emu, "semantic_validate_dialect")
            assert not _carry_is_set(emu)
            assert emu.get_state().a == token

        emu.set_a(TOKEN_WHILE)
        _run_paged(emu, "semantic_validate_dialect")
        assert _carry_is_set(emu)

        emu.set_a(DIALECT_BASICV35)
        _run_paged(emu, "semantic_set_dialect")
        emu.set_a(TOKEN_WHILE)
        _run_paged(emu, "semantic_validate_dialect")
        assert not _carry_is_set(emu)

        emu.set_a(0xFF)
        _run_paged(emu, "semantic_validate_dialect")
        assert _carry_is_set(emu)

    @pytest.mark.parametrize(
        "token",
        [
            TOKEN_NEW,
            TOKEN_RUN,
            TOKEN_CONT,
            TOKEN_CLR,
            TOKEN_LIST,
            TOKEN_COMPILE,
            TOKEN_LOAD,
            TOKEN_SAVE,
            TOKEN_VERIFY,
            TOKEN_BASIC2,
            TOKEN_BASIC3_5,
        ],
    )
    @pytest.mark.callable_coverage("semantic_classify_direct", executor="execute")
    def test_direct_only_statement_tokens_are_rejected_in_programs(
        self, token: int
    ) -> None:
        emu = _new_emu()
        emu.set_a(token)
        _run_paged(emu, "semantic_classify_direct")
        assert _carry_is_set(emu)
        assert emu.get_state().a == token

    @pytest.mark.callable_coverage("semantic_classify_direct", executor="execute")
    @pytest.mark.parametrize("token", [TOKEN_PRINT, TOKEN_FOR, TOKEN_NEXT])
    def test_program_statement_tokens_are_not_direct_only(self, token: int) -> None:
        emu = _new_emu()
        emu.set_a(token)
        _run_paged(emu, "semantic_classify_direct")
        assert not _carry_is_set(emu)

    @pytest.mark.parametrize(
        ("source", "error"),
        [
            (b"FOR I=1 TO 2:NEXT", 0),
            # Bare NEXT is allowed at line level so multi-line FOR works;
            # unmatched NEXT is a runtime concern, not a frontend reject.
            (b"NEXT", 0),
            (b"FOR I=1 TO 2", 0),
        ],
    )
    def test_line_validation_checks_control_structure(
        self, source: bytes, error: int
    ) -> None:
        emu = _new_emu(source)
        _call_source(emu, "semantic_validate_line")
        assert _carry_is_set(emu) is (error != 0)
        assert emu.get_state().a == error

    @pytest.mark.callable_coverage("semantic_validate_line", executor="execute")
    @pytest.mark.callable_coverage("semantic_set_dialect", executor="execute")
    def test_line_validation_applies_dialect_without_publishing_state(self) -> None:
        emu = _new_emu(b"DO:LOOP")
        _call_source(emu, "semantic_validate_line")
        assert _carry_is_set(emu)
        assert emu.get_state().a == ERR_SYNTAX

        emu.set_a(DIALECT_BASICV35)
        _run_paged(emu, "semantic_set_dialect")
        generation = _generation(emu)
        _call_source(emu, "semantic_validate_line")
        assert not _carry_is_set(emu)
        assert emu.get_state().a == 0
        assert _generation(emu) == generation

    def test_line_validation_rejects_direct_only_command_in_program_line(
        self,
    ) -> None:
        emu = _new_emu(b"10 RUN")
        _call_source(emu, "semantic_validate_line")
        assert _carry_is_set(emu)

        emu = _new_emu(b"RUN")
        _call_source(emu, "semantic_validate_line")
        assert not _carry_is_set(emu)

    @pytest.mark.callable_coverage("semantic_set_numeric_mode", executor="execute")
    @pytest.mark.callable_coverage("semantic_get_numeric_mode", executor="execute")
    def test_numeric_mode_round_trips_and_invalidates_generation(self) -> None:
        emu = _new_emu()
        initial = _generation(emu)
        emu.set_a(NUMERIC_INT_FAST)
        _run_paged(emu, "semantic_set_numeric_mode")
        assert not _carry_is_set(emu)
        assert _generation(emu) == initial + 1
        _run_paged(emu, "semantic_get_numeric_mode")
        assert emu.get_state().a == NUMERIC_INT_FAST

        emu.set_a(NUMERIC_INT_FAST)
        _run_paged(emu, "semantic_set_numeric_mode")
        assert _generation(emu) == initial + 1

        emu.set_a(2)
        _run_paged(emu, "semantic_set_numeric_mode")
        assert _carry_is_set(emu)
        assert _generation(emu) == initial + 1
