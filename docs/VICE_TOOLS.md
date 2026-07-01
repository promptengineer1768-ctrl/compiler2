# VICE File Tools

## Tool Location

The project uses the VICE command-line tools installed at:

```text
C:\Users\me\Documents\Coding Projects\tools\vice-mcp\dist\HeadlessVICE-windows-x86_64
```

In PowerShell:

```powershell
$ViceTools = "C:\Users\me\Documents\Coding Projects\tools\vice-mcp\dist\HeadlessVICE-windows-x86_64"
```

Temporary images, extracted files, listings, and diagnostic output belong
under `debug/`. Release D64 images are generated under `build/`.

## Creating a D64 Test Image with c1541

Create and format a fresh 35-track D64 image:

```powershell
& "$ViceTools\c1541.exe" `
  -format "COMPILER2 TESTS,00" d64 ".\debug\compiler2_tests.d64"
```

Write a host PRG into the image using an explicit Commodore disk filename:

```powershell
& "$ViceTools\c1541.exe" `
  -attach ".\debug\compiler2_tests.d64" `
  -write ".\build\basicv3.prg" "BASICV3"
```

Write each additional test program with a separate checked invocation:

```powershell
& "$ViceTools\c1541.exe" `
  -attach ".\debug\compiler2_tests.d64" `
  -write ".\debug\graphics_test.prg" "GFXTEST"
```

The host `.prg` suffix is not part of the Commodore filename. Disk filenames
are at most 16 PETSCII characters; use stable uppercase names without relying
on the host filename. A raw PRG contains a two-byte little-endian load address
followed by its payload.

List and validate the resulting directory:

```powershell
& "$ViceTools\c1541.exe" `
  -attach ".\debug\compiler2_tests.d64" `
  -list
```

Tests should run `c1541` through `subprocess.run(..., check=True)` and assert
the quoted disk filenames and file types in the listing. A D64 helper must fail
on a nonzero exit status and must not silently reuse a stale image.

## Listing Tokenized BASIC with PETCAT

List a tokenized C64 BASIC V2 PRG on standard output:

```powershell
& "$ViceTools\petcat.exe" -2 -- ".\debug\program.prg"
```

Write the detokenized listing to a text file:

```powershell
& "$ViceTools\petcat.exe" -2 -o ".\debug\program.bas" -- `
  ".\debug\program.prg"
```

Use BASIC 3.5 keyword decoding for a stock Plus/4 program:

```powershell
& "$ViceTools\petcat.exe" -3 -- ".\debug\plus4_program.prg"
```

The `--` terminates PETCAT options. Use `-2` for stock C64 BASIC V2 and `-3`
for stock BASIC V3.5. PETCAT is an independent check for stock token streams;
it does not know Compiler 2's versioned extended-token encoding. Extended
programs must be listed with the project's own tested detokenizer.

PETCAT can also create a stock tokenized fixture from an ASCII listing:

```powershell
& "$ViceTools\petcat.exe" -w2 -o ".\debug\program.prg" -- `
  ".\debug\program.bas"
```

Use `-w3` for BASIC 3.5. Tokenized fixtures used as semantic or binary
references must still record their machine, dialect, PETCAT/VICE version, and
source provenance.
