"""Minimal public-KERNAL vector stubs for local bridge mechanics tests.

The local 6502 model intentionally has no ROM overlay unless a test loads one.
These byte stubs are an external KERNAL fixture: production bridge code still
executes its real JSRs through the public jump-table addresses. VICE covers the
actual KERNAL and device implementations.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

KERNAL_SCNKEY = 0xFF9F
KERNAL_READST = 0xFFB7
KERNAL_SETLFS = 0xFFBA
KERNAL_SETNAM = 0xFFBD
KERNAL_OPEN = 0xFFC0
KERNAL_CLOSE = 0xFFC3
KERNAL_CHKIN = 0xFFC6
KERNAL_CHKOUT = 0xFFC9
KERNAL_CLRCHN = 0xFFCC
KERNAL_CHRIN = 0xFFCF
KERNAL_CHROUT = 0xFFD2
KERNAL_LOAD = 0xFFD5
KERNAL_SAVE = 0xFFD8
KERNAL_SETTIM = 0xFFDB
KERNAL_RDTIM = 0xFFDE
KERNAL_STOP = 0xFFE1
KERNAL_GETIN = 0xFFE4
KERNAL_UDTIM = 0xFFEA

# Place tightly packed stub bodies above the linked compiler image and below
# the I/O window. The fixture validates this boundary against compiler.map so
# normal-RAM growth cannot silently overwrite production code.
KERNAL_STUB_CODE_BASE = 0xCB00
KERNAL_STUB_INPUT = 0xCEF0
KERNAL_STUB_OUTPUT = 0xCEF1
KERNAL_STUB_LAST_A = 0xCEF2
KERNAL_STUB_LAST_X = 0xCEF3
KERNAL_STUB_LAST_Y = 0xCEF4
KERNAL_STUB_LAST_PORT = 0xCEF5
COMPILER_MAP = Path(__file__).resolve().parents[1] / "build" / "compiler.map"


class _MemoryEmulator(Protocol):
    """Subset of the native C64 emulator used by this fixture."""

    def write_mem(self, address: int, value: int) -> None:
        """Write one byte to CPU-visible memory."""

    def write_mem_range(self, start: int, data: bytes) -> None:
        """Write a byte sequence to CPU-visible memory."""


def _word(value: int) -> bytes:
    """Encode one 16-bit CPU address in little-endian order."""
    return bytes((value & 0xFF, value >> 8))


def _absolute(opcode: int, address: int) -> bytes:
    """Encode an absolute-addressing instruction."""
    return bytes((opcode,)) + _word(address)


def _prefix() -> bytes:
    """Record entry registers and the CPU-port value without changing A."""
    return b"".join(
        (
            _absolute(0x8D, KERNAL_STUB_LAST_A),  # STA last_a
            _absolute(0x8E, KERNAL_STUB_LAST_X),  # STX last_x
            _absolute(0x8C, KERNAL_STUB_LAST_Y),  # STY last_y
            bytes((0x48,)),  # PHA
            _absolute(0xAD, 0x0001),  # LDA $0001
            _absolute(0x8D, KERNAL_STUB_LAST_PORT),  # STA last_port
            bytes((0x68,)),  # PLA
        )
    )


def _success() -> bytes:
    """Return a successful KERNAL-style result."""
    return bytes((0x18, 0x60))  # CLC / RTS


def _input_byte() -> bytes:
    """Consume and return the configurable one-byte local input queue."""
    return b"".join(
        (
            _absolute(0xAD, KERNAL_STUB_INPUT),  # LDA input
            bytes((0x48, 0xA9, 0x00)),  # PHA / LDA #0
            _absolute(0x8D, KERNAL_STUB_INPUT),  # STA input
            bytes((0x68, 0x18, 0x60)),  # PLA / CLC / RTS
        )
    )


def _status_success() -> bytes:
    """Clear the KERNAL status byte and return success."""
    return bytes((0xA9, 0x00)) + _absolute(0x8D, 0x0090) + _success()


def _setlfs() -> bytes:
    """Implement the source-visible SETLFS workspace effects."""
    return b"".join(
        (
            _absolute(0x8D, 0x00B8),
            _absolute(0x8E, 0x00BA),
            _absolute(0x8C, 0x00B9),
            _status_success(),
        )
    )


def _setnam() -> bytes:
    """Implement the source-visible SETNAM workspace effects."""
    return b"".join(
        (
            _absolute(0x8D, 0x00B7),
            _absolute(0x8E, 0x00BB),
            _absolute(0x8C, 0x00BC),
            _status_success(),
        )
    )


def _load() -> bytes:
    """Publish the alternate load address as the local LOAD end address."""
    return b"".join(
        (
            _absolute(0x8E, 0x00AE),
            _absolute(0x8C, 0x00AF),
            _status_success(),
        )
    )


def _save() -> bytes:
    """Implement SAVE's start-pointer and exclusive-end workspace effects."""
    return b"".join(
        (
            _absolute(0xAE, KERNAL_STUB_LAST_X),  # LDX last_x
            _absolute(0x8E, 0x00AE),
            _absolute(0xAC, KERNAL_STUB_LAST_Y),  # LDY last_y
            _absolute(0x8C, 0x00AF),
            _absolute(0xAE, KERNAL_STUB_LAST_A),  # LDX start-pointer address
            bytes((0xBD, 0x00, 0x00)),  # LDA $0000,X
            _absolute(0x8D, 0x00AC),
            bytes((0xBD, 0x01, 0x00)),  # LDA $0001,X
            _absolute(0x8D, 0x00AD),
            _status_success(),
        )
    )


def _settim() -> bytes:
    """Implement SETTIM's documented jiffy-clock stores."""
    return b"".join(
        (
            _absolute(0x8D, 0x00A2),
            _absolute(0x8E, 0x00A1),
            _absolute(0x8C, 0x00A0),
            _success(),
        )
    )


def _rdtim() -> bytes:
    """Implement RDTIM's documented jiffy-clock loads."""
    return b"".join(
        (
            _absolute(0xAD, 0x00A2),
            _absolute(0xAE, 0x00A1),
            _absolute(0xAC, 0x00A0),
            _success(),
        )
    )


def _udtim() -> bytes:
    """Increment the little-endian 24-bit jiffy clock."""
    return b"".join(
        (
            _absolute(0xEE, 0x00A2),  # INC low
            bytes((0xD0, 0x08)),  # BNE done
            _absolute(0xEE, 0x00A1),  # INC middle
            bytes((0xD0, 0x03)),  # BNE done
            _absolute(0xEE, 0x00A0),  # INC high
            _success(),
        )
    )


def _scnkey() -> bytes:
    """Model the narrow keyboard-state writes needed by local callers."""
    return b"".join(
        (
            _absolute(0xAD, 0x000F),  # LDA zp_crsr_x
            _absolute(0x8D, 0x00C5),  # STA lstx
            _absolute(0xEE, 0x00C6),  # INC ndx
            _success(),
        )
    )


def _chrout() -> bytes:
    """Capture output while preserving the production bridge's actual call."""
    return (
        _absolute(0xAD, KERNAL_STUB_LAST_A)
        + _absolute(0x8D, KERNAL_STUB_OUTPUT)
        + _success()
    )


def _readst() -> bytes:
    """Return the stock KERNAL status byte."""
    return _absolute(0xAD, 0x0090) + bytes((0x60,))


def _stop() -> bytes:
    """Return the not-stopped result with Z set."""
    return bytes((0xA9, 0x00, 0x18, 0x60))


def _bodies() -> dict[int, bytes]:
    """Return vector-specific local KERNAL behavior after the common prefix."""
    return {
        KERNAL_SCNKEY: _scnkey(),
        KERNAL_READST: _readst(),
        KERNAL_SETLFS: _setlfs(),
        KERNAL_SETNAM: _setnam(),
        KERNAL_OPEN: _status_success(),
        KERNAL_CLOSE: _status_success(),
        KERNAL_CHKIN: _status_success(),
        KERNAL_CHKOUT: _status_success(),
        KERNAL_CLRCHN: _status_success(),
        KERNAL_CHRIN: _input_byte(),
        KERNAL_CHROUT: _chrout(),
        KERNAL_LOAD: _load(),
        KERNAL_SAVE: _save(),
        KERNAL_SETTIM: _settim(),
        KERNAL_RDTIM: _rdtim(),
        KERNAL_STOP: _stop(),
        KERNAL_GETIN: _input_byte(),
        KERNAL_UDTIM: _udtim(),
    }


def install_kernal_stubs(emu: _MemoryEmulator) -> None:
    """Install byte-level public KERNAL stubs into a no-ROM local emulator."""
    segments = re.findall(
        r"^\S+\s+([0-9A-Fa-f]{6})\s+([0-9A-Fa-f]{6})\s+[0-9A-Fa-f]{6}",
        COMPILER_MAP.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    linked_end = max(int(end, 16) for start, end in segments if int(start, 16) < 0xD000)
    if linked_end >= KERNAL_STUB_CODE_BASE:
        raise AssertionError(
            f"compiler image ends at ${linked_end:04X}, colliding with KERNAL "
            f"stub fixture at ${KERNAL_STUB_CODE_BASE:04X}"
        )
    emu.write_mem(KERNAL_STUB_INPUT, 0)
    emu.write_mem(KERNAL_STUB_OUTPUT, 0)
    emu.write_mem(KERNAL_STUB_LAST_A, 0)
    emu.write_mem(KERNAL_STUB_LAST_X, 0)
    emu.write_mem(KERNAL_STUB_LAST_Y, 0)
    emu.write_mem(KERNAL_STUB_LAST_PORT, 0)
    target = KERNAL_STUB_CODE_BASE
    for vector, body in _bodies().items():
        code = _prefix() + body
        if target + len(code) > KERNAL_STUB_INPUT:
            raise AssertionError("KERNAL stub fixture exceeds its reserved RAM gap")
        emu.write_mem_range(target, code)
        emu.write_mem_range(vector, bytes((0x4C,)) + _word(target))
        target += len(code)


def install_vector_stub(
    emu: _MemoryEmulator, vector: int, target: int, body: bytes
) -> None:
    """Install one custom public-vector implementation for a focused test."""
    emu.write_mem_range(target, body)
    emu.write_mem_range(vector, bytes((0x4C,)) + _word(target))
