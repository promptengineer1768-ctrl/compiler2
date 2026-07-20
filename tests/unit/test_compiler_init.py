"""Unit tests for compiler init routines (compiler_init.asm).

Tests verify configuration, vector setup, and state machine entry.
"""

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
    pass


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _load_symbol_address(symbol_name: str) -> int:
    lbl_path = ROOT / "build" / "compiler.lbl"
    if lbl_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            lbl_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    dir_path = ROOT / "build" / "routine_directory.json"
    if dir_path.exists():
        try:
            with open(dir_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            routines = data.get("routines", {})
            if symbol_name in routines:
                addr_str = routines[symbol_name].get("address", "")
                if addr_str.startswith("$"):
                    return int(addr_str[1:], 16)
        except Exception:
            pass
    map_path = ROOT / "build" / "compiler.map"
    if not map_path.exists():
        pytest.fail("build/compiler.map not found. Run build.ps1 first.")
    pattern = rf"\b{symbol_name}\b\s+([0-9A-Fa-f]{{6}})"
    content = map_path.read_text(encoding="utf-8")
    match = re.search(pattern, content)
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found.")


def _new_emulator() -> C64Emu6502:
    """Load the linked production image into a fresh C64 emulator."""
    emu = C64Emu6502(lib_path=_dll_path())
    emu.set_rom_overlay_enabled(True)
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.set_georam_enabled(True)
    georam = (ROOT / "build" / "georam.bin").read_bytes()
    assert georam[:2] == b"\x00\xde"
    backing = len(emu.export_georam())
    assert backing >= len(georam) - 2
    emu.load_georam(georam[2:] + bytes(backing - (len(georam) - 2)))
    emu.execute(_load_symbol_address("ctx_init"), 10_000)
    return emu


def _run_xip(emu: C64Emu6502, routine: str) -> None:
    """Invoke an init page through the installed production geoRAM gate."""
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record = directory["routines"][routine]
    assert record["layer"] == "georam"
    routine_id = int(record["id"])
    assert 0 <= routine_id <= 0xFF
    emu.set_x(routine_id & 0xFF)
    emu.execute(_load_symbol_address("georam_call_group_0"), 500_000)


@pytest.mark.unit
@pytest.mark.local
class TestCompilerInit:
    """Compiler init tests."""

    def test_init_configuration(self) -> None:
        """compiler_init is linked as the non-returning system entry."""
        routines = json.loads(
            (ROOT / "manifests" / "routines.json").read_text(encoding="utf-8")
        )["routines"]
        contract = next(item for item in routines if item["name"] == "compiler_init")
        assert contract["return_kind"] == "non_returning"
        assert contract["layer"] == "geoasm"
        assert contract["xip_page"] == 46
        assert contract["calls"] == [
            "compiler_state_machine",
            "init_arenas",
            "init_editor",
            "compiler_vectors",
            "compiler_state_machine",
            "init_enter_main_loop",
        ]

    def test_clear_bss_uses_linker_defined_full_segment(self) -> None:
        """init_clear_bss clears every linked BSS byte and no adjacent byte."""
        emu = _new_emulator()
        start = _load_symbol_address("__BSS_RUN__")
        size = _load_symbol_address("__BSS_SIZE__")
        emu.write_mem(start - 1, 0x3C)
        emu.write_mem_range(start, bytes([0xA5]) * size)
        emu.write_mem(start + size, 0xC3)

        # Clearing BSS destroys a gate context by definition, so this cold
        # routine is executed from its real selected XIP bytes directly.  The
        # loader-facing compiler_bootstrap performs this operation pre-gate.
        emu.write_mem(0xDFFF, 0)
        emu.write_mem(0xDFFE, 47)
        emu.execute(0xDE00, 500_000)

        assert bytes(emu.read_mem(start + offset) for offset in range(size)) == bytes(
            size
        )
        assert emu.read_mem(start - 1) == 0x3C
        assert emu.read_mem(start + size) == 0xC3

    @pytest.mark.callable_coverage("init_editor", executor="execute")
    @pytest.mark.callable_coverage("georam_select", executor="execute")
    def test_init_editor_clears_the_separately_loaded_pinned_metadata(self) -> None:
        """Cold editor init clears RAM_HIGH rw state without touching HIBASIC code."""
        emu = _new_emulator()
        start = _load_symbol_address("__EDITOR_PINNED_LOAD__")
        size = _load_symbol_address("__EDITOR_PINNED_SIZE__")
        # $E000-1 is $DFFF, the geoRAM block register rather than ordinary
        # RAM.  Establish it through the production selection gate so the
        # context stack owns the selection it must restore; a raw emulator
        # write would intentionally bypass that contract.
        emu.set_x(0x3C)
        emu.set_a(0x2D)
        emu.execute(_load_symbol_address("georam_select"), 10_000)
        emu.write_mem_range(start, bytes([0xA5]) * size)
        # First executable HIBASIC byte, immediately after the writable
        # EDITOR_PINNED extent.  This is the genuine adjacent-memory guard.
        emu.write_mem(start + size, 0xC3)

        _run_xip(emu, "init_editor")

        assert bytes(emu.read_mem(start + offset) for offset in range(size)) == bytes(
            size
        )
        assert emu.read_mem(0xDFFF) == 0x3C
        assert emu.read_mem(0xDFFE) == 0x2D
        assert emu.read_mem(start + size) == 0xC3

    @pytest.mark.callable_coverage("init_arenas", executor="execute")
    @pytest.mark.callable_coverage("arena_handle_valid", executor="execute")
    def test_init_arenas_constructs_the_real_typed_directory(self) -> None:
        """init_arenas delegates to the production arena constructor."""
        emu = _new_emulator()
        _run_xip(emu, "init_arenas")
        state = emu.get_state()
        assert not (int(state.p) & 0x01)
        assert emu.read_mem(_load_symbol_address("init_arena_state")) == 1

        for arena_id in range(1, 10):
            emu.set_x(arena_id)
            emu.set_y(1)
            emu.execute(_load_symbol_address("arena_handle_valid"), 10_000)
            assert not (int(emu.get_state().p) & 0x01)


@pytest.mark.unit
@pytest.mark.local
class TestCompilerVectors:
    """Vector setup tests."""

    @pytest.mark.callable_coverage("irq_entry", executor="execute_rts")
    def test_setup_vectors_installs_irq_and_nmi(self) -> None:
        """compiler_vectors saves priors and installs irq_entry/nmi_entry."""
        emu = _new_emulator()
        irq_entry = _load_symbol_address("irq_entry")
        irq_kernal_entry = _load_symbol_address("irq_kernal_entry")
        nmi_entry = _load_symbol_address("nmi_entry")
        # Seed stock-like priors.
        emu.write_mem(0x0314, 0x31)
        emu.write_mem(0x0315, 0xEA)
        emu.write_mem(0x0318, 0x47)
        emu.write_mem(0x0319, 0xFE)
        emu.execute(_load_symbol_address("compiler_vectors"), 10_000)
        state = emu.get_state()
        assert not (int(state.p) & 0x01)
        assert emu.read_mem(0x0314) == (irq_kernal_entry & 0xFF)
        assert emu.read_mem(0x0315) == (irq_kernal_entry >> 8)
        assert emu.read_mem(0x0318) == (nmi_entry & 0xFF)
        assert emu.read_mem(0x0319) == (nmi_entry >> 8)
        assert emu.read_mem(0xFFFA) == (nmi_entry & 0xFF)
        assert emu.read_mem(0xFFFB) == (nmi_entry >> 8)
        assert emu.read_mem(0xFFFC) == 0xE2
        assert emu.read_mem(0xFFFD) == 0xFC
        assert emu.read_mem(0xFFFE) == (irq_entry & 0xFF)
        assert emu.read_mem(0xFFFF) == (irq_entry >> 8)
        assert emu.read_mem(_load_symbol_address("vectors_prior_irq")) == 0x31
        assert emu.read_mem(_load_symbol_address("vectors_prior_irq") + 1) == 0xEA
        assert emu.read_mem(_load_symbol_address("vectors_prior_nmi")) == 0x47
        assert emu.read_mem(_load_symbol_address("vectors_prior_nmi") + 1) == 0xFE
        assert emu.read_mem(_load_symbol_address("vectors_installed")) == 1

    def test_vectors_restore_puts_priors_back(self) -> None:
        """vectors_restore reinstalls the saved stock IRQ/NMI vectors."""
        emu = _new_emulator()
        emu.write_mem(0x0314, 0x31)
        emu.write_mem(0x0315, 0xEA)
        emu.write_mem(0x0318, 0x47)
        emu.write_mem(0x0319, 0xFE)
        emu.execute(_load_symbol_address("compiler_vectors"), 10_000)
        emu.execute(_load_symbol_address("vectors_restore"), 10_000)
        assert emu.read_mem(0x0314) == 0x31
        assert emu.read_mem(0x0315) == 0xEA
        assert emu.read_mem(0x0318) == 0x47
        assert emu.read_mem(0x0319) == 0xFE
        assert emu.read_mem(_load_symbol_address("vectors_installed")) == 0


# Bootstrap phase codes (must match compiler_init.asm INIT_STATE_*).
INIT_STATE_COLD = 0x00
INIT_STATE_REDETECT = 0x01
INIT_STATE_READY = 0x02
ERR_ILLEGAL_QUANTITY = 0x0E


@pytest.mark.unit
@pytest.mark.local
class TestCompilerStateMachine:
    """Honest bootstrap phase latch tests."""

    def test_state_machine_accepts_cold_and_redetect(self) -> None:
        """COLD and REDETECT latch with Y=0 and do not require subsystems."""
        emu = _new_emulator()
        phase = _load_symbol_address("init_phase")
        addr = _load_symbol_address("compiler_state_machine")

        emu.set_x(INIT_STATE_COLD)
        emu.set_y(0)
        emu.execute(addr, 10_000)
        assert not (int(emu.get_state().p) & 0x01)
        assert emu.get_state().a == 0
        assert emu.read_mem(phase) == INIT_STATE_COLD

        emu.set_x(INIT_STATE_REDETECT)
        emu.set_y(0)
        emu.execute(addr, 10_000)
        assert not (int(emu.get_state().p) & 0x01)
        assert emu.read_mem(phase) == INIT_STATE_REDETECT

    def test_state_machine_rejects_unknown_or_non_zero_y(self) -> None:
        """Unknown phase codes and non-zero Y fail without latching."""
        emu = _new_emulator()
        phase = _load_symbol_address("init_phase")
        addr = _load_symbol_address("compiler_state_machine")
        emu.write_mem(phase, 0xAA)

        emu.set_x(0x7F)
        emu.set_y(0)
        emu.execute(addr, 10_000)
        state = emu.get_state()
        assert int(state.p) & 0x01
        assert state.a == ERR_ILLEGAL_QUANTITY
        assert emu.read_mem(phase) == 0xAA

        emu.set_x(INIT_STATE_COLD)
        emu.set_y(1)
        emu.execute(addr, 10_000)
        state = emu.get_state()
        assert int(state.p) & 0x01
        assert state.a == ERR_ILLEGAL_QUANTITY
        assert emu.read_mem(phase) == 0xAA

    def test_state_machine_ready_requires_arenas_and_vectors(self) -> None:
        """READY is rejected until arenas and vectors are actually published."""
        emu = _new_emulator()
        phase = _load_symbol_address("init_phase")
        addr = _load_symbol_address("compiler_state_machine")
        arena_state = _load_symbol_address("init_arena_state")
        vectors = _load_symbol_address("vectors_installed")

        emu.write_mem(arena_state, 0)
        emu.write_mem(vectors, 0)
        emu.set_x(INIT_STATE_READY)
        emu.set_y(0)
        emu.execute(addr, 10_000)
        assert int(emu.get_state().p) & 0x01
        assert emu.get_state().a == ERR_ILLEGAL_QUANTITY

        emu.write_mem(arena_state, 1)
        emu.write_mem(vectors, 0)
        emu.set_x(INIT_STATE_READY)
        emu.set_y(0)
        emu.execute(addr, 10_000)
        assert int(emu.get_state().p) & 0x01

        emu.write_mem(arena_state, 1)
        emu.write_mem(vectors, 1)
        emu.set_x(INIT_STATE_READY)
        emu.set_y(0)
        emu.execute(addr, 10_000)
        assert not (int(emu.get_state().p) & 0x01)
        assert emu.get_state().a == 0
        assert emu.read_mem(phase) == INIT_STATE_READY


@pytest.mark.callable_coverage("init_editor", executor="execute")
@pytest.mark.unit
@pytest.mark.local
def test_init_editor_sets_cold_start_state() -> None:
    """Editor initialization sets the default row and clears mode state."""
    emu = _new_emulator()
    _run_xip(emu, "init_editor")
    state_addr = _load_symbol_address("init_editor_state")
    assert bytes(emu.read_mem(state_addr + index) for index in range(4)) == bytes(
        [5, 0, 0, 0]
    )


@pytest.mark.unit
@pytest.mark.local
def test_init_enter_main_loop_records_tail_entry() -> None:
    """Main-loop entry records entry, enables IRQs, and tail-jumps resident_main."""
    emu = _new_emulator()
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record = directory["routines"]["init_enter_main_loop"]
    assert record["layer"] == "georam"
    assert record["page"] == 50
    entry = _load_symbol_address("init_enter_main_loop")
    marker = _load_symbol_address("init_main_loop_entered")
    resident = _load_symbol_address("resident_main")
    emu.write_mem(0xDFFF, int(record["block"]))
    emu.write_mem(0xDFFE, int(record["page"]))
    assert bytes(emu.read_mem(entry + offset) for offset in range(9)) == bytes(
        [
            0xA9,
            0x01,
            0x8D,
            marker & 0xFF,
            marker >> 8,
            0x58,
            0x4C,
            resident & 0xFF,
            resident >> 8,
        ]
    )
