"""Unit tests for math runtime helpers (math_core.asm)."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
PROJECT_TOOLS_ROOT = ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
if str(PROJECT_TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_TOOLS_ROOT))

from numeric.c64float import add, div, from_float, mul, sqr, sub  # noqa: E402

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    pass


def _artifact_root() -> Path:
    return ROOT / "build"


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
    hibasic = _artifact_root() / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
        emu.write_mem(0x0001, 0x35)
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


def _set_value(emu: C64Emu6502, base: int, value: int) -> None:
    emu.write_mem(base + 3, value & 0xFF)
    emu.write_mem(base + 4, (value >> 8) & 0xFF)
    emu.write_mem(base, 0x00 if value >= 0 else 0x80)


def _get_value(emu: C64Emu6502, base: int) -> int:
    value = emu.read_mem(base + 3) | (emu.read_mem(base + 4) << 8)
    return int(-((~value + 1) & 0xFFFF) if emu.read_mem(base) & 0x80 else value)


def _set_float(emu: C64Emu6502, base: int, value: float) -> bytes:
    packed = from_float(value).to_bytes()
    for offset, byte in enumerate(packed):
        emu.write_mem(base + offset, byte)
    return packed


def _set_packed(emu: C64Emu6502, base: int, packed: bytes) -> None:
    """Write one exact packed C64 float without host-float conversion."""
    for offset, byte in enumerate(packed):
        emu.write_mem(base + offset, byte)


def _get_float_bytes(emu: C64Emu6502, base: int) -> bytes:
    return bytes(emu.read_mem(base + offset) for offset in range(5))


@pytest.mark.unit
@pytest.mark.local
class TestMathCore:
    """Runtime math helper tests."""

    @pytest.mark.callable_coverage("math_sub", executor="execute_rts")
    @pytest.mark.callable_coverage("math_sqr", executor="execute_rts")
    @pytest.mark.callable_coverage("math_mul", executor="execute_rts")
    @pytest.mark.callable_coverage("math_div", executor="execute_rts")
    @pytest.mark.callable_coverage("math_add", executor="execute_rts")
    def test_add_sub_mul_div(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        zp_fac1 = _zp_address("zp_fac1")
        zp_arg = _zp_address("zp_arg")

        left = _set_float(emu, zp_fac1, 5)
        right = _set_float(emu, zp_arg, 7)
        emu.execute(_load_symbol_address("math_add"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == add(left, right)

        left = _set_float(emu, zp_fac1, 12)
        right = _set_float(emu, zp_arg, 7)
        emu.execute(_load_symbol_address("math_sub"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == sub(left, right)

        left = _set_float(emu, zp_fac1, 3)
        right = _set_float(emu, zp_arg, 4)
        emu.execute(_load_symbol_address("math_mul"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == mul(left, right)

        left = _set_float(emu, zp_fac1, 12)
        right = _set_float(emu, zp_arg, 4)
        emu.execute(_load_symbol_address("math_div"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == div(left, right)

        value = _set_float(emu, zp_fac1, 9)
        emu.execute(_load_symbol_address("math_sqr"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == sqr(value)

    @pytest.mark.parametrize(
        ("routine", "oracle", "left", "right"),
        [
            ("math_add", add, -5.5, 5.5),
            ("math_add", add, 1.0, 2.0**-20),
            ("math_sub", sub, -5.5, -2.25),
            ("math_sub", sub, 1.0, 1.0),
            ("math_mul", mul, -3.25, 2.5),
            ("math_mul", mul, 0.0, -32768.0),
            ("math_div", div, -13.0, 4.0),
            ("math_div", div, 0.0, -7.0),
        ],
    )
    def test_binary_float_sign_zero_and_rounding_edges(
        self,
        routine: str,
        oracle: Callable[[bytes, bytes], bytes],
        left: float,
        right: float,
    ) -> None:
        """Binary entries match the packed-float oracle at semantic edges."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        left_packed = _set_float(emu, _zp_address("zp_fac1"), left)
        right_packed = _set_float(emu, _zp_address("zp_arg"), right)

        emu.execute(_load_symbol_address(routine), 10000)

        assert _get_float_bytes(emu, _zp_address("zp_fac1")) == oracle(
            left_packed, right_packed
        )
        assert (emu.get_state().p & 0x01) == 0

    @pytest.mark.parametrize(
        ("routine", "oracle", "left", "right"),
        [
            ("math_add", add, bytes.fromhex("8100000000"), bytes.fromhex("6100000000")),
            ("math_add", add, bytes.fromhex("8100000000"), bytes.fromhex("6100000001")),
            ("math_sub", sub, bytes.fromhex("ff7fffffff"), bytes.fromhex("fe7fffffff")),
            ("math_sub", sub, bytes.fromhex("8100000001"), bytes.fromhex("8100000000")),
            ("math_mul", mul, bytes.fromhex("fe7fffffff"), bytes.fromhex("8040000000")),
            ("math_mul", mul, bytes.fromhex("8180000000"), bytes.fromhex("0100000000")),
            ("math_div", div, bytes.fromhex("ff7fffffff"), bytes.fromhex("fe7fffffff")),
            ("math_div", div, bytes.fromhex("8180000000"), bytes.fromhex("8140000000")),
        ],
    )
    def test_binary_float_exact_extreme_and_rounding_matrix(
        self,
        routine: str,
        oracle: Callable[[bytes, bytes], bytes],
        left: bytes,
        right: bytes,
    ) -> None:
        """Direct entries match the exact oracle beyond host-float precision."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        _set_packed(emu, _zp_address("zp_fac1"), left)
        _set_packed(emu, _zp_address("zp_arg"), right)

        emu.execute(_load_symbol_address(routine), 20000)

        assert _get_float_bytes(emu, _zp_address("zp_fac1")) == oracle(left, right)
        assert (emu.get_state().p & 0x01) == 0

    @pytest.mark.parametrize("routine", ["math_negate", "math_abs"])
    @pytest.mark.parametrize(
        "packed", [bytes(5), bytes.fromhex("0100000000"), bytes.fromhex("ff7fffffff")]
    )
    @pytest.mark.callable_coverage("math_negate", executor="execute_rts")
    @pytest.mark.callable_coverage("math_abs", executor="execute_rts")
    def test_unary_float_exact_exponent_extremes(
        self, routine: str, packed: bytes
    ) -> None:
        """Unary sign operations preserve every exponent and magnitude bit."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        _set_packed(emu, _zp_address("zp_fac1"), packed)

        emu.execute(_load_symbol_address(routine), 10000)

        expected = bytearray(packed)
        if expected[0] != 0 and routine == "math_negate":
            expected[1] ^= 0x80
        if routine == "math_abs":
            expected[1] &= 0x7F
        assert _get_float_bytes(emu, _zp_address("zp_fac1")) == bytes(expected)
        assert (emu.get_state().p & 0x01) == 0

    @pytest.mark.callable_coverage("math_div", executor="execute_rts")
    def test_divide_by_zero_reports_error_without_fabricating_result(self) -> None:
        """Division by zero sets carry and preserves the dividend in FAC."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        original = _set_float(emu, _zp_address("zp_fac1"), 12.5)
        _set_float(emu, _zp_address("zp_arg"), 0.0)

        emu.execute(_load_symbol_address("math_div"), 10000)

        assert (emu.get_state().p & 0x01) == 1
        assert _get_float_bytes(emu, _zp_address("zp_fac1")) == original

    @pytest.mark.callable_coverage("math_mul", executor="execute_rts")
    def test_float_underflow_flushes_to_canonical_zero(self) -> None:
        """A result below the smallest packed exponent becomes positive zero."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        _set_packed(emu, _zp_address("zp_fac1"), bytes.fromhex("0100000000"))
        _set_packed(emu, _zp_address("zp_arg"), bytes.fromhex("8000000000"))

        emu.execute(_load_symbol_address("math_mul"), 20000)

        assert _get_float_bytes(emu, _zp_address("zp_fac1")) == bytes(5)
        assert (emu.get_state().p & 0x01) == 0

    @pytest.mark.callable_coverage("math_mul", executor="execute_rts")
    @pytest.mark.callable_coverage("math_add", executor="execute_rts")
    @pytest.mark.parametrize("routine", ["math_add", "math_mul", "math_div"])
    def test_float_overflow_reports_error(self, routine: str) -> None:
        """Exponent overflow is reported instead of publishing wrapped success."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        maximum = bytes.fromhex("ff7fffffff")
        _set_packed(emu, _zp_address("zp_fac1"), maximum)
        if routine == "math_add":
            operand = maximum
        elif routine == "math_mul":
            operand = bytes.fromhex("8200000000")
        else:
            operand = bytes.fromhex("7f00000000")
        _set_packed(emu, _zp_address("zp_arg"), operand)

        emu.execute(_load_symbol_address(routine), 20000)

        assert (emu.get_state().p & 0x01) == 1

    @pytest.mark.callable_coverage("math_sgn", executor="execute_rts")
    @pytest.mark.callable_coverage("math_negate", executor="execute_rts")
    @pytest.mark.callable_coverage("math_int_to_float", executor="execute_rts")
    @pytest.mark.callable_coverage("math_int", executor="execute_rts")
    @pytest.mark.callable_coverage("math_float_to_int", executor="execute_rts")
    @pytest.mark.callable_coverage("math_abs", executor="execute_rts")
    def test_unary_and_conversion_helpers(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        zp_fac1 = _zp_address("zp_fac1")

        _set_float(emu, zp_fac1, 5)
        emu.execute(_load_symbol_address("math_negate"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == from_float(-5).to_bytes()

        _set_float(emu, zp_fac1, -5)
        emu.execute(_load_symbol_address("math_abs"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == from_float(5).to_bytes()

        _set_float(emu, zp_fac1, 0)
        emu.execute(_load_symbol_address("math_sgn"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == from_float(0).to_bytes()

        _set_float(emu, zp_fac1, -5)
        emu.execute(_load_symbol_address("math_int"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == from_float(-5).to_bytes()

        emu.set_x(0x34)
        emu.set_y(0x12)
        emu.execute(_load_symbol_address("math_int_to_float"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == from_float(0x1234).to_bytes()

        emu.execute(_load_symbol_address("math_float_to_int"), 10000)
        state = emu.get_state()
        assert state.x == 0x34 and state.y == 0x12

        emu.set_x(1)
        emu.set_y(0)
        emu.execute(_load_symbol_address("math_int_to_float"), 10000)
        _set_float(emu, zp_fac1, -123)
        emu.execute(_load_symbol_address("math_float_to_int"), 10000)
        state = emu.get_state()
        assert (state.x, state.y) == (0x85, 0xFF)
        assert (state.p & 0x01) == 0

        emu.set_x(1)
        emu.set_y(0)
        emu.execute(_load_symbol_address("math_int_to_float"), 10000)
        _set_float(emu, zp_fac1, 1.5)
        emu.execute(_load_symbol_address("math_float_to_int"), 10000)
        assert (emu.get_state().p & 0x01) == 1

    @pytest.mark.callable_coverage("math_int_to_float", executor="execute_rts")
    @pytest.mark.callable_coverage("math_float_to_int", executor="execute_rts")
    @pytest.mark.parametrize("value", [-32768, -1, 0, 1, 32767])
    def test_signed_int_float_conversion_boundaries(self, value: int) -> None:
        """Every signed 16-bit boundary round-trips through packed float."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.set_x(value & 0xFF)
        emu.set_y((value >> 8) & 0xFF)
        emu.execute(_load_symbol_address("math_int_to_float"), 10000)
        assert (
            _get_float_bytes(emu, _zp_address("zp_fac1"))
            == from_float(float(value)).to_bytes()
        )
        emu.execute(_load_symbol_address("math_float_to_int"), 10000)
        state = emu.get_state()
        assert (state.x | (state.y << 8)) == (value & 0xFFFF)
        assert (state.p & 0x01) == 0

    @pytest.mark.callable_coverage("math_float_to_int", executor="execute_rts")
    @pytest.mark.parametrize("value", [-32769.0, 32768.0, -1.5, 1.5])
    def test_float_to_int_rejects_out_of_range_or_fractional_values(
        self, value: float
    ) -> None:
        """Narrowing rejects values that have no exact signed-16 representation."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        _set_float(emu, _zp_address("zp_fac1"), value)
        emu.execute(_load_symbol_address("math_float_to_int"), 10000)
        assert (emu.get_state().p & 0x01) == 1

    @pytest.mark.parametrize(
        ("value", "expected_a", "negative", "zero"),
        [
            (-1.0, 0xFF, True, False),
            (0.0, 0x00, False, True),
            (1.0, 0x01, False, False),
        ],
    )
    @pytest.mark.callable_coverage("math_fpe", executor="execute_rts")
    def test_fpe_sets_branch_flags(
        self, value: float, expected_a: int, negative: bool, zero: bool
    ) -> None:
        """FPE exposes canonical A, N, and Z classes for branch consumers."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        _set_float(emu, _zp_address("zp_fac1"), value)
        emu.execute(_load_symbol_address("math_fpe"), 10000)
        state = emu.get_state()
        assert state.a == expected_a
        assert bool(state.p & 0x80) is negative
        assert bool(state.p & 0x02) is zero

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0.0, 0.0),
            (0.25, 0.0),
            (0.999999, 0.0),
            (1.25, 1.0),
            (127.999, 127.0),
            (-0.25, -1.0),
            (-0.999999, -1.0),
            (-1.25, -2.0),
            (-127.001, -128.0),
            (32767.75, 32767.0),
            (-32768.25, -32769.0),
            (2147483647.0, 2147483647.0),
            (-2147483648.0, -2147483648.0),
        ],
    )
    @pytest.mark.callable_coverage("math_int", executor="execute_rts")
    def test_int_uses_stock_floor_semantics(
        self, value: float, expected: float
    ) -> None:
        """INT floors finite packed values, including negative fractions."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        zp_fac1 = _zp_address("zp_fac1")
        _set_float(emu, zp_fac1, value)

        emu.execute(_load_symbol_address("math_int"), 10000)

        assert _get_float_bytes(emu, zp_fac1) == from_float(expected).to_bytes()
        assert (emu.get_state().p & 0x01) == 0

    @pytest.mark.parametrize(
        ("value", "expected"), [(-9.0, -1.0), (0.0, 0.0), (9.0, 1.0)]
    )
    @pytest.mark.callable_coverage("math_sgn", executor="execute_rts")
    def test_sgn_direct_cases(self, value: float, expected: float) -> None:
        """SGN returns a packed -1, 0, or 1 for every sign class."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        zp_fac1 = _zp_address("zp_fac1")
        _set_float(emu, zp_fac1, value)
        emu.execute(_load_symbol_address("math_sgn"), 10000)
        assert _get_float_bytes(emu, zp_fac1) == from_float(expected).to_bytes()

    @pytest.mark.parametrize(
        ("left", "right", "expected"),
        [(3.0, 7.0, 0xFF), (7.0, 7.0, 0x00), (9.0, -2.0, 0x01)],
    )
    @pytest.mark.callable_coverage("math_cmp", executor="execute_rts")
    def test_cmp_direct_ordering(
        self, left: float, right: float, expected: int
    ) -> None:
        """CMP returns the canonical negative, equal, and positive classes."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        _set_float(emu, _zp_address("zp_fac1"), left)
        _set_float(emu, _zp_address("zp_arg"), right)
        emu.execute(_load_symbol_address("math_cmp"), 10000)
        assert emu.get_state().a == expected

    @pytest.mark.parametrize(
        ("left_type", "left", "right_type", "right", "expected"),
        [
            (1, -1, 2, -1, 0x00),
            (1, -128, 2, 127, 0xFF),
            (2, 127, 1, -128, 0x01),
            (3, 65535, 2, -1, 0x01),
            (2, -1, 3, 0, 0xFF),
            (3, 32768, 2, 32767, 0x01),
            (2, 32767, 3, 32768, 0xFF),
        ],
        ids=[
            "int1-sign-extends-equal",
            "int1-negative-vs-int2-positive",
            "int2-positive-vs-int1-negative",
            "int3-max-vs-int2-negative",
            "int2-negative-vs-int3-zero",
            "int3-high-bit-is-unsigned",
            "int2-max-vs-int3-high-bit",
        ],
    )
    @pytest.mark.callable_coverage("math_cmp", executor="execute_rts")
    def test_mixed_adaptive_integer_comparison(
        self,
        left_type: int,
        left: int,
        right_type: int,
        right: int,
        expected: int,
    ) -> None:
        """Mixed integer tiers compare with signed extension and unsigned INT3."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        fac, arg = _zp_address("zp_fac1"), _zp_address("zp_arg")
        emu.write_mem(fac, left & 0xFF)
        emu.write_mem(fac + 1, (left >> 8) & 0xFF)
        emu.write_mem(arg, right & 0xFF)
        emu.write_mem(arg + 1, (right >> 8) & 0xFF)
        emu.write_mem(_load_symbol_address("math_fac_type"), left_type)
        emu.write_mem(_load_symbol_address("math_arg_type"), right_type)
        emu.execute(_load_symbol_address("math_cmp"), 10000)
        assert emu.get_state().a == expected

    @pytest.mark.callable_coverage("math_sub_int", executor="execute_rts")
    @pytest.mark.callable_coverage("math_mul_int", executor="execute_rts")
    @pytest.mark.callable_coverage("math_fpe", executor="execute_rts")
    @pytest.mark.callable_coverage("math_div_int", executor="execute_rts")
    @pytest.mark.callable_coverage("math_cmp", executor="execute_rts")
    @pytest.mark.callable_coverage("math_add_int", executor="execute_rts")
    def test_cmp_fpe_and_int_helpers(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        zp_fac1 = _zp_address("zp_fac1")
        zp_arg = _zp_address("zp_arg")

        _set_float(emu, zp_fac1, 3)
        _set_float(emu, zp_arg, 7)
        emu.execute(_load_symbol_address("math_cmp"), 10000)
        assert emu.get_state().a == 0xFF

        emu.execute(_load_symbol_address("math_fpe"), 10000)
        assert emu.get_state().a is not None

        emu.write_mem(0x5000, 0x02)
        emu.write_mem(0x5001, 0x00)
        emu.write_mem(0x5002, 0x03)
        emu.write_mem(0x5003, 0x00)
        emu.set_x(0x00)
        emu.set_y(0x50)
        emu.execute(_load_symbol_address("math_add_int"), 10000)
        assert emu.read_mem(0x5000) == 0x05

        emu.write_mem(0x5020, 0x09)
        emu.write_mem(0x5021, 0x00)
        emu.write_mem(0x5022, 0x04)
        emu.write_mem(0x5023, 0x00)
        emu.set_x(0x20)
        emu.set_y(0x50)
        emu.execute(_load_symbol_address("math_sub_int"), 10000)
        assert emu.read_mem(0x5020) == 0x05

        emu.write_mem(0x5040, 0x03)
        emu.write_mem(0x5041, 0x00)
        emu.write_mem(0x5042, 0x04)
        emu.write_mem(0x5043, 0x00)
        emu.set_x(0x40)
        emu.set_y(0x50)
        emu.execute(_load_symbol_address("math_mul_int"), 10000)
        assert emu.read_mem(0x5040) == 0x0C

        emu.write_mem(0x5100, 0x05)
        emu.write_mem(0x5101, 0x00)
        emu.write_mem(0x5102, 0x02)
        emu.write_mem(0x5103, 0x00)
        emu.set_x(0x00)
        emu.set_y(0x51)
        emu.execute(_load_symbol_address("math_div_int"), 10000)
        assert (emu.get_state().p & 0x01) == 0
        assert bytes(emu.read_mem(0x5100 + i) for i in range(2)) == b"\x02\x00"

        emu.write_mem_range(0x5120, bytes([0xF7, 0xFF, 0x02, 0x00]))
        emu.set_x(0x20)
        emu.set_y(0x51)
        emu.execute(_load_symbol_address("math_div_int"), 10000)
        assert bytes(emu.read_mem(0x5120 + i) for i in range(2)) == b"\xfc\xff"
        assert (emu.get_state().p & 0x01) == 0

        emu.write_mem_range(0x5140, bytes([0x05, 0x00, 0x00, 0x00]))
        emu.set_x(0x40)
        emu.set_y(0x51)
        emu.execute(_load_symbol_address("math_div_int"), 10000)
        assert (emu.get_state().p & 0x01) == 1

    @pytest.mark.parametrize(
        ("routine", "left", "right", "expected", "error"),
        [
            ("math_add_int", 32767, 0, 32767, False),
            ("math_add_int", -32768, 0, -32768, False),
            ("math_add_int", 32767, 1, None, True),
            ("math_add_int", -32768, -1, None, True),
            ("math_sub_int", -32768, 0, -32768, False),
            ("math_sub_int", 32767, -1, None, True),
            ("math_sub_int", -32768, 1, None, True),
            ("math_mul_int", 181, 181, 32761, False),
            ("math_mul_int", -16384, 2, -32768, False),
            ("math_mul_int", -32768, -1, None, True),
            ("math_mul_int", 32767, 2, None, True),
            ("math_mul_int", 0, -32768, 0, False),
            ("math_div_int", -32768, 1, -32768, False),
            ("math_div_int", -32768, -1, None, True),
            ("math_div_int", -9, 2, -4, False),
            ("math_div_int", 9, -2, -4, False),
            ("math_div_int", 5, 0, None, True),
        ],
    )
    def test_signed_int_arithmetic_full_word_and_errors(
        self,
        routine: str,
        left: int,
        right: int,
        expected: int | None,
        error: bool,
    ) -> None:
        """Integer helpers return exact words and reject non-representable results."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        address = 0x5200
        original = (left & 0xFFFF).to_bytes(2, "little") + (right & 0xFFFF).to_bytes(
            2, "little"
        )
        emu.write_mem_range(address, original)
        emu.set_x(address & 0xFF)
        emu.set_y(address >> 8)

        emu.execute(_load_symbol_address(routine), 100000)

        assert bool(emu.get_state().p & 0x01) is error
        result = bytes(emu.read_mem(address + offset) for offset in range(2))
        if error:
            assert result == original[:2]
        else:
            assert expected is not None
            assert result == (expected & 0xFFFF).to_bytes(2, "little")

    @pytest.mark.callable_coverage("math_u24_to_float", executor="execute_rts")
    @pytest.mark.parametrize("value", [0, 1, 255, 65535, 0xFFFFFF])
    def test_unsigned_24_bit_to_float_is_exact(self, value: int) -> None:
        """The shared u24 conversion exactly covers the complete jiffy domain."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.set_a(value & 0xFF)
        emu.set_x((value >> 8) & 0xFF)
        emu.set_y((value >> 16) & 0xFF)
        emu.execute(_load_symbol_address("math_u24_to_float"), 10000)
        fac = _zp_address("zp_fac1")
        actual = bytes(emu.read_mem(fac + offset) for offset in range(5))
        assert actual == from_float(float(value)).to_bytes()
        assert not (emu.get_state().p & 1)
