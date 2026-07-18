"""Real-byte unit tests for loader-core installation and hand-off behavior."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
TESTS_ROOT = ROOT / "tests"
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from tests.kernal_stubs import install_kernal_stubs  # noqa: E402

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None


def _dll_path() -> Path:
    """Return the local emulator library or skip when it is unavailable."""
    for name in ("emu6502.dll", "msys-emu6502.dll"):
        path = TOOLS_ROOT / name
        if path.is_file():
            return path
    pytest.skip("Emulator DLL not found in tools folder.")


def _load_symbol_address(symbol_name: str) -> int:
    """Resolve an exported symbol from the current linked artifact."""
    label_path = ROOT / "build" / "compiler.lbl"
    if label_path.is_file():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            label_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)

    directory_path = ROOT / "build" / "routine_directory.json"
    if directory_path.is_file():
        data = json.loads(directory_path.read_text(encoding="utf-8"))
        address = data.get("routines", {}).get(symbol_name, {}).get("address", "")
        if isinstance(address, str) and address.startswith("$"):
            return int(address[1:], 16)

    pytest.fail(f"Symbol '{symbol_name}' not found in the linked artifact.")


def _load_zp_address(name: str) -> int:
    """Resolve one generated zero-page symbol."""
    allocation_path = ROOT / "build" / "zp_allocation.json"
    if not allocation_path.is_file():
        pytest.fail("build/zp_allocation.json not found. Run build.ps1 first.")
    allocation = json.loads(allocation_path.read_text(encoding="utf-8"))["allocation"]
    return int(allocation[name].removeprefix("$"), 16)


def _new_emulator(*, georam_kib: int | None, kernal_stubs: bool = False) -> Any:
    """Load the production binary into an unpatched local emulator instance."""
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable.")
    emu = C64Emu6502(lib_path=_dll_path())
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_address = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_address, payload[2:])
    setattr(emu, "_compiler2_real_bytes_only", True)
    emu.set_georam_enabled(False)
    if georam_kib is not None:
        emu.load_georam(b"\x00" * georam_kib * 1024)
        emu.set_georam_enabled(True)
    if kernal_stubs:
        # loader_entry status strings go through the KERNAL bridge/CHROUT.
        install_kernal_stubs(emu)
        emu.write_mem(0x0001, 0x35)
    return emu


def _run(emu: Any, symbol_name: str, cycles: int = 100_000) -> Any:
    """Execute the linked routine directly through its RTS boundary."""
    emu.execute_rts(_load_symbol_address(symbol_name), cycles)
    return emu.get_state()


def _linked_bytes(address: int, length: int) -> bytes:
    """Read bytes from the linked PRG payload at an absolute CPU address."""
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_address = payload[0] | (payload[1] << 8)
    offset = address - load_address
    if offset < 0 or offset + length > len(payload) - 2:
        pytest.fail(f"Address ${address:04X} is outside build/compiler.bin.")
    return payload[2 + offset : 2 + offset + length]


def _contains_absolute_transfer(code: bytes, opcode: int, target: int) -> bool:
    """Return whether linked code contains a selected absolute transfer."""
    return bytes((opcode, target & 0xFF, target >> 8)) in code


@pytest.mark.unit
@pytest.mark.local
class TestLoaderCore:
    """Loader-core behavior that does not require a disk-backed emulator."""

    def test_detect_wrapper_runs_real_detector_from_hidden_io(self) -> None:
        """The loader wrapper must publish a supported GeoRAM profile directly."""
        emu = _new_emulator(georam_kib=512)
        emu.write_mem(0x0001, 0x30)

        state = _run(emu, "loader_detect_georam", 1_000_000)

        assert (state.p & 0x01) == 0
        assert (state.x, state.y) == (0x00, 0x08)
        assert emu.read_mem(0x0001) == 0x30

    def test_memory_paging_selects_the_requested_four_kib_page(self) -> None:
        """Four-KiB page five maps to GeoRAM block one, page sixteen."""
        emu = _new_emulator(georam_kib=512)
        emu.write_mem(0x0001, 0x35)
        emu.set_a(5)

        state = _run(emu, "loader_memory_paging")

        assert (state.p & 0x01) == 0
        assert emu.read_mem(_load_zp_address("zp_gr_block")) == 1
        assert emu.read_mem(_load_zp_address("zp_gr_page")) == 16
        assert emu.read_mem(0xDFFF) == 1
        assert emu.read_mem(0xDFFE) == 16

    def test_ram_payload_install_uses_one_source_page_without_pointer_skips(
        self,
    ) -> None:
        """The linked loop advances Y only; the VICE loader test checks bytes."""
        entry = _load_symbol_address("loader_install_ram_payload")
        code = _linked_bytes(entry, 32)
        zp_tmptr = _load_zp_address("zp_tmptr")
        assert bytes((0x86, zp_tmptr, 0x84, zp_tmptr + 1, 0xA0, 0x00)) in code
        assert bytes((0xB1, zp_tmptr, 0x99, 0x00, 0x10, 0xC8, 0xD0)) in code

    def test_stage_buffer_reserves_the_fake_prg_header(self) -> None:
        """The bounded staging buffer must include two header bytes plus two pages."""
        stage = _load_symbol_address("georam_stage_buffer")
        count = _load_symbol_address("georam_stage_page_count")
        assert count - stage == 2 + 2 * 256

    def test_entry_contains_detection_and_compiler_init_handoff(self) -> None:
        """The fixed loader page must detect, install, restore mapping, then jump to init."""
        entry = _load_symbol_address("loader_entry")
        code = _linked_bytes(entry, 0x100 - (entry & 0xFF))

        assert _contains_absolute_transfer(
            code, 0x20, _load_symbol_address("loader_detect_georam")
        )
        assert _contains_absolute_transfer(
            code, 0x20, _load_symbol_address("loader_restore_banking")
        )
        assert _contains_absolute_transfer(
            code, 0x4C, _load_symbol_address("compiler_init")
        )

    def test_loader_detect_prefers_georam_when_both_present(self) -> None:
        """Dual detect selects geoRAM store and marks REU assist when both exist."""
        emu = _new_emulator(georam_kib=512)
        emu.write_mem(0x0001, 0x35)
        emu.set_reu_enabled(True)
        emu.load_reu(b"\x00" * (512 * 1024))

        state = _run(emu, "loader_detect_georam", 1_000_000)

        assert (state.p & 0x01) == 0
        assert (state.x, state.y) == (0x00, 0x08)
        assert emu.read_mem(_load_symbol_address("expansion_store")) == 1
        assert emu.read_mem(_load_symbol_address("expansion_reu_assist")) == 1
        assert emu.read_mem(_load_symbol_address("loader_georam_ok")) == 1
        assert emu.read_mem(_load_symbol_address("loader_reu_ok")) == 1
        assert emu.read_mem(_load_symbol_address("expansion_capacity_georam")) == 0x20
        assert emu.read_mem(_load_symbol_address("expansion_capacity_reu")) == 8

    def test_loader_detect_reu_only_selects_reu_store(self) -> None:
        """REU-only systems select REU store without geoRAM assist."""
        emu = _new_emulator(georam_kib=None)
        emu.write_mem(0x0001, 0x35)
        emu.set_reu_enabled(True)
        emu.load_reu(b"\x00" * (512 * 1024))

        state = _run(emu, "loader_detect_georam", 1_000_000)

        assert (state.p & 0x01) == 0
        assert emu.read_mem(_load_symbol_address("expansion_store")) == 2
        assert emu.read_mem(_load_symbol_address("expansion_reu_assist")) == 0
        assert emu.read_mem(_load_symbol_address("loader_reu_ok")) == 1
        assert emu.read_mem(_load_symbol_address("expansion_capacity_reu")) == 8

    def test_loader_detect_neither_fails_clean(self) -> None:
        """Neither device present must fail without claiming a store."""
        emu = _new_emulator(georam_kib=None)
        emu.write_mem(0x0001, 0x35)
        emu.set_reu_enabled(False)

        state = _run(emu, "loader_detect_georam", 1_000_000)

        assert state.p & 0x01
        assert emu.read_mem(_load_symbol_address("expansion_store")) == 0

    def test_loader_detect_never_fakes_de00(self) -> None:
        """Source must call real detectors, not poke fake $DE00 patterns alone."""
        source = (ROOT / "src" / "geoasm" / "loader_core.asm").read_text(
            encoding="utf-8"
        )
        assert "jsr detect_georam" in source
        assert "jsr detect_reu" in source
        assert "sta $DE00" in source  # install path still writes window
        assert "stx $D000" not in source

    def test_loader_entry_neither_fails_clean(self) -> None:
        """No expansion device → error path and cleared profile."""
        emu = _new_emulator(georam_kib=None, kernal_stubs=True)
        emu.write_mem(0x0001, 0x35)
        # Undersized geoRAM so stepped mapping is visible while both probes fail.
        emu.set_georam_enabled(True)
        emu.load_georam(b"\x00" * (64 * 1024))
        emu.set_reu_enabled(False)
        emu.write_mem(_load_symbol_address("loader_sequence_phase"), 0x5A)

        state = _run(emu, "loader_entry", 1_000_000)

        assert state.p & 0x01
        assert state.a == 0x1D  # ERR_LOAD
        assert emu.read_mem(_load_symbol_address("loader_sequence_phase")) == 0xFF
        assert emu.read_mem(_load_symbol_address("expansion_store")) == 0

    def test_loader_entry_skip_reload_when_fingerprint_matches(self) -> None:
        """Matching image fingerprint with session ready skips disk reload."""
        emu = _new_emulator(georam_kib=512, kernal_stubs=True)
        emu.write_mem(0x0001, 0x35)
        _run(emu, "loader_detect_georam", 1_000_000)
        assert (emu.get_state().p & 0x01) == 0
        store = emu.read_mem(_load_symbol_address("expansion_store"))
        cap_geo = emu.read_mem(_load_symbol_address("expansion_capacity_georam"))
        cap_reu = emu.read_mem(_load_symbol_address("expansion_capacity_reu"))
        candidate = (0xC1 ^ store ^ cap_geo ^ cap_reu) & 0xFF
        emu.write_mem(_load_symbol_address("expansion_session_ready"), 1)
        emu.write_mem(_load_symbol_address("expansion_image_fingerprint"), candidate)
        emu.write_mem(_load_symbol_address("loader_sequence_phase"), 0)

        # Plant RTS at compiler_init so the non-returning handoff returns without
        # init_clear_bss wiping loader/expansion BSS (which would hide skip success).
        emu.write_mem(_load_symbol_address("compiler_init"), 0x60)
        state = _run(emu, "loader_entry", 1_000_000)
        phase = emu.read_mem(_load_symbol_address("loader_sequence_phase"))
        assert phase != 0xFF
        assert phase >= 2
        assert emu.read_mem(_load_symbol_address("expansion_session_ready")) == 1
        # Carry is undefined after the planted RTS; ensure we did not take @failed.
        assert state.a != 0x1D
