"""Unit tests for control runtime helpers (control.asm)."""

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


def _artifact_root() -> Path:
    debug_root = ROOT / "debug" / "runtime_slice"
    return debug_root if debug_root.exists() else ROOT / "build"


def _dll_path() -> Path:
    for candidate in (
        ROOT.parent / "tools" / "emu6502.dll",
        ROOT.parent / "tools" / "msys-emu6502.dll",
    ):
        if candidate.exists():
            return candidate
    pytest.skip("Emulator DLL not found in tools folder.")


def _load_binary(emu: C64Emu6502) -> None:
    payload = (_artifact_root() / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.set_georam_enabled(True)


def _load_symbol_address(symbol_name: str) -> int:
    labels_path = _artifact_root() / "compiler.lbl"
    if labels_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    directory_path = _artifact_root() / "routine_directory.json"
    if directory_path.exists():
        data = json.loads(directory_path.read_text(encoding="utf-8"))
        routine = data.get("routines", {}).get(symbol_name)
        if routine:
            addr = routine.get("address", "")
            if addr.startswith("$"):
                return int(addr[1:], 16)
    map_path = _artifact_root() / "compiler.map"
    match = re.search(
        rf"\b{re.escape(symbol_name)}\b\s+([0-9A-Fa-f]{{6}})",
        map_path.read_text(encoding="utf-8"),
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found.")


def _zp_address(name: str) -> int:
    data = json.loads(
        (ROOT / "build" / "zp_allocation.json").read_text(encoding="utf-8")
    )
    addr = data.get("allocation", {}).get(name, "")
    if addr.startswith("$"):
        return int(addr[1:], 16)
    pytest.fail(f"Zero page symbol '{name}' not found.")


@pytest.mark.unit
@pytest.mark.local
class TestControl:
    """Runtime control helper tests."""

    def test_tagged_push_pop_and_stop_poll(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        push_addr = _load_symbol_address("ctrl_push_loop_frame")
        pop_addr = _load_symbol_address("ctrl_pop_loop_frame")
        check_addr = _load_symbol_address("ctrl_check_stop")

        emu.set_x(0x00)
        emu.set_y(0x60)
        emu.execute(push_addr, 10000)
        emu.execute(pop_addr, 10000)
        state = emu.get_state()
        assert state.x == 0x00 and state.y == 0x60
        emu.execute(pop_addr, 10000)
        assert (emu.get_state().p & 0x01) == 1
        emu.set_p(emu.get_state().p & ~0x01)

        stop_flag = _zp_address("zp_stop_flag")
        emu.write_mem(stop_flag, 1)
        emu.execute(check_addr, 10000)
        assert emu.get_state().a == 0x01

    def test_loop_and_branch_helpers(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        for_addr = _load_symbol_address("ctrl_for_init")
        next_addr = _load_symbol_address("ctrl_for_next")
        loop_addr = _load_symbol_address("ctrl_loop_test")
        on_goto_addr = _load_symbol_address("ctrl_on_goto")
        on_gosub_addr = _load_symbol_address("ctrl_on_gosub")
        exit_addr = _load_symbol_address("ctrl_exit_loop")
        do_addr = _load_symbol_address("ctrl_do_init")
        end_addr = _load_symbol_address("ctrl_end")
        return_addr = _load_symbol_address("ctrl_return")
        gosub_addr = _load_symbol_address("ctrl_gosub")

        emu.write_mem_range(
            0x6000,
            b"F\x02\x20\x60\xff\x00\xff\x7f\x01\x00\x34\x12",
        )
        emu.set_x(0x00)
        emu.set_y(0x60)
        emu.execute(for_addr, 10000)
        emu.execute(next_addr, 10000)
        assert emu.read_mem(0x6020) == 0x00
        assert emu.read_mem(0x6021) == 0x01

        emu.set_a(0x00)
        emu.execute(loop_addr, 10000)
        assert (emu.get_state().p & 0x01) == 1
        emu.set_p(emu.get_state().p & ~0x01)

        emu.write_mem(0x6100, 0x34)
        emu.write_mem(0x6101, 0x12)
        emu.write_mem(0x6102, 0x78)
        emu.write_mem(0x6103, 0x56)
        emu.set_a(0x02)
        emu.set_x(0x00)
        emu.set_y(0x61)
        emu.execute(on_goto_addr, 10000)
        assert emu.get_state().x == 0x78 and emu.get_state().y == 0x56

        emu.set_a(0x00)
        emu.set_x(0x00)
        emu.set_y(0x61)
        emu.execute(on_goto_addr, 10000)
        assert (emu.get_state().p & 0x01) == 1
        emu.set_p(emu.get_state().p & ~0x01)

        emu.set_a(0x01)
        emu.set_x(0x00)
        emu.set_y(0x61)
        emu.execute(on_gosub_addr, 10000)
        emu.execute(return_addr, 10000)
        state = emu.get_state()
        assert (state.x, state.y) == (0x34, 0x12)

        emu.execute(exit_addr, 10000)
        assert (emu.get_state().p & 0x01) == 0

        emu.write_mem_range(0x6020, b"D\x00\x34\x12")
        emu.set_x(0x20)
        emu.set_y(0x60)
        emu.execute(do_addr, 10000)
        emu.execute(exit_addr, 10000)
        state = emu.get_state()
        assert (state.x, state.y) == (0x20, 0x60)

        emu.set_a(0)
        emu.execute(end_addr, 10000)
        emu.set_x(0x40)
        emu.set_y(0x60)
        emu.execute(gosub_addr, 10000)
        emu.execute(return_addr, 10000)
        state = emu.get_state()
        assert (state.x, state.y) == (0x40, 0x60)

    @pytest.mark.parametrize(
        ("start", "limit", "step", "values"),
        [
            (1, 3, 1, [(2, False), (3, False), (4, True)]),
            (3, 1, -1, [(2, False), (1, False), (0, True)]),
            (-2, 2, 2, [(0, False), (2, False), (4, True)]),
        ],
        ids=["positive-step", "negative-step", "signed-range"],
    )
    def test_for_next_honors_signed_limit_and_step(
        self,
        start: int,
        limit: int,
        step: int,
        values: list[tuple[int, bool]],
    ) -> None:
        """FOR frames initialize and advance signed integer loop variables."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        descriptor = 0xC200
        variable = 0xC300
        value_type = 1 if -128 <= start <= 127 and -128 <= limit + step <= 127 else 2
        frame = (
            b"F"
            + bytes([value_type])
            + variable.to_bytes(2, "little")
            + (start & 0xFFFF).to_bytes(2, "little")
            + (limit & 0xFFFF).to_bytes(2, "little")
            + (step & 0xFFFF).to_bytes(2, "little")
            + b"\x34\x12"
        )
        emu.write_mem_range(descriptor, frame)
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)
        emu.execute(_load_symbol_address("ctrl_for_init"), 10000)
        assert (emu.get_state().p & 1) == 0
        initial = emu.read_mem(variable)
        if value_type != 1:
            initial |= emu.read_mem(variable + 1) << 8
        elif initial & 0x80:
            initial |= 0xFF00
        assert initial == start & 0xFFFF

        for expected, done in values:
            emu.set_x(descriptor & 0xFF)
            emu.set_y(descriptor >> 8)
            emu.execute(_load_symbol_address("ctrl_for_next"), 10000)
            actual = emu.read_mem(variable)
            if value_type != 1:
                actual |= emu.read_mem(variable + 1) << 8
            elif actual & 0x80:
                actual |= 0xFF00
            assert actual == expected & 0xFFFF
            assert bool(emu.get_state().p & 1) is done

    @pytest.mark.parametrize(
        ("value_type", "start", "limit", "step", "expected"),
        [(1, 126, 127, 1, 127), (2, 300, 301, 1, 301), (3, 300, 301, 1, 301)],
        ids=["int1", "int2", "int3"],
    )
    def test_for_uses_compiler_assigned_integer_storage_type(
        self, value_type: int, start: int, limit: int, step: int, expected: int
    ) -> None:
        """Specialized FOR frames honor their statically deduced numeric tier."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        descriptor, variable = 0xC700, 0xC800
        emu.write_mem_range(
            descriptor,
            b"F"
            + bytes([value_type])
            + variable.to_bytes(2, "little")
            + start.to_bytes(2, "little", signed=True)
            + limit.to_bytes(2, "little", signed=True)
            + step.to_bytes(2, "little", signed=True)
            + b"\x34\x12",
        )
        for routine in ("ctrl_for_init", "ctrl_for_next"):
            emu.set_x(descriptor & 0xFF)
            emu.set_y(descriptor >> 8)
            emu.execute(_load_symbol_address(routine), 10000)
            assert (emu.get_state().p & 1) == 0
        actual = emu.read_mem(variable)
        if value_type != 1:
            actual |= emu.read_mem(variable + 1) << 8
        assert actual == expected

    def test_generic_integer_for_promotes_int1_to_int2(self) -> None:
        """A non-specialized frame widens rather than wrapping an INT1 variable."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        descriptor, variable = 0xCB00, 0xCC00
        emu.write_mem_range(
            descriptor,
            b"F\x01"
            + variable.to_bytes(2, "little")
            + b"\x7f\x00\x81\x00\x01\x00\x34\x12",
        )
        for routine in ("ctrl_for_init", "ctrl_for_next"):
            emu.set_x(descriptor & 0xFF)
            emu.set_y(descriptor >> 8)
            emu.execute(_load_symbol_address(routine), 10000)
            assert (emu.get_state().p & 1) == 0
        assert emu.read_mem(descriptor + 1) == 2
        assert emu.read_mem(variable) | (emu.read_mem(variable + 1) << 8) == 128

    def test_int3_for_comparison_is_unsigned(self) -> None:
        """INT3 high-bit values sort above every nonnegative signed limit."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        descriptor, variable = 0xCD00, 0xCE00
        emu.write_mem_range(
            descriptor,
            b"F\x03"
            + variable.to_bytes(2, "little")
            + b"\xff\x7f\xff\x7f\x01\x00\x34\x12",
        )
        for routine in ("ctrl_for_init", "ctrl_for_next"):
            emu.set_x(descriptor & 0xFF)
            emu.set_y(descriptor >> 8)
            emu.execute(_load_symbol_address(routine), 10000)
        assert emu.read_mem(variable) | (emu.read_mem(variable + 1) << 8) == 32768
        assert emu.get_state().p & 1

    def test_generic_float_for_uses_packed_numeric_runtime(self) -> None:
        """A FLOAT loop variable advances through the canonical packed math path."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        descriptor, variable = 0xC900, 0xCA00
        emu.write_mem_range(
            descriptor,
            b"F\x00"
            + variable.to_bytes(2, "little")
            + b"\x01\x00\x03\x00\x01\x00\x34\x12",
        )
        for expected, done in ((2, False), (3, False), (4, True)):
            if expected == 2:
                emu.set_x(descriptor & 0xFF)
                emu.set_y(descriptor >> 8)
                emu.execute(_load_symbol_address("ctrl_for_init"), 10000)
                assert bytes(emu.read_mem(variable + i) for i in range(5)) == bytes(
                    [0x81, 0, 0, 0, 0]
                )
            emu.set_x(descriptor & 0xFF)
            emu.set_y(descriptor >> 8)
            emu.execute(_load_symbol_address("ctrl_for_next"), 10000)
            carry = bool(emu.get_state().p & 1)
            fac = _zp_address("zp_fac1")
            emu.write_mem_range(
                fac, bytes(emu.read_mem(variable + i) for i in range(5))
            )
            packed = bytes(emu.read_mem(variable + i) for i in range(5))
            emu.write_mem(_load_symbol_address("math_fac_type"), 0)
            emu.execute(_load_symbol_address("math_float_to_int"), 10000)
            state = emu.get_state()
            assert (state.x | (state.y << 8)) == expected, packed.hex()
            assert carry is done

    @pytest.mark.parametrize(
        ("flags", "condition", "exits"),
        [(0, 0, False), (1, 0, True), (1, 1, False), (3, 0, False), (3, 1, True)],
        ids=["bare", "while-false", "while-true", "until-false", "until-true"],
    )
    def test_loop_condition_modes(
        self, flags: int, condition: int, exits: bool
    ) -> None:
        """LOOP supports bare, WHILE, and UNTIL post-tests."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        descriptor = 0xC400
        emu.write_mem_range(descriptor, b"D" + bytes([flags]) + b"\x78\x56")
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)
        emu.execute(_load_symbol_address("ctrl_do_init"), 10000)
        assert (emu.get_state().p & 1) == 0
        emu.set_a(condition)
        emu.set_x(descriptor & 0xFF)
        emu.set_y(descriptor >> 8)
        emu.execute(_load_symbol_address("ctrl_loop_test"), 10000)
        assert bool(emu.get_state().p & 1) is exits

    def test_continuation_snapshot_validates_generation_and_restores_stack(
        self,
    ) -> None:
        """STOP/CONT persists the complete tagged control stack."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        loop = 0xC500
        continuation = 0xC600
        emu.write_mem_range(loop, b"D\x00\x34\x12")
        emu.set_x(loop & 0xFF)
        emu.set_y(loop >> 8)
        emu.execute(_load_symbol_address("ctrl_do_init"), 10000)
        emu.write_mem_range(continuation, b"C\x2a\x78\x56" + bytes(35))
        emu.set_x(continuation & 0xFF)
        emu.set_y(continuation >> 8)
        emu.execute(_load_symbol_address("ctrl_stop"), 10000)
        assert (emu.get_state().p & 1) == 0

        emu.execute(_load_symbol_address("ctrl_exit_loop"), 10000)
        emu.set_x(continuation & 0xFF)
        emu.set_y(continuation >> 8)
        emu.execute(_load_symbol_address("ctrl_cont"), 10000)
        assert (emu.get_state().p & 1) == 0
        assert (emu.get_state().x, emu.get_state().y) == (0x78, 0x56)
        emu.execute(_load_symbol_address("ctrl_exit_loop"), 10000)
        assert (emu.get_state().x, emu.get_state().y) == (loop & 0xFF, loop >> 8)

        emu.write_mem(continuation + 1, 0x2B)
        emu.set_x(continuation & 0xFF)
        emu.set_y(continuation >> 8)
        emu.execute(_load_symbol_address("ctrl_cont"), 10000)
        assert (emu.get_state().p & 1) == 1

    def test_end_exits_graphics_and_enters_development_ready_shell(self) -> None:
        """END restores text mode and publishes the development READY prompt."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.write_mem(0xD011, 0x3B)
        emu.write_mem(0xD018, 0x18)
        emu.write_mem(0xD020, 0x06)
        emu.write_mem(0xD021, 0x06)
        emu.write_mem(0x00D3, 0)
        emu.write_mem(0x00D6, 0)
        emu.write_mem_range(0x0400, b" " * 40)

        emu.set_a(0)
        emu.execute(_load_symbol_address("ctrl_end"), 100000)

        assert emu.read_mem(0xD011) == 0x1B
        assert emu.read_mem(0xD018) == 0x17
        assert emu.read_mem(0xD020) == 0x00
        assert emu.read_mem(0xD021) == 0x0E
        assert emu.read_mem(_load_symbol_address("kernal_output_byte")) == 0x0D

    def test_end_enters_standalone_inspection_shell(self) -> None:
        """Standalone END restores text mode and remains in its READY loop."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.write_mem(0xD011, 0x3B)
        emu.write_mem(0x00D3, 0)
        emu.write_mem(0x00D6, 0)
        emu.write_mem_range(0x0400, b" " * 40)

        emu.set_a(1)
        emu.execute(_load_symbol_address("ctrl_end"), 100000)

        assert emu.read_mem(0xD011) == 0x1B
        assert emu.read_mem(_load_symbol_address("kernal_output_byte")) == 0x0D
