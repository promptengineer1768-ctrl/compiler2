"""Boot the release disk and verify the installed BASIC V3 loader contract."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from vice_harness import MACHINES, ViceMCPError, running_vice

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.e2e
@pytest.mark.georam
@pytest.mark.vice
@pytest.mark.hardware
@pytest.mark.basicv3
@pytest.mark.timeout(1900)
def test_release_loader_installs_georam_and_answers_basic_query() -> None:
    """Exercise the actual D64, disk transfer, installed prompt, and query."""
    subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "build.ps1"),
            "-GeoramCompiler",
            "-UseCompressor",
        ],
        cwd=ROOT,
        check=True,
        timeout=180,
    )
    disk = ROOT / "build" / "compiler.d64"
    expected_georam = (ROOT / "build" / "georam.bin").read_bytes()[2:]

    machine = MACHINES["basicv2"]
    with running_vice(machine, port=6524, extra_args=("-georam",)) as vice:
        vice.call("vice.disk.attach", {"unit": 8, "path": str(disk)})
        vice.wait_for_ready_screen(machine)
        vice.submit_command(machine, 'LOAD"*",8', timeout=30)
        vice.type_text("RUN\n")
        vice.call("vice.execution.run", timeout=1)

        deadline = time.monotonic() + 1800
        unavailable_deadline = time.monotonic() + 30
        screen = ""
        observed = ""
        while time.monotonic() < deadline:
            time.sleep(5)
            try:
                screen = vice.screen_text(machine)
            except ViceMCPError as exc:
                if time.monotonic() >= unavailable_deadline:
                    stderr_path = ROOT / "debug" / "basicv2_vice_stderr.log"
                    stderr = (
                        stderr_path.read_text(encoding="utf-8", errors="replace")
                        if stderr_path.exists()
                        else "<VICE stderr log was not created>"
                    )
                    pytest.fail(
                        "VICE MCP remained unavailable for 30 seconds while "
                        f"waiting for loader completion: {exc}\n{stderr}"
                    )
                continue
            unavailable_deadline = time.monotonic() + 30
            observed += "\n" + screen
            if "?GEORAM LOAD ERROR" in screen:
                pytest.fail(f"loader reported a geoRAM installation error:\n{screen}")
            if "BASIC V3 READY" in screen:
                break
        else:
            pytest.fail(f"loader did not finish geoRAM installation:\n{screen}")

        for message in (
            "DETECTING GEORAM",
            "GEORAM DETECTED",
            "LOADING TO GEORAM",
            "BASIC V3 READY",
        ):
            assert message in observed

        vice.type_text("?BASIC()\n")
        vice.call("vice.execution.run", timeout=1)
        time.sleep(1)
        assert " 2" in vice.screen_text(machine)

        installed = bytearray()
        vice.call("vice.execution.pause")
        try:
            for block in range(4):
                for page in range(64):
                    vice.memory_write(0xDFFE, bytes((page, block)))
                    installed.extend(vice.memory_read(0xDE00, 256))
        finally:
            vice.call("vice.execution.run")
        assert bytes(installed) == expected_georam
