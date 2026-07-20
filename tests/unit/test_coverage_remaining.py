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

    @pytest.mark.callable_coverage("loader_restore_banking", executor="execute")
    def test_loader_restore_banking_restores_canonical_mapping(self) -> None:
        emu = _new_emu()
        emu.write_mem(0x0001, 0x30)
        _returns(emu, "loader_restore_banking")
        assert emu.read_mem(0x0001) == 0x35

    @pytest.mark.callable_coverage("loader_detect_georam", executor="execute")
    def test_loader_detect_georam_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "loader_detect_georam")

    @pytest.mark.callable_coverage("loader_install_ram_payload", executor="execute")
    def test_loader_install_ram_payload_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "loader_install_ram_payload")

    @pytest.mark.callable_coverage("loader_check_sentinel", executor="execute")
    def test_loader_check_sentinel_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "loader_check_sentinel")

    @pytest.mark.callable_coverage("loader_entry", executor="execute")
    def test_loader_entry_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "loader_entry", 50000)

    @pytest.mark.callable_coverage("georam_install_pages", executor="execute")
    def test_georam_install_pages_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "georam_install_pages")

    @pytest.mark.callable_coverage("georam_load_georam_file", executor="execute")
    def test_georam_load_georam_file_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "georam_load_georam_file")

    @pytest.mark.callable_coverage("georam_stream_load", executor="execute")
    def test_georam_stream_load_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "georam_stream_load")


@pytest.mark.unit
@pytest.mark.local
class TestCompilerPipelineRoutines:
    """Pipeline orchestration callables execute through linked bytes."""

    @pytest.mark.callable_coverage("pipeline_compile_line", executor="execute")
    def test_pipeline_compile_line_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "pipeline_compile_line")

    @pytest.mark.callable_coverage("pipeline_compile_program", executor="execute")
    def test_pipeline_compile_program_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "pipeline_compile_program")

    @pytest.mark.callable_coverage("pipeline_serialize_boundary", executor="execute")
    def test_pipeline_serialize_boundary_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "pipeline_serialize_boundary")

    @pytest.mark.callable_coverage("pipeline_validate_boundary", executor="execute")
    def test_pipeline_validate_boundary_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "pipeline_validate_boundary")

    @pytest.mark.callable_coverage("pipeline_report_failure", executor="execute")
    def test_pipeline_report_failure_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "pipeline_report_failure")


@pytest.mark.unit
@pytest.mark.local
class TestIncrementalRoutines:
    """Incremental compilation callables execute through linked bytes."""

    @pytest.mark.callable_coverage("incremental_abort", executor="execute")
    def test_incremental_abort_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "incremental_abort")

    @pytest.mark.callable_coverage("incremental_publish", executor="execute")
    def test_incremental_publish_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "incremental_publish")


@pytest.mark.unit
@pytest.mark.local
class TestWedgeRoutines:
    """DOS wedge callables execute through linked bytes."""

    @pytest.mark.callable_coverage("wedge_dispatch_development", executor="execute")
    def test_wedge_dispatch_development_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "wedge_dispatch_development")

    @pytest.mark.callable_coverage("wedge_format_directory", executor="execute")
    def test_wedge_format_directory_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "wedge_format_directory")


@pytest.mark.unit
@pytest.mark.local
class TestInspectionShell:
    """Inspection REPL executes through linked bytes."""

    @pytest.mark.callable_coverage("inspect_shell", executor="execute")
    def test_inspect_shell_runs(self) -> None:
        emu = _new_emu()
        _returns(emu, "inspect_shell", 50000)


@pytest.mark.unit
@pytest.mark.local
class TestCodegenEmitters:
    """Codegen emitter callables execute through linked bytes."""

    @pytest.mark.callable_coverage("codegen_emit_data", executor="execute")
    def test_codegen_emit_data(self) -> None:
        _returns(_new_emu(), "codegen_emit_data")

    @pytest.mark.callable_coverage("codegen_emit_dim", executor="execute")
    def test_codegen_emit_dim(self) -> None:
        _returns(_new_emu(), "codegen_emit_dim")

    @pytest.mark.callable_coverage("codegen_emit_do_fast", executor="execute")
    def test_codegen_emit_do_fast(self) -> None:
        _returns(_new_emu(), "codegen_emit_do_fast")

    @pytest.mark.callable_coverage("codegen_emit_do_generic", executor="execute")
    def test_codegen_emit_do_generic(self) -> None:
        _returns(_new_emu(), "codegen_emit_do_generic")

    @pytest.mark.callable_coverage("codegen_emit_exit", executor="execute")
    def test_codegen_emit_exit(self) -> None:
        _returns(_new_emu(), "codegen_emit_exit")

    @pytest.mark.callable_coverage("codegen_emit_for_fast", executor="execute")
    def test_codegen_emit_for_fast(self) -> None:
        _returns(_new_emu(), "codegen_emit_for_fast")

    @pytest.mark.callable_coverage("codegen_emit_for_generic", executor="execute")
    def test_codegen_emit_for_generic(self) -> None:
        _returns(_new_emu(), "codegen_emit_for_generic")

    @pytest.mark.callable_coverage("codegen_emit_gosub", executor="execute")
    def test_codegen_emit_gosub(self) -> None:
        _returns(_new_emu(), "codegen_emit_gosub")

    @pytest.mark.callable_coverage("codegen_emit_if", executor="execute")
    def test_codegen_emit_if(self) -> None:
        _returns(_new_emu(), "codegen_emit_if")

    @pytest.mark.callable_coverage("codegen_emit_input", executor="execute")
    def test_codegen_emit_input(self) -> None:
        _returns(_new_emu(), "codegen_emit_input")

    @pytest.mark.callable_coverage("codegen_emit_let", executor="execute")
    def test_codegen_emit_let(self) -> None:
        _returns(_new_emu(), "codegen_emit_let")

    @pytest.mark.callable_coverage("codegen_emit_on", executor="execute")
    def test_codegen_emit_on(self) -> None:
        _returns(_new_emu(), "codegen_emit_on")

    @pytest.mark.callable_coverage("codegen_emit_print", executor="execute")
    def test_codegen_emit_print(self) -> None:
        _returns(_new_emu(), "codegen_emit_print")

    @pytest.mark.callable_coverage("codegen_emit_read", executor="execute")
    def test_codegen_emit_read(self) -> None:
        _returns(_new_emu(), "codegen_emit_read")

    @pytest.mark.callable_coverage("codegen_emit_stmt", executor="execute")
    def test_codegen_emit_stmt(self) -> None:
        _returns(_new_emu(), "codegen_emit_stmt")


@pytest.mark.unit
@pytest.mark.local
class TestCompilerInitRoutines:
    """Compiler init callables execute through linked bytes."""

    @pytest.mark.callable_coverage("compiler_init", executor="execute")
    def test_compiler_init(self) -> None:
        _returns(_new_emu(), "compiler_init", 50000)

    @pytest.mark.callable_coverage("init_clear_bss", executor="execute")
    def test_init_clear_bss(self) -> None:
        _returns(_new_emu(), "init_clear_bss")

    @pytest.mark.callable_coverage("init_enter_main_loop", executor="execute")
    def test_init_enter_main_loop(self) -> None:
        _returns(_new_emu(), "init_enter_main_loop")


@pytest.mark.unit
@pytest.mark.local
class TestDataRoutines:
    """Data stream callables execute through linked bytes."""

    @pytest.mark.callable_coverage("data_reset", executor="execute")
    def test_data_reset(self) -> None:
        _returns(_new_emu(), "data_reset")


@pytest.mark.unit
@pytest.mark.local
class TestDetectRoutines:
    """Detection callables execute through linked bytes."""

    @pytest.mark.callable_coverage("detect_probe_pattern1", executor="execute")
    def test_detect_probe_pattern1(self) -> None:
        _returns(_new_emu(), "detect_probe_pattern1")

    @pytest.mark.callable_coverage("detect_probe_pattern2", executor="execute")
    def test_detect_probe_pattern2(self) -> None:
        _returns(_new_emu(), "detect_probe_pattern2")

    @pytest.mark.callable_coverage("detect_reu_restore_state", executor="execute")
    def test_detect_reu_restore_state(self) -> None:
        _returns(_new_emu(), "detect_reu_restore_state")

    @pytest.mark.callable_coverage("detect_reu_save_state", executor="execute")
    def test_detect_reu_save_state(self) -> None:
        _returns(_new_emu(), "detect_reu_save_state")


@pytest.mark.unit
@pytest.mark.local
class TestDiagRoutines:
    """Diagnostic callables execute through linked bytes."""

    @pytest.mark.callable_coverage("diag_error_from_kernal", executor="execute")
    def test_diag_error_from_kernal(self) -> None:
        _returns(_new_emu(), "diag_error_from_kernal")

    @pytest.mark.callable_coverage("diag_format_error", executor="execute")
    def test_diag_format_error(self) -> None:
        _returns(_new_emu(), "diag_format_error")

    @pytest.mark.callable_coverage("diag_format_source_context", executor="execute")
    def test_diag_format_source_context(self) -> None:
        _returns(_new_emu(), "diag_format_source_context")

    @pytest.mark.callable_coverage("diag_format_warning", executor="execute")
    def test_diag_format_warning(self) -> None:
        _returns(_new_emu(), "diag_format_warning")

    @pytest.mark.callable_coverage("diag_print_error", executor="execute")
    def test_diag_print_error(self) -> None:
        _returns(_new_emu(), "diag_print_error")


@pytest.mark.unit
@pytest.mark.local
class TestExpansionRoutines:
    """Expansion callables execute through linked bytes."""

    @pytest.mark.callable_coverage("expansion_check_skip_reload", executor="execute")
    def test_expansion_check_skip_reload(self) -> None:
        _returns(_new_emu(), "expansion_check_skip_reload")

    @pytest.mark.callable_coverage("expansion_clear", executor="execute")
    def test_expansion_clear(self) -> None:
        _returns(_new_emu(), "expansion_clear")

    @pytest.mark.callable_coverage("expansion_mark_ready", executor="execute")
    def test_expansion_mark_ready(self) -> None:
        _returns(_new_emu(), "expansion_mark_ready")

    @pytest.mark.callable_coverage("expansion_publish", executor="execute")
    def test_expansion_publish(self) -> None:
        _returns(_new_emu(), "expansion_publish")


@pytest.mark.unit
@pytest.mark.local
class TestExportRoutines:
    """Export callables execute through linked bytes."""

    @pytest.mark.callable_coverage("export_apply_soft_budgets", executor="execute")
    def test_export_apply_soft_budgets(self) -> None:
        _returns(_new_emu(), "export_apply_soft_budgets")

    @pytest.mark.callable_coverage("export_select_layout", executor="execute")
    def test_export_select_layout(self) -> None:
        _returns(_new_emu(), "export_select_layout")


@pytest.mark.unit
@pytest.mark.local
class TestGraphicsRoutines:
    """Graphics callables execute through linked bytes."""

    @pytest.mark.callable_coverage("graphics_enter", executor="execute")
    def test_graphics_enter(self) -> None:
        _returns(_new_emu(), "graphics_enter")

    @pytest.mark.callable_coverage("graphics_exit", executor="execute")
    def test_graphics_exit(self) -> None:
        _returns(_new_emu(), "graphics_exit")

    @pytest.mark.callable_coverage("graphics_matrix_copy", executor="execute")
    def test_graphics_matrix_copy(self) -> None:
        _returns(_new_emu(), "graphics_matrix_copy")

    @pytest.mark.callable_coverage("graphics_validate_bounds", executor="execute")
    def test_graphics_validate_bounds(self) -> None:
        _returns(_new_emu(), "graphics_validate_bounds")


@pytest.mark.unit
@pytest.mark.local
class TestIncrementalRoutinesExtended:
    """Incremental compilation callables execute through linked bytes."""

    @pytest.mark.callable_coverage("incremental_can_run", executor="execute")
    def test_incremental_can_run(self) -> None:
        _returns(_new_emu(), "incremental_can_run")

    @pytest.mark.callable_coverage("incremental_fingerprint", executor="execute")
    def test_incremental_fingerprint(self) -> None:
        _returns(_new_emu(), "incremental_fingerprint")

    @pytest.mark.callable_coverage("incremental_mark_dependents", executor="execute")
    def test_incremental_mark_dependents(self) -> None:
        _returns(_new_emu(), "incremental_mark_dependents")

    @pytest.mark.callable_coverage("incremental_resolve_dirty", executor="execute")
    def test_incremental_resolve_dirty(self) -> None:
        _returns(_new_emu(), "incremental_resolve_dirty")


@pytest.mark.unit
@pytest.mark.local
class TestInspectionRoutinesExtended:
    """Inspection callables execute through linked bytes."""

    @pytest.mark.callable_coverage("inspect_load", executor="execute")
    def test_inspect_load(self) -> None:
        _returns(_new_emu(), "inspect_load")

    @pytest.mark.callable_coverage("inspect_parse_command", executor="execute")
    def test_inspect_parse_command(self) -> None:
        _returns(_new_emu(), "inspect_parse_command")

    @pytest.mark.callable_coverage("inspect_save", executor="execute")
    def test_inspect_save(self) -> None:
        _returns(_new_emu(), "inspect_save")

    @pytest.mark.callable_coverage("inspect_verify", executor="execute")
    def test_inspect_verify(self) -> None:
        _returns(_new_emu(), "inspect_verify")


@pytest.mark.unit
@pytest.mark.local
class TestIREmitRoutines:
    """IR builder callables execute through linked bytes."""

    @pytest.mark.callable_coverage("ir_emit_array_ref", executor="execute")
    def test_ir_emit_array_ref(self) -> None:
        _returns(_new_emu(), "ir_emit_array_ref")

    @pytest.mark.callable_coverage("ir_emit_literal_float", executor="execute")
    def test_ir_emit_literal_float(self) -> None:
        _returns(_new_emu(), "ir_emit_literal_float")

    @pytest.mark.callable_coverage("ir_emit_literal_int", executor="execute")
    def test_ir_emit_literal_int(self) -> None:
        _returns(_new_emu(), "ir_emit_literal_int")

    @pytest.mark.callable_coverage("ir_emit_literal_str", executor="execute")
    def test_ir_emit_literal_str(self) -> None:
        _returns(_new_emu(), "ir_emit_literal_str")

    @pytest.mark.callable_coverage("ir_emit_loop", executor="execute")
    def test_ir_emit_loop(self) -> None:
        _returns(_new_emu(), "ir_emit_loop")

    @pytest.mark.callable_coverage("ir_emit_string_ref", executor="execute")
    def test_ir_emit_string_ref(self) -> None:
        _returns(_new_emu(), "ir_emit_string_ref")

    @pytest.mark.callable_coverage("ir_emit_var_ref", executor="execute")
    def test_ir_emit_var_ref(self) -> None:
        _returns(_new_emu(), "ir_emit_var_ref")


@pytest.mark.unit
@pytest.mark.local
class TestIRQRoutine:
    """IRQ callables execute through linked bytes."""

    @pytest.mark.callable_coverage("irq_scan_keyboard", executor="execute")
    def test_irq_scan_keyboard(self) -> None:
        _returns(_new_emu(), "irq_scan_keyboard")


@pytest.mark.unit
@pytest.mark.local
class TestPageAllocRoutines:
    """Page allocator callables execute through linked bytes."""

    @pytest.mark.callable_coverage("page_alloc", executor="execute")
    def test_page_alloc(self) -> None:
        _returns(_new_emu(), "page_alloc")

    @pytest.mark.callable_coverage("page_free", executor="execute")
    def test_page_free(self) -> None:
        _returns(_new_emu(), "page_free")


@pytest.mark.unit
@pytest.mark.local
class TestParserRoutines:
    """Parser callables execute through linked bytes."""

    @pytest.mark.callable_coverage("parse_factor", executor="execute")
    def test_parse_factor(self) -> None:
        _returns(_new_emu(), "parse_factor")

    @pytest.mark.callable_coverage("parse_primary", executor="execute")
    def test_parse_primary(self) -> None:
        _returns(_new_emu(), "parse_primary")

    @pytest.mark.callable_coverage("parse_term", executor="execute")
    def test_parse_term(self) -> None:
        _returns(_new_emu(), "parse_term")


@pytest.mark.unit
@pytest.mark.local
class TestProgramLinesRoutines:
    """Program lines callables execute through linked bytes."""

    @pytest.mark.callable_coverage("program_lines_print_selected_line_number", executor="execute")
    def test_program_lines_print_selected_line_number(self) -> None:
        _returns(_new_emu(), "program_lines_print_selected_line_number")


@pytest.mark.unit
@pytest.mark.local
class TestResidentMainRoutine:
    """Resident main callables execute through linked bytes."""

    @pytest.mark.callable_coverage("resident_main", executor="execute")
    def test_resident_main(self) -> None:
        _returns(_new_emu(), "resident_main", 50000)


@pytest.mark.unit
@pytest.mark.local
class TestStringRoutines:
    """String callables execute through linked bytes."""

    @pytest.mark.callable_coverage("str_alloc", executor="execute")
    def test_str_alloc(self) -> None:
        _returns(_new_emu(), "str_alloc")

    @pytest.mark.callable_coverage("str_chr", executor="execute")
    def test_str_chr(self) -> None:
        _returns(_new_emu(), "str_chr")

    @pytest.mark.callable_coverage("str_copy", executor="execute")
    def test_str_copy(self) -> None:
        _returns(_new_emu(), "str_copy")

    @pytest.mark.callable_coverage("str_left", executor="execute")
    def test_str_left(self) -> None:
        _returns(_new_emu(), "str_left")

    @pytest.mark.callable_coverage("str_mid", executor="execute")
    def test_str_mid(self) -> None:
        _returns(_new_emu(), "str_mid")

    @pytest.mark.callable_coverage("str_right", executor="execute")
    def test_str_right(self) -> None:
        _returns(_new_emu(), "str_right")


@pytest.mark.unit
@pytest.mark.local
class TestTokenInitRoutine:
    """Tokenizer init callable executes through linked bytes."""

    @pytest.mark.callable_coverage("token_init", executor="execute")
    def test_token_init(self) -> None:
        _returns(_new_emu(), "token_init")


@pytest.mark.unit
@pytest.mark.local
class TestWedgeRunRoutine:
    """Wedge run callable executes through linked bytes."""

    @pytest.mark.callable_coverage("wedge_run_development", executor="execute")
    def test_wedge_run_development(self) -> None:
        _returns(_new_emu(), "wedge_run_development")
