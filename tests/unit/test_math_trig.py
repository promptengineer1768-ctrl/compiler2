"""Unit tests for trigonometric math routines (math_trig.asm).

Tests verify SIN, COS, TAN, ATN, ACS, and ASN functions against stock
BASIC V2 values and legacy project Python proxy accuracy fixtures.
"""

from __future__ import annotations

import json
import math
import re
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
class TestMathSin:
    """SIN function tests."""

    def test_sin_zero(self) -> None:
        """SIN(0) should return 0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_sin")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 0.0 to FAC1
        emu.write_mem(zp_fac1, 0x00)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result) < 1e-6, f"SIN(0) should be ~0, got {result}"

    def test_sin_half_pi(self) -> None:
        """SIN(pi/2) should return ~1.0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_sin")
        zp_fac1 = _load_zp_address("zp_fac1")

        _write_float_to_fac1(emu, zp_fac1, math.pi / 2)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 1.0) < 0.001, f"SIN(pi/2) should be ~1.0, got {result}"

    def test_sin_negative(self) -> None:
        """SIN(-x) should return -SIN(x)."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_sin")
        zp_fac1 = _load_zp_address("zp_fac1")

        _write_float_to_fac1(emu, zp_fac1, -math.pi / 2)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result + 1.0) < 0.001, f"SIN(-pi/2) should be ~-1.0, got {result}"


@pytest.mark.unit
@pytest.mark.local
class TestMathCos:
    """COS function tests."""

    def test_cos_zero(self) -> None:
        """COS(0) should return 1.0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_cos")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 0.0 to FAC1
        emu.write_mem(zp_fac1, 0x00)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 1.0) < 0.001, f"COS(0) should be ~1.0, got {result}"

    def test_cos_pi(self) -> None:
        """COS(pi) should return ~-1.0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_cos")
        zp_fac1 = _load_zp_address("zp_fac1")

        _write_float_to_fac1(emu, zp_fac1, math.pi)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result + 1.0) < 0.001, f"COS(pi) should be ~-1.0, got {result}"


@pytest.mark.unit
@pytest.mark.local
class TestMathTan:
    """TAN function tests."""

    def test_tan_zero(self) -> None:
        """TAN(0) should return 0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_tan")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 0.0 to FAC1
        emu.write_mem(zp_fac1, 0x00)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result) < 1e-6, f"TAN(0) should be ~0, got {result}"

    def test_tan_quarter_pi(self) -> None:
        """TAN(pi/4) should return ~1.0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_tan")
        zp_fac1 = _load_zp_address("zp_fac1")

        _write_float_to_fac1(emu, zp_fac1, math.pi / 4)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - 1.0) < 0.01, f"TAN(pi/4) should be ~1.0, got {result}"


@pytest.mark.unit
@pytest.mark.local
class TestMathAtn:
    """ATN function tests."""

    def test_atn_zero(self) -> None:
        """ATN(0) should return 0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_atn")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 0.0 to FAC1
        emu.write_mem(zp_fac1, 0x00)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result) < 1e-6, f"ATN(0) should be ~0, got {result}"

    def test_atn_one(self) -> None:
        """ATN(1) should return ~pi/4."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_atn")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 1.0 to FAC1
        emu.write_mem(zp_fac1, 0x81)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        expected = math.pi / 4
        assert abs(result - expected) < 0.001, f"ATN(1) should be ~pi/4, got {result}"

    def test_atn_negative(self) -> None:
        """ATN(-1) should return ~-pi/4."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_atn")
        zp_fac1 = _load_zp_address("zp_fac1")

        _write_float_to_fac1(emu, zp_fac1, -1.0)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        expected = -math.pi / 4
        assert abs(result - expected) < 0.001, f"ATN(-1) should be ~-pi/4, got {result}"


@pytest.mark.unit
@pytest.mark.local
class TestMathAcs:
    """ACS (arccosine) function tests."""

    def test_acs_one(self) -> None:
        """ACS(1) should return 0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_acs")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 1.0 to FAC1
        emu.write_mem(zp_fac1, 0x81)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result) < 0.001, f"ACS(1) should be ~0, got {result}"

    def test_acs_zero(self) -> None:
        """ACS(0) should return ~pi/2."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_acs")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 0.0 to FAC1
        emu.write_mem(zp_fac1, 0x00)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        expected = math.pi / 2
        assert abs(result - expected) < 0.001, f"ACS(0) should be ~pi/2, got {result}"

    def test_acs_half_general_path(self) -> None:
        """ACS(0.5) must traverse the real ASN/SQR/ATN production path."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)
        zp_fac1 = _load_zp_address("zp_fac1")
        _write_float_to_fac1(emu, zp_fac1, 0.5)

        emu.execute(_load_symbol_address("math_acs"), 100_000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - math.acos(0.5)) < 0.001


@pytest.mark.unit
@pytest.mark.local
class TestMathAsn:
    """ASN (arcsine) function tests."""

    def test_asn_zero(self) -> None:
        """ASN(0) should return 0."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_asn")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 0.0 to FAC1
        emu.write_mem(zp_fac1, 0x00)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result) < 1e-6, f"ASN(0) should be ~0, got {result}"

    def test_asn_one(self) -> None:
        """ASN(1) should return ~pi/2."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)

        addr = _load_symbol_address("math_asn")
        zp_fac1 = _load_zp_address("zp_fac1")

        # Write 1.0 to FAC1
        emu.write_mem(zp_fac1, 0x81)
        emu.write_mem(zp_fac1 + 1, 0x00)
        emu.write_mem(zp_fac1 + 2, 0x00)
        emu.write_mem(zp_fac1 + 3, 0x00)
        emu.write_mem(zp_fac1 + 4, 0x00)

        emu.execute(addr, 10000)

        result = _load_float_from_fac1(emu, zp_fac1)
        expected = math.pi / 2
        assert abs(result - expected) < 0.001, f"ASN(1) should be ~pi/2, got {result}"

    def test_asn_half_general_path(self) -> None:
        """ASN(0.5) must execute the general identity, not an exact shortcut."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_compiler_image(emu)
        emu.set_georam_enabled(True)
        zp_fac1 = _load_zp_address("zp_fac1")
        _write_float_to_fac1(emu, zp_fac1, 0.5)

        emu.execute(_load_symbol_address("math_asn"), 100_000)

        result = _load_float_from_fac1(emu, zp_fac1)
        assert abs(result - math.asin(0.5)) < 0.001
