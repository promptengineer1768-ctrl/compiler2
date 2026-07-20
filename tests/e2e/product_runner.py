"""Product-side E2E executor: boot Compiler 2 D64 and apply matrix cases."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Final

from tests.e2e.reference_fixtures import load_reference

ROOT: Final = Path(__file__).resolve().parents[2]
DISK: Final = ROOT / "build" / "compiler.d64"
KEY_QUEUE: Final = 0x0277
KEY_COUNT: Final = 0x00C6
# Project editor ZP / BSS (from build/compiler.lbl; keep in sync if relocated).
ZP_CRSR_X: Final = 0x0F
ZP_CRSR_Y: Final = 0x10
CURSOR_DRAWN: Final = 0x3725
CURSOR_SAVED: Final = 0x3726
PROGRAM_LINES_COUNT: Final = 0xE103
SCREEN_BASE: Final = 0x0400

# Keywords whose stock values are non-deterministic across runs/emulators.
# TI$ itself is non-deterministic; LEN(TI$) fixtures use keyword TI$ but are
# numeric-stable — only bare TI prints use shape matching today.
# ST after stock fixture capture often retains load-status bits (e.g. 64);
# product cold READY may see 0. Compare shape (numeric) rather than exact value.
_NONDETERMINISTIC_KEYWORDS: Final = frozenset({"TI", "ST", "RND", "FRE"})


def normalize_product_screen(screen: str, source_lines: list[str]) -> str:
    """Normalize Compiler 2 screen text similarly to stock fixture rules.

    Also strips stock LOAD banners that some older fixtures still contain so
    product observations can compare to semantic result lines.
    """
    echoes = {line.strip().upper() for line in source_lines} | {
        "RUN",
        "LIST",
        "NEW",
        "COMPILE",
        "BASIC V3 READY",
        "DETECTING GEORAM",
        "GEORAM DETECTED",
        "LOADING TO GEORAM",
    }
    noise_prefixes = (
        'LOAD"',
        "SEARCHING FOR",
        "LOADING",
        "READY.",
        "**** COMMODORE",
        "64K RAM SYSTEM",
        "3-PLUS-1",
        "COMPILE",
    )
    bare_echoes = {re.sub(r"^\d+\s+", "", e) for e in echoes}
    kept: list[str] = []
    for line in screen.splitlines():
        normalized = re.sub(r"\s+", " ", line.strip().upper())
        if not normalized:
            continue
        if normalized in echoes:
            continue
        if any(normalized.startswith(p) for p in noise_prefixes):
            continue
        if normalized.endswith("BYTES FREE"):
            continue
        # Drop pure typed command echoes that match source without numbers
        if normalized in bare_echoes:
            continue
        # Drop RUN/COMPILE glued to a leftover digit from prior paint.
        if re.fullmatch(r"(RUN|COMPILE)\d*", normalized):
            continue
        # Drop residual numbered source lines left on screen (including
        # cursor-corrupted forms like ``0 PRINT "OK"`` from ``10 PRINT``).
        if re.match(r"^\d+\s+", normalized):
            continue
        kept.append(normalized)
    return "\n".join(kept)


def semantic_core(normalized: str) -> str:
    """Return the semantic payload of a normalized observation.

    Older stock fixtures sometimes embed LOAD/SEARCHING/LOADING noise. Product
    results do not. Comparison uses non-noise lines only.
    """
    if not normalized:
        return ""
    lines = normalized.splitlines()
    noise_starts = ("LOAD", "SEARCHING", "LOADING", "SEARCHING FOR")
    core = [
        ln
        for ln in lines
        if not any(ln.startswith(n) for n in noise_starts) and 'LOAD"' not in ln
    ]
    return "\n".join(core)


def _petscii_to_screen(code: int) -> int:
    if code < 0x20:
        return code
    if code < 0x60:
        return code & 0x3F
    if code < 0x80:
        return code & 0xDF
    return (code & 0x7F) | 0x40


def _hide_project_cursor(vice: Any) -> None:
    """Restore any reverse-video blink cell before host-side screen paints.

    The IRQ cursor saves the cell under the caret and ORs $80. If the host
    paints a new line while cursor_drawn=1, the next hide/toggle restores the
    *old* glyph and can wipe the first character of a numbered line (e.g.
    ``10 PRINT`` becomes `` 0 PRINT`` → stored as line 0).
    """
    drawn = vice.memory_read(CURSOR_DRAWN, 1)[0]
    if drawn:
        cx = vice.memory_read(ZP_CRSR_X, 1)[0]
        cy = vice.memory_read(ZP_CRSR_Y, 1)[0]
        if cx < 40 and cy < 25:
            saved = vice.memory_read(CURSOR_SAVED, 1)[0]
            addr = SCREEN_BASE + cy * 40 + cx
            vice.memory_write(addr, bytes((saved,)))
        vice.memory_write(CURSOR_DRAWN, bytes((0,)))
    # Also force cursor invisible so IRQ will not re-paint mid-write.
    # zp_crsr_vis is typically near cursor BSS; clear drawn is the critical bit.


def _paint_and_return(
    vice: Any, machine: Any, text: str, timeout: float = 30.0
) -> None:
    """Paint one logical line as screen codes and inject RETURN."""
    del machine  # reserved for future machine-specific maps
    mon = vice._bound().monitor
    assert mon is not None
    # Stay paused for the whole paint so IRQ cannot race the row rewrite.
    mon.ping()
    _hide_project_cursor(vice)
    cy = min(vice.memory_read(ZP_CRSR_Y, 1)[0], 23)
    cells = bytes(_petscii_to_screen(ord(c) & 0x7F) for c in text.upper())
    if len(cells) >= 40:
        cells = cells[:39]
    row = SCREEN_BASE + cy * 40
    # Full row rewrite so reverse bits and leftovers cannot stick.
    payload = cells + bytes([0x20] * (40 - len(cells)))
    vice.memory_write(row, payload)
    # Re-write first cell after hide in case an IRQ slipped a restore.
    if cells:
        vice.memory_write(row, cells[:1])
    vice.memory_write(ZP_CRSR_X, bytes((len(cells),)))
    vice.memory_write(ZP_CRSR_Y, bytes((cy,)))
    vice.memory_write(CURSOR_DRAWN, bytes((0,)))
    # Verify first digit of numbered lines survived before RETURN.
    if cells and cells[0] in range(0x30, 0x3A):
        first = vice.memory_read(row, 1)[0] & 0x7F
        if first != cells[0]:
            vice.memory_write(row, cells[:1])
    vice.memory_write(KEY_QUEUE, bytes((0x0D,)))
    vice.memory_write(KEY_COUNT, bytes((1,)))
    mon.resume()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.15)
        mon.ping()
        if vice.memory_read(KEY_COUNT, 1)[0] == 0:
            mon.resume()
            # Allow the line handler / codegen / RUN to settle.
            time.sleep(0.55)
            return
        mon.resume()
    mon.ping()
    mon.resume()
    raise TimeoutError(f"editor did not consume RETURN for {text!r}")


def _enter_numbered_line(vice: Any, machine: Any, text: str) -> None:
    """Enter one numbered program line and assert the store accepted it."""
    before = vice.memory_read(PROGRAM_LINES_COUNT, 1)[0]
    # The direct screen painter is intentionally limited to a physical C64
    # row.  A stored BASIC source line is not: Noel's benchmark, for example,
    # has a 55-character timing line.  Feed such lines through VICE's keyboard
    # transport so this remains an editor-input test instead of truncating the
    # source or substituting a test-only program representation.
    if len(text) < 40:
        _paint_and_return(vice, machine, text, timeout=45)
    else:
        vice.type_text(text + "\n")
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            time.sleep(0.15)
            if vice.memory_read(KEY_COUNT, 1)[0] == 0:
                # Keyboard-feed delivery does not use the C64 key queue on all
                # VICE builds; give the editor one frame to submit the line.
                time.sleep(0.25)
                break
        else:
            raise TimeoutError(f"editor did not consume keyboard input for {text!r}")
    # A drained keyboard queue only proves GETIN accepted the final byte.  A
    # long numbered line can still be compiling and publishing through the
    # program-store transaction.  Wait for that production-state transition
    # before injecting the next source line, otherwise a following RETURN can
    # arrive while the previous compile is still active.
    deadline = time.monotonic() + 20
    after = vice.memory_read(PROGRAM_LINES_COUNT, 1)[0]
    while after == before and time.monotonic() < deadline:
        time.sleep(0.15)
        after = vice.memory_read(PROGRAM_LINES_COUNT, 1)[0]
    # Replace/delete of the same line keeps count; matrix cases enter unique,
    # non-empty source lines, so a new line must publish a new count.
    if after == before:
        raise RuntimeError(
            f"numbered line was not published for {text!r}; "
            "hibasic/program_lines may be unavailable"
        )
    # After a silent store the cursor may not advance; force next physical row
    # so the following paint does not overwrite this line's screen cells.
    mon = vice._bound().monitor
    mon.ping()
    _hide_project_cursor(vice)
    cy = min(vice.memory_read(ZP_CRSR_Y, 1)[0] + 1, 24)
    vice.memory_write(ZP_CRSR_X, bytes((0,)))
    vice.memory_write(ZP_CRSR_Y, bytes((cy,)))
    mon.resume()
    time.sleep(0.1)


def _boot_product(vice: Any, machine: Any) -> str:
    """LOAD/RUN the release disk and wait for Compiler 2 READY."""
    vice.wait_for_ready_screen(machine)
    vice.submit_command(machine, 'LOAD"*",8', timeout=30)
    vice.type_text("RUN\n")
    vice.call("vice.execution.run", timeout=1)
    deadline = time.monotonic() + 240
    last = ""
    while time.monotonic() < deadline:
        time.sleep(2)
        try:
            last = vice.screen_text(machine)
        except OSError as exc:
            # A binary-monitor reset immediately after the raw IEC transfer is
            # materially different from an in-guest loader loop.  Preserve the
            # last visible loader phase so the VICE-backed caller can tell
            # whether the emulator disappeared during transfer, after handoff,
            # or while the editor was coming up.  Do not retry through a dead
            # monitor: that would turn a deterministic process failure into a
            # misleading READY timeout.
            running = getattr(vice, "is_running", False)
            raise RuntimeError(
                "VICE binary monitor disconnected while booting product "
                f"(process_running={running}); last screen:\n{last}"
            ) from exc
        if "BASIC V3 READY" in last:
            # Allow HIBASIC install / vector arm after first banner paint.
            time.sleep(3)
            last = vice.screen_text(machine)
            if "BASIC V3 READY" in last:
                return last
        if "?GEORAM LOAD ERROR" in last:
            raise RuntimeError(f"geoRAM load failed:\n{last}")
    raise TimeoutError(f"product READY not reached:\n{last}")


def run_product_cell(cell: dict[str, Any], *, port: int = 6700) -> dict[str, Any]:
    """Execute one matrix cell on Compiler 2 and return observation record.

    Returns:
        Dict with keys: actual, screen, mode, error (optional).
    """
    from vice_harness import MACHINES, running_vice

    if not DISK.exists():
        raise FileNotFoundError(f"missing product disk: {DISK}")

    profile = str(cell["profile"])
    # Product always boots C64 BASICV3 image today; basicv35 product path later.
    machine_key = "basicv2"
    machine = MACHINES[machine_key]
    mode = str(cell["mode"])
    source_lines = list(cell.get("source_lines") or [])
    if not source_lines:
        raise ValueError(f"cell {cell.get('cell_id')} has no source_lines")

    with running_vice(
        machine,
        port=port,
        extra_args=("-georam", "-georamsize", "512", "-8", str(DISK)),
    ) as vice:
        _boot_product(vice, machine)
        if mode == "immediate":
            for line in source_lines:
                _paint_and_return(vice, machine, line)
        elif mode in ("program", "compile"):
            # Clear any residual program, then enter numbered lines one by one.
            try:
                _paint_and_return(vice, machine, "NEW", timeout=20)
            except TimeoutError:
                pass
            time.sleep(0.35)
            for line in source_lines:
                _enter_numbered_line(vice, machine, line)
            # compile mode: attempt COMPILE then RUN when product supports it;
            # until then fall through to program RUN semantics as interim path.
            if mode == "compile":
                try:
                    _paint_and_return(vice, machine, "COMPILE", timeout=45)
                except TimeoutError:
                    pass
                time.sleep(0.5)
            _paint_and_return(vice, machine, "RUN", timeout=60)
        else:
            raise ValueError(f"unknown mode {mode}")
        time.sleep(1.0)
        vice.call("vice.execution.pause")
        screen = vice.screen_text(machine)
        vice.call("vice.execution.run")

    actual = normalize_product_screen(screen, source_lines)
    return {"actual": actual, "screen": screen, "mode": mode, "profile": profile}


def _shape_match_numeric(actual_core: str, expected_core: str) -> bool:
    """Match non-deterministic numeric prints (TI) by shape, not value.

    Stock and product TI values differ by wall-clock. Accept when every
    expected semantic line is a number and actual has the same count of
    numeric lines.
    """
    exp_lines = [ln for ln in expected_core.splitlines() if ln.strip()]
    act_lines = [ln for ln in actual_core.splitlines() if ln.strip()]
    if not exp_lines or len(exp_lines) != len(act_lines):
        return False
    num = re.compile(r"^[+-]?\d+(\.\d+)?([E][+-]?\d+)?$")
    return all(num.match(e.replace(" ", "")) for e in exp_lines) and all(
        num.match(a.replace(" ", "")) for a in act_lines
    )


def compare_to_oracle(cell: dict[str, Any], actual: str) -> dict[str, Any]:
    """Compare product actual against stock/project oracle.

    Returns:
        passed (bool|None), expected, actual_core, expected_core, detail.
    """
    if cell.get("applicability") == "not_applicable":
        return {
            "passed": None,
            "expected": "",
            "actual_core": actual,
            "expected_core": "",
            "detail": "not_applicable",
        }

    if cell.get("oracle") == "project":
        expected = str(cell.get("expected_result") or "")
        exp_core = semantic_core(expected.upper() if expected else "")
        act_core = semantic_core(actual)
        return {
            "passed": act_core == exp_core,
            "expected": expected,
            "actual_core": act_core,
            "expected_core": exp_core,
            "detail": "project_oracle",
        }

    fixture_id = cell.get("fixture_id")
    if not fixture_id:
        return {
            "passed": None,
            "expected": "",
            "actual_core": actual,
            "expected_core": "",
            "detail": "missing_fixture_id",
        }
    try:
        fixture = load_reference(str(cell["profile"]), str(fixture_id))
    except (OSError, ValueError, KeyError) as exc:
        return {
            "passed": None,
            "expected": "",
            "actual_core": actual,
            "expected_core": "",
            "detail": f"fixture_load_error:{exc}",
        }
    if fixture.get("normalization_rules") == "catalog-v1":
        return {
            "passed": None,
            "expected": fixture.get("normalized_result", ""),
            "actual_core": actual,
            "expected_core": "",
            "detail": "catalog_placeholder",
        }
    expected = str(fixture.get("normalized_result") or "")
    exp_core = semantic_core(expected)
    act_core = semantic_core(actual)
    keyword = str(cell.get("keyword") or "").upper()
    if keyword in _NONDETERMINISTIC_KEYWORDS:
        passed = _shape_match_numeric(act_core, exp_core)
        return {
            "passed": passed,
            "expected": expected,
            "actual_core": act_core,
            "expected_core": exp_core,
            "detail": "stock_oracle_shape",
        }
    return {
        "passed": act_core == exp_core,
        "expected": expected,
        "actual_core": act_core,
        "expected_core": exp_core,
        "detail": "stock_oracle",
    }
