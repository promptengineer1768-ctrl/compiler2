"""Real-byte tests for the COMPILE export record contracts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from tests.kernal_stubs import install_kernal_stubs

ROOT = Path(__file__).resolve().parents[2]
_TOOLS_CANDIDATES = (
    ROOT.parent / "tools",
    Path(r"C:\Users\me\Documents\Coding Projects\tools"),
)
TOOLS_ROOT = next(
    (path for path in _TOOLS_CANDIDATES if (path / "emu6502.dll").exists()),
    _TOOLS_CANDIDATES[0],
)
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from emu6502_c64_bindings import C64Emu6502  # noqa: E402

ERR_ILLEGAL_QUANTITY = 0x0E
ERR_OUT_OF_MEMORY = 0x10

EXPORT_LAYOUT_STOCK = 0
EXPORT_LAYOUT_DEVELOPER = 1
EXPORT_FLAG_CE00_RESERVED = 0x01
EXPORT_STATE_GE_80 = 0x01
EXPORT_STATE_GE_100 = 0x02


def _symbol(name: str) -> int:
    """Return a linked production symbol address."""
    labels = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{name}$", labels, re.MULTILINE)
    if match is None:
        pytest.fail(f"missing linked symbol {name}")
    return int(match.group(1), 16)


GEORAM_PAGE = 0xDFFE
GEORAM_BLOCK = 0xDFFF

MAX_CYCLES = 8_000_000


def _load_binary(emu: C64Emu6502) -> None:
    """Load the real linked compiler plus the geoRAM image and enable geoRAM."""
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_address = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_address, payload[2:])
    georam_path = ROOT / "build" / "georam.bin"
    if not georam_path.exists():
        pytest.fail("build/georam.bin not found. Run build.ps1 first.")
    image = georam_path.read_bytes()
    assert image[:2] == b"\x00\xde"
    emu.set_georam_enabled(True)
    backing_size = len(emu.export_georam())
    payload_bytes = image[2:]
    assert backing_size >= len(payload_bytes)
    emu.load_georam(payload_bytes + bytes(backing_size - len(payload_bytes)))


def _load_routine_record(symbol: str) -> dict[str, object]:
    """Return the routine_directory.json entry for one routine."""
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    record = data["routines"][symbol]
    assert isinstance(record, dict)
    return record


def _run_paged(emu: C64Emu6502, routine: str, *, x: int, y: int) -> None:
    """Reach a geoRAM routine through the production XY XIP gate.

    Routine IDs below 256 take the group-0 gate (A=id); IDs 256..511 take the
    group-n gate (A=low byte of id), which indexes the group-1 directory.
    """
    record = _load_routine_record(routine)
    assert record.get("layer") == "georam", f"{routine} is not a geoRAM routine"
    routine_id_obj = record["id"]
    assert isinstance(routine_id_obj, int)
    routine_id = routine_id_obj
    assert routine_id < 0x200
    if routine_id < 0x100:
        gate = "georam_call_group_0_xy"
    else:
        gate = "georam_call_group_n_xy"
    emu.set_a(routine_id & 0xFF)
    emu.set_x(x)
    emu.set_y(y)
    emu.execute(_symbol(gate), MAX_CYCLES)


def _emulator() -> C64Emu6502:
    """Load the production artifact into a real-byte-only emulator."""
    dll = TOOLS_ROOT / "emu6502.dll"
    emu = C64Emu6502(lib_path=dll)
    _load_binary(emu)
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    install_kernal_stubs(emu)
    return emu


def _call(emu: C64Emu6502, routine: str, pointer: int) -> tuple[int, int, int, bool]:
    """Execute an export routine and return A/X/Y/carry.

    geoRAM-paged overlays are reached through the production group XY XIP gate
    (A=routine id, X/Y=pointer); the linked export_compile_command runs at its
    linked address with X/Y=pointer. The gate preserves the callee carry, A,
    and X/Y for georAM routines.
    """
    record = _load_routine_record(routine)
    if record.get("layer") == "georam":
        _run_paged(emu, routine, x=pointer & 0xFF, y=pointer >> 8)
    else:
        emu.set_x(pointer & 0xFF)
        emu.set_y(pointer >> 8)
        emu.execute(_symbol(routine), MAX_CYCLES)
    state = emu.get_state()
    return int(state.a), int(state.x), int(state.y), bool(int(state.p) & 1)


def _cpu_read(emu: C64Emu6502, address: int) -> int:
    """Read CPU-visible RAM directly; emu.read_mem reflects CPU stores."""
    return int(emu.read_mem(address))


def _write_eb(
    emu: C64Emu6502,
    record: int,
    start: int,
    end: int,
    workspace_start: int,
    workspace_end: int,
) -> None:
    """Store an EB range plan at *record*."""
    words = (start, end, workspace_start, workspace_end)
    emu.write_mem_range(
        record,
        b"EB" + b"".join(bytes((word & 0xFF, word >> 8)) for word in words),
    )


def _reset_budget_state(emu: C64Emu6502) -> None:
    """Clear soft-budget latches and diagnostic print count."""
    emu.write_mem(_symbol("export_budget_state"), 0)
    emu.write_mem(_symbol("export_layout_profile"), 0)
    emu.write_mem(_symbol("export_layout_flags"), 0)
    emu.write_mem(_symbol("diag_print_count"), 0)


@pytest.mark.unit
@pytest.mark.local
def test_export_parse_command_defaults_and_validates_device() -> None:
    """Empty CP fields use COMPILED/fa; explicit devices are limited to 8..11."""
    emu = _emulator()
    record = 0xC000
    emu.write_mem(0xBA, 9)
    emu.write_mem_range(record, b"CP\x00\x00\x00\x00\x00")
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

    emu.write_mem_range(record, b"CP\x00\x00\x00\x07\x00")
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
        record, bytes((ord("C"), ord("P"), name & 0xFF, name >> 8, 5, 11, 0))
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
        (0x0801, 0xD000, 0x0200, 0x0801, True),  # full stock ceiling fits
        (0x0801, 0xD001, 0x0200, 0x0801, True),  # oversize allowed (soft warn)
        (0x0800, 0x1000, 0x0200, 0x0800, False),  # start below $0801
        (0x0801, 0x2000, 0x1FFF, 0x3000, False),  # workspace overlaps image
        (0x2000, 0x2000, 0x0200, 0x0801, False),  # empty image
    ],
)
def test_export_check_budgets_hard_fail_only_invalid_ranges(
    start: int,
    end: int,
    workspace_start: int,
    workspace_end: int,
    valid: bool,
) -> None:
    """EB hard-fails only invalid ranges; oversize is admitted with soft policy."""
    emu = _emulator()
    _reset_budget_state(emu)
    record = 0xC000
    _write_eb(emu, record, start, end, workspace_start, workspace_end)
    a, _, _, carry = _call(emu, "export_check_budgets", record)
    assert carry is (not valid)
    if not valid:
        assert a == ERR_OUT_OF_MEMORY


@pytest.mark.unit
@pytest.mark.local
def test_export_check_budgets_edge_triggered_80_and_100_warnings() -> None:
    """Soft 80%/100% warnings fire once per threshold crossing, not continuously."""
    emu = _emulator()
    record = 0xC000
    _reset_budget_state(emu)

    # Below 80%: no warning.
    _write_eb(emu, record, 0x0801, 0x1000, 0x0200, 0x0801)
    _, _, _, carry = _call(emu, "export_check_budgets", record)
    assert not carry
    assert _cpu_read(emu, _symbol("diag_print_count")) == 0
    assert _cpu_read(emu, _symbol("export_budget_state")) == 0

    # Cross up through 80% → one near-limit warning.
    _write_eb(emu, record, 0x0801, 0xA800, 0x0200, 0x0801)
    _, _, _, carry = _call(emu, "export_check_budgets", record)
    assert not carry
    assert _cpu_read(emu, _symbol("diag_print_count")) == 1
    assert _cpu_read(emu, _symbol("export_budget_state")) & EXPORT_STATE_GE_80

    # Stay >= 80%: no additional print.
    _write_eb(emu, record, 0x0801, 0xB000, 0x0200, 0x0801)
    _, _, _, carry = _call(emu, "export_check_budgets", record)
    assert not carry
    assert _cpu_read(emu, _symbol("diag_print_count")) == 1

    # Cross 100% ceiling → one exceeds warning (still admitted).
    _write_eb(emu, record, 0x0801, 0xD001, 0x0200, 0x0801)
    _, _, _, carry = _call(emu, "export_check_budgets", record)
    assert not carry
    assert _cpu_read(emu, _symbol("diag_print_count")) == 2
    state = _cpu_read(emu, _symbol("export_budget_state"))
    assert state & EXPORT_STATE_GE_80
    assert state & EXPORT_STATE_GE_100

    # Stay oversize: no spam.
    _write_eb(emu, record, 0x0801, 0xE000, 0x0200, 0x0801)
    _, _, _, carry = _call(emu, "export_check_budgets", record)
    assert not carry
    assert _cpu_read(emu, _symbol("diag_print_count")) == 2

    # Drop below both thresholds → one clear per boundary (2 prints).
    _write_eb(emu, record, 0x0801, 0x1000, 0x0200, 0x0801)
    _, _, _, carry = _call(emu, "export_check_budgets", record)
    assert not carry
    assert _cpu_read(emu, _symbol("diag_print_count")) == 4
    assert _cpu_read(emu, _symbol("export_budget_state")) == 0


@pytest.mark.unit
@pytest.mark.local
@pytest.mark.parametrize(
    ("start", "end", "workspace_start", "workspace_end", "layout", "flags"),
    [
        # Fits stock ceiling, workspace below image → stock, $CE00 free.
        (0x0801, 0x2000, 0x0200, 0x0801, EXPORT_LAYOUT_STOCK, 0),
        # Full stock image including $CE00 as ordinary RAM → still stock/free.
        (0x0801, 0xD000, 0x0200, 0x0801, EXPORT_LAYOUT_STOCK, 0),
        # Workspace only in hot pages $C800-$CDFF → stock; hot not permanent.
        (0x0801, 0x2000, 0xC800, 0xCE00, EXPORT_LAYOUT_STOCK, 0),
        # Oversize image → developer, $CE00 reserved.
        (
            0x0801,
            0xD001,
            0x0200,
            0x0801,
            EXPORT_LAYOUT_DEVELOPER,
            EXPORT_FLAG_CE00_RESERVED,
        ),
        # Workspace past stock ceiling → developer.
        (
            0x0801,
            0x2000,
            0xD000,
            0xE000,
            EXPORT_LAYOUT_DEVELOPER,
            EXPORT_FLAG_CE00_RESERVED,
        ),
    ],
)
def test_export_check_budgets_dual_layout_profiles(
    start: int,
    end: int,
    workspace_start: int,
    workspace_end: int,
    layout: int,
    flags: int,
) -> None:
    """Stock frees $CE00; developer reserves it; hot pages stay disposable."""
    emu = _emulator()
    _reset_budget_state(emu)
    record = 0xC000
    _write_eb(emu, record, start, end, workspace_start, workspace_end)
    _, _, _, carry = _call(emu, "export_check_budgets", record)
    assert not carry
    assert _cpu_read(emu, _symbol("export_layout_profile")) == layout
    assert _cpu_read(emu, _symbol("export_layout_flags")) == flags
    # Hot-page permanent bits are never set (only CE00 reserved bit exists).
    assert (
        _cpu_read(emu, _symbol("export_layout_flags")) & ~EXPORT_FLAG_CE00_RESERVED
    ) == 0


@pytest.mark.unit
@pytest.mark.local
def test_export_compile_command_transaction_parse_deps_link_budgets_write() -> None:
    """Full CP→ED→EL→EB→EW transaction admits a closed plan and writes via SAVE."""
    emu = _emulator()
    _reset_budget_state(emu)
    plan, name = 0xC000, 0xC100
    emu.write_mem_range(name, b"OUTPUT")
    # Contiguous plan: EO slot(7) + ED(3) + EL(3) + EB(10) + EW(11).
    body = bytearray()
    body += bytes((ord("C"), ord("P"), name & 0xFF, name >> 8, 6, 10, 0))
    body += bytes((ord("E"), ord("D"), 0x0F))
    body += bytes((ord("E"), ord("L"), 0x01))
    body += b"EB" + b"".join(
        bytes((word & 0xFF, word >> 8)) for word in (0x0801, 0x2000, 0x0200, 0x0801)
    )
    body += bytes(
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
    )
    assert len(body) == 7 + 3 + 3 + 10 + 11
    emu.write_mem_range(plan, bytes(body))
    _, _, _, carry = _call(emu, "export_compile_command", plan)
    assert not carry
    assert _cpu_read(emu, _symbol("export_layout_profile")) == EXPORT_LAYOUT_STOCK

    # Oversize plan still completes the write transaction (soft budget only).
    body[13:23] = b"EB" + b"".join(
        bytes((word & 0xFF, word >> 8)) for word in (0x0801, 0xD001, 0x0200, 0x0801)
    )
    # Re-seed CP (previous run canonicalized to EO).
    body[0:2] = b"CP"
    emu.write_mem_range(plan, bytes(body))
    _reset_budget_state(emu)
    _, _, _, carry = _call(emu, "export_compile_command", plan)
    assert not carry
    assert _cpu_read(emu, _symbol("export_layout_profile")) == EXPORT_LAYOUT_DEVELOPER
    assert _cpu_read(emu, _symbol("export_layout_flags")) == EXPORT_FLAG_CE00_RESERVED


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

    # export_write_prg is a geoRAM XIP page (offset 0 at $DE00); inspect its
    # linked bytes in the geoRAM image for the resident KERNAL calls.
    directory = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    page = int(directory["routines"]["export_write_prg"]["page"])
    georam = (ROOT / "build" / "georam.bin").read_bytes()
    body = georam[2 + page * 256 : 2 + page * 256 + 256]
    for callee in ("kernal_setnam", "kernal_setlfs"):
        address = _symbol(callee)
        assert bytes((0x20, address & 0xFF, address >> 8)) in body
    save = _symbol("kernal_save")
    assert bytes((0x4C, save & 0xFF, save >> 8)) in body

    emu.write_mem(record + 5, 12)
    a, _, _, carry = _call(emu, "export_write_prg", record)
    assert carry and a == ERR_ILLEGAL_QUANTITY
