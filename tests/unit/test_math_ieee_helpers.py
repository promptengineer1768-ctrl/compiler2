"""Direct real-byte tests for the IEEE math helper routines.

These routines are pure FAC1/ARG manipulations and are exercised through the
linked production bytes. Each test sets FAC1 (and ARG where needed) via the
generated ``zp_fac1``/``zp_arg`` zero-page locations and asserts the observable
effect on the FAC and accumulator.

C64 packed-float model used by this codebase:

    byte 0  exponent (bias $7F; $80 = 1.0)
    byte 1  mantissa high + sign (bit 7)
    byte 2  mantissa mid-high
    byte 3  mantissa mid-low
    byte 4  mantissa low
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import cast

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
    for path in (
        ROOT.parent / "tools" / "emu6502.dll",
        ROOT.parent / "tools" / "msys-emu6502.dll",
    ):
        if path.exists():
            return path
    pytest.skip("Emulator DLL not found in tools folder.")


def _load_symbol_address(symbol_name: str) -> int:
    labels_path = ROOT / "build" / "compiler.lbl"
    if labels_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    map_path = ROOT / "build" / "compiler.map"
    if not map_path.exists():
        pytest.fail("build/compiler.map not found. Run build.ps1 first.")
    match = re.search(
        rf"\b{re.escape(symbol_name)}\b\s+([0-9A-Fa-f]{{6}})",
        map_path.read_text(encoding="utf-8"),
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol {symbol_name!r} not found in linked outputs.")


def _zp(name: str) -> int:
    data = json.loads(
        (ROOT / "build" / "zp_allocation.json").read_text(encoding="utf-8")
    )
    addr = data.get("allocation", {}).get(name, "")
    if not str(addr).startswith("$"):
        pytest.fail(f"Zero-page symbol {name!r} not found.")
    return int(addr[1:], 16)


def _new_emu() -> C64Emu6502:
    emu = C64Emu6502(lib_path=_dll_path())
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    hibasic_path = ROOT / "build" / "hibasic.bin"
    if hibasic_path.exists():
        emu.write_mem_range(0xE000, hibasic_path.read_bytes())
        emu.write_mem(0x0001, 0x35)
    emu.set_georam_enabled(True)
    return emu


def _set_fac(emu: C64Emu6502, fac: str, value: bytes) -> None:
    base = _zp("zp_fac1" if fac == "fac1" else "zp_arg")
    assert len(value) == 5
    for i, b in enumerate(value):
        emu.write_mem(base + i, b)


def _get_fac(emu: C64Emu6502, fac: str = "fac1") -> bytes:
    base = _zp("zp_fac1" if fac == "fac1" else "zp_arg")
    return bytes(emu.read_mem(base + i) for i in range(5))


def _call(emu: C64Emu6502, name: str) -> int:
    emu.execute(_load_symbol_address(name), 20000)
    return cast(int, emu.get_state().a)


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.smoke
class TestMathClassification:
    """IEEE classification helpers return A=1 for true, A=0 for false."""

    def test_iszero(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes(5))
        assert _call(emu, "math_iszero") == 1
        _set_fac(emu, "fac1", bytes([0x81, 0x00, 0x00, 0x00, 0x00]))
        assert _call(emu, "math_iszero") == 0

    def test_isnan(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0xFF, 0x80, 0x00, 0x00, 0x00]))
        assert _call(emu, "math_isnan") == 1
        _set_fac(emu, "fac1", bytes(5))
        assert _call(emu, "math_isnan") == 0

    def test_isinf(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0xFF, 0x80, 0x00, 0x00, 0x00]))
        assert _call(emu, "math_isinf") == 1
        _set_fac(emu, "fac1", bytes([0xFF, 0x00, 0x00, 0x00, 0x00]))  # NaN
        assert _call(emu, "math_isinf") == 0
        _set_fac(emu, "fac1", bytes([0x81, 0x00, 0x00, 0x00, 0x00]))
        assert _call(emu, "math_isinf") == 0

    def test_isfin(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x81, 0x00, 0x00, 0x00, 0x00]))
        assert _call(emu, "math_isfin") == 1
        _set_fac(emu, "fac1", bytes([0xFF, 0x80, 0x00, 0x00, 0x00]))  # inf
        assert _call(emu, "math_isfin") == 0

    def test_isnorm(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x80, 0x00, 0x00, 0x00, 0x00]))
        assert _call(emu, "math_isnorm") == 1
        _set_fac(emu, "fac1", bytes(5))  # zero
        assert _call(emu, "math_isnorm") == 0
        _set_fac(emu, "fac1", bytes([0xFF, 0x80, 0x00, 0x00, 0x00]))  # inf
        assert _call(emu, "math_isnorm") == 0

    def test_issnan(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0xFF, 0x00, 0x00, 0x00, 0x01]))
        assert _call(emu, "math_issnan") == 1
        _set_fac(emu, "fac1", bytes([0xFF, 0x80, 0x00, 0x00, 0x00]))  # inf
        assert _call(emu, "math_issnan") == 0
        _set_fac(emu, "fac1", bytes([0x81, 0x00, 0x00, 0x00, 0x00]))
        assert _call(emu, "math_issnan") == 0

    def test_isunord(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x81, 0x00, 0x00, 0x00, 0x00]))
        _set_fac(emu, "arg", bytes([0x81, 0x00, 0x00, 0x00, 0x00]))
        assert _call(emu, "math_isunord") == 0
        _set_fac(emu, "fac1", bytes([0xFF, 0x80, 0x00, 0x00, 0x00]))
        assert _call(emu, "math_isunord") == 1

    def test_sgnbit(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x81, 0x80, 0x00, 0x00, 0x00]))  # negative
        assert _call(emu, "math_sgnbit") == 1
        _set_fac(emu, "fac1", bytes([0x81, 0x00, 0x00, 0x00, 0x00]))  # positive
        assert _call(emu, "math_sgnbit") == 0


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.smoke
class TestMathFACManipulation:
    """Helpers that rewrite the FAC in place."""

    def test_mant_sets_exponent_to_one(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x85, 0x12, 0x34, 0x56, 0x78]))
        _call(emu, "math_mant")
        assert _get_fac(emu)[0] == 0x80

    def test_logb_returns_unbiased_exponent(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x81, 0x00, 0x00, 0x00, 0x00]))  # 1.0
        _call(emu, "math_logb")
        # math_logb(FAC1) = unbiased exponent, published in FAC1 as integer 1.
        assert _get_fac(emu) == bytes([0x81, 0x00, 0x00, 0x00, 0x00])

    def test_scalb_adds_exponent(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x80, 0x00, 0x00, 0x00, 0x00]))
        emu.set_x(3)
        _call(emu, "math_scalb")
        assert _get_fac(emu)[0] == 0x83

    def test_nextup_increments_mantissa(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x80, 0x00, 0x00, 0x00, 0x00]))
        _call(emu, "math_nextup")
        fac = _get_fac(emu)
        assert fac[4] == 0x01 and fac[0] == 0x80

    def test_nextdown_decrements_mantissa(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x80, 0x00, 0x00, 0x00, 0x01]))
        _call(emu, "math_nextdown")
        fac = _get_fac(emu)
        assert fac[4] == 0x00 and fac[0] == 0x80

    def test_copysign_takes_arg_sign(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x81, 0x00, 0x00, 0x00, 0x00]))  # positive
        _set_fac(emu, "arg", bytes([0x81, 0x80, 0x00, 0x00, 0x00]))  # negative
        _call(emu, "math_copysign")
        assert _get_fac(emu)[1] & 0x80

    def test_totalorder_returns_sign_of_difference(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x81, 0x00, 0x00, 0x00, 0x00]))  # 1.0
        _set_fac(emu, "arg", bytes([0x82, 0x00, 0x00, 0x00, 0x00]))  # 2.0
        assert _call(emu, "math_totalorder") & 0x80

    def test_rint_truncates_to_integer(self) -> None:
        emu = _new_emu()
        _set_fac(emu, "fac1", bytes([0x81, 0x20, 0x00, 0x00, 0x00]))
        _call(emu, "math_rint")
        fac = _get_fac(emu)
        assert fac[0] == 0x81
        assert fac[1] == 0x00
