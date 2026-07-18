"""Boot the release disk and verify the installed BASIC V3 loader contract."""

from __future__ import annotations

import re
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
    # Uncompressed dual D64: raw GEORAM PRG install path (CGS1 covered unit-side).
    subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "build.ps1"),
            "-GeoramCompiler",
        ],
        cwd=ROOT,
        check=True,
        timeout=180,
    )
    disk = ROOT / "build" / "compiler.d64"
    expected_georam = (ROOT / "build" / "georam.bin").read_bytes()[2:]

    machine = MACHINES["basicv2"]
    # Match the proven detection-project VICE profile: enable geoRAM with an
    # explicit size in KiB. Bare `-georam` alone is insufficient on HeadlessVICE
    # (see Coding Projects/detection tests/vice_profiles.py GEORAM_PROFILES).
    with running_vice(
        machine,
        port=6524,
        extra_args=("-georam", "-georamsize", "512", "-8", str(disk)),
    ) as vice:
        vice.wait_for_ready_screen(machine)
        vice.submit_command(machine, 'LOAD"*",8', timeout=30)
        vice.type_text("RUN\n")
        vice.call("vice.execution.run", timeout=1)

        deadline = time.monotonic() + 300
        unavailable_deadline = time.monotonic() + 60
        screen = ""
        observed = ""
        while time.monotonic() < deadline:
            time.sleep(2)
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
                        "VICE MCP remained unavailable for 60 seconds while "
                        f"waiting for loader completion: {exc}\n{stderr}"
                    )
                continue
            unavailable_deadline = time.monotonic() + 60
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

        # Editor must be functional, not merely update private state behind a
        # startup banner. The IRQ cursor must visibly reverse the screen cell
        # at the project cursor coordinates.
        vice.call("vice.execution.pause")
        cursor_x = vice.memory_read(0x0F, 1)[0]  # zp_crsr_x
        cursor_y = vice.memory_read(0x10, 1)[0]  # zp_crsr_y
        assert cursor_x < 40 and cursor_y < 25
        cursor_address = 0x0400 + cursor_y * 40 + cursor_x
        cursor_samples = set()
        for _ in range(8):
            cursor_samples.add(vice.memory_read(cursor_address, 1)[0])
            vice.call("vice.execution.run", timeout=1)
            time.sleep(0.25)
        assert any((value ^ 0x80) in cursor_samples for value in cursor_samples), (
            f"cursor cell ${cursor_address:04X} did not alternate reverse video: "
            f"{sorted(cursor_samples)}"
        )

        # The disk channel opened for the GEORAM transfer must be closed, not
        # left open. KERNAL input-channel state $99 must read 0.
        open_channel = vice.memory_read(0x99, 1)[0]
        assert open_channel == 0, (
            f"GEORAM load channel left open (KERNAL $99={open_channel:#04X}); "
            "loader did not close the file."
        )

        # A keystroke must be consumed and visibly edited into the line.
        # Drive the production GETIN path: place PETSCII into the stock KERNAL
        # keyboard queue ($0277/$C6) while the resident poll loop is live. VICE
        # keyboard_feed alone can leave bytes queued without a guaranteed
        # SCNKEY/GETIN turn under the project IRQ ownership model.
        vice.call("vice.execution.pause")
        key_queue = 0x0277
        key_count = 0x00C6
        prior = vice.memory_read(key_count, 1)[0]
        assert prior < 10, f"keyboard queue unexpectedly full (ndx={prior})"
        vice.memory_write(key_queue + prior, bytes((ord("X"),)))
        vice.memory_write(key_count, bytes((prior + 1,)))
        vice.call("vice.execution.run")
        time.sleep(1.5)
        vice.call("vice.execution.pause")
        post_input_screen = vice.screen_text(machine)
        post_ndx = vice.memory_read(key_count, 1)[0]
        vice.call("vice.execution.run")
        assert post_ndx == 0, (
            f"resident editor did not drain GETIN queue (ndx={post_ndx})"
        )
        assert "X" in post_input_screen, "resident editor did not echo a typed key"

        # Direct-mode PRINT must execute on RETURN and paint through CHROUT.
        # Paint the statement as screen codes on the project cursor row (same
        # cells the editor captures), then inject RETURN through the KERNAL
        # queue so resident_handle_key submits and runs the line.
        vice.call("vice.execution.pause")
        cursor_x = vice.memory_read(0x0F, 1)[0]
        cursor_y = vice.memory_read(0x10, 1)[0]
        assert cursor_y < 25
        command = 'PRINT "HELLO WORLD"'

        def _petscii_letter_to_screen(code: int) -> int:
            """Map unshifted PETSCII text to default-charset screen codes."""
            if code < 0x20:
                return code
            if code < 0x60:
                return code & 0x3F
            if code < 0x80:
                return code & 0xDF
            return (code & 0x7F) | 0x40

        row_addr = 0x0400 + cursor_y * 40
        cells = bytes(_petscii_letter_to_screen(ord(ch) & 0x7F) for ch in command)
        assert len(cells) < 40
        vice.memory_write(row_addr, cells + bytes([0x20] * (40 - len(cells))))
        # Leave the project cursor on this row so screen_line_input captures it.
        vice.memory_write(0x0F, bytes((len(cells),)))  # zp_crsr_x
        vice.memory_write(0x10, bytes((cursor_y,)))  # zp_crsr_y
        vice.memory_write(key_queue, bytes((0x0D,)))
        vice.memory_write(key_count, bytes((1,)))
        vice.call("vice.execution.run")
        drain_deadline = time.monotonic() + 20
        while time.monotonic() < drain_deadline:
            time.sleep(0.2)
            vice.call("vice.execution.pause")
            if vice.memory_read(key_count, 1)[0] == 0:
                break
            vice.call("vice.execution.run")
        else:
            pytest.fail("editor did not consume RETURN for PRINT submit")
        time.sleep(1.0)
        vice.call("vice.execution.pause")
        print_screen = vice.screen_text(machine)
        vice.call("vice.execution.run")
        # Require a line that is exactly the printed text (not the source line
        # PRINT "HELLO WORLD", which also contains those words).
        output_lines = [line.strip() for line in print_screen.splitlines()]
        assert any(line == "HELLO WORLD" for line in output_lines), (
            "direct-mode PRINT did not execute on RETURN:\n" + print_screen
        )

        # PRINT of an unbound single-letter variable must evaluate (stock: 0).
        vice.call("vice.execution.pause")
        cursor_y = vice.memory_read(0x10, 1)[0]
        if cursor_y >= 24:
            cursor_y = 23
        cmd_x = "PRINT X"
        cells_x = bytes(
            _petscii_letter_to_screen(ord(ch) & 0x7F) for ch in cmd_x
        )
        row_addr = 0x0400 + cursor_y * 40
        vice.memory_write(row_addr, cells_x + bytes([0x20] * (40 - len(cells_x))))
        vice.memory_write(0x0F, bytes((len(cells_x),)))
        vice.memory_write(0x10, bytes((cursor_y,)))
        vice.memory_write(key_queue, bytes((0x0D,)))
        vice.memory_write(key_count, bytes((1,)))
        vice.call("vice.execution.run")
        drain_deadline = time.monotonic() + 45
        drained = False
        while time.monotonic() < drain_deadline:
            time.sleep(0.25)
            vice.call("vice.execution.pause")
            if vice.memory_read(key_count, 1)[0] == 0:
                drained = True
                break
            vice.call("vice.execution.run")
        print_x_screen = vice.screen_text(machine)
        vice.call("vice.execution.run")
        assert drained, (
            "editor did not consume RETURN for PRINT X:\n" + print_x_screen
        )
        # Unbound single-letter int cells default to 0.
        numeric_lines = [
            line.strip()
            for line in print_x_screen.splitlines()
            if line.strip()
            and "PRINT" not in line.upper()
            and "HELLO" not in line.upper()
            and "READY" not in line.upper()
        ]
        assert any(
            re.fullmatch(r" *0 *", line) for line in numeric_lines
        ), ("direct-mode PRINT X produced no numeric 0 output:\n" + print_x_screen)

        # Verify the installed geoRAM image matches the release GEORAM payload.
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
