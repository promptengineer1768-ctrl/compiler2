"""Unit tests for resident KERNAL bridge helpers."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from tests.kernal_stubs import (
    KERNAL_READST,
    KERNAL_STUB_INPUT,
    KERNAL_STUB_LAST_PORT,
    install_kernal_stubs,
    install_vector_stub,
)

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
            data = json.loads(dir_path.read_text(encoding="utf-8"))
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


def _load_binary(emu: C64Emu6502) -> None:
    emu.set_georam_enabled(True)
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    install_kernal_stubs(emu)


def _linked_bytes(address: int, length: int) -> bytes:
    """Return linked compiler bytes for an absolute memory address range."""
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    offset = address - load_addr
    if offset < 0 or offset + length > len(payload) - 2:
        pytest.fail(f"Address ${address:04X} is outside build/compiler.bin")
    return payload[2 + offset : 2 + offset + length]


@pytest.mark.unit
@pytest.mark.local
class TestKernalBridge:
    """Bridge behavior tests."""

    @pytest.mark.callable_coverage("kernal_setnam", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_setlfs", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_save", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_load", executor="execute_rts")
    def test_workspace_calls_store_parameters_and_restore_mapping(self) -> None:
        """SETLFS, SETNAM, LOAD, and SAVE should update their workspace bytes."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        emu.write_mem(0x0001, 0x35)
        state = emu.get_state()
        emu.set_p(state.p | 0x04)

        emu.set_a(0x02)
        emu.set_x(0x08)
        emu.set_y(0x01)
        emu.execute(_load_symbol_address("kernal_setlfs"), 10_000)
        assert (emu.get_state().p & 1) == 0
        assert emu.read_mem(0x0001) == 0x35

        emu.set_a(0x04)
        emu.set_x(0x20)
        emu.set_y(0xC0)
        emu.execute(_load_symbol_address("kernal_setnam"), 10_000)
        assert (emu.get_state().p & 1) == 0

        emu.set_x(0x11)
        emu.set_y(0x22)
        emu.execute(_load_symbol_address("kernal_load"), 10_000)
        assert (emu.get_state().p & 1) == 0

        emu.write_mem(0xC100, 0x33)
        emu.write_mem(0xC101, 0x44)
        emu.set_a(0x02)
        emu.write_mem(0x0002, 0x00)
        emu.write_mem(0x0003, 0xC1)
        emu.set_x(0x55)
        emu.set_y(0x66)
        emu.execute(_load_symbol_address("kernal_save"), 10_000)
        assert (emu.get_state().p & 1) == 0

        assert emu.get_state().p & 0x04

    @pytest.mark.callable_coverage("kernal_open", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_clrchn", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_close", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_chkout", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_chkin", executor="execute_rts")
    def test_open_close_and_channel_calls_preserve_interrupt_state(self) -> None:
        """OPEN/CLOSE/CHKIN/CHKOUT/CLRCHN should restore the incoming I flag."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_fnlen = _load_zp_address("zp_fnlen")
        zp_status = _load_zp_address("zp_status")

        routine_cases = [
            ("kernal_open", 0x00, 0x00, 0x00, True),
            ("kernal_close", 0x01, 0x00, 0x00, False),
            ("kernal_chkin", 0x00, 0x05, 0x00, False),
            ("kernal_chkout", 0x00, 0x06, 0x00, False),
            ("kernal_clrchn", 0x00, 0x00, 0x00, False),
        ]
        for name, a_val, x_val, y_val, needs_fnlen in routine_cases:
            emu.write_mem(0x0001, 0x35)
            emu.write_mem(zp_status, 0x7F)
            if needs_fnlen:
                emu.write_mem(zp_fnlen, 0x01)
            state = emu.get_state()
            emu.set_p(state.p & ~0x04)
            emu.set_a(a_val)
            emu.set_x(x_val)
            emu.set_y(y_val)
            emu.execute(_load_symbol_address(name), 10_000)
            assert emu.read_mem(0x0001) == 0x35
            assert (emu.get_state().p & 1) == (
                1 if name == "kernal_open" and not needs_fnlen else 0
            )
            assert (emu.get_state().p & 0x04) == 0

    @pytest.mark.callable_coverage("kernal_udtim", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_stop", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_settim", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_scnkey", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_readst", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_rdtim", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_getin", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_chrout", executor="execute_rts")
    @pytest.mark.callable_coverage("kernal_chrin", executor="execute_rts")
    def test_io_and_time_helpers_round_trip(self) -> None:
        """CHRIN/CHROUT, RDTIM/SETTIM, UDTIM, STOP, and SCNKEY should be bounded."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        zp_time = _load_zp_address("zp_time")
        zp_ndx = _load_zp_address("zp_ndx")
        zp_lstx = _load_zp_address("zp_lstx")
        zp_status = _load_zp_address("zp_status")
        zp_stkey = _load_zp_address("zp_stkey")
        kernal_input = KERNAL_STUB_INPUT

        emu.set_a(0x11)
        emu.set_x(0x22)
        emu.set_y(0x33)
        emu.execute(_load_symbol_address("kernal_settim"), 10_000)
        assert emu.read_mem_range(zp_time, zp_time + 2) == b"\x33\x22\x11"
        emu.execute(_load_symbol_address("kernal_rdtim"), 10_000)
        state = emu.get_state()
        assert state.a == 0x11
        assert state.x == 0x22
        assert state.y == 0x33

        emu.write_mem(zp_time, 0x01)
        emu.write_mem(zp_time + 1, 0x00)
        emu.write_mem(zp_time + 2, 0xFF)
        emu.execute(_load_symbol_address("kernal_udtim"), 10_000)
        assert emu.read_mem(zp_time) == 0x01
        assert emu.read_mem(zp_time + 1) == 0x01
        assert emu.read_mem(zp_time + 2) == 0x00

        emu.write_mem(kernal_input, 0x5A)
        emu.execute(_load_symbol_address("kernal_getin"), 10_000)
        assert emu.get_state().a == 0x5A
        assert emu.read_mem(kernal_input) == 0x00

        emu.write_mem(kernal_input, 0x6B)
        emu.execute(_load_symbol_address("kernal_chrin"), 10_000)
        assert emu.get_state().a == 0x6B

        emu.set_a(0xA5)
        emu.execute(_load_symbol_address("kernal_chrout"), 10_000)
        assert (emu.get_state().p & 1) == 0

        emu.write_mem(zp_status, 0x9A)
        emu.execute(_load_symbol_address("kernal_readst"), 10_000)
        assert emu.get_state().a == 0x9A

        emu.write_mem(zp_stkey, 0x00)
        emu.execute(_load_symbol_address("kernal_stop"), 10_000)
        assert emu.get_state().p & 0x02

        emu.write_mem(zp_ndx, 0x03)
        zp_crsr_x = _load_zp_address("zp_crsr_x")
        emu.write_mem(zp_crsr_x, 0x44)
        emu.execute(_load_symbol_address("kernal_scnkey"), 10_000)
        assert emu.read_mem(zp_lstx) == 0x44
        assert emu.read_mem(zp_ndx) == 0x04

    @pytest.mark.parametrize(
        ("routine", "vector"),
        [
            ("kernal_readst", 0xFFB7),
            ("kernal_setlfs", 0xFFBA),
            ("kernal_setnam", 0xFFBD),
            ("kernal_open", 0xFFC0),
            ("kernal_close", 0xFFC3),
            ("kernal_chkin", 0xFFC6),
            ("kernal_chkout", 0xFFC9),
            ("kernal_clrchn", 0xFFCC),
            ("kernal_chrin", 0xFFCF),
            ("kernal_chrout", 0xFFD2),
            ("kernal_load", 0xFFD5),
            ("kernal_save", 0xFFD8),
            ("kernal_settim", 0xFFDB),
            ("kernal_rdtim", 0xFFDE),
            ("kernal_stop", 0xFFE1),
            ("kernal_getin", 0xFFE4),
            ("kernal_udtim", 0xFFEA),
            ("kernal_scnkey", 0xFF9F),
        ],
    )
    def test_each_bridge_calls_its_public_kernal_vector(
        self, routine: str, vector: int
    ) -> None:
        """Every bridge must dispatch through the documented jump-table entry."""
        body = _linked_bytes(_load_symbol_address(routine), 16)
        assert bytes((0x20, vector & 0xFF, vector >> 8)) in body

    @pytest.mark.callable_coverage("kernal_print_packed", executor="execute_rts")
    def test_packed_static_string_emitter_masks_final_character(self) -> None:
        """The shared emitter stops on bit 7 and outputs the masked byte."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        message = 0xC900
        emu.write_mem_range(message, b"OK" + bytes([0x8D, ord("X")]))
        emu.set_x(message & 0xFF)
        emu.set_y(message >> 8)

        emu.execute(_load_symbol_address("kernal_print_packed"), 10_000)

        output = _load_symbol_address("kernal_output_byte")
        assert emu.read_mem(output) == 0x0D
        assert (emu.get_state().p & 1) == 0

    @pytest.mark.callable_coverage("kernal_readst", executor="execute_rts")
    @pytest.mark.parametrize("irq_disabled", [False, True])
    def test_bridge_returns_kernal_results_and_restores_mapping_and_irq_state(
        self, irq_disabled: bool
    ) -> None:
        """The external vector sees $36 and its result survives the bridge."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.write_mem(0x0000, 0x2F)
        emu.write_mem(0x0001, 0x35)
        state = emu.get_state()
        expected_p = (state.p | 0x04) if irq_disabled else (state.p & ~0x04)
        emu.set_p(expected_p)

        body = bytes(
            (
                0xAD,
                0x01,
                0x00,
                0x8D,
                KERNAL_STUB_LAST_PORT & 0xFF,
                KERNAL_STUB_LAST_PORT >> 8,
                0xA9,
                0xA5,
                0xA2,
                0xB6,
                0xA0,
                0xC7,
                0x38,
                0x60,
            )
        )
        install_vector_stub(emu, KERNAL_READST, 0xED00, body)

        emu.execute_rts(_load_symbol_address("kernal_readst"), 10_000)
        result = emu.get_state()
        assert (result.a, result.x, result.y) == (0xA5, 0xB6, 0xC7)
        assert result.p & 0x01
        assert (result.p & 0x04) == (expected_p & 0x04)
        assert emu.read_mem(KERNAL_STUB_LAST_PORT) == 0x36
        assert emu.read_mem(0x0000) == 0x2F
        assert emu.read_mem(0x0001) == 0x35
