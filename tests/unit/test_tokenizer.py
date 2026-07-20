"""Unit tests for the geoasm tokenizer."""

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
    C64Emu6502 = None

TOKEN_EOF = 0x00
TOKEN_IDENTIFIER = 0x01
TOKEN_NUMBER = 0x02
TOKEN_STRING = 0x03
TOKEN_REM = 0x04
TOKEN_DATA = 0x05
TOKEN_SYMBOL = 0x06

KEYWORD_DATA = 0x83
KEYWORD_REM = 0x8F
KEYWORD_PRINT = 0x99

# Keep test input outside the linked $0801-$C7xx image.
SOURCE_ADDR = 0xC900
_ADDRESS_CACHE: dict[str, int] = {}


def _dll_path() -> Path:
    path = ROOT.parent / "tools" / "emu6502.dll"
    if not path.exists():
        path = ROOT.parent / "tools" / "msys-emu6502.dll"
    if not path.exists():
        pytest.skip("Emulator DLL not found in tools folder.")
    return path


def _symbol_address(symbol: str) -> int:
    if symbol in _ADDRESS_CACHE:
        return _ADDRESS_CACHE[symbol]
    lbl_text = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(rf"\bal\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}\b", lbl_text)
    if match is not None:
        _ADDRESS_CACHE[symbol] = int(match.group(1), 16)
        return _ADDRESS_CACHE[symbol]
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    raw = data["routines"].get(symbol, {}).get("address", "")
    if raw.startswith("$"):
        _ADDRESS_CACHE[symbol] = int(raw[1:], 16)
        return _ADDRESS_CACHE[symbol]
    map_text = (ROOT / "build" / "compiler.map").read_text(encoding="utf-8")
    match = re.search(rf"\b{re.escape(symbol)}\b\s+([0-9A-Fa-f]{{6}})", map_text)
    assert match is not None, f"Symbol {symbol!r} not found in compiler.map"
    _ADDRESS_CACHE[symbol] = int(match.group(1), 16)
    return _ADDRESS_CACHE[symbol]


def _load_binary(emu: C64Emu6502) -> None:
    payload = (ROOT / "build" / "compiler.bin").read_bytes()
    load_addr = payload[0] | (payload[1] << 8)
    emu.write_mem_range(load_addr, payload[2:])
    georam_path = ROOT / "build" / "georam.bin"
    if not georam_path.exists():
        pytest.fail("build/georam.bin not found. Run build.ps1 first.")
    image = georam_path.read_bytes()
    assert image[:2] == b"\x00\xde"
    if hasattr(emu, "set_georam_enabled"):
        emu.set_georam_enabled(True)
    backing_size = len(emu.export_georam())
    payload_bytes = image[2:]
    assert backing_size >= len(payload_bytes)
    emu.load_georam(payload_bytes + bytes(backing_size - len(payload_bytes)))


def _load_map_address(symbol: str) -> int:
    if symbol in _ADDRESS_CACHE:
        return _ADDRESS_CACHE[symbol]
    lbl_text = (ROOT / "build" / "compiler.lbl").read_text(encoding="utf-8")
    match = re.search(rf"\bal\s+([0-9A-Fa-f]{{6}})\s+\.{re.escape(symbol)}\b", lbl_text)
    if match is not None:
        _ADDRESS_CACHE[symbol] = int(match.group(1), 16)
        return _ADDRESS_CACHE[symbol]
    data = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    raw = data["routines"].get(symbol, {}).get("address", "")
    if raw.startswith("$"):
        _ADDRESS_CACHE[symbol] = int(raw[1:], 16)
        return _ADDRESS_CACHE[symbol]
    map_text = (ROOT / "build" / "compiler.map").read_text(encoding="utf-8")
    match = re.search(rf"\b{re.escape(symbol)}\b\s+([0-9A-Fa-f]{{6}})", map_text)
    assert match is not None, f"Symbol {symbol!r} not found in compiler.map"
    _ADDRESS_CACHE[symbol] = int(match.group(1), 16)
    return _ADDRESS_CACHE[symbol]


def _call_token_init(emu: C64Emu6502, source_addr: int) -> None:
    """Enter page-bound token_init through the group-0 XY gate."""
    directory = json.loads(
        (ROOT / "build" / "routine_directory.json").read_text(encoding="utf-8")
    )
    record = directory["routines"]["token_init"]
    assert record.get("layer") == "georam"
    routine_id = int(record["id"])
    assert routine_id < 0x100
    emu.set_a(routine_id & 0xFF)
    emu.set_x(source_addr & 0xFF)
    emu.set_y(source_addr >> 8)
    emu.execute(_symbol_address("georam_call_group_0_xy"), 10000)


def _new_emu(source: bytes) -> C64Emu6502:
    if C64Emu6502 is None:
        pytest.skip("Emulator binding unavailable")
    emu = C64Emu6502(lib_path=_dll_path())
    _load_binary(emu)
    emu.write_mem(0x0000, 0x2F)
    emu.write_mem(0x0001, 0x35)
    emu.execute(_symbol_address("ctx_init"), 50_000)
    emu.write_mem_range(SOURCE_ADDR, source + b"\x00")
    _call_token_init(emu, SOURCE_ADDR)
    return emu


def _token_state(emu: C64Emu6502) -> tuple[int, int, int]:
    return (
        emu.read_mem(_load_map_address("token_last_type")),
        emu.read_mem(_load_map_address("token_last_len")),
        emu.read_mem(_load_map_address("token_keyword_id")),
    )


def _state_address(symbol: str) -> int:
    """Return the linked address of tokenizer state."""
    return _load_map_address(symbol)


def _token_byte(command: dict[str, object]) -> int:
    """Return the primary token byte from token_val or token_bytes."""
    if "token_val" in command:
        token_value = command["token_val"]
        if isinstance(token_value, int):
            return token_value
    token_bytes = command.get("token_bytes")
    if isinstance(token_bytes, list) and token_bytes:
        token_value = token_bytes[0]
        if isinstance(token_value, int):
            return token_value
    raise KeyError(f"command {command.get('keyword')!r} lacks token_val/token_bytes")


def _commands() -> list[dict[str, object]]:
    """Return command manifest entries used by generated tokenizer tables."""
    data = json.loads((ROOT / "manifests" / "commands.json").read_text())
    return list(data["commands"])


def _abbreviation_minima() -> dict[str, int]:
    """Return manifest-derived shortest unambiguous abbreviation lengths."""
    keywords = [str(command["keyword"]).upper() for command in _commands()]
    minima: dict[str, int] = {}
    for keyword in keywords:
        for length in range(2, len(keyword) + 1):
            prefix = keyword[:length]
            if [other for other in keywords if other.startswith(prefix)] == [keyword]:
                minima[keyword] = length
                break
        else:
            minima[keyword] = len(keyword)
    return minima


def _abbreviate(keyword: str, length: int) -> bytes:
    """Return stock high-bit final-character abbreviation bytes."""
    raw = bytearray(keyword[:length].encode("ascii"))
    raw[-1] |= 0x80
    return bytes(raw)


def _set_scan_state(emu: C64Emu6502, *, cursor: int, start: int) -> None:
    """Prepare scan state for directly testing a public scanner routine."""
    emu.write_mem(_state_address("token_cursor"), cursor)
    emu.write_mem(_state_address("token_start"), start)


def _carry_is_set(emu: C64Emu6502) -> bool:
    return (int(emu.get_state().p) & 0x01) != 0


@pytest.mark.unit
@pytest.mark.local
class TestTokenizer:
    """Tokenizer behavior tests."""

    def test_next_peek_whitespace_numbers_strings_and_symbols(self) -> None:
        emu = _new_emu(b' 123 "HI" +')

        emu.execute(_symbol_address("token_peek"), 10000)
        assert emu.get_state().a == TOKEN_NUMBER
        assert _token_state(emu) == (TOKEN_NUMBER, 3, 0)

        emu.execute(_symbol_address("token_next"), 10000)
        assert emu.get_state().a == TOKEN_NUMBER
        assert _token_state(emu) == (TOKEN_NUMBER, 3, 0)

        emu.execute(_symbol_address("token_next"), 10000)
        assert emu.get_state().a == TOKEN_STRING
        assert _token_state(emu) == (TOKEN_STRING, 2, 0)

        emu.execute(_symbol_address("token_next"), 10000)
        assert emu.get_state().a == TOKEN_SYMBOL
        assert _token_state(emu) == (TOKEN_SYMBOL, 1, 0)

        emu.execute(_symbol_address("token_next"), 10000)
        assert emu.get_state().a == TOKEN_EOF

    @pytest.mark.parametrize(
        ("source", "length"),
        [
            (b"0,", 1),
            (b"12345 ", 5),
            (b"12.5E-2+", 7),
            (b".625:", 4),
        ],
    )
    def test_number_forms_use_real_scanner_bytes(
        self, source: bytes, length: int
    ) -> None:
        emu = _new_emu(source)
        emu.execute(_symbol_address("token_next"), 10000)
        assert not _carry_is_set(emu)
        assert _token_state(emu) == (TOKEN_NUMBER, length, 0)

    def test_unterminated_string_reports_token_error(self) -> None:
        emu = _new_emu(b'"OPEN')
        emu.execute(_symbol_address("token_next"), 10000)
        assert _carry_is_set(emu)
        assert _token_state(emu) == (0xFF, 4, 0)

    def test_identifiers_keywords_abbreviations_rem_and_data(self) -> None:
        emu = _new_emu(bytes([ord("P"), ord("R") | 0x80]) + b" A1 REM X: DATA 1,2")

        emu.execute(_symbol_address("token_next"), 10000)
        assert _token_state(emu) == (TOKEN_IDENTIFIER, 2, KEYWORD_PRINT)

        emu.execute(_symbol_address("token_next"), 10000)
        assert _token_state(emu) == (TOKEN_IDENTIFIER, 2, 0)

        emu.execute(_symbol_address("token_next"), 10000)
        assert _token_state(emu) == (TOKEN_REM, 15, KEYWORD_REM)

        emu = _new_emu(b"DATA 1,2")
        emu.execute(_symbol_address("token_next"), 10000)
        assert _token_state(emu) == (TOKEN_DATA, 8, KEYWORD_DATA)

        emu = _new_emu(b"DATA 1,2:+")
        emu.execute(_symbol_address("token_next"), 10000)
        assert _token_state(emu) == (TOKEN_DATA, 8, KEYWORD_DATA)
        emu.execute(_symbol_address("token_next"), 10000)
        assert _token_state(emu) == (TOKEN_SYMBOL, 1, 0)

    def test_dialect_filtering_for_plus4_keyword(self) -> None:
        emu = _new_emu(b"DO")
        emu.write_mem(_load_map_address("token_dialect"), 0)
        emu.execute(_symbol_address("token_next"), 10000)
        assert _carry_is_set(emu)
        assert emu.get_state().a == 0xFF

        emu = _new_emu(b"DO")
        emu.write_mem(_load_map_address("token_dialect"), 1)
        emu.execute(_symbol_address("token_next"), 10000)
        # DO is BASIC 3.5 token $EB (235) per MANUAL Appendix B / commands.json.
        assert _token_state(emu) == (TOKEN_IDENTIFIER, 2, 0xEB)

    @pytest.mark.parametrize(
        "command",
        _commands(),
        ids=lambda command: str(command["keyword"]),
    )
    def test_generated_keyword_trie_covers_command_manifest(
        self, command: dict[str, object]
    ) -> None:
        keyword = str(command["keyword"])
        token_val = _token_byte(command)
        dialect = 1 if command["dialect"] == "BASIC35" else 0

        emu = _new_emu(keyword.encode("ascii"))
        emu.write_mem(_load_map_address("token_dialect"), dialect)
        emu.execute(_symbol_address("token_next"), 10000)

        assert not _carry_is_set(emu)
        expected_type = (
            TOKEN_REM
            if keyword == "REM"
            else TOKEN_DATA if keyword == "DATA" else TOKEN_IDENTIFIER
        )
        # TAB(/SPC( include the paren in the keyword spelling; token length
        # is the full spelling length when the source matches exactly.
        assert _token_state(emu) == (expected_type, len(keyword), token_val)

    @pytest.mark.parametrize(
        "command",
        [entry for entry in _commands() if len(str(entry["keyword"])) >= 2],
        ids=lambda command: f"{command['keyword']}-abbr",
    )
    def test_generated_keyword_trie_accepts_stock_abbreviations(
        self, command: dict[str, object]
    ) -> None:
        keyword = str(command["keyword"])
        token_val = _token_byte(command)
        dialect = 1 if command["dialect"] == "BASIC35" else 0
        abbrev_len = _abbreviation_minima()[keyword.upper()]
        source = _abbreviate(keyword, abbrev_len)

        emu = _new_emu(source)
        emu.write_mem(_load_map_address("token_dialect"), dialect)
        emu.execute(_symbol_address("token_next"), 10000)

        assert not _carry_is_set(emu)
        expected_type = (
            TOKEN_REM
            if keyword == "REM"
            else TOKEN_DATA if keyword == "DATA" else TOKEN_IDENTIFIER
        )
        assert _token_state(emu) == (expected_type, abbrev_len, token_val)

    def test_keyword_lookup_report_proves_generated_bounds(self) -> None:
        report = json.loads((ROOT / "build" / "keyword_lookup_report.json").read_text())

        assert report["keywords"] == [entry["keyword"] for entry in _commands()]
        assert report["total_keywords"] == len(_commands())
        assert report["trie_depth"] == max(len(str(c["keyword"])) for c in _commands())
        assert report["max_fan_out"] >= 1
        assert report["worst_observed_transitions"] >= 1
        assert report["total_trie_bytes"] > len(_commands())

    def test_public_scanners_have_direct_real_byte_coverage(self) -> None:
        emu = _new_emu(b" \tX")
        emu.execute(_symbol_address("token_skip_whitespace"), 10000)
        assert emu.read_mem(_state_address("token_cursor")) == 2

        emu = _new_emu(b"abc9% ")
        emu.execute(_symbol_address("token_identifier"), 10000)
        assert _token_state(emu) == (TOKEN_IDENTIFIER, 5, 0)

        emu = _new_emu(b"42.25 ")
        emu.execute(_symbol_address("token_number"), 10000)
        assert _token_state(emu) == (TOKEN_NUMBER, 5, 0)

        emu = _new_emu(b'"OK"')
        emu.execute(_symbol_address("token_string"), 10000)
        assert _token_state(emu) == (TOKEN_STRING, 2, 0)

        emu = _new_emu(b"REM verbatim")
        _set_scan_state(emu, cursor=3, start=0)
        emu.execute(_symbol_address("token_rem"), 10000)
        assert _token_state(emu) == (TOKEN_REM, 12, KEYWORD_REM)

        emu = _new_emu(b"DATA 1:PRINT")
        _set_scan_state(emu, cursor=4, start=0)
        emu.execute(_symbol_address("token_data"), 10000)
        assert _token_state(emu) == (TOKEN_DATA, 6, KEYWORD_DATA)
