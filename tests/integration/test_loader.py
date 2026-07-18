"""Integration tests for the uncompressed geoRAM loader sequence."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
TESTS_ROOT = ROOT / "tests"
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from tests.kernal_stubs import install_kernal_stubs  # noqa: E402

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    C64Emu6502 = None


def _address(symbol: str) -> int:
    """Resolve a linked routine or exported loader-state address."""
    data = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    routines = data.get("routines", {})
    if symbol in routines:
        value = routines[symbol]["address"]
        assert value != "dynamic"
        return int(value.removeprefix("$"), 16)
    lbl_path = ROOT / "build" / "compiler.lbl"
    match = re.search(
        rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}$",
        lbl_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol {symbol!r} not found")


def _emulator(*, georam: bool = True, reu: bool = False) -> Any:
    """Load the production compiler image into the local emulator."""
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    dll = next(
        (
            path
            for path in (TOOLS_ROOT / "emu6502.dll", TOOLS_ROOT / "msys-emu6502.dll")
            if path.exists()
        ),
        None,
    )
    if dll is None:
        pytest.skip("Emulator DLL not found in tools folder.")
    emu = C64Emu6502(lib_path=dll, georam=georam)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.write_mem(0x0001, 0x35)
    emu.set_georam_enabled(georam)
    emu.set_reu_enabled(reu)
    if reu:
        emu.load_reu(b"\x00" * (512 * 1024))
    return emu


def _run(emu: Any, symbol: str, cycles: int = 20_000) -> Any:
    """Execute one loader stage."""
    emu.execute(_address(symbol), cycles)
    return emu.get_state()


@pytest.mark.integration
@pytest.mark.local
def test_full_uncompressed_loader_sequence() -> None:
    """Validate, install, restore banking, and accept the installed sentinel."""
    emu = _emulator()
    pages = bytes((index * 17 + 3) & 0xFF for index in range(512))
    # The stage buffer holds a PRG: a two-byte load address, then the payload.
    emu.write_mem_range(_address("georam_stage_buffer"), b"\x00\x00" + pages)
    emu.write_mem_range(_address("georam_stage_page_count"), b"\x02")

    loaded = _run(emu, "georam_load_georam_file")
    assert (loaded.p & 1) == 0
    assert emu.read_mem(_address("georam_file_loaded")) == 1

    installed = _run(emu, "georam_install_pages")
    assert (installed.p & 1) == 0
    assert emu.read_mem(_address("georam_installed_pages")) == 2
    geo = emu.export_georam()
    c = 0
    for b in geo[0:512]:
        c ^= b
    assert c == 0, "installed geoRAM payload must xor to zero"
    checksum = 0
    for value in pages:
        checksum ^= value
    assert emu.read_mem(_address("georam_install_checksum")) == checksum

    _run(emu, "loader_restore_banking")
    assert emu.read_mem(_address("loader_banking_state")) == 0x35
    emu.write_mem_range(0x1000, b"\xa9")
    assert (_run(emu, "loader_check_sentinel").p & 1) == 0


@pytest.mark.integration
@pytest.mark.local
def test_install_reads_payload_after_prg_header() -> None:
    """georam_install_pages must copy the stage payload at offset +2, not an
    unrelated BSS region.

    Regression for the ca65 operator-precedence defect where
    ``#<georam_stage_buffer+2`` evaluated to ``(<addr)+2`` yielding a pointer
    ``buffer + 0x0202`` instead of ``buffer + 2``.
    """
    emu = _emulator()
    # Two distinguishable regions: correct payload (buffer+2) and the bytes that
    # the broken pointer (buffer+0x0202) would have read.
    page_bytes = 256
    page_count = 2
    total = page_count * page_bytes
    payload = bytes(((index * 7 + 1) & 0xFF) for index in range(total))
    wrong = bytes(((index * 13 + 0x80) & 0xFF) for index in range(total + 4))
    emu.write_mem_range(_address("georam_stage_buffer"), b"\x00\x00" + payload)
    emu.write_mem_range(_address("georam_stage_buffer") + 0x0202, wrong)
    emu.write_mem_range(_address("georam_stage_page_count"), bytes([page_count]))
    emu.write_mem(_address("georam_file_loaded"), 1)

    _run(emu, "georam_install_pages")

    geo = emu.export_georam()
    for page in range(page_count):
        installed = geo[page * page_bytes : (page + 1) * page_bytes]
        expected = payload[page * page_bytes : (page + 1) * page_bytes]
        assert installed == expected, f"page {page} installed wrong source bytes"


@pytest.mark.integration
@pytest.mark.local
def test_loader_rejects_missing_georam_image() -> None:
    """An empty disk-image stage cannot be installed or published."""
    emu = _emulator()
    emu.write_mem_range(_address("georam_stage_page_count"), b"\x00")
    assert (_run(emu, "georam_load_georam_file").p & 1) == 1
    assert (_run(emu, "georam_install_pages").p & 1) == 1


@pytest.mark.integration
@pytest.mark.local
def test_dual_detect_prefers_georam_when_both_present() -> None:
    """loader_detect_georam selects geoRAM store and marks REU assist."""
    emu = _emulator(georam=True, reu=True)
    state = _run(emu, "loader_detect_georam", 200_000)
    assert (state.p & 1) == 0
    assert emu.read_mem(_address("expansion_store")) == 1
    assert emu.read_mem(_address("expansion_reu_assist")) == 1
    assert emu.read_mem(_address("expansion_capacity_georam")) == 0x20
    assert emu.read_mem(_address("expansion_capacity_reu")) == 8


@pytest.mark.integration
@pytest.mark.local
def test_dual_detect_reu_only_selects_reu_store() -> None:
    """With only REU present the wrapper publishes REU store."""
    emu = _emulator(georam=False, reu=True)
    state = _run(emu, "loader_detect_georam", 200_000)
    assert (state.p & 1) == 0
    assert emu.read_mem(_address("expansion_store")) == 2
    assert emu.read_mem(_address("expansion_reu_assist")) == 0
    assert emu.read_mem(_address("expansion_capacity_reu")) == 8


@pytest.mark.integration
@pytest.mark.local
def test_loader_entry_fails_clean_without_devices() -> None:
    """loader_entry must not enter the shell when neither device validates."""
    emu = _emulator(georam=False, reu=False)
    # Undersized geoRAM keeps mapping visible while dual probe still fails.
    emu.set_georam_enabled(True)
    emu.load_georam(b"\x00" * (64 * 1024))
    emu.set_reu_enabled(False)
    install_kernal_stubs(emu)
    emu.write_mem(0x0001, 0x35)
    state = _run(emu, "loader_entry", 300_000)
    assert (state.p & 1) == 1
    assert state.a == 0x1D  # ERR_LOAD
    assert emu.read_mem(_address("loader_sequence_phase")) == 0xFF
    assert emu.read_mem(_address("expansion_store")) == 0
