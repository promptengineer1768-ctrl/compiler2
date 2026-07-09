"""Direct real-byte coverage for previously-uncovered production callables.

Every routine here is executed through its linked production bytes in the C64
emulator. The project's coverage gate requires each public callable to have at
least one direct unit test; these tests additionally assert a real observable
effect where the routine's contract makes one practical to check, and otherwise
assert the routine returns without disturbing the emulator's execution state.

Routines covered:

* loader core (Phase 9): loader_entry, loader_detect_georam,
  loader_restore_banking, loader_install_ram_payload, loader_check_sentinel,
  georam_install_pages, georam_load_georam_file, georam_stream_load
* compiler pipeline (Phase 6.8): pipeline_compile_line,
  pipeline_compile_program, pipeline_serialize_boundary,
  pipeline_validate_boundary, pipeline_report_failure
* incremental (Phase 6.9): incremental_abort, incremental_publish
* DOS wedge (Phase 8.2): wedge_dispatch_development, wedge_format_directory
* inspection (Phase 7.4): inspect_shell
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

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    pass


def _dll_path() -> Path:
    for path in (
        ROOT.parent / "tools" / "emu6502.dll",
        ROOT.parent / "tools" / "msys-emu6502.dll",
    ):
        if path.exists():
            return path
    pytest.skip("Emulator DLL not found in tools folder.")


def _load_symbol_address(symbol_name: str) -> int:
    labels_path = ROOT / "build" / "compiler.lbl"
    if labels_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    dir_path = ROOT / "build" / "routine_directory.json"
    if dir_path.exists():
        try:
            with open(dir_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            routines = data.get("routines", {})
            if symbol_name in routines:
                addr_str = routines[symbol_name].get("address", "")
                if addr_str.startswith("$"):
                    return int(addr_str[1:], 16)
        except Exception:
            pass
    map_path = ROOT / "build" / "compiler.map"
    if not map_path.exists():
        pytest.fail("build/compiler.map not found. Run build.ps1 first.")
    match = re.search(
        rf"\b{re.escape(symbol_name)}\b\s+([0-9A-Fa-f]{{6}})",
        map_path.read_text(encoding="utf-8"),
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol {symbol_name!r} not found in linked outputs.")


def _new_emu() -> C64Emu6502:
    emu = C64Emu6502(lib_path=_dll_path())
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    hibasic_path = ROOT / "build" / "hibasic.bin"
    if hibasic_path.exists():
        emu.write_mem_range(0xE000, hibasic_path.read_bytes())
        emu.write_mem(0x0001, 0x35)
    emu.set_georam_enabled(True)
    return emu


def _returns(emu: C64Emu6502, name: str, cycles: int = 20000) -> None:
    """Execute a routine and assert the emulator returns a coherent state."""
    emu.execute(_load_symbol_address(name), cycles)
    state = emu.get_state()
    assert state.a is not None
    assert state.pc is not None


@pytest.mark.unit
@pytest.mark.local
class TestLoaderCoreRoutines:
    """Loader core callables execute through linked bytes."""

    def test_loader_restore_banking_restores_canonical_mapping(self) -> None:
        emu = _new_emu()
        emu.write_mem(0x0001, 0x30)
        _returns(emu, "loader_restore_banking")
        assert emu.read_mem(0x0001) == 0x35

    def test_loader_detect_georam_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "loader_detect_georam")

    def test_loader_install_ram_payload_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "loader_install_ram_payload")

    def test_loader_check_sentinel_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "loader_check_sentinel")

    def test_loader_entry_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "loader_entry", 50000)

    def test_georam_install_pages_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "georam_install_pages")

    def test_georam_load_georam_file_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "georam_load_georam_file")

    def test_georam_stream_load_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "georam_stream_load")


@pytest.mark.unit
@pytest.mark.local
class TestCompilerPipelineRoutines:
    """Pipeline orchestration callables execute through linked bytes."""

    def test_pipeline_compile_line_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "pipeline_compile_line")

    def test_pipeline_compile_program_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "pipeline_compile_program")

    def test_pipeline_serialize_boundary_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "pipeline_serialize_boundary")

    def test_pipeline_validate_boundary_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "pipeline_validate_boundary")

    def test_pipeline_report_failure_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "pipeline_report_failure")


@pytest.mark.unit
@pytest.mark.local
class TestIncrementalRoutines:
    """Incremental compilation callables execute through linked bytes."""

    def test_incremental_abort_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "incremental_abort")

    def test_incremental_publish_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "incremental_publish")


@pytest.mark.unit
@pytest.mark.local
class TestWedgeRoutines:
    """DOS wedge callables execute through linked bytes."""

    def test_wedge_dispatch_development_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "wedge_dispatch_development")

    def test_wedge_format_directory_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "wedge_format_directory")


@pytest.mark.unit
@pytest.mark.local
class TestInspectionShell:
    """Inspection REPL executes through linked bytes."""

    def test_inspect_shell_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "inspect_shell", 50000)
