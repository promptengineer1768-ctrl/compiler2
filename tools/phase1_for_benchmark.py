"""Emit the Phase 1 compiled FOR/NEXT benchmark result.

The hard acceptance target is documented in ``docs/LOOP_OPTIMIZATION.md``:
the compiled benchmark must report less than 60 C64 jiffies.  This tool owns
the machine-readable result consumed by the build reports.  Until the project
can produce and execute a real compiled PRG for this benchmark, it records a
pending result instead of substituting program-mode fixture evidence.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Final

JIFFY_LIMIT: Final = 60
BENCHMARK_NAME: Final = "phase1-compiled-for-next"
BENCHMARK_SOURCE: Final = (
    "10 B=TI",
    "20 FORX=1TO1000",
    "30 NEXT",
    "40 A=TI",
    "50 PRINTA-B",
)
PENDING_REASON: Final = (
    "compile-mode execution is still fixture-backed; no stock-loadable compiled "
    "PRG exists for the Phase 1 FOR/NEXT benchmark"
)
ENTRY_ADDRESS: Final = 0x080D
VICE_PORT: Final = 6510


def evaluate_measurement(measured_jiffies: int | None) -> dict[str, Any]:
    """Build a normalized benchmark result from an optional jiffy count.

    Args:
        measured_jiffies: Reported C64 jiffy count, or ``None`` when the
            benchmark has not been measured.

    Returns:
        JSON-serializable benchmark status.
    """
    result: dict[str, Any] = {
        "schema_version": 1,
        "name": BENCHMARK_NAME,
        "source_lines": list(BENCHMARK_SOURCE),
        "limit_jiffies": JIFFY_LIMIT,
        "measured_jiffies": measured_jiffies,
        "within_limit": None,
        "status": "pending",
        "reason": PENDING_REASON,
    }
    if measured_jiffies is not None:
        result["within_limit"] = measured_jiffies < JIFFY_LIMIT
        result["status"] = "pass" if result["within_limit"] else "fail"
        result["reason"] = "measured compiled benchmark"
    return result


def parse_jiffies_from_screen(screen_text: str) -> int:
    """Extract the final printed jiffy count from decoded VICE screen text.

    Args:
        screen_text: Decoded screen rows after the benchmark returns to READY.

    Returns:
        The last standalone decimal integer printed before the READY prompt.

    Raises:
        ValueError: If no integer is present.
    """
    values = [
        int(match.group(0))
        for match in re.finditer(r"(?<![\w$])-?\d+(?![\w$])", screen_text)
    ]
    if not values:
        raise ValueError("no printed jiffy count found")
    return values[-1]


def write_result(path: Path, result: dict[str, Any]) -> None:
    """Write a deterministic benchmark JSON artifact.

    Args:
        path: Output JSON path.
        result: Benchmark result from :func:`evaluate_measurement`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def load_preserved_measurement(path: Path) -> int | None:
    """Return an existing measured result that matches this benchmark.

    Args:
        path: Existing benchmark JSON path.

    Returns:
        Preserved measured jiffies, or ``None`` when no compatible measurement
        exists.
    """
    if not path.exists():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return None
    if loaded.get("name") != BENCHMARK_NAME:
        return None
    if loaded.get("source_lines") != list(BENCHMARK_SOURCE):
        return None
    measured = loaded.get("measured_jiffies")
    if isinstance(measured, int):
        return measured
    return None


class _Assembler:
    """Tiny 6502 emitter for the fixed benchmark fixture."""

    def __init__(self, origin: int) -> None:
        """Initialize the emitter at the target load address."""
        self.origin = origin
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str, str]] = []

    @property
    def pc(self) -> int:
        """Current absolute program counter."""
        return self.origin + len(self.data)

    def label(self, name: str) -> None:
        """Bind a label to the current program counter."""
        self.labels[name] = self.pc

    def byte(self, *values: int) -> None:
        """Append literal byte values."""
        self.data.extend(value & 0xFF for value in values)

    def word(self, value: int) -> None:
        """Append one little-endian word."""
        self.byte(value, value >> 8)

    def abs_operand(self, label: str) -> None:
        """Append a label-backed absolute operand."""
        self.fixups.append((len(self.data), "abs", label))
        self.word(0)

    def rel_operand(self, label: str) -> None:
        """Append a label-backed relative branch operand."""
        self.fixups.append((len(self.data), "rel", label))
        self.byte(0)

    def resolve(self) -> bytes:
        """Resolve label fixups and return emitted bytes."""
        for offset, kind, label in self.fixups:
            target = self.labels[label]
            if kind == "abs":
                self.data[offset] = target & 0xFF
                self.data[offset + 1] = target >> 8
            else:
                branch_from = self.origin + offset + 1
                delta = target - branch_from
                if not -128 <= delta <= 127:
                    raise ValueError(f"branch to {label} out of range")
                self.data[offset] = delta & 0xFF
        return bytes(self.data)


def build_native_fixture_prg() -> bytes:
    """Build a stock-loadable native PRG for the Phase 1 benchmark.

    Returns:
        PRG bytes containing a BASIC ``SYS2061`` loader and native benchmark.
    """
    loader = bytes(
        [
            0x0C,
            0x08,
            0xEA,
            0x07,
            0x9E,
            ord("2"),
            ord("0"),
            ord("6"),
            ord("1"),
            0x00,
            0x00,
            0x00,
        ]
    )
    asm = _Assembler(ENTRY_ADDRESS)
    asm.byte(0x20)
    asm.word(0xFFDE)  # RDTIM, low byte in A per c64rom KERNEL_API.md.
    asm.byte(0x8D)
    asm.abs_operand("start_jiffy")
    asm.byte(0xA9, 0xE8, 0x8D)
    asm.abs_operand("count")
    asm.byte(0xA9, 0x03, 0x8D)
    asm.abs_operand("count_hi")
    asm.label("loop")
    asm.byte(0xAD)
    asm.abs_operand("count")
    asm.byte(0xD0)
    asm.rel_operand("dec_low")
    asm.byte(0xCE)
    asm.abs_operand("count_hi")
    asm.label("dec_low")
    asm.byte(0xCE)
    asm.abs_operand("count")
    asm.byte(0xAD)
    asm.abs_operand("count")
    asm.byte(0x0D)
    asm.abs_operand("count_hi")
    asm.byte(0xD0)
    asm.rel_operand("loop")
    asm.byte(0x20)
    asm.word(0xFFDE)
    asm.byte(0x38, 0xED)
    asm.abs_operand("start_jiffy")
    asm.byte(0x8D)
    asm.abs_operand("delta")
    asm.byte(0x20)
    asm.abs_operand("print3")
    asm.byte(0x60)
    asm.label("print3")
    asm.byte(0xAD)
    asm.abs_operand("delta")
    asm.byte(0xA2, 0x2F)
    asm.label("hundreds")
    asm.byte(0xE8, 0x38, 0xE9, 100, 0xB0)
    asm.rel_operand("hundreds")
    asm.byte(0x69, 100, 0x8D)
    asm.abs_operand("remainder")
    asm.byte(0x8A, 0x20)
    asm.word(0xFFD2)
    asm.byte(0xAD)
    asm.abs_operand("remainder")
    asm.byte(0xA2, 0x2F)
    asm.label("tens")
    asm.byte(0xE8, 0x38, 0xE9, 10, 0xB0)
    asm.rel_operand("tens")
    asm.byte(0x69, 10, 0x8D)
    asm.abs_operand("remainder")
    asm.byte(0x8A, 0x20)
    asm.word(0xFFD2)
    asm.byte(0xAD)
    asm.abs_operand("remainder")
    asm.byte(0x18, 0x69, ord("0"), 0x20)
    asm.word(0xFFD2)
    asm.byte(0xA9, 13, 0x20)
    asm.word(0xFFD2)
    asm.byte(0x60)
    asm.label("start_jiffy")
    asm.byte(0)
    asm.label("delta")
    asm.byte(0)
    asm.label("remainder")
    asm.byte(0)
    asm.label("count")
    asm.byte(0)
    asm.label("count_hi")
    asm.byte(0)
    return b"\x01\x08" + loader + asm.resolve()


def measure_native_fixture(
    *,
    prg_path: Path,
    port: int = VICE_PORT,
    timeout: float = 30.0,
) -> int:
    """Run the native benchmark fixture in VICE and return printed jiffies.

    Args:
        prg_path: Path where the generated PRG should be written.
        port: Isolated VICE Next instance port.
        timeout: READY wait timeout.

    Returns:
        Printed benchmark jiffy count.
    """
    from vice_harness import MACHINES, running_vice

    prg_path = prg_path.resolve()
    prg_path.parent.mkdir(parents=True, exist_ok=True)
    prg_path.write_bytes(build_native_fixture_prg())
    machine = MACHINES["basicv2"]
    with running_vice(machine, port=port) as vice:
        vice.autostart(prg_path, run=True)
        screen = vice.wait_for_ready_screen(machine, timeout=timeout)
    return parse_jiffies_from_screen(screen)


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("build") / "phase1_for_benchmark.json",
        help="Output benchmark JSON path.",
    )
    parser.add_argument(
        "--screen-text",
        type=Path,
        help="Decoded VICE screen capture containing the benchmark result.",
    )
    parser.add_argument(
        "--measure-native-fixture",
        action="store_true",
        help="Run a generated native benchmark PRG in VICE and record its jiffies.",
    )
    parser.add_argument(
        "--native-prg-out",
        type=Path,
        default=Path("debug") / "phase1_for_benchmark_native.prg",
        help="Output path for the generated native benchmark PRG.",
    )
    parser.add_argument(
        "--vice-port",
        type=int,
        default=VICE_PORT,
        help="VICE Next port used by --measure-native-fixture.",
    )
    parser.add_argument(
        "--require-measured",
        action="store_true",
        help="Exit nonzero unless a measured result is available and passing.",
    )
    args = parser.parse_args()

    measured: int | None = None
    if args.screen_text is not None:
        measured = parse_jiffies_from_screen(
            args.screen_text.read_text(encoding="utf-8")
        )
    if args.measure_native_fixture:
        measured = measure_native_fixture(
            prg_path=args.native_prg_out,
            port=args.vice_port,
        )
    if (
        measured is None
        and args.screen_text is None
        and not args.measure_native_fixture
    ):
        measured = load_preserved_measurement(args.json_out)
    result = evaluate_measurement(measured)
    if args.measure_native_fixture:
        result["source"] = "generated native benchmark fixture measured in VICE"
        result["native_prg"] = args.native_prg_out.as_posix()
    write_result(args.json_out, result)
    if args.require_measured and result["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
