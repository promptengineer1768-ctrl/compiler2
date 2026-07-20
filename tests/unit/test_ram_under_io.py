"""Unit tests for RAM-under-I/O gate routines.

Tests enter/exit and copy operations that bypass the I/O page ($D000-$DFFF)
to access underlying RAM.
"""

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

# Ensure the C64 emulator bindings can be imported
try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    pass


def _load_zp_address(name: str) -> int:
    """Helper to parse zero-page symbol allocation address."""
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
    """Helper to parse the address of a symbol from compiler.map or routine_directory.json."""
    labels = ROOT / "build" / "compiler.lbl"
    if labels.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)

    dir_path = ROOT / "build" / "routine_directory.json"
    if dir_path.exists():
        try:
            import json

            with open(dir_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            routines = data.get("routines", {})
            if symbol_name in routines:
                addr_str = routines[symbol_name].get("address", "")
                if addr_str.startswith("$"):
                    return int(addr_str[1:], 16)
        except Exception:
            pass

    # Fallback to compiler.map
    map_path = ROOT / "build" / "compiler.map"
    if not map_path.exists():
        pytest.fail(
            f"build/compiler.map not found. Run build.ps1 first. Missing: {symbol_name}"
        )

    # Look for symbol name in map
    # A line in ld65 map: symbol_name       001234
    pattern = rf"\b{symbol_name}\b\s+([0-9A-Fa-f]{{6}})"
    content = map_path.read_text(encoding="utf-8")
    match = re.search(pattern, content)
    if match:
        return int(match.group(1), 16)

    pytest.fail(
        f"Symbol '{symbol_name}' not found in compiler.map or routine directory."
    )


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


_RAM_UNDER_IO_SKIP_REASON = (
    "emu6502 does not model the $01 processor port / RAM-under-I/O; "
    "authoritative coverage is in tests/hardware/test_ram_under_io.py (VICE)."
)


def _emulator_models_ram_under_io() -> bool:
    """Detect whether the local emulator models the $01 port and RAM-under-I/O.

    Returns:
        True when a ``STA $01`` with an all-RAM mapping byte ($30) is observable
        via a subsequent CPU read; real C64 hardware preserves $30 while the
        unmodeled emulator forces the bits back to $35.
    """
    try:
        from emu6502_c64_bindings import C64Emu6502
    except ImportError:
        return False
    dll = _dll_path()
    emu = C64Emu6502(lib_path=dll)
    # LDA #$30; STA $01; RTS, parked at $0200.
    program = bytes([0xA9, 0x30, 0x8D, 0x01, 0x00, 0x60])
    emu.write_mem_range(0x0200, program)
    emu.write_mem(0x0001, 0x35)
    emu.execute_rts(0x0200, 1000)
    return bool(emu.read_mem(0x0001) == 0x30)


@pytest.mark.unit
@pytest.mark.local
class TestRamUnderIoGate:
    """Unit tests for the RAM-under-I/O gate."""

    @pytest.mark.callable_coverage("ram_under_io_enter", executor="execute_rts")
    def test_gate_enter_sets_all_ram_and_sei(self) -> None:
        """ram_under_io_enter must set $01 to $30 and set interrupt disable flag."""
        if not _emulator_models_ram_under_io():
            pytest.skip(_RAM_UNDER_IO_SKIP_REASON)
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)

        # Load compiled compiler.bin
        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.fail("build/compiler.bin not found. Run build.ps1 first.")

        # Load binary into memory (standard load address is $0801, read from first two bytes)
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])

        # Find entry point
        addr = _load_symbol_address("ram_under_io_enter")

        # Set initial C64 state: mapping = $35, interrupts CLI (I=0)
        emu.write_mem(0x0001, 0x35)
        state = emu.get_state()
        emu.set_p(state.p & ~0x04)  # Clear Interrupt flag (CLI)

        # Execute subroutine
        emu.execute(addr, 1000)

        # Verify results
        new_state = emu.get_state()
        assert (
            emu.read_mem(0x0001) == 0x30
        ), "ram_under_io_enter must select all-RAM mapping ($30)"
        assert (
            new_state.p & 0x04
        ) != 0, "ram_under_io_enter must set the Interrupt Disable (I) flag"

    @pytest.mark.callable_coverage("ram_under_io_exit", executor="execute_rts")
    def test_gate_exit_restores_mapping_and_cli(self) -> None:
        """ram_under_io_exit must restore the mapping to $35 and clear interrupt disable."""
        if not _emulator_models_ram_under_io():
            pytest.skip(_RAM_UNDER_IO_SKIP_REASON)
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)

        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])

        addr = _load_symbol_address("ram_under_io_exit")

        # Setup pre-conditions for exit: current mapping is $30, IRQ disabled
        emu.write_mem(0x0001, 0x30)
        emu.set_p(emu.get_state().p | 0x04)  # Set Interrupt flag (SEI)

        emu.execute(addr, 1000)

        # Verify exit restored state
        new_state = emu.get_state()
        assert (
            emu.read_mem(0x0001) == 0x35
        ), "ram_under_io_exit must restore mapping to $35"
        assert (
            new_state.p & 0x04
        ) == 0, "ram_under_io_exit must restore interrupt state (CLI)"

    @pytest.mark.callable_coverage("ram_under_io_copy_in", executor="execute_rts")
    def test_copy_in_copies_to_under_io_ram(self) -> None:
        """ram_under_io_copy_in copies a buffer into the $D000-$DFFF RAM area."""
        if not _emulator_models_ram_under_io():
            pytest.skip(_RAM_UNDER_IO_SKIP_REASON)
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)

        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])

        addr = _load_symbol_address("ram_under_io_copy_in")

        # Prepare source buffer in normal RAM outside the linked image.
        src_data = b"TEST_RAM_UNDER_IO_PAYLOAD"
        emu.write_mem_range(0xC900, src_data)

        # Setup registers: X/Y = destination ($D100), A = length, src pointer in zero page
        zp_src_addr = _load_zp_address("zp_src")

        # Write source address ($C900) to zp_src (little endian)
        emu.write_mem(zp_src_addr, 0x00)
        emu.write_mem(zp_src_addr + 1, 0xC9)

        # Set CPU registers before call
        emu.set_x(0x00)  # Dest low byte ($D100)
        emu.set_y(0xD1)  # Dest high byte ($D100)
        emu.set_a(len(src_data))

        # Run
        emu.execute(addr, 5000)

        # Verify RAM under I/O has the copy
        # To read it back, we temporarily map out I/O via $0001 = $30
        assert (
            emu.read_mem(0x0001) == 0x35
        ), "ram_under_io_copy_in must restore canonical mapping before return"
        emu.write_mem(0x0001, 0x30)
        copied = emu.read_mem_range(0xD100, 0xD100 + len(src_data) - 1)
        assert copied == src_data

    @pytest.mark.callable_coverage("ram_under_io_copy_out", executor="execute_rts")
    def test_copy_out_reads_from_under_io_ram(self) -> None:
        """ram_under_io_copy_out copies from the $D000-$DFFF RAM area back to normal RAM."""
        if not _emulator_models_ram_under_io():
            pytest.skip(_RAM_UNDER_IO_SKIP_REASON)
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)

        bin_path = ROOT / "build" / "compiler.bin"
        if not bin_path.exists():
            pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
        payload = bin_path.read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])

        addr = _load_symbol_address("ram_under_io_copy_out")

        # Prepare source data directly in RAM under I/O
        src_data = b"READ_BACK_PAYLOAD"
        emu.write_mem(0x0001, 0x30)  # Map in all-RAM temporarily to write
        emu.write_mem_range(0xD200, src_data)
        emu.write_mem(0x0001, 0x35)  # Restore normal C64 mapping with I/O

        # Setup registers: X/Y = source ($D200), A = length, dest pointer in zero page (zp_dest)
        zp_dest_addr = _load_zp_address("zp_dest")

        # Write destination address ($C950) to zp_dest (little endian)
        emu.write_mem(zp_dest_addr, 0x50)
        emu.write_mem(zp_dest_addr + 1, 0xC9)

        # Set CPU registers before call
        emu.set_x(0x00)  # Source low byte ($D200)
        emu.set_y(0xD2)  # Source high byte ($D200)
        emu.set_a(len(src_data))

        # Run
        emu.execute(addr, 5000)

        # Verify normal RAM at $C950 has the copy
        assert (
            emu.read_mem(0x0001) == 0x35
        ), "ram_under_io_copy_out must restore canonical mapping before return"
        copied = emu.read_mem_range(0xC950, 0xC950 + len(src_data) - 1)
        assert copied == src_data

    def test_copy_routines_link_to_shared_exit_gate(self) -> None:
        """Linked copy routines must close the RAM-under-I/O gate before RTS."""
        exit_addr = _load_symbol_address("ram_under_io_exit")
        jsr_exit = bytes([0x20, exit_addr & 0xFF, exit_addr >> 8])
        for symbol in ("ram_under_io_copy_in", "ram_under_io_copy_out"):
            routine = _linked_bytes(_load_symbol_address(symbol), 64)
            jsr_index = routine.find(jsr_exit)
            assert jsr_index >= 0, f"{symbol} must call ram_under_io_exit"
            rts_index = routine.find(b"\x60", jsr_index)
            assert rts_index > jsr_index, f"{symbol} must RTS after closing the gate"
