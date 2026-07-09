"""Unit tests for runtime I/O helpers (io.asm)."""

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
    setattr(emu, "_compiler2_real_bytes_only", True)
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x30)


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


def _carry_is_clear(emu: C64Emu6502) -> bool:
    return (int(emu.get_state().p) & 0x01) == 0


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
        kernal_input = _load_map_address("kernal_input_byte")
        current_channel = _load_map_address("io_current_channel")
        emu.write_mem(kernal_input, ord("Q"))
        emu.execute(_load_symbol_address("io_get"), 10000)
        assert emu.get_state().a == ord("Q")
        assert _carry_is_clear(emu), hex(int(emu.get_state().a))

        emu.execute_rts(_load_symbol_address("arena_init_all"), 100_000)
        descriptor, cell, request = 0xCC00, 0xCC20, 0xCC40
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

        cmd_request = 0xCC60
        emu.write_mem_range(cmd_request, b"IC\x02")
        emu.set_x(cmd_request & 0xFF)
        emu.set_y(cmd_request >> 8)
        emu.execute(_load_symbol_address("io_cmd"), 10000)
        assert emu.read_mem(current_channel) == 2
        assert _carry_is_clear(emu)

        string_descriptor, string_cell, string_request = 0xCC80, 0xCCA0, 0xCCC0
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
        kernal_input = _load_map_address("kernal_input_byte")

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

        emu.write_mem(request + 7, 1)
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)
        emu.execute(_load_symbol_address("rio_verify"), 10000)
        assert _carry_is_clear(emu)

        # RS: magic, name pointer, length, device, secondary, start, end.
        emu.write_mem_range(
            request,
            b"RS" + name.to_bytes(2, "little") + b"\x04\x08\x01\x00\x20\x00\x21",
        )
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)
        emu.execute(_load_symbol_address("rio_save"), 10000)
        assert _carry_is_clear(emu)

        # RO: magic, logical file, device, secondary, length, name pointer.
        emu.write_mem_range(request, b"RO\x02\x08\x02\x04" + name.to_bytes(2, "little"))
        emu.set_x(request & 0xFF)
        emu.set_y(request >> 8)
        emu.execute(_load_symbol_address("rio_open"), 10000)
        assert _carry_is_clear(emu)

        close_request = 0xC180
        emu.write_mem_range(close_request, b"RC\x02")
        emu.set_x(close_request & 0xFF)
        emu.set_y(close_request >> 8)
        emu.execute(_load_symbol_address("rio_close"), 10000)
        assert _carry_is_clear(emu)

        write_request = 0xC190
        emu.write_mem_range(write_request, b"RW\x02" + bytes([ord("Z")]))
        emu.set_x(write_request & 0xFF)
        emu.set_y(write_request >> 8)
        emu.execute(_load_symbol_address("rio_chrout"), 10000)
        assert _carry_is_clear(emu)

        emu.write_mem(kernal_input, ord("Q"))
        read_request = 0xC1A0
        emu.write_mem_range(read_request, b"RI\x02")
        emu.set_x(read_request & 0xFF)
        emu.set_y(read_request >> 8)
        emu.execute(_load_symbol_address("rio_chrin"), 10000)
        assert emu.get_state().a == ord("Q")

        emu.execute(_load_symbol_address("rio_clrchn"), 10000)
        assert _carry_is_clear(emu)

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
