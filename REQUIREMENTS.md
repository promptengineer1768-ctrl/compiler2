# Compiler 2 Requirements

## 1. Status and Priority

This document defines required externally visible behavior and engineering
acceptance criteria. Dual-device expansion detail is specified in
`REU_REQUIREMENTS.md`. `DESIGN2.md`, `REU_DESIGN.md`, and
`docs/COMPILER_ARCHITECTURE.md` describe the architecture that satisfies these
requirements. If design documents and this file disagree on common product
behavior, this document wins; if they disagree on dual-device expansion
detection, REU hardware, or dual packaging, `REU_REQUIREMENTS.md` wins.

Requirements use these terms:

- **must**: required for acceptance
- **should**: expected unless a measured reason is documented
- **may**: optional

Correctness has priority over size and speed. After correctness, optimization
is lexicographic:

1. minimize permanently resident normal-RAM code and state;
2. maximize useful dynamic storage for programs, variables, and compiled code;
3. minimize execution time on normal workloads.

Every change that increases the resident footprint must report the byte delta
and explain why the new resident behavior cannot be geoRAM-backed.

Numbered sections and subsections are requirement group IDs. For example,
section 8 is `R8` and section 3.1 is `R3.1`. Individual test matrices may add
stable suffixes such as `R8-NESTED-CALL`.

## 2. Product Requirements

The product must be a native 6502 compiler and interactive BASIC environment
for the Commodore 64 with a supported expansion-memory device. The release is
a **dual-capable** installation: one common `BASICV3` program detects
**geoRAM** and/or a **Commodore REU** (REC at `$DF00-$DF0A`) at startup and
uses **exactly one** device for the session. **geoRAM is preferred** when both
are present and valid (more efficient execute-in-place). When only REU is
valid, REU is used.

`REU_REQUIREMENTS.md` and `REU_DESIGN.md` detail dual-device detection, REU
hardware, the geoRAM-canonical image + REU patch packaging model, and REU
verification. This document remains authoritative for language behavior, the
runtime ABI, `COMPILE` exports, the canonical CPU map, KERNAL use, testing
hierarchy, and build reproducibility.

**geoRAM-canonical implementation.** Expansion-native code is designed and
built as geoRAM 256-byte XIP pages. The REU path does **not** use a separate
service-sized overlay architecture: it DMA-copies the equivalent 256-byte page
into a designated normal-RAM XIP buffer (ideally the RAM-under-I/O image of
`$DE00-$DEFF` when hardware and banking allow, otherwise a fixed normal-RAM
window) and executes that page in place. Only fetch/stash/call gate routines
differ between backends. One source tree; deployment differs by a small REU
patch applied after loading the geoRAM-canonical expansion image.

It must:

- accept direct commands and numbered BASIC program lines;
- retain an editable tokenized program;
- compile stored programs to native 6502 code;
- execute compiled programs with BASIC-compatible results;
- load and save tokenized BASIC programs in stock-compatible form for the
  target dialect machine (C64 for BASIC V2; Plus/4-compatible linked form for
  supported BASIC 3.5 programs);
- save compiled programs in a documented executable format for the **C64**;
- provide large dynamic arenas for tokenized programs, compiled programs,
  scalar variables, arrays, strings, compiler data, and diagnostics;
- leave the largest practical amount of ordinary C64 RAM available to running
  programs;
- fail cleanly if no supported expansion device is present, if the selected
  device is too small, corrupt, or changes unexpectedly, or if both devices
  fail validation.

The minimum supported capacity for **each** backend is 512 KiB of non-aliased
expansion memory. The build must declare the minimum and the detector's
measured capacity for the selected device. Larger supported devices must
increase arena capacity without changing language semantics. Language,
editor, compiler, runtime ABI, and numeric-profile behavior must be the same
whether geoRAM or REU is selected.

When both devices are present and valid, **prefer geoRAM** as the expansion
store and XIP backend. The REU remains available for an **internal DMA-assisted
memcopy** used by large block moves (see design: shared copy helper). When
exactly one device is valid, that device is the expansion store (REU-only also
uses REU for DMA). When neither is valid, installation aborts. After probe, the
non-selected store is not used for arenas/XIP; a co-detected REU may still be
used only for DMA-assist when geoRAM is the store.

### 2.1 Phase 1 Install and Editor Slice

The first implementation phase must produce an installable C64 disk image with
a stock BASIC loader line:

```text
2026 SYS2061
```

The loader machine code must begin at decimal address 2061 (`$080D`). Starting
the loader must non-destructively probe geoRAM and REU, select one supported
backend per the dual-device rules above, reject the case where neither device
is usable, install the common normal-RAM payload, load **only** the selected
device's sidecar payload, initialize that backend, and jump to the Compiler 2
project initialization entry. Initialization must enter the interactive
editor.

The release D64 must carry one common PRG, the **geoRAM-canonical** expansion
image, and a **small REU patch** (not a second full assembly of the product):

| Host build object | C64 D64 filename | Role |
|---|---|---|
| `basicv3.prg` | `BASICV3` | Common loader, detectors, RAM payload |
| `georam.bin` | `GEORAM` | Normative expansion image (XIP pages/directories) |
| REU patch object | `REU` | Small delta/patch + optional deterministic fixup code for REU |

Install sequence: detect device → load `GEORAM` image into the selected
expansion store (geoRAM pages, or REU memory via DMA) → if REU was selected,
load and apply the `REU` patch (and any in-place deterministic fixup loops) →
enter `compiler_init`. A geoRAM session must not require the `REU` patch after
selection.

The first editor/runtime slice must support enough BASIC V2 behavior to enter,
list, save, load, and run this timing program:

```basic
10 B=TI
20 FORX=1TO1000
30 NEXT
40 A=TI
50 PRINTA-B
```

This phase must include:

- editor entry of numbered program lines;
- canonical tokenized program storage for the supported syntax;
- `RUN`, `LIST`, and `NEW`;
- immediate `?` and `PRINT` of numeric scalar variables and `TI`;
- immediate `LOAD` and `SAVE` of tokenized BASIC programs;
- numeric scalar variables;
- the special variables `TI` and `TI$`, including `TI$` assignment;
- `FOR`, `NEXT`, and `TO` sufficient for the required loop.

## 3. Language Compatibility

### 3.1 BASIC V2

For stock syntax, the system must be semantically compatible with Commodore 64
BASIC V2 except for the explicit direct-mode restrictions in section 4.

Compatibility includes:

- lexical rules, abbreviations, token boundaries, quoting, and `REM` behavior;
- stock edge limits for line numbers, tokenized lines, screen-editor logical
  lines, variable names, string lengths, integer and byte coercions, address
  arguments, arrays, logical files, devices, secondary addresses, filenames,
  and input fields as defined in `docs/BASIC_COMPATIBILITY_LIMITS.md`;
- operator precedence and associativity;
- numeric parsing, formatting, coercion, overflow, and error behavior;
- string creation, slicing, comparison, and lifetime behavior;
- scalar and array naming, implicit creation, `DIM`, and subscript checks;
- `DATA`, `READ`, and `RESTORE` ordering;
- `FOR`/`NEXT`, `GOTO`, `GOSUB`, `RETURN`, `ON`, and `IF` control flow;
- file/channel statements and KERNAL-visible errors;
- `TI`, `TI$`, `ST`, `GET`, keyboard, STOP, and screen-visible behavior;
- the error class and observable state after an error;
- deterministic `RND` behavior where the stock seed and call sequence are
  defined;
- `PEEK`, `POKE`, `SYS`, `USR`, and `WAIT` effects on the real C64 address
  space, subject to documented protected compiler storage. Protected storage
  is limited to the control plane required for system integrity: hardware
  vectors and the high-memory guard (`$FFF9-$FFFF`), pinned IRQ/NMI and
  resident control blocks, geoRAM gate/selection state, arena-directory
  mirrors that must remain consistent, and compiler-owned zero-page ranges
  from the generated allocation map. Ordinary program, variable, string,
  compiled-image, screen, I/O, and free dynamic RAM ranges remain
  user-accessible through `PEEK`/`POKE` as on stock BASIC; user corruption of
  those ranges is allowed and produces stock-like or fail-clean consequences
  rather than silent protection. The build publishes the exact protected
  intervals in generated map artifacts;
- `FRE` free-memory reporting that is profile-aware: in the installed
  geoRAM-backed development environment, `FRE` returns free bytes in the
  primary variable/string arena used by running programs (which may be
  geoRAM-backed); in a source-free `COMPILE` export without geoRAM, `FRE`
  returns free bytes in the normal-RAM dynamic region remaining after the
  exported image. The argument to `FRE` is accepted and discarded as in stock
  BASIC V2;

The required stock keyword surface is:

- Statements and commands: `END`, `FOR`, `NEXT`, `DATA`, `INPUT#`, `INPUT`,
  `DIM`, `READ`, `LET`, `GOTO`, `RUN`, `IF`, `RESTORE`, `GOSUB`, `RETURN`,
  `REM`, `STOP`, `ON`, `WAIT`, `LOAD`, `SAVE`, `VERIFY`, `DEF`, `POKE`,
  `PRINT#`, `PRINT`, `CONT`, `LIST`, `CLR`, `CMD`, `SYS`, `OPEN`, `CLOSE`,
  `GET`, and `NEW`.
- Operators and syntax tokens: `TAB(`, `TO`, `FN`, `SPC(`, `THEN`, `NOT`,
  `STEP`, `+`, `-`, `*`, `/`, `^`, `AND`, `OR`, `>`, `=`, and `<`.
- Functions: `SGN`, `INT`, `ABS`, `USR`, `FRE`, `POS`, `SQR`, `RND`, `LOG`,
  `EXP`, `COS`, `SIN`, `TAN`, `ATN`, `PEEK`, `LEN`, `STR$`, `VAL`, `ASC`,
  `CHR$`, `LEFT$`, `RIGHT$`, and `MID$`.

`docs/KEYWORDS.md` must describe each implemented keyword, but omission from
that reference does not reduce the BASIC V2 compatibility requirement.
Likewise, every limit in `docs/BASIC_COMPATIBILITY_LIMITS.md` is a
compatibility contract even when an individual keyword entry omits the edge
case.

### 3.2 Implemented Extensions

The implementation must preserve the extension behavior already accepted by
the compatibility tests and documented in `docs/KEYWORDS.md`.

The required BASIC 3 gateway surface is:

- `BASIC2`
- `BASIC3.5`
- `BASIC()`
- `COMPILE`
- `QUIT`
- `FPMODE0`
- `FPMODE1`
- `FPMODE()`

`QUIT` is direct-mode only. It must leave the Compiler 2 environment via a
**soft reset into stock BASIC V2** with this **locked sequence**:

1. restore CPU banking, BASIC/KERNAL map pointers (including `txttab`/`vartab`/
   `memsiz` consistency for the retained program), and IRQ/NMI vectors so
   stock BASIC can run;
2. clean any Compiler 2-owned normal-RAM control state not fixed by that
   restore;
3. perform **CLR semantics explicitly** (reset `vartab`/`arytab`/`strend`/
   `fretop` and the string stack while leaving the program) — stock warm-start
   `panic` alone is **not** sufficient (it does not call `clear`/`clearc`);
4. enter stock **READY** (or the stock path that reaches READY after CLR).

Do **not** take cold `init`/`initcz` (rebinding `txttab` / zeroing the
program). Do **not** bare-`panic` without the explicit CLR step. Variables
need not be preserved. The **tokenized program remains** in BASIC program
memory. **Expansion device contents are left untouched** (no wipe of
geoRAM/REU images).

**Test contract:** after `QUIT`, a program that contains **only stock BASIC V2
tokens** must be `LIST`able and `RUN`nable under stock BASIC V2 with the same
source semantics. If the program contains BASIC 3/3.5 or other non-V2 tokens,
stock BASIC may error; that is acceptable and need not be mitigated.

**Re-entry:** the user must be able to load the Compiler 2 installer again
after `QUIT`. Skip-reload integrity uses the **same content-based install
image fingerprint(s)** already required for GEORAM/REU validation (not a
separate ad hoc checksum). If resident expansion images still match those
fingerprints for what the installer would load, the installer may **skip
reloading** those images and proceed to verify and re-enter Compiler 2.
Expansion RAM is expected to remain intact across a normal `QUIT`.

`QUIT` must remain available in the minimal no-expansion-device editor (§8.5).

The required opt-in BASIC 3.5/7 structured subset is:

- `ELSE`
- `DO`
- `LOOP`
- `EXIT`, including `EXIT DO` and `EXIT FOR`
- `UNTIL`
- `WHILE`
- `DO WHILE`, `DO UNTIL`, `LOOP WHILE`, and `LOOP UNTIL`

The dialect must start in BASIC V2 mode. Structured extension tokens must
produce `?SYNTAX ERROR` while BASIC 3.5 mode is disabled. IEEE mode and dialect
mode must remain independent.

The BASIC V2 loop implementation for `FOR`, `NEXT`, `STEP`, and `TO` must be
co-designed with the BASIC 3.5 structured loop implementation for `DO`, `LOOP`,
`WHILE`, `UNTIL`, `EXIT DO`, and `EXIT FOR`. Even when BASIC 3.5 loop tokens
are not enabled or testable in an early milestone, the parser, control-flow
descriptors, loop stack model, invalidation rules, runtime ABI, and optimizer
metadata must be capable of representing both loop families without a later
rewrite of the BASIC V2 loop architecture.

IEEE functions and any additional extensions listed in `docs/KEYWORDS.md` are
required once marked implemented. Planned entries must be visibly identified as
planned and must not be counted as supported.

### 3.3 Semantic Oracle

Stock behavior must be checked against the rebuildable BASIC and KERNAL source
at:

`C:\Users\me\Documents\Coding Projects\c64rom`

That tree builds byte-identical stock BASIC V2 and KERNAL ROMs, preserves
labels, and provides source-derived API and zero-page reports. The current
compiler project is a useful behavioral and test oracle, but it is not
automatically a design oracle.

VICE is the ultimate behavioral reference emulator for the C64 and Plus/4.
When the source-derived expectation and a stock VICE observation appear to
disagree, the discrepancy must be captured as an oracle issue and resolved
before Compiler 2 behavior is accepted.

The explicit stock limit contracts are in
`docs/BASIC_COMPATIBILITY_LIMITS.md`. VICE confirmation for those contracts is
deferred until the project has a harness, but implementation tasks and tests
must still reserve named cases for each limit.

## 4. Direct and Program Modes

The parser must classify command context before execution. Direct-only commands
must be rejected from stored programs with a BASIC-compatible syntax error and
must never be silently compiled as no-ops.

The following are direct-mode only:

| Group | Commands |
|---|---|
| Program/session | `NEW`, `RUN`, `CONT`, `CLR`, `LIST`, `COMPILE`, `QUIT` |
| File program management | `LOAD`, `SAVE`, `VERIFY` |
| Dialect/policy | `BASIC2`, `BASIC3.5`, `FPMODE0`, `FPMODE1` |
| DOS wedge | `$`, `/`, `@`, `!` |

`RUN` must support the stock bare form and line-number form. `LIST` must
eventually support the stock range forms, even if an early milestone supports
only bare `LIST`.

All other stock statements must work in stored programs. They must also work in
direct mode wherever stock BASIC V2 permits direct execution.

DOS-wedge prefixes are editor commands, not tokenized program statements. Their
exact supported forms and any staged limitations must be documented.

DOS wedge device-selection commands must update the same current disk device
state used by `LOAD`, `SAVE`, and `COMPILE`. For example, `@10` sets the
current disk device to 10, so a later bare `COMPILE` writes `COMPILED` to
device 10.

`LOWMEM` is not part of Compiler 2. Improved variable and arena management must
make a user-selectable low-memory preservation policy unnecessary.

## 5. Tokenized Program Compatibility

Stock-only saved programs must be binary compatible with Commodore 64 BASIC V2.

This requires:

- PRG load address `$0801`;
- the stock linked-line record structure;
- little-endian next-line pointers and line numbers;
- stock token byte assignments without remapping;
- a zero byte terminating each line and a zero link terminating the program;
- correct quote, `DATA`, and `REM` tokenization rules;
- canonical relinking when materializing a program for save.

**Stock tokenize / LOAD / SAVE / VERIFY compatibility** is required for the
target dialect machine:

- **BASIC V2 programs** must use unmodified C64 BASIC V2 linked-line PRG form
  (load address `$0801`, stock links, stock token bytes). A stock V2 PRG
  loaded and saved without editing must preserve program semantics; canonical
  save tests compare against stock C64 output. `petcat -2` and stock C64 VICE
  are valid tooling oracles for this surface.
- **Supported BASIC 3.5 programs** must use **Plus/4 PRG headers and token
  bytes** for LOAD/SAVE/VERIFY so that (a) a real Plus/4 stock 3.5 program can
  be loaded and run on the C64 host under Compiler 2, and (b) a 3.5 program
  edited on the C64 host and SAVEd can run under stock Plus/4 BASIC 3.5.
  Plus/4 VICE and `petcat -3` are oracles for that surface. The C64 host must
  accept Plus/4-style PRG headers on load.
- **Compiler 2-only keywords** (BASIC 3 gateway, IEEE, and other non-stock
  tokens) are not expected to round-trip through `petcat` or stock ROMs. They
  must still use unambiguous token bytes that do not remap stock V2 tokens,
  remain round-trippable in Compiler 2, and fail cleanly on unsupported
  versions.

**LOAD recognizes program version/format** from the file (C64 V2 PRG vs Plus/4
3.5 PRG vs Compiler 2-only encoding) before replacing the program directory.
On successful LOAD of a recognized stock V2 or stock 3.5 file, the session
dialect must match that program class (auto-select `BASIC2` or `BASIC3.5` as
appropriate) so subsequent editing uses the correct token set.

**SAVE chooses format from tokenized content**, not REM/string text and not
merely the current dialect mode:

1. if any **Compiler 2-only tokens** appear outside REM/string contexts →
   Compiler 2-only encoding;
2. else if any **BASIC 3.5 tokens** appear outside REM/string contexts →
   **Plus/4 3.5 PRG** (do not translate to V2; stock V2 may fail to LIST/RUN);
3. else → **C64 V2 PRG**.

**VERIFY** must compare the file on disk to **exactly what SAVE would write**
for the current program (same format class and bytes). VERIFY is intended for
use after SAVE. Comparison is **pure byte equality** against the SAVE emission
path (including Plus/4-format files on the C64 host); it must not require a
Plus/4 ROM or interpreter.

Compiled native programs run on the **C64** only and may use any implemented
keywords (V2, 3.5, or Compiler 2 extensions). Plus/4 already runs a BASIC
superset of C64 V2; compiled output is not a Plus/4 target.

The internal expansion representation may use handles or indexes, but `LOAD`,
`SAVE`, `LIST`, and compatibility tests must observe the stock form rules
above.

## 6. Compilation and Runtime

Compilation must be deterministic for identical source, options, and build
version.

The compilation pipeline must have explicit, inspectable boundaries:

1. canonical tokenized source;
2. lexical/statement records;
3. symbols and variable descriptors;
4. control-flow and loop descriptors;
5. typed intermediate representation;
6. optimized intermediate representation;
7. emitted code, relocations, and runtime dependencies;
8. installed compiled image.

Each boundary must have a versioned serialization suitable for replay in host
tests. Failed compilation must identify the phase, source line, and error class.

Compiled code must use a documented runtime ABI. It must not depend on private
compiler workspace addresses, physical geoRAM allocation, or editor state.

The runtime ABI must cover at least:

- scalar and array resolution, load, store, and type promotion;
- string allocation, assignment, slicing, comparison, and reclamation;
- numeric arithmetic and comparisons;
- control flow, loop frames, STOP, and CONT state;
- screen, keyboard, channel, and file I/O;
- BASIC error construction and unwind;
- geoRAM-backed math calls where selected.

### 6.1 Incremental Compilation

The hard interactive requirement is **line entry responsiveness**: ordinary
numbered-line entry (Return to editor-ready) must complete in about **0.5
seconds or less**.

**Error reporting matches stock BASIC:** on line entry, report only what stock
does when tokenizing/storing a line (tokenization failures and any other
entry-time errors stock raises). Do **not** report full parse/semantic/runtime
errors at entry beyond stock. Those surface at **`RUN`** or immediate
execution. Immediate-mode lines still execute after entry as stock does.

**Full per-line code generation may be deferred** when it would violate the
0.5-second budget. Deferred compile work must complete no later than the next
`RUN` (or other execution entry) that needs a consistent compiled image.
Immediate mode must still compile a temporary program for execution through
the same machinery. There is no interpreter fallback: a program is executable
only when the compiled image is consistent with the current source generation
at the moment of execution. Deferred-compile state must be **test-observable**
(e.g. a documented dirty flag or generation mismatch) so automated tests can
assert entry-without-full-compile and compile-on-`RUN` without relying on
timing alone.

The tokenized source remains canonical. Per-line compiled records are cache
entries tied to source generation, dialect, numeric mode, runtime ABI version,
and dependency fingerprints. Publishing a fully compiled record requires
tokenization, validation, code generation, relocation, and cross-line checks
to succeed. On failure of a published compile step, the previous valid
compiled state remains intact.

### 6.2 COMPILE Export

`COMPILE` must produce an independent, stock-compatible compiled program. The
exported PRG must be loadable and runnable on a stock Commodore 64 without
geoRAM using a normal BASIC loader line, must include all runtime support
required by the compiled program, and must not require the Compiler 2 editor,
compiler workspace, tokenized source, installed development environment, or
geoRAM.

The direct command syntax is:

```text
COMPILE ["filename" [,device]]
```

With no filename, `COMPILE` must save as `COMPILED`. With no explicit device,
`COMPILE` must use the current disk device, matching the stock BASIC V2
file-device state held in KERNAL zero-page `fa` at `$BA`. The project assumes a
disk drive is required; supported current disk devices are 8 through 11.
Testing normally uses device 8, but a test environment loaded from device 9
must leave the current disk device as 9 so `COMPILE` without an explicit device
exports to device 9.

The exported compiled program has no source. `LIST` in the standalone
direct-mode environment may show only the exact loader stub:

```basic
2026 SYS2061
```

It must not include tokenized source and must not attempt to decompile or
reconstruct BASIC source from the compiled image.

**Primary goal:** support programs that export cleanly to a **stock C64**
without expansion. The compiler must continuously report the standalone code
budget:

```text
standalone_code_budget = standalone_loader_bytes + compiled_program_bytes
```

with the conventional stock ceiling at the PRG image ending by `$CFFF`
(payload from `$080D` with loader line `2026 SYS2061`). Soft warnings:

- stock-size **status messages are edge-triggered on the 80% boundary**:
  - when estimated standalone size **crosses from below 80% to ≥ 80%**, issue
    the near-limit warning once for that crossing;
  - when it **crosses from ≥ 80% back below 80%** (program shrunk), issue a
    clear/recovery status once for that crossing;
  - hovering around the boundary may produce multiple warnings/clears over
    time, one per crossing, not a continuous spam on every keystroke while
    staying on one side of the threshold;
- when the image would exceed the stock C64 code ceiling, issue
  **`WARNING: EXCEEDS STOCK RAM`** (or equivalent documented wording) but
  **do not hard-reject** the program solely for that reason. (Exceed-ceiling
  messages follow the same edge-triggered pattern relative to the 100%
  boundary unless a higher layer documents otherwise.)

Programs that require expansion-backed storage at runtime or exceed stock
export size remain legal in the development environment. The user is expected
to adapt such programs; release to stock machines is best-effort with warnings.
This supersedes earlier requirements that forced hard rejection of oversize
exports.

**Export layout profiles (stock vs developer).** `COMPILE` must choose a
runtime memory layout based on whether the program can run on a stock C64:

1. **Stock-compatible layout** — when the current program (code + required
   variables/strings/stack) is small enough to work **standalone without
   expansion** and without the development-time XIP reservations: the export
   must assume **`$CE00` is free** in the resulting stock runtime environment,
   even though `$CE00` is reserved on the development machine for REU XIP.
   Hot pages `$C800–$CDFF` are never treated as permanent export reservations.
2. **Developer layout** — when the program/variables would only work in the
   installed Compiler 2 development environment (expansion-backed storage,
   larger workspace, or other non-stock dependencies): compile against the
   **development runtime layout**, which **reserves the fixed `$CE00` page**
   (and any other documented developer-only reservations). Soft stock-size
   warnings still apply when the image would not fit a stock machine.

User-visible size messaging remains the existing edge-triggered stock
budget warnings only (including **`WARNING: EXCEEDS STOCK RAM`**). Layout
profile (stock vs developer / `$CE00` reserved) is an **internal and
export-metadata** fact for linker/tests; it is **not** a second user banner.

Layout choice must be deterministic and testable from program/workspace
measurements; it must not silently use developer-only pages in a stock export.

`compiled_program_bytes` includes emitted user code, required runtime helpers,
relocation or runtime metadata, variable descriptors, the standalone
direct-mode environment, and any other bytes that occupy the standalone PRG
load range. Tokenized source is excluded. Development may store source,
metadata, and caches in expansion memory independently of the stock export
warning threshold.

Variable/array/string/stack/inspection storage for a stock export must still
be budgeted against remaining normal RAM after the image loads. Graphics-mode
exports may use `$D000-$D7FF` RAM under I/O only through documented gates.

A compiled export must provide a source-free standalone direct-mode environment
after program stop/end/error where state remains valid. For inspection, that
environment must support:

- `?` or `PRINT` followed by one single-term expression;
- scalar variables;
- string variables;
- array elements such as `A(N)` or `A$(N)`;
- `CONT` when the compiled stop state is valid.

The standalone environment shall support the immediate commands `RUN`, `LOAD`,
`SAVE`, `VERIFY`, and `CLR`, plus all DOS wedge commands specified in
`docs/DOS_WEDGE.md`. File and wedge commands shall use and update the stock
KERNAL current-device state, `fa` at `$BA`, as applicable.

The environment must reject assignment, compound expressions, program editing,
and arbitrary BASIC statement execution outside the required command set.
`CONT` must be supported by compiled programs when the stop state is valid,
including STOP keyword and STOP-key interruption. There is no source dependency
for `CONT`.

The exported compiled program has no tokenized source. `LIST` may show only the
exact `2026 SYS2061` loader stub; it must not reconstruct BASIC source from the
compiled image.

## 7. Memory and Arena Requirements

Normal RAM must contain only behavior needed while compiled code or the
foreground editor is actively running. Human-latency operations and slow
numeric operations should be expansion-native: execute-in-place through the
geoRAM window when geoRAM is active, or through normal-RAM overlay slots
loaded from REU when REU is active (`REU_REQUIREMENTS.md` RREU-5).

### 7.1 Nominal CPU Memory Map

Normal editor and compiled-runtime operation must use one canonical CPU-port
mapping:

| Address range | Normal mapping |
|---|---|
| `$0000-$CFFF` | RAM, except the 6510 port registers at `$0000-$0001` |
| `$D000-$DFFF` | I/O, including the geoRAM window and selection registers |
| `$E000-$FFFF` | RAM, with KERNAL ROM banked out |

BASIC ROM must also be banked out, leaving RAM visible at `$A000-$BFFF`.
With the standard CPU-port DDR, this mapping corresponds to `$01 = $35`.

RAM at `$FFF9-$FFFF` is reserved. `$FFF9` is a project high-memory guard byte
and `$FFFA-$FFFF` are the 6502 hardware vectors:

- `$FFFA-$FFFB`: NMI;
- `$FFFC-$FFFD`: RESET;
- `$FFFE-$FFFF`: IRQ/BRK.

Ordinary runtime, editor, compiled-code, and geoRAM-call paths must neither save
nor change the CPU banking setup. CPU banking transitions are permitted only:

1. through the explicit RAM-under-I/O access gate, which temporarily exposes
   RAM at `$D000-$DFFF`; or
2. through a KERNAL bridge, which explicitly banks in KERNAL ROM for the
   duration of a documented ROM call.

Both exceptional gates must restore the canonical mapping before returning.
Debug builds must assert the canonical mapping at public entry and exit
boundaries. The RAM-under-I/O gate must mask interrupts, perform only a bounded
transfer, restore I/O visibility, and then restore the incoming interrupt state.

### 7.2 Graphics Memory Contract

Bitmap graphics must use the documented C64 layout:

- the 8000-byte bitmap occupies RAM at `$E000-$FF3F`;
- the 1000-byte bitmap screen/color matrix occupies RAM beneath I/O at
  `$DC00-$DFE7`;
- physical VIC-II color RAM remains `$D800-$DBE7` while I/O is visible;
- `$FFF9-$FFFF` remains reserved and is not bitmap data.

The screen matrix beneath `$DC00` must be accessed only through the bounded
RAM-under-I/O gate. Code running with I/O visible must treat `$DC00` as CIA 1,
not as ordinary RAM. Graphics support must test the VIC bank and memory-pointer
configuration, all address bounds, preservation of `$FFF9-$FFFF`, and
restoration of the canonical `$35` CPU mapping.

Graphics mode must always exit to text mode with stock C64 colors. This restore
is required on normal end of program, any BASIC error, `STOP` statement, and
STOP-key interruption.

The installed environment may place edit/compile-only `HIBASIC` code at
`$E000+`; it must not be a running-program runtime dependency. Before `RUN`
permits graphics to claim an overlapping range, occupied `HIBASIC` bytes must
be copied transactionally to a dedicated geoRAM buffer. `END` or fall-through
ends the graphics reservation and restores those bytes. Error, `STOP`, and
STOP-key paths restore the display but retain graphics memory for `CONT`.
Editing a line invalidates continuation and lazily restores `HIBASIC`, knowingly
overwriting the old graphics. Compiler entry must also force this restore.

### 7.3 Hard Memory Budgets

Normal RAM may be used up to the documented hardware and system reservations:

- `$0000-$0001` are the 6510 processor port registers;
- `$0100-$01FF` is reserved for inherent CPU stack operation;
- `$D000-$DFFF` is the visible I/O window in the canonical map;
- `$FFF9-$FFFF` is reserved high memory, including hardware vectors;
- when REU XIP is active, **`$CE00–$CEFF` is reserved** as the primary XIP miss
  slot; **`$C800–$CDFF` hot slots are optional cache** and may be reclaimed
  under memory pressure (not permanent reservations).

POKE/PEEK protection remains the **narrow control-plane** policy in §3.1
(vectors, gates, profile mirrors, compiler ZP). Do **not** blanket-protect
`$C800–$CDFF` solely because they may hold hot XIP; `$CE00` may be listed as
protected while REU XIP is active if corruption would crash the gate.

All other normal RAM is available to the implementation subject to the
canonical banking contract. All geoRAM memory provided by the supported device
may be used by Compiler 2 arenas, allocator metadata, overlays, variables,
tokenized programs, compiled programs, and scratch storage.

Strings have a maximum length of 255 characters. The installed Compiler 2
environment should prefer geoRAM-backed string payloads for scalar strings and
string-array elements when geoRAM is available. String descriptors and runtime
helpers must also support normal-RAM-backed payloads because source-free
compiled exports must run on a stock C64 without geoRAM. A string descriptor
must record the payload storage class, bounds, ownership, and lifetime so that
string allocation, assignment, slicing, comparison, reclamation, and compiled
export state inspection do not depend on physical geoRAM allocation.

When a string payload is geoRAM-backed, each materialized scalar string value
and each materialized string-array element should own one full geoRAM page.
GeoRAM-backed string payloads must not span pages. Normal-RAM-backed string
payloads must have equivalent ownership, bounds, and stale-handle checks, but
are not required to use page-sized allocation.

The following must be expansion-backed (selected geoRAM or REU backend) unless
measurement proves that a small resident component is necessary:

- editor parsing and line editing transforms;
- lexer and tokenizer;
- parser and semantic analysis;
- symbol, control-flow, IR, optimization, and code-generation passes;
- diagnostics formatting;
- trigonometric and transcendental math;
- tokenized program storage;
- compiled program storage;
- cold scalar variables and arrays;
- string payloads when the active runtime profile has expansion memory
  available.

Large objects must be addressed by stable logical handles rather than raw
window addresses, REU physical addresses, or DMA staging pointers.

Trig, transcendental, and IEEE extension math must meet the accuracy and ABI
contracts in `docs/IEEE754.md` and the generated runtime ABI. Implementations
may adopt proven external algorithms when they fit Compiler 2 contracts.
Memory map, fixed addresses, and zero-page assignments from any external
codebase are not requirements; all placement follows Compiler 2 generated
manifests, ABI, and expansion policy.

Every arena must have:

- a type and format version;
- capacity and allocation metadata;
- page ownership and bounds checks;
- generation numbers for stale-handle detection;
- explicit allocation failure behavior;
- integrity checks usable by tests;
- deterministic reset and invalidation rules.

At minimum, separate ownership must exist for:

- tokenized program;
- compiled images;
- scalar descriptors and cold scalar payloads;
- arrays;
- strings;
- symbols and compiler IR;
- overlay code and dispatch metadata;
- scratch and diagnostics.

An arena may share a physical free-page allocator, but one region must not be
able to corrupt another without an integrity check detecting it.

## 8. Expansion Memory Requirements (geoRAM and REU)

The product uses one **active expansion backend** per session. **geoRAM XIP is
normative.** REU emulates the same 256-byte page model by DMA into a
designated XIP RAM buffer. Detail: `docs/GEORAM_BANKING.md`,
`REU_REQUIREMENTS.md`, `REU_DESIGN.md`.

### 8.1 Common dual-device rules

- Startup must probe geoRAM and REU non-destructively, prefer geoRAM when both
  are valid, select exactly one **store** backend, load the geoRAM-canonical
  expansion image into that store, and apply the `REU` patch only when REU is
  the selected store.
- Supported geoRAM capacity is **always at least 512 KiB**. The geoRAM-canonical
  project image (XIP pages, directories, required fixed arenas) must **fully fit
  in 512 KiB**. A **build that exceeds 512 KiB must fail**. Larger detected
  geoRAM may be used **only as extra dynamic storage** (e.g. strings, growth),
  never as a requirement for the base image. XIP pages must be packed into
  **lower geoRAM space first** (low block/page numbers before high).
- REU store sessions use the same logical page image; REU patching of XIP
  routines must **not** require the geoRAM device size—only the canonical
  image layout, page IDs, and fixup bases (`$CE00` / optional hot slots). Patch
  metadata must include image fingerprint/version (and other validation) but
  not a geoRAM capacity field used for fixup.
- Expansion-native services share one source and one logical page/directory
  model; backends differ only in page select vs DMA-to-buffer and install
  patching.
- Logical handles, routine IDs, and the runtime ABI must not expose physical
  geoRAM or REU addresses to compiled user programs.
- IRQ/NMI code must be pinned in normal RAM and must not depend on the
  selected geoRAM page or program the REU controller during normal service.
- Interactive DMA must complete within **one jiffy** (≤ ~17 000 cycles on the
  C64) per transfer quantum; XIP page fills are one 256-byte page at a time.
- **“Both present”** means both geoRAM and REU were successfully detected at
  cold install **or** after an NMI re-detect (§8.5). The session then uses
  geoRAM as store and may set REU assist for memcopy/memfill.
- Tests must cover: geoRAM only; REU only; both present (geoRAM store + REU
  assist); neither (abort or minimal editor per §8.5). Layered testing: full
  low-level fetch/stash/call per backend; bulk language E2E on geoRAM; REU
  smoke. VICE snapshots must use the explicit names in the design (§ testing).

### 8.1.1 Expansion profile record (R8.1.1)

After successful install (and after each successful NMI re-detect that keeps
full capability), the system must publish one immutable-for-the-interval
**expansion profile** in resident storage, readable by all gates. It must
include at least:

- store kind (`georam` | `reu` | `none` for degraded mode);
- `reu_assist` boolean;
- detected capacities/fingerprints as applicable;
- XIP slot bases and counts;
- memcopy/memfill thresholds in force (`N_dma`, `N_fill`);
- optional feature bits (`verify`, `swap`) if implemented;
- generation/status for assist-off and degraded modes.

Gates must not re-probe hardware on every call; they consult the profile.
Every re-detect that changes store or assist must bump **profile generation**;
in-flight DMA/XIP ops that observe a generation mismatch must abort cleanly.
Assist-only REU failure must clear `reu_assist` and continue the session on
CPU memcopy/memfill without requiring reinstall (§8.5). Profile fingerprints
for `GEORAM`/`REU` images must be content-based (reproducible), not host paths
or wall-clock times.

### 8.1.2 DMA range classes (R8.1.2)

All REU DMA (memcopy, memfill, optional swap/verify, install) must classify
C64 endpoints before programming the REC. The design owns the class table;
required classes include at least: normal RAM, bitmap RAM, colour RAM (I/O
visible), matrix under I/O (only inside the RAM-under-I/O gate), and
forbidden ranges (I/O registers, stack, unprotected project control). DMA
into a forbidden class must fail cleanly without programming an illegal
transfer.

### 8.2 Shared memcopy policy (R8.2)

The system must provide one internal **memcopy** helper for block moves of
**1–256 bytes** between validated C64 normal-RAM ranges (and, with staging,
to/from expansion pages). Callers that perform bulk payload or page-sized
copies (including string payloads, geoRAM page-to-page moves, program-stream
shifts/clones, and similar) must use this helper rather than ad hoc per-byte
loops, except where a shorter specialized sequence is provably fixed-size and
below the DMA threshold.

**When REU DMA is available** (REU selected as store, or geoRAM selected as
store with REU co-detected for assist):

- transfers of length **N &lt; N_dma** must use a native 6502 path (abs,X or
  equivalent zp-indirect form suitable for the addresses);
- transfers of length **N ≥ N_dma** must use REU DMA when the ranges are
  DMA-legal (1-hop or 2-hop as required by the endpoints);
- **N_dma** is an integer **1 ≤ N_dma ≤ 256**, published in the design and as a
  checked-in or generated production constant shared with tests;
- initial required default: **N_dma = 32**, chosen at the conservative
  C64↔C64 (2-hop) break-even from scratch measurement; the design may document
  a lower 1-hop floor (~16) only as measurement context, not as a second
  production threshold unless later re-measure justifies splitting;
- **N_dma** may change only with recorded re-measurement and updates to the
  design section that implements this requirement;
- each interactive DMA quantum still obeys the one-jiffy bound.

**When REU is not available**, memcopy always uses the native path.

Memcopy must not be used for tiny fixed descriptor/math copies that are
structurally shorter than a call+threshold check would justify; those remain
inline. System or unit tests must prove: (a) lengths below threshold never
program the REC; (b) lengths at/above threshold use DMA when REU is available;
(c) result bytes match the native path for representative lengths and
alignments.

### 8.2.1 Shared memfill policy (R8.2.1)

When REU DMA is available, the system must provide an internal **memfill**
helper that sets **1–65536 bytes** of a DMA-legal C64 range to one constant
byte by storing that byte once in REU (or using a fixed fill cell) and
executing REU→C64 DMA with **REU address fixed** and **C64 address
incrementing** (`$DF0A` bit 6 set, bit 7 clear). Chunking must obey the
one-jiffy interactive DMA quantum; long fills (e.g. 8000-byte bitmap clear)
must yield between quanta so IRQ/timer/keyboard service can run.

When REU is not available, memfill uses a native 6502 fill path.

Bulk clear/fill of graphics bitmap, bitmap screen matrix, color RAM (with I/O
visible as required), and arena/string page zeroing must use memfill when the
length is at least **N_fill** bytes. Default **N_fill = 32** (same order as
`N_dma`) unless re-measurement documents a different constant. Tiny fixed
clears remain inline.

### 8.3 geoRAM backend

When geoRAM is selected, follow `docs/GEORAM_BANKING.md`: non-destructive
detection; page/block ownership; nested call page restore; distinct return vs
tail transfer; no execute across the 256-byte window boundary; generated ABI
and directory checks; IRQ independent of selected page. Minimum **512 KiB**
must hold the entire project image; pack XIP from low addresses first.

### 8.4 REU backend (page-buffer XIP)

When REU is selected:

- REU memory is DMA-only; code never executes from REU itself;
- each logical XIP page is DMA'd (256 bytes) into the designated XIP buffer
  before entry; optional multi-buffer cache of hot pages is allowed when
  normal RAM permits, prefilled for invariant hot paths (e.g. lexer/keyword
  tables);
- XIP runs from normal-RAM slots (primary `$CE00`, optional hot slots in
  `$C800–$CDFF`); each slot is fixed for its own base at DMA-in so calls route
  directly into hot slots without recopying through `$CE00`;
- only the pinned REU gate writes REC `$DF01-$DF0A` in production;
- transfers use explicit `$DF01` execute; `$FF00` trigger disabled by default;
- DMA stalls the 6510; quanta ≤ one jiffy with IRQ service between quanta.
- REU patching must not depend on geoRAM device size; pack and fixup use the
  canonical page image only (§8.1).

### 8.5 Re-detect, assist degradation, and minimal editor (R8.5)

**RESTORE / NMI.** The user is assumed to press RESTORE because of a **hang or
untrusted state**. The NMI path must be **minimal and distrustful**:

- must not resume the interrupted program or trust its stack/code;
- must invalidate **CONT** and any continuation frames;
- must mark compile state **fully dirty** (any in-flight or aborted compile is
  discarded as untrusted);
- must trust existing RAM as little as practical beyond source the design
  marks durable (prefer re-validate generation/canaries; do not resume
  mid-statement);
- must re-enter editor init far enough to **re-probe** devices and republish
  the expansion profile (or degraded mode);
- must not depend on expansion-resident code before re-detect succeeds.

**Assist degradation.** If the expansion **store** remains valid but REU assist
fails mid-session, clear `reu_assist`, keep the session, use CPU memcopy/memfill,
and report once (design-defined message).

**Store loss / no devices after re-detect.** If re-detect finds **no** usable
expansion store (neither device valid), the system must enter a **minimal
resident editor** that:

- displays a clear error that expansion memory is missing or failed;
- accepts **`QUIT`** to return to stock BASIC;
- on any other direct command, re-displays the same expansion-memory error
  without invoking expansion-native services.

The minimal editor must **not** pull the full editor/compiler into resident
RAM—only enough UI and input path to show the error and honor `QUIT`.

**Cold install with neither device** still aborts before trusting expansion
state (R2); the minimal editor applies after a session that later loses
devices (e.g. NMI re-detect), or as design specifies for post-install loss.

## 9. Editor and Interrupt Requirements

The foreground editor may use expansion-native services because human response
time is the target, not instruction-level latency. A small pinned
screen/keyboard front end may remain resident.

Line submission must be transactional for source:

- tokenize into scratch storage (stock-equivalent entry errors only);
- allocate or resize the destination record;
- commit the new program directory atomically;
- leave the old line intact on failure.

Deferred full compile until `RUN` is permitted per §6.1. The implementation
must expose a testable **compile-dirty** (or equivalent) state so tests can
prove entry without full compile and successful compile-on-`RUN`.

The IRQ path must remain resident, bounded, and expansion-selection-
independent. It must:

- update the KERNAL jiffy clock;
- scan the keyboard;
- maintain required cursor state;
- acknowledge the interrupt source;
- preserve the interrupted CPU-port and expansion context.

The NMI path must satisfy §8.5 (RESTORE re-detect / editor re-entry).

Long compilation and math operations must not stop timer or keyboard service.

The editor must preserve stock C64 line-editing behavior that affects programs:
logical-line limits, quote mode, insert/delete, cursor movement, screen wrap,
keyboard repeat, STOP polling, and visible screen output must match stock
behavior unless a documented Compiler 2 extension applies.

## 10. KERNAL Requirements

All ROM calls must pass through documented bank-safe bridges as specified in
`docs/KERNAL_ABI.md`.

KERNAL ROM is absent from the nominal runtime map. A KERNAL bridge must
explicitly switch from the canonical `$35` mapping to the KERNAL+I/O mapping
for the ROM call, then restore `$35` before returning. With the standard DDR,
the bridge mapping is `$01 = $36`; BASIC ROM remains banked out.

Each bridge must declare:

- entry registers and flags;
- returned registers and flags;
- KERNAL and project zero-page locations read or written;
- CPU-port and interrupt-state behavior;
- whether it may block or invoke device-specific code.

KERNAL zero-page effects must be derived from the source under `c64rom`, not
from memory or folklore. Any project allocation live across a KERNAL call or
IRQ must interfere with that call's zero-page set.

The generated zero-page allocation map must reserve or model all stock KERNAL
zero-page locations used by Compiler 2's KERNAL bridges and IRQ paths. This
includes KERNAL file-device byte `fa` at `$BA`, which is both the stock
`SETLFS` device byte and Compiler 2's current disk device state.

## 11. Optimization Requirements

Optimizations must be optional refinements of a correct generic path.

Compiled programs should execute faster, measured in 6502-family CPU cycles,
than the corresponding stock interpreted program for most supported
non-extension language cases. BASIC V2 keyword performance is compared against
stock C64 BASIC V2. BASIC 3.5 keyword performance is compared against stock
Plus/4 BASIC 3.5 and must be normalized by cycles, not elapsed time, because
the Plus/4 has a different clock speed. This is an expected design target, not
permission to change semantics. There is no compiled-speed requirement for
IEEE extensions, the editor, or DOS wedge commands.

The Phase 1 timing-loop program in section 2.1 must execute in less than 60
C64 jiffies when run as a compiled program:

```basic
10 B=TI
20 FORX=1TO1000
30 NEXT
40 A=TI
50 PRINTA-B
```

This is a hard Phase 1 performance requirement because it proves that the
minimal `FOR`/`NEXT`, numeric scalar, `TI`, and `PRINT` runtime path is faster
than stock C64 BASIC V2 for the project bootstrap benchmark.

Incremental compilation should complete ordinary numbered-line entry in about
0.5 seconds or less on the target development environment. This is not a hard
acceptance limit, but line-entry latency must be measured and reported because
slow line submission makes the editor feel sluggish.

Tokenizer and parser algorithms must be selected with these performance
targets in mind. Keyword recognition must avoid repeatedly scanning the full
keyword table for every candidate token; a bucketed, trie-like, hashed, or
otherwise bounded lookup strategy is required unless measurement proves that a
simpler strategy meets the line-entry target. Every build must report the
selected lookup representation, table size, maximum lookup depth/fan-out, and
measured keyword-recognition cost so a supposedly bounded implementation
cannot silently regress to a full-table scan.

The loop strategy in `docs/LOOP_OPTIMIZATION.md` is required:

- stable variable and loop descriptors;
- explicit partner, type, banking, condition, and invalidation metadata;
- direct integer `FOR`/`NEXT` only when all eligibility proofs pass;
- direct backedges for safe bare `DO`/`LOOP`;
- direct simple-condition branches only when descriptor facts remain valid;
- generic fallback for every unproved case;
- identical errors, final values, STOP behavior, and side effects in optimized
  and generic execution.

No optimization may be selected from source shape alone when aliases, `POKE`,
`SYS`, callbacks, banking, or mutable descriptors can invalidate its proof.

The generic loop descriptor and runtime path must be shared by BASIC V2
`FOR`/`NEXT` loops and BASIC 3.5 structured loops. Direct or optimized loop
forms may be added incrementally, but early BASIC V2 loop support must not use
a one-off representation that must be replaced before `DO`/`LOOP`/`EXIT`
support can be accepted.

## 12. Robustness and Observability

Build generation must be the source of truth for:

- routine IDs and geoRAM placement;
- dispatch and relocation tables;
- arena IDs and layouts;
- runtime ABI versions;
- zero-page allocations and interference edges;
- exported test entry points;
- resident and geoRAM byte counts;
- the current-build callable API and calling conventions;
- the current-build CPU, zero-page, segment, geoRAM, arena, and standalone
  memory map.

Generated outputs must be reproducible and checked for overlap, overflow,
duplicate IDs, unresolved references, and stale versions.

Every build must generate table-formatted `build/API.md` and `build/MAP.md`.
`API.md` must contain every production callable exactly once with its address
or geoRAM placement, inputs, outputs, error/flag result, clobbers/preservation,
zero-page use, stack/return kind, banking/interrupt behavior, side effects, and
availability profile. `MAP.md` must summarize all occupied, reserved, dynamic,
free, and profile-dependent CPU/zero-page/geoRAM ranges and reconcile its
totals with the linker, arena, zero-page, and size artifacts. These references
describe the current build and are not checked-in normative inputs.

Debug builds must support:

- arena canaries and checksums;
- poisoned scratch and zero page between calls;
- phase artifact dumps;
- geoRAM selection traces;
- call-depth and stack-watermark checks;
- deterministic fault injection for allocation and I/O failures.

Release builds may remove expensive checks, but must retain bounds checks at
untrusted handles and file/program format boundaries.

### 12.1 Build Toolchain

All production 6502 assembly must be assembled with `ca65` and linked with
`ld65` from the cc65 toolchain. No alternate assembler syntax or linker may
silently become authoritative.

The canonical installed tools are:

```text
C:\Users\me\Documents\Coding Projects\tools\ca65.exe
C:\Users\me\Documents\Coding Projects\tools\ld65.exe
```

The known baseline is ca65/ld65 2.19. The build must record tool versions in
its manifest and must fail if required tools, generated inputs, assembly,
linking, or post-link validation fail.

`build/API.md` and `build/MAP.md` are required in debug, release, clean, and
incremental builds. Their checksums must be recorded in `build_manifest.json`;
generation or validation failure fails the build.

`docs/BUILD.md` defines the required build order, artifacts, and reproducibility
rules. `docs/GENERATED_REFERENCE.md` defines the generated-reference schemas.

## 13. Test Hierarchy

Test scope and execution fidelity are separate classifications.

Every callable assembly subroutine must have direct unit tests. Production
public entries are tested through their normal exports. Callable internal
subroutines must be published through a generated test-build entry manifest so
they can be invoked directly without becoming part of the production ABI.
Branch-local control-flow labels are not subroutines. Unit tests must verify
each routine's documented success, boundary/error, register, flag, stack,
banking, and zero-page contracts as applicable.

Integration tests must enter through one public API and exercise multiple real
subroutines in one call. They must not replace downstream assembly behavior
with a host-language implementation.

Functional tests must prove a complete user-visible feature through its stable
application interface. End-to-end tests must prove the installed system,
including editor submission, tokenized storage, compilation or execution,
runtime behavior, and observable result.

System contract tests must prove properties of the assembled and linked system
that do not belong to one callable routine or one user feature. This category
includes toolchain, linker, memory-map, generated-table, binary-artifact,
banking/vector, resource-budget, snapshot, and cross-artifact consistency
contracts.

Tests must run in the fidelity order defined in `docs/TESTING.md`:

1. host unit, format, static, and generated-artifact tests;
2. local 6502 emulator routine tests;
3. local emulator integration tests with geoRAM;
4. VICE snapshot-backed application tests using direct editor-buffer injection;
5. focused VICE keyboard, IRQ, timer, device, and hardware tests.

A higher layer must not duplicate behavior already proven below unless it is
testing integration unique to that layer.

A stable subset of unit, integration, functional, system contract, and
end-to-end tests must be marked `smoke`. Smoke status selects existing
authoritative tests; it must not create a second weaker implementation of the
same test.

Every regression test must be classified as a previously untested edge case of
an existing unit, integration, functional, system contract, E2E, or hardware
behavior. It must extend the existing owning suite, case table, or canonical
module for that behavior. Regression work must not create an ad hoc test
category, directory, marker, top-level test file, or bug-number-specific suite.

When a test is added with a current bug fix specifically to prevent that defect
from returning, the authoritative test case may also be marked `smoke` within
its normal category. The `smoke` marker is additional selection metadata; it
does not replace the test's scope, environment, language-profile, or mode
classification.

The local emulator can execute 6502 entry points, inspect registers and memory,
model C64 banking/ROM overlays, and model persistent geoRAM window selection.
It does not schedule real IRQ/NMI execution and is not proof of CIA, VIC,
keyboard-scan timing, IEC, or cycle-exact hardware behavior.

VICE testing must:

- prove the real keyboard-to-editor path in a small dedicated suite;
- use atomic direct injection into the editor mailbox/input buffer for the
  remaining language suite;
- test timer IRQ and keyboard scanning independently;
- begin normal tests from a fingerprinted snapshot of a freshly loaded and
  installed BASIC3 environment;
- reject stale snapshots when build artifacts or startup configuration change;
- restore isolation between tests;
- wait for observable state transitions rather than relying on long sleeps.

### 13.1 Critical Language E2E Matrix

Critical language E2E tests must be organized along three dimensions:

- language profile: BASIC V2, BASIC V3, BASIC V3.5, and IEEE extensions;
- execution mode: immediate, stored-program, and explicit compile mode;
- language kind: statements and functions.

The canonical pytest modules are:

```text
tests/e2e/test_e2e_basicv2_functions.py
tests/e2e/test_e2e_basicv2_statements.py
tests/e2e/test_e2e_basicv3_functions.py
tests/e2e/test_e2e_basicv3_statements.py
tests/e2e/test_e2e_basicv35_functions.py
tests/e2e/test_e2e_basicv35_statements.py
tests/e2e/test_e2e_basicv3_functions_ieee.py
tests/e2e/test_e2e_basicv3_statements_ieee.py
```

Each module must use named semantic cases and a shared execution-mode
parameter. For example, the BASIC V2 function module must cover the complete
required function surface, including `SGN`, `ASC`, and `SPC`, in immediate,
stored-program, and compile modes wherever the syntax is legal.

Every implemented keyword and operator in the token/keyword manifest must map
to at least one critical E2E semantic case. Syntax modifiers such as `TO`,
`THEN`, or `STEP` are tested through the statement forms that consume them.
A generated coverage check must fail when an implemented keyword has no
collected E2E case.

Mode restrictions are themselves required behavior. A direct-only statement
has an immediate-mode success case and explicit stored-program/compile rejection
cases rather than being silently omitted from those modes.

The matrix must report missing, unsupported, and not-applicable cells
explicitly. Empty coverage must not appear as a passing profile.

### 13.2 Stock Semantic Reference Results

Every critical E2E keyword case must have reference provenance. Assertions for
all stock-compatible BASIC V2 and BASIC V3.5 keywords must be derived from
observed VICE runs against unmodified stock BASIC:

- BASIC V2 cases use VICE C64 emulation with stock C64 BASIC V2 and KERNAL;
- BASIC V3.5 cases use VICE Plus/4 emulation with stock Plus/4 BASIC V3.5.

Reference runs must cover immediate and stored-program forms where the stock
dialect permits them. Compiler 2 immediate and program results are compared
with the corresponding stock form. Compiler 2 compile-mode results are compared
with the stock stored-program result because stock BASIC has no compile mode.

Every keyword case must record its reference machine, dialect, source text,
VICE version, ROM identity, raw observation, normalized semantic result, and
regeneration fingerprint.

Stock BASIC V2 and implemented BASIC V3.5 expected-result fixtures may be
generated once for the lifetime of the project because the selected stock ROM
semantics are immutable. They must not be regenerated merely because Compiler
2 changes. New fixture cases may be generated when additional edge cases are
discovered. Existing fixtures may be regenerated only for a reviewed oracle,
ROM-identity, generator, normalization, or fixture-schema correction, with the
reason recorded in the change.

Plus/4 BASIC V3.5 is a semantic reference, not a binary-format reference.
Machine-specific screen, memory, color, and token differences must be retained
in raw observations and excluded only by documented normalization.

Compiler 2-only BASIC V3 and IEEE keywords have no stock equivalent. Their
stock-numeric-mode behavior and inherited operands/errors must still be
compared with the appropriate stock reference. Extension-specific results must use the
normative Compiler 2 specification and, for IEEE operations, an independent
IEEE oracle. A stock `?SYNTAX ERROR` for an extension token is provenance, not
the expected extension result.

VICE observations are the final source of truth for C64 and Plus/4 emulation
behavior used by these fixtures. Source listings, labels, and ROM reports are
used to explain and implement behavior, but accepted assertions are grounded in
documented VICE runs.

## 14. Acceptance Traceability

Every requirement above must map to one or more named tests. A generated
requirements matrix must report:

- requirement ID;
- implementation component;
- test nodes at each applicable layer;
- last passing build;
- unsupported or planned status.

No feature is complete solely because a static source-pattern test passes.
