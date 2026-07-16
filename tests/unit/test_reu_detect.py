"""Unit tests for non-destructive REU detection."""

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

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:  # pragma: no cover - environment-specific
    C64Emu6502 = None  # type: ignore[misc, assignment]


def _dll_path() -> Path:
    """Return the local emulator library or skip when it is unavailable."""
    for name in ("emu6502.dll", "msys-emu6502.dll"):
        path = TOOLS_ROOT / name
        if path.exists():
            return path
    pytest.skip("Emulator DLL not found in tools folder.")


def _load_symbol_address(symbol_name: str) -> int:
    """Resolve an exported symbol from the linked artifact."""
    dir_path = ROOT / "build" / "routine_directory.json"
    if dir_path.exists():
        try:
            data = json.loads(dir_path.read_text(encoding="utf-8"))
            routines = data.get("routines", {})
            if symbol_name in routines:
                addr_str = routines[symbol_name].get("address", "")
                if isinstance(addr_str, str) and addr_str.startswith("$"):
                    return int(addr_str[1:], 16)
        except Exception:
            pass
    lbl_path = ROOT / "build" / "compiler.lbl"
    if lbl_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            lbl_path.read_text(encoding="utf-8"),
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
    pytest.fail(f"Symbol '{symbol_name}' not found.")


def _load_binary(emu: Any, *, reu: bool, size: int = 512 * 1024) -> None:
    """Load the production image and configure REU presence."""
    bin_path = ROOT / "build" / "compiler.bin"
    if not bin_path.exists():
        pytest.fail("build/compiler.bin not found. Run build.ps1 first.")
    payload = bin_path.read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.write_mem(0x0001, 0x35)
    emu.set_georam_enabled(False)
    emu.set_reu_enabled(reu)
    if reu:
        # Seed non-zero probe sites so restore can be observed (within size).
        data = bytearray(b"\x00" * size)
        data[0] = 0x11
        if size > 0x40000:
            data[0x40000] = 0x22
        if size > 0x7FF00:
            data[0x7FF00] = 0x33
        emu.load_reu(bytes(data))


@pytest.mark.unit
@pytest.mark.local
class TestReuDetect:
    """REU detection and fingerprint tests."""

    def test_detect_reu_present_publishes_fingerprint(self) -> None:
        """detect_reu succeeds on 512 KiB REU and publishes capacity + fingerprint."""
        if C64Emu6502 is None:
            pytest.skip("Emulator binding unavailable")
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, reu=True)
        emu.write_mem(0xDF09, 0xAA)
        emu.write_mem(0xDF0A, 0x55)
        emu.execute(_load_symbol_address("detect_reu"), 200_000)
        state = emu.get_state()
        assert (state.p & 0x01) == 0
        assert emu.read_mem(_load_symbol_address("detect_reu_valid")) == 1
        assert emu.read_mem(_load_symbol_address("detect_reu_capacity_banks")) == 8
        assert emu.read_mem(_load_symbol_address("detect_reu_capacity_kib_hi")) == 0x02
        fp = emu.read_mem(_load_symbol_address("detect_reu_fingerprint"))
        assert fp != 0
        # REC mask/control restored
        assert emu.read_mem(0xDF09) == 0xAA
        assert emu.read_mem(0xDF0A) == 0x55
        # Probe bytes restored
        reu = emu.export_reu()
        assert reu[0] == 0x11
        assert reu[0x40000] == 0x22
        assert reu[0x7FF00] == 0x33

    def test_detect_reu_absent_fails_and_restores(self) -> None:
        """detect_reu fails cleanly when no REU is present."""
        if C64Emu6502 is None:
            pytest.skip("Emulator binding unavailable")
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, reu=False)
        emu.write_mem(0x0001, 0x35)
        emu.write_mem(0xDF09, 0x1E)
        emu.execute(_load_symbol_address("detect_reu"), 200_000)
        assert emu.get_state().p & 0x01
        assert emu.read_mem(_load_symbol_address("detect_reu_valid")) == 0
        assert emu.read_mem(_load_symbol_address("detect_reu_capacity_banks")) == 0
        assert emu.read_mem(0x0001) == 0x35

    def test_detect_reu_undersized_fails(self) -> None:
        """REU smaller than 512 KiB must not publish a valid profile."""
        if C64Emu6502 is None:
            pytest.skip("Emulator binding unavailable")
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, reu=True, size=256 * 1024)
        emu.execute(_load_symbol_address("detect_reu"), 200_000)
        assert emu.get_state().p & 0x01
        assert emu.read_mem(_load_symbol_address("detect_reu_valid")) == 0
        assert emu.read_mem(_load_symbol_address("detect_reu_fingerprint")) == 0

    def test_detect_reu_check_minimum(self) -> None:
        """detect_reu_check_minimum rejects fewer than 8 banks."""
        if C64Emu6502 is None:
            pytest.skip("Emulator binding unavailable")
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu, reu=True)
        banks = _load_symbol_address("detect_reu_capacity_banks")
        emu.write_mem(banks, 7)
        emu.execute(_load_symbol_address("detect_reu_check_minimum"), 5_000)
        assert emu.get_state().p & 0x01
        emu.write_mem(banks, 8)
        emu.execute(_load_symbol_address("detect_reu_check_minimum"), 5_000)
        assert (emu.get_state().p & 0x01) == 0

    def test_source_is_real_rec_probe_not_de00_fake(self) -> None:
        """REU detect must exercise REC DMA, not a geoRAM $DE00 fake."""
        source = (ROOT / "src" / "arena" / "reu_detect.asm").read_text(
            encoding="utf-8"
        )
        assert "REU_STATUS" in source or "$DF00" in source
        assert "REU_CMD_TO_REU" in source or "$80" in source
        assert "REU_CMD_FROM_REU" in source or "$81" in source
        assert "sta $DE00" not in source
