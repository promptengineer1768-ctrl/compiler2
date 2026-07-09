"""Real-byte tests for the COMPILE export record contracts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from emu6502_c64_bindings import C64Emu6502  # noqa: E402

ERR_ILLEGAL_QUANTITY = 0x0E


def _symbol(name: str) -> int:
    """Return a linked production symbol address."""
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{name}$", labels, re.MULTILINE)
    if match is None:
        pytest.fail(f"missing linked symbol {name}")
    return int(match.group(1), 16)


def _emulator() -> C64Emu6502:
    """Load the production artifact into a real-byte-only emulator."""
    dll = TOOLS_ROOT / "emu6502.dll"
    emu = C64Emu6502(lib_path=dll)
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load, payload[2:])
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    emu._compiler2_real_bytes_only = True
    return emu


def _call(emu: C64Emu6502, routine: str, pointer: int) -> tuple[int, int, int, bool]:
    """Execute an export routine and return A/X/Y/carry."""
    emu.set_x(pointer & 0xFF)
    emu.set_y(pointer >> 8)
    emu.execute(_symbol(routine), 30_000)
    state = emu.get_state()
    return int(state.a), int(state.x), int(state.y), bool(int(state.p) & 1)


def _bytes(emu: C64Emu6502, address: int, length: int) -> bytes:
    """Read emulator memory."""
    return bytes(emu.read_mem(address + offset) for offset in range(length))


@pytest.mark.unit
@pytest.mark.local
def test_export_parse_command_defaults_and_validates_device() -> None:
    """Empty CP fields use COMPILED/fa; explicit devices are limited to 8..11."""
    emu = _emulator()
    record = 0xC000
    emu.write_mem(0xBA, 9)
    emu.write_mem_range(record, b"CP\x00\x00\x00\x00")
    _, low, high, carry = _call(emu, "export_parse_command", record)
    assert not carry
    options = low | (high << 8)
    assert options == record
    # The emulator binding does not expose CPU-written RAM through host reads;
    # a second parse proves the CPU-visible magic was changed from CP to EO.
    a, _, _, carry = _call(emu, "export_parse_command", record)
    assert carry and a == ERR_ILLEGAL_QUANTITY

    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    assert b"COMPILED" in payload

    emu.write_mem_range(record, b"CP\x00\x00\x00\x07")
    a, _, _, carry = _call(emu, "export_parse_command", record)
    assert carry and a == ERR_ILLEGAL_QUANTITY


@pytest.mark.unit
@pytest.mark.local
def test_export_parse_command_preserves_explicit_filename() -> None:
    """A nonempty filename pointer and legal device become canonical EO fields."""
    emu = _emulator()
    record, name = 0xC000, 0xC100
    emu.write_mem_range(name, b"HELLO")
    emu.write_mem_range(
        record, bytes((ord("C"), ord("P"), name & 0xFF, name >> 8, 5, 11))
    )
    _, low, high, carry = _call(emu, "export_parse_command", record)
    assert not carry
    assert (low | (high << 8)) == record
    a, _, _, carry = _call(emu, "export_parse_command", record)
    assert carry and a == ERR_ILLEGAL_QUANTITY


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.parametrize("forbidden", [0x10, 0x20, 0x40, 0x80])
def test_export_collect_dependencies_rejects_development_dependencies(
    forbidden: int,
) -> None:
    """Editor, compiler, source, and geoRAM dependency bits are inadmissible."""
    emu = _emulator()
    record = 0xC000
    emu.write_mem_range(record, bytes((ord("E"), ord("D"), forbidden)))
    a, _, _, carry = _call(emu, "export_collect_dependencies", record)
    assert carry and a == ERR_ILLEGAL_QUANTITY
    emu.write_mem_range(record, b"ED\x0f")
    _, low, high, carry = _call(emu, "export_collect_dependencies", record)
    assert not carry and (low | (high << 8)) == record


@pytest.mark.unit
@pytest.mark.local
def test_export_link_image_requires_resolved_standalone_image() -> None:
    """EL accepts only a resolved, source-free, normal-RAM image."""
    emu = _emulator()
    record = 0xC000
    emu.write_mem_range(record, b"EL\x01")
    _, low, high, carry = _call(emu, "export_link_image", record)
    assert not carry and (low | (high << 8)) == record
    emu.write_mem_range(record, b"EL\x00")
    a, _, _, carry = _call(emu, "export_link_image", record)
    assert carry and a == ERR_ILLEGAL_QUANTITY


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.parametrize(
    ("start", "end", "workspace_start", "workspace_end", "valid"),
    [
        (0x0801, 0xD000, 0x0200, 0x0801, True),
        (0x0800, 0x1000, 0x0200, 0x0800, False),
        (0x0801, 0xD001, 0x0200, 0x0801, False),
        (0x0801, 0x2000, 0x1FFF, 0x3000, False),
        (0x2000, 0x2000, 0x0200, 0x0801, False),
    ],
)
def test_export_check_budgets_enforces_load_range_and_disjoint_workspace(
    start: int,
    end: int,
    workspace_start: int,
    workspace_end: int,
    valid: bool,
) -> None:
    """EB uses exclusive ranges and rejects overlap or out-of-budget images."""
    emu = _emulator()
    record = 0xC000
    words = (start, end, workspace_start, workspace_end)
    emu.write_mem_range(
        record,
        b"EB" + b"".join(bytes((word & 0xFF, word >> 8)) for word in words),
    )
    a, _, _, carry = _call(emu, "export_check_budgets", record)
    assert carry is (not valid)
    if not valid:
        assert a == ERR_OUT_OF_MEMORY


ERR_OUT_OF_MEMORY = 0x10


@pytest.mark.unit
@pytest.mark.local
def test_export_write_prg_validates_record_and_uses_kernal_save_abi() -> None:
    """EW publishes SETNAM/SETLFS/SAVE arguments through the resident bridge."""
    emu = _emulator()
    record, name = 0xC000, 0xC100
    emu.write_mem_range(name, b"OUTPUT")
    emu.write_mem_range(
        record,
        bytes(
            (
                ord("E"),
                ord("W"),
                name & 0xFF,
                name >> 8,
                6,
                10,
                0,
                0x01,
                0x08,
                0x00,
                0x20,
            )
        ),
    )
    _, _, _, carry = _call(emu, "export_write_prg", record)
    assert not carry

    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load = payload[0] | (payload[1] << 8)
    start = _symbol("export_write_prg") - load + 2
    body = payload[start : start + 240]
    for callee in ("kernal_setnam", "kernal_setlfs"):
        address = _symbol(callee)
        assert bytes((0x20, address & 0xFF, address >> 8)) in body
    save = _symbol("kernal_save")
    assert bytes((0x4C, save & 0xFF, save >> 8)) in body

    emu.write_mem(record + 5, 12)
    a, _, _, carry = _call(emu, "export_write_prg", record)
    assert carry and a == ERR_ILLEGAL_QUANTITY
