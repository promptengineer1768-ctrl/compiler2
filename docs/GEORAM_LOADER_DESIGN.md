# GeoRAM Loader Design

## Loader Shape

The build produces two disk files:

- `BASICV3`: the BASIC-loadable PRG containing the loader and RAM payload.
- `GEORAM`: the compressed geoRAM page image loaded by the installer.

The geoRAM compiler build keeps code that must be RAM-visible in the PRG, moves
compiler/backend routines to `GEORAM`, and reserves zero-filled compiler
workspace in no-load `COMPILER_BSS`.

## Compressor Integration

The build uses the 6502 LZSS compressor project at
`C:\Users\me\Documents\Coding Projects\compressor` to compress the GEORAM
installation file. The compressor produces a CGS1 sidecar that can be streamed
directly into geoRAM during installation.

### Compressor Toolchain

Required tools from the compressor project:

```text
C:\Users\me\Documents\Coding Projects\compressor\build\lzss_compressor.exe
C:\Users\me\Documents\Coding Projects\compressor\build\lzss_unpacker.exe
```

### CGS1 Sidecar Format

The compressed GEORAM file uses the CGS1 (Compressed GeoRAM Stream V1) format:

- 4-byte signature: `CGS1`
- 2-byte version
- 2-byte chunk count
- 4-byte required device size (KiB)
- 2-byte page size
- 1-byte algorithm ID
- 1-byte reserved
- 4-byte total unpacked size
- 4-byte total unpacked CRC32
- 4-byte packed file size
- For each chunk:
  - 1-byte block selector
  - 1-byte page selector (low 6 bits)
  - 1-byte page high bits
  - 4-byte logical start address
  - 4-byte unpacked size
  - 4-byte packed size
  - 4-byte packed CRC32
  - 4-byte unpacked CRC32
  - Compressed LZSS stream data

### GeoRAM Stream Reader

The compressor project includes `src/6502/decompressor/georam_stream_reader.asm`,
a standalone 6502 decompressor that:

1. Opens the CGS1 sidecar file using KERNAL file I/O
2. Reads and validates the CGS1 header
3. Iterates through each chunk
4. Decompresses each chunk directly through the `$DE00-$DEFF` geoRAM window
5. Writes `$DFFE` (page) and `$DFFF` (block) registers as needed

The decompressor never stages the compressed file in RAM - it streams
directly from disk to geoRAM, minimizing memory usage.

## Build Modes

Uncompressed:

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1 -GeoramCompiler
```

Compressed:

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1 -GeoramCompiler -UseCompressor
```

The compressed path packs `build/compile.bin`, the extracted RAM payload, rather
than the full linker output. This avoids the compressor staging failure that
occurs when `compiler.bin` contains unrelated linker ranges and geoRAM output
areas.

Legacy measured output, retained only as sizing guidance until Compiler 2 has
its own build artifacts:

| Artifact | Size |
| --- | ---: |
| `build/compile.bin` | 28,402 bytes |
| uncompressed `BASICV3` PRG | 28,414 bytes |
| compressed `BASICV3` PRG | 20,683 bytes |
| `build/georam.bin` | 29,952 bytes |

## Install Flow

1. BASIC loads and starts `BASICV3`.
2. The loader detects geoRAM.
3. RAM payload is installed/decompressed to its runtime locations.
4. The loader loads `GEORAM` from disk and copies pages into geoRAM.
5. ROM/I/O banking is restored to the expected runtime state.
6. Control jumps to `compiler_init`.

KERNAL disk calls require KERNAL ROM visible. geoRAM access requires I/O visible.
Writes to RAM under I/O must happen with interrupts disabled while I/O is banked
out.

## Compression Strategy

### RAM Payload Compression

`tools/extract_segments.py` writes only file-backed RAM segments into
`build/compile.bin`; `COMPILER_BSS` is skipped. `tools/prepare_compressor_segments.py`
then creates `segments/compiler_main.bin` from that smaller payload and writes
`build/compressor_layout.cfg`.

`lzss_compressor.exe --pack --cfg build/compressor_layout.cfg` produces
`build/compile_compressed.prg`. If the compressor fails, `build.ps1` falls back
to the simple PRG builder.

### GeoRAM Image Compression

The geoRAM image is compressed using the compressor's `georam_stream` segment
type. The build invokes:

```powershell
& "C:\Users\me\Documents\Coding Projects\compressor\build\lzss_compressor.exe" `
  --pack `
  --cfg build/georam_stream.cfg `
  -o build/GEORAM_compressed.prg
```

The compressor configuration `build/georam_stream.cfg` specifies:

```ini
entry = $0801
entry_mode = jmp

segment = georam, georam_stream, build/georam.bin, 0, 0, 512, 256, GEORAM
```

This produces:
- `build/GEORAM_compressed.prg`: the compressed GEORAM sidecar
- `build/GEORAM_compressed.json`: JSON metadata for the sidecar

The compressed sidecar is verified with:

```powershell
& "C:\Users\me\Documents\Coding Projects\compressor\build\lzss_unpacker.exe" `
  --decompress-sidecar GEORAM build/georam_check --bin
```

### Loader Integration

The loader includes `georam_stream_reader.asm` from the compressor project:

```asm
GEORAM_STREAM_ORIGIN = INSTALL_LOADER + loader_size
GEORAM_STREAM_ZP = zp_loader_start
.include "georam_stream_reader.asm"
```

During installation:
1. BASIC loads and starts `BASICV3`
2. The loader detects geoRAM
3. RAM payload is installed/decompressed to its runtime locations
4. The loader calls `georam_stream_load` with the GEORAM filename
5. The stream reader opens the CGS1 sidecar and decompresses directly to geoRAM
6. ROM/I/O banking is restored to the expected runtime state
7. Control jumps to `compiler_init`

## Guardrails

- Pack `compile.bin`, not `compiler.bin`, when `-UseCompressor` is set.
- Keep no-load workspace in `COMPILER_BSS` and clear it from `compiler_init`.
- Use `georam_stream` segment type for GEORAM compression, not standard PRG packing.
- Verify the compressed GEORAM sidecar before packaging into D64.
- Fall back to an uncompressed PRG if the compressor cannot solve staging.
- The `georam_stream_reader.asm` must fit within the loader budget.
- The decompressor ZP usage must not conflict with other loader ZP allocations.

## Verification

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1 -GeoramCompiler -UseCompressor
pytest tests\ -v -m "static or georam"
```

### Compressed GEORAM Verification

1. Verify the compressed sidecar is valid:
```powershell
& "C:\Users\me\Documents\Coding Projects\compressor\build\lzss_unpacker.exe" `
  --decompress-sidecar GEORAM build/georam_check --bin
```

2. Compare decompressed output with original:
```powershell
fc /b build\georam.bin build\georam_check\georam.bin
```

3. Verify the D64 contains the compressed GEORAM file:
```powershell
& "C:\Users\me\Documents\Coding Projects\tools\vice-mcp\dist\HeadlessVICE-windows-x86_64\c1541.exe" `
  -attach build\compiler.d64 -list
```

### Loader Size Budget

The loader must fit within the `INSTALL_LOADER` segment budget. The
`georam_stream_reader.asm` adds approximately 300 bytes to the loader.
Verify the total loader size after including the decompressor:

```powershell
# Check loader size in the linker map
Select-String -Path build\compiler.map -Pattern "INSTALL_LOADER"
```
