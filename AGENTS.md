# Compiler 2 Agent Guidelines

## Working Style

This project is a fresh design exercise. Prefer reading the local code and
documents first, then make changes that fit the existing structure in this
tree. This is a fresh design of a legacy project at "C:\Users\me\Documents\Coding Projects\compiler"; 
you may copy completed code if possible or relevant, or use it as guidance, but you will not assume that the design or implementation
meets the same requirements of this project.

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

Install and verify the Python tools with:

```powershell
pip install ruff mypy black pytest
ruff --version
mypy --version
black --version
pytest --version
```

If `mypy` is installed but not on `PATH`, use one of these:

```powershell
python -m mypy tools/ tests/ --strict
C:\Users\me\AppData\Local\Programs\Python\Python313\Scripts\mypy.exe tools\ tests\ --strict
$env:Path += ";C:\Users\me\AppData\Local\Programs\Python\Python313\Scripts"
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
