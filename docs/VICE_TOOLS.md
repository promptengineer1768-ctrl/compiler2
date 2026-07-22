# VICE Next File Tools

## Tool Location

The project uses the VICE Next supervised runtime. Configure machine tools
explicitly. The Windows runtime verified on 2026-07-22 was extracted from
release `v3.10-instrumented-20260722-nmi.1` (archive SHA-256
`f8ab4106d6d86757a59eb34a73b7912ab311ba71badc28b45f4a999bfa1a0a38`):

```text
C:\Users\me\Downloads\vice-instrumentation-29898426510\windows-extracted\HeadlessVICE-3.10-win64-rnone
```

In PowerShell:

```powershell
$env:VICE_NEXT_RUNTIME = "C:\Users\me\Downloads\vice-instrumentation-29898426510\windows-extracted\HeadlessVICE-3.10-win64-rnone"
$env:VICE_X64SC = Join-Path $env:VICE_NEXT_RUNTIME "x64sc.exe"
$env:VICE_XPLUS4 = Join-Path $env:VICE_NEXT_RUNTIME "xplus4.exe"
```

## Generating Stock Semantic Fixtures

The shared VICE Next supervisor/client implementation is `tools/vice_harness.py`.
Generate the checked-in C64 BASIC V2 and Plus/4 BASIC 3.5 observations with:

```powershell
python tools/generate_vice_fixtures.py
python tools/generate_vice_fixtures.py --profile basicv2
python tools/generate_vice_fixtures.py --case basicv35-program-WHILE
# Keyword matrix (group priority order; missing stock oracles only):
python tools/generate_vice_fixtures.py --from-keyword-matrix --group group1 --missing-only
```

Product E2E against the matrix runs with:

```powershell
python -m pytest -n auto tests/e2e tests/hardware -v
```

Product E2E uses a build-fingerprinted warm snapshot under `debug/vice-warm/`.
On a cache miss, one worker performs the complete cold boot and verifies
`BASIC V3 READY` before atomically publishing the snapshot. Each worker restores
a private copy into its own supervised, ephemeral-port VICE instance, so the
remaining VICE tests can execute in parallel without sharing monitor ports or
mutable snapshot files. A changed `compiler.d64` creates a new snapshot key.

Group order is group1 → group2 → group3. Within a group, capture stock
oracles first, then product tests in immediate → program → compile order.

The harness starts an isolated supervised emulator for every case, tokenizes stock
BASIC source with an explicitly configured `petcat.exe`, autostarts the
resulting PRG, and records the VICE version and SHA-256 identities of the
available machine ROMs. C64 screen observations use `$0400`; Plus/4
observations use `$0C00`. PAL/NTSC selection is not a general test dimension;
use a named timing profile only for a test with an explicit timing requirement.

For stock BASIC semantic fixtures, prefer tokenized PRG autostart and wait for
the final stable `READY.` predicate. Preserve the fixture's profile, ROM
checksums, source, input sequence, raw screen, and normalization metadata.

Regeneration logs and emulator diagnostics are written under `debug/`.
Checked-in observations are written under `tests/fixtures/reference/`.

Temporary images, extracted files, listings, and diagnostic output belong
under `debug/`. Release D64 images are generated under `build/`.

## Creating a D64 Test Image

The project packager uses its deterministic direct D64 writer by default. Use
an external disk utility only when `VICE_C1541` is explicitly set to an
existing file; the instrumented runtime does not currently ship `c1541.exe`.

Create and format a fresh 35-track D64 image:

```powershell
& $env:VICE_C1541 `
  -format "COMPILER2 TESTS,00" d64 ".\debug\compiler2_tests.d64"
```

Write a host PRG into the image using an explicit Commodore disk filename:

```powershell
& $env:VICE_C1541 `
  -attach ".\debug\compiler2_tests.d64" `
  -write ".\build\basicv3.prg" "BASICV3"
```

Write each additional test program with a separate checked invocation:

```powershell
& $env:VICE_C1541 `
  -attach ".\debug\compiler2_tests.d64" `
  -write ".\debug\graphics_test.prg" "GFXTEST"
```

The host `.prg` suffix is not part of the Commodore filename. Disk filenames
are at most 16 PETSCII characters; use stable uppercase names without relying
on the host filename. A raw PRG contains a two-byte little-endian load address
followed by its payload.

List and validate the resulting directory:

```powershell
& $env:VICE_C1541 `
  -attach ".\debug\compiler2_tests.d64" `
  -list
```

Tests should run `c1541` through `subprocess.run(..., check=True)` and assert
the quoted disk filenames and file types in the listing. A D64 helper must fail
on a nonzero exit status and must not silently reuse a stale image.

## Listing Tokenized BASIC with PETCAT

List a tokenized C64 BASIC V2 PRG on standard output:

```powershell
& $env:VICE_PETCAT -2 -- ".\debug\program.prg"
```

Write the detokenized listing to a text file:

```powershell
& $env:VICE_PETCAT -2 -o ".\debug\program.bas" -- `
  ".\debug\program.prg"
```

Use BASIC 3.5 keyword decoding for a stock Plus/4 program:

```powershell
& $env:VICE_PETCAT -3 -- ".\debug\plus4_program.prg"
```

The `--` terminates PETCAT options. Use `-2` for stock C64 BASIC V2 and `-3`
for stock BASIC V3.5. PETCAT is an independent check for stock token streams;
it does not know Compiler 2's versioned extended-token encoding. Extended
programs must be listed with the project's own tested detokenizer.

PETCAT can also create a stock tokenized fixture from an ASCII listing:

```powershell
& $env:VICE_PETCAT -w2 -o ".\debug\program.prg" -- `
  ".\debug\program.bas"
```

Use `-w3` for BASIC 3.5. Tokenized fixtures used as semantic or binary
references must still record their machine, dialect, PETCAT/VICE version, and
source provenance.

PETCAT tokenization expects BASIC program text to be lowercase outside quoted
strings. Uppercase ASCII keywords can be interpreted as PETSCII/control-token
names and produce invalid or surprising token streams. Fixture generators
should lowercase only the unquoted BASIC text and preserve string literals
exactly.
