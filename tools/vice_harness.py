"""Shared supervised VICE-next harness for stock reference observations."""

from __future__ import annotations

import json
import os
import shutil
import struct
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final

ROOT: Final = Path(__file__).resolve().parents[1]
VICE_NEXT_ROOT: Final = ROOT.parent / "tools" / "vice-next-mcp"
VICE_NEXT_SRC: Final = VICE_NEXT_ROOT / "src"
if str(VICE_NEXT_SRC) not in sys.path:
    sys.path.insert(0, str(VICE_NEXT_SRC))

from vice_next_mcp.monitor import BinaryMonitorTransport  # noqa: E402,F401
from vice_next_mcp.monitor_sync import BinaryMonitor  # noqa: E402
from vice_next_mcp.supervisor import Instance, Supervisor  # noqa: E402

_DEFAULT_RUNTIME: Final = (
    ROOT.parent / "builds" / "vice-instrumentation-windows" / "extracted" / "src"
)
VICE_ROOT: Final = Path(os.environ.get("VICE_NEXT_RUNTIME", _DEFAULT_RUNTIME)).resolve()


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
    """Raised when a supervised VICE-next operation fails."""


class ViceMCP:
    """Compatibility facade over one supervised binary-monitor instance."""

    def __init__(self, endpoint: str = "vice-next://unbound") -> None:
        """Create an unbound facade for compatibility/introspection tests."""
        self.endpoint = endpoint
        self._instance: Instance | None = None
        self._supervisor: Supervisor | None = None
        self.artifact_dir: Path | None = None
        self._paused = False

    @classmethod
    def connected(
        cls, supervisor: Supervisor, instance: Instance, artifact_dir: Path
    ) -> "ViceMCP":
        """Bind a facade to a supervised instance."""
        item = cls(f"vice-next://{instance.id}")
        item._supervisor = supervisor
        item._instance = instance
        item.artifact_dir = artifact_dir
        return item

    @property
    def monitor_port(self) -> int:
        """Return the supervisor-assigned ephemeral monitor port."""
        if self._instance is None or self._instance.monitor is None:
            raise ViceMCPError("VICE-next client is not connected")
        return int(self._instance.monitor.socket.getpeername()[1])

    @property
    def capabilities(self) -> frozenset[str]:
        """Return native and instrumented capabilities for this instance."""
        return frozenset(self._bound().capabilities)

    @property
    def process_id(self) -> int:
        """Return the supervised emulator process ID."""
        process = self._bound().process
        if process is None:
            raise ViceMCPError("VICE-next process is unavailable")
        return int(process.pid)

    @property
    def is_running(self) -> bool:
        """Return whether the supervised emulator process is alive."""
        process = self._bound().process
        return process is not None and process.poll() is None

    def _bound(self) -> Instance:
        if self._instance is None or self._instance.monitor is None:
            raise ViceMCPError("VICE-next client is not connected")
        return self._instance

    @staticmethod
    def _text_result(value: dict[str, object]) -> dict[str, object]:
        return {"content": [{"type": "text", "text": json.dumps(value)}]}

    def call(
        self,
        name: str,
        arguments: dict[str, object] | None = None,
        *,
        timeout: float = 10.0,
        retries: int = 2,
    ) -> object:
        """Translate the legacy call surface to native monitor operations."""
        del timeout, retries
        args = arguments or {}
        instance = self._bound()
        monitor = instance.monitor
        assert monitor is not None
        try:
            if name == "vice.ping":
                version, revision = _vice_info(monitor.call(0x85).body)
                return self._text_result(
                    {
                        "version": ".".join(str(item) for item in version),
                        "revision": revision,
                        "instance_id": instance.id,
                        "generation": instance.generation,
                        "monitor_port": self.monitor_port,
                    }
                )
            if name == "vice.execution.pause":
                monitor.ping()
                self._paused = True
                return self._text_result({"execution_state": "paused"})
            if name == "vice.execution.run":
                monitor.resume()
                self._paused = False
                return self._text_result({"execution_state": "running"})
            if name == "vice.memory.read":
                address = _address(args["address"])
                data = monitor.memory(address, int(args["size"]))
                if not self._paused:
                    monitor.resume()
                return self._text_result({"data": list(data)})
            if name == "vice.memory.write":
                monitor.memory_write(_address(args["address"]), bytes(args["data"]))
                return self._text_result({"written": len(args["data"])})
            if name == "vice.keyboard.type":
                monitor.keyboard_feed(_petscii(str(args["text"])))
                return self._text_result({"accepted": len(str(args["text"]))})
            if name == "vice.keyboard.restore":
                self.restore_key(str(args.get("action", "press")))
                return self._text_result({"physical_restore": True})
            if name == "vice.keyboard.key_press":
                self.press_key(str(args["key"]))
                return self._text_result({"accepted": 1})
            if name == "vice.disk.attach":
                _autostart(monitor, Path(str(args["path"])), run=False)
                return self._text_result({"unit": int(args.get("unit", 8))})
            if name == "vice.autostart":
                _autostart(
                    monitor,
                    Path(str(args["path"])),
                    run=bool(args.get("run", True)),
                )
                return self._text_result({"path": str(args["path"])})
            if name == "vice.snapshot.save":
                if self.artifact_dir is None:
                    raise ViceMCPError("snapshot requires an artifact directory")
                snapshot = self.artifact_dir / f"{args['name']}.vsf"
                monitor.dump(snapshot)
                return self._text_result({"path": str(snapshot), "name": args["name"]})
        except Exception as exc:  # noqa: BLE001
            raise ViceMCPError(f"VICE-next operation failed: {name}") from exc
        raise ViceMCPError(f"unsupported VICE-next compatibility operation: {name}")

    def memory_read(self, address: int, length: int) -> bytes:
        """Read bytes through the current CPU-visible map."""
        monitor = self._bound().monitor
        assert monitor is not None
        data = monitor.memory(address, length)
        if not self._paused:
            monitor.resume()
        return data

    def memory_write(self, address: int, data: bytes) -> None:
        """Write bytes through the current CPU-visible map."""
        monitor = self._bound().monitor
        assert monitor is not None
        monitor.memory_write(address, data)

    def type_text(self, text: str) -> None:
        """Feed a complete PETSCII sequence through monitor command ``0x72``."""
        monitor = self._bound().monitor
        assert monitor is not None
        monitor.keyboard_feed(_petscii(text))
        if any(char in "\r\n" for char in text):
            time.sleep(0.1)

    def press_key(
        self,
        key: str,
        *,
        hold_frames: int | None = None,
        hold_ms: int | None = None,
    ) -> None:
        """Press a feed key, or use the instrumented RESTORE extension."""
        del hold_frames, hold_ms
        if key.upper() == "RESTORE":
            self.restore_key("press")
            self.restore_key("release")
            return
        names = {"RETURN": "\r", "ENTER": "\r", "SPACE": " "}
        self.type_text(names.get(key.upper(), key))

    def restore_key(self, action: str = "press") -> None:
        """Drive the physical RESTORE line through instrumented command ``0x74``."""
        if "vice.keyboard.restore" not in self.capabilities:
            raise ViceMCPError("instrumented RESTORE capability is unavailable")
        if action not in {"press", "release"}:
            raise ValueError("RESTORE action must be press or release")
        monitor = self._bound().monitor
        assert monitor is not None
        monitor.keyboard_restore(action == "press")

    def autostart(self, path: Path, *, run: bool = True) -> None:
        """Load a PRG or disk image through native autostart."""
        monitor = self._bound().monitor
        assert monitor is not None
        _autostart(monitor, path, run=run)

    def snapshot_save(self, path: Path) -> None:
        """Save this exact emulator state to a caller-owned snapshot path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        monitor = self._bound().monitor
        assert monitor is not None
        monitor.dump(path)

    def snapshot_load(self, path: Path) -> None:
        """Restore one caller-owned snapshot into this isolated instance."""
        monitor = self._bound().monitor
        assert monitor is not None
        monitor.undump(path)

    def submit_command(
        self,
        machine: ViceMachine,
        command: str,
        *,
        timeout: float = 20.0,
    ) -> str:
        """Feed one command and wait for a new READY prompt."""
        before = self.screen_text(machine)
        self.type_text(command.rstrip("\r\n") + "\r")
        monitor = self._bound().monitor
        assert monitor is not None
        monitor.resume()
        deadline = time.monotonic() + timeout
        last_screen = before
        while time.monotonic() < deadline:
            last_screen = self.screen_text(machine)
            if _command_completed(before, last_screen):
                return last_screen
            monitor.resume()
            time.sleep(0.05)
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
        monitor = self._bound().monitor
        assert monitor is not None
        while time.monotonic() < deadline:
            screen = self.screen_text(machine)
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
            monitor.resume()
            time.sleep(0.05)
        raise TimeoutError(f"VICE did not reach a stable READY prompt\n{last_screen}")


@contextmanager
def running_vice(
    machine: ViceMachine,
    *,
    port: int | None = None,
    startup_timeout: float = 15.0,
    extra_args: tuple[str, ...] = (),
) -> Iterator[ViceMCP]:
    """Start an isolated instrumented VICE instance on an ephemeral port."""
    del port  # Legacy caller ports are intentionally replaced by ephemeral leases.
    executable = VICE_ROOT / machine.executable
    if not executable.is_file():
        raise FileNotFoundError(executable)
    artifacts = ROOT / "debug" / "vice-next"
    artifacts.mkdir(parents=True, exist_ok=True)
    supervisor = Supervisor(
        executable=str(executable),
        monitor_port=0,
        startup_timeout=startup_timeout,
        workdir=str(VICE_ROOT),
        headless=True,
    )
    os.environ.setdefault("VICE_MCP_INSTRUMENTED", "1")
    instance = supervisor.create(
        machine=machine.executable.removesuffix(".exe"),
        extra_args=("-warp", "-sounddev", "dummy", *extra_args),
    )
    client = ViceMCP.connected(supervisor, instance, artifacts)
    try:
        instance.monitor.resume()
        yield client
    finally:
        supervisor.close()


@contextmanager
def _snapshot_lock(path: Path, timeout: float = 180.0) -> Iterator[None]:
    """Serialize cold creation of one reusable warm snapshot across workers."""
    lock = path.with_suffix(path.suffix + ".lock")
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                owner = int(lock.read_text(encoding="ascii").strip())
                os.kill(owner, 0)
            except (FileNotFoundError, ProcessLookupError, ValueError):
                lock.unlink(missing_ok=True)
                continue
            except PermissionError:
                pass
            try:
                if time.time() - lock.stat().st_mtime > timeout:
                    lock.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for warm snapshot {path}")
            time.sleep(0.1)
            continue
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        try:
            yield
        finally:
            lock.unlink(missing_ok=True)
        return


def _private_snapshot_path(snapshot: Path) -> Path:
    """Return a worker-private snapshot copy safe for parallel UNDUMP calls."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    safe_worker = "".join(char if char.isalnum() else "_" for char in worker)
    return snapshot.with_name(
        f"{snapshot.stem}.{safe_worker}.{os.getpid()}.{time.time_ns()}{snapshot.suffix}"
    )


@contextmanager
def running_warm_vice(
    machine: ViceMachine,
    snapshot: Path,
    prepare: Callable[[ViceMCP], object],
    ready: Callable[[ViceMCP], bool],
    *,
    startup_timeout: float = 15.0,
    extra_args: tuple[str, ...] = (),
) -> Iterator[ViceMCP]:
    """Start an isolated instance from a verified, build-keyed warm snapshot.

    Exactly one xdist worker cold-boots and publishes the snapshot atomically.
    Every consumer restores a private copy, preventing VICE snapshot races while
    preserving parallel execution after the warm state is available.
    """
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    private = _private_snapshot_path(snapshot)
    with running_vice(
        machine, startup_timeout=startup_timeout, extra_args=extra_args
    ) as client:
        try:
            if snapshot.exists():
                shutil.copy2(snapshot, private)
                client.snapshot_load(private)
            else:
                with _snapshot_lock(snapshot):
                    if snapshot.exists():
                        shutil.copy2(snapshot, private)
                        client.snapshot_load(private)
                    else:
                        prepare(client)
                        if not ready(client):
                            raise RuntimeError(
                                "cold VICE boot did not reach verified warm state"
                            )
                        temporary = private.with_suffix(".tmp")
                        client.snapshot_save(temporary)
                        os.replace(temporary, snapshot)
                        shutil.copy2(snapshot, private)
            if not ready(client):
                raise RuntimeError("restored VICE warm snapshot is not ready")
            yield client
        finally:
            private.unlink(missing_ok=True)


def _address(value: object) -> int:
    if isinstance(value, int):
        return value
    return int(str(value).replace("$", "0x"), 0)


def _petscii(text: str) -> bytes:
    return bytes(0x0D if char in "\r\n" else ord(char) & 0x7F for char in text)


def _autostart(monitor: BinaryMonitor, path: Path, *, run: bool) -> None:
    """Issue VICE binary-monitor autostart command ``0xDD``."""
    encoded = str(path).encode("utf-8")
    if len(encoded) > 0xFF:
        raise ValueError("VICE autostart path exceeds the protocol's 255-byte limit")
    monitor.call(0xDD, struct.pack("<BHB", int(run), 0, len(encoded)) + encoded)


def _vice_info(body: bytes) -> tuple[tuple[int, ...], str]:
    version_length = body[0]
    version = tuple(body[1 : 1 + version_length])
    revision_length = body[1 + version_length]
    revision = body[2 + version_length : 2 + version_length + revision_length]
    return version, revision.decode("utf-8")


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
