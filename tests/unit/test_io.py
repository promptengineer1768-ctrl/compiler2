"""Unit tests for runtime I/O helpers (io.asm)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from tests.kernal_stubs import (
    KERNAL_CHRIN,
    KERNAL_CHROUT,
    KERNAL_CLRCHN,
    KERNAL_STUB_INPUT,
    KERNAL_STUB_OUTPUT,
    install_kernal_stubs,
    install_vector_stub,
)

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT.parent / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from numeric.c64float import from_float  # noqa: E402

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    pass


def _artifact_root() -> Path:
    """Use the canonical freshly linked production artifact."""
    return ROOT / "build"


def _dll_path() -> Path:
    for candidate in (
        ROOT.parent / "tools" / "emu6502.dll",
        ROOT.parent / "tools" / "msys-emu6502.dll",
    ):
        if candidate.exists():
            return candidate
    pytest.skip("Emulator DLL not found in tools folder.")


def _load_binary(emu: C64Emu6502) -> None:
    payload = (_artifact_root() / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    emu.set_georam_enabled(True)
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    # Variable stores and other runtime helpers live in the RAM_HIGH image.
    hibasic = _artifact_root() / "hibasic.bin"
    if hibasic.exists():
        emu.write_mem_range(0xE000, hibasic.read_bytes())
    install_kernal_stubs(emu)


def _load_symbol_address(symbol_name: str) -> int:
    labels_path = _artifact_root() / "compiler.lbl"
    if labels_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    directory_path = _artifact_root() / "routine_directory.json"
    if directory_path.exists():
        data = json.loads(directory_path.read_text(encoding="utf-8"))
        routine = data.get("routines", {}).get(symbol_name)
        if routine:
            addr = routine.get("address", "")
            if addr.startswith("$"):
                return int(addr[1:], 16)
    map_path = _artifact_root() / "compiler.map"
    match = re.search(
        rf"\b{re.escape(symbol_name)}\b\s+([0-9A-Fa-f]{{6}})",
        map_path.read_text(encoding="utf-8"),
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Symbol '{symbol_name}' not found.")


def _load_map_address(symbol_name: str) -> int:
    labels_path = _artifact_root() / "compiler.lbl"
    if labels_path.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol_name)}$",
            labels_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    directory_path = _artifact_root() / "routine_directory.json"
    if directory_path.exists():
        data = json.loads(directory_path.read_text(encoding="utf-8"))
        routine = data.get("routines", {}).get(symbol_name)
        if routine:
            addr = routine.get("address", "")
            if addr.startswith("$"):
                return int(addr[1:], 16)
    map_path = _artifact_root() / "compiler.map"
    match = re.search(
        rf"\b{re.escape(symbol_name)}\b\s+([0-9A-Fa-f]{{6}})",
        map_path.read_text(encoding="utf-8"),
    )
    if match:
        return int(match.group(1), 16)
    pytest.fail(f"Label '{symbol_name}' not found.")


def _load_zp_address(symbol_name: str) -> int:
    """Return a generated zero-page symbol address from the current artifact."""
    symbols_path = _artifact_root() / "zp_symbols.inc"
    if symbols_path.exists():
        match = re.search(
            rf"^{re.escape(symbol_name)}\s*=\s*\$([0-9A-Fa-f]+)$",
            symbols_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    allocation_path = _artifact_root() / "zp_allocation.json"
    if allocation_path.exists():
        data = json.loads(allocation_path.read_text(encoding="utf-8"))
        address = data.get("allocation", {}).get(symbol_name, "")
        if address.startswith("$"):
            return int(address[1:], 16)
    pytest.fail(f"Zero-page symbol '{symbol_name}' not found.")


def _carry_is_clear(emu: C64Emu6502) -> bool:
    return (int(emu.get_state().p) & 0x01) == 0


def _routine_record(symbol_name: str) -> dict[str, object]:
    directory_path = _artifact_root() / "routine_directory.json"
    data: dict[str, object] = json.loads(directory_path.read_text(encoding="utf-8"))
    routines = data["routines"]
    assert isinstance(routines, dict)
    record = routines[symbol_name]
    assert isinstance(record, dict)
    return record


def _routine_layer(symbol_name: str) -> str:
    record = _routine_record(symbol_name)
    layer = record.get("layer", "")
    assert isinstance(layer, str)
    return layer


def _load_georam_backing(emu: C64Emu6502) -> None:
    """Load build/georam.bin into the emulator's geoRAM backing.

    geoRAM-paged overlays (layer=georam) live in this image and must be
    banked into the $DE00 window before execution.
    """
    georam_path = _artifact_root() / "georam.bin"
    if not georam_path.exists():
        pytest.fail("build/georam.bin not found. Run build.ps1 first.")
    image = georam_path.read_bytes()
    assert image[:2] == b"\x00\xde"
    emu.set_georam_enabled(True)
    backing_size = len(emu.export_georam())
    payload_bytes = image[2:]
    assert backing_size >= len(payload_bytes)
    emu.load_georam(payload_bytes + bytes(backing_size - len(payload_bytes)))


@pytest.mark.unit
@pytest.mark.local
class TestIo:
    """Runtime console I/O tests."""

    def test_print_helpers_update_output_buffer(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        out_len = _load_map_address("io_output_len")
        out_buf = _load_map_address("io_output_buf")
        emu.write_mem(out_len, 0x00)

        fac = 0x02
        emu.write_mem(fac, 42)
        emu.set_a(1)  # TYPE_INT1
        emu.execute(_load_symbol_address("io_print_value"), 10000)
        assert emu.read_mem_range(out_buf, out_buf + 3) == b" 42 "
        assert emu.read_mem(out_len) == 4
        emu.write_mem(out_len, 0x00)

        for name, expected in (
            ("io_print_newline", 0x0D),
            ("io_print_space", 0x20),
        ):
            emu.execute(_load_symbol_address(name), 10000)
            assert emu.read_mem(out_buf) == expected
            assert emu.read_mem(out_len) == 1
            emu.write_mem(out_len, 0x00)

        emu.execute(_load_symbol_address("io_print_comma"), 10000)
        assert emu.read_mem(out_len) == 10
        assert emu.read_mem_range(out_buf, out_buf + 9) == b" " * 10
        emu.write_mem(out_len, 0)

        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        out_len = _load_map_address("io_output_len")
        out_buf = _load_map_address("io_output_buf")
        emu.write_mem(out_len, 0)
        emu.set_a(3)
        emu.execute_rts(_load_symbol_address("io_print_tab"), 10000)
        assert emu.read_mem(out_len) == 3
        assert emu.read_mem_range(out_buf, out_buf + 2) == b"   "

        emu.execute(_load_symbol_address("io_print_semicolon"), 10000)
        assert emu.get_state().a is not None

    @pytest.mark.parametrize(
        ("value_type", "raw", "expected"),
        [
            (1, b"\x80", b"-128 "),
            (2, b"\xff\x7f", b" 32767 "),
            (2, b"\x00\x80", b"-32768 "),
            (3, b"\xff\xff", b" 65535 "),
        ],
        ids=["int1-negative", "int2-positive", "int2-min", "int3-unsigned"],
    )
    def test_print_formats_each_integer_tier(
        self, value_type: int, raw: bytes, expected: bytes
    ) -> None:
        """PRINT preserves signed tiers and formats INT3 as unsigned."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        out_len = _load_map_address("io_output_len")
        out_buf = _load_map_address("io_output_buf")
        emu.write_mem(out_len, 0)
        emu.write_mem_range(0x02, raw)
        emu.set_a(value_type)
        emu.execute(_load_symbol_address("io_print_value"), 10000)
        assert _carry_is_clear(emu), hex(int(emu.get_state().a))
        actual_len = emu.read_mem(out_len)
        assert actual_len == len(expected), emu.read_mem_range(
            out_buf, out_buf + actual_len - 1
        )
        assert emu.read_mem_range(out_buf, out_buf + len(expected) - 1) == expected

    def test_print_formats_packed_float_through_string_runtime(self) -> None:
        """FLOAT PRINT uses the canonical packed formatter and string arena."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.execute_rts(_load_symbol_address("arena_init_all"), 100_000)
        out_len = _load_map_address("io_output_len")
        out_buf = _load_map_address("io_output_buf")
        emu.write_mem(out_len, 0)
        emu.write_mem_range(0x02, from_float(3.5).to_bytes())
        emu.set_a(0)
        emu.execute_rts(_load_symbol_address("io_print_value"), 1_000_000)
        expected = b" 3.5 "
        assert _carry_is_clear(emu)
        actual_len = emu.read_mem(out_len)
        assert actual_len == len(expected), emu.read_mem_range(
            out_buf, out_buf + actual_len - 1
        )
        assert emu.read_mem_range(out_buf, out_buf + len(expected) - 1) == expected

    def test_input_get_and_cmd_helpers(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)
        kernal_input = KERNAL_STUB_INPUT
        current_channel = _load_map_address("io_current_channel")
        emu.write_mem(kernal_input, ord("Q"))
        emu.execute(_load_symbol_address("io_get"), 10000)
        assert emu.get_state().a == ord("Q")
        assert _carry_is_clear(emu), hex(int(emu.get_state().a))

        emu.execute_rts(_load_symbol_address("arena_init_all"), 100_000)
        # Test records must not overlap the linked image, which may occupy all
        # normal program RAM through $CFFF.  This path calls the variable and
        # string helpers located in that upper region.
        descriptor, cell, request = 0x0500, 0x0520, 0x0540
        emu.write_mem_range(
            descriptor,
            b"VD\x01\x01\x00\x00" + cell.to_bytes(2, "little") + bytes(4),
        )
        emu.write_mem_range(
            request,
            b"IN" + descriptor.to_bytes(2, "little") + bytes(6),
        )
        emu.write_mem(kernal_input, ord("7"))
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)
        emu.execute(_load_symbol_address("io_input_value"), 10000)
        assert _carry_is_clear(emu), hex(int(emu.get_state().a))
        assert emu.read_mem(cell) == 7
        assert emu.read_mem(cell + 1) == 0

        cmd_request = 0x0560
        emu.write_mem_range(cmd_request, b"IC\x02")
        emu.set_x(cmd_request & 0xFF)
        emu.set_y(cmd_request >> 8)
        emu.execute(_load_symbol_address("io_cmd"), 10000)
        assert emu.read_mem(current_channel) == 2
        assert _carry_is_clear(emu)

        string_descriptor, string_cell, string_request = 0x0580, 0x05A0, 0x05C0
        emu.write_mem_range(
            string_descriptor,
            b"VD\x03\x01\x00\x00" + string_cell.to_bytes(2, "little") + bytes(4),
        )
        emu.write_mem_range(
            string_request,
            b"IN" + string_descriptor.to_bytes(2, "little") + bytes(6),
        )
        emu.write_mem(kernal_input, ord("R"))
        emu.set_x(string_request & 0xFF)
        emu.set_y(string_request >> 8)
        emu.execute(_load_symbol_address("io_input_string"), 10000)
        assert _carry_is_clear(emu)
        assert emu.read_mem_range(string_cell, string_cell + 1) == b"SD"
        assert emu.read_mem(string_cell + 3) == 1

    def test_input_rejects_removed_raw_character_abi(self) -> None:
        """INPUT entries require an IN request and destination descriptor."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        request = 0xC500
        emu.write_mem_range(request, bytes(10))
        for routine in ("io_input_value", "io_input_string"):
            emu.set_x(request & 0xFF)
            emu.set_y(request >> 8)
            emu.execute(_load_symbol_address(routine), 10000)
            assert emu.get_state().p & 1

    def test_runtime_io_wrappers_drive_kernal_bridge_state(self) -> None:
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        _load_binary(emu)

        # Stock KERNAL workspace from the authoritative c64rom ZP report.
        kernal_input = KERNAL_STUB_INPUT
        kernal_output = _load_map_address("kernal_output_byte")
        zp_eal = _load_zp_address("zp_eal")
        zp_fa = _load_zp_address("zp_fa")
        zp_fnadr = _load_zp_address("zp_fnadr")
        zp_fnlen = _load_zp_address("zp_fnlen")
        zp_la = _load_zp_address("zp_la")
        zp_sa = _load_zp_address("zp_sa")
        zp_status = _load_zp_address("zp_status")
        emu.write_mem(0x0001, 0x35)

        name = 0xC000
        emu.write_mem_range(name, b"TEST")
        request = 0xC100
        # RL: magic, name pointer, length, device, secondary, mode, address, reserved.
        emu.write_mem_range(
            request,
            b"RL" + name.to_bytes(2, "little") + b"\x04\x08\x01\x00\x01\x08\x00\x00",
        )
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)
        emu.execute(_load_symbol_address("rio_load"), 10000)
        assert _carry_is_clear(emu), hex(int(emu.get_state().a))
        assert emu.read_mem(0x0001) == 0x35
        assert emu.read_mem(zp_fnlen) == 4
        assert emu.read_mem_range(zp_fnadr, zp_fnadr + 1) == name.to_bytes(2, "little")
        assert (emu.read_mem(zp_la), emu.read_mem(zp_fa), emu.read_mem(zp_sa)) == (
            1,
            8,
            1,
        )
        assert emu.read_mem_range(zp_eal, zp_eal + 1) == b"\x01\x08"
        assert emu.read_mem(zp_status) == 0

        # Language SAVE/VERIFY require a published program; covered separately
        # in test_rio_save_and_verify_use_token_class_emission.

        # RO: magic, logical file, device, secondary, length, name pointer.
        emu.write_mem_range(request, b"RO\x02\x08\x02\x04" + name.to_bytes(2, "little"))
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)
        emu.execute(_load_symbol_address("rio_open"), 10000)
        assert _carry_is_clear(emu)
        assert emu.read_mem(0x0001) == 0x35
        assert (emu.read_mem(zp_la), emu.read_mem(zp_fa), emu.read_mem(zp_sa)) == (
            2,
            8,
            2,
        )
        assert emu.read_mem(zp_status) == 0

        close_request = 0xC180
        emu.write_mem_range(close_request, b"RC\x02")
        emu.set_x(close_request & 0xFF)
        emu.set_y(close_request >> 8)
        emu.execute(_load_symbol_address("rio_close"), 10000)
        assert _carry_is_clear(emu)
        assert emu.read_mem(0x0001) == 0x35
        assert emu.read_mem(zp_status) == 0

        write_request = 0xC190
        emu.write_mem_range(write_request, b"RW\x02" + bytes([ord("Z")]))
        emu.set_x(write_request & 0xFF)
        emu.set_y(write_request >> 8)
        emu.execute(_load_symbol_address("rio_chrout"), 10000)
        assert _carry_is_clear(emu)
        assert emu.read_mem(kernal_output) == ord("Z")
        assert emu.read_mem(zp_status) == 0

        emu.write_mem(kernal_input, ord("Q"))
        read_request = 0xC1A0
        emu.write_mem_range(read_request, b"RI\x02")
        emu.set_x(read_request & 0xFF)
        emu.set_y(read_request >> 8)
        emu.execute(_load_symbol_address("rio_chrin"), 10000)
        assert emu.get_state().a == ord("Q")
        assert emu.read_mem(kernal_input) == 0
        assert emu.read_mem(zp_status) == 0

        emu.execute(_load_symbol_address("rio_clrchn"), 10000)
        assert _carry_is_clear(emu)
        assert emu.read_mem(0x0001) == 0x35
        assert emu.read_mem(zp_status) == 0

    @pytest.mark.parametrize("routine", ["rio_chrin", "rio_chrout"])
    def test_channel_wrappers_preserve_primary_error_and_restore_channel(
        self, routine: str
    ) -> None:
        """Channel cleanup must not hide the failed KERNAL operation."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.write_mem(0x0001, 0x35)
        marker = KERNAL_STUB_OUTPUT

        # Return a deterministic KERNAL error from the data operation.
        failing_body = bytes((0xA9, 0x05, 0x38, 0x60))
        if routine == "rio_chrin":
            install_vector_stub(emu, KERNAL_CHRIN, 0xED00, failing_body)
            request = 0xC2A0
            emu.write_mem_range(request, b"RI\x02")
        else:
            install_vector_stub(emu, KERNAL_CHROUT, 0xED00, failing_body)
            request = 0xC2B0
            emu.write_mem_range(request, b"RW\x02Z")

        # CLRCHN records that cleanup ran and succeeds.
        cleanup_body = bytes(
            (
                0xA9,
                0x01,
                0x8D,
                marker & 0xFF,
                marker >> 8,
                0x18,
                0x60,
            )
        )
        install_vector_stub(emu, KERNAL_CLRCHN, 0xED20, cleanup_body)
        emu.write_mem(marker, 0)
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)

        emu.execute(_load_symbol_address(routine), 10000)

        assert emu.get_state().p & 1
        assert emu.get_state().a == 0x05
        assert emu.read_mem(marker) == 1
        assert emu.read_mem(0x0001) == 0x35

    def test_rio_save_and_verify_use_token_class_emission(self) -> None:
        """SAVE emits format bytes for the published program; VERIFY matches them."""
        dll = _dll_path()
        emu = C64Emu6502(lib_path=dll)
        # Match codec/store unit tests: enable geoRAM without real-bytes-only port force.
        payload = (_artifact_root() / "compiler.bin").read_bytes()
        load_addr = payload[0] | (payload[1] << 8)
        emu.write_mem_range(load_addr, payload[2:])
        # program_replace_from_load is a geoRAM-paged overlay; its bytes live in
        # build/georam.bin and must be banked into the $DE00 window.
        _load_georam_backing(emu)

        def call(routine: str, *, a: int = 0, x: int = 0, y: int = 0) -> bool:
            emu.set_a(a)
            emu.set_x(x)
            emu.set_y(y)
            if _routine_layer(routine) == "georam":
                record = _routine_record(routine)
                routine_id_obj = record["id"]
                assert isinstance(routine_id_obj, int)
                routine_id = routine_id_obj
                if routine_id < 0x100:
                    emu.set_a(routine_id & 0xFF)
                    emu.execute(_load_symbol_address("georam_call_group_0_xy"), 2_000_000)
                else:
                    emu.set_a(routine_id & 0xFF)
                    emu.execute(_load_symbol_address("georam_call_group_n_xy"), 2_000_000)
            else:
                emu.execute(_load_symbol_address(routine), 2_000_000)
            return bool(int(emu.get_state().p) & 1)

        assert not call("arena_init_all")

        # Normalized logical program: 10 PRINT 1  (body $99 '1' $00)
        logical = (
            (5).to_bytes(2, "little")
            + (10).to_bytes(2, "little")
            + bytes([0x99, ord("1"), 0x00])
            + b"\x00\x00"
        )
        expected_prg = (
            b"\x01\x08"
            + bytes([0x08, 0x08, 0x0A, 0x00, 0x99, ord("1"), 0x00])
            + b"\x00\x00"
        )
        scratch_arena = 8
        staging = 0xC200
        emu.write_mem_range(
            staging,
            b"PS"
            + len(logical).to_bytes(2, "little")
            + bytes([scratch_arena, 1, 0, 0]),
        )
        for index, value in enumerate(logical):
            page, offset = divmod(index, 256)
            if offset == 0:
                assert not call("arena_select_page", a=page, x=scratch_arena, y=1)
            emu.write_mem(0xDE00 + offset, value)

        assert not call(
            "program_replace_from_load", x=staging & 0xFF, y=staging >> 8
        ), hex(int(emu.get_state().a))

        name = 0xC000
        emu.write_mem_range(name, b"TEST")
        workspace = 0xC300
        workspace_end = workspace + 64
        request = 0xC100
        # RS workspace receives the emitted format bytes before KERNAL SAVE.
        emu.write_mem_range(
            request,
            b"RS"
            + name.to_bytes(2, "little")
            + b"\x04\x08\x01"
            + workspace.to_bytes(2, "little")
            + workspace_end.to_bytes(2, "little"),
        )
        assert not call("rio_save", x=request & 0xFF, y=request >> 8), hex(
            int(emu.get_state().a)
        )
        assert (
            bytes(emu.read_mem(workspace + i) for i in range(len(expected_prg)))
            == expected_prg
        )

        # VERIFY: pure byte equality against the same emission.
        emu.write_mem_range(workspace, expected_prg)
        emu.write_mem_range(
            request,
            b"RL"
            + name.to_bytes(2, "little")
            + b"\x04\x08\x01\x01"
            + workspace.to_bytes(2, "little")
            + b"\x00\x00",
        )
        assert not call("rio_verify", x=request & 0xFF, y=request >> 8), hex(
            int(emu.get_state().a)
        )

        # Mismatch must report VERIFY error.
        emu.write_mem(workspace + 4, emu.read_mem(workspace + 4) ^ 0xFF)
        assert call("rio_verify", x=request & 0xFF, y=request >> 8)
        assert emu.get_state().a == 0x1C  # ERR_VERIFY

    @pytest.mark.parametrize(
        "routine", ["rio_load", "rio_save", "rio_verify", "rio_open"]
    )
    def test_runtime_io_rejects_untyped_requests(self, routine: str) -> None:
        """File wrappers reject the removed pointer/no-op ABI."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        request = 0xC200
        emu.write_mem_range(request, bytes(16))
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)
        emu.execute(_load_symbol_address(routine), 10000)
        assert emu.get_state().p & 1

    @pytest.mark.parametrize(
        ("value_type", "raw", "expected", "ok"),
        [
            (1, b"\x7f", 127, True),
            (1, b"\xff", 0x0E, False),
            (2, b"\xff\x00", 255, True),
            (2, b"\x00\x01", 0x0E, False),
            (3, b"\x80\x00", 128, True),
            (3, b"\x00\x01", 0x0E, False),
            (0, from_float(255.0).to_bytes(), 255, True),
            (0, from_float(256.0).to_bytes(), 0x0E, False),
            (0, from_float(-1.0).to_bytes(), 0x0E, False),
            (0, from_float(1.5).to_bytes(), 0x0E, False),
        ],
        ids=[
            "int1-max",
            "int1-negative",
            "int2-255",
            "int2-256",
            "int3-128",
            "int3-256",
            "float-255",
            "float-256",
            "float-negative",
            "float-fractional",
        ],
    )
    def test_argument_byte_coercion_is_unsigned_and_range_checked(
        self, value_type: int, raw: bytes, expected: int, ok: bool
    ) -> None:
        """Argument byte is a special unsigned storage domain, not INT1."""
        emu = C64Emu6502(lib_path=_dll_path())
        _load_binary(emu)
        emu.write_mem_range(0x02, raw)
        emu.set_a(value_type)
        emu.execute(_load_symbol_address("math_to_arg_byte"), 10000)
        assert _carry_is_clear(emu) is ok
        assert emu.get_state().a == expected
