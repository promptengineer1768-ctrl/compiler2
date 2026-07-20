"""Focused diagnostics tests for the product VICE boot runner."""

from __future__ import annotations

from typing import Any

import pytest

from tests.e2e.product_runner import _boot_product


class _ResettingVice:
    """External-monitor boundary that loses its socket after loader output."""

    is_running = False

    def __init__(self) -> None:
        self.screen_calls = 0

    def wait_for_ready_screen(self, machine: Any) -> None:
        del machine

    def submit_command(self, machine: Any, command: str, timeout: float) -> None:
        del machine, command, timeout

    def type_text(self, text: str) -> None:
        assert text == "RUN\n"

    def call(self, name: str, timeout: float) -> None:
        assert name == "vice.execution.run"
        assert timeout == 1

    def screen_text(self, machine: Any) -> str:
        del machine
        self.screen_calls += 1
        if self.screen_calls == 1:
            return "DETECTING GEORAM\nGEORAM DETECTED\nLOADING TO GEORAM"
        raise ConnectionResetError(10054, "connection reset")


@pytest.mark.unit
def test_boot_reports_binary_monitor_reset_with_last_loader_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A monitor reset must not be mislabeled as a 240-second loader hang."""
    monkeypatch.setattr("tests.e2e.product_runner.time.sleep", lambda _: None)
    vice = _ResettingVice()

    with pytest.raises(RuntimeError, match="binary monitor disconnected") as exc:
        _boot_product(vice, object())

    text = str(exc.value)
    assert "process_running=False" in text
    assert "LOADING TO GEORAM" in text
