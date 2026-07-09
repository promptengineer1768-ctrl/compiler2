"""Exact Commodore BASIC 5-byte float reference model.

The model is copied from the proven ``basic v3`` numeric tooling and kept
small here for arithmetic proof tests. It represents operations with exact
``Fraction`` values, then quantizes to the target 5-byte format using
nearest-even rounding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Self

BIAS = 128
MANT_BITS = 32
HIDDEN_BIT = 1 << (MANT_BITS - 1)
FRACTION_MASK = HIDDEN_BIT - 1


@dataclass(frozen=True, order=True)
class C64Float:
    """A Commodore BASIC 5-byte floating-point value."""

    sign: int
    exponent: int
    mantissa: int

    @classmethod
    def zero(cls) -> Self:
        """Return canonical positive zero."""
        return cls(1, 0, 0)

    @property
    def is_zero(self) -> bool:
        """Return whether the value is zero."""
        return self.exponent == 0 and self.mantissa == 0

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        """Decode a 5-byte Commodore packed float."""
        if len(data) != 5:
            raise ValueError("C64 floats are exactly 5 bytes")
        if data == bytes(5):
            return cls.zero()
        sign = -1 if data[1] & 0x80 else 1
        fraction = ((data[1] & 0x7F) << 24) | (data[2] << 16) | (data[3] << 8) | data[4]
        return cls(sign, data[0] - BIAS, HIDDEN_BIT | fraction)

    def to_bytes(self) -> bytes:
        """Encode the value as five packed bytes."""
        if self.is_zero:
            return bytes(5)
        stored = self.exponent + BIAS
        if not 1 <= stored <= 255:
            raise OverflowError(f"exponent out of C64 range: {self.exponent}")
        fraction = self.mantissa & FRACTION_MASK
        if self.sign < 0:
            fraction |= 0x80 << 24
        return bytes(
            [
                stored,
                (fraction >> 24) & 0xFF,
                (fraction >> 16) & 0xFF,
                (fraction >> 8) & 0xFF,
                fraction & 0xFF,
            ]
        )

    def to_fraction(self) -> Fraction:
        """Convert the value to an exact fraction."""
        if self.is_zero:
            return Fraction(0)
        value = Fraction(self.mantissa, HIDDEN_BIT) * Fraction(2) ** (self.exponent - 1)
        return value if self.sign > 0 else -value

    def to_float(self) -> float:
        """Convert the value to a Python float."""
        return float(self.to_fraction())


def _round_quotient(numerator: int, denominator: int) -> int:
    """Round an integer quotient to nearest-even."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    quotient, remainder = divmod(numerator, denominator)
    twice = remainder * 2
    if twice > denominator:
        return quotient + 1
    if twice < denominator:
        return quotient
    return quotient + (quotient & 1)


def quantize_fraction(value: Fraction) -> C64Float:
    """Quantize an exact fraction to nearest-even C64 float."""
    if value == 0:
        return C64Float.zero()
    sign = -1 if value < 0 else 1
    magnitude = abs(value)
    exponent = magnitude.numerator.bit_length() - magnitude.denominator.bit_length() + 1
    while magnitude < Fraction(2) ** (exponent - 1):
        exponent -= 1
    while magnitude >= Fraction(2) ** exponent:
        exponent += 1
    scaled = magnitude * Fraction(HIDDEN_BIT, 1) / (Fraction(2) ** (exponent - 1))
    mantissa = _round_quotient(scaled.numerator, scaled.denominator)
    if mantissa >= (1 << MANT_BITS):
        mantissa >>= 1
        exponent += 1
    return C64Float(sign, exponent, mantissa)


def from_float(value: float) -> C64Float:
    """Convert a finite Python float to nearest-even C64 float."""
    if not math.isfinite(value):
        raise ValueError("C64 BASIC float model only supports finite values")
    return quantize_fraction(Fraction.from_float(value))


def add(left: bytes, right: bytes) -> bytes:
    """Return fully rounded ``left + right``."""
    return quantize_fraction(
        C64Float.from_bytes(left).to_fraction()
        + C64Float.from_bytes(right).to_fraction()
    ).to_bytes()


def sub(left: bytes, right: bytes) -> bytes:
    """Return fully rounded ``left - right``."""
    return quantize_fraction(
        C64Float.from_bytes(left).to_fraction()
        - C64Float.from_bytes(right).to_fraction()
    ).to_bytes()


def mul(left: bytes, right: bytes) -> bytes:
    """Return fully rounded ``left * right``."""
    return quantize_fraction(
        C64Float.from_bytes(left).to_fraction()
        * C64Float.from_bytes(right).to_fraction()
    ).to_bytes()


def div(left: bytes, right: bytes) -> bytes:
    """Return fully rounded ``left / right``."""
    denominator = C64Float.from_bytes(right).to_fraction()
    if denominator == 0:
        raise ZeroDivisionError("C64 float divide by zero")
    return quantize_fraction(
        C64Float.from_bytes(left).to_fraction() / denominator
    ).to_bytes()


def sqr(value: bytes) -> bytes:
    """Return fully rounded square root for non-negative input."""
    fraction = C64Float.from_bytes(value).to_fraction()
    if fraction < 0:
        raise ValueError("square root domain error")
    root = Fraction.from_float(math.sqrt(float(fraction)))
    return quantize_fraction(root).to_bytes()
