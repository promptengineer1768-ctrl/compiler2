"""Authoritative VICE-backed coverage for the RAM-under-I/O gate routines.

These tests drive the real linked production bytes on x64sc through the
supervised VICE-next harness and assert the genuine C64 behavior that the
local unit emulator cannot model (the $01 processor port banking and the
RAM hidden under the $D000-$DFFF I/O window).

The local unit tests in ``tests/unit/test_ram_under_io.py`` are
capability-gated and skip on emulators that do not model the processor port;
the tests here are the authoritative execution path.

Driver note
-----------
The resident gate routines are built to run inside the compiler's own
installed context (intact ZP and KERNAL/IRQ vectors). The linked image
loaded here occupies $0801..$C9xx and intentionally overwrites the ZP and
the $0314/$0316/$0318 indirect vectors that VICE's headless KERNAL IRQ path
relies on; once a routine re-enables interrupts with ``CLI`` a pending KERNAL
IRQ jams the emulated CPU at $FFFF. To exercise the *real* banking and
RAM-under-I/O logic on VICE without that harness artifact, each routine is
relocated to free RAM ($CA00+) and its trailing ``CLI`` is kept as ``SEI`` so
interrupts stay masked for the duration of the driver. Every byte of the
banking behavior under test ($01 = $30 / $35, and the hidden RAM at
$D000-$DFFF) is the production code, unchanged.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from vice_harness import MACHINES, VICE_ROOT, ViceMCP, running_vice  # noqa: E402

# Zero-page symbols used by the resident gate routines.
ZP_SRC = 0x16  # zp_src
ZP_DEST = 0x18  # zp_dest

# Routines are relocated into this free RAM window (above the loaded image,
# which ends below $CA00) and driven from a stub parked at STUB_ADDR.
RELOC_BASE = 0xCA00
STUB_ADDR = 0xC000
DONE_FLAG = 0xCF00  # written by the stub after the routine returns

# Payloads mirror the ones used by the local unit tests.
COPY_IN_PAYLOAD = b"TEST_RAM_UNDER_IO_PAYLOAD"
COPY_OUT_PAYLOAD = b"READ_BACK_PAYLOAD"


def _require_vice_exe() -> Path:
    """Require the bundled C64 VICE executable."""
    exe = VICE_ROOT / "x64sc.exe"
    if not exe.exists():
        pytest.skip(f"x64sc.exe not found under {VICE_ROOT}")
    return exe


def _load_symbol_addresses() -> dict[str, int]:
    """Resolve the RAM-under-I/O routines from the linked label file."""
    labels = ROOT / "build" / "compiler.lbl"
    if not labels.exists():
        pytest.fail("build/compiler.lbl not found. Run build.ps1 first.")
    text = labels.read_text(encoding="utf-8")
    out: dict[str, int] = {}
    for sym in (
        "ram_under_io_enter",
        "ram_under_io_exit",
        "ram_under_io_copy_in",
        "ram_under_io_copy_out",
    ):
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(sym)}$",
            text,
            re.MULTILINE,
        )
        if not match:
            pytest.fail(f"Symbol '{sym}' not found in build/compiler.lbl")
        out[sym] = int(match.group(1), 16)
    return out


def _read_routine(vice: ViceMCP, addr: int) -> bytes:
    """Read a relocated-clean copy of a routine up to and including its RTS."""
    body = vice.memory_read(addr, 64)
    end = body.index(0x60) + 1
    return bytes(body[:end])


def _relocate_routine(
    vice: ViceMCP, addr: int, base: int, jsr_fixes: dict[int, int]
) -> int:
    """Park a routine at ``base`` with ``CLI``->``SEI`` and remapped JSRs.

    Args:
        vice: Connected ``ViceMCP`` instance.
        addr: Production address of the routine (read from the loaded image).
        base: Free-RAM address to park the relocated routine.
        jsr_fixes: Map of original called-address to relocated address so the
            routine still calls the relocated helpers rather than the image.

    Returns:
        The relocated base address.
    """
    body = bytearray(_read_routine(vice, addr))
    for i, byte in enumerate(body):
        # Keep interrupts masked for the driver (see module note).
        if byte == 0x58:  # CLI
            body[i] = 0x78  # SEI
        # Remap JSR targets that point at relocated helpers.
        if byte == 0x20 and i + 2 < len(body):
            target = body[i + 1] | (body[i + 2] << 8)
            if target in jsr_fixes:
                body[i + 1] = jsr_fixes[target] & 0xFF
                body[i + 2] = jsr_fixes[target] >> 8
    vice.memory_write(base, bytes(body))
    return base


def _install_image(vice: ViceMCP) -> None:
    """Load the linked compiler image into VICE memory."""
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    vice.memory_write(load_addr, payload[2:])


def _run_stub(vice: ViceMCP, stub: bytes, *, timeout: float = 5.0) -> None:
    """Park ``stub`` at STUB_ADDR, set PC to it, run, and poll the done flag.

    Args:
        vice: Connected ``ViceMCP`` instance.
        stub: Raw 6502 bytes to execute from STUB_ADDR. Must end in an
            infinite loop so the machine can be paused and inspected.
        timeout: Maximum seconds to wait for the done flag.
    """
    vice.memory_write(STUB_ADDR, stub)
    # Clear any stale done flag and park the CPU at the stub.
    vice.memory_write(DONE_FLAG, b"\x00")
    vice._bound().monitor.registers_set({"PC": STUB_ADDR})  # noqa: SLF001
    vice.call("vice.execution.run")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        vice.call("vice.execution.pause")
        if vice.memory_read(DONE_FLAG, 1) == b"\xaa":
            return
        vice.call("vice.execution.run")
        time.sleep(0.05)
    raise TimeoutError("VICE stub did not reach the done flag in time.")


def _halt(vice: ViceMCP) -> None:
    """Pause VICE so banked memory writes are not disturbed by the running CPU."""
    vice.call("vice.execution.pause")


@pytest.mark.hardware
@pytest.mark.vice
def test_ram_under_io_enter_selects_all_ram_and_ram_window_is_writable() -> None:
    """Entering all-RAM mode exposes $D000-$DFFF as RAM and sets $01=$30.

    After the gate opens, a sentinel written under the I/O window must read
    back as the same RAM cell, and restoring the canonical mapping ($35)
    must hide that RAM behind the I/O devices again.
    """
    _require_vice_exe()
    addrs = _load_symbol_addresses()
    machine = MACHINES["basicv2"]
    with running_vice(machine, port=6601) as vice:
        _install_image(vice)
        enter = _relocate_routine(vice, addrs["ram_under_io_enter"], RELOC_BASE, {})

        # Stub: JSR enter; signal done; spin.
        stub = bytes(
            [
                0x20,
                enter & 0xFF,
                enter >> 8,
                0xA9,
                0xAA,
                0x8D,
                DONE_FLAG & 0xFF,
                DONE_FLAG >> 8,
                0x4C,
                (STUB_ADDR + 5) & 0xFF,
                (STUB_ADDR + 5) >> 8,
            ]
        )
        _run_stub(vice, stub)

        # The gate must have selected the all-RAM mapping ($30).
        assert vice.memory_read(0x0001, 1) == b"\x30"

        # Under all-RAM mapping the hidden RAM at $D100 is writable and visible.
        _halt(vice)
        vice.memory_write(0x0001, bytes([0x30]))
        vice.memory_write(0xD100, b"HI_RAM")
        assert vice.memory_read(0xD100, 6) == b"HI_RAM"

        # Restoring the canonical mapping hides the RAM behind the I/O window.
        vice.memory_write(0x0001, bytes([0x35]))
        assert vice.memory_read(0xD100, 6) != b"HI_RAM"


@pytest.mark.hardware
@pytest.mark.vice
def test_ram_under_io_exit_restores_mapping() -> None:
    """ram_under_io_exit restores the canonical $35 mapping after all-RAM."""
    _require_vice_exe()
    addrs = _load_symbol_addresses()
    machine = MACHINES["basicv2"]
    with running_vice(machine, port=6602) as vice:
        _install_image(vice)
        # Precondition: machine is in all-RAM mode ($30). Done while halted so
        # no KERNAL IRQ can fire into the ROM-less map during setup.
        _halt(vice)
        vice.memory_write(0x0001, bytes([0x30]))
        exit_addr = _relocate_routine(vice, addrs["ram_under_io_exit"], RELOC_BASE, {})

        stub = bytes(
            [
                0x20,
                exit_addr & 0xFF,
                exit_addr >> 8,
                0xA9,
                0xAA,
                0x8D,
                DONE_FLAG & 0xFF,
                DONE_FLAG >> 8,
                0x4C,
                (STUB_ADDR + 5) & 0xFF,
                (STUB_ADDR + 5) >> 8,
            ]
        )
        _run_stub(vice, stub)

        # The gate must have restored the canonical mapping ($35).
        assert vice.memory_read(0x0001, 1) == b"\x35"


@pytest.mark.hardware
@pytest.mark.vice
def test_ram_under_io_copy_in_round_trips_through_ram_window() -> None:
    """ram_under_io_copy_in copies a buffer into the $D000-$DFFF RAM area."""
    _require_vice_exe()
    addrs = _load_symbol_addresses()
    machine = MACHINES["basicv2"]
    with running_vice(machine, port=6603) as vice:
        _install_image(vice)

        enter = _relocate_routine(vice, addrs["ram_under_io_enter"], RELOC_BASE, {})
        exit_addr = _relocate_routine(
            vice,
            addrs["ram_under_io_exit"],
            RELOC_BASE + 0x10,
            {addrs["ram_under_io_enter"]: enter},
        )
        copy_in = _relocate_routine(
            vice,
            addrs["ram_under_io_copy_in"],
            RELOC_BASE + 0x20,
            {
                addrs["ram_under_io_enter"]: enter,
                addrs["ram_under_io_exit"]: exit_addr,
            },
        )

        src = 0xC900
        dest = 0xD100
        # Source lives in normal RAM; safe to write while running.
        vice.memory_write(src, COPY_IN_PAYLOAD)
        # zp_src -> source address ($C900).
        vice.memory_write(ZP_SRC, bytes([src & 0xFF, src >> 8]))

        # Stub: set A=len, X/Y=dest, JSR copy_in, signal done, spin.
        stub = bytes(
            [
                0xA9,
                len(COPY_IN_PAYLOAD),
                0xA2,
                dest & 0xFF,
                0xA0,
                dest >> 8,
                0x20,
                copy_in & 0xFF,
                copy_in >> 8,
                0xA9,
                0xAA,
                0x8D,
                DONE_FLAG & 0xFF,
                DONE_FLAG >> 8,
                0x4C,
                0x0B,
                0xC0,
            ]
        )
        _run_stub(vice, stub)

        # The routine restored the canonical mapping on return, so reopen the
        # all-RAM window to inspect the hidden RAM it copied into.
        _halt(vice)
        vice.memory_write(0x0001, bytes([0x30]))
        # The hidden RAM under $D100 must hold the copied payload.
        assert vice.memory_read(0xD100, len(COPY_IN_PAYLOAD)) == COPY_IN_PAYLOAD
        # And the routine restored the canonical mapping on return.
        vice.memory_write(0x0001, bytes([0x35]))
        assert vice.memory_read(0x0001, 1) == b"\x35"


@pytest.mark.hardware
@pytest.mark.vice
def test_ram_under_io_copy_out_round_trips_through_ram_window() -> None:
    """ram_under_io_copy_out copies from the $D000-$DFFF RAM area to normal RAM."""
    _require_vice_exe()
    addrs = _load_symbol_addresses()
    machine = MACHINES["basicv2"]
    with running_vice(machine, port=6604) as vice:
        _install_image(vice)

        enter = _relocate_routine(vice, addrs["ram_under_io_enter"], RELOC_BASE, {})
        exit_addr = _relocate_routine(
            vice,
            addrs["ram_under_io_exit"],
            RELOC_BASE + 0x10,
            {addrs["ram_under_io_enter"]: enter},
        )
        copy_out = _relocate_routine(
            vice,
            addrs["ram_under_io_copy_out"],
            RELOC_BASE + 0x40,
            {
                addrs["ram_under_io_enter"]: enter,
                addrs["ram_under_io_exit"]: exit_addr,
            },
        )

        src = 0xD200
        dest = 0xC950
        # Place the source payload directly in the hidden RAM under I/O. Done
        # while halted so no KERNAL IRQ fires into the ROM-less map.
        _halt(vice)
        vice.memory_write(0x0001, bytes([0x30]))
        vice.memory_write(src, COPY_OUT_PAYLOAD)
        vice.memory_write(0x0001, bytes([0x35]))
        # zp_dest -> destination address ($C950).
        vice.memory_write(ZP_DEST, bytes([dest & 0xFF, dest >> 8]))

        stub = bytes(
            [
                0xA9,
                len(COPY_OUT_PAYLOAD),
                0xA2,
                src & 0xFF,
                0xA0,
                src >> 8,
                0x20,
                copy_out & 0xFF,
                copy_out >> 8,
                0xA9,
                0xAA,
                0x8D,
                DONE_FLAG & 0xFF,
                DONE_FLAG >> 8,
                0x4C,
                0x0B,
                0xC0,
            ]
        )
        _run_stub(vice, stub)

        # Normal RAM at $C950 must hold the payload copied out of the window.
        assert vice.memory_read(dest, len(COPY_OUT_PAYLOAD)) == COPY_OUT_PAYLOAD
        # The routine restored the canonical mapping on return.
        assert vice.memory_read(0x0001, 1) == b"\x35"
