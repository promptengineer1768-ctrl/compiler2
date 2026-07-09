"""Direct real-byte tests for arena-backed string descriptors."""

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

from numeric.c64float import from_float  # noqa: E402

try:
    from emu6502_c64_bindings import C64Emu6502
except ImportError:
    pass

MAX_CYCLES = 5_000_000
STRING_ARENA = 5
ARENA_GENERATION = 1
REQUEST = 0xC800
DESCRIPTORS = 0xC820
SD_SIZE = 12


def _artifact_root() -> Path:
    """Return the active linked-artifact directory."""
    debug_root = ROOT / "debug" / "runtime_slice"
    return debug_root if debug_root.exists() else ROOT / "build"


def _dll_path() -> Path:
    """Return the real 6502 emulator binding."""
    for candidate in (
        ROOT.parent / "tools" / "emu6502.dll",
        ROOT.parent / "tools" / "msys-emu6502.dll",
    ):
        if candidate.exists():
            return candidate
    pytest.skip("Emulator DLL not found in tools folder.")


def _symbol(name: str) -> int:
    """Resolve a production symbol from linked outputs."""
    labels = _artifact_root() / "compiler.lbl"
    if labels.exists():
        match = re.search(
            rf"^al\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(name)}$",
            labels.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return int(match.group(1), 16)
    directory = _artifact_root() / "routine_directory.json"
    if directory.exists():
        routine = (
            json.loads(directory.read_text(encoding="utf-8"))
            .get("routines", {})
            .get(name)
        )
        if routine and str(routine.get("address", "")).startswith("$"):
            return int(routine["address"][1:], 16)
    pytest.fail(f"Symbol {name!r} not found in linked outputs.")


def _zp(name: str) -> int:
    """Resolve a generated zero-page allocation."""
    data = json.loads((ROOT / "build" / "zp_allocation.json").read_text())
    address = data.get("allocation", {}).get(name, "")
    if str(address).startswith("$"):
        return int(address[1:], 16)
    pytest.fail(f"Zero-page symbol {name!r} not found.")


def _call(emu: C64Emu6502, routine: str, *, x: int = 0, y: int = 0) -> bool:
    """Execute linked production bytes and return carry (error) status."""
    emu.set_x(x)
    emu.set_y(y)
    emu.execute(_symbol(routine), MAX_CYCLES)
    return bool(int(emu.get_state().p) & 1)


def _new_emu() -> C64Emu6502:
    """Load production bytes and initialize all manifest arenas."""
    emu = C64Emu6502(lib_path=_dll_path())
    payload = (_artifact_root() / "compiler.bin").read_bytes()
    load_address = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_address, payload[2:])
    emu.set_georam_enabled(True)
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    assert not _call(emu, "arena_init_all")
    return emu


def _invoke(emu: C64Emu6502, routine: str, record: bytes) -> bool:
    """Invoke a typed request-record routine."""
    emu.write_mem_range(REQUEST, record)
    return _call(emu, routine, x=REQUEST & 0xFF, y=REQUEST >> 8)


def _alloc(emu: C64Emu6502, descriptor: int, length: int) -> bool:
    """Allocate one caller-owned SD through an SA request."""
    return _invoke(
        emu, "str_alloc", b"SA" + descriptor.to_bytes(2, "little") + bytes([length])
    )


def _sd(emu: C64Emu6502, address: int) -> bytes:
    """Read a complete caller-owned descriptor."""
    return bytes(emu.read_mem(address + index) for index in range(SD_SIZE))


def _payload(emu: C64Emu6502, descriptor: int) -> bytes:
    """Read an SD payload through its arena handle and geoRAM window."""
    sd = _sd(emu, descriptor)
    assert sd[:2] == b"SD"
    result = bytearray()
    for index in range(sd[3]):
        absolute = sd[8] + index
        page = int.from_bytes(sd[6:8], "little") + absolute // 256
        offset = absolute & 0xFF
        if index == 0 or offset == 0:
            emu.set_a(page & 0xFF)
            assert not _call(emu, "arena_select_page", x=sd[4], y=sd[5])
        result.append(emu.read_mem(0xDE00 + offset))
    return bytes(result)


def _chr(emu: C64Emu6502, descriptor: int, value: int) -> None:
    """Publish CHR$(value) into an SD."""
    assert not _invoke(
        emu, "str_chr", b"SH" + descriptor.to_bytes(2, "little") + bytes([value])
    )


def _copy(emu: C64Emu6502, destination: int, source: int) -> None:
    """Copy one SD into another using the SX ABI."""
    assert not _invoke(
        emu,
        "str_copy",
        b"SX" + destination.to_bytes(2, "little") + source.to_bytes(2, "little"),
    )


@pytest.mark.unit
@pytest.mark.local
class TestStrings:
    """String descriptors own arena pages and never expose transient pointers."""

    def test_three_live_allocations_zero_255_and_descriptor_shape(self) -> None:
        """Multiple values coexist; empty and maximum strings are representable."""
        emu = _new_emu()
        for index, length in enumerate((0, 1, 255)):
            address = DESCRIPTORS + index * SD_SIZE
            assert not _alloc(emu, address, length)
            sd = _sd(emu, address)
            assert sd[:6] == b"SD" + bytes([1, length, STRING_ARENA, ARENA_GENERATION])
            assert (int.from_bytes(sd[10:12], "little") != 0) is (length != 0)
            assert sd[9] == (0 if length == 0 else 1)
        assert (
            _sd(emu, DESCRIPTORS + SD_SIZE)[6:8]
            != _sd(emu, DESCRIPTORS + 2 * SD_SIZE)[6:8]
        )

    def test_capacity_free_reuse_stale_double_free_and_malformed(self) -> None:
        """The 64-page arena exhausts, reuses frees, and rejects invalid SDs."""
        emu = _new_emu()
        for index in range(64):
            assert not _alloc(emu, DESCRIPTORS + index * SD_SIZE, 1)
        overflow = DESCRIPTORS + 64 * SD_SIZE
        assert _alloc(emu, overflow, 1)

        victim = DESCRIPTORS + 17 * SD_SIZE
        stale = _sd(emu, victim)
        released_page = stale[6:8]
        assert not _call(emu, "str_free", x=victim & 0xFF, y=victim >> 8)
        assert _call(emu, "str_free", x=victim & 0xFF, y=victim >> 8)
        assert not _alloc(emu, overflow, 1)
        assert _sd(emu, overflow)[6:8] == released_page

        malformed = DESCRIPTORS + 63 * SD_SIZE
        emu.write_mem(malformed, ord("X"))
        assert _call(emu, "str_free", x=malformed & 0xFF, y=malformed >> 8)
        emu.write_mem_range(malformed, stale)
        assert _call(emu, "str_free", x=malformed & 0xFF, y=malformed >> 8)

    def test_copy_assign_and_concat_are_alias_safe_and_atomic(self) -> None:
        """Destination aliasing works and overflow preserves its old value."""
        emu = _new_emu()
        left, right, output = DESCRIPTORS, DESCRIPTORS + SD_SIZE, DESCRIPTORS + 24
        _chr(emu, left, ord("A"))
        _chr(emu, right, ord("B"))
        _copy(emu, output, left)
        assert _payload(emu, output) == b"A"
        assert not _invoke(
            emu,
            "str_assign",
            b"SX" + output.to_bytes(2, "little") + right.to_bytes(2, "little"),
        )
        assert _payload(emu, output) == b"B"
        assert not _invoke(
            emu,
            "str_concat",
            b"SC"
            + left.to_bytes(2, "little")
            + left.to_bytes(2, "little")
            + right.to_bytes(2, "little"),
        )
        assert _payload(emu, left) == b"AB"

        before = _sd(emu, output), _payload(emu, output)
        assert _alloc(emu, left, 200) is False
        assert _alloc(emu, right, 100) is False
        assert _invoke(
            emu,
            "str_concat",
            b"SC"
            + output.to_bytes(2, "little")
            + left.to_bytes(2, "little")
            + right.to_bytes(2, "little"),
        )
        assert (_sd(emu, output), _payload(emu, output)) == before

    def test_from_bytes_and_export_bytes_use_bounded_normal_memory(self) -> None:
        """SB imports normal bytes into an SD; SE exports only when capacity fits."""
        emu = _new_emu()
        source = 0xCB80
        output = 0xCB90
        descriptor = DESCRIPTORS
        emu.write_mem_range(source, b"HELLO")

        assert not _invoke(
            emu,
            "str_from_bytes",
            b"SB"
            + descriptor.to_bytes(2, "little")
            + source.to_bytes(2, "little")
            + bytes([5]),
        )
        assert _payload(emu, descriptor) == b"HELLO"

        assert _invoke(
            emu,
            "str_export_bytes",
            b"SE"
            + descriptor.to_bytes(2, "little")
            + output.to_bytes(2, "little")
            + bytes([4]),
        )
        assert not _invoke(
            emu,
            "str_export_bytes",
            b"SE"
            + descriptor.to_bytes(2, "little")
            + output.to_bytes(2, "little")
            + bytes([5]),
        )
        assert emu.get_state().a == 5
        assert bytes(emu.read_mem(output + index) for index in range(5)) == b"HELLO"

    @pytest.mark.parametrize(
        ("routine", "magic", "extra", "expected"),
        [
            ("str_left", b"SL", bytes([2]), b"AB"),
            ("str_right", b"SR", bytes([2]), b"CD"),
            ("str_mid", b"SM", bytes([2, 2]), b"BC"),
            ("str_left", b"SL", bytes([255]), b"ABCD"),
            ("str_mid", b"SM", bytes([5, 9]), b""),
        ],
    )
    def test_slice_edges_and_destination_aliasing(
        self, routine: str, magic: bytes, extra: bytes, expected: bytes
    ) -> None:
        """LEFT$, RIGHT$, and one-based MID$ clamp exactly at boundaries."""
        emu = _new_emu()
        source, temp = DESCRIPTORS, DESCRIPTORS + SD_SIZE
        for value in b"ABCD":
            _chr(emu, temp, value)
            if _sd(emu, source)[:2] != b"SD":
                _copy(emu, source, temp)
            else:
                assert not _invoke(
                    emu,
                    "str_concat",
                    b"SC"
                    + source.to_bytes(2, "little")
                    + source.to_bytes(2, "little")
                    + temp.to_bytes(2, "little"),
                )
        record = (
            magic + source.to_bytes(2, "little") + source.to_bytes(2, "little") + extra
        )
        assert not _invoke(emu, routine, record)
        assert _payload(emu, source) == expected

    def test_unsigned_petscii_compare_chr_len_and_asc(self) -> None:
        """Comparison is unsigned and scalar helpers consume valid SDs."""
        emu = _new_emu()
        left, right = DESCRIPTORS, DESCRIPTORS + SD_SIZE
        _chr(emu, left, 0xC1)
        _chr(emu, right, 0x41)
        assert not _invoke(
            emu,
            "str_cmp",
            b"SP" + left.to_bytes(2, "little") + right.to_bytes(2, "little"),
        )
        assert emu.get_state().a == 1
        assert not _call(emu, "str_len", x=left & 0xFF, y=left >> 8)
        assert emu.get_state().a == 1
        assert not _call(emu, "str_asc", x=left & 0xFF, y=left >> 8)
        assert emu.get_state().a == 0xC1
        assert not _alloc(emu, left, 0)
        assert _call(emu, "str_asc", x=left & 0xFF, y=left >> 8)

    @pytest.mark.parametrize(
        ("text", "value"),
        [(b"  -123X", -123.0), (b"+.5", 0.5), (b"1.25E2!", 125.0), (b"junk", 0.0)],
    )
    def test_val_stock_numeric_prefixes(self, text: bytes, value: float) -> None:
        """VAL accepts stock spaces, signs, decimals, exponents, and trailing junk."""
        emu = _new_emu()
        source, char, work = DESCRIPTORS, DESCRIPTORS + SD_SIZE, DESCRIPTORS + 24
        assert not _alloc(emu, source, 0)
        for byte in text:
            _chr(emu, char, byte)
            assert not _invoke(
                emu,
                "str_concat",
                b"SC"
                + work.to_bytes(2, "little")
                + source.to_bytes(2, "little")
                + char.to_bytes(2, "little"),
            )
            source, work = work, source
        assert not _call(emu, "str_val", x=source & 0xFF, y=source >> 8)
        fac = _zp("zp_fac1")
        assert (
            bytes(emu.read_mem(fac + index) for index in range(5))
            == from_float(value).to_bytes()
        )

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(9.0, b" 9"), (-123.0, b"-123"), (0.5, b" .5"), (3.5, b" 3.5")],
    )
    def test_str_uses_stock_basic_format(self, value: float, expected: bytes) -> None:
        """STR$ includes the stock leading sign space and decimal spelling."""
        emu = _new_emu()
        fac = _zp("zp_fac1")
        emu.write_mem_range(fac, from_float(value).to_bytes())
        assert not _invoke(emu, "str_str", b"ST" + DESCRIPTORS.to_bytes(2, "little"))
        assert _payload(emu, DESCRIPTORS) == expected
