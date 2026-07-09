"""Accuracy proof tests for the Compiler 2 finite float oracle."""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from numeric.c64float import (  # noqa: E402
    C64Float,
    add,
    div,
    from_float,
    mul,
    quantize_fraction,
    sqr,
    sub,
)


def _ordered_key(data: bytes) -> int:
    """Return a monotonic key for ULP distance checks."""
    value = C64Float.from_bytes(data)
    if value.is_zero:
        return 0
    magnitude = (value.exponent << 32) | value.mantissa
    return magnitude if value.sign > 0 else -magnitude


def _ulp_distance(left: bytes, right: bytes) -> int:
    """Return the representable-value distance between two packed floats."""
    return abs(_ordered_key(left) - _ordered_key(right))


def _packed(value: float) -> bytes:
    """Return the exact nearest-even packed representation for a test value."""
    return from_float(value).to_bytes()


@pytest.mark.local
def test_known_packed_values_round_trip() -> None:
    """Known C64 BASIC packed values encode and decode exactly."""
    assert quantize_fraction(Fraction(0)).to_bytes() == bytes(5)
    assert quantize_fraction(Fraction(1)).to_bytes() == bytes([0x81, 0, 0, 0, 0])
    assert quantize_fraction(Fraction(2)).to_bytes() == bytes([0x82, 0, 0, 0, 0])
    assert quantize_fraction(Fraction(3)).to_bytes() == bytes([0x82, 0x40, 0, 0, 0])
    assert C64Float.from_bytes(bytes([0x81, 0x80, 0, 0, 0])).to_fraction() == -1


@pytest.mark.local
def test_round_nearest_ties_to_even() -> None:
    """Halfway quantization cases use IEEE round-to-nearest-even."""
    one = Fraction(1)
    ulp = Fraction(1, 1 << 31)

    assert quantize_fraction(one + ulp / 2).to_fraction() == one
    assert quantize_fraction(one + ulp + ulp / 2).to_fraction() == one + ulp * 2


@pytest.mark.local
@pytest.mark.parametrize(
    ("label", "helper", "reference"),
    [
        ("add", add, lambda left, right: left + right),
        ("sub", sub, lambda left, right: left - right),
        ("mul", mul, lambda left, right: left * right),
        ("div", div, lambda left, right: left / right),
    ],
)
def test_arithmetic_helpers_are_fully_rounded(
    label: str,
    helper: Callable[[bytes, bytes], bytes],
    reference: Callable[[Fraction, Fraction], Fraction],
) -> None:
    """Finite arithmetic is exactly rounded to the destination format."""
    values = [
        0,
        0.01,
        0.1,
        0.25,
        0.5,
        0.75,
        1,
        1.5,
        2,
        2.5,
        3,
        4,
        5,
        8,
        10,
        15,
        100,
        1000,
        -0.01,
        -0.5,
        -1,
        -2.25,
        -10,
    ]

    for left_value in values:
        for right_value in values:
            if label == "div" and right_value == 0:
                continue
            left = _packed(left_value)
            right = _packed(right_value)
            expected = quantize_fraction(
                reference(
                    C64Float.from_bytes(left).to_fraction(),
                    C64Float.from_bytes(right).to_fraction(),
                )
            ).to_bytes()
            actual = helper(left, right)
            assert _ulp_distance(actual, expected) == 0, (
                f"{label}({left_value}, {right_value}) got {actual.hex()} "
                f"expected {expected.hex()}"
            )


@pytest.mark.local
def test_square_root_helper_is_fully_rounded() -> None:
    """Finite square roots are exactly rounded to the destination format."""
    values = [
        0,
        0.01,
        0.02,
        0.03,
        0.1,
        0.25,
        0.5,
        0.75,
        1,
        1.5,
        2,
        2.5,
        3,
        4,
        6,
        7,
        9,
        16,
        25,
        123.5,
        1000,
    ]

    for value in values:
        packed = _packed(value)
        fraction = C64Float.from_bytes(packed).to_fraction()
        expected = from_float(math.sqrt(float(fraction))).to_bytes()
        actual = sqr(packed)
        assert (
            _ulp_distance(actual, expected) == 0
        ), f"sqr({value}) got {actual.hex()} expected {expected.hex()}"


@pytest.mark.local
def test_domain_errors_are_explicit() -> None:
    """Undefined finite operations report errors instead of fabricating values."""
    with pytest.raises(ZeroDivisionError):
        div(_packed(1), _packed(0))
    with pytest.raises(ValueError, match="square root"):
        sqr(_packed(-1))
