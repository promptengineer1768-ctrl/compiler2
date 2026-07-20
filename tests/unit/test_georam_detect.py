"""Unit tests for geoRAM detection."""

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
TESTS_ROOT = ROOT / "tests"
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

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
    dir_path = ROOT / "build" / "routine_directory.json"
    if dir_path.exists():
        try:
            data = json.loads(dir_path.read_text(encoding="utf-8"))
            routines = data.get("routines", {})
            if symbol_name in routines:
                addr_str = routines[symbol_name].get("address", "")
                if addr_str.startswith("$"):
                    return int(addr_str[1:], 16)
        except Exception:
            pass
    lbl_path = ROOT / "build" / "compiler.lbl"
    if lbl_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            lbl_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    map_path = ROOT / "build" / "compiler.map"
    if not map_path.exists():
        pytest.fail("build/compiler.map not found. Run build.ps1 first.")
    match = re.search(
        rf"\b{symbol_name}\b\s+([0-9A-Fa-f]{{6}})",
        map_path.read_text(encoding="utf-8"),
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found in compiler.map.")


def _load_zp_address(name: str) -> int:
    inc_path = ROOT / "build" / "zp_symbols.inc"
    if inc_path.exists():
        match = re.search(
            rf"^{re.escape(name)}\s*=\s*\$([0-9A-Fa-f]+)$",
            inc_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    path = ROOT / "build" / "zp_allocation.json"
    if not path.exists():
        pytest.fail("build/zp_allocation.json not found. Run build.ps1 first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    addr_str = data.get("allocation", {}).get(name, "")
    if addr_str.startswith("$"):
        return int(addr_str[1:], 16)
    pytest.fail(f"Zero page symbol '{name}' not found in allocation.")


def _load_binary(emu: C64Emu6502, *, georam_enabled: bool) -> None:
    """Load the linked image and opt out of semantic emulator substitutions."""
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.set_georam_enabled(georam_enabled)


@pytest.mark.unit
@pytest.mark.local
class TestGeoramDetect:
    """geoRAM detection and profile tests."""

    @pytest.mark.parametrize(
        "routine", ["detect_probe_pattern1", "detect_probe_pattern2"]
    )
    def test_direct_probe_patterns_verify_distinct_pages(self, routine: str) -> None:
        """Each destructive probe pattern executes and recognizes real geoRAM."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, georam_enabled=True)
        emu.execute_rts(_load_symbol_address(routine), 10_000)
        assert (emu.get_state().p & 0x01) == 0

    def test_publish_profile_copies_capacity_and_returns_page_count(self) -> None:
        """detect_publish_profile publishes the measured capacity atomically."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, georam_enabled=True)
        emu.execute_rts(_load_symbol_address("detect_probe_aliasing"), 1_000_000)
        emu.execute_rts(_load_symbol_address("detect_publish_profile"), 10_000)
        state = emu.get_state()
        assert (state.x, state.y) == (0x00, 0x08)
        emu.execute_rts(_load_symbol_address("detect_validate_profile"), 10_000)
        assert (emu.get_state().p & 0x01) == 0

    def test_detect_absent_restores_state_and_fails(self) -> None:
        """detect_georam should fail cleanly when geoRAM pages alias."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu, georam_enabled=False)

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")

        emu.write_mem(zp_gr_block, 0x12)
        emu.write_mem(zp_gr_page, 0x34)
        emu.write_mem(0x0001, 0x35)
        emu.write_mem(0xDFFF, 0x12)
        emu.write_mem(0xDFFE, 0x34)

        emu.execute_rts(_load_symbol_address("detect_georam"), 1_000_000)
        state = emu.get_state()
        assert state.p & 0x01
        assert emu.read_mem(zp_gr_block) == 0x12
        assert emu.read_mem(zp_gr_page) == 0x34
        assert emu.read_mem(0x0001) == 0x35
        assert emu.read_mem(0xDFFF) == 0x12
        assert emu.read_mem(0xDFFE) == 0x34

    def test_detect_present_publishes_profile(self) -> None:
        """detect_georam should publish a 512 KiB profile when pages are distinct."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu, georam_enabled=True)

        emu.write_mem(0x0001, 0x35)

        emu.execute_rts(_load_symbol_address("detect_georam"), 1_000_000)
        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert state.x == 0x00
        assert state.y == 0x08

        emu.set_x(0x00)
        emu.set_y(0x08)
        emu.execute(_load_symbol_address("detect_validate_profile"), 10_000)
        assert (emu.get_state().p & 0x01) == 0

    def test_detect_undersized_georam_fails_cleanly(self) -> None:
        """detect_georam should reject geoRAM smaller than 512 KiB."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu, georam_enabled=False)
        emu.load_georam(b"\x00" * (256 * 1024))

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")
        emu.write_mem(zp_gr_block, 0x03)
        emu.write_mem(zp_gr_page, 0x04)
        emu.write_mem(0x0001, 0x35)
        emu.write_mem(0xDFFF, 0x03)
        emu.write_mem(0xDFFE, 0x04)

        emu.execute_rts(_load_symbol_address("detect_georam"), 1_000_000)
        assert emu.get_state().p & 0x01
        assert emu.read_mem(zp_gr_block) == 0x03
        assert emu.read_mem(zp_gr_page) == 0x04
        assert emu.read_mem(0xDFFF) == 0x03
        assert emu.read_mem(0xDFFE) == 0x04

    def test_detect_aliasing_and_minimum_threshold(self) -> None:
        """Probe aliasing should distinguish absent and supported capacity."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu, georam_enabled=False)

        emu.execute_rts(_load_symbol_address("detect_probe_aliasing"), 1_000_000)
        assert emu.get_state().p & 0x01
        assert emu.read_mem(_load_symbol_address("detect_capacity_blocks")) == 0x00

        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu, georam_enabled=True)
        emu.execute_rts(_load_symbol_address("detect_probe_aliasing"), 1_000_000)
        assert emu.read_mem(_load_symbol_address("detect_capacity_blocks")) == 0x20
        emu.execute(_load_symbol_address("detect_check_minimum"), 10_000)
        assert (emu.get_state().p & 0x01) == 0

    def test_minimum_threshold_rejects_undersized_capacity(self) -> None:
        """detect_check_minimum should reject capacities below 512 KiB."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu, georam_enabled=True)

        capacity_blocks = _load_symbol_address("detect_capacity_blocks")
        emu.write_mem(capacity_blocks, 0x1F)

        emu.execute(_load_symbol_address("detect_check_minimum"), 10_000)
        assert emu.get_state().p & 0x01

        emu.write_mem(capacity_blocks, 0x20)
        emu.execute(_load_symbol_address("detect_check_minimum"), 10_000)
        assert (emu.get_state().p & 0x01) == 0

    def test_save_and_restore_round_trip(self) -> None:
        """detect_save_state and detect_restore_state should round-trip the map."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu, georam_enabled=True)

        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")
        emu.write_mem(zp_gr_block, 0x01)
        emu.write_mem(zp_gr_page, 0x02)
        emu.write_mem(0x0001, 0x35)
        emu.write_mem(0xDFFF, 0x01)
        emu.write_mem(0xDFFE, 0x02)

        emu.execute(_load_symbol_address("detect_save_state"), 10_000)
        emu.write_mem(zp_gr_block, 0x09)
        emu.write_mem(zp_gr_page, 0x0A)
        emu.write_mem(0x0001, 0x35)
        emu.write_mem(0xDFFF, 0x09)
        emu.write_mem(0xDFFE, 0x0A)
        emu.execute(_load_symbol_address("detect_restore_state"), 10_000)
        assert emu.read_mem(zp_gr_block) == 0x01
        assert emu.read_mem(zp_gr_page) == 0x02
        assert emu.read_mem(0x0001) == 0x35
        assert emu.read_mem(0xDFFF) == 0x01
        assert emu.read_mem(0xDFFE) == 0x02

    @pytest.mark.parametrize(
        ("capacity_kib", "expected_blocks"),
        [(512, 0x20), (1024, 0x40)],
        ids=["512k", "1m"],
    )
    def test_detect_measures_actual_supported_capacity(
        self, capacity_kib: int, expected_blocks: int
    ) -> None:
        """Detection must publish the measured contiguous capacity, not a floor."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, georam_enabled=False)
        emu.load_georam(b"\x00" * capacity_kib * 1024)
        emu.set_georam_enabled(True)
        emu.write_mem(0x0001, 0x35)

        emu.execute_rts(_load_symbol_address("detect_georam"), 1_000_000)

        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert (
            emu.read_mem(_load_symbol_address("detect_capacity_blocks"))
            == expected_blocks
        )
        assert (state.x | (state.y << 8)) == expected_blocks * 64

    def test_detect_establishes_io_visibility_and_restores_hidden_mapping(self) -> None:
        """Detection must probe real hardware even when I/O starts hidden."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, georam_enabled=True)
        zp_gr_block = _load_zp_address("zp_gr_block")
        zp_gr_page = _load_zp_address("zp_gr_page")

        emu.write_mem(zp_gr_block, 0x12)
        emu.write_mem(zp_gr_page, 0x34)
        emu.write_mem(0x0001, 0x35)
        emu.write_mem(0xDFFF, 0x12)
        emu.write_mem(0xDFFE, 0x34)
        emu.write_mem(0x0001, 0x30)

        emu.execute_rts(_load_symbol_address("detect_georam"), 1_000_000)

        assert (emu.get_state().p & 0x01) == 0
        assert emu.read_mem(0x0001) == 0x30
        assert emu.read_mem(zp_gr_block) == 0x12
        assert emu.read_mem(zp_gr_page) == 0x34
        emu.write_mem(0x0001, 0x35)
        assert emu.read_mem(0xDFFF) == 0x12
        assert emu.read_mem(0xDFFE) == 0x34

    @pytest.mark.parametrize(
        ("georam", "reu", "expected_store", "expected_assist"),
        [
            (True, False, 1, 0),
            (False, True, 2, 0),
            (True, True, 1, 1),
        ],
        ids=["georam-only", "reu-only", "both-prefer-georam"],
    )
    def test_dual_detector_selects_one_store_and_publishes_profile(
        self,
        georam: bool,
        reu: bool,
        expected_store: int,
        expected_assist: int,
    ) -> None:
        """Cold detection selects one store and publishes all required policy."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, georam_enabled=georam)
        emu.set_reu_enabled(False)
        if reu:
            # Real REC probe requires enabled REU memory (not $DF00 status fakes).
            emu.load_reu(b"\x00" * (512 * 1024))
            emu.set_reu_enabled(True)

        emu.execute_rts(_load_symbol_address("detect_expansion"), 5_000_000)

        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert state.a == expected_store
        assert (
            emu.read_mem(_load_symbol_address("detect_profile_store_kind"))
            == expected_store
        )
        assert (
            emu.read_mem(_load_symbol_address("detect_profile_reu_assist"))
            == expected_assist
        )
        assert emu.read_mem(_load_symbol_address("detect_profile_xip_base_lo")) == 0x00
        assert emu.read_mem(_load_symbol_address("detect_profile_xip_base_hi")) == 0xCE
        assert emu.read_mem(_load_symbol_address("detect_profile_xip_slots")) == 1
        assert emu.read_mem(_load_symbol_address("detect_profile_n_dma")) == 32
        assert emu.read_mem(_load_symbol_address("detect_profile_n_fill")) == 32
        assert emu.read_mem(_load_symbol_address("detect_profile_generation")) != 0

    def test_dual_detector_rejects_neither_device(self) -> None:
        """Installation fails before publishing a store when neither probe passes."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, georam_enabled=False)
        emu.set_reu_enabled(False)

        emu.execute_rts(_load_symbol_address("detect_expansion"), 5_000_000)

        assert emu.get_state().p & 0x01
        assert emu.read_mem(_load_symbol_address("detect_profile_store_kind")) == 0

    def test_dual_profile_integrity_detects_policy_corruption(self) -> None:
        """The immutable interval fingerprint covers policy, slots, and thresholds."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, georam_enabled=True)
        emu.load_reu(b"\x00" * (512 * 1024))
        emu.set_reu_enabled(True)
        emu.execute_rts(_load_symbol_address("detect_expansion"), 5_000_000)
        state = emu.get_state()
        pages = int(state.x) | (int(state.y) << 8)
        emu.set_x(pages & 0xFF)
        emu.set_y(pages >> 8)
        emu.execute_rts(_load_symbol_address("detect_validate_profile"), 10_000)
        assert (emu.get_state().p & 0x01) == 0

        threshold = _load_symbol_address("detect_profile_n_dma")
        emu.write_mem(threshold, emu.read_mem(threshold) ^ 1)
        emu.set_x(pages & 0xFF)
        emu.set_y(pages >> 8)
        emu.execute_rts(_load_symbol_address("detect_validate_profile"), 10_000)
        assert emu.get_state().p & 0x01
