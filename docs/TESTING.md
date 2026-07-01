# Testing Strategy

## Purpose

The test hierarchy finds inexpensive structural failures before invoking slow
hardware integration. Each layer proves only what it can model faithfully.

## Two Orthogonal Classifications

Every test has a scope and an execution environment.

Scope describes how much production behavior is exercised:

| Scope | Required meaning |
|---|---|
| Unit | One callable assembly subroutine invoked directly |
| Integration | One public call traversing multiple real subroutines |
| Functional | One complete user-visible feature through a stable interface |
| System contract | A whole-build, linker, layout, artifact, or environment invariant |
| E2E | Installed BASIC system from input submission to observable result |

Environment describes where the test runs:

- host/static;
- local 6502 emulator;
- local 6502 emulator with geoRAM;
- VICE snapshot/application;
- focused VICE hardware.

Markers do not redefine scope. A test can be `integration`, `georam`, and
`local`, or `e2e`, `vice`, and `basicv2`.

## System Contract Tests

`system contract` is the name for tests whose subject is the assembled system
rather than one routine or language feature. These tests usually inspect source
contracts, generated metadata, ca65 listings, ld65 maps, linked binaries, or
packaged artifacts.

The existing compiler suite demonstrates these useful system-test families:

- **Toolchain and reproducibility:** required ca65/ld65 versions, command-line
  defines/include paths, generated-input ordering, deterministic clean builds,
  and stale-output detection.
- **Linker and memory layout:** MEMORY/SEGMENT settings, origins, ceilings,
  overlap checks, RAM-under-I/O ownership, geoRAM page placement, and reserved
  `$FFF9-$FFFF` reserved high-memory tail and vectors.
- **Banking and architectural policy:** canonical `$35` mapping, only approved
  `$01` writers, pinned IRQ/NMI code, no forbidden ROM dependency, and no
  undeclared literal zero-page allocations.
- **Generated metadata:** routine IDs, geoRAM page/offset tables, block
  thresholds, relocation records, public/test entry manifests, arena schemas,
  zero-page coloring, dependency tables, and keyword-trie bounds.
- **Generated references:** `API.md` contains every production callable exactly
  once with a complete calling convention; `MAP.md` is sorted, non-overlapping,
  balances occupied/free totals, and agrees with linker, label, zero-page,
  arena, geoRAM, standalone, and size artifacts.
- **Binary artifact formats:** PRG load address and loader line, compiled-image
  format, geoRAM image size/order/padding, RAM sidecars, compressed payloads,
  D64 directory contents, checksums, and format versions.
- **Cross-artifact consistency:** addresses and sizes agree among source
  contracts, ca65 listings, ld65 maps, labels, manifests, binaries, and geoRAM
  directories.
- **Resource and performance contracts:** resident byte budget, segment
  ceilings, stack depth, context depth, arena capacity, free-page accounting,
  standalone compiled-code budget, line-entry latency reports, and benchmark
  regression thresholds.
- **Harness and environment contracts:** local-emulator bindings, geoRAM model,
  editor-mailbox symbols, VICE startup profiles, snapshot fingerprints, ROM
  identities, markers, and reference-fixture provenance.

This is not a miscellaneous bucket. A Python helper algorithm still receives a
unit test; a user-visible load/save workflow still receives functional/E2E
coverage. A system test applies when the asserted property belongs to the
complete build or its execution environment.

Canonical system modules include:

```text
tests/system/test_system_toolchain.py
tests/system/test_system_linker_contract.py
tests/system/test_system_memory_map.py
tests/system/test_system_banking_vectors.py
tests/system/test_system_generated_metadata.py
tests/system/test_system_generated_reference.py
tests/system/test_system_binary_artifacts.py
tests/system/test_system_resource_budgets.py
tests/system/test_system_test_environment.py
```

## Unit-Test Completeness

Every callable assembly subroutine must appear in either the production public
entry manifest or the test-build entry manifest and have at least one direct
unit-test node. Internal routines use test-only exports and do not become part
of the production ABI. Branch destinations and other local control-flow labels
are excluded unless they are callable subroutines.

Each public entry's test set covers, where relevant:

- nominal success;
- empty, minimum, maximum, and boundary values;
- each documented error return;
- A/X/Y and processor flags returned or preserved;
- stack balance and maximum contribution;
- zero-page reads, writes, and preservation;
- CPU banking and geoRAM selection;
- arena bounds, generations, and rollback.

A generated coverage check compares both entry manifests with collected pytest
node metadata. Missing routine tests fail collection or the static suite.

## Integration and Functional Tests

Integration tests call a public entry and allow it to traverse multiple
production subroutines. Mocks may provide external faults or hardware edges,
but must not replace the assembly path being integrated.

Functional tests begin at a stable feature boundary such as line submission,
program load/save, compilation, variable access, or a BASIC operation. They
assert user-visible output, errors, state, and persistence without requiring a
full cold boot for every case.

## E2E Language Organization

Critical E2E language coverage is organized first by language profile, then by
functions versus statements. Execution mode is a shared parameter within each
module. This keeps one semantic case together across modes and prevents three
mode-specific files from drifting.

The canonical modules are:

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

The consistent `basicv3` spelling is used in filenames; pytest requires the
leading `test_` for normal discovery.

### Execution Modes

The shared mode IDs are:

| Mode | Meaning |
|---|---|
| `immediate` | Submit the expression or statement directly at READY |
| `program` | Store numbered tokenized lines and execute through normal `RUN` |
| `compile` | Use explicit `COMPILE`, then execute the resulting native artifact |

Compile-mode tests must prove that the installed compiled image ran; reaching a
generic direct or program path does not count.

Each semantic case declares its legal modes. The default for ordinary BASIC
functions is all three. For example,
`test_e2e_basicv2_functions.py` contains named cases for the complete BASIC V2
function surface, including `SGN`, `ASC`, and the PRINT-context `SPC`, and runs
each in immediate, program, and compile modes where legal.

Direct-only statements are tested positively in immediate mode and negatively
in program and compile modes. A mode/profile cell may be `not applicable`, but
the reason must be machine-readable and included in the coverage report.

### Naming Inside Modules

Tests and parameter IDs must remain readable in pytest output:

```text
test_function_semantics[immediate-SGN-positive]
test_function_semantics[program-ASC-first-character]
test_function_semantics[compile-SPC-print-context]
```

Do not create one opaque test containing every keyword. Cases may share a
runner, but failures must identify profile, mode, keyword, and semantic case.

The collected E2E case IDs are compared with the generated token/keyword
manifest. Every implemented keyword and operator must be represented. Modifiers
such as `TO`, `THEN`, and `STEP` map to semantic cases in their containing
statement module rather than artificial standalone invocations.

## Smoke Tests

`smoke` is a marker applied to a stable, fast subset of authoritative tests at
each scope. The smoke selection includes at least:

- one public-entry ABI unit test;
- one multi-routine integration test;
- one linker/memory-map system contract test;
- one generated-artifact system contract test;
- one geoRAM selection/call test;
- one function and one statement from each active language profile;
- immediate, program, and compile execution;
- one snapshot-backed E2E READY-to-result path;
- one focused keyboard/IRQ health test when VICE smoke is requested.

Smoke tests are not separate simplified test bodies. The same pytest node runs
in smoke and full selections.

## Regression Placement

A regression is evidence that an edge case was missing from an existing
behavioral group. Add the case to the suite that already owns that behavior:

- routine contract failures extend the appropriate unit suite;
- multi-routine failures extend the owning integration suite;
- user-visible feature failures extend the owning functional suite;
- linker, layout, artifact, or environment failures extend the appropriate
  system contract module;
- language semantic failures extend the appropriate profile/function-or-
  statement E2E case table and legal execution modes;
- IRQ, keyboard, device, or timing failures extend the focused hardware suite.

Do not create `tests/regressions/`, a `regression` marker, top-level
`test_regression_*.py` files, issue-number files, or one-off bug categories.
Prefer adding a named parameter or focused test to the existing module. If the
owning component has no module yet, create one only under the established scope
directory and stable component/profile naming rules.

A regression case added for the bug currently being fixed may also carry the
`smoke` marker so the fast selection guards it immediately. It remains the
authoritative case in its normal group and retains every applicable scope,
environment, profile, and mode marker.

## Pytest Layout and Markers

The planned layout is:

```text
tests/
  unit/
  integration/
  functional/
  system/
  e2e/
  hardware/
  fixtures/
```

Required scope markers are `unit`, `integration`, `functional`, `system`, and
`e2e`. Cross-cutting markers include `smoke`, `static`, `local`, `georam`,
`vice`, `hardware`, `basicv2`, `basicv3`, `basicv35`, `ieee`, `immediate`,
`program`, and `compile`.

Files use `test_<scope>_<profile>_<kind>.py` for matrix suites and
`test_<component>.py` for focused unit/integration suites. Avoid historical
phase numbers in filenames once a stable component or behavior name exists.

## Layer 1: Host and Static Tests

Run first on every change.

This layer covers:

- token, program, compiled-image, and arena format parsing;
- canonical BASIC V2 fixtures and golden phase artifacts;
- generated routine IDs, placement, relocations, and checksums;
- zero-page graph coloring and linker overlap;
- call-graph, stack-depth, ABI, and resident-size checks;
- source-independent compiler phase models;
- requirement-to-test traceability.

Static banking checks must prove that only the KERNAL bridge and
RAM-under-I/O gate write the CPU-port banking bits. They must also reserve
`$FFF9-$FFFF` and verify generated NMI, RESET, and IRQ/BRK vector targets.

Static source-pattern checks are useful guardrails but cannot establish runtime
correctness by themselves.

## Layer 2: Local 6502 Routine Tests

The local emulator directly calls exported assembly entry points and runs to a
declared stop such as RTS, BRK, error, or cycle budget.

It can:

- load PRGs and linked runtime segments;
- read and write RAM and CPU registers;
- execute individual 6502 routines deterministically;
- enforce instruction/cycle budgets;
- poison and inspect zero page, stack, and scratch memory;
- model CPU-port bank visibility and optional ROM overlays;
- compare generic and optimized execution.

Use it for tokenizer, parser, math, descriptors, arenas, code generation,
runtime helpers, errors, and ABI contracts.

## Layer 3: Local geoRAM Integration

The geoRAM-capable local emulator additionally models:

- `$DE00-$DEFF` as a selected persistent 256-byte window;
- `$DFFE` page and `$DFFF` block selection;
- RAM beneath the I/O window;
- loading a geoRAM image;
- page persistence and selection restoration;
- nested returning calls, tail transfers, callbacks, and data access.

Use it for almost all geoRAM logic before VICE.

### Local Emulator Limitation

The local emulator does not schedule real IRQ or NMI execution. It therefore
does not prove:

- CIA timer interrupt timing or acknowledgement;
- KERNAL `UDTIM`/`SCNKEY` execution under real IRQ;
- keyboard matrix scanning and repeat timing;
- VIC raster behavior;
- IEC device timing;
- arbitrary interrupt arrival during a geoRAM instruction sequence.

Minimal ROM stubs prove bridge mechanics, not KERNAL semantics. Those concerns
belong to focused VICE tests.

## Layer 4: VICE Snapshot Application Tests

Normal language and application tests run in VICE from a fingerprinted snapshot
representing a freshly loaded, installed, and ready BASIC3 environment.

The snapshot fingerprint includes at least:

- installable PRG;
- geoRAM image;
- ABI/schema versions;
- startup dialect and numeric profile;
- VICE machine and geoRAM configuration.

A fingerprint mismatch makes the snapshot unusable. Snapshot regeneration is
intentional and reported, never an automatic way to hide startup regressions.

At test start:

1. load the matching snapshot;
2. verify READY state, dialect/profile, CPU port, IRQ vectors, and geoRAM
   signature;
3. clear host-injected keyboard and editor-mailbox state;
4. submit commands through the editor mailbox/input buffer;
5. wait on a submit counter, READY state, error code, or explicit completion
   marker;
6. collect screen, memory, variable, and arena observations.

Direct injection is atomic: pause VICE, write the buffer and length/pending
fields, resume, and wait for consumption. It exercises editor submission and
all application logic without introducing keyboard timing into every test.

## Layer 5: Focused VICE Hardware Tests

The slowest layer is reserved for behavior that requires VICE fidelity.

### Keyboard Proof

A small dedicated suite proves the complete path once:

```text
VICE key event -> CIA matrix -> IRQ SCNKEY -> KERNAL queue
-> GETIN -> editor -> line submission
```

It covers ordinary keys, Return, delete/edit keys, shifted keys, queue limits,
and key repeat. The broad language suite then uses direct editor-buffer
injection.

### IRQ and Timer Proof

Independent tests verify:

- CIA Timer A is configured for the selected PAL/NTSC profile;
- the IRQ vector reaches pinned code;
- `UDTIM` advances `$A0-$A2`;
- cursor service is bounded;
- `SCNKEY` follows `UDTIM`;
- timer and keyboard continue during long compile, editor, math, and compiled
  loop operations;
- interrupted CPU-port and geoRAM selection are restored;
- STOP closes channels/flushes input as required.

These tests do not depend on the language suite to incidentally trigger IRQ
coverage.

### Device and Mapping Proof

VICE also covers real KERNAL load/save/channel calls, ROM/I/O banking, geoRAM
capacity profiles, and interrupts at sensitive bank-switch boundaries. Tests
assert `$35` during normal editor/runtime/geoRAM operation, `$36` only inside a
KERNAL bridge, and restoration to `$35` after KERNAL and RAM-under-I/O access.

## Canonical and Differential Tests

Stock BASIC implementation details are explained by the ROM source/reference
environment in:

`C:\Users\me\Documents\Coding Projects\c64rom`

VICE observations are the final source of truth for accepted C64 and Plus/4
behavior. Source listings, labels, and reports explain why the behavior occurs
and guide implementation. Fixtures record input program, mode, output, errors,
variable state, and any relevant token bytes. Extended-language fixtures use
the documented Compiler 2 semantics.

Optimizations always compare against the generic implementation. A benchmark
result never substitutes for a semantic comparison.

Performance tests measure CPU cycles for compiled-vs-stock comparisons. BASIC
V2 cases compare against stock C64 BASIC V2. BASIC 3.5 cases compare against
stock Plus/4 BASIC 3.5 and use cycle counts rather than elapsed time because
the machines have different clocks. IEEE extensions, editor services, and DOS
wedge commands have no compiled-speed acceptance target.

The Phase 1 `FOR`/`NEXT` timing program is a hard benchmark: the compiled run
must report less than 60 C64 jiffies. Incremental line-entry latency is a
reported responsiveness metric with an ordinary-line target of about 0.5
seconds, but it is not a hard pass/fail semantic gate.

### Stock VICE Oracles

Expected E2E semantics are generated from clean stock VICE machines:

| Compiler 2 profile | Reference executable | Stock reference |
|---|---|---|
| BASIC V2 | `x64sc.exe` | C64 BASIC V2 in C64 mode |
| BASIC V3 inherited V2 behavior | `x64sc.exe` | C64 BASIC V2 |
| BASIC V3.5 | `xplus4.exe` | Plus/4 BASIC V3.5 |
| IEEE extensions | stock profile where inherited behavior applies, plus IEEE oracle | no stock extension equivalent |

The installed executables are under:

`C:\Users\me\Documents\Coding Projects\tools\vice-mcp\dist\HeadlessVICE-windows-x86_64`

Reference generation starts each machine with its stock ROMs and clean default
state. It executes the exact immediate command or numbered stored program,
captures raw screen/error/state observations, and writes versioned fixtures
under `tests/fixtures/reference/`.

Assertions are derived from those fixtures rather than transcribed from memory.
The stock ROM behavior is immutable, so BASIC V2 and implemented BASIC V3.5
fixtures normally are generated once for the lifetime of the project. New
reference cases are generated when additional edge cases are discovered.
Routine Compiler 2 implementation changes do not regenerate existing expected
results.

Regeneration of an existing fixture is an explicit reviewed operation limited
to a documented oracle/ROM correction, generator or normalization fix, or
fixture-schema migration. Each fixture includes:

- profile and machine (`c64` or `plus4`);
- VICE executable/version and ROM checksums;
- exact source and input sequence;
- immediate or program reference mode;
- raw screen/error/state capture;
- normalized semantic value, error, and side effects;
- generator and schema version.

For Compiler 2 `compile` mode, the expected semantics come from the matching
stock program-mode fixture. The E2E harness must additionally prove that the
compiled artifact, rather than the ordinary RUN path, produced the result.

Normalization may remove banners, cursor placement, screen-code representation,
or hardware-specific display details only when the rule is named and tested.
It must not erase numeric formatting, error classes, control-flow effects,
variable values, file behavior, or other language semantics.

Plus/4 reference fixtures do not define C64 token bytes or memory addresses.
Binary program compatibility remains a C64 BASIC V2 contract.

## Failure Localization

When a VICE test fails, reproduce downward:

1. capture the command, source generation, routine ID, arena metadata, and
   selected block/page;
2. replay the relevant phase artifact or runtime call locally;
3. extend the owning local suite when the local model can represent the fault;
4. extend the owning VICE suite only when hardware interaction is essential.

Debug output belongs in `debug/`. Reproducers must be deterministic and must
not become alternate production implementations.

## Timing Guidance

Prefer state-based waits over fixed sleeps. Keyboard hardware tests may require
short pacing; mailbox tests should not.

Run layers 1-3 in the foreground. Run broad VICE suites in isolated background
processes with per-test timeouts, captured output, and stale VICE instances
removed before a new run.

## Completion Rule

A feature is complete when:

- every new callable subroutine has direct unit coverage;
- its multi-subroutine paths have integration coverage;
- its user-visible behavior has functional coverage;
- its build/layout/artifact obligations have system contract coverage;
- applicable profile/mode/kind E2E matrix cells are present;
- stock-compatible E2E assertions have traceable C64 V2 or Plus/4 V3.5
  reference fixtures;
- its requirements are mapped to tests;
- static and local layers pass;
- relevant VICE integration passes;
- real keyboard/IRQ/device tests pass when the feature depends on them;
- resident and geoRAM size deltas are recorded;
- documentation and generated schemas agree.
- `API.md` and `MAP.md` are present, deterministic, current, and consistent
  with the completed build.
