"""Shared client and process harness for stock VICE reference observations."""

from __future__ import annotations

import base64
import json
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT: Final = Path(__file__).resolve().parents[1]
VICE_ROOT: Final = (
    ROOT.parent / "tools" / "vice-mcp" / "dist" / "HeadlessVICE-windows-x86_64"
)


@dataclass(frozen=True)
class ViceMachine:
    """Static configuration needed to observe one stock VICE machine."""

    profile: str
    machine: str
    executable: str
    screen_address: int
    columns: int
    rows: int
    rom_directory: str
    rom_files: tuple[str, ...]


MACHINES: Final = {
    "basicv2": ViceMachine(
        "basicv2",
        "C64",
        "x64sc.exe",
        0x0400,
        40,
        25,
        "C64",
        (
            "basic-901226-01.bin",
            "kernal-901227-03.bin",
            "chargen-901225-01.bin",
        ),
    ),
    "basicv35": ViceMachine(
        "basicv35",
        "PLUS4",
        "xplus4.exe",
        0x0C00,
        40,
        25,
        "PLUS4",
        (
            "basic-318006-01.bin",
            "kernal-318004-05.bin",
            "3plus1-317053-01.bin",
            "3plus1-317054-01.bin",
        ),
    ),
}


class ViceMCPError(RuntimeError):
    """Raised when a VICE MCP request fails."""


class ViceMCP:
    """Small JSON-RPC client for the HTTP MCP endpoint embedded in VICE."""

    def __init__(self, endpoint: str) -> None:
        """Initialize the client with an endpoint including the ``/mcp`` path."""
        self.endpoint = endpoint.rstrip("/") + "/mcp"

    def call(
        self,
        name: str,
        arguments: dict[str, object] | None = None,
        *,
        timeout: float = 10.0,
        retries: int = 2,
    ) -> object:
        """Invoke one VICE MCP tool, retrying transient transport failures."""
        payload = {
            "jsonrpc": "2.0",
            "id": time.time_ns(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                with urlopen(request, timeout=timeout) as response:
                    decoded = json.loads(response.read())
                break
            except (OSError, TimeoutError, URLError) as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(0.15)
        else:
            raise ViceMCPError(f"VICE MCP call failed: {name}") from last_error
        if "error" in decoded:
            raise ViceMCPError(f"VICE MCP error for {name}: {decoded['error']}")
        return decoded.get("result", {})

    def memory_read(self, address: int, length: int) -> bytes:
        """Read bytes through the machine's current CPU-visible memory map."""
        result = self.call(
            "vice.memory.read",
            {"address": f"0x{address:04X}", "size": length},
        )
        return _extract_bytes(result)

    def memory_write(self, address: int, data: bytes) -> None:
        """Write bytes through the machine's current CPU-visible memory map."""
        self.call(
            "vice.memory.write",
            {"address": f"0x{address:04X}", "data": list(data)},
        )

    def type_text(self, text: str) -> None:
        """Submit text through VICE's keyboard path."""
        for char in text:
            self.call("vice.keyboard.type", {"text": char})
            time.sleep(0.12)
            if char in "\r\n":
                time.sleep(1.0)

    def press_key(
        self,
        key: str,
        *,
        hold_frames: int | None = None,
        hold_ms: int | None = None,
    ) -> None:
        """Press one key through VICE's keyboard matrix."""
        arguments: dict[str, object] = {"key": key}
        if hold_frames is not None:
            arguments["hold_frames"] = hold_frames
        if hold_ms is not None:
            arguments["hold_ms"] = hold_ms
        self.call("vice.keyboard.key_press", arguments)

    def autostart(self, path: Path, *, run: bool = True) -> None:
        """Load a PRG or disk image through VICE autostart."""
        self.call("vice.autostart", {"path": str(path), "run": run}, timeout=20.0)

    def submit_command(
        self,
        machine: ViceMachine,
        command: str,
        *,
        timeout: float = 20.0,
    ) -> str:
        """Type one command and wait for the machine to return to READY."""
        before = self.screen_text(machine)
        self.type_text(command.rstrip("\r\n") + "\n")
        self.call("vice.execution.run", timeout=1.0)
        # Keyboard events need a few frames before MCP memory polling resumes.
        time.sleep(0.5)
        deadline = time.monotonic() + timeout
        last_screen = before
        while time.monotonic() < deadline:
            try:
                last_screen = self.screen_text(machine)
            except ViceMCPError:
                time.sleep(0.15)
                continue
            if _command_completed(before, last_screen):
                return last_screen
            time.sleep(0.15)
        raise TimeoutError(
            f"VICE did not return to READY after {command!r}\n{last_screen}"
        )

    def screen_text(self, machine: ViceMachine) -> str:
        """Decode the current text screen into stable ASCII rows."""
        data = self.memory_read(machine.screen_address, machine.columns * machine.rows)
        lines = []
        for row in range(machine.rows):
            start = row * machine.columns
            raw = data[start : start + machine.columns]
            lines.append(
                "".join(_screen_code_to_ascii(value) for value in raw).rstrip()
            )
        return "\n".join(lines).rstrip()

    def wait_for_ready_screen(
        self,
        machine: ViceMachine,
        *,
        timeout: float = 30.0,
        settle_reads: int = 3,
    ) -> str:
        """Wait until the screen has returned to a stable READY prompt."""
        deadline = time.monotonic() + timeout
        last_screen = ""
        stable_reads = 0
        while time.monotonic() < deadline:
            try:
                screen = self.screen_text(machine)
            except ViceMCPError:
                time.sleep(0.15)
                continue
            lines = [
                line.strip().upper() for line in screen.splitlines() if line.strip()
            ]
            ready = bool(lines) and lines[-1] == "READY."
            if ready:
                stable_reads = stable_reads + 1 if screen == last_screen else 1
                if stable_reads >= settle_reads:
                    return screen
            else:
                stable_reads = 0
            last_screen = screen
            time.sleep(0.25)
        raise TimeoutError(f"VICE did not reach a stable READY prompt\n{last_screen}")


@contextmanager
def running_vice(
    machine: ViceMachine,
    *,
    port: int = 6510,
    startup_timeout: float = 15.0,
    extra_args: tuple[str, ...] = (),
) -> Iterator[ViceMCP]:
    """Start an isolated VICE process and yield its connected MCP client."""
    executable = VICE_ROOT / machine.executable
    if not executable.is_file():
        raise FileNotFoundError(executable)
    debug = ROOT / "debug"
    debug.mkdir(exist_ok=True)
    stdout_path = debug / f"{machine.profile}_vice_stdout.log"
    stderr_path = debug / f"{machine.profile}_vice_stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout:
        with stderr_path.open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(
                [
                    str(executable),
                    "-default",
                    "-mcpserver",
                    "-mcpserverport",
                    str(port),
                    "-warp",
                    "-sounddev",
                    "dummy",
                    *extra_args,
                ],
                cwd=VICE_ROOT,
                stdout=stdout,
                stderr=stderr,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            client = ViceMCP(f"http://127.0.0.1:{port}")
            deadline = time.monotonic() + startup_timeout
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(
                        f"{machine.executable} exited with {process.returncode}; "
                        f"see {stderr_path}"
                    )
                try:
                    client.call("vice.ping", timeout=1.0)
                    client.call("vice.execution.run", timeout=1.0)
                    break
                except ViceMCPError:
                    time.sleep(0.1)
            else:
                process.terminate()
                process.wait(timeout=5)
                raise TimeoutError(f"VICE MCP did not start; see {stderr_path}")
            try:
                yield client
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def _extract_bytes(result: object) -> bytes:
    """Extract bytes from the MCP protocol's nested content representation."""
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list) and content:
            item = content[0]
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                return _extract_bytes(json.loads(item["text"]))
        for key in ("data", "bytes", "memory"):
            value = result.get(key)
            if isinstance(value, list):
                return bytes(
                    int(item, 16) if isinstance(item, str) else item for item in value
                )
            if isinstance(value, str):
                try:
                    return bytes.fromhex(value)
                except ValueError:
                    return base64.b64decode(value)
    raise TypeError(f"Unexpected VICE memory response: {result!r}")


def _screen_code_to_ascii(value: int) -> str:
    """Convert the stable printable subset of Commodore screen codes."""
    if value in (0x20, 0xA0):
        return " "
    if 1 <= value <= 26:
        return chr(64 + value)
    if 0x30 <= value <= 0x39:
        return chr(value)
    if 0x41 <= value <= 0x5A:
        return chr(value)
    if 0x61 <= value <= 0x7A:
        return chr(value - 0x20)
    if value in b"!\"#$%&'()*+,-./:;<=>?[]":
        return chr(value)
    return " "


def _command_completed(before: str, after: str) -> bool:
    """Return whether a new READY prompt appeared after command submission."""
    lines = [line.strip().upper() for line in after.splitlines() if line.strip()]
    return (
        after != before
        and after.upper().count("READY.") > before.upper().count("READY.")
        and bool(lines)
        and lines[-1] == "READY."
    )
