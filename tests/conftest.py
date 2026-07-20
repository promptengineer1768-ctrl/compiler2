"""Shared pytest harness adjustments for the local C64 emulator binding.

This harness performs one adjustment only: it makes ``emu.execute`` run the
real assembled routine until it returns (``execute_rts``), matching the
subroutine-style unit tests. It never simulates, shadows, or overwrites the
emulator's state. Every assertion observes the real 6502 execution of the
production bytes, including CPU-port banking and RAM under the I/O window as
modelled by the emulator core.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, cast

ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = ROOT.parent / "tools"
PROJECT_TOOLS_ROOT = ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
if str(PROJECT_TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_TOOLS_ROOT))


def pytest_configure() -> None:
    """Make ``emu.execute`` run the real routine until RTS.

    The native ``execute`` runs for a cycle budget; the subroutine-style unit
    tests expect run-until-return semantics against the real assembled bytes.
    No other emulator behaviour is altered.
    """
    try:
        from emu6502_c64_bindings import C64Emu6502
    except ImportError:
        return

    if getattr(C64Emu6502, "_compiler2_harness_patched", False):
        return

    original_execute_rts = cast(Callable[[Any, int, int], Any], C64Emu6502.execute_rts)

    def execute(self: Any, address: int, max_cycles: int) -> Any:
        """Execute a callable routine until RTS against the real bytes."""
        return original_execute_rts(self, address, max_cycles)

    C64Emu6502.execute = execute
    C64Emu6502._compiler2_harness_patched = True
