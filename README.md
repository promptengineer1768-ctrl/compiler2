# Compiler 2

A native 6502 compiler and interactive BASIC environment for the Commodore 64 with dual expansion-memory support (geoRAM and REU).

## Overview

Compiler 2 is a **new** implementation (not backward-compatible with the earlier compiler) that provides:

- Interactive BASIC V2 environment with direct commands and numbered program lines
- Native 6502 compilation of stored BASIC programs
- Execute-in-place (XIP) compiled code from expansion memory
- Large dynamic arenas for programs, variables, arrays, strings, and compiler data
- Dual-device expansion support: **geoRAM** (preferred) or **Commodore REU** (512 KiB minimum)
- Stock-compatible LOAD/SAVE of tokenized BASIC programs
- Documented executable format for compiled C64 programs

## Key Features

### Dual Expansion Support
- Automatically detects geoRAM and/or REU at startup
- Prefers geoRAM when both devices are present (more efficient XIP)
- Uses REU when it's the only valid device
- Fails cleanly if no supported expansion device is found

### Architecture
- **Resident foreground**: IRQ handling, editor, KERNAL bridge, expansion call gate
- **Expansion-native services**: Compiler, diagnostics, cold data (loaded as 256-byte XIP pages)
- **Compiled runtime**: Documented ABI for user programs
- **Arena manager**: Typed generation handles for dynamic storage

### Memory Model
- Minimizes permanently resident normal-RAM code
- Maximizes dynamic storage in expansion memory
- geoRAM-canonical implementation: REU path DMA-copies pages into XIP buffer

## Documentation

| Document | Description |
|----------|-------------|
| [`REQUIREMENTS.md`](REQUIREMENTS.md) | Product requirements and acceptance criteria |
| [`REU_REQUIREMENTS.md`](REU_REQUIREMENTS.md) | Dual-device expansion and REU-specific requirements |
| [`DESIGN2.md`](DESIGN2.md) | Top-level design index |
| [`REU_DESIGN.md`](REU_DESIGN.md) | Dual-device and REU detailed design |
| [`docs/`](docs/) | Focused subsystem design documents |
| [`AGENTS.md`](AGENTS.md) | Development guidelines and agent instructions |

### Key Design Documents
- [`COMPILER_ARCHITECTURE.md`](docs/COMPILER_ARCHITECTURE.md) — Layer map and runtime ABI
- [`GEORAM_BANKING.md`](docs/GEORAM_BANKING.md) — geoRAM hardware contract
- [`ZERO_PAGE.md`](docs/ZERO_PAGE.md) — Zero-page allocation manifest
- [`KERNAL_ABI.md`](docs/KERNAL_ABI.md) — KERNAL bridge contract
- [`BASIC_COMPATIBILITY_LIMITS.md`](docs/BASIC_COMPATIBILITY_LIMITS.md) — Stock edge limits
- [`BUILD.md`](docs/BUILD.md) — Toolchain and build instructions
- [`TESTING.md`](docs/TESTING.md) — Test hierarchy and fixtures

## Build Requirements

### 6502 Toolchain
- **ca65** assembler (version 2.19+ baseline)
- **ld65** linker
- Located at: `C:\Users\me\Documents\Coding Projects\tools\`

### Python
- **Python 3.13** required (uses features not available in earlier versions)
- Host tools for code generation and validation

### Emulator Testing
- **VICE Next** with instrumented binaries
- `x64sc.exe` for C64 (BASIC V2)
- `xplus4.exe` for Plus/4 (BASIC V3.5 reference)

## Building

```powershell
# Canonical build entry point
powershell -ExecutionPolicy Bypass -File .\build.ps1

# With custom configuration
.\build.ps1 -BuildDir "custom_build" -Config Release
```

The build produces:
- `basicv3.prg` — Common loader and RAM payload
- `georam.bin` — GeoRAM-canonical expansion image
- REU patch object — Delta for REU installation
- D64 disk image — Installable artifact

See [`docs/BUILD.md`](docs/BUILD.md) for complete build documentation.

## Project Structure

```
compiler2/
├── src/                    # Assembly source code
│   ├── arena/             # Arena management
│   ├── common/            # Constants, macros, zero-page
│   ├── geoasm/            # Compiler pipeline
│   ├── loader/            # Expansion loaders
│   ├── resident/          # Resident foreground code
│   ├── runtime/           # Compiled program runtime
│   └── standalone/        # Exported program support
├── tests/                  # Test suites
│   ├── e2e/               # End-to-end tests
│   ├── hardware/          # Hardware interaction tests
│   └── unit/              # Unit tests
├── tools/                  # Python build and validation tools
├── docs/                   # Design documentation
├── manifests/              # Structured metadata
├── build.ps1               # Build script
├── REQUIREMENTS.md         # Product requirements
├── DESIGN2.md              # Design index
└── AGENTS.md               # Development guidelines
```

## Testing

```powershell
# Run all tests
python -m pytest tests/ -v

# Run smoke tests only
python -m pytest tests/ -m smoke

# Run VICE-backed E2E/hardware tests
python -m pytest tests/e2e tests/hardware -v
```

Test categories:
- **Unit tests**: Direct coverage of callable assembly routines
- **Integration tests**: Multi-routine public calls
- **Functional tests**: Complete user-visible features
- **System contract tests**: Toolchain, linker, memory-map invariants
- **E2E tests**: Authoritative language behavior via VICE

## License

[License information if applicable]

## References

- Stock BASIC V2 and KERNAL: `C:\Users\me\Documents\Coding Projects\c64rom`
- Earlier compiler (implementation aid only): `C:\Users\me\Documents\Coding Projects\compiler`

## Status

Compiler 2 is under active development. See [`TASKS.md`](TASKS.md) and [`REU_TASKS.md`](REU_TASKS.md) for implementation progress.
