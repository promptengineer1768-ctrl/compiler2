# Compiler 2 Agent Guidelines

When instructions conflict, correctness and completion integrity take precedence
over preserving previously passing but inadequate tests or `[x]` task markers.

## Working Style

Compiler 2 is a **new** project. Prefer reading the local design, code, and
tests in this tree first, then make changes that fit the current structure and
contracts here.

**Design is the source of truth for architecture.** Normative order:

1. `REQUIREMENTS.md` (and `REU_REQUIREMENTS.md` for dual-device expansion)
2. `DESIGN.md` (and `REU_DESIGN.md` for dual-device / REU detail)
3. focused docs under `docs/` that `DESIGN.md` points to
4. manifests, generated contracts, and production source

When documents disagree, requirements win over design prose; design wins over
implementation notes, skeletons, and task lists. Do not retain obsolete
implementations, bounded fallback paths, compatibility wrappers, dual
representations, or deprecated interfaces. When existing code or an API is
incorrect for the current design, replace it completely and update all callers,
tests, manifests, generated contracts, and documentation to the single correct
design.

**External reference (implementation aid only).** An earlier C64 compiler
codebase may exist at `C:\Users\me\Documents\Coding Projects\compiler`. Agents
may consult it while implementing to recover proven algorithms, measurements,
or preferences, but it is **not** a design authority, not a compatibility
target, and not part of this repository. Do not assume its design or behavior
meets Compiler 2 requirements. Prefer algorithms that fit Compiler 2
manifests, ABI, and memory model; never copy fixed addresses or memory maps
from that tree as if they were normative.

The authoritative stock Commodore BASIC V2 and KERNAL reference is at
`C:\Users\me\Documents\Coding Projects\c64rom`. It contains source that builds
the ROMs used by VICE, retains labels, and generates BASIC/KERNAL API and
zero-page reports. Use it to resolve stock semantics, routine labels, entry
points, and zero-page locations instead of relying on remembered addresses.
Useful starting points are `docs/BASIC_API.md`, `docs/BASIC_ZP.md`,
`docs/KERNEL_API.md`, `docs/KERNEL_ZP.md`, and `debug/c64rom.labels`.
VICE observations are the final source of truth for accepted C64 and Plus/4
emulation behavior; use `c64rom` to explain and implement that behavior.

- Use `rg` or `rg --files` for searching when available.
- Parallelize file reads when it helps.
- Keep edits tightly scoped to the request.
- Do not revert or overwrite unrelated user changes.
- Prefer non-interactive git commands.
- Use `apply_patch` for manual file edits.
- Put all temporary files, diagnostic captures, emulator dumps, one-off
  reproducers, and other debug artifacts under `debug/`. The directory is safe
  to delete and must never be an input to a release build.

### Project Knowledge Graph

Use the `graphify` skill in this project for architecture, implementation, and
documentation analysis. When `graphify-out/` exists, query it before answering
broad questions about the project, then verify critical conclusions against
the source documents or code.

Run a full Graphify build for a new tree and an incremental update after
meaningful code or documentation changes. `graphify-out/` is generated
navigation and audit data; it is not a production build input or a substitute
for normative documents, source inspection, or tests.

## Development Environment

### 6502 Toolchain

Use the cc65 toolchain for all production assembly:

```text
C:\Users\me\Documents\Coding Projects\tools\ca65.exe
C:\Users\me\Documents\Coding Projects\tools\ld65.exe
```

`ca65` is the required assembler and `ld65` is the required linker. Do not
introduce another assembler dialect. The known baseline is version 2.19; record
the actual versions in build manifests.

The canonical build entry point is `build.ps1`. Build details and required
artifacts are defined in `docs/BUILD.md`.

### Python

**Required:** Python 3.13. The project uses features not available in earlier versions.

```powershell
# Use Python 3.13 explicitly
$PYTHON = "C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe"
& $PYTHON --version  # Python 3.13.13

# Install and verify tools
& $PYTHON -m pip install ruff mypy black pytest
& $PYTHON -m ruff --version
& $PYTHON -m mypy --version
& $PYTHON -m black --version
& $PYTHON -m pytest --version
```

**Run Python commands:**

```powershell
# Run scripts
& $PYTHON tools/zp_alloc.py
& $PYTHON tools/validate_build.py --all

# Run tests
& $PYTHON -m pytest tests/ -v
& $PYTHON -m pytest tests/ -m smoke

# Run type checker
& $PYTHON -m mypy tools/ tests/ --strict
```

**Add to PATH (optional):**

```powershell
$env:Path += ";C:\Users\me\AppData\Local\Programs\Python\Python313\Scripts"
```

### VICE Next

E2E and hardware tests drive a real emulator through the VICE Next supervised
native-monitor transport. The tooling lives at:

```
C:\Users\me\Documents\Coding Projects\tools\vice-next-mcp
```

Configure the instrumented executables explicitly; the shared harness creates
isolated VICE Next processes and owns their native-monitor ports:

```
C:\Users\me\Documents\Coding Projects\builds\vice-instrumentation-windows\extracted\src\
    x64sc.exe     # C64  (BASIC V2)
    xplus4.exe    # Plus/4 (BASIC V3.5)
```

**Runtime configuration:**

```powershell
$env:VICE_X64SC = "C:\Users\me\Documents\Coding Projects\builds\vice-instrumentation-windows\extracted\src\x64sc.exe"
$env:VICE_XPLUS4 = "C:\Users\me\Documents\Coding Projects\builds\vice-instrumentation-windows\extracted\src\xplus4.exe"
```

**For the test suite:** VICE is launched automatically by the harness in
`tools/vice_harness.py` via isolated VICE Next instances. E2E/hardware tests
marked `@pytest.mark.vice` are gated on a runnable configured runtime; do not
replace unavailable hardware execution with mocks or synthetic state. Use the
shared harness runtime-discovery API rather than hard-coded paths.

```powershell
# Run the VICE-backed E2E/hardware suite (requires the binaries above)
& $PYTHON -m pytest tests/e2e tests/hardware -v
```

## Coding Standards

### Python Code Style

All Python code must follow these standards:

1. Type annotations on all function signatures.
2. Google-style docstrings for modules, classes, and functions.
3. Black formatting with 88 character line length and Python 3.12 target.
4. Ruff linting with `E`, `W`, `F`, `I`, `UP`, `D`, and `ANN`.

### Assembly Code Style

1. Use snake_case for filenames.
2. Use descriptive labels with proper scoping.
3. Document exported functions and complex logic.
4. Use relative includes from the `src/` root.
5. Every public entry must document its purpose, inputs, outputs, side effects,
   registers clobbered, flags returned, and zero-page use.
6. Zero-page assignments must come from the generated lifetime/interference
   allocation; do not introduce literal project ZP addresses in assembly.

## General Direction

- Favor small, explicit abstractions over broad ones.
- Prefer structured data and parsers over ad hoc text handling where possible.
- Keep the runtime small and the design inspectable.
- Add tests when behavior changes.
- Update relevant documentation when adding or changing features.

## Test Organization

- Give every callable assembly subroutine direct unit coverage. Use test-only
  exports for internal routines; do not enlarge the production ABI.
- Add integration tests for public calls that traverse multiple subroutines.
- Add functional tests for complete user-visible features.
- Add system contract tests for toolchain, linker, memory-map, banking/vector,
  generated-metadata, artifact, resource, and test-environment invariants.
- Keep critical language E2E tests under `tests/e2e/`, grouped by BASIC profile
  and functions versus statements as defined in `docs/TESTING.md`.
- Parameterize immediate, program, and compile modes through the shared mode
  runner instead of duplicating semantic cases across files.
- Mark a stable subset of authoritative tests `smoke`; do not create weaker
  smoke-only implementations.
- Treat every regression as a missing edge case in an existing test group.
  Extend the owning suite or case table; do not create ad hoc regression
  directories, markers, top-level files, or bug-number suites.
- A regression case added for the bug currently being fixed may also be marked
  `smoke`, but it must retain its normal category and all applicable markers.
- Test names and parameter IDs must identify profile, mode, keyword, and case.
- Derive stock-compatible E2E assertions from versioned VICE C64 BASIC V2 or
  Plus/4 BASIC V3.5 reference fixtures; do not hand-invent expected semantics.
- Stock BASIC V2 and implemented BASIC V3.5 assertion fixtures normally need
  to be generated only once because their reference ROM semantics do not
  change. Add reference runs when new edge cases are discovered; do not
  routinely regenerate unchanged assertions after Compiler 2 changes.

## Documentation

Keep documentation aligned with the implementation. When adding new behavior,
update the relevant docs in `docs/` and keep comments succinct and useful.

## Completion Integrity

A task is complete only when its stated user-visible behavior works through the
real production path. File existence, successful assembly, placeholder logic,
mocked execution, or passing isolated tests are not completion.

### Prohibited Completion Shortcuts

Do not:

- implement stubs, skeletons, placeholders, no-op success paths, dummy values,
  hard-coded test answers, or "for now" behavior;
- mark a task complete while comments contain `TODO`, `stub`, `placeholder`,
  `not implemented`, `future work`, `later phase`, or equivalent deferrals;
- weaken, delete, skip, xfail, narrow, or rewrite a failing test merely to make
  it pass;
- replace expected behavior with assertions matching the current
  implementation;
- use test-only emulator shims, hooks, monkeypatches, mocks, or synthetic state
  to stand in for production assembly behavior;
- enlarge the production ABI solely to expose state to tests;
- claim integration or E2E coverage when production stages are bypassed;
- mark verification tasks complete without running their documented commands;
- infer completion from existing `[x]` markers in generated task Markdown.

If a temporary scaffold is necessary, mark the owning task `[~]`, document the
missing behavior, and keep an authoritative failing test for it.

### Required Completion Evidence

Before changing any task to `[x]`:

1. Read the full task, prerequisites, normative documentation, and acceptance
   tests.
2. Identify the complete production call path and inspect every routine it
   traverses.
3. Add or strengthen a test that fails for the missing behavior.
4. Run that test before implementation and confirm the expected failure.
5. Implement the production behavior without test-specific branches.
6. Run direct unit tests for every changed callable assembly routine.
7. Run the owning integration, functional, system, and E2E tests.
8. For user-visible C64 behavior, verify the actual built artifact in VICE.
9. Inspect generated binaries, maps, disk files, and installed memory where
   relevant; do not rely only on process exit codes.
10. Search changed production code for unfinished markers and reject completion
    if any apply to the task.
11. Update documentation and traceability.
12. Record the exact verification commands and results.

A passing test is insufficient when the test does not exercise the production
path or does not assert the task's full behavior.

### Test Integrity

Tests are requirements, not obstacles.

When a test fails:

- fix production code when the test expresses the documented requirement;
- fix the test only when authoritative documentation, stock VICE behavior, or
  an independently verified artifact proves the test itself is wrong;
- document that evidence when changing an established expectation;
- preserve or strengthen the original behavioral coverage;
- never substitute a weaker assertion.

Mocks are permitted only for genuine external boundaries in host-tool unit
tests. At least one higher-level test must exercise the real boundary.
Assembly behavior must be tested by executing the real assembled bytes.

### Mandatory Regression Coverage

Every discovered defect must produce:

- a focused regression test for its root cause;
- an integration test for the affected production path;
- an artifact or system contract when packaging/linking caused the defect;
- a VICE E2E test when the defect was user-visible on the C64.

Tests must detect recurrence independently. One broad happy-path test is not a
substitute for root-cause coverage.

### Task Manifest Status and Completion Rules

`manifests/tasks.json` is the formal source of truth for task state and
completion evidence. `TASKS.md` and `REU_TASKS.md` are generated views: never
edit their checkboxes directly. Read `docs/TASKS_MANIFEST.md` before changing
task status.

To check current task state, run:

```powershell
& $PYTHON tools/task_manifest.py validate
```

To update a task, change its matching `tasks[]` record in
`manifests/tasks.json`, retain its `requirements` and `design_refs`, add
evidence records, then regenerate and validate:

```powershell
& $PYTHON tools/task_manifest.py render
& $PYTHON tools/task_manifest.py validate
```

An `"x"` task requires at least one passing machine-readable evidence record
and no failing, missing, stale, skipped, or invalidated evidence. Each record
must state its `kind`, machine-addressable `target`, `status`, and the exact
`claim` it proves. Use one record per test, artifact, public symbol, command,
or VICE run; do not collapse several assertions into an unverifiable prose
claim. The validator rejects stale generated Markdown, duplicate task IDs, and
unsupported completion states. It also rejects an unanchored task or a
traceability requirement with no owning task.

Treat every existing status as untrusted until verified.

- `[ ]`: not started
- `[~]`: partially implemented, scaffolded, unverified, or failing acceptance
- `[x]`: fully implemented and verified through the required production path
- `[-]`: blocked with a concrete documented blocker
- `[!]`: intentionally skipped with an approved reason

Never bulk-mark tasks complete. Audit each task against its complete acceptance
criteria. If any prerequisite, behavior, test layer, documentation update, or
verification command is missing, leave it `[~]`.

Structural subtasks such as "create file" may be `[x]` when the artifact exists,
but this does not imply that the enclosing feature is complete.

### Stop Conditions

Do not report success while any of the following is true:

- required tests fail or are skipped unexpectedly;
- the build emits warnings indicating missing required segments or artifacts;
- production code contains relevant placeholder behavior;
- generated artifacts disagree with source manifests or linker output;
- the release artifact was not rebuilt after source changes;
- the E2E test uses a stale artifact;
- the feature works only through a test shim or diagnostic export;
- the implementation satisfies only the example case rather than the general
  requirement.

Report partial progress honestly and keep the task `[~]`.
