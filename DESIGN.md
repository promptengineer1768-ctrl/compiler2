# Compiler 2 Design

## 0. Role of This Document

`REQUIREMENTS.md` is the authority for common Compiler 2 behavior.
`REU_REQUIREMENTS.md` is the authority for the dual-device expansion profile
(geoRAM and REU detection, selection, REU hardware/DMA/overlays, dual
packaging). This document describes one implementation that satisfies both.
On disagreement, the applicable requirements document wins.

This file is the top-level design index. Dual-device expansion detail lives in
`REU_DESIGN.md`; geoRAM hardware detail lives in `docs/GEORAM_BANKING.md`.
This file states the architecture that ties them together, fills sections that
have no dedicated document yet, and shows how every requirement section is
satisfied. Section numbers below match the corresponding `R<n>` group in
`REQUIREMENTS.md` unless noted as `RREU-*`.

| Requirement group | Design coverage |
|---|---|
| R2 Product / R2.1 Phase 1 | §1, §2; `REU_DESIGN.md` §1, §8 |
| R3 Language Compatibility | §3, `docs/KEYWORDS.md`, `docs/MANUAL.md`, `docs/BASIC_COMPATIBILITY_LIMITS.md`, `docs/SYSTEM_PRIMITIVES.md` |
| R4 Direct and Program Modes | §4 |
| R5 Tokenized Program Compatibility | §5, `manifests/program_formats.json`, `docs/MANUAL.md` Appendix B |
| R6 Compilation and Runtime | §6, `docs/INCREMENTAL_COMPILATION.md`, `docs/COMPILE_EXPORT.md` |
| R7 Memory and Arenas | §7, `docs/MEMORY_BUDGETS.md`, `docs/GRAPHICS_MEMORY.md`, `REU_DESIGN.md` §6 |
| R8 Expansion (geoRAM + REU) | §8, `docs/GEORAM_BANKING.md`, `docs/GEORAM_LOADER_DESIGN.md`, `REU_DESIGN.md`, `REU_REQUIREMENTS.md` |
| R8.1.1 Expansion profile | §8.0 |
| R8.1.2 DMA range classes | §8.0.1 |
| R8.2 Shared memcopy policy | §8.2.1; requirement in `REQUIREMENTS.md` §8.2 |
| R8.2.1 Shared memfill (REU fixed-src) | §8.2.2; requirement in `REQUIREMENTS.md` §8.2.1 |
| R8.5 Re-detect / degraded / QUIT | §8.5, §9.3 |
| RREU-1..13 Dual-device REU | §1, §2, §7.4, §8, §13; detail in `REU_DESIGN.md` |
| R9 Editor and Interrupts | §9, `docs/EDITOR.md`, `docs/DOS_WEDGE.md`, `REU_DESIGN.md` §7 |
| R10 KERNAL | §10, `docs/KERNAL_ABI.md` |
| R11 Optimization | §11, `docs/LOOP_OPTIMIZATION.md` |
| R12 Robustness and Observability | §12 |
| R12.1 Build Toolchain | §13, `docs/BUILD.md`, `docs/GENERATED_REFERENCE.md`, `docs/VICE_TOOLS.md`, `REU_DESIGN.md` §9 |
| R13 Test Hierarchy | §14, `docs/TESTING.md`, `docs/CANONICAL_TESTS.md`, `REU_DESIGN.md` §11 |
| R14 Acceptance Traceability | §15, `docs/TRACEABILITY.md` |
| Cross-cutting: zero page | §16, `docs/ZERO_PAGE.md` |
| Cross-cutting: IEEE 754 | §17, `docs/IEEE754.md` |

A document map is repeated at §18.

## 1. Product Architecture (R2)

Compiler 2 is a native 6502 compiler and interactive BASIC environment for a
Commodore 64 with **one selected expansion store** per session: **geoRAM**
(preferred) or **REU**. **geoRAM 256-byte XIP is the normative implementation.**
When only REU is available, XIP is emulated by DMA into `$CE00` / hot slots.
When **both** are present, geoRAM is the store/XIP backend and REU is kept for
an **internal DMA memcopy assist** (large block moves), not as a second arena.
One `BASICV3` startup detects both, prefers geoRAM for the store, loads the
geoRAM-canonical image, and applies the `REU` patch only when REU is the
selected store. Detail: `REU_DESIGN.md`.

The system is partitioned into five cooperating layers:

1. **Resident foreground** — IRQ, screen front end, editor mailbox,
   RAM-under-I/O gate, KERNAL bridge, dual-device detection/selection, expansion
   call gate, and a shared **memcopy** helper that uses REU DMA when profitable
   (§8, §9, §10).
2. **Expansion-native services** — editor, compiler pipeline, diagnostics,
   slow math, cold data. Always authored as geoRAM XIP pages; under REU the
   same page image is DMA'd into the XIP buffer before entry (§6, §7, §8).
3. **Compiled program runtime** — documented ABI for user programs (§6.3).
4. **Expansion arena manager** — typed generation handles; physical store is
   geoRAM pages or REU memory with the same logical page/arena model (§7.4).
5. **Build and verification** — build the geoRAM-canonical image plus a small
   REU patch; dual-capable D64; layered tests (§13, §14).

```text
routine ID ──► call gate ─┬─ GeoRAM: select page @ $DE00 ─► XIP call
                          └─ REU: DMA 256 B → XIP buffer ─► same entry model

logical handle ──► arena backend ─┬─ geoRAM window R/W
                                  └─ REU DMA R/W (page or bulk)
```

Layer 1 owns page selection / REC programming and banking critical sections.
Layers 2–4 use `$01=$35`. IRQ never selects geoRAM pages and never programs
the REC. Interactive DMA quanta are ≤ one jiffy (~17 000 cycles).

The minimum supported capacity for **each** backend is 512 KiB. The
geoRAM-canonical expansion image (XIP pages, directories, required fixed
arenas) must **fully fit in 512 KiB**; a **host build that exceeds 512 KiB
must fail**. The build records declared minima and the selected device's
measured capacity in `build_manifest.json`. Larger detected geoRAM/REU may be
used **only as extra dynamic storage** (e.g. strings); never as a requirement
for the base image or language semantics. XIP packs into **lower** expansion
page numbers first.

Failure when **neither** device validates, or when the **selected** device's
profile is corrupt or changes unexpectedly after install, aborts before any
arena/editor/compiler state is trusted (or enters the clean fatal path after
selection). The Phase 1 loader (§2) is the only code that runs before
selection succeeds.

Installation publishes one **active-expansion record** (device type, capacity,
capabilities, format versions, fingerprint, selection/fallback reason). Later
integrity checks compare against that record. The unselected device is never
allocated, loaded, or executed for the rest of the session. Corrupt metadata,
failed checks, or an unexpected profile change enter one clean fatal path:
stop expansion execution and allocation, restore mapping and interrupt state
(and geoRAM selection or REC idle as applicable), report the failure, and
require reinstallation. The system never silently shrinks, remaps, or
continues under a changed profile.

## 2. Phase 1 Install and Editor Slice (R2.1)

Phase 1 produces an installable dual-device D64 image (`docs/BUILD.md`, §13,
`REU_DESIGN.md` §8) whose loadable PRG starts with the stock BASIC loader line:

```basic
2026 SYS2061
```

`SYS2061` (`$080D`) is the entry point of the common host-built loader. The
loader:

1. establishes canonical `$35` mapping and saves loader/interrupt state;
2. probes and restores **geoRAM** non-destructively (`docs/GEORAM_BANKING.md`);
3. probes and restores **REU** non-destructively (`REU_DESIGN.md` §3);
4. validates each candidate against its 512 KiB minimum independently;
5. selects the only valid device, or applies the generated preference when both
   are valid (default **geoRAM**); falls back to the other validated device if
   the preferred one fails;
6. if neither is valid, rejects with a clean error and does not enter the
   editor;
7. publishes the active-expansion record and installs the common normal-RAM
   payload (decompressing it if the build used `-UseCompressor`);
8. loads the **geoRAM-canonical** expansion image (`GEORAM`) into the selected
   store (geoRAM pages, or REU memory via DMA);
9. if REU is selected, loads the small **REU patch** and applies it (including
   any deterministic in-place fixup loops for XIP buffer origin);
10. restores ROM/I/O banking to the canonical runtime mapping;
11. jumps to `compiler_init`, which performs first-time arena construction and
    enters the interactive editor.

| Host artifact | D64 name | Role |
|---|---|---|
| `basicv3.prg` | `BASICV3` | Common loader, detectors, RAM payload |
| `georam.bin` | `GEORAM` | Normative expansion image (all XIP pages) |
| REU patch object | `REU` | Small delta + optional fixup code for REU |

System contracts assert names stay consistent. A geoRAM session does not need
the REU patch after selection; an REU session always starts from the same
`GEORAM` image plus the patch.

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

Phase 1 exercises dual-device detection (prefer geoRAM), the RAM-under-I/O gate,
KERNAL bridge, IRQ jiffy clock, transactional line submission, and the direct
loop fast path. The release disk always carries `GEORAM` plus the REU patch.

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

Byte-valued operands have one shared numeric conversion boundary. The public
runtime helper `math_to_arg_byte` accepts a typed `FLOAT`, `INT1`, `INT2`, or
`INT3` value and returns the exact unsigned value `0..255`. This argument-byte
domain is not a fifth numeric variable type and is not signed `INT1` storage.
Negative, fractional, greater-than-255, and unknown-type inputs produce
`?ILLEGAL QUANTITY` before a command-specific action occurs. File/channel
logical numbers, devices, secondary addresses, and byte-valued operands such
as the value in `POKE` and the value/mask in `WAIT` use this same helper; no
statement subsystem owns a private byte-coercion implementation.

`PEEK`, `POKE`, `SYS`, `USR`, and `WAIT` operate on the real C64 CPU address
space. Protection is a narrow control-plane policy, not a blanket ban on the
standalone code range: the runtime rejects writes only into generated
integrity-critical intervals — `$FFF9-$FFFF` (guard and hardware vectors),
pinned IRQ/NMI and resident control blocks, geoRAM gate/selection state,
resident arena-directory mirrors that must stay consistent, and
compiler-owned zero-page ranges from the generated allocation map
(`docs/SYSTEM_PRIMITIVES.md`, `docs/ZERO_PAGE.md`). When REU XIP is active,
**`$CE00–$CEFF` may be protected** as the primary miss slot (corruption would
crash the gate). **Hot pages `$C800–$CDFF` are disposable cache** under memory
pressure and must **not** be blanket-protected solely for holding hot XIP.
Ordinary program, variable, string, compiled-image, screen, I/O, and free
dynamic RAM remain `PEEK`/`POKE`-accessible as on stock BASIC; self-modifying
or self-corrupting user code is allowed and fails cleanly rather than being
silently blocked. The build publishes the exact protected intervals in
`MAP.md` / `zp_protected_ranges.inc`. A **stock-compatible** standalone export
has no hidden development-only ranges and treats `$CE00` as free; a
**developer-layout** export may reserve `$CE00` per §6.4. Address operands use
the separate unsigned 16-bit address contract; byte-valued operands use
`math_to_arg_byte`.

`FRE` is profile-aware (R3.1). In the installed development environment it
returns free bytes in the primary variable/string arena used by running
programs (expansion-backed on the selected geoRAM or REU backend). In a
source-free `COMPILE` export without expansion memory it returns free bytes
in the normal-RAM dynamic region remaining after the exported image loads.
The numeric argument is accepted and discarded as in stock BASIC V2. `FRE`
never reports raw device capacity; it reports allocator-visible free space for
the active runtime profile so programs see a single free-memory number that
matches the storage class actually backing variables and strings.

### 3.2 Dialect and Mode Gating

A single dialect/mode state machine governs which token set the tokenizer
accepts:

- **Dialect**: `BASIC2` (default at cold start) or `BASIC3.5`. Selected only
  by the direct-mode-only commands `BASIC2` / `BASIC3.5`, and inspectable
  through `BASIC()`.
- **Numeric mode**: stock BASIC numeric semantics (default) or IEEE, selected
  by `FPMODE0` / `FPMODE1`, inspectable through `FPMODE()`. Numeric mode is
  independent of dialect — IEEE functions are reachable regardless of
  `BASIC2`/`BASIC3.5` selection, and structured-loop tokens are gated by
  dialect alone.

**Always-available gateway surface.** The BASIC 3 gateway keywords
`BASIC2`, `BASIC3.5`, `BASIC()`, `COMPILE`, `QUIT`, `FPMODE0`, `FPMODE1`, and
`FPMODE()` are accepted in both dialect modes from cold start (subject to
direct-mode-only rules in §4). `QUIT` returns to stock BASIC (and is the only
command honored in the minimal no-device editor, §8.5). They are not gated behind `BASIC3.5`. Only
the structured subset (`ELSE`, `DO`, `LOOP`, `EXIT`, `UNTIL`, `WHILE`, and
any graphics keywords that require BASIC 3.5 mode per `docs/MANUAL.md`) is
dialect-gated. Token byte assignments for stock V2, gateway, structured, and
IEEE keywords are owned by `docs/MANUAL.md` Appendix B and the generated
command/token tables derived from `manifests/commands.json`; those tables
must never reassign a stock BASIC V2 token byte (`$80`–`$CB` stock range).

While `BASIC3.5` mode is disabled, the structured tokens (`ELSE`, `DO`,
`LOOP`, `EXIT`, `UNTIL`, `WHILE`) must tokenize to `?SYNTAX ERROR`, exactly as
stock BASIC V2 would treat an unrecognized identifier sequence. The tokenizer
therefore consults the active dialect before accepting a dialect-gated
extended token, not only at parse time — a line typed in BASIC2 mode is never
silently stored with structured tokens that later "activate" if the dialect
changes.

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
(`BASIC2`, `BASIC3.5`, `BASIC()`, `COMPILE`, `QUIT`, `FPMODE0`, `FPMODE1`,
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

### 5.1 Goal and machine pairing

Compiler 2's primary language targets are **stock BASIC V2** (C64) and
**supported stock BASIC 3.5** keywords (Plus/4-compatible token bytes). Tokenize,
`LOAD`, `SAVE`, and `VERIFY` for those surfaces must match the respective
stock machine. Compiled native images always target the **C64** and may use any
implemented keyword surface.

| Program content | On-disk form | Oracle tooling |
|---|---|---|
| BASIC V2 only | C64 stock linked-line PRG `$0801` | stock C64 VICE, `petcat -2` |
| Supported BASIC 3.5 | **Plus/4 PRG header** + stock 3.5 tokens/links | Plus/4 VICE, `petcat -3` |
| Compiler 2-only (gateway/IEEE/…) | Not petcat/stock-ROM portable | Compiler 2 + VICE C64 |

### 5.2 Stock V2 and stock 3.5 form

Stock V2 saves use C64 PRG load `$0801`, stock next-line links, little-endian
line numbers, unmodified stock token bytes `$80`–`$CB`, zero line terminator,
zero program terminator, and stock `DATA`/`REM`/quote rules. Materializing for
`SAVE` always relinks canonically.

**BASIC 3.5:** Plus/4 PRG header + Plus/4 tokens for 3.5 keywords.

**LOAD:** classify file format first (C64 V2 vs Plus/4 3.5 vs Compiler 2-only).
On success, set session dialect to match (`BASIC2` / `BASIC3.5`) so editing
uses the correct token set. Reject or error cleanly on unknown formats.

**SAVE:** format follows **tokens present in the program**, not REM/string
text and not only the current dialect mode:

1. any Compiler 2-only **tokens** (outside REM/string contexts) → Compiler
   2-only encoding (not pure stock);
2. else any BASIC 3.5 / Plus/4 **tokens** (outside REM/string) → Plus/4 3.5
   PRG — **do not translate to V2**; stock V2 may fail to LIST/RUN;
3. else stock V2 tokens only → C64 V2 PRG.

**VERIFY** compares the on-disk file to **exactly the bytes SAVE would write**
for the current program (same format class). Intended for use after SAVE.
Pure **byte equality** only — no Plus/4 ROM required for Plus/4-format files.

**Compiled** programs always target the C64 only (any keywords).

### 5.3 Compiler 2-only tokens

Gateway, IEEE, and other non-stock tokens must not remap stock V2 bytes, must
round-trip inside Compiler 2, and must fail cleanly on unknown versions. They
are **not** required to load under stock ROMs or petcat. A proprietary C2P1
envelope is **not** required for stock V2/V3.5 programs (that earlier decision
is superseded). Optional versioned envelopes may still be used for
Compiler 2-only package features if they never masquerade as stock V2/3.5
saves in the common path.

Keyword recognition uses the generated letter-led trie for alphanumeric
keywords (including `TAB(` / `SPC(`). Single-character operators
(`+ - * / ^ > = <`) use stock token bytes **170–179** via the expression
scanner and remain part of the token stream for stock-compatible SAVE — they
are not omitted from the language surface.

### 5.4 Internal representation

Internally, expansion arenas may store handles/indexes; external boundaries
always present the stock form for the active dialect as in §5.1.

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

**Hard requirement:** ordinary numbered-line entry returns editor-ready in
about **0.5 s or less**.

**Stock-equivalent entry errors:** on entry, behave like stock BASIC — tokenize
and store the line; report only tokenization failures (and any other errors
stock would raise while accepting a line). Do **not** report full parse,
semantic, or runtime errors at entry beyond stock. Those appear at **`RUN`**
or immediate execution. Immediate mode still tokenizes then executes.

**Full code generation may be deferred** when it would miss the budget. Dirty
compile work is completed no later than the next `RUN` (or other execution
entry) that needs a consistent compiled image. There is no interpreter
fallback.

When compile-on-entry is affordable, numbered-line entry may also compile in
the same Return; when deferred, only stock-equivalent tokenize/store runs on
entry. Failures of a full compile leave the previous valid compiled cache
intact when source was already published.

Per-line compiled records are keyed by source generation, dialect, IEEE mode,
runtime ABI version, and the usual dependency generations. Local vs structural
edits dirty only what they must. Immediate mode always runs a temporary
full compile.

Keyword recognition uses the generated first-character trie for letter-led
keywords (including `TAB(`/`SPC(`); stock operator tokens 170–179 are produced
by the expression scanner. `keyword_lookup_report.json` tracks trie cost so
the 0.5 s budget is not lost to linear keyword scans.

#### 6.2.1 Publication Rule

`RUN` (and other execution entries) succeed only after all deferred/dirty
compile records are resolved, layout is verified, and the compiled-image
checksum matches the current source generation. Until then, deferred dirty
state is allowed in the editor as long as source publication succeeded.
Unresolved dirty records at `RUN` report the phase/line and leave the last
valid compiled state intact when applicable.

### 6.3 Runtime ABI

Compiled code depends only on the documented runtime ABI — never on private
compiler workspace addresses, physical geoRAM page allocation, or editor
state. The ABI covers:

- scalar and array resolution, load, store, and type promotion;
- string allocation, assignment, slicing, comparison, and reclamation;
- numeric arithmetic, comparisons, and the shared unsigned argument-byte
  coercion entry `math_to_arg_byte`;
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

**Stock memory budget (warnings, not hard reject — for code size only).** With
`2026 SYS2061`, the conventional stock payload ends by `$CFFF`. The compiler
continuously reports

```text
standalone_code_budget = standalone_loader_bytes + compiled_program_bytes
```

Primary goal: stock-exportable programs. Soft policy (applies to compiled
**code** size, not to array placement — arrays are addressed separately below):

- **Edge-triggered 80% status** (not continuous while remaining on one side):
  - crossing **up** through 80% → one near-limit warning for that crossing;
  - crossing **down** through 80% (edit/delete shrank the estimate) → one
    clear/recovery status for that crossing;
  - hovering around the boundary may warn and clear multiple times (once per
    crossing), not on every keystroke while size stays ≥ 80% or stays < 80%;
- crossing the **100%** stock ceiling →
  **`WARNING: EXCEEDS STOCK RAM`** (edge-triggered enter/leave similarly);
  still allow the program in the expansion-backed environment and still allow
  export, because this warning covers only code that is approaching but still
  fits the ceiling;
- never silently truncate.

**Compiled code may never use geoRAM expansion.** The emitted native 6502 image
must always fit in normal RAM, in both the development environment and a
`COMPILE` export; code has no "give it more room via geoRAM" option the way
arrays do (§7.3). A compiled-code image that does not fit the standalone budget
(`$080D-$CFFF`) is a **hard compile-time error**, caught before `RUN` and again
at `COMPILE` time, not a warning.

**Array data has the only expansion escape hatch.** In the installed
development environment, arrays may be geoRAM-backed so an interactive program
can `DIM` more array space than stock RAM allows (§7.3). A compiled program that
runs in development with geoRAM-backed arrays but whose arrays do not fit the
remaining normal-RAM budget at `COMPILE` time must hard-fail as a *distinct
diagnostic* from the code-size warning — it means "cannot export this program,"
not "runs but tight." Report the byte delta the arrays are over budget,
consistent with the footprint-delta reporting convention in `docs/MEMORY_BUDGETS.md`.
Array overflow is an error; code-size overage stays a warning.

**Export layout profiles.**

| Profile | When | `$CE00` in export runtime |
|---|---|---|
| **Stock-compatible** | Program + vars fit standalone without expansion / developer XIP | **Free** — do not reserve; stock machines do not hold REU XIP there |
| **Developer** | Needs expansion-backed storage or developer workspace | **Reserved** — match installed Compiler 2 layout |

Hot slots `$C800–$CDFF` are disposable cache under memory pressure and are
never permanent export reservations. Stock layout choice is deterministic from
measurements; never silently place stock-export live data only at `$CE00`.
User messaging stays the stock-budget warnings only; layout profile is
internal/export-metadata, not a second banner.

Tokenized source may grow in expansion memory independently. Variable and
workspace budgets for a true stock export remain separate from the code image.
Graphics-mode exports may use `$D000-$D7FF` under I/O only through documented
gates (§7.2).

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
Display restoration is required on normal end, BASIC error, `STOP`, and
STOP-key interruption alike, but it is distinct from releasing graphics
memory. Before a graphics-capable `RUN`, edit/compile-only `HIBASIC` bytes at
`$E000+` are saved to a dedicated geoRAM buffer. `END` and last-line
fall-through release graphics and restore `HIBASIC`. Error and STOP paths keep
`$DC00-$FF3F` intact for `CONT`; editing invalidates `CONT` and lazily restores
`HIBASIC`, overwriting the old bitmap. Compiler entry also forces restoration.
One explicit transition state machine owns these events and the save buffer.

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

**Scalar variables are always normal-RAM resident, unconditionally.** They are
never expansion-backed. This holds identically in the installed development
environment and in `COMPILE` exports, and matches the `VD` descriptor's
direct-cell mode (`docs/COMPILER_ARCHITECTURE.md`): a scalar descriptor names a
direct normal-RAM cell, never an arena handle or geoRAM page. String descriptors
(`SD`) must also support a normal-RAM-backed payload so source-free compiled
exports run without geoRAM, but scalar and array *value* cells do not change
residence by profile.

The following are expansion-backed by default (selected geoRAM or REU backend)
and may move to a small resident component only when measurement proves it
necessary, with the byte delta reported and justified (R2 optimization
priority): editor parsing/line-edit transforms, lexer/tokenizer,
parser/semantic analysis, symbol/control-flow/IR/optimization/codegen passes,
diagnostics formatting, transcendental math, tokenized program storage,
compiled program storage (but see the hard code-size rule above — code must fit
normal RAM and may not expand into geoRAM), arrays — **in the development
environment only, as a deliberate capacity feature** that lets an interactive
program `DIM` more array space than stock RAM permits; this is intended and
documented as a benefit, not a performance hedge, and does not apply to
`COMPILE` export, which requires arrays to fit normal RAM — and string payloads
when the active profile has expansion memory.

### 7.4 Arena Model

Every arena declares: type and format version; capacity and allocation
metadata; ownership and bounds checks; generation numbers for stale-handle
detection; explicit allocation-failure behavior; integrity checks usable by
tests; and deterministic reset/invalidation rules. At minimum, separate
ownership exists for: tokenized program; compiled images; scalar descriptors
and cold scalar payloads; arrays; strings; symbols and compiler IR;
overlay/dispatch metadata; and scratch/diagnostics.

The **logical** arena API is backend-neutral: arena IDs, handle fields,
generations, ownership, and transactional publication rules are the same on
geoRAM and REU (`REU_REQUIREMENTS.md` RREU-6). The **physical** adapter is
chosen from the active-expansion record:

- **geoRAM adapter** — page allocation and `$DE00` window access; arenas may
  share one physical free-page allocator with per-region integrity checks.
- **REU adapter** — byte extents or generated size classes; no requirement
  that strings own one 256-byte page solely to imitate geoRAM paging
  (`REU_DESIGN.md` §6).

The pinned resident arena directory stores only enough information to find and
validate the full expansion-resident directory: format version, active device
type, detected capacity, allocator generation, directory location, checksum,
and recovery status. The full directory owns extents, high-water marks, free
lists, per-arena generations, and integrity metadata.

Large objects are addressed by stable logical handles, never raw window
addresses, REU physical addresses, or DMA staging pointers. Physical backing
may move (compaction, rebalancing, scratch reuse) without invalidating handle
holders. There is no hidden capacity reserve outside declared arena, overlay,
allocator-metadata, or scratch ownership. An unexpected capacity/profile
change is a fatal integrity event handled by §1, never an online resize.

Variable descriptors may point to expansion-backed payloads, normal-RAM
payloads, or a small resident scalar cache when measurement justifies the
resident bytes. Any resident scalar cache is explicitly tagged by descriptor
and generation; writes are write-through or marked dirty by contract, and
program exit, BASIC error, STOP, CONT invalidation, and eviction all use one
tested flush path. Under REU, string and cold-payload operations materialize
bounded ranges into leased work buffers and commit through the common
publication path (`REU_DESIGN.md` §6.2–§6.4).

## 8. Expansion Memory (R8 / RREU)

Compiler 2 selects one expansion backend per session. This section states the
common dual-device model and summarizes each backend. Authoritative detail:

| Backend | Authority |
|---|---|
| Dual selection, REU DMA/overlays/arenas | `REU_REQUIREMENTS.md`, `REU_DESIGN.md` |
| geoRAM hardware and XIP calls | `docs/GEORAM_BANKING.md` |
| geoRAM install stream shape | `docs/GEORAM_LOADER_DESIGN.md` |

### 8.0 Dual-device selection, profile, and dispatcher

#### Expansion profile (R8.1.1)

After install and after each successful NMI re-detect that retains capability,
resident storage holds one **expansion profile** consulted by all gates:

```text
store: georam | reu | none
reu_assist: bool
capacity_georam, capacity_reu, fingerprints
xip_slot_bases[], xip_slot_count
N_dma, N_fill
feature bits: verify?, swap?
generation, degraded reason
```

Gates do not re-probe on every call. Assist-only REU loss clears `reu_assist`
and keeps `store` (R8.5).

#### DMA range classes (R8.1.2)

| Class | Example | Banking | REU DMA |
|---|---|---|---|
| Normal RAM | `$0800–$CFFF` (excl. reserved) | `$35` | yes |
| Bitmap | `$E000–$FF3F` | `$35` | yes |
| Colour RAM | `$D800–$DBE7` | I/O visible | yes |
| Matrix under I/O | `$DC00–$DFE7` | only inside RAM-under-I/O gate | yes |
| I/O registers | other `$D000–$DFFF` | — | **never** |
| Stack / control ZP | `$0100–$01FF`, protected ZP | — | **never** |

One classifier serves memcopy, memfill, optional swap/verify, and install.

#### Selection

Startup probes both devices non-destructively, validates each candidate
independently against its 512 KiB minimum, then:

1. selects the only valid device; or
2. when both are valid, applies the generated preference (default geoRAM); or
3. if the preferred device fails after a successful probe of the other, falls
   back to the other and records the reason; or
4. if neither is valid, aborts before any expansion state is trusted.

One **active-expansion record** is published for the session. After selection
the unselected hardware is never touched. The resident **expansion
dispatcher** is the only common production entry for expansion-native calls,
tail transfers, range ingress/egress, byte/word access, compare/checksum,
allocation, and profile queries. It routes by active device type to
`georam_*` or `reu_*` gates and never pretends XIP and DMA-overlay mechanics
are the same.

Every dual-device routine ID has ABI-compatible geoRAM and REU placement
records (inputs, outputs, clobbers, return kind, callbacks, errors). Build
checks reject a routine available to one backend but absent or ABI-incompatible
on the other.

### 8.1 geoRAM backend

`docs/GEORAM_BANKING.md` is authoritative for the hardware contract, native
call ABI, and selection-ownership rules. Summary of the load-bearing
decisions:

- **Mapping independence**: selecting, reading, writing, or executing a
  geoRAM page never changes the CPU-port mapping (§7.1); the geoRAM window
  and registers are already visible under the canonical `$35` map.
- **Non-destructive detection**: the detector saves processor status,
  registers, selection, and probe bytes before touching candidate pages; verifies
  distinct persistence across two candidate pages; probes address-bit
  aliasing to bound capacity; restores every modified byte/selection/status
  and every saved register on success or failure; and runs a second pattern
  order in debug builds to catch floating-bus false positives. Capacity is
  accepted only if it meets the declared minimum (**512 KiB**, and the full
  project image must fit in that minimum). **XIP pages pack from low geoRAM
  space first** (low block/page before high).
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

### 8.2 REU backend (geoRAM-page emulation)

`REU_DESIGN.md` is authoritative. REU is **not** a second overlay architecture:
it **emulates geoRAM XIP pages**.

#### XIP buffer decision

Linker policy places each geoRAM page at origin **`$DE00`**. Absolute
`JMP`/`JSR`/abs-mode operands targeting the window use high byte `$DE`.
Relative branches need no fixup. Heuristic scan of current `build/georam.bin`
(incomplete fill): roughly **~15 nonempty pages** and **~45 absolute `$DExx`
sites** would need high-byte rewrite if run outside `$DE00` (final counts rise
as pages fill; not every page has abs `$DE` refs).

**Reject primary execute from RAM-under-I/O `$DE00`:** with I/O visible
(canonical `$35`, matching geoRAM), `$DE00` is the geoRAM **window**, not RAM —
REC cannot deposit executable RAM there. Banking I/O out makes `$DE00` RAM but
hides REC (`$DF00`) and **diverges from geoRAM** (geoRAM XIP runs with I/O
visible). DMA would need a staging buffer then a second copy under I/O, plus
`$01` save/restore every quantum.

**Chosen: multi-slot normal-RAM XIP windows below I/O, keep `$01=$35`.**

| Item | Choice |
|---|---|
| Primary / miss slot | **`$CE00–$CEFF`** (only fixed reservation; POKE-protect while REU XIP active) |
| Hot XIP slots | **`$C800–$CDFF`** (up to 6 pages) when free; **reclaimable** under memory pressure; not permanent reservations |
| I/O during XIP | Canonical **`$35`** (I/O visible) |
| Fixup | **Per slot, at DMA-in time:** abs operand hi `$DE` → that slot’s page high byte (`$CE`, `$C8`, `$C9`, …); relative branches unchanged; abs targets outside `$DE00–$DEFF` unchanged |
| Why not “data cache → copy to `$CE00`” | Hot slots are **additional XIP pages** fixed for their own base so the call gate can **JSR/JMP straight into the slot** with no second copy |

**Feasibility of multi-base hot XIP (yes):** every page is linked for `$DE00`, so
intra-window absolute operands share high byte `$DE`. For any page-aligned
slot base `$xx00`, a single deterministic scan rewrites `$DE` → `$xx` in those
operands. Cross-page control must already go through the gate (never absolute
`$DExx` into another logical page). Therefore:

1. **Cold miss:** DMA logical page → `$CE00`, fixup for `$CE`, enter at
   `$CE00+entry`.
2. **Promote / fill hot slot:** DMA logical page → slot base `$Cn00`, fixup
   for `$Cn`, record `(logical_page_id → slot, base, entry map)`.
3. **Hot hit:** gate routes to `base+entry` **immediately** — no DMA, no
   copy through `$CE00`.
4. **Nested calls:** pin slots that have live frames (same rule as before);
   a callee miss uses `$CE00` or another free slot without clobbering a pinned
   hot page.
5. **Eviction:** only unpinned slots; next miss refills and re-fixups.

This is strictly faster than treating hot RAM as a data cache that always
re-copies into `$CE00` before execute. Cost of fixup is once per DMA-in to a
slot (~page scan), amortized across many hits.

- **Call gate:** resolve routine → if slot hit, call fixed base+offset;
  else DMA+fixup into `$CE00` (or promote into a free hot slot per policy),
  then call. Return/tail-transfer semantics match geoRAM.
- **DMA budget:** ≤ one jiffy (~17 000 cycles) per interactive quantum.
- **REC ownership:** only the REU gate writes `$DF01–$DF0A`; IRQ never programs REC.
- **Install:** DMA-load `GEORAM` into REU memory, apply D64 file **`REU`**.
  Optional: prefill known-hot logical pages into hot slots with fixup at
  install (lexer/keyword tables, etc.).

#### 8.2.1 Shared memcopy — design choice for **R8.2**

**Requirement ID:** `REQUIREMENTS.md` §8.2 (`R8.2`). This subsection is the
normative design choice for thresholds, decision procedure, call sites, and
native form so implementation and tests can trace to R8.2.

**API (internal):** one helper, e.g. `mem_copy(dst, src, n)` with
`n ∈ 1..256`.

**When to use DMA vs CPU (formal decision procedure):**

```text
if n == 0:
    return success                    ; no-op
if not reu_dma_available:
    native_copy(n)
elif n < N_dma:                       ; default N_dma = 32 (R8.2)
    native_copy(n)
elif ranges are DMA-legal:
    reu_dma_copy(n)                   ; 1-hop or 2-hop as needed
else:
    native_copy(n)                    ; cannot stage → CPU
```

**Constant:** `N_dma = 32` until re-measured on the production REC gate; any
change updates R8.2 and this section with evidence.

**Native form:**

```text
  ldx #N
loop:
  lda src-1,x
  sta dst-1,x
  dex
  bne loop
```

(or equivalent full-page `inx`/`bne` form for N=256).

**Evidence** (`debug/bench_memcopy_reu.py`, tools REU model ≈70 reg + 60+N
DMA/hop): break-even ≈11–16 B (1-hop), ≈24–32 B (2-hop). At N=256, 2-hop
~772 vs native ~3584 (~4.6×). Defaults sit at the conservative 2-hop edge.

**Must call memcopy for bulk work:** string payload page copies; geoRAM
page-to-page payload moves; program-store clone/shift when a linear chunk is
≥ `N_dma`; install/bulk page fills. **Must not** replace fixed tiny
descriptor/math field copies that are always &lt; `N_dma` and cheaper inline.

**Tests (trace R8.2):** unit tests at N=31 vs N=32 with REU on/off (no REC
programming below threshold; DMA at/above when available); byte-identical
results vs native; at least one integration case each for string page copy and
geoRAM page copy.

#### 8.2.2 Shared memfill — design choice for **R8.2.1**

**Hardware:** `$DF0A` bit 6 = fix REU address; bit 7 = fix C64 address.
REU→C64 with REU fixed and C64 incrementing writes the **same REU byte** to
every C64 destination — a hardware fill. Procedure:

1. store fill byte at a dedicated REU fill cell (or any fixed REU address);
2. program C64 start, REU start = fill cell, length (0 ⇒ 65536 for one REC op);
3. `$DF0A = $40` (fix REU, increment C64);
4. execute REU→C64 (`$DF01` command bits for REU→C64 + execute);
5. for lengths &gt; one safe quantum, split into ≤1-jiffy chunks with IRQ
   service between chunks (bitmap clear is ~8000 bytes ≈ several quanta).

**Native fallback:** `lda #byte` / `sta dst,x` / `dex` style for short fills,
or zp-indirect page loops for long fills without REU.

**Primary call sites (project code today):**

| Site | Size / pattern | Fit |
|---|---|---|
| Bitmap clear / SCNCLR-style | **8000** bytes at `$E000` | Excellent — main win |
| Bitmap screen matrix clear | **1000** bytes under `$DC00` (RAM-under-I/O gate) | Strong if fill runs under the same banking gate as graphics |
| Color RAM fill (`$D800–$DBE7`) | **1000** nybble-bytes, I/O visible | Strong — REC can target color RAM with I/O mapped |
| Text `screen_clear` | 1000 cells / attributes | Good if bulk |
| `arr_clear_payload` / string page zero | up to page-sized | Good when ≥ `N_fill` |
| Arena page zero / BSS-style init | page-sized or multi-page | Good in chunks |

**Not a substitute for memcopy:** fill is constant-byte only. Patterned
clears (e.g. checkerboard) still use copy or CPU.

**Default:** `N_fill = 32` (R8.2.1). Same REU-available rule as memcopy
(geoRAM store + co-detected REU assist, or REU store).

### 8.3 Loader and packaging (canonical image + REU patch)

Build **one** geoRAM-canonical expansion image and a small patch named **`REU`**
on the D64 — not two full product images.

| Host artifact | D64 | Purpose |
|---|---|---|
| `basicv3.prg` | `BASICV3` | Loader, detectors, resident payload |
| `georam.bin` | `GEORAM` | Full XIP/arena image (normative; fits in 512 KiB; low pages first) |
| REU patch object | **`REU`** | Versioned delta + fixup; **no geoRAM size field** |

**REU patch envelope (required fields):** magic, format version, ABI version,
**fingerprint of the paired `GEORAM` image**, fixup/reloc script or blob list,
CRC/checksum. Reject if fingerprint ≠ loaded image. Patch must not need
geoRAM capacity to apply XIP fixups—only page IDs and slot bases
(`$CE00` / `$C800+`). Peak install may include a disposable fixup utility in
dynamic RAM; after apply, return that RAM to free (R12 resident budget).

Install (§2): probe → prefer geoRAM store → install RAM payload → load
`GEORAM` into selected store → if REU store, load/apply **`REU`** → publish
expansion profile → `$35` → `compiler_init`.

### 8.4 Optional verify and swap

- **verify:** optional integrity / all-equal checks (not language search).
- **swap:** optional save-and-clear / buffer exchange (e.g. HIBASIC↔graphics).

Implement when those features need them; not required for Phase 1 language.

### 8.5 NMI re-detect, degraded editor, QUIT (R8.5)

**RESTORE key → NMI:** resident NMI handler re-enters editor init far enough to
**re-probe** geoRAM and REU and republish the expansion profile (or degraded
mode). Does not run expansion-native code before re-detect.

| Re-detect result | Action |
|---|---|
| Store still valid; REU assist lost | `reu_assist=0`; CPU memcopy/memfill; one status |
| Store still valid; both OK | refresh profile (“both” if both detected) |
| No store | **minimal resident editor**: error text; only **`QUIT`** accepted; any other command re-shows the error |

Minimal editor stays tiny: no full compiler/geoasm in resident.

**RESTORE / NMI distrust.** RESTORE is assumed to follow a **hang or untrusted
state**. The NMI path must be **minimal**:

- do not resume interrupted code or trust its stack;
- **invalidate CONT** and continuation frames;
- mark compile state **fully dirty** (aborted compiles untrusted);
- re-validate durable canaries/generations; re-probe devices; republish
  profile;
- never run expansion-native code before re-detect succeeds.

**`QUIT` (gateway, direct-only)** locked sequence:

1. restore banking, map pointers (program-end / `vartab` consistency), IRQ/NMI;
2. clean Compiler 2-owned normal-RAM control state;
3. **CLR explicitly** (stock `panic` alone is insufficient);
4. enter stock **READY**.

Keep the tokenized program (no cold-`init`). Leave expansion untouched.
Variables need not be preserved.

**Test contract:** after `QUIT`, V2-token-only programs must `LIST`/`RUN`
under stock BASIC V2. Non-V2 tokens may error on stock — acceptable.
Re-entry: reload installer; skip-reload uses the **install image
fingerprint(s)** already required for GEORAM/REU validation — if they match
what would be loaded, skip reload and re-enter after verify.

### 8.6 VICE snapshot names

| Snapshot | Meaning |
|---|---|
| `snap_georam_ready` | geoRAM store only; editor ready |
| `snap_reu_ready` | REU store only; editor ready |
| `snap_both_georam_store` | both detected; geoRAM store + REU assist; editor ready |
| `snap_neither` | neither device (abort or minimal editor path only) |

“Both” = both devices detected at install **or** after NMI re-detect.

## 9. Editor and Interrupt Requirements (R9)

### 9.1 Resident / expansion-native split

The resident front end (`docs/EDITOR.md`) owns timing-sensitive work and handoff
to expansion-native services. Those services are the same XIP pages under
geoRAM or REU page-buffer execution. IRQ never enters expansion-native code
and never programs the REC. Under REU, page DMA quanta leave room for pending
IRQ service between transfers.

### 9.2 Transactional Line Submission

Line submission is transactional for **source**: tokenize into scratch as stock
does, commit the program directory atomically, leave the old line on failure.
Report only stock-equivalent entry errors (tokenization failures). Full
compile may be deferred per §6.2 until `RUN` if needed to keep Return→ready
under ~0.5 s.

### 9.3 IRQ and NMI paths

The pinned IRQ (`docs/KERNAL_ABI.md` IRQ Call Order) is resident, bounded,
geoRAM-independent, and REC-independent. Its fixed order is: select KERNAL+I/O
mapping → call `UDTIM` → bounded project cursor service → call `SCNKEY` →
acknowledge CIA interrupt state → restore mapping and registers → `RTI`. The
foreground editor drains input with `GETIN` and never calls `SCNKEY` or
advances the jiffy clock itself. Under REU, DMA stalls the 6510; the gate
releases between measured chunks so pending IRQ service can run. Entry saves
interrupted CPU-port; never writes geoRAM selection or REC registers.

**NMI (RESTORE):** resident handler → invalidate CONT + full compile dirty →
re-enter editor initialization through device re-probe and profile publish
(§8.5). Do not resume the interrupted program. Cold `compiler_init` and NMI
re-entry share the re-detect tail so “both present” is defined identically at
install and after RESTORE.

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

### 11.1 Noels Retro Lab End-to-End Gate (R11.1)

`tests/performance/noels_retro_lab_cbm_v2.bas` is retained unchanged as the
integration-scale performance contract. The VICE test loads it through the
installed editor, invokes `RUN`, proves that the installed compiled artifact
executed rather than an editor/interpreter fallback, checks the ten dots,
`500500`, and `E` output, and records the artifact fingerprint plus `TI`
jiffies. The result is compared with the versioned 2,388-jiffy stock C64 BASIC
V2 reference in clean NTSC VICE. This gate exercises the normal production
path; generated native fixtures and prefilled timing data are invalid evidence.

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
- **Build order** (extends the common pipeline; detail in `REU_DESIGN.md` §9):
  validate tool paths/versions → validate common, geoRAM, REU, and
  selection-policy manifests → generate zero-page symbols and interference
  reports (§16), treating geoRAM/REU foreground lifetimes as mutually exclusive
  but startup-detection and IRQ lifetimes as concurrent → generate routine
  IDs, dual placement directories (geoRAM pages + REU overlays/slots),
  expansion dispatch table, arena constants, runtime ABI tables, test-entry
  exports, and the keyword trie/lookup report (§8, §7.4, §6.3, §6.2) →
  generate the `ld65` configuration from linker policy plus generated geoRAM
  page inventory and REU slot/overlay inventory → assemble each translation
  unit → link → validate cross-artifact contracts → construct
  `basicv3.prg`, `georam.bin`, `reu.bin`, loader manifests, and D64 (§8.3) →
  compute size/resource reports (§12.3) → generate and validate
  `API.md`/`MAP.md`, fingerprint/manifest → run system contracts and the
  configured smoke/full test selection (§14), including geoRAM-only, REU-only,
  both-present preference cases, and neither-device abort. A generator-input
  change forces dependents to rebuild; clean and no-change incremental builds
  with identical inputs produce byte-identical release artifacts.
- **Linker policy**: the checked-in policy owns canonical banking
  assumptions (§7.1), pinned runtime/IRQ/NMI placement, RAM-under-I/O
  ownership, the `$FFF9-$FFFF` reservation, REU overlay slot classes, and
  segment alignment/maximum sizes; the generated configuration adds the
  current geoRAM page inventory, REU overlay/slot inventory, and generated
  segments. `ld65` fails on overlap, overflow, missing segments, unresolved
  symbols, or vector misplacement, and post-link validators cross-check map,
  labels, binary lengths, placement manifests, and embedded headers.
- **Required artifacts** under `build/`: `obj/`, `listings/`, `generated/`,
  `compiler.bin`, `georam.bin`, `reu.bin`, `basicv3.prg`, `compiler.map`,
  `compiler.lbl`, `compiler.d64`, `build_manifest.json`,
  `loader_manifest.json`, `reu_loader_manifest.json`, `routine_directory.json`,
  `overlay_directory.json`, `reu_layout.json`, `arena_layout.json`,
  `runtime_abi.json`, `production_entries.json`, `test_entries.json`,
  `zp_allocation.json`, `size_report.json`, `keyword_lookup_report.json`,
  `API.md`, `MAP.md`, `requirements_matrix.json`, `requirements_matrix.md`.
  `API.md` and `MAP.md` are required on every build; `compiler.d64` is required
  for release/VICE installation tests but may be omitted from a narrowly
  selected developer build.
- **Packaging**: the release D64 stores `BASICV3`, `GEORAM`, and `REU` (§8.3).
  Packaging validates PRG load address/loader record, payload destination
  ranges, absence of load-time writes through visible I/O or ROM, geoRAM page
  and REU extent order/padding/checksums, D64 directory contents, and
  agreement with both loader manifests. Compression is only behind versioned
  formats with round-trip verification; uncompressed linked images remain
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
and, for IEEE, an independent IEEE oracle (§17). Their stock-numeric-mode
behavior and any inherited operand, coercion, or error behavior still compare
against the appropriate stock reference. A stock `?SYNTAX ERROR` for an extension
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
BASIC V2-compatible internal floating layout and stock-compatible
formatting — IEEE mode changes arithmetic and classification behavior, not
the on-disk/in-memory numeric encoding. `FPMODE1`/`FPMODE0`/`FPMODE()` select
and report the active mode independently of dialect (`BASIC2`/`BASIC3.5`,
§3.2). Core operations `+`, `-`, `*`, `/`, `SQR` are exactly rounded to the
destination format under the active rounding mode; transcendental functions
(trigonometric, logarithmic, exponential, power, etc.) are within 2 ULP over
their documented domain and may be geoRAM-native (§7.3 lists transcendental
math among the default geoRAM-backed subsystems) given they are not
compiled-speed-critical (§11).

Trig, transcendental, and IEEE routines follow `docs/IEEE754.md` and the
generated ABI. Implementations may reuse proven external algorithms where they
fit those contracts. Compiler 2's generated manifests, ZP allocation, dual
expansion placement, and ABI remain authoritative; external memory maps and
fixed addresses are not.

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
DESIGN.md                       (this file — top-level architecture/index)
REQUIREMENTS.md                  (common product requirements)
REU_REQUIREMENTS.md              (dual-device / REU EARS requirements)
REU_DESIGN.md                    (dual-device + REU detailed design)
REU_TASKS.md                     (REU implementation task breakdown)
docs/
  COMPILER_ARCHITECTURE.md     (layer map, program store, runtime ABI sketch)
  KEYWORDS.md                  (per-keyword language reference)
  MANUAL.md                    (user-facing manual: dialects, tokens, wedge, IEEE)
  BASIC_COMPATIBILITY_LIMITS.md (stock edge-limit contracts)
  CONTROL_FLOW.md              (FOR/DO frames, STOP/CONT continuation)
  RUNTIME_IO.md                (channel/file runtime request records)
  SYSTEM_PRIMITIVES.md         (PEEK/POKE/SYS/USR/WAIT/TI protection and clock)
  TESTING.md                   (test hierarchy and fixture mechanics)
  CANONICAL_TESTS.md           (fixture/regeneration policy)
  TRACEABILITY.md              (EARS trace record format)
  GRAPHICS_MEMORY.md           (bitmap/screen-matrix/color-RAM layout)
  GEORAM_BANKING.md            (geoRAM hardware contract and call ABI)
  GEORAM_LOADER_DESIGN.md      (install-time geoRAM loader and CGS1 stream)
  INCREMENTAL_COMPILATION.md   (per-line compile/publish machinery)
  COMPILE_EXPORT.md            (stock-C64 export format and budget)
  MEMORY_BUDGETS.md            (full normal-RAM and expansion byte accounting)
  ZERO_PAGE.md                 (zero-page manifest and interference graph)
  KERNAL_ABI.md                (KERNAL bridge contract and call surface)
  EDITOR.md                    (resident/expansion editor split)
  DOS_WEDGE.md                 ($ @ / ! direct-mode commands)
  LOOP_OPTIMIZATION.md         (loop descriptor model and fast paths)
  IEEE754.md                   (IEEE 754 profile summary)
  BUILD.md                     (toolchain, build order, artifacts)
  GENERATED_REFERENCE.md       (generated API.md and MAP.md schemas)
  VICE_TOOLS.md                (D64/PETCAT command recipes)
manifests/
  program_formats.json         (stock + C2P1 on-disk schemas)
  commands.json                (keyword/token/mode/dialect table)
  arenas.json, linker_policy.json, zero_page.json, …
```

`CGS1` names only the compressed geoRAM install stream. Dual-device packaging
always includes `BASICV3`, `GEORAM` (canonical expansion image), and `REU`
(the small REU patch). Stock V2/V3.5 tokenized programs use stock machine
formats (§5), not a proprietary envelope. The documents above, taken with this
file, cover every requirement group in `REQUIREMENTS.md` and
`REU_REQUIREMENTS.md`. Where a subsystem has a dedicated doc, that doc is
authoritative for its detail; this file owns the cross-cutting architecture
and the requirement-to-design map in §0.
