"""RED system contracts for production expansion-native execution paths."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import xip_path_audit  # noqa: E402


@pytest.mark.system
def test_expansion_xip_policy_entries_have_generated_georam_records() -> None:
    """A conforming XIP classification requires a real generated page entry."""
    errors = xip_path_audit.missing_xip_directory_entries(
        ROOT / "manifests" / "placement_policy.json",
        ROOT / "build" / "routine_directory.json",
    )
    assert errors == []


@pytest.mark.system
def test_georam_xip_entries_have_abi_compatible_reu_dual_records() -> None:
    """Every geoRAM page placement must have a planned dual REU record (RREU-5.17)."""
    errors = xip_path_audit.missing_reu_dual_records(
        ROOT / "manifests" / "placement_policy.json",
        ROOT / "build" / "routine_directory.json",
        ROOT / "build" / "reu_layout.json",
    )
    assert errors == []


@pytest.mark.system
def test_production_never_directly_calls_an_expansion_xip_mirror() -> None:
    """Resident and overlay callers must enter XIP through the dispatcher/gate."""
    violations = xip_path_audit.direct_xip_calls(
        ROOT / "src", ROOT / "manifests" / "placement_policy.json"
    )
    assert violations == []


def test_audit_reports_direct_mirror_call_and_missing_page(tmp_path: Path) -> None:
    """The auditor rejects a direct symbol call and a missing conforming page."""
    policy = {
        "routines": [
            {
                "name": "compile_line",
                "target_placement": "expansion_xip",
                "conformance": "conforming",
                "xip_page": 24,
            }
        ]
    }
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    source = tmp_path / "src"
    source.mkdir()
    (source / "caller.asm").write_text("jsr compile_line\n", encoding="utf-8")
    directory_path = tmp_path / "directory.json"
    directory_path.write_text(json.dumps({"routines": {}}), encoding="utf-8")

    assert xip_path_audit.direct_xip_calls(source, policy_path) == [
        f"{source / 'caller.asm'}:1: direct jsr to expansion_xip routine compile_line"
    ]
    assert xip_path_audit.missing_xip_directory_entries(
        policy_path, directory_path
    ) == ["compile_line: conforming expansion_xip routine lacks geoRAM entry"]


def test_audit_accepts_dispatch_without_direct_xip_symbol(tmp_path: Path) -> None:
    """A caller may invoke a resident gate while the target stays indirect."""
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "routines": [
                    {
                        "name": "compile_line",
                        "target_placement": "expansion_xip",
                        "conformance": "conforming",
                        "xip_page": 24,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    source = tmp_path / "src"
    source.mkdir()
    (source / "caller.asm").write_text(
        "ldx #$42\njsr georam_call_group_1\n", encoding="utf-8"
    )
    directory_path = tmp_path / "directory.json"
    directory_path.write_text(
        json.dumps(
            {
                "routines": {
                    "compile_line": {
                        "id": 42,
                        "layer": "georam",
                        "block": 0,
                        "page": 1,
                        "offset": 0,
                        "address": "$DE00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    import generate_expansion_contracts as expansion_contracts

    reu_layout_path = tmp_path / "reu_layout.json"
    reu_layout_path.write_text(
        json.dumps(
            {
                "routine_records": [
                    expansion_contracts.dual_routine_record(
                        routine_id=42,
                        routine_name="compile_line",
                        block=0,
                        page=1,
                        entry_offset=0,
                        window_address="$DE00",
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    assert xip_path_audit.direct_xip_calls(source, policy_path) == []
    assert (
        xip_path_audit.missing_xip_directory_entries(policy_path, directory_path) == []
    )
    assert (
        xip_path_audit.missing_reu_dual_records(
            policy_path, directory_path, reu_layout_path
        )
        == []
    )


def test_audit_reports_missing_reu_dual_record(tmp_path: Path) -> None:
    """A geoRAM page without a dual REU record is a placement contract failure."""
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "routines": [
                    {
                        "name": "compile_line",
                        "target_placement": "expansion_xip",
                        "conformance": "conforming",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    directory_path = tmp_path / "directory.json"
    directory_path.write_text(
        json.dumps(
            {
                "routines": {
                    "compile_line": {
                        "id": 42,
                        "layer": "georam",
                        "block": 0,
                        "page": 1,
                        "offset": 0,
                        "address": "$DE00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    reu_layout_path = tmp_path / "reu_layout.json"
    reu_layout_path.write_text(json.dumps({"routine_records": []}), encoding="utf-8")

    assert xip_path_audit.missing_reu_dual_records(
        policy_path, directory_path, reu_layout_path
    ) == ["compile_line: missing or mismatched ABI-compatible REU dual record"]


def test_wedge_parse_xip_pilot_is_page_bound_and_gate_only() -> None:
    """wedge_parse must execute from its generated page, never a RAM mirror."""
    source = (ROOT / "src" / "geoasm" / "dos_wedge.asm").read_text(encoding="utf-8")
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record = directory["routines"]["wedge_parse"]

    assert '.segment "GEORAM_PAGE_40"' in source
    assert ".assert * - wedge_parse <= $FA" in source
    assert record == {
        "id": 369,
        "layer": "georam",
        "logical_layer": "geoasm",
        "block": 0,
        "page": 40,
        "offset": 0,
        "address": "$DE00",
    }
    production = [
        path for path in (ROOT / "src").rglob("*.asm") if path.name != "dos_wedge.asm"
    ]
    direct_call = re.compile(r"^\s*jsr\s+wedge_parse\s*(?:;.*)?$", re.MULTILINE)
    assert all(
        direct_call.search(path.read_text(encoding="utf-8")) is None
        for path in production
    )
    assert "jsr georam_call_group_n" in source


def test_program_classify_file_is_a_page_bound_xip_entry() -> None:
    """The cold codec classifier has no resident entry-point mirror."""
    source_path = ROOT / "src" / "geoasm" / "program_codec.asm"
    source = source_path.read_text(encoding="utf-8")
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record = directory["routines"]["program_classify_file"]

    assert '.segment "GEORAM_PAGE_6"' in source
    assert ".assert * - program_classify_file <= $FA" in source
    assert record == {
        "id": 335,
        "layer": "georam",
        "logical_layer": "geoasm",
        "block": 0,
        "page": 6,
        "offset": 0,
        "address": "$DE00",
    }

    code_prefix = source.split('.segment "GEORAM_PAGE_6"', maxsplit=1)[0]
    assert "program_classify_file:" not in code_prefix
    direct_call = re.compile(
        r"^\s*jsr\s+program_classify_file\s*(?:;.*)?$", re.MULTILINE
    )
    assert all(
        direct_call.search(path.read_text(encoding="utf-8")) is None
        for path in (ROOT / "src").rglob("*.asm")
    )


def test_export_parse_command_is_a_page_bound_gate_called_xip_entry() -> None:
    """COMPILE's CP canonicalizer executes only from its assigned XIP page."""
    source_path = ROOT / "src" / "geoasm" / "compile_export.asm"
    source = source_path.read_text(encoding="utf-8")
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record = directory["routines"]["export_parse_command"]

    assert record == {
        "id": 364,
        "layer": "georam",
        "logical_layer": "geoasm",
        "block": 0,
        "page": 35,
        "offset": 0,
        "address": "$DE00",
    }
    page_start = source.index('.segment "GEORAM_PAGE_35"')
    next_segment = re.search(r'^\.segment\s+"', source[page_start + 1 :], re.MULTILINE)
    assert next_segment is not None
    page_end = page_start + 1 + next_segment.start()
    page_source = source[page_start:page_end]
    assert "export_parse_command:" in page_source
    assert "export_validate_device" in page_source
    assert ".assert * - export_parse_command <= $FA" in page_source
    assert "jsr georam_call_group_n_xy" in source
    direct_call = re.compile(
        r"^\s*(?:jsr|jmp)\s+export_parse_command\s*(?:;.*)?$", re.MULTILINE
    )
    assert all(
        direct_call.search(path.read_text(encoding="utf-8")) is None
        for path in (ROOT / "src").rglob("*.asm")
    )


def test_extended_codec_operations_execute_from_bound_xip_pages() -> None:
    """C2P1 decode, encode, and selection keep real bodies in XIP pages."""
    source = (ROOT / "src" / "geoasm" / "program_codec.asm").read_text(encoding="utf-8")
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    expected = {
        "program_decode_extended": (11, "__program_stream_decode_extended"),
        "program_encode_extended": (12, "__program_stream_encode_extended"),
        "program_select_save_format": (13, "__program_stream_select_save_format"),
    }
    for name, (page, body) in expected.items():
        record = directory["routines"][name]
        assert record["page"] == page
        assert record["offset"] == 0
        assert record["address"] == "$DE00"
        start = source.index(f'.segment "GEORAM_PAGE_{page}"')
        end = source.find('.segment "', start + 1)
        assert f"{name}:" in source[start:end]
        assert f"{body}:" in source[start:end]

    runtime = (ROOT / "src" / "runtime" / "runtime_io.asm").read_text(encoding="utf-8")
    assert "jsr georam_call_group_n_xy" in runtime
    for name in expected:
        assert re.search(rf"^\s*jsr\s+{name}\s*$", runtime, re.MULTILINE) is None


def test_stock_codec_entry_and_page_sensitive_passes_are_bound_to_xip() -> None:
    """V2 codec dispatch enters real page-7/page-8 work, not RAM mirrors."""
    source = (ROOT / "src" / "geoasm" / "program_codec.asm").read_text(encoding="utf-8")
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    expected = {
        "program_decode_stock": (7, "__program_stream_validate_stock"),
        "program_encode_stock": (8, "__program_stream_canonicalize_stock"),
    }
    for name, (page, body) in expected.items():
        record = directory["routines"][name]
        assert record["page"] == page
        assert record["offset"] == 0
        start = source.index(f'.segment "GEORAM_PAGE_{page}"')
        end = source.find('.segment "', start + 1)
        page_source = source[start:end]
        assert f"{name}:" in page_source
        assert f"{body}" in page_source
        assert f".assert * - {name} <= $FA" in source


def test_editor_cold_operations_are_page_bound_and_gate_only() -> None:
    """READY and line deletion execute from their generated geoRAM pages."""
    source = (ROOT / "src" / "geoasm" / "editor_svc.asm").read_text(encoding="utf-8")
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    expected = {
        "editor_delete_line": (2, "GEORAM_PAGE_2"),
        "editor_ready_transition": (5, "GEORAM_PAGE_5"),
    }
    for name, (page, segment) in expected.items():
        record = directory["routines"][name]
        assert record["page"] == page
        assert record["offset"] == 0
        assert record["address"] == "$DE00"
        assert f'.segment "{segment}"' in source
        assert f".assert * - {name} <= $FA" in source
        direct_call = re.compile(rf"^\\s*jsr\\s+{name}\\s*(?:;.*)?$", re.MULTILINE)
        assert all(
            direct_call.search(path.read_text(encoding="utf-8")) is None
            for path in (ROOT / "src").rglob("*.asm")
        )

    for runtime_source in ("errors.asm", "control.asm"):
        text = (ROOT / "src" / "runtime" / runtime_source).read_text(encoding="utf-8")
        assert "jsr georam_call_group_n" in text


def test_program_lines_list_formatter_is_a_gate_called_xip_page() -> None:
    """LIST's decimal formatter has one page-bound XIP implementation."""
    source = (ROOT / "src" / "geoasm" / "program_lines.asm").read_text(encoding="utf-8")
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record = directory["routines"]["program_lines_print_selected_line_number"]
    assert record["page"] == 42
    assert record["offset"] == 0
    assert '.segment "GEORAM_PAGE_42"' in source
    assert ".assert * - program_lines_print_selected_line_number <= $FA" in source
    assert "ldx #<GEORAM_ROUTINE_ID_PROGRAM_LINES_PRINT_SELECTED_LINE_NUMBER" in source
    assert "jsr georam_call_group_n" in source


def test_graphics_bounds_validator_is_a_page_bound_xip_entry() -> None:
    """Graphics descriptor validation has only the page-45 XIP body."""
    source = (ROOT / "src" / "geoasm" / "graphics.asm").read_text(encoding="utf-8")
    directory = json.loads((ROOT / "build" / "routine_directory.json").read_text())
    record = directory["routines"]["graphics_validate_bounds"]
    assert record["layer"] == "georam"
    assert record["page"] == 45
    assert record["offset"] == 0
    page_start = source.index('.segment "GEORAM_PAGE_45"')
    page_end = source.index('.segment "GRAPHICS"', page_start)
    page = source[page_start:page_end]
    assert "graphics_validate_bounds:" in page
    assert "graphics_validate_set_canonical:" in page
    assert ".assert * - graphics_validate_bounds <= $FA" in page


def test_numbered_program_lines_use_transaction_gates() -> None:
    """The editor never invokes transactional XIP store entries as RAM calls."""
    source = (ROOT / "src" / "geoasm" / "program_lines.asm").read_text(encoding="utf-8")
    for routine, gate, register in (
        ("program_replace_from_load", "georam_call_group_n_xy", "lda"),
        ("program_tx_begin", "georam_call_group_n", "ldx"),
        ("program_tx_put_line", "georam_call_group_n_xy", "lda"),
        ("program_tx_delete_line", "georam_call_group_n_xy", "lda"),
        ("program_tx_commit", "georam_call_group_n_xy", "lda"),
        ("program_tx_abort", "georam_call_group_n_xy", "lda"),
        ("pipeline_compile_line", "georam_call_group_n_xy", "lda"),
    ):
        identifier = f"GEORAM_ROUTINE_ID_{routine.upper()}"
        assert identifier in source
        assert re.search(rf"{register} #<{identifier}\s+jsr {gate}", source), routine
        direct_call = re.compile(rf"^\s*(?:jsr|jmp)\s+{routine}\s*$", re.MULTILINE)
        assert direct_call.search(source) is None


def test_group_one_gate_opens_io_and_restores_each_context_port() -> None:
    """XIP callers may execute with $DE00 hidden by their RAM mapping."""
    source = (ROOT / "src" / "resident" / "georam_gate.asm").read_text(
        encoding="utf-8"
    )
    assert "georam_xip_port_stack" in source
    assert "georam_xip_open_io:" in source
    assert "ora #$07" in source
    assert "georam_xip_prepare_close:" in source
    assert "georam_xip_finish_close:" in source

    for entry in ("georam_call_group_n:", "georam_call_group_n_xy:"):
        start = source.index(entry)
        next_entry = source.find("\ngeoram_call_", start + len(entry))
        body = source[start : None if next_entry == -1 else next_entry]
        assert "jsr georam_xip_open_io" in body
        assert "jsr georam_xip_prepare_close" in body
        assert "jsr georam_xip_finish_close" in body


def test_program_transaction_pages_restore_code_mapping_after_data_access() -> None:
    """Transaction XIP bodies cannot resume from a program-data page."""
    source = (ROOT / "src" / "geoasm" / "program_store.asm").read_text(
        encoding="utf-8"
    )
    for page, routine in (
        (14, "program_tx_begin"),
        (15, "program_tx_put_line"),
        (16, "program_tx_delete_line"),
        (17, "program_tx_commit"),
        (18, "program_tx_abort"),
    ):
        assert f'.segment "GEORAM_PAGE_{page}"' in source
        assert f"{routine}:" in source

    # The only program-store primitives that select a geoRAM data page must
    # restore the active gate page before their RTS paths.  This is the
    # counterpart to program_codec's stream helper contract.
    for helper in (
        "program_store_read_src",
        "program_store_write_dst",
        "program_store_probe_src",
    ):
        start = source.index(f".proc {helper}")
        end = source.index(".endproc", start)
        assert "jsr georam_restore_xip_code" in source[start:end]


def test_compiler_dispatch_paths_enter_nested_xip_routines_through_the_gate() -> None:
    """Direct RUN/immediate input never jumps from one XIP page to another."""
    callers = {
        ROOT
        / "src"
        / "resident"
        / "resident_main.asm": (
            "pipeline_compile_line",
            "direct_execute_command",
        ),
        ROOT
        / "src"
        / "geoasm"
        / "direct_dispatch.asm": (
            "pipeline_compile_line",
            "pipeline_compile_program",
        ),
    }
    for path, routines in callers.items():
        source = path.read_text(encoding="utf-8")
        assert "jsr georam_call_group_n_xy" in source
        for routine in routines:
            identifier = f"GEORAM_ROUTINE_ID_{routine.upper()}"
            assert identifier in source
            assert re.search(
                rf"lda #<{identifier}\s+jsr georam_call_group_n_xy", source
            ), f"{path.name}: {routine}"
            assert (
                re.search(rf"^\s*(?:jsr|jmp)\s+{routine}\s*$", source, re.MULTILINE)
                is None
            )


def test_editor_xip_pages_enter_pipeline_and_list_helpers_through_the_gate() -> None:
    """Editor page 1/page 4 cannot call their XIP peer mirrors directly."""
    source = (ROOT / "src" / "geoasm" / "editor_svc.asm").read_text(encoding="utf-8")
    assert source.count("jsr georam_call_group_n_xy") >= 2
    for routine in ("pipeline_compile_line", "editor_detokenize_line"):
        identifier = f"GEORAM_ROUTINE_ID_{routine.upper()}"
        assert identifier in source
        assert re.search(
            rf"lda #<{identifier}\s+jsr georam_call_group_n_xy", source
        ), routine
        assert (
            re.search(rf"^\s*(?:jsr|jmp)\s+{routine}\s*$", source, re.MULTILINE) is None
        )
