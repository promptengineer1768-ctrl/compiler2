"""Unit tests for geoasm optimizer predicates and cached summaries."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None

DESCRIPTOR_ADDR = 0xC900

FOR_REQUIRED = 0x1F
DO_SIMPLE = 0x20
DO_BARE = 0x40

COND_WHILE = 0
COND_UNTIL = 1
BRANCH_BNE = 0xD0
BRANCH_BEQ = 0xF0


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _symbol_address(symbol: str) -> int:
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(
        rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}$",
        labels,
        re.MULTILINE,
    )
    if match:
        return int(match.group(1), 16)
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    raw = data["routines"][symbol]["address"]
    assert raw.startswith("$")
    return int(raw[1:], 16)


def _new_emu(descriptor: bytes = b"\x00\x00\x00\x00") -> C64Emu6502:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    # Optimizer coverage must observe linked production bytes without the
    # compatibility post-processing used by older unit suites.
    setattr(emu, "_compiler2_real_bytes_only", True)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    emu.write_mem_range(DESCRIPTOR_ADDR, descriptor)
    emu.set_x(DESCRIPTOR_ADDR & 0xFF)
    emu.set_y(DESCRIPTOR_ADDR >> 8)
    return emu


def _carry_is_set(emu: C64Emu6502) -> bool:
    return (int(emu.get_state().p) & 0x01) != 0


def _set_ir(emu: C64Emu6502, records: bytes) -> None:
    """Install typed IR records directly at the production analysis boundary."""
    assert len(records) % 4 == 0
    emu.write_mem_range(_symbol_address("ir_buffer"), records)
    emu.write_mem(_symbol_address("ir_buffer_len"), len(records))


@pytest.mark.unit
@pytest.mark.local
class TestOptimizer:
    """Optimizer behavior tests."""

    def test_for_fast_path_eligibility_and_barriers(self) -> None:
        emu = _new_emu(bytes([FOR_REQUIRED, 0, 0, 1]))
        emu.execute(_symbol_address("opt_eligible_for_for_fast"), 1000)
        assert _carry_is_set(emu)

        for descriptor in (
            bytes([FOR_REQUIRED & ~0x04, 0, 0, 1]),
            bytes([FOR_REQUIRED, 0x01, 0, 1]),
            bytes([FOR_REQUIRED, 0, 0x01, 1]),
        ):
            emu = _new_emu(descriptor)
            emu.execute(_symbol_address("opt_eligible_for_for_fast"), 1000)
            assert not _carry_is_set(emu)

    def test_do_fast_path_and_branch_polarity(self) -> None:
        for flags in (DO_SIMPLE, DO_BARE):
            emu = _new_emu(bytes([flags, 0, 0, 1]))
            emu.execute(_symbol_address("opt_eligible_for_do_fast"), 1000)
            assert _carry_is_set(emu)

        emu = _new_emu(bytes([DO_SIMPLE, 0x02, 0, 1]))
        emu.execute(_symbol_address("opt_eligible_for_do_fast"), 1000)
        assert not _carry_is_set(emu)

        emu = _new_emu(bytes([DO_SIMPLE | DO_BARE, 0, 0, 1]))
        emu.execute(_symbol_address("opt_eligible_for_do_fast"), 1000)
        assert not _carry_is_set(emu)

        emu.set_a(COND_WHILE)
        emu.execute(_symbol_address("opt_select_branch_polarity"), 1000)
        assert emu.get_state().a == BRANCH_BNE
        emu.set_a(COND_UNTIL)
        emu.execute(_symbol_address("opt_select_branch_polarity"), 1000)
        assert emu.get_state().a == BRANCH_BEQ

        emu.set_a(2)
        emu.execute(_symbol_address("opt_select_branch_polarity"), 1000)
        assert _carry_is_set(emu)

    def test_cached_effect_summary_invalidation_alias_and_dirty(self) -> None:
        emu = _new_emu(bytes([FOR_REQUIRED, 0x24, 0x80, 7]))
        emu.execute(_symbol_address("opt_check_invalidation"), 1000)
        assert emu.get_state().a == 0x24

        emu.set_x(DESCRIPTOR_ADDR & 0xFF)
        emu.set_y(DESCRIPTOR_ADDR >> 8)
        emu.execute(_symbol_address("opt_check_aliasing"), 1000)
        assert _carry_is_set(emu)

        emu.set_a(0x04)
        emu.execute(_symbol_address("opt_propagate_dirty"), 1000)
        assert emu.get_state().a == 0x04
        emu.set_a(0x20)
        emu.execute(_symbol_address("opt_propagate_dirty"), 1000)
        assert emu.get_state().a == 0x24

    def test_summary_generation_cache_and_pass_driver(self) -> None:
        emu = _new_emu()
        _set_ir(
            emu,
            bytes(
                [
                    0x01,
                    0,
                    0x04,
                    0x20,
                    0x07,
                    FOR_REQUIRED,
                    0x02,
                    0x40,
                    0x00,
                    0,
                    0,
                    0,
                ]
            ),
        )
        emu.set_x(0x34)
        emu.set_y(0x12)
        emu.execute(_symbol_address("opt_build_effect_summaries"), 1000)
        state = emu.get_state()
        summary = _symbol_address("opt_summary_table")
        assert state.x == (summary & 0xFF)
        assert state.y == (summary >> 8)
        emu.set_x(summary & 0xFF)
        emu.set_y(summary >> 8)
        emu.execute(_symbol_address("opt_check_invalidation"), 1000)
        assert emu.get_state().a == 0x06
        emu.set_x(summary & 0xFF)
        emu.set_y(summary >> 8)
        emu.execute(_symbol_address("opt_check_aliasing"), 1000)
        assert _carry_is_set(emu)

        # A same-generation request must consume the cache, not changed IR.
        _set_ir(emu, bytes([0x07, 0, 0xFF, 0xFF, 0, 0, 0, 0]))
        emu.set_x(0x34)
        emu.set_y(0x12)
        emu.execute(_symbol_address("opt_build_effect_summaries"), 1000)
        emu.set_x(summary & 0xFF)
        emu.set_y(summary >> 8)
        emu.execute(_symbol_address("opt_check_invalidation"), 1000)
        assert emu.get_state().a == 0x06

        emu.set_x(0x35)
        emu.set_y(0x12)
        emu.execute(_symbol_address("opt_run_passes"), 1000)
        assert not _carry_is_set(emu)

    def test_summary_capacity_failure_is_not_published(self) -> None:
        records = b"".join(bytes([0x07, FOR_REQUIRED, 0, 0]) for _ in range(5))
        emu = _new_emu()
        _set_ir(emu, records)
        emu.set_x(1)
        emu.set_y(0)
        emu.execute(_symbol_address("opt_build_effect_summaries"), 2000)
        assert _carry_is_set(emu)

    def test_stop_poll_uses_summary_metadata(self) -> None:
        for meta, expected in ((0, False), (1, True)):
            emu = _new_emu(bytes([FOR_REQUIRED, 0, 0, meta]))
            emu.execute(_symbol_address("opt_check_stop_poll"), 1000)
            assert _carry_is_set(emu) is expected
