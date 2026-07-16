"""Stages segments for compression and builds fallback uncompressed PRG files.

Creates uncompressed basicv3.prg or prepares LZSS compressor configurations.
"""

import os
import shutil
import sys


def stage_segments(
    compile_bin_path: str,
    segments_dir: str,
    layout_path: str,
) -> None:
    """Stage the linked RAM payload and deterministic compressor layout.

    Args:
        compile_bin_path: Extracted linked RAM payload.
        segments_dir: Directory receiving ``compiler_main.bin``.
        layout_path: Compressor configuration output path.
    """
    if not os.path.exists(compile_bin_path):
        raise FileNotFoundError(f"Source binary not found: {compile_bin_path}")
    os.makedirs(segments_dir, exist_ok=True)
    os.makedirs(os.path.dirname(layout_path), exist_ok=True)
    staged_path = os.path.join(segments_dir, "compiler_main.bin")
    shutil.copyfile(compile_bin_path, staged_path)
    normalized_path = os.path.abspath(staged_path).replace("\\", "/")
    content = "\n".join(
        [
            "entry = $080D",
            "entry_mode = jmp",
            f"segment = compiler_main, bin, {normalized_path}, $080D",
            "",
        ]
    )
    with open(layout_path, "w", encoding="utf-8", newline="\n") as layout:
        layout.write(content)


def build_simple_prg(compile_bin_path: str, prg_output_path: str) -> None:
    """Prepends little-endian load address to binary payload to build C64 PRG.

    Args:
        compile_bin_path: Path to compile.bin.
        prg_output_path: Path to save the final basicv3.prg.
    """
    if not os.path.exists(compile_bin_path):
        raise FileNotFoundError(f"Source binary not found: {compile_bin_path}")

    with open(compile_bin_path, "rb") as f:
        data = f.read()

    # Load at $0801 with a one-line BASIC launcher:
    # 2026 SYS2061, followed by the machine-code payload at $080D.
    basic_loader = bytes(
        [
            0x0B,
            0x08,  # next BASIC line pointer ($080B end marker)
            0xEA,
            0x07,  # line number 2026
            0x9E,  # SYS token
            0x32,
            0x30,
            0x36,
            0x31,  # "2061"
            0x00,  # line terminator
            0x00,
            0x00,  # end of BASIC program
        ]
    )
    # extract_segments preserves the linked BASIC bootstrap.  Do not prepend a
    # second launcher in that production path; doing so creates a self-looping
    # BASIC program at RUN.  Standalone fixtures still receive the launcher.
    linked_bootstrap = bytes(data[:12]) == bytes(basic_loader)
    payload = data if linked_bootstrap else bytes(basic_loader) + data
    prg_data = bytearray([0x01, 0x08]) + bytearray(payload)

    os.makedirs(os.path.dirname(prg_output_path), exist_ok=True)
    with open(prg_output_path, "wb") as f:
        f.write(prg_data)


def main() -> None:
    """Main execution of the compressor staging tool."""
    if len(sys.argv) < 3:
        compile_bin_path = "build/compile.bin"
        prg_output_path = "build/basicv3.prg"
    else:
        compile_bin_path = sys.argv[1]
        prg_output_path = sys.argv[2]

    if not os.path.exists(compile_bin_path):
        print(f"Warning: compile.bin not found at {compile_bin_path}. Skipping.")
        return

    build_simple_prg(compile_bin_path, prg_output_path)
    build_dir = os.path.dirname(os.path.abspath(prg_output_path))
    stage_segments(
        compile_bin_path,
        os.path.join(build_dir, "segments"),
        os.path.join(build_dir, "compressor_layout.cfg"),
    )
    print("Fallback PRG built successfully.")


if __name__ == "__main__":
    main()
