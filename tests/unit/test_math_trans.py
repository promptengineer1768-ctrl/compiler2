"""Unit tests for transcendental math routines (math_trans.asm).

Tests verify LOG, EXP, SQR, POW, RND, FMA, and IEEE extension functions
against stock BASIC V2 values and legacy project Python proxy accuracy fixtures.
"""

from __future__ import annotations

import json
import math
import re
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
PROJECT_TOOLS_ROOT = ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
if str(PROJECT_TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_TOOLS_ROOT))

from numeric.c64float import C64Float, from_float  # noqa: E402

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    pass


def _load_zp_address(name: str) -> int:
    """Load zero-page symbol address from allocation."""
    path = ROOT / "build" / "zp_allocation.json"
    if not path.exists():
        pytest.fail("build/zp_allocation.json not found. Run build.ps1 first.")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    addr_str = data.get("allocation", {}).get(name, "")
    if addr_str.startswith("$"):
        return int(addr_str[1:], 16)
    pytest.fail(f"Zero page symbol '{name}' not found in allocation.")


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _load_symbol_address(symbol_name: str) -> int:
    """Load symbol address from compiler.map or routine_directory.json."""
    labels_path = ROOT / "build" / "compiler.lbl"
    if labels_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels_path.read_text(encoding="utf-8"),
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
        pytest.fail(
            f"build/compiler.map not found. Run build.ps1 first. Missing: {symbol_name}"
        )

    pattern = rf"\b{symbol_name}\b\s+([0-9A-Fa-f]{{6}})"
    content = map_path.read_text(encoding="utf-8")
    match = re.search(pattern, content)
    if match:
        return int(match.group(1), 16)

    pytest.fail(
        f"Symbol '{symbol_name}' not found in compiler.map or routine directory."
    )


def _load_compiler_image(emu: C64Emu6502) -> None:
    """Load the linked compiler image and optional high-memory sidecar."""
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])

    hibasic_path = ROOT / "build" / "hibasic.bin"
    if hibasic_path.exists():
        emu.write_mem_range(0xE000, hibasic_path.read_bytes())
        emu.write_mem(0x0001, 0x35)
    setattr(emu, "_compiler2_real_bytes_only", True)


def _load_float_from_fac1(emu: C64Emu6502, zp_fac1: int) -> float:
    """Load a C64 5-byte packed float from FAC1 zero-page location."""
    bytes_data = emu.read_mem_range(zp_fac1, zp_fac1 + 4)
    return _decode_c64_float(bytes_data)


def _write_float_to_fac1(emu: C64Emu6502, zp_fac1: int, value: float) -> None:
    """Store one finite Python value in FAC1 using the shared C64 model."""
    emu.write_mem_range(zp_fac1, from_float(value).to_bytes())


def _decode_c64_float(data: bytes) -> float:
    """Decode a C64 5-byte packed float to Python float."""
    if len(data) != 5:
        return 0.0
    return C64Float.from_bytes(data).to_float()


@pytest.mark.unit
@pytest.mark.local
class TestMathLog:
    """LOG (natural logarithm) function tests."""

    def test_log_one(self) -> None:
        """LOG(1) should return 0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_rom_overlay_enabled(True)

        addr = _load_symbol_address("math_log")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 1.0 to FAC1
        emu.write_mem(zp_fac1, 0x81)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 100_000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result) < 1e-6, f"LOG(1) should be ~0, got {result}"

    def test_log_e(self) -> None:
        """LOG(e) should return ~1.0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_rom_overlay_enabled(True)

        addr = _load_symbol_address("math_log")
        zp_fac1 = _load_zp_address("zp_fac1")

        _write_float_to_fac1(emu, zp_fac1, math.e)

        emu.execute(addr, 100_000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 1.0) < 0.001, f"LOG(e) should be ~1.0, got {result}"

    def test_log_positive(self) -> None:
        """LOG(10) should return ~2.302585."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_rom_overlay_enabled(True)

        addr = _load_symbol_address("math_log")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 10.0 to FAC1
        emu.write_mem(zp_fac1, 0x84)
        emu.write_mem(zp_fac1 + 1, 0x20)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 100_000)

        result = _load_float_from_fac1(emu, zp_fac1)
        expected = math.log(10)
        assert (
            abs(result - expected) < 0.001
        ), f"LOG(10) should be ~{expected}, got {result}"


@pytest.mark.unit
@pytest.mark.local
class TestMathExp:
    """EXP function tests."""

    def test_exp_zero(self) -> None:
        """EXP(0) should return 1.0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_exp")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 0.0 to FAC1
        emu.write_mem(zp_fac1, 0x00)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 1.0) < 0.001, f"EXP(0) should be ~1.0, got {result}"

    def test_exp_one(self) -> None:
        """EXP(1) should return ~e."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_exp")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 1.0 to FAC1
        emu.write_mem(zp_fac1, 0x81)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        expected = math.e
        assert (
            abs(result - expected) < 0.01
        ), f"EXP(1) should be ~e={expected}, got {result}"


@pytest.mark.unit
@pytest.mark.local
class TestMathSqr:
    """SQR (square root) function tests."""

    def test_sqr_zero(self) -> None:
        """SQR(0) should return 0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_sqr")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 0.0 to FAC1
        emu.write_mem(zp_fac1, 0x00)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result) < 1e-6, f"SQR(0) should be ~0, got {result}"

    def test_sqr_four(self) -> None:
        """SQR(4) should return 2.0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_sqr")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 4.0 to FAC1
        emu.write_mem(zp_fac1, 0x83)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 2.0) < 0.001, f"SQR(4) should be ~2.0, got {result}"

    def test_sqr_nine(self) -> None:
        """SQR(9) should return 3.0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_sqr")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 9.0 to FAC1
        emu.write_mem(zp_fac1, 0x84)
        emu.write_mem(zp_fac1 + 1, 0x10)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 3.0) < 0.001, f"SQR(9) should be ~3.0, got {result}"


@pytest.mark.unit
@pytest.mark.local
class TestMathPow:
    """Exponentiation (math_pow) tests."""

    def test_pow_two_three(self) -> None:
        """2^3 should return 8.0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_pow")
        zp_fac1 = _load_zp_address("zp_fac1")
        zp_arg = _load_zp_address("zp_arg")

        # Write 2.0 to FAC1 (base)
        emu.write_mem(zp_fac1, 0x82)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        # Write 3.0 to ARG (exponent)
        emu.write_mem(zp_arg, 0x82)
        emu.write_mem(zp_arg + 1, 0x40)
        emu.write_mem(zp_arg + 2, 0x00)
        emu.write_mem(zp_arg + 3, 0x00)
        emu.write_mem(zp_arg + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 8.0) < 0.01, f"2^3 should be ~8.0, got {result}"


@pytest.mark.unit
@pytest.mark.local
class TestMathRnd:
    """RND (random number) function tests."""

    def test_rnd_negative_argument(self) -> None:
        """RND with negative argument should seed RNG."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_rnd")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write -1.0 to FAC1 (seed)
        emu.write_mem(zp_fac1, 0x81)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x80)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert 0.0 <= result <= 1.0, f"RND(-1) should be in [0,1], got {result}"

    def test_rnd_positive_argument(self) -> None:
        """RND with positive argument should return value in [0,1]."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_rnd")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 1.0 to FAC1
        emu.write_mem(zp_fac1, 0x81)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert 0.0 <= result <= 1.0, f"RND(1) should be in [0,1], got {result}"


@pytest.mark.unit
@pytest.mark.local
class TestMathFma:
    """Fused multiply-add (math_fma) tests."""

    def test_fma_basic(self) -> None:
        """FMA(2, 3, 1) should return 7.0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_fma")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write operand record to a known location (e.g., $1000)
        # Record format: a(5 bytes) + b(5 bytes) + c(5 bytes) = 15 bytes
        # a=2.0
        emu.write_mem(0x1000, 0x82)
        emu.write_mem(0x1001, 0x00)
        emu.write_mem(0x1002, 0x00)
        emu.write_mem(0x1003, 0x00)
        emu.write_mem(0x1004, 0x00)
        # b=3.0
        emu.write_mem(0x1005, 0x82)
        emu.write_mem(0x1006, 0x40)
        emu.write_mem(0x1007, 0x00)
        emu.write_mem(0x1008, 0x00)
        emu.write_mem(0x1009, 0x00)
        # c=1.0
        emu.write_mem(0x100A, 0x81)
        emu.write_mem(0x100B, 0x00)
        emu.write_mem(0x100C, 0x00)
        emu.write_mem(0x100D, 0x00)
        emu.write_mem(0x100E, 0x00)

        # Set X/Y to point to operand record
        emu.set_x(0x00)
        emu.set_y(0x10)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 7.0) < 0.01, f"FMA(2,3,1) should be ~7.0, got {result}"


@pytest.mark.unit
@pytest.mark.local
class TestMathIEEEExtensions:
    """IEEE extension function tests."""

    @pytest.mark.parametrize(
        ("dividend", "divisor"),
        [(7.0, 3.0), (7.0, 2.0), (-7.0, 2.0), (5.0, 2.0)],
        ids=["positive", "nearest-not-fmod", "negative", "tie-even"],
    )
    def test_math_remain_matches_ieee_oracle(
        self, dividend: float, divisor: float
    ) -> None:
        """math_remain uses nearest-even quotient selection like IEEE remainder."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_compiler_image(emu)
        zp_fac1 = _load_zp_address("zp_fac1")
        zp_arg = _load_zp_address("zp_arg")
        _write_float_to_fac1(emu, zp_fac1, dividend)
        emu.write_mem_range(zp_arg, from_float(divisor).to_bytes())

        emu.execute(_load_symbol_address("math_remain"), 100_000)

        assert _load_float_from_fac1(emu, zp_fac1) == pytest.approx(
            math.remainder(dividend, divisor), abs=1e-6
        )


@pytest.mark.unit
@pytest.mark.local
class TestMathBinary32Text:
    """Direct production-byte coverage for BIN32$ and VAL32 conversion."""

    @pytest.mark.parametrize(
        "value", [0.0, 1.0, -2.5, math.pi], ids=["zero", "one", "negative", "pi"]
    )
    def test_bin32str_matches_python_binary32_oracle(self, value: float) -> None:
        """BIN32$ emits canonical big-endian IEEE binary32 text."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_compiler_image(emu)
        zp_fac1 = _load_zp_address("zp_fac1")
        _write_float_to_fac1(emu, zp_fac1, value)
        emu.set_x(0x00)
        emu.set_y(0x10)

        emu.execute(_load_symbol_address("math_bin32str"), 100_000)

        result = emu.read_mem_range(0x1000, 0x1008).decode("ascii")
        expected = "$" + struct.pack(">f", value).hex().upper()
        assert result == expected

    @pytest.mark.parametrize(
        "text", ["3F800000", "$C0200000", "40490FDB"],
        ids=["one", "prefixed-negative", "pi"],
    )
    def test_val32_matches_python_binary32_oracle(self, text: str) -> None:
        """VAL32 parses canonical text through assembled production bytes."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_compiler_image(emu)
        emu.write_mem_range(0x1000, text.encode("ascii"))
        emu.set_x(0x00)
        emu.set_y(0x10)

        emu.execute(_load_symbol_address("math_val32"), 100_000)

        bits = text.removeprefix("$")
        expected = struct.unpack(">f", bytes.fromhex(bits))[0]
        assert _load_float_from_fac1(
            emu, _load_zp_address("zp_fac1")
        ) == pytest.approx(expected, rel=1e-6)

    def test_math_min(self) -> None:
        """math_min should return the smaller value."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_min")
        zp_fac1 = _load_zp_address("zp_fac1")
        zp_arg = _load_zp_address("zp_arg")

        # Write 5.0 to FAC1
        emu.write_mem(zp_fac1, 0x83)
        emu.write_mem(zp_fac1 + 1, 0x20)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        # Write 3.0 to ARG
        emu.write_mem(zp_arg, 0x82)
        emu.write_mem(zp_arg + 1, 0x40)
        emu.write_mem(zp_arg + 2, 0x00)
        emu.write_mem(zp_arg + 3, 0x00)
        emu.write_mem(zp_arg + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 3.0) < 0.001, f"math_min(5,3) should be ~3.0, got {result}"

    def test_math_max(self) -> None:
        """math_max should return the larger value."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_max")
        zp_fac1 = _load_zp_address("zp_fac1")
        zp_arg = _load_zp_address("zp_arg")

        # Write 5.0 to FAC1
        emu.write_mem(zp_fac1, 0x83)
        emu.write_mem(zp_fac1 + 1, 0x20)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        # Write 3.0 to ARG
        emu.write_mem(zp_arg, 0x82)
        emu.write_mem(zp_arg + 1, 0x40)
        emu.write_mem(zp_arg + 2, 0x00)
        emu.write_mem(zp_arg + 3, 0x00)
        emu.write_mem(zp_arg + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 5.0) < 0.001, f"math_max(5,3) should be ~5.0, got {result}"

    def test_math_isnan(self) -> None:
        """math_isnan should return 1 for NaN, 0 for normal value."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)
        emu.write_mem(0x0000, 0x2F)
        emu.write_mem(0x0001, 0x35)

        addr = _load_symbol_address("math_isnan")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write NaN to FAC1 (exponent=$FF, mantissa!=0)
        emu.write_mem(zp_fac1, 0xFF)
        emu.write_mem(zp_fac1 + 1, 0x80)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result_a = emu.get_state().a
        assert result_a == 1, f"math_isnan(NaN) should return 1, got {result_a}"

    def test_math_isinf(self) -> None:
        """math_isinf should return 1 for Infinity, 0 for normal value."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_isinf")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write +Infinity to FAC1 (exponent=$FF, mantissa=$800000, sign=0)
        emu.write_mem(zp_fac1, 0xFF)
        emu.write_mem(zp_fac1 + 1, 0x80)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result_a = emu.get_state().a
        assert result_a == 1, f"math_isinf(+Inf) should return 1, got {result_a}"
