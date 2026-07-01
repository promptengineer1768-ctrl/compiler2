# Compiler 2 Architecture

This document is the high-level architecture map for Compiler 2. It summarizes
the load-bearing design decisions and points to the normative documents that
own the details. `../REQUIREMENTS.md` remains the compatibility authority,
`../DESIGN2.md` is the main design authority, and `../SKELETON.md` maps each
responsibility to source files, manifests, generated artifacts, and tests.

Compiler 2 is a fresh design of the legacy compiler. Legacy code, tests, and
documents may be used as evidence or porting material, especially for proven
math routines, but Compiler 2's manifests, generated memory map, ABI, and test
contracts are authoritative.

## Architectural Principles

- Keep stock Commodore BASIC V2 behavior compatible unless an extension is
  explicitly enabled.
- Compile every executable BASIC path through one compiler pipeline: stored
  programs, immediate commands, and per-line compile-on-entry use the same
  machinery.
- Keep resident normal-RAM code small, pinned, and hardware-facing; move cold
  compiler/editor/math services to geoRAM by default.
- Use generated contracts for addresses, routine IDs, ABI records, zero-page
  allocation, geoRAM placement, command tables, and traceability.
- Make every important boundary inspectable, replayable, and testable.
- Fail before publishing partially valid state: source edits, compiled code,
  exports, and generated artifacts publish atomically.

## Runtime Layers

Compiler 2 is organized into five practical layers.

| Layer | Location | Responsibility |
|---|---|---|
| Common | `src/common/` | Constants, macros, and generated zero-page include plumbing |
| Resident | `src/resident/`, `src/loader/` | IRQ, screen front end, KERNAL bridge, geoRAM gate, RAM-under-I/O gate, loader, fatal path |
| geoRAM services | `src/geoasm/` | Editor service, tokenizer, parser, semantic checks, compiler pipeline, optimizer, codegen, diagnostics, slow math |
| Runtime ABI | `src/runtime/` | Compiled-program helpers for variables, arrays, strings, math, control flow, I/O, errors, inspection, graphics |
| Arena/overlay | `src/arena/` | geoRAM detection, page allocation, typed arenas, overlay dispatch, nested call context |

Resident code is the trusted hardware-facing core. It owns IRQ/NMI reachability,
KERNAL banking, visible I/O access, geoRAM selection entry points, and clean
failure paths. geoRAM code is larger and colder; it must enter through
generated gate records and must not assume a stable physical page outside its
declared call.

## Memory Model

The canonical runtime CPU mapping is `$35`: RAM at `$A000-$BFFF` and
`$E000-$FFFF`, visible I/O at `$D000-$DFFF`, and KERNAL/BASIC ROM hidden. Two
bounded exceptions exist:

- the KERNAL bridge temporarily selects the ROM/I/O map required for approved
  KERNAL calls;
- the RAM-under-I/O gate temporarily exposes RAM under `$D000-$DFFF` for
  graphics-owned memory.

Zero page is generated, not hand assigned. `manifests/zero_page.json` describes
live ranges, fixed reservations, aliases, and KERNAL/IRQ domains.
`tools/zp_alloc.py` builds the interference graph and emits
`build/zp_symbols.inc`, reports, and validation artifacts. Assembly imports
symbols from the generated include rather than using literal project ZP
addresses.

Exact normal-RAM and geoRAM ranges are generated from linker policy and
manifests. `build/MAP.md` is the current-build memory reference; prose docs
describe policies, not final addresses.

## geoRAM Architecture

geoRAM provides a 256-byte window at `$DE00-$DEFF` and selection registers at
`$DFFE`/`$DFFF`. Selecting geoRAM does not change CPU-port banking. Compiler 2
requires a supported profile of at least 512 KiB and treats the installed
capacity/fingerprint as immutable for the session.

Only the pinned geoRAM gate and approved diagnostics write the selection
registers. The gate maintains a software mirror, saves caller selection and
context, resolves generated routine-directory records, calls or tail-transfers
to the target, and restores the caller page before returning. IRQ/NMI handlers
never select geoRAM.

Every geoRAM-native routine has a generated routine ID, ABI record, page,
entry offset, checksum, return kind, and call-graph edge. Routines fit within
one selected page and do not fall through across `$DEFF`; larger behavior is
split at explicit call boundaries.

## Compiler Pipeline

Compilation has eight explicit boundaries:

1. canonical tokenized source;
2. lexical and statement records;
3. symbols and variable descriptors;
4. control-flow and loop descriptors;
5. typed IR;
6. optimized IR;
7. emitted code, relocations, and runtime dependencies;
8. installed compiled image.

Each boundary has a versioned serialization suitable for host replay tests.
The same pipeline handles stored `RUN`, immediate executable commands wrapped
as temporary programs, and per-line compile-on-entry. There is no interpreter
fallback for dirty code: executable compiled records must match the current
source generation, options, ABI version, dialect, numeric mode, and dependency
fingerprints.

Tokenization uses a generated first-character-indexed trie with token ID,
dialect mask, abbreviation, and longest-match metadata at accepting nodes. The
compiler records lookup size and timing in `keyword_lookup_report.json` so a
linear-scan regression is visible.

## Publication and Editing

Line entry is transactional. The editor captures a line, tokenizes and
validates it in scratch storage, compiles it into scratch records, updates
dependency fingerprints, resolves layout, and publishes source plus compiled
records together. Failure leaves the previously published source and compiled
cache intact.

Program load/save uses canonical stock BASIC V2 linked-line format at external
boundaries. Extended-token programs use a versioned envelope that cannot be
mistaken for stock linked lines. Loading validates into scratch storage before
replacing the current program directory.

## Runtime ABI and Standalone Export

Compiled code calls only the documented runtime ABI. It never depends on
private compiler workspace addresses, editor state, or physical geoRAM
placement. The ABI covers variables, arrays, strings, math, control flow,
screen/keyboard/file I/O, errors, STOP/CONT, graphics, and inspection.

`COMPILE` emits a stock-loadable PRG with a BASIC V2 loader line, native code,
required runtime helpers, relocation/version metadata, variable descriptors,
and the source-free standalone direct environment. A standalone export must
run on a stock C64 without geoRAM. A compiled image accepted in the installed
geoRAM-backed environment is not valid unless the same bytes fit the standalone
budget and pass export system tests.

## Numeric Architecture

Resident `math_core.asm` owns fast compiled arithmetic used by hot paths.
Slower trigonometric, transcendental, and IEEE extension routines are
geoRAM-resident by default.

The legacy project's trig, transcendental, and IEEE algorithms/source are the
preferred starting point where they fit Compiler 2 contracts. Their
calculations were already proven through Python proxies and validated for
accuracy. Their memory map, fixed addresses, and zero-page layout are not
binding; ported code must use Compiler 2 generated ZP symbols, manifests,
geoRAM placement, and ABI.

IEEE mode changes arithmetic/classification behavior while keeping the stock
BASIC-compatible internal numeric layout and legacy-compatible formatting.
Core arithmetic is exactly rounded to the Compiler 2 destination format;
transcendentals target the documented 2 ULP accuracy bound.

## Build and Generated Contracts

The canonical build entry point is `build.ps1`. Production assembly uses
`ca65` and `ld65`; Python tools generate inputs, validate outputs, and render
current-build references.

Build order is contract-first:

1. validate tool paths, versions, and manifests;
2. generate zero-page symbols, interference reports, routine IDs, geoRAM
   placement, runtime ABI, arena layout, command tables, test entries, and
   keyword trie reports;
3. generate the ld65 configuration from checked-in linker policy plus generated
   placement data;
4. assemble and link;
5. validate maps, labels, manifests, binaries, budgets, and stale generated
   files;
6. package PRG/geoRAM/D64 artifacts;
7. generate `build/API.md`, `build/MAP.md`, and traceability matrices;
8. run system contracts and the selected test suite.

`build/` is generated and safe to delete. `debug/` holds temporary captures and
is never a release input.

## Testing Architecture

Tests are layered by scope and environment:

- host tool, format, static, and generated-artifact tests;
- local 6502 emulator unit tests for callable assembly entries;
- local emulator integration tests with geoRAM;
- VICE snapshot-backed application tests;
- focused VICE hardware tests for keyboard, IRQ, timers, banking, and devices.

Every callable assembly routine appears in the production entry manifest or
test-entry manifest and has direct unit coverage. System contract tests verify
whole-build invariants such as toolchain versions, deterministic generation,
linker/memory maps, banking policy, generated metadata, binary artifacts,
resource budgets, test environment assumptions, and traceability.

E2E language tests are organized by profile (`basicv2`, `basicv3`,
`basicv35`, `ieee`), by functions versus statements, and by shared execution
modes (`immediate`, `program`, `compile`). Stock BASIC behavior comes from
versioned VICE fixtures; Compiler 2-only IEEE behavior uses the specification
and an independent IEEE oracle.

## Ownership Map

| Concern | Primary documents |
|---|---|
| Requirements and compatibility | `../REQUIREMENTS.md` |
| Detailed architecture | `../DESIGN2.md`, this document |
| Source/module skeleton | `../SKELETON.md` |
| Build and artifacts | `BUILD.md`, `GENERATED_REFERENCE.md` |
| geoRAM banking and loader | `GEORAM_BANKING.md`, `GEORAM_LOADER_DESIGN.md` |
| Memory and zero page | `MEMORY_BUDGETS.md`, `ZERO_PAGE.md` |
| KERNAL/IRQ banking | `KERNAL_ABI.md` |
| Compiler pipeline | `INCREMENTAL_COMPILATION.md`, `LOOP_OPTIMIZATION.md` |
| Standalone export | `COMPILE_EXPORT.md` |
| Testing and traceability | `TESTING.md`, `TRACEABILITY.md`, `../TESTS.md` |
| Implementation order | `../TASKS.md` |

