"""Generate fingerprinted VICE Next snapshots and inject editor mailbox input."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Final

from vice_harness import MACHINES, VICE_ROOT, ViceMCP, running_vice

ROOT: Final = Path(__file__).resolve().parents[1]
MAILBOX_SYMBOLS: Final = (
    "editor_mailbox_buffer",
    "editor_mailbox_length",
    "editor_mailbox_pending",
    "editor_mailbox_submit_count",
    "editor_mailbox_error",
)


def _decode_text(result: object) -> dict[str, Any]:
    """Decode a JSON text result returned by the VICE Next bridge.

    Args:
        result: Raw MCP response.

    Returns:
        Decoded result dictionary.
    """
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list) and content:
            item = content[0]
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                decoded = json.loads(item["text"])
                if isinstance(decoded, dict):
                    return decoded
    raise TypeError(f"unexpected VICE response: {result!r}")


def mailbox_addresses(build_dir: Path) -> dict[str, int]:
    """Resolve all editor mailbox symbols from linked metadata.

    Args:
        build_dir: Compiler build directory.

    Returns:
        Symbol-to-address mapping.
    """
    directory = json.loads((build_dir / "routine_directory.json").read_text())
    addresses: dict[str, int] = {}
    for symbol in MAILBOX_SYMBOLS:
        raw = directory["routines"][symbol]["address"]
        if not isinstance(raw, str) or not raw.startswith("$"):
            raise ValueError(f"mailbox symbol has no linked address: {symbol}")
        addresses[symbol] = int(raw[1:], 16)
    return addresses


def inject_editor_mailbox(
    client: ViceMCP, addresses: dict[str, int], text: str
) -> None:
    """Atomically submit PETSCII-compatible text through the editor mailbox.

    Args:
        client: Connected VICE Next client.
        addresses: Linked mailbox addresses.
        text: ASCII command text without Return.
    """
    payload = text.encode("ascii")
    if len(payload) > 80:
        raise ValueError("editor mailbox input exceeds 80 bytes")
    client.call("vice.execution.pause")
    try:
        client.call(
            "vice.memory.write",
            {
                "address": f"${addresses['editor_mailbox_buffer']:04X}",
                "data": [*payload, 0],
            },
        )
        client.call(
            "vice.memory.write",
            {
                "address": f"${addresses['editor_mailbox_length']:04X}",
                "data": [len(payload)],
            },
        )
        client.call(
            "vice.memory.write",
            {
                "address": f"${addresses['editor_mailbox_pending']:04X}",
                "data": [1],
            },
        )
    finally:
        client.call("vice.execution.run")


def snapshot_fingerprint(
    compiler_path: Path,
    profile: str,
    addresses: dict[str, int],
    roms: dict[str, str],
) -> str:
    """Hash every input that makes a startup snapshot reusable.

    Args:
        compiler_path: Installed compiler image.
        profile: VICE machine profile.
        addresses: Mailbox ABI addresses.
        roms: ROM SHA-256 identities.

    Returns:
        SHA-256 snapshot fingerprint.
    """
    document = {
        "compiler_sha256": hashlib.sha256(compiler_path.read_bytes()).hexdigest(),
        "profile": profile,
        "mailbox": addresses,
        "roms": roms,
    }
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()


def create_snapshot(
    profile: str,
    build_dir: Path,
    *,
    port: int = 6510,
    autostart: bool = False,
) -> dict[str, Any]:
    """Create a named startup snapshot and its checked metadata contract.

    Args:
        profile: VICE profile key.
        build_dir: Compiler build directory.
        port: Isolated MCP port.
        autostart: Autostart compiler.d64 before capture.

    Returns:
        Snapshot metadata document.
    """
    machine = MACHINES[profile]
    addresses = mailbox_addresses(build_dir)
    compiler = build_dir / "compiler.d64"
    roms = {
        name: hashlib.sha256(
            (VICE_ROOT / machine.rom_directory / name).read_bytes()
        ).hexdigest()
        for name in machine.rom_files
    }
    fingerprint = snapshot_fingerprint(compiler, profile, addresses, roms)
    name = f"compiler2_{profile}_{fingerprint[:12]}"
    with running_vice(machine, port=port) as client:
        client.wait_for_ready_screen(machine, timeout=15.0, settle_reads=1)
        if autostart:
            client.autostart(compiler, run=True)
        ping = _decode_text(client.call("vice.ping"))
        saved = _decode_text(
            client.call(
                "vice.snapshot.save",
                {
                    "name": name,
                    "description": "Compiler 2 fingerprinted startup state",
                    "include_roms": False,
                    "include_disks": autostart,
                },
            )
        )
    return {
        "schema_version": 1,
        "name": name,
        "fingerprint": fingerprint,
        "profile": profile,
        "machine": machine.machine,
        "vice_version": ping.get("version", "unknown"),
        "rom_checksums": roms,
        "compiler_path": compiler.as_posix(),
        "mailbox": addresses,
        "autostarted": autostart,
        "snapshot": saved,
    }


def main() -> int:
    """Generate a snapshot metadata file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=sorted(MACHINES), default="basicv2")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--port", type=int, default=6510)
    parser.add_argument("--autostart", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "build" / "vice_snapshot.json"
    )
    args = parser.parse_args()
    document = create_snapshot(
        args.profile,
        args.build_dir.resolve(),
        port=args.port,
        autostart=args.autostart,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
