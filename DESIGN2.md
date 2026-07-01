# Compiler 2 Design

## 0. Role of This Document

`REQUIREMENTS.md` is the authority for required behavior. This document
describes one implementation that satisfies those requirements. Where this
document and `REQUIREMENTS.md` disagree, `REQUIREMENTS.md` wins.

This file is the top-level design index. Several subsystems already have a
focused design document; this file states the architecture that ties them
together, fills the sections that have no dedicated document yet, and shows
how every requirement section is satisfied. Section numbers below match the
corresponding `R<n>` requirement group in `REQUIREMENTS.md`.

| Requirement group | Design coverage |
|---|---|
| R2 Product / R2.1 Phase 1 | §1, §2 (this document) |
| R3 Language Compatibility | §3 (this document), `docs/KEYWORDS.md`, `docs/MANUAL.md` |
| R4 Direct and Program Modes | §4 (this document) |
| R5 Tokenized Program Compatibility | §5 (this document) |
| R6 Compilation and Runtime | §6 (this document), `docs/INCREMENTAL_COMPILATION.md`, `docs/COMPILE_EXPORT.md` |
| R7 Memory and Arenas | §7 (this document), `docs/MEMORY_BUDGETS.md`, `docs/GRAPHICS_MEMORY.md` |
| R8 geoRAM | §8 (this document), `docs/GEORAM_BANKING.md`, `docs/GEORAM_LOADER_DESIGN.md` |
| R9 Editor and Interrupts | §9 (this document), `docs/EDITOR.md`, `docs/DOS_WEDGE.md` |
| R10 KERNAL | §10 (this document), `docs/KERNAL_ABI.md` |
| R11 Optimization | §11 (this document), `docs/LOOP_OPTIMIZATION.md` |
| R12 Robustness and Observability | §12 (this document) |
| R12.1 Build Toolchain | §13 (this document), `docs/BUILD.md`, `docs/GENERATED_REFERENCE.md`, `docs/VICE_TOOLS.md` |
| R13 Test Hierarchy | §14 (this document), `docs/TESTING.md`, `docs/CANONICAL_TESTS.md` |
| R14 Acceptance Traceability | §15 (this document), `docs/TRACEABILITY.md` |
| Cross-cutting: zero page | §16, `docs/ZERO_PAGE.md` |
| Cross-cutting: IEEE 754 | §17, `docs/IEEE754.md` |

A document map is repeated at §18.

## 1. Product Architecture (R2)

Compiler 2 is a native 6502 compiler and interactive BASIC environment for a
Commodore 64 with geoRAM. The system is partitioned into five cooperating
layers:

1. **Resident foreground** — the smallest possible set of always-RAM-resident
   code: the IRQ keyboard/jiffy handler, a bounded screen/cursor front end,
   the editor line-capture mailbox, the RAM-under-I/O gate, the KERNAL bridge,
   and the geoRAM call gate (see §8, §9, §10).
2. **geoRAM-resident services** — editor tokenization/detokenization/listing,
   the compiler pipeline (lexer through code generation), diagnostics
   formatting, transcendental math, and cold variable/array/string storage
   (see §6, §7).
3. **Compiled program runtime** — the documented runtime ABI invoked by
   emitted native code: scalar/array access, string operations, arithmetic,
   control flow, STOP/CONT, and I/O (see §6.3).
4. **geoRAM arena and overlay manager** — typed, generation-stamped arenas for
   tokenized programs, compiled images, variables, arrays, strings, compiler
   IR, overlay dispatch, and scratch/diagnostics (see §7.4).
5. **Build and verification system** — the host-side generator/validator
   pipeline that turns checked-in manifests and `ca65`/`ld65` output into a
   reproducible, contract-checked release (see §13, §14).

Layer 1 is the only code that may run with arbitrary geoRAM page selection
state, arbitrary CPU banking transitions in progress, or during another
layer's critical section. Layers 2-4 always run with the canonical `$01=$35`
mapping (§7.1) and a stable, gate-owned geoRAM selection (§8.5). This
partition is what allows long compiler, math, and overlay-call work to run
with interrupts enabled (R9) without the IRQ ever depending on geoRAM page
state.

The minimum supported geoRAM size is 512 KiB (eight 64 KiB blocks). The build
records the declared minimum and the detector's measured capacity in
`build_manifest.json`; larger devices increase arena capacity only, never
language semantics (§8.2).

Failure to find usable geoRAM, or a geoRAM capacity below the declared
minimum, must abort installation before any arena, editor, or compiler state
is trusted. The Phase 1 loader (§2) is the only code that runs before
detection succeeds.

Installation records a geoRAM profile containing the detected capacity,
aliasing result, and integrity fingerprint. Later gate and arena integrity
checks compare against that profile. Corrupt arena metadata, failed page
checks, or an unexpected device/capacity/aliasing change enters one clean
fatal-error path: stop geoRAM execution and allocation, restore the selected
page, CPU mapping, and interrupt state, report the failure, and require
reinstallation. The system never silently shrinks, remaps, or continues using
pages under a changed profile.

## 2. Phase 1 Install and Editor Slice (R2.1)

Phase 1 produces an installable D64 image (`docs/BUILD.md`, §13) whose
loadable PRG starts with the stock BASIC loader line:

```basic
2026 SYS2061
```

`SYS2061` (`$080D`) is the entry point of the host-built loader described in
`docs/GEORAM_LOADER_DESIGN.md`. The loader:

1. detects geoRAM presence/capacity non-destructively (`docs/GEORAM_BANKING.md`
   Detection);
2. rejects absent or undersized geoRAM with a clean, documented error and
   does not enter the editor;
3. installs the RAM payload (decompressing it if the build used
   `-UseCompressor`) to its runtime locations, and loads the `GEORAM` file
   from disk into the geoRAM page image;
4. restores ROM/I/O banking to the canonical runtime mapping;
5. jumps to `compiler_init`, which performs first-time arena construction and
   enters the interactive editor.

The build-system payload object is named `georam.bin`; D64 packaging
materializes it as the Commodore filename `GEORAM`, and the host PRG is
packaged as `BASICV3`. A system contract test (`docs/BUILD.md` Packaging)
asserts these two names stay consistent between the build manifest and the
D64 directory.

The Phase 1 editor/runtime slice supports exactly the surface needed to
enter, list, save, load, and run the bootstrap benchmark:

```basic
10 B=TI
20 FORX=1TO1000
30 NEXT
40 A=TI
50 PRINTA-B
```

That requires: numbered-line entry through the transactional submission path
(§9.2); canonical tokenized storage (§5); `RUN`, `LIST`, `NEW`; immediate `?`
and `PRINT` of numeric scalars and `TI`; immediate `LOAD`/`SAVE`; numeric
scalar variables; `TI`/`TI$` including assignment; and the direct integer
`FOR`/`NEXT` fast path (`docs/LOOP_OPTIMIZATION.md`) sufficient to meet the
sub-60-jiffy Phase 1 performance requirement (§11).

Phase 1 deliberately exercises every cross-cutting mechanism the rest of the
system depends on — geoRAM detection, the RAM-under-I/O gate, the KERNAL
bridge, the IRQ-owned jiffy clock, transactional line submission, and the
direct loop fast path — at minimum scope, so later phases extend proven
machinery instead of replacing it.

## 3. Language Compatibility and Dialect Model (R3)

### 3.1 Compatibility Surface

For stock syntax, Compiler 2 must be semantically compatible with C64 BASIC
V2 except for the direct-mode restrictions in §4. The required stock keyword,
operator, and function surface is the list in `REQUIREMENTS.md` §3.1; the
per-keyword behavioral reference is `docs/KEYWORDS.md`, and the user-facing
description (including DOS wedge, BASIC 3/3.5 extensions, and IEEE mode) is
`docs/MANUAL.md`. Omission of a keyword from `docs/KEYWORDS.md` never reduces
the BASIC V2 compatibility requirement — it only means the reference entry is
missing and must be added.

Stock behavior is checked against the rebuildable ROM source tree
(`c64rom`), which builds byte-identical BASIC `901226-01` and KERNAL
`901227-03` and exposes source-derived labels and API/ZP reports
(`docs/KERNAL_ABI.md`, `docs/ZERO_PAGE.md`). VICE observation is the final
behavioral oracle (`docs/CANONICAL_TESTS.md`); a disagreement between the
source-derived expectation and an observed VICE run is an oracle issue that
must be resolved, not silently picked one way.

`docs/BASIC_COMPATIBILITY_LIMITS.md` is the implementation contract for stock
edge limits: line-number range, tokenized-line form, editor logical-line
length, variable-name canonicalization, string length, byte and address
coercion, arrays, logical files, devices, secondary addresses, filenames, and
input fields. Parser, runtime, editor, KERNAL bridge, and E2E tests consume
that table as a manifest of required edge behavior rather than treating
"BASIC V2 compatible" as an informal blanket statement.

The implementation divides the compatibility surface into generated
lexical/token tables, the typed expression and value layer, scalar/array/string
descriptors, control-flow and continuation descriptors, KERNAL-backed I/O,
and one BASIC error/unwind path. Every stock keyword in the required manifest
maps to those shared mechanisms rather than carrying a private approximation
of coercion, lifetime, or error behavior. The error path preserves the same
observable program and device state that the applicable stock VICE fixture
records.

`PEEK`, `POKE`, `SYS`, `USR`, and `WAIT` operate on the real C64 CPU address
space. The build generates the documented protected Compiler 2 ranges from
the linker/arena policy, and the runtime applies protection only to those
ranges; a standalone export has no hidden development-environment ranges.

### 3.2 Dialect and Mode Gating

A single dialect/mode state machine governs which token set the tokenizer
accepts:

- **Dialect**: `BASIC2` (default at cold start) or `BASIC3.5`. Selected only
  by the direct-mode-only commands `BASIC2` / `BASIC3.5`, and inspectable
  through `BASIC()`.
- **Numeric mode**: legacy (default) or IEEE, selected by `FPMODE0` /
  `FPMODE1`, inspectable through `FPMODE()`. Numeric mode is independent of
  dialect — IEEE functions are reachable regardless of `BASIC2`/`BASIC3.5`
  selection, and structured-loop tokens are gated by dialect alone.

While `BASIC3.5` mode is disabled, the structured tokens (`ELSE`, `DO`,
`LOOP`, `EXIT`, `UNTIL`, `WHILE`) must tokenize to `?SYNTAX ERROR`, exactly as
stock BASIC V2 would treat an unrecognized identifier sequence. The tokenizer
therefore consults the active dialect before accepting an extended token, not
only at parse time — a line typed in BASIC2 mode is never silently stored
with extended tokens that later "activate" if the dialect changes.

### 3.3 Loop Family Co-Design

`docs/LOOP_OPTIMIZATION.md` defines one loop-descriptor model shared by
BASIC V2 `FOR`/`NEXT`/`STEP`/`TO` and BASIC 3.5 `DO`/`LOOP`/`WHILE`/`UNTIL`/
`EXIT DO`/`EXIT FOR`. Even before BASIC 3.5 tokens are enabled, the parser,
control-flow descriptors, loop stack model, invalidation rules, runtime ABI,
and optimizer eligibility checks must already represent both families. This
is enforced structurally: the loop-descriptor `kind` field (§ Loop
Descriptors in `docs/LOOP_OPTIMIZATION.md`) already enumerates `FOR`, `NEXT`,
bare `DO`, pretest `DO`, posttest `LOOP`, and `exit`, and the generic runtime
frame is shared by both families from Phase 1 onward.

### 3.4 Extensions

`REQUIREMENTS.md` §3.2 lists the required BASIC 3 gateway surface
(`BASIC2`, `BASIC3.5`, `BASIC()`, `COMPILE`, `FPMODE0`, `FPMODE1`,
`FPMODE()`) and the opt-in BASIC 3.5/7 structured subset. IEEE functions and
any further extension marked **implemented** in `docs/KEYWORDS.md` are
required; entries marked **planned** are not counted as supported and must be
visibly distinguished in both `docs/KEYWORDS.md` and the generated
requirements matrix (§15). Existing accepted extension compatibility cases
remain regression requirements when the implementation changes; a redesign
may replace their mechanism but not their observable behavior.

## 4. Direct and Program Mode Classification (R4)

The parser classifies command context — direct or stored-program — before
compiling or executing a statement, using one generated table rather than ad
hoc per-statement checks scattered across the front end. The direct-only
command set is exactly the `REQUIREMENTS.md` §4 table:

| Group | Commands |
|---|---|
| Program/session | `NEW`, `RUN`, `CONT`, `CLR`, `LIST`, `COMPILE` |
| File program management | `LOAD`, `SAVE`, `VERIFY` |
| Dialect/policy | `BASIC2`, `BASIC3.5`, `FPMODE0`, `FPMODE1` |
| DOS wedge | `$`, `/`, `@`, `!` |

A direct-only command typed into a stored program line produces a
BASIC-compatible syntax error at tokenize/validate time (the same
transactional step that line submission already performs, §9.2). It is never
compiled as a no-op, and it is never silently accepted and later rejected
only at `RUN` time — rejection happens at line-commit time so the editor
state stays consistent with what would actually run.

`RUN` supports the stock bare and line-number forms. `LIST` supports the
stock range forms once an early milestone's bare-`LIST`-only restriction is
lifted; the milestone restriction itself is recorded as a test-matrix `not
applicable` cell (§14.2), not a silent omission.

All other stock statements work identically in stored programs and in direct
mode wherever stock BASIC V2 itself permits direct execution — the
direct/program classifier does not invent new restrictions beyond the table
above.

DOS-wedge prefixes (`docs/DOS_WEDGE.md`) are editor commands recognized by the
input front end before tokenization, not tokenized program statements; they
cannot appear in a stored line at all, so they need no separate
program-mode-rejection path. Wedge device-selection commands (`@8`-`@11`)
write the same KERNAL file-device byte `fa` (`$BA`, `docs/KERNAL_ABI.md`)
used by `LOAD`, `SAVE`, and `COMPILE`'s default-device resolution, so device
selection made through the wedge is visible to every subsequent defaulted
file command, including a bare `COMPILE`.

`LOWMEM` does not exist in Compiler 2; the arena and variable-management
design in §7 is required to make a user-selectable low-memory policy
unnecessary.

## 5. Tokenized Program Compatibility (R5)

Stock-only saved programs are binary compatible with C64 BASIC V2: PRG load
address `$0801`, stock linked-line records, little-endian next-line pointers
and line numbers, unmodified stock token byte assignments, a zero byte
terminating each line, a zero link terminating the program, and stock
`DATA`/`REM`/quote tokenization rules. Materializing a program for `SAVE`
always relinks line pointers canonically rather than trusting any pointer
value carried over from `LOAD` or in-memory editing — the canonical-save test
loads a stock PRG, saves it unmodified, and compares the resulting token
stream and line structure byte-for-byte with the stock loader's own output.

Programs containing extended (BASIC 3/3.5/IEEE) keywords are exempt from
stock binary compatibility, but their encoding must still be:

- **versioned** — every extended-token program carries a format/ABI version
  the loader checks before trusting the encoding;
- **unambiguous** — an extended opcode byte is never reused for a stock
  token meaning;
- **round-trippable** — load then save reproduces the same semantic program;
- **non-corrupting on version mismatch** — loading an unsupported extension
  version reports an error rather than misinterpreting the bytes as a
  different, plausible-looking program.

The loader classifies a file as stock or extended before decoding any
extension token. An extended program carries a magic and format version in a
versioned envelope that cannot be mistaken for a stock linked-line record;
extension token IDs live in that envelope's namespace and never remap a stock
token byte. Validation completes in scratch storage before the canonical
program directory is replaced, so an unknown or malformed extension version
leaves the current program intact.

Internally, the geoRAM-resident tokenized-program arena (§7.4) may store
lines as handles or indexes rather than literal linked records, but `LOAD`,
`SAVE`, `LIST`, and every compatibility test observe only the canonical
BASIC V2 linked-line form (or its versioned extended-token superset) — the
internal representation is invisible at every external boundary.

## 6. Compilation and Runtime (R6)

### 6.1 Pipeline Boundaries

Compilation has eight explicit, inspectable boundaries, each with a versioned
serialization suitable for replay in host tests:

1. canonical tokenized source;
2. lexical/statement records;
3. symbols and variable descriptors (`docs/LOOP_OPTIMIZATION.md` Stable
   Variable Descriptors);
4. control-flow and loop descriptors (`docs/LOOP_OPTIMIZATION.md` Loop
   Descriptors);
5. typed intermediate representation;
6. optimized intermediate representation;
7. emitted code, relocations, and runtime dependencies;
8. installed compiled image.

Compilation is deterministic for identical source, options, and build
version: the same boundary inputs always produce the same boundary outputs,
which is what allows the host-side compiler tests to replay any one boundary
without driving the whole pipeline. Failed compilation identifies the phase,
source line, and error class, and leaves every already-published boundary
output untouched (this composes with the per-line transactional rule in
§6.2).

### 6.2 Incremental Compilation

Numbered-line entry follows the transactional sequence in
`docs/INCREMENTAL_COMPILATION.md`: capture, tokenize into scratch storage,
validate syntax/dialect, compile into a scratch compiled record, update
dependency fingerprints, resolve relocations and cross-line dependencies,
validate code layout, then publish source and compiled records together. Any
step failing leaves the previously stored line and published compiled cache
valid and unchanged. Deleting a line removes its source record, rebuilds or
invalidates every affected branch/`DATA`/loop/subroutine record, and publishes
the resulting generation atomically, never as a sequence of partially-applied
edits.

Per-line compiled records are cache entries keyed by source generation,
dialect, IEEE mode, runtime ABI version, branch-target-table generation,
`FOR`/`NEXT`-`DO`/`LOOP`-`GOSUB`/`RETURN` metadata generation, `DATA`-order
generation, variable-descriptor generation, and code-layout generation. A
purely local edit republishes only the changed line when every fingerprint
above is still valid; a structural edit (one that can move branch targets,
reorder `DATA`, or change a descriptor) dirties the dependent lines or
triggers a whole-program relink. There is no interpreter fallback path —
"not yet recompiled" is a state the publication rule (§6.2.1) refuses to
execute, not a state that downgrades to interpretation.

Immediate mode reuses the same machinery: a direct command is wrapped as a
one-line temporary program, compiled through the full pipeline, executed,
and discarded. This gives the project exactly one compiler path for stored
execution, direct execution, and per-line compile-on-entry, which is also
why the dialect/mode gating in §3.2 and the direct/program classification in
§4 must be checked before the temporary program is even constructed.

Keyword recognition during tokenization uses one generated
first-character-indexed trie, not a linear rescan of the keyword table per
candidate token. Accepting states carry token ID, dialect mask, abbreviation
policy, and longest-match metadata so stock abbreviations and extension gating
do not require a fallback table scan. Lookup cost is bounded by the candidate
length plus the generated node-transition bound. Every build emits
`keyword_lookup_report.json` with table bytes, maximum depth/fan-out, and
measured lookup/line-tokenization timing so a representation or placement
regression is visible before the editor misses the ~0.5-second responsiveness
target.

#### 6.2.1 Publication Rule

Compiled code is executable only after all dirty records are resolved, code
layout is verified, and the compiled-image checksum matches the current
source generation. A program with any unresolved dirty record cannot be
`RUN`; the failure path reports the offending phase/line and otherwise
leaves the last valid compiled state intact.

### 6.3 Runtime ABI

Compiled code depends only on the documented runtime ABI — never on private
compiler workspace addresses, physical geoRAM page allocation, or editor
state. The ABI covers:

- scalar and array resolution, load, store, and type promotion;
- string allocation, assignment, slicing, comparison, and reclamation;
- numeric arithmetic and comparisons;
- control flow, loop frames, STOP, and CONT state;
- screen, keyboard, channel, and file I/O (through the KERNAL bridge, §10);
- BASIC error construction and unwind;
- geoRAM-backed math calls where the active numeric/dialect profile selects
  them.

Indirection through the ABI is what lets the geoRAM-resident compiler
(layer 2, §1) evolve, and what lets `COMPILE` (§6.4) re-link the same emitted
code against a normal-RAM-only runtime profile instead of the geoRAM-backed
development profile.

### 6.4 COMPILE Export

`COMPILE` produces an independent, stock-compatible compiled PRG per
`docs/COMPILE_EXPORT.md`:

```text
COMPILE ["filename" [,device]]
```

Defaults: filename `COMPILED`, device = current disk device (`fa` at `$BA`,
shared with `SETLFS`/`LOAD`/`SAVE`/DOS-wedge device selection, §4, §10).
Supported current disk devices are 8 through 11. Installation preserves the
device from which the environment was loaded rather than forcing device 8, so
a system loaded from device 9 defaults a later bare `COMPILE` to device 9.
The export contains a stock BASIC V2 loader line, native compiled code,
required runtime helpers, resolved relocation/version metadata, variable
descriptors needed for runtime and direct inspection, and the standalone
direct-mode environment — and nothing that depends on the Compiler 2 editor,
compiler workspace, source arena, installed environment, or geoRAM.

**Stock memory budget.** With the standard loader line `2026 SYS2061`, the
standalone payload starts at `$080D`; the longest possible contiguous
compiled payload therefore ends at `$CFFF`. The compiler reports and enforces

```text
standalone_code_budget = standalone_loader_bytes + compiled_program_bytes
```

`compiled_program_bytes` includes user code, required runtime helpers,
relocation/runtime metadata, variable descriptors, the standalone direct-mode
environment, and every other byte loaded as part of the standalone image.
Tokenized source is excluded and never counts against this budget. The
installed development environment may cache the compiled image in geoRAM, but
that cache is accepted only if the same bytes would fit the standalone budget
— "works in the geoRAM-backed dev environment" is never sufficient on its
own; `COMPILE` re-validates the budget at export time and rejects an oversized
program rather than truncating or partially exporting it.

The tokenized source arena may grow independently in geoRAM. Any normal-RAM
materialization of the compiled cache is still limited to the loader-accounted
`$0801` image with payload in `$080D-$CFFF`; geoRAM does not create a second,
larger executable-image profile.

Variable/array/string/stack/direct-mode working storage is budgeted separately
from the code image and must fit in normal RAM remaining after the exported
PRG loads. A graphics-mode export may use `$D000-$D7FF` RAM beneath I/O only
through the documented banking gates (§7.2) and only when the graphics layout
in `docs/GRAPHICS_MEMORY.md` permits it.

**No source.** The compiled PRG carries no tokenized source. `LIST` in the
standalone environment shows only the exact loader stub `2026 SYS2061`; it
never reconstructs or decompiles BASIC source.

**Standalone direct-mode environment.** After normal `END`, `STOP`, STOP-key
interruption, or a BASIC error leaves runtime state valid, the export returns
to `READY.` in a restricted source-free environment. A generated command table
and parser accept:

```basic
?A
PRINT A
?A(N)
PRINT A$(N)
CONT
LIST
RUN
LOAD
SAVE
VERIFY
CLR
```

The term after `?`/`PRINT` is exactly one numeric or string scalar, or one
numeric or string array element. The same dispatcher also accepts every `$`,
`/`, `@`, and `!` DOS wedge form required by `docs/DOS_WEDGE.md`. `LOAD`,
`SAVE`, `VERIFY`, and wedge operations go through the standalone KERNAL bridges
and share `fa` at `$BA`; device-selection wedges therefore affect later
defaulted file commands. `RUN` re-enters the current compiled image through
its normal initialization entry, while `CLR` clears runtime variables,
arrays, strings, loop/subroutine frames, and continuation state without
requiring source.

Assignment, compound expressions, numbered-line entry, program editing, and
arbitrary BASIC statements outside this command table are rejected by the
restricted grammar. `LIST` has only the loader-stub behavior above. `CONT`
resumes from a valid STOP-keyword or STOP-key state using only the compiled
continuation frame, runtime state, and variable arenas; it has no source
dependency.

Export system tests parse the PRG and dependency manifest to prove the complete
`$0801-$CFFF` load range, absence of geoRAM/editor/source dependencies, and
separate code/workspace budgets. Stock-C64 VICE tests with geoRAM disabled
cold-load the export, run it through the loader stub, reach the post-run
environment after end/stop/error, inspect numeric/string scalar and array
state, exercise `CONT`, `LIST`, `RUN`, `LOAD`, `SAVE`, `VERIFY`, `CLR`, and
every wedge family, verify `fa` device propagation, and prove that assignment,
compound expressions, editing, and arbitrary statements are rejected.

## 7. Memory and Arena Requirements (R7)

### 7.1 Nominal CPU Memory Map

Normal editor and compiled-runtime operation uses exactly one canonical CPU
banking state, `$01 = $35` under the standard DDR:

| Address range | Normal mapping |
|---|---|
| `$0000-$CFFF` | RAM, except 6510 port registers at `$0000-$0001` |
| `$D000-$DFFF` | I/O, including the geoRAM window/registers |
| `$E000-$FFFF` | RAM, KERNAL and BASIC ROM banked out |

Ordinary runtime, editor, compiled-code, and geoRAM-call paths never save or
change this mapping. The only two permitted transitions are the
RAM-under-I/O gate (temporarily exposes RAM at `$D000-$DFFF`,
`docs/GRAPHICS_MEMORY.md` CPU Banking Consequences) and the KERNAL bridge
(temporarily exposes KERNAL ROM at `$01=$36`, §10). Both gates mask
interrupts only for their bounded critical section, perform a fixed/validated
transfer or call, and restore `$35` and the incoming interrupt state before
returning. Debug builds assert `$35` at every public entry/exit boundary
that is not itself inside one of these two gates.

RAM `$FFF9-$FFFF` is reserved: `$FFF9` is a project high-memory guard byte,
and `$FFFA-$FFFF` are the NMI/RESET/IRQ-BRK hardware vectors.

### 7.2 Graphics Memory Contract

`docs/GRAPHICS_MEMORY.md` is authoritative. Summary: bitmap pixels occupy
`$E000-$FF3F` (8000 bytes, ordinary RAM under the canonical mapping); the
bitmap screen/color matrix occupies `$DC00-$DFE7` (1000 bytes, reachable only
through the RAM-under-I/O gate because `$DC00` is CIA 1 while I/O is
visible); physical VIC-II color RAM remains `$D800-$DBE7`; `$FFF9-$FFFF`
stays reserved and is never bitmap data. VIC bank 3 (`$C000-$FFFF`) and
`$D018=$78` select this layout. Entering bitmap mode raises the bottom of
allocatable dynamic RAM to exclude `$DC00-$FF3F`; leaving graphics mode
restores stock text mode and colors and only then restores the text-mode
ceiling, after graphics-owned arena metadata is invalidated transactionally.
This restore is required on normal end, BASIC error, `STOP`, and STOP-key
interruption alike — there is exactly one graphics-exit path, reached from
all four triggers, not four separately maintained restore sequences.

### 7.3 Hard Memory Budgets

`docs/MEMORY_BUDGETS.md` is authoritative for the full byte-range accounting;
the standalone `COMPILE` budget (`$080D-$CFFF` payload, `$0801`-based loader
accounting) is detailed in §6.4. Strings are capped at 255 characters;
geoRAM-backed string payloads own one full geoRAM page per materialized
scalar string or array element and never span pages, while normal-RAM-backed
payloads (required so stock `COMPILE` exports work without geoRAM) provide
equivalent bounds/ownership/stale-handle checks without the page-sized
constraint.

Every string descriptor records payload storage class, bounds, ownership, and
lifetime/generation. String allocation, assignment, slicing, comparison,
reclamation, and standalone state inspection dispatch through that descriptor,
so none of those operations assumes that a payload is physically in geoRAM.

The following are geoRAM-backed by default and may move to a small resident
component only when measurement proves it necessary, with the byte delta
reported and justified (R2 optimization priority): editor parsing/line-edit
transforms, lexer/tokenizer, parser/semantic analysis, symbol/control-flow/
IR/optimization/codegen passes, diagnostics formatting, transcendental math,
tokenized program storage, compiled program storage, cold scalar
variables/arrays, and string payloads when the active profile has geoRAM.

### 7.4 Arena Model

Every arena declares: type and format version; capacity and allocation
metadata; page ownership and bounds checks; generation numbers for
stale-handle detection; explicit allocation-failure behavior; integrity
checks usable by tests; and deterministic reset/invalidation rules. At
minimum, separate ownership exists for: tokenized program; compiled images;
scalar descriptors and cold scalar payloads; arrays; strings; symbols and
compiler IR; overlay code and dispatch metadata; and scratch/diagnostics.
Arenas may share one physical free-page allocator, but each region's
integrity check must be able to detect corruption originating from another
region — sharing the allocator is a capacity optimization, not permission for
one arena's bug to silently corrupt another's data.

The pinned resident arena directory stores only enough information to find and
validate the full geoRAM-resident directory: format version, detected capacity,
allocator generation, directory block/page, checksum, and recovery status. The
full directory owns extents, high-water marks, free lists, per-arena
generations, and integrity metadata. This keeps resident bytes small while
still giving fatal/error paths a bounded way to decide whether geoRAM state can
be trusted.

Large objects are addressed by stable logical handles, never raw window
addresses, so the physical geoRAM page backing a handle can move (compaction,
arena rebalancing, or scratch-page reuse) without invalidating code that only
ever held the handle. All pages exposed by the installed supported geoRAM
profile may be assigned through the common allocator; there is no hidden
capacity reserve outside declared arena, overlay, allocator-metadata, or
scratch ownership. An unexpected capacity/profile change is a fatal integrity
event handled by §1, never an online resize.

Variable descriptors may point to geoRAM-backed payloads, normal-RAM payloads,
or a small resident scalar cache when measurement justifies the resident bytes.
Any resident scalar cache is explicitly tagged by descriptor and generation;
writes are write-through or marked dirty by contract, and program exit, BASIC
error, STOP, CONT invalidation, and eviction all use one tested flush path.
There is no implicit cache ownership that bypasses descriptor generation or
arena integrity checks.

## 8. geoRAM Requirements (R8)

`docs/GEORAM_BANKING.md` is authoritative for the hardware contract, native
call ABI, and selection-ownership rules; `docs/GEORAM_LOADER_DESIGN.md` is
authoritative for the install-time loader/build shape. Summary of the
load-bearing decisions:

- **Mapping independence**: selecting, reading, writing, or executing a
  geoRAM page never changes the CPU-port mapping (§7.1); the geoRAM window
  and registers are already visible under the canonical `$35` map.
- **Non-destructive detection**: the detector saves processor status,
  registers, selection, and probe bytes before touching candidate pages; verifies
  distinct persistence across two candidate pages; probes address-bit
  aliasing to bound capacity; restores every modified byte/selection/status
  and every saved register on success or failure; and runs a second pattern
  order in debug builds to catch floating-bus false positives. Capacity is
  accepted only if it meets the declared minimum (512 KiB, §1) and maps to a
  supported whole number of 16 KiB blocks.
- **Profile continuity and corruption failure**: the installed capacity and
  aliasing fingerprint are immutable for the session. Gate checks, arena
  generations, bounds, canaries/checksums, and optional page guards detect
  stale handles, corrupt metadata/data, bypassed selection ownership, or an
  unexpected hardware profile change and route them through the clean failure
  path in §1 before another page is trusted.
- **Selection ownership**: only the pinned geoRAM gate and approved
  diagnostics write `$DFFE`/`$DFFF`. The gate keeps a software mirror of the
  selected block/page; debug builds compare mirror against hardware at
  public-call boundaries, and a mismatch is treated as an integrity error
  (bypassed ownership), not a benign drift. IRQ/NMI handlers never select
  geoRAM, which is what keeps the foreground-selected page stable across
  interrupts and lets long native overlay routines run with timer/keyboard
  service enabled.
- **Indexed call directory**: routine IDs are grouped in 256s; each group has
  a generated 256-byte target-page array, 256-byte entry-offset array, block
  base/threshold descriptor, ABI metadata, and checksum. `georam_call_group_n`
  is a real returning call: assert canonical mapping, save caller
  block/page/registers, resolve and map the target, call it, capture result
  registers/flags, restore caller page/block *before* control returns into
  caller geoRAM code, restore the incoming interrupt state, return documented
  results. A tail transfer reuses or removes the current frame so the
  destination returns directly to the original caller; it is never an alias
  for a returning call. Nested calls and callbacks use the same fixed-depth
  context stack (sized from the generated overlay/callback call graph plus a
  safety margin), restore the caller's selected page, and detect overflow
  before changing the selected page.
- **Native routine constraints**: each routine fits in one selected page,
  enters only at a generated entry offset, returns/tail-transfers through a
  declared path, never falls through across `$DEFF`, and never self-modifies
  a shared read-only page. Routines needing more code are split at explicit
  call boundaries.
- **One default register ABI**: a declared per-routine input/output set,
  carry as the standard success/error signal, decimal mode clear at public
  boundaries, the incoming interrupt-enable state restored, and no
  undocumented preservation — a wrapper that claims to preserve a register
  must contain real preservation code plus a local-emulator test proving it.
- **Generated contracts and pinned interrupt code**: every routine ID has one
  generated ABI/placement record, and the build cross-checks every ID,
  directory entry, target page/offset, checksum, return kind, and call-graph
  edge against linked symbols. IRQ and NMI entries and everything they call
  are pinned in normal RAM and have no dependency on the selected geoRAM page.

### 8.1 Loader and Build Shape

The build produces `BASICV3` (BASIC-loadable PRG: loader plus normal-RAM
payload) and `GEORAM` (raw geoRAM page image). The compressed build mode
packs only `build/compile.bin` (the extracted RAM payload, via
`tools/extract_segments.py` / `tools/prepare_compressor_segments.py` /
`lzss_compressor.exe`), never the full linker output, and falls back to an
uncompressed PRG if the compressor cannot solve staging. `GEORAM` stays a
separate D64 file until the loader and compressor share a direct-to-geoRAM
compressed segment manifest — direct compressed streaming into geoRAM is a
future extension, not a current requirement. Install order: BASIC starts
`BASICV3` → loader detects geoRAM → RAM payload installs/decompresses →
loader loads `GEORAM` and copies pages into geoRAM → banking restored to the
canonical runtime state → jump to `compiler_init`.

## 9. Editor and Interrupt Requirements (R9)

### 9.1 Resident/geoRAM Split

The resident front end (`docs/EDITOR.md`) owns only timing-sensitive work:
IRQ keyboard scan and jiffy-clock service, cursor state needed for visible
editing, bounded current-line capture, and handoff to the geoRAM editor
service. The geoRAM service owns tokenization, detokenization, `LIST`, range
formatting, line insertion/deletion, diagnostics, and program-directory
maintenance. IRQ code never enters a geoRAM editor routine (consistent with
§8's selection-ownership rule); long editor services stay bounded and
measurable so timer/keyboard progress continues through them.

### 9.2 Transactional Line Submission

Line submission is transactional: tokenize and validate into scratch
storage, allocate or resize the destination record, commit the new program
directory atomically, and leave the old line intact on failure. This is the
same sequence detailed for compiled-record publication in §6.2 — tokenize/
validate/compile/fingerprint/publish — applied at the editor boundary that
triggers it.

### 9.3 IRQ Path

The pinned IRQ (`docs/KERNAL_ABI.md` IRQ Call Order) is resident, bounded,
and geoRAM-independent. Its fixed order is: select KERNAL+I/O mapping → call
`UDTIM` → bounded project cursor service → call `SCNKEY` → acknowledge CIA
interrupt state → restore mapping and registers → `RTI`. The foreground
editor drains input with `GETIN` and never calls `SCNKEY` or advances the
jiffy clock itself — those are exclusively IRQ-owned, which is what lets long
compilation and math operations (running in geoRAM, layer 2) proceed with
interrupts enabled without racing the foreground on keyboard or timer state.
The entry saves the interrupted CPU-port value and never writes the geoRAM
selection registers; exit therefore restores the exact interrupted CPU-port,
processor, and geoRAM context rather than assuming a fresh default context.

### 9.4 Stock Line-Editing Behavior

The editor preserves stock C64 line-editing behavior that affects programs:
logical-line length and wrapping, quote mode, insert/delete, cursor
movement, keyboard repeat, STOP polling, screen scrolling, color/output
behavior visible to BASIC programs, and canonical tokenization of `REM`,
`DATA`, quotes, abbreviations, and extended tokens — unless a documented
Compiler 2 extension explicitly applies.

### 9.5 DOS Wedge

`docs/DOS_WEDGE.md` is authoritative. The wedge is direct-mode only,
recognized by the input front end ahead of tokenization (§4), and follows
the Action Replay MK VI surface for `$`, `@`, `/`, and `!`:

- `$` / `@$`: directory listing to the current text screen, never loading
  over the BASIC program.
- `/name` / `/"name"`: absolute PRG load equivalent to
  `LOAD "name",device,1` against the current disk device.
- `@`: bare form prints the disk error channel; `@8`-`@11` write `fa` at
  `$BA` (same byte used by `SETLFS`/`LOAD`/`SAVE`/`COMPILE`, §4, §6.4, §10);
  other `@command` forms send a disk command and report status.
  Initialization, validation, rename, scratch, and new/format are staged
  implementation milestones; scratch and format require confirmation because
  they are destructive.
- `!name` / `!"name"`: streams a SEQ file's PETSCII bytes to the current
  text screen through the normal output path; STOP aborts streaming and
  closes the file.

There is no special screen-state restoration around wedge commands — a wedge
command that clears the screen, changes colors, scrolls, or moves the cursor
leaves that as the resulting editor screen state, by design.

## 10. KERNAL Requirements (R10)

`docs/KERNAL_ABI.md` is authoritative. All ROM calls pass through a
documented bank-safe bridge. The canonical runtime map has KERNAL ROM banked
out (§7.1), so an ordinary `JSR` to a jump-table address would execute RAM,
not ROM; a bridge therefore: (1) asserts the canonical `$35` entry mapping in
debug builds, (2) saves interrupt state and declared result registers,
(3) selects `$01=$36` (KERNAL+I/O visible, BASIC ROM still banked out),
(4) marshals documented register inputs, (5) calls the public jump-table
address, (6) captures returned registers/carry/zero as required,
(7) restores `$35` and the incoming interrupt state, and (8) returns only the
documented result. Bridges serialize use of shared KERNAL workspace; a
foreground bridge cannot be entered from IRQ, and the IRQ uses only its
explicitly approved KERNAL routines (`UDTIM`, `SCNKEY`, §9.3). While KERNAL
ROM is visible, hardware vectors come from ROM, so any bridge that permits
IRQ during the call must ensure the KERNAL RAM indirect vectors (including
`$0314`) reach the pinned bank-safe handlers — masking interrupts for an
entire blocking file call is not acceptable.

Each generated bridge contract names its input registers/flags, returned
registers/flags, complete KERNAL and project zero-page read/write set,
CPU-port and interrupt-state behavior, and whether it can block or enter
device-specific code. These sets are derived from the labeled `c64rom` source
and generated BASIC/KERNAL API and zero-page reports, not remembered
addresses. The zero-page interference generator adds an edge from every
project allocation live across a bridge or IRQ to the corresponding
source-derived clobber set.

The planned call surface (`READST`, `SETLFS`, `SETNAM`, `OPEN`, `CLOSE`,
`CHKIN`, `CHKOUT`, `CLRCHN`, `CHRIN`, `CHROUT`, `LOAD`, `SAVE`, `SETTIM`,
`RDTIM`, `STOP`, `GETIN`, `UDTIM`, `SCNKEY`) and their zero-page effects are
listed in `docs/KERNAL_ABI.md` and seed the zero-page allocator (§16). The
canonical file sequences are `SETNAM → SETLFS → LOAD` / `SAVE` for program
files and `SETNAM → SETLFS → OPEN → CHKIN/CHKOUT → CHRIN/CHROUT/READST →
CLRCHN → CLOSE` for channel I/O. Every error exit restores the default
channel as needed and restores the canonical CPU mapping; carry and KERNAL
error code convert to one documented BASIC error in a resident wrapper.
`fa` at `$BA` is simultaneously the stock `SETLFS` device byte and Compiler
2's persistent current-disk-device state (§4, §6.4); it is therefore modeled
as live across any direct command that relies on the current disk device, and
must never be reused as unrelated scratch while that state is meant to
persist.

## 11. Optimization Requirements (R11)

`docs/LOOP_OPTIMIZATION.md` is authoritative. The governing rule: every loop
has a correct generic implementation, and a fast path is selected only when
compiler-built descriptors prove the shorter implementation has identical
observable behavior — no fast path is ever chosen from source shape alone.

- **FOR/NEXT fast path** is eligible only when start/limit/step are proven
  integers of a supported width with nonzero step, the variable descriptor
  resolves to a stable accessible cell, body analysis finds no aliasing
  write/`POKE`/`SYS`/callback/`DIM`/`CLR`/bank change that could invalidate
  the cell, overflow/promotion behavior matches the generic path, `NEXT`
  naming is consistent with stock unnamed-`NEXT` rules, and nested-loop/
  error-unwind metadata is valid. Any failed condition selects the generic
  frame-based runtime helper instead.
- **DO/LOOP fast paths**: safe bare `DO`/`LOOP` always gets a direct native
  backedge; simple truthiness/scalar-comparison `WHILE`/`UNTIL` forms (in
  either pretest or posttest position) get a native branch with an explicit
  polarity field rather than scattered branch inversion. Complex
  expressions, function calls, mutable aliases, or invalidated operands fall
  back to generic expression evaluation.
- **Invalidation barriers** (treated conservatively unless a narrower proven
  effect exists): `POKE` into runtime/descriptor/banking/arena control
  storage, `SYS`/`USR`, KERNAL or user callbacks, `CLR`/`NEW`/`RUN`/program
  replacement, dynamic array allocation/redimensioning, unknown string
  compaction side effects, and error paths that can expose intermediate
  variable state. Dirty masks identify exactly which descriptor facts a loop
  body changes, and one shared eligibility predicate is consulted by every
  emitter — no emitter reproduces a partial copy of the check.
- **STOP/timer**: timer advancement stays IRQ-owned; fast loops never
  synthesize jiffy ticks. Long loops reach a bounded statement/iteration
  boundary that polls the bank-safe STOP bridge; polling cadence may be
  amortized, but STOP behavior and final visible variable state must match
  the generic path exactly.

The Phase 1 benchmark (§2) is the hard proof point: the compiled bootstrap
program must run in under 60 C64 jiffies, demonstrating the minimal
`FOR`/`NEXT`, numeric-scalar, `TI`, and `PRINT` runtime path beats stock C64
BASIC V2 on the project's own bootstrap workload. Outside Phase 1, compiled
programs should run faster than the corresponding stock interpreted program
for most non-extension cases, measured in CPU cycles (BASIC V2 against stock
C64 BASIC V2; BASIC 3.5 against stock Plus/4 BASIC 3.5, normalized by cycles
because clock speeds differ). There is no compiled-speed requirement for IEEE
extensions, the editor, or DOS wedge commands.

Every optimized form is differential-tested against the generic path in the
local emulator, against stock BASIC V2/3.5 where the syntax is stock, and
against VICE for IRQ/STOP/timer/banking behavior, covering positive/negative/
zero step, empty loops, integer-width edges, promotion, nesting, named and
unnamed `NEXT`, modified loop variables, arrays, `POKE`, `SYS`, errors,
STOP/CONT, and every `WHILE`/`UNTIL` polarity. Static tests prove descriptor
completeness and that every fast-path branch has an explicit fallback.
Benchmarks run only after semantic tests pass.

## 12. Robustness and Observability (R12)

### 12.1 Generated Source of Truth

The build, not hand-maintained source, is the source of truth for: routine
IDs and geoRAM placement (§8); dispatch and relocation tables; arena IDs and
layouts (§7.4); runtime ABI versions (§6.3); zero-page allocations and
interference edges (§16); exported test entry points; and resident/geoRAM
byte counts. The same validated artifacts generate `build/API.md`, containing
the current production callable surface and complete calling conventions, and
`build/MAP.md`, containing the current CPU/ZP/segment/geoRAM/arena/standalone
memory summary (`docs/GENERATED_REFERENCE.md`). Every generated output is
reproducible and checked for overlap, overflow, duplicate IDs, unresolved
references, incomplete contracts, inconsistent ranges, and stale versions as
part of the build order (§13).

### 12.2 Debug Build Support

Debug builds additionally support: arena canaries and checksums (§7.4);
poisoned scratch and zero page between calls (so a routine that reads
undeclared state fails immediately rather than by accident, §16); phase
artifact dumps at each compilation boundary (§6.1); geoRAM selection traces
(cross-checked against the gate's software mirror, §8); call-depth and
stack-watermark checks (especially for the geoRAM context stack, §8); and
deterministic fault injection for allocation and I/O failures, so error-path
behavior is exercised on demand rather than only by accident in production.
Release builds may drop these checks for size/speed, but must retain bounds
checks at untrusted handles and file/program format boundaries — release
status never removes the checks that protect against corrupt input.

### 12.3 Resident-Footprint Accountability

Per the lexicographic optimization order in `REQUIREMENTS.md` §1
(correctness, then minimize resident footprint, then maximize dynamic
storage, then minimize execution time), every change that increases
permanently resident normal-RAM code or state must report the byte delta and
explain why the new behavior cannot be geoRAM-backed (§7.3 lists the default
geoRAM-backed subsystems). This obligation is checked mechanically: the
generated `size_report.json` (§13) records resident and geoRAM byte counts
per build, and a system contract test compares successive builds' resident
footprint against the declared budget.

## 13. Build System (R12.1)

`docs/BUILD.md` is authoritative for toolchain, build order, artifacts, and
reproducibility; `docs/VICE_TOOLS.md` is authoritative for the D64/PETCAT
command recipes used by build and test tooling. Summary of load-bearing
points:

- **Toolchain**: `ca65`/`ld65` (cc65, baseline 2.19) are the only production
  assembler/linker. The canonical installed paths are
  `C:\Users\me\Documents\Coding Projects\tools\ca65.exe` and
  `C:\Users\me\Documents\Coding Projects\tools\ld65.exe`; actual tool paths
  and versions are recorded in the build manifest, and a version change is
  treated as a reproducibility change. VICE (`c1541.exe`, `x64sc.exe`,
  `xplus4.exe`, `petcat.exe`) is the packaging/reference toolset. All
  production C64 code is `ca65` assembly; Python host tools generate and
  validate artifacts but never become production code.
- **Entry point**: `powershell -ExecutionPolicy Bypass -File .\build.ps1`,
  with every external command running through one checked invocation helper.
  A nonzero result from any generator, `ca65`, `ld65`, validator, packager,
  or system test fails the build outright — no best-effort fallback, no
  continuing with a stale copied binary.
- **Build order** (12 steps): validate tool paths/versions → validate
  structured manifests/schemas → generate zero-page symbols and interference
  reports (§16) → generate routine IDs/geoRAM placement/call directories/
  arena constants/runtime ABI tables/test-entry exports and the keyword trie/
  lookup report (§8, §7.4, §6.3, §6.2) →
  generate the `ld65` configuration from checked-in linker policy plus
  generated geoRAM/page inventory → assemble each translation unit →
  link all objects → validate cross-artifact contracts → construct the
  installable PRG/loader manifest/D64 (§8.1) → compute size/resource reports
  (§12.3) → generate and validate `API.md`/`MAP.md`, then
  compute the final artifact fingerprint/manifest → run system contract tests,
  then the configured smoke/full test selection (§14). A generator-input change
  forces all dependents to rebuild; a clean build and an incremental
  no-change build must produce byte-identical final artifacts.
- **Linker policy**: the checked-in policy owns canonical banking
  assumptions (§7.1), pinned runtime/IRQ/NMI placement, RAM-under-I/O
  ownership, the `$FFF9-$FFFF` reservation, and segment alignment/maximum
  sizes; the generated configuration only adds the current geoRAM page
  inventory and generated segments. `ld65` fails on overlap, overflow,
  missing segments, unresolved symbols, or vector misplacement, and
  post-link validators cross-check map, labels, binary lengths, placement
  manifests, and embedded headers.
- **Required artifacts** under `build/`: `obj/`, `listings/`, `generated/`,
  `compiler.bin`, `georam.bin`, `basicv3.prg`, `compiler.map`,
  `compiler.lbl`, `compiler.d64`, `build_manifest.json`,
  `loader_manifest.json`, `routine_directory.json`, `arena_layout.json`,
  `runtime_abi.json`, `production_entries.json`, `test_entries.json`,
  `zp_allocation.json`, `size_report.json`, `keyword_lookup_report.json`,
  `API.md`, `MAP.md`, `requirements_matrix.json`, `requirements_matrix.md`.
  `API.md` and `MAP.md` are required on every build; `compiler.d64` is required
  for release/VICE installation tests but may be omitted from a narrowly
  selected developer build.
- **Packaging**: the release D64 stores `basicv3.prg` as Commodore filename
  `BASICV3` and `georam.bin` as `GEORAM` (§8.1), and packaging validates PRG
  load address/loader record, payload destination ranges, absence of
  load-time writes through visible I/O or ROM, geoRAM page order/padding/
  checksums, D64 directory contents, and agreement with
  `loader_manifest.json`. Compression is added only behind a versioned
  format with round-trip verification; uncompressed linked images remain
  authoritative for maps, symbols, and debugging.
- **Reproducibility**: `build/` is generated and safe to remove; `debug/`
  holds diagnostic captures and is never a release input. The build
  fingerprint covers all checked-in inputs, generated schema versions,
tool versions, build configuration, and final artifact checksums; VICE
snapshots and stock-reference fixtures record the applicable fingerprint
and a stale snapshot cannot be reused after a relevant build change (§14).
`API.md` and `MAP.md` do not embed their own checksum or the final fingerprint,
avoiding a hash cycle; `build_manifest.json` records both document checksums.

Build success is defined by the full system-contract suite passing
(toolchain/version contracts, deterministic generation, linker/memory-map
contracts, banking assumptions, map/listing/label/manifest consistency,
routine-directory and geoRAM image consistency, PRG/compiled-image/D64
formats, resource budgets, traceability, and absence of stale/undeclared
generated files) — producing `basicv3.prg` alone is explicitly not
sufficient. System contracts also prove every production entry appears exactly
once in `API.md` with a complete calling convention and every `MAP.md` range
and total agrees with the validated structured artifacts.

## 14. Test Hierarchy (R13)

`docs/TESTING.md` is authoritative; `docs/CANONICAL_TESTS.md` is
authoritative for fixture/regeneration policy. Summary:

### 14.1 Scope × Environment

Every test has an orthogonal **scope** (unit / integration / functional /
system contract / E2E) and **environment** (host-static / local 6502
emulator / local emulator with geoRAM / VICE snapshot-application / focused
VICE hardware). Markers compose freely (`integration` + `georam`, or `e2e` +
`vice` + `basicv2`) but never redefine scope.

Suites run in increasing fidelity order:

1. host unit, format, static, and generated-artifact tests;
2. local 6502-emulator routine tests;
3. local-emulator integration tests with geoRAM;
4. VICE snapshot-backed application tests using direct editor injection;
5. focused VICE keyboard, IRQ, timer, device, and hardware tests.

The local emulator can execute entry points, inspect registers/memory, model
ROM overlays and CPU banking, and retain geoRAM selection, but it does not
schedule real IRQ/NMI execution and cannot prove CIA/VIC/keyboard/IEC timing.
A higher layer repeats a lower-layer assertion only when the integration or
hardware behavior of that layer is itself the subject of the test.

System contract tests prove whole-build properties — toolchain/
reproducibility, linker/memory layout, banking/architectural policy,
generated metadata, binary artifact formats, cross-artifact consistency, and
resource/performance contracts (§12, §13) — and live in canonical modules
such as `tests/system/test_system_memory_map.py` and
`tests/system/test_system_banking_vectors.py`.

Every callable assembly subroutine appears in the production public-entry
manifest or the test-build entry manifest and has at least one direct unit
test covering nominal success, boundary values, each documented error
return, register/flag contracts, stack balance, zero-page reads/writes/
preservation, CPU banking and geoRAM selection, and arena bounds/generations/
rollback as applicable. A generated coverage check compares both manifests
against collected test metadata and fails collection on a gap.

Integration tests call one public entry and let it traverse multiple real
subroutines without replacing downstream assembly with a host-language
stand-in. Functional tests start at a stable feature boundary (line
submission, load/save, compilation, variable access, a BASIC operation) and
assert user-visible output/errors/state/persistence without a full cold boot
per case.

### 14.2 Critical Language E2E Matrix

E2E coverage is organized first by language profile (BASIC V2, V3, V3.5,
IEEE extensions), then functions vs. statements, with execution mode
(`immediate`, `program`, `compile`) as a shared parameter inside each module:

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

Each module uses named semantic cases whose IDs include profile, mode, keyword,
and case. The shared mode runner supplies `immediate`, `program`, and
`compile`; semantic expectations are not copied into three independent tests.
The BASIC V2 function suite covers the entire required surface, including
`SGN`, `ASC`, and `SPC` in every legal mode.

`compile`-mode cases must prove the installed compiled image actually ran
(§6.4) — reaching a generic direct/program path does not satisfy the cell.
Every implemented keyword/operator in the generated manifest must be
represented by at least one collected case (modifiers like `TO`, `THEN`,
`STEP` map into their containing statement's cases rather than standalone
invocations); direct-only statements (§4) get a positive immediate-mode case
and negative program/compile-mode cases. The generated matrix reports
`missing`, `unsupported`, and `not-applicable` cells explicitly, with a
machine-readable reason for the latter two; a profile with no collected
coverage cannot pass.

### 14.3 Reference Fixture Policy

Every critical E2E keyword case has reference provenance, generated from
clean stock VICE machines: BASIC V2 from `x64sc.exe` stock C64 BASIC V2/
KERNAL; BASIC 3.5 from `xplus4.exe` stock Plus/4 BASIC V3.5. Each fixture
records source text, execution mode, reference machine/dialect, VICE
version, ROM identity, raw observation, normalized result, and a
regeneration fingerprint. Stock V2/V3.5 fixtures are normally generated once
— immutable ROM semantics — and are **not** regenerated just because
Compiler 2 changes; regeneration is an explicit, reviewed operation for a
documented oracle/ROM-identity/generator/normalization/schema correction,
with the reason recorded.

Reference generation covers immediate and stored-program forms wherever stock
syntax permits them. Compiler 2 immediate/program results compare with the
corresponding stock form; Compiler 2 `compile` results compare with the stock
stored-program result because stock BASIC has no compile mode. Plus/4
machine-specific screen, memory, color, and token differences remain in the
raw fixture and are removed only by documented normalization.

Compiler-2-only BASIC 3/IEEE keywords have no stock equivalent; their
extension-specific results are compared against the normative Compiler 2 spec
and, for IEEE, an independent IEEE oracle (§17). Their legacy-mode behavior
and any inherited operand, coercion, or error behavior still compare against
the appropriate stock reference. A stock `?SYNTAX ERROR` for an extension
token is provenance that the token is unrecognized by stock BASIC, not the
expected extension result.

### 14.4 VICE Layers

Layer 4 (snapshot-application) starts every normal language/application test
from a fingerprinted snapshot of a freshly loaded, installed, ready
environment (PRG, geoRAM image, ABI/schema versions, startup dialect/numeric
profile, VICE/geoRAM configuration all included in the fingerprint); commands
are submitted through atomic direct injection into the editor mailbox/input
buffer, and tests wait on observable state transitions rather than sleeps.
Layer 5 (focused hardware tests) is reserved for what only VICE fidelity can
prove: the full keyboard path (`VICE key event → CIA matrix → IRQ SCNKEY →
KERNAL queue → GETIN → editor → line submission`) in one small dedicated
suite; independent IRQ/timer proofs (Timer A configuration, vector reaching
pinned code, `UDTIM` advancing `$A0-$A2`, bounded cursor service, `SCNKEY`
following `UDTIM`, continued timer/keyboard service during long compiler/
math/loop operations, restoration of interrupted CPU-port and geoRAM
selection, STOP closing channels/flushing input); and device/mapping proofs
(real KERNAL load/save/channel calls, ROM/I/O banking, geoRAM capacity
profiles, interrupts at bank-switch boundaries, with `$35` asserted during
normal operation and `$36` only inside a KERNAL bridge).

### 14.5 Failure Localization and Completion

A failing VICE test is reproduced downward: capture command/source
generation/routine ID/arena metadata/selected block-page, replay the
relevant phase artifact or runtime call locally, and extend the owning local
suite when the local model can represent the fault — extending the VICE
suite is reserved for faults that genuinely require hardware interaction. A
feature is complete only when it has unit, integration, functional, and
system-contract coverage as applicable; its E2E matrix cells are present;
stock-compatible E2E assertions have traceable reference fixtures; its
requirements map to tests (§15); static/local/VICE layers all pass;
resident/geoRAM size deltas are recorded (§12.3); and documentation/generated
schemas agree.

### 14.6 Smoke Selection and Regression Ownership

A stable subset of authoritative unit, integration, functional, system
contract, and E2E tests carries the `smoke` marker. The marker only selects
existing tests; it never creates a reduced duplicate implementation. A case
added with a current defect fix may also be marked `smoke`, but it retains its
normal scope, environment, profile, and mode markers.

Every regression is recorded as a newly covered edge case in the existing
owning suite, named case table, or canonical module. Bug work must not create a
regression-only directory, marker, top-level test file, bug-number suite, or
other parallel taxonomy.

## 15. Acceptance Traceability (R14)

`docs/TRACEABILITY.md` is authoritative for the EARS statement forms
(ubiquitous, event-driven, state-driven, optional-feature, unwanted-behavior)
and the trace-record schema (requirement ID, EARS statement, requirement
source section, design element, implementation component, test nodes by
layer, reference fixture provenance, status, last passing build/fixture
fingerprint). `requirements_matrix.json` is the machine-readable build
artifact; Markdown/CSV renderings may also be generated from it. The build
fails when an implemented requirement lacks a trace record, a trace record
points to a missing requirement/design section/test node, an implemented
keyword lacks a critical-language E2E case (§14.2), a stock-compatible
critical-language case lacks reference provenance (§14.3), or the generated
matrix is stale relative to its source trace inputs. A static source-pattern
test never completes a requirement by itself — at least one test node must
prove the behavior at the appropriate fidelity layer (§14.1).

## 16. Zero-Page Allocation (Cross-Cutting)

`docs/ZERO_PAGE.md` is authoritative. Zero page is a scheduled resource:
every byte has a declared owner, size, alignment, lifetime domain, alias
policy, and IRQ/ROM-call interaction, generated from a structured manifest
rather than assigned as literal addresses in assembly source. Lifetime
domains include CPU port (always live), IRQ/NMI state (concurrently live
with foreground code), the geoRAM call gate and nested context (§8), runtime
ABI call, expression evaluation, numeric FAC/extended math, statement-local
scratch, tokenizer/lexer, parser/compiler phase, editor foreground,
loader/install-only, error unwind, STOP/CONT resumable state, and KERNAL
bridge call (§10) — domains are not assumed mutually exclusive, since a
parser can call math, editor submission can invoke the tokenizer, geoRAM code
can call a resident runtime helper, and an IRQ can interrupt any IRQ-safe
foreground domain.

An interference graph node is each allocation/contiguous range; an edge is
added when lifetimes overlap, one node is live across a call that clobbers
the other, one is foreground-visible and the other IRQ/NMI-visible, a nested
call can require both, an error/callback can observe both, or an explicit
alias prohibition applies. Colors are concrete aligned address ranges;
multi-byte nodes require contiguous colors; non-interfering domains (e.g.
install-only scratch and post-install runtime scratch) may overlay. An alias
is legal only when represented in the manifest — accidental numeric overlap
is a build failure even when no current test happens to exercise both paths.

The always-concurrent IRQ set (`$91` stkey, `$A0-$A2` time, `$C5` lstx, `$C6`
ndx, `$CB` sfdx, `$F5-$F6` keytab, generated and checked against `c64rom`)
and the call-scoped KERNAL bridge interference sets (§10) seed the
interference graph; `$BA` (`fa`) is modeled as live across any direct command
relying on current-disk-device state (§4, §6.4, §9.5) and cannot be reused as
unrelated scratch while that state is valid. The allocator prefers, in
order: fixed architectural/IRQ reservations; stable runtime ABI ranges;
frequently used two-byte pointers; larger math ranges; phase-local overlays;
loader-only overlays — favoring a slightly larger coloring when it removes a
complex lifetime exception or callback dependency over a marginally smaller
one that doesn't.

Every build emits `zp_symbols.inc`, `zp_allocation.json`, `zp_allocation.md`,
`zp_interference.dot`, an unused/contingency-byte list, the source reason for
every interference edge, and the maximum simultaneous live-byte count by
domain (§13). The linker map is checked against the generated allocation;
documentation never carries a hand-maintained address table presented as
current truth. Static tests verify no undeclared literal ZP operands,
overlaps, or missing contracts; local-emulator tests poison non-live zero
page on entry and verify public routines touch only declared bytes; VICE
tests verify IRQ-owned bytes while long compiler/math routines run with
interrupts enabled (§9.3, §14.4). Any new zero-page use requires a manifest
change and a regenerated graph — a comment alone is not allocation.

## 17. IEEE 754 Numeric Profile (Cross-Cutting)

`docs/IEEE754.md` and `docs/MANUAL.md` (IEEE 754 Numeric Extensions, Appendix
C) are authoritative for the full operation/constant surface. Summary: IEEE
mode follows IEEE 754:2019 semantics except that Compiler 2 keeps the stock
BASIC V2-compatible internal floating layout and legacy-compatible
formatting — IEEE mode changes arithmetic and classification behavior, not
the on-disk/in-memory numeric encoding. `FPMODE1`/`FPMODE0`/`FPMODE()` select
and report the active mode independently of dialect (`BASIC2`/`BASIC3.5`,
§3.2). Core operations `+`, `-`, `*`, `/`, `SQR` are exactly rounded to the
destination format under the active rounding mode; transcendental functions
(trigonometric, logarithmic, exponential, power, etc.) are within 2 ULP over
their documented domain and may be geoRAM-native (§7.3 lists transcendental
math among the default geoRAM-backed subsystems) given they are not
compiled-speed-critical (§11).

The legacy project is reusable evidence and source material for this area.
Its trig, transcendental, and IEEE extension algorithms and ca65 source should
be reused where they fit Compiler 2's contracts, because the calculations were
already proven through Python proxy models and accuracy validation. The legacy
memory map, fixed addresses, and zero-page choices are not binding; they are
only porting guidance. Compiler 2's generated manifests, ZP allocation,
geoRAM placement, and ABI remain authoritative.

The required surface spans mode/flags (`FPMODE`, `FPFLAGS`, `FPCLR`,
`FPSET`, `FPTEST`, `FPTTEST`), classification (`ISNAN`, `ISSNAN`, `ISINF`,
`ISFIN`, `ISNORM`, `ISZERO`, `SGNBIT`, `ISUNORD`), operations (`COPYSGN`,
`TOTALORDER`, `FMA`, `REMAIN`, `MIN`, `MAX`, `SCALB`, `LOGB`, `MANT`, `RINT`,
`NEXTUP`, `NEXTDOWN`), interchange helpers (`BIN32$`, `VAL32`), and constants/
printed values (`INF`, `-INF`, `NAN`, `SNAN`). Flag bits are invalid
operation, divide-by-zero, overflow, underflow, and inexact; rounding modes
are ties-to-even, toward zero, toward positive infinity, toward negative
infinity, and ties-away. Per §14.3, IEEE E2E cases are compared against the
normative Compiler 2 specification and an independent IEEE oracle rather
than a stock VICE reference, since no stock ROM implements this surface.

## 18. Document Map

```text
DESIGN2.md                       (this file — top-level architecture/index)
REQUIREMENTS.md                  (authoritative requirements)
docs/
  KEYWORDS.md                  (per-keyword language reference)
  MANUAL.md                    (user-facing manual: dialects, wedge, IEEE)
  TESTING.md                   (test hierarchy and fixture mechanics)
  CANONICAL_TESTS.md           (fixture/regeneration policy)
  TRACEABILITY.md              (EARS trace record format)
  GRAPHICS_MEMORY.md           (bitmap/screen-matrix/color-RAM layout)
  GEORAM_BANKING.md            (geoRAM hardware contract and call ABI)
  GEORAM_LOADER_DESIGN.md      (install-time loader and build shape)
  INCREMENTAL_COMPILATION.md   (per-line compile/publish machinery)
  COMPILE_EXPORT.md            (stock-C64 export format and budget)
  MEMORY_BUDGETS.md            (full normal-RAM and geoRAM byte accounting)
  ZERO_PAGE.md                 (zero-page manifest and interference graph)
  KERNAL_ABI.md                (KERNAL bridge contract and call surface)
  EDITOR.md                    (resident/geoRAM editor split)
  DOS_WEDGE.md                 ($ @ / ! direct-mode commands)
  LOOP_OPTIMIZATION.md         (loop descriptor model and fast paths)
  IEEE754.md                   (IEEE 754 profile summary)
  BUILD.md                     (toolchain, build order, artifacts)
  GENERATED_REFERENCE.md       (generated API.md and MAP.md schemas)
  VICE_TOOLS.md                (D64/PETCAT command recipes)
```

Every design document above states required behavior consistent with
`REQUIREMENTS.md`; this file is what shows that the set of documents, taken
together, covers every requirement group with no gap and no unresolved
conflict.
