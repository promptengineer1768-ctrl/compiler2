# Build Design

## Required Toolchain

Compiler 2 uses the cc65 toolchain:

```text
C:\Users\me\Documents\Coding Projects\tools\ca65.exe
C:\Users\me\Documents\Coding Projects\tools\ld65.exe
```

`ca65` is the only production 6502 assembler. `ld65` is the production linker.
The current known baseline is version 2.19. The build records the actual
version strings and treats a toolchain change as a reproducibility change.

### Compressor Toolchain

For compressed builds, the 6502 LZSS compressor is required:

```text
C:\Users\me\Documents\Coding Projects\compressor\build\lzss_compressor.exe
C:\Users\me\Documents\Coding Projects\compressor\build\lzss_unpacker.exe
```

The compressor provides:
- RAM payload compression for smaller PRG files
- GeoRAM image compression using `georam_stream` segment type
- CGS1 sidecar generation for direct-to-geoRAM streaming

The compressor version is recorded in `build_manifest.json` alongside the
cc65 toolchain versions.

VICE packaging and reference tools are installed under:

```text
C:\Users\me\Documents\Coding Projects\tools\vice-mcp\dist\HeadlessVICE-windows-x86_64
```

Important programs include `c1541.exe`, `x64sc.exe`, and `xplus4.exe`.
`petcat.exe` is used to inspect stock tokenized BASIC programs. Exact D64 and
PETCAT command recipes are in `docs/VICE_TOOLS.md`.

Python host tools use the configured Python installation documented in
`AGENTS.md`. Host tools may generate and validate artifacts, but all C64
production code is ca65 assembly.

## Canonical Entry Point

The project build entry point shall be:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The script accepts an overridable tools root, build directory, and
debug/release configuration. Defaults use the shared tools directory above and
the project-local `build/` directory.

Every external command runs through one checked invocation helper. A nonzero
generator, ca65, ld65, validator, packager, or system-test result fails the
build. Production builds must not continue with a copied stale binary or a
best-effort fallback.

## Inputs

Checked-in inputs include:

- assembly translation units under `src/`;
- include files and ABI declarations under `src/`;
- the fixed linker-policy source;
- structured routine, arena, zero-page, and format manifests;
- generated-reference schemas from `docs/GENERATED_REFERENCE.md`;
- host generators and validators under `tools/`;
- canonical test/reference schemas.

Generated assembly, includes, linker configuration, objects, listings, maps,
labels, and binary images live under `build/`. Generated files are not written
back into `src/`.

## Build Order

The required order is:

1. Validate tool paths and record ca65, ld65, Python, and packaging-tool
   versions.
2. Validate structured source manifests and schema versions.
3. Generate zero-page symbols and interference reports.
4. Generate routine IDs, geoRAM placement, indexed call directories, arena
   constants, runtime ABI tables, test-entry exports, the
   first-character-indexed keyword trie, and `keyword_lookup_report.json`.
5. Generate the final ld65 configuration from the checked-in linker policy and
   generated geoRAM/page inventory.
6. Assemble each normal-RAM and geoRAM translation unit with ca65, producing an
   object and listing for each unit.
7. Link all objects with ld65, producing the RAM image, geoRAM image, map, and
   label file.
8. Validate all cross-artifact contracts before packaging.
9. Construct the installable PRG, loader manifest, and optional D64 image.
10. Compute size/resource reports.
11. Generate and validate `API.md` and `MAP.md`, then compute the final build
    fingerprint and `build_manifest.json`, including both document checksums.
12. Run system contract tests, then the configured smoke/full test selection.

A generator input change must cause all dependent outputs to rebuild. A clean
build and an incremental no-change build must produce identical final bytes.

## ca65 Rules

The build invokes ca65 separately for each translation unit. Common options
include:

- output object path under `build/obj/`;
- listing path under `build/listings/`;
- include roots for `src/` and `build/generated/`;
- explicit debug/release feature defines;
- dependency output where supported.

Assembly must use ca65 syntax, segments, scopes, imports/exports, assertions,
and conditional assembly. Public and test-only exports are generated from
manifests rather than reconstructed from listing text when ca65 can provide the
information directly.

Warnings and assembler assertions are build failures. No object from a previous
failed build may be linked.

## ld65 Rules

The checked-in linker policy owns invariant CPU requirements, including:

- canonical RAM/I/O/ROM banking assumptions;
- pinned runtime and IRQ/NMI placement;
- RAM-under-I/O ownership;
- high-memory reservation at `$FFF9-$FFFF`, including hardware vectors;
- segment alignment and maximum sizes.

The generated linker configuration adds the current native geoRAM page
inventory and generated segments. `ld65` emits:

- linked RAM binary;
- ordered geoRAM binary;
- complete map;
- VICE/monitor label file;
- exported-symbol data needed by the runtime/test manifest.

The linker must fail on overlap, overflow, missing segments, unresolved
symbols, or vector misplacement. Post-link validators compare the map, labels,
binary lengths, placement manifests, and embedded headers.

## Required Artifacts

The build directory contains at least:

```text
build/
  obj/
  listings/
  generated/
  compiler.bin
  georam.bin
  GEORAM_compressed.prg        # compressed GEORAM sidecar (when -UseCompressor)
  GEORAM_compressed.json       # sidecar metadata (when -UseCompressor)
  basicv3.prg
  compiler.map
  compiler.lbl
  compiler.d64
  build_manifest.json
  loader_manifest.json
  routine_directory.json
  arena_layout.json
  runtime_abi.json
  production_entries.json
  test_entries.json
  zp_allocation.json
  size_report.json
  keyword_lookup_report.json
  API.md
  MAP.md
  requirements_matrix.json
  requirements_matrix.md
```

`API.md` and `MAP.md` are generated on every build, including narrowly selected
developer builds. `compiler.d64` is required for release and VICE installation
tests but may be omitted from a narrowly selected developer build. The manifest
records every produced artifact's size and checksum.

## Generated API and Memory Map

`tools/generate_reference.py` runs only after the linker outputs, routine/ABI
directories, zero-page allocation, arena layout, and size report agree. It
generates:

- `build/API.md`, a table-formatted production entry reference with the default
  calling convention and exact per-entry inputs, outputs, errors/flags,
  clobbers/preservation, zero-page sets, stack/return kind, banking/IRQ
  behavior, side effects, address or geoRAM placement, and availability;
- `build/MAP.md`, a table-formatted CPU, segment, dynamic/free, standalone,
  zero-page, geoRAM, arena, hardware, graphics, guard, and vector map.

The generator consumes structured JSON plus linker map/label output. It must
not infer the API by scraping assembly comments or hand-written documentation.
The exact columns, sorting, profile sections, and validation rules are defined
in `GENERATED_REFERENCE.md`.

Both documents are deterministic. They contain no timestamp, host-specific
path, final build fingerprint, or self-checksum. This avoids a hash cycle:
`build_manifest.json` is produced afterward and records their checksums.

## Packaging

The installable PRG contains the BASIC loader and normal-RAM installation
payload required to establish the canonical runtime. The geoRAM image is a
separate ordered page image. A D64 release image contains stable, documented
filenames for the loader/runtime and geoRAM data.

The release D64 must store `basicv3.prg` with the Commodore filename
`BASICV3` and `georam.bin` with the Commodore filename `GEORAM`.

When `-UseCompressor` is set, the D64 stores the compressed GEORAM sidecar
as `GEORAM` instead of the raw `georam.bin`. The compressed sidecar is verified
before packaging.

Packaging must validate:

- PRG load address and loader record;
- payload destination ranges;
- no load-time write through visible I/O or ROM;
- geoRAM page order, padding, and checksums;
- D64 directory filenames and file types;
- agreement with `loader_manifest.json`.

Compression may be added only behind a versioned format and round-trip
verification. The uncompressed linked images remain authoritative for maps,
symbols, and debugging.

## Reproducibility and Cleaning

`build/` contains generated artifacts and is safe to remove. `debug/` contains
diagnostic captures and is not an input to release builds.

The build fingerprint covers:

- all checked-in source inputs;
- generated schema versions;
- ca65/ld65 and host-tool versions;
- build configuration;
- final artifact checksums.

The generated references are final artifacts covered by the manifest. A clean
build and an incremental no-change build must produce byte-identical
`API.md`/`MAP.md`.

VICE startup snapshots and stock-reference fixtures record the applicable
fingerprint. Stale snapshots cannot be reused after a relevant build change.

## Build Verification

System contract tests validate:

- tool versions and checked command construction;
- deterministic generation and clean/incremental equivalence;
- linker MEMORY/SEGMENT contracts and reserved vectors;
- canonical banking assumptions;
- map/listing/label/manifest consistency;
- routine-directory and geoRAM image consistency;
- keyword trie structure, dialect/abbreviation acceptance, bounded lookup
  report, and tokenizer timing;
- `API.md` production-entry completeness and calling-convention consistency;
- `MAP.md` ordering, non-overlap, totals, free extents, and agreement with
  linker/ZP/arena/size artifacts;
- PRG, compiled-image, and D64 formats;
- resident, stack, arena, standalone-code, performance, and geoRAM capacity
  budgets;
- requirements traceability, including EARS records and requirement-to-test
  coverage;
- absence of stale or undeclared generated files;
- compressed GEORAM sidecar integrity and round-trip verification;
- loader size budget including `georam_stream_reader.asm`.

Build success means these contracts pass. Producing `basicv3.prg` alone is not
sufficient.
