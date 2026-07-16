"""Build deterministic compressor configs and compressed Compiler 2 artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
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


def _verify_georam_sidecar(
    unpacker: Path,
    sidecar: Path,
    expected_payload: bytes,
    root: Path,
) -> None:
    """Verify a CGS1 sidecar recovers the exact staged geoRAM payload.

    Args:
        unpacker: Compressor project's sidecar unpacker executable.
        sidecar: Fake-header PRG containing the CGS1 stream.
        expected_payload: Headerless geoRAM bytes that were compressed.
        root: Compiler 2 root, used for temporary debug output.

    Raises:
        ValueError: If the sidecar header or recovered payload is incorrect.
    """
    data = sidecar.read_bytes()
    if data[:2] != b"\x00\xde" or data[2:6] != b"CGS1":
        raise ValueError("compressed geoRAM sidecar is not a CGS1 PRG")

    debug_dir = root / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="georam_sidecar_verify_", dir=debug_dir
    ) as temporary:
        temporary_dir = Path(temporary)
        headerless = temporary_dir / "GEORAM"
        headerless.write_bytes(data[2:])
        _run(
            [
                str(unpacker),
                "--decompress-sidecar",
                str(headerless),
                str(temporary_dir),
                "--bin",
            ],
            root,
        )
        recovered = temporary_dir / "georam.bin"
        if not recovered.is_file():
            raise ValueError("sidecar unpacker produced no geoRAM payload")
        if recovered.read_bytes() != expected_payload:
            raise ValueError(
                "compressed geoRAM sidecar does not round-trip its staged payload"
            )


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
    unpacker = compressor_root / "build" / "lzss_unpacker.exe"
    if not unpacker.exists():
        raise FileNotFoundError(f"unpacker not found: {unpacker}")

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
    emitted_sidecar = build_dir / "GEORAM"
    emitted_sidecar.unlink(missing_ok=True)
    normalized = build_dir / "GEORAM_compressed.prg"
    normalized.unlink(missing_ok=True)
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

    if not emitted_sidecar.exists():
        raise FileNotFoundError("compressor did not emit the GEORAM sidecar")
    emitted_sidecar.replace(normalized)
    compressed = normalized.read_bytes()
    if compressed[:4] != b"CGS1":
        raise ValueError("compressed geoRAM sidecar has no CGS1 header")
    normalized.write_bytes(b"\x00\xde" + compressed)
    georam_payload = (build_dir / "segments" / "georam_payload.bin").read_bytes()
    _verify_georam_sidecar(unpacker, normalized, georam_payload, root)

    if not metadata.exists():
        raise FileNotFoundError("compressor did not emit the GEORAM sidecar manifest")
    manifest = json.loads(metadata.read_text(encoding="utf-8"))
    sidecars = manifest.get("sidecars")
    if not isinstance(sidecars, list) or len(sidecars) != 1:
        raise ValueError("GEORAM sidecar manifest must contain one sidecar")
    record = sidecars[0]
    if not isinstance(record, dict) or record.get("destination_kind") != "georam":
        raise ValueError("GEORAM sidecar manifest has no geoRAM record")
    record["path"] = str(normalized)
    record["packed_size"] = len(normalized.read_bytes()) - 2
    record["unpacked_size"] = len(georam_payload)
    metadata.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
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
