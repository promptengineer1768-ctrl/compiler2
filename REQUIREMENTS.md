# Compiler 2 Requirements

## 1. Status and Priority

This document defines required externally visible behavior and engineering
acceptance criteria. `DESIGN2.md` and `docs/COMPILER_ARCHITECTURE.md`
describe the implementation architecture that satisfies these requirements.
If the design documents and this file disagree, this document wins.

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
for the Commodore 64 with geoRAM.

It must:

- accept direct commands and numbered BASIC program lines;
- retain an editable tokenized program;
- compile stored programs to native 6502 code;
- execute compiled programs with BASIC-compatible results;
- load and save tokenized BASIC programs;
- save compiled programs in a documented executable format;
- provide large dynamic arenas for tokenized programs, compiled programs,
  scalar variables, arrays, strings, compiler data, and diagnostics;
- leave the largest practical amount of ordinary C64 RAM available to running
  programs;
- fail cleanly if geoRAM is absent, too small, corrupt, or changes unexpectedly.

The minimum supported geoRAM size must be 512 KiB. The build must declare the
minimum and detected capacity. Larger supported devices must increase arena
capacity without changing language semantics.

### 2.1 Phase 1 Install and Editor Slice

The first implementation phase must produce an installable C64 disk image with
a stock BASIC loader line:

```text
2026 SYS2061
```

The loader machine code must begin at decimal address 2061 (`$080D`). Starting
the loader must detect geoRAM presence and capacity, reject absent or
unsupported geoRAM cleanly, load the geoRAM payload, install it, and jump to
the Compiler 2 project initialization entry. Initialization must enter the
interactive editor.

The build-system geoRAM payload object must be named `georam.bin`. Disk-image
packaging must materialize that payload as a C64 file named `GEORAM` on the
D64 image. Loader and packaging tests must verify that this host-build name and
C64 disk filename remain consistent.

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
  space, subject to documented protected compiler storage.

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
- `FPMODE0`
- `FPMODE1`
- `FPMODE()`

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
| Program/session | `NEW`, `RUN`, `CONT`, `CLR`, `LIST`, `COMPILE` |
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

A stock BASIC V2 PRG loaded and saved without editing must preserve its program
semantics. A canonical-save test must compare the resulting token stream and
line structure with stock output.

Programs containing extended keywords are exempt from stock binary
compatibility. Their encoding must nevertheless be versioned, unambiguous,
round-trippable, and unable to reinterpret stock token bytes. Loading an
unsupported extension version must report an error instead of corrupting the
program.

The internal geoRAM representation may use handles or indexes, but `LOAD`,
`SAVE`, `LIST`, and compatibility tests must observe the canonical BASIC V2
form.

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

Incremental compilation is required. The system must compile each numbered
program line when that line is entered, deleted, or replaced. Immediate mode
must compile a full temporary program for execution, and the same machinery
must be reusable for per-line program compilation.

The tokenized source remains canonical. Per-line compiled records are cache
entries tied to source generation, dialect, numeric mode, runtime ABI version,
and dependency fingerprints. Replacing a line must publish the new compiled
record only after tokenization, validation, code generation, relocation, and
cross-line dependency checks succeed. On failure, the previous stored line and
published compiled state must remain intact.

Structural changes may invalidate dependent lines or trigger a whole-program
rebuild for branch, `DATA`, loop, or subroutine metadata. They must not fall
back to an interpreter path. A program is executable only when the compiled
image is consistent with the current source generation.

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

Every source-free compiled program produced by `COMPILE` must fit the memory
available to a stock C64 without geoRAM. The exported PRG load range, including
the BASIC loader line and every byte loaded by the PRG, must stay within
`$0801-$CFFF`. The standard standalone loader line is `2026 SYS2061`, so the
longest possible contiguous machine-code/runtime payload starts at `$080D` and
ends at `$CFFF`.

The build and compiler must report a standalone code budget for each compiled
program:

```text
standalone_code_budget = standalone_loader_bytes + compiled_program_bytes
```

`compiled_program_bytes` includes emitted user code, required runtime helpers,
relocation or metadata needed at runtime, variable descriptors, the standalone
direct-mode environment, and any other bytes that occupy the standalone PRG load
range. Tokenized source is not part of `compiled_program_bytes` and does not
count against the standalone code budget.
The installed development environment may store the compiled cache, compiler
metadata, diagnostics, and editor state in geoRAM or other extra memory, but
the published compiled cache for a program must obey the same standalone code
budget that `COMPILE` will enforce. A program that cannot be exported within
the stock C64 budget must be rejected as too large rather than accepted only in
the geoRAM-backed development environment.

During development, tokenized source may live entirely in geoRAM and may grow
independently of the standalone compiled-code budget. The maximum normal-RAM
compiled cache budget remains the standalone payload range `$080D-$CFFF`
plus the loader bytes accounted from `$0801`.

The stock C64 export budget leaves little or no normal RAM for variables when
code approaches `$CFFF`. Runtime variable, array, string, stack, and minimal
inspection-shell storage for an exported program must be budgeted separately
from the code image and must fit normal C64 RAM available after the exported
code is loaded. A graphics-mode exported program may use RAM beneath I/O at
`$D000-$D7FF` only through documented banking gates and only when that memory is
compatible with the selected graphics layout and hardware-visible I/O needs.

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
numeric operations should be geoRAM-native.

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

Bitmap graphics must preserve the proven C64 layout carried forward from the
legacy implementation:

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

### 7.3 Hard Memory Budgets

Normal RAM may be used up to the documented hardware and system reservations:

- `$0000-$0001` are the 6510 processor port registers;
- `$0100-$01FF` is reserved for inherent CPU stack operation;
- `$D000-$DFFF` is the visible I/O window in the canonical map;
- `$FFF9-$FFFF` is reserved high memory, including hardware vectors.

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

The following must be geoRAM-backed unless measurement proves that a small
resident component is necessary:

- editor parsing and line editing transforms;
- lexer and tokenizer;
- parser and semantic analysis;
- symbol, control-flow, IR, optimization, and code-generation passes;
- diagnostics formatting;
- trigonometric and transcendental math;
- tokenized program storage;
- compiled program storage;
- cold scalar variables and arrays;
- string payloads when the active runtime profile has geoRAM available.

Large objects must be addressed by stable logical handles rather than raw
window addresses.

Trig, transcendental, and IEEE extension math should reuse algorithms and
source from the legacy compiler when practical. That legacy work has already
been proven through Python proxy calculations and accuracy validation, so
Compiler 2 should treat it as preferred implementation evidence. The legacy
memory map, fixed addresses, and zero-page assignments are not requirements;
they are guidance to be adapted to Compiler 2's generated manifests, ABI, and
placement model.

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

## 8. geoRAM Requirements

The implementation must follow `docs/GEORAM_BANKING.md`.

In particular:

- detection must be non-destructive;
- the selected block/page, interrupt state, registers, and probe bytes must be
  restored;
- size detection must detect aliasing and reject unsupported capacities;
- every geoRAM routine must have a generated ABI contract;
- nested calls and callbacks must restore the caller's selected page;
- returning calls and true tail transfers must have distinct stack-correct
  mechanisms;
- no routine may execute across the 256-byte window boundary;
- build checks must validate every routine ID and dispatch-table record;
- IRQ/NMI code must be pinned and must not depend on the current geoRAM page.

## 9. Editor and Interrupt Requirements

The foreground editor may use geoRAM because human response time is the target,
not instruction-level latency. A small pinned screen/keyboard front end may
remain resident.

Line submission must be transactional:

- tokenize and validate into scratch storage;
- allocate or resize the destination record;
- commit the new program directory atomically;
- leave the old line intact on failure.

The IRQ path must remain resident, bounded, and geoRAM-independent. It must:

- update the KERNAL jiffy clock;
- scan the keyboard;
- maintain required cursor state;
- acknowledge the interrupt source;
- preserve the interrupted CPU-port and geoRAM context.

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
legacy-mode behavior and inherited operands/errors must still be compared with
the appropriate stock reference. Extension-specific results must use the
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
