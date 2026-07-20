"""Real-byte tests for generated GeoRAM overlay dispatch."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import TypedDict, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    pass

MAX_CYCLES = 100_000


class RoutineRecord(TypedDict):
    """Generated fields consumed by the overlay tests."""

    id: int
    layer: str
    block: int
    page: int
    offset: int


def _dll_path() -> Path:
    path = TOOLS_ROOT / "emu6502.dll"
    if not path.exists():
        path = TOOLS_ROOT / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _address(symbol_name: str) -> int:
    labels = ROOT / "build" / "compiler.lbl"
    match = re.search(
        rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
        labels.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found in linked labels.")


def _directory_record(name: str) -> RoutineRecord:
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    record = cast(RoutineRecord, data["routines"][name])
    assert record["layer"] == "georam"
    return record


def _directory_count() -> int:
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    return sum(
        1 for record in data["routines"].values() if record.get("layer") == "georam"
    )


def _new_emulator() -> C64Emu6502:
    emu = C64Emu6502(lib_path=_dll_path())
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_address = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_address, payload[2:])
    emu.set_georam_enabled(True)
    emu.write_mem(0x0001, 0x35)
    return emu


def _execute(emu: C64Emu6502, routine: str, *, a: int | None = None) -> bool:
    if a is not None:
        emu.set_a(a)
    emu.execute(_address(routine), MAX_CYCLES)
    return bool(int(emu.get_state().p) & 0x01)


@pytest.mark.unit
@pytest.mark.local
class TestGeoramOverlayDispatch:
    """Resolution, nesting, and generated-directory integrity coverage."""

    @pytest.mark.callable_coverage("overlay_resolve", executor="execute")
    @pytest.mark.callable_coverage("editor_submit_line", executor="execute")
    def test_resolve_uses_generated_page_and_offset(self) -> None:
        """A real group-1 routine ID resolves to its generated placement."""
        emu = _new_emulator()
        record = _directory_record("editor_submit_line")
        routine_id = int(record["id"])
        assert routine_id >> 8 == 1
        assert not _execute(emu, "overlay_resolve", a=routine_id & 0xFF)
        state = emu.get_state()
        assert int(state.x) == int(record["page"])
        assert int(state.y) == int(record["offset"])
        assert _execute(emu, "overlay_resolve", a=0)

    @pytest.mark.callable_coverage("overlay_validate", executor="execute")
    @pytest.mark.callable_coverage("editor_submit_line", executor="execute")
    def test_validate_detects_generated_table_corruption(self) -> None:
        """Runtime validation rejects any byte drift in the linked tables."""
        emu = _new_emulator()
        assert not _execute(emu, "overlay_validate")
        count = emu.read_mem(_address("__overlay_directory_count"))
        assert count == _directory_count()

        record = _directory_record("editor_submit_line")
        table_byte = _address("georam_group_1_pages") + (int(record["id"]) & 0xFF)
        original = emu.read_mem(table_byte)
        emu.write_mem(table_byte, original ^ 1)
        assert _execute(emu, "overlay_validate")
        emu.write_mem(table_byte, original)
        assert not _execute(emu, "overlay_validate")

    @pytest.mark.callable_coverage("overlay_exit", executor="execute")
    @pytest.mark.callable_coverage("overlay_enter", executor="execute")
    @pytest.mark.callable_coverage("georam_select", executor="execute")
    @pytest.mark.callable_coverage("editor_submit_line", executor="execute")
    @pytest.mark.callable_coverage("editor_delete_line", executor="execute")
    def test_nested_enter_exit_restores_real_georam_selection(self) -> None:
        """Nested overlays restore each caller selection and reject underflow."""
        emu = _new_emulator()
        first = _directory_record("editor_submit_line")
        second = _directory_record("editor_delete_line")
        emu.set_a(5)
        emu.set_x(2)
        assert not _execute(emu, "georam_select")

        assert not _execute(emu, "overlay_enter", a=int(first["id"]) & 0xFF)
        assert emu.read_mem(0xDFFF) == int(first["block"])
        assert emu.read_mem(0xDFFE) == int(first["page"])
        assert emu.read_mem(_address("__overlay_stack_pointer")) == 1

        assert not _execute(emu, "overlay_enter", a=int(second["id"]) & 0xFF)
        assert emu.read_mem(0xDFFF) == int(second["block"])
        assert emu.read_mem(0xDFFE) == int(second["page"])
        assert emu.read_mem(_address("__overlay_stack_pointer")) == 2

        assert not _execute(emu, "overlay_exit")
        assert emu.read_mem(0xDFFF) == int(first["block"])
        assert emu.read_mem(0xDFFE) == int(first["page"])
        assert not _execute(emu, "overlay_exit")
        assert emu.read_mem(0xDFFF) == 2
        assert emu.read_mem(0xDFFE) == 5
        assert _execute(emu, "overlay_exit")
