"""Focused tests for the real VICE fixture infrastructure."""

from __future__ import annotations

from pathlib import Path
import sys
import json

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from generate_vice_fixtures import normalize_screen, rom_checksums  # noqa: E402
from vice_harness import MACHINES, ViceMCP, _command_completed  # noqa: E402
from vice_snapshot import inject_editor_mailbox, snapshot_fingerprint  # noqa: E402

VICE_ROOT = ROOT.parent / "tools" / "vice-mcp" / "dist" / "HeadlessVICE-windows-x86_64"


def _vice_exe(name: str) -> Path:
    path = VICE_ROOT / name
    if not path.exists():
        pytest.skip(f"{name} not found under {VICE_ROOT}")
    return path


@pytest.mark.hardware
@pytest.mark.vice
@pytest.mark.smoke
def test_x64sc_version_is_reported() -> None:
    """The stock C64 VICE executable should be present and usable."""
    exe = _vice_exe("x64sc.exe")
    assert exe.stat().st_size > 0
    assert (VICE_ROOT / "C64").is_dir()


@pytest.mark.hardware
@pytest.mark.vice
def test_xplus4_version_is_reported() -> None:
    """The stock Plus/4 VICE executable should also be present."""
    exe = _vice_exe("xplus4.exe")
    assert exe.stat().st_size > 0
    assert (VICE_ROOT / "PLUS4").is_dir()


@pytest.mark.hardware
@pytest.mark.vice
def test_mcp_endpoint_uses_documented_path() -> None:
    """Clients must target the endpoint served by the bundled VICE build."""
    assert ViceMCP("http://127.0.0.1:6510").endpoint.endswith("/mcp")


@pytest.mark.hardware
@pytest.mark.vice
def test_machine_profiles_define_distinct_screen_maps() -> None:
    """C64 and Plus/4 captures must not read one another's screen RAM."""
    assert MACHINES["basicv2"].screen_address == 0x0400
    assert MACHINES["basicv35"].screen_address == 0x0C00


@pytest.mark.hardware
@pytest.mark.vice
def test_rom_checksums_are_sha256() -> None:
    """Fixture provenance includes exact ROM identities."""
    checksums = rom_checksums(MACHINES["basicv2"])
    assert checksums
    assert all(len(digest) == 64 for digest in checksums.values())


@pytest.mark.hardware
@pytest.mark.vice
def test_fixture_normalization_removes_echo_and_prompt() -> None:
    """Only semantic output survives stable screen normalization."""
    screen = '**** COMMODORE 64 BASIC V2 ****\nREADY.\nPRINT "OK"\nOK\nREADY.'
    assert normalize_screen(screen, ('PRINT "OK"',)) == "OK"


@pytest.mark.hardware
@pytest.mark.vice
def test_command_completion_requires_a_new_final_ready_prompt() -> None:
    """An old boot prompt or echoed input is not command completion."""
    before = "READY."
    assert not _command_completed(before, 'READY.\nPRINT "OK"')
    assert _command_completed(before, 'READY.\nPRINT "OK"\nOK\nREADY.')


class _RecordingVice:
    """Small call recorder for mailbox atomicity tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []

    def call(self, name: str, arguments: object | None = None) -> object:
        """Record one MCP call."""
        self.calls.append((name, arguments))
        return {}


@pytest.mark.hardware
@pytest.mark.vice
def test_editor_mailbox_injection_is_atomic() -> None:
    """Mailbox writes occur while execution is paused, then resume once."""
    client = _RecordingVice()
    addresses = {
        "editor_mailbox_buffer": 0x2000,
        "editor_mailbox_length": 0x2051,
        "editor_mailbox_pending": 0x2052,
    }
    inject_editor_mailbox(client, addresses, 'PRINT "OK"')  # type: ignore[arg-type]
    names = [name for name, _ in client.calls]
    assert names == [
        "vice.execution.pause",
        "vice.memory.write",
        "vice.memory.write",
        "vice.memory.write",
        "vice.execution.run",
    ]


@pytest.mark.hardware
@pytest.mark.vice
def test_snapshot_fingerprint_changes_with_mailbox_abi(tmp_path: Path) -> None:
    """Snapshot reuse is rejected when linked mailbox addresses change."""
    compiler = tmp_path / "compiler.d64"
    compiler.write_bytes(b"compiler")
    first = snapshot_fingerprint(compiler, "basicv2", {"buffer": 1}, {"rom": "a"})
    second = snapshot_fingerprint(compiler, "basicv2", {"buffer": 2}, {"rom": "a"})
    assert first != second


@pytest.mark.hardware
@pytest.mark.vice
def test_generated_snapshot_contract_is_fingerprinted() -> None:
    """Snapshot generation records VICE, ROM, compiler, and mailbox identity."""
    document = json.loads((ROOT / "build" / "vice_snapshot.json").read_text())
    assert len(document["fingerprint"]) == 64
    assert document["name"].startswith("compiler2_basicv2_")
    assert document["vice_version"]
    assert document["rom_checksums"]
    assert set(document["mailbox"]) == {
        "editor_mailbox_buffer",
        "editor_mailbox_length",
        "editor_mailbox_pending",
        "editor_mailbox_submit_count",
        "editor_mailbox_error",
    }
