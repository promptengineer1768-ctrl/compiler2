"""Build deterministic compressor configs and compressed Compiler 2 artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def write_configs(build_dir: Path) -> tuple[Path, Path]:
    """Write compressor configs and stage the compiler payload.

    Args:
        build_dir: Generated build directory.

    Returns:
        Paths to the compiler and geoRAM stream configs.
    """
    compile_bin = build_dir / "compile.bin"
    georam_bin = build_dir / "georam.bin"
    if not compile_bin.exists() or not georam_bin.exists():
        raise FileNotFoundError("compile.bin and georam.bin must exist")
    segments = build_dir / "segments"
    segments.mkdir(parents=True, exist_ok=True)
    compiler_main = segments / "compiler_main.bin"
    shutil.copyfile(compile_bin, compiler_main)
    georam_payload = segments / "georam_payload.bin"
    georam_bytes = georam_bin.read_bytes()
    if georam_bytes[:2] != b"\x00\xde":
        raise ValueError("georam.bin must start with fake PRG load address $DE00")
    georam_payload.write_bytes(georam_bytes[2:])

    compiler_cfg = build_dir / "compressor_layout.cfg"
    compiler_cfg.write_text(
        "entry = $080D\n"
        "entry_mode = jmp\n"
        f"segment = compiler_main, bin, {compiler_main.as_posix()}, $080D\n",
        encoding="ascii",
    )
    georam_cfg = build_dir / "georam_stream.cfg"
    georam_cfg.write_text(
        "entry = $080D\n"
        "entry_mode = jmp\n"
        f"segment = compiler_main, bin, {compiler_main.as_posix()}, $080D\n"
        f"segment = georam, georam_stream, {georam_payload.as_posix()}, "
        "0, 0, 512, 256, GEORAM\n",
        encoding="ascii",
    )
    return compiler_cfg, georam_cfg


def _run(command: list[str], cwd: Path) -> None:
    """Run one compressor command and surface its diagnostics.

    Args:
        command: Executable and arguments.
        cwd: Project root working directory.
    """
    subprocess.run(command, cwd=cwd, check=True)


def build_artifacts(root: Path, build_dir: Path, compressor_root: Path) -> None:
    """Build compressed PRG and CGS1 sidecar artifacts.

    Args:
        root: Compiler 2 project root.
        build_dir: Generated build directory.
        compressor_root: Compressor project root.
    """
    compiler_cfg, georam_cfg = write_configs(build_dir)
    compressor = compressor_root / "build" / "lzss_compressor.exe"
    if not compressor.exists():
        raise FileNotFoundError(f"compressor not found: {compressor}")

    compressed_main = build_dir / "compile_compressed.prg"
    _run(
        [
            str(compressor),
            "--pack",
            "--cfg",
            str(compiler_cfg),
            "-o",
            str(compressed_main),
        ],
        root,
    )
    metadata = build_dir / "GEORAM_compressed.json"
    sidecar_driver = build_dir / "georam_sidecar_loader.prg"
    _run(
        [
            str(compressor),
            "--pack",
            "--cfg",
            str(georam_cfg),
            "--manifest-output",
            str(metadata),
            "-o",
            str(sidecar_driver),
        ],
        root,
    )

    candidates = [root / "GEORAM", build_dir / "GEORAM", root / "GEORAM.prg"]
    sidecar = next((path for path in candidates if path.exists()), None)
    if sidecar is None:
        raise FileNotFoundError("compressor did not emit the GEORAM sidecar")
    normalized = build_dir / "GEORAM_compressed.prg"
    shutil.move(str(sidecar), normalized)
    compressed = normalized.read_bytes()
    if compressed[:4] != b"CGS1":
        raise ValueError("compressed geoRAM sidecar has no CGS1 header")
    normalized.write_bytes(b"\x00\xde" + compressed)
    if not metadata.exists():
        metadata.write_text(
            json.dumps({"format": "CGS1", "sidecar": normalized.name}, indent=2),
            encoding="ascii",
        )


def main() -> None:
    """Parse command-line arguments and build compressor artifacts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument(
        "--compressor-root",
        type=Path,
        default=Path(r"C:\Users\me\Documents\Coding Projects\compressor"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    build_dir = (root / args.build_dir).resolve()
    build_artifacts(root, build_dir, args.compressor_root.resolve())


if __name__ == "__main__":
    main()
