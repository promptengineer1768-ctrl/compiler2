# Test Suite Layout

The normative test strategy is in `../docs/TESTING.md`.

## Scope Directories

```text
tests/
  unit/         one callable assembly subroutine per direct test target
  integration/  one call exercising multiple production subroutines
  functional/   complete user-visible features
  system/       linker, layout, build, artifact, and environment contracts
  e2e/          installed-system language and workflow tests
  hardware/     focused VICE keyboard, IRQ, timer, device, and mapping tests
  fixtures/     canonical inputs and expected artifacts
```

## Critical E2E Modules

Use these canonical pytest filenames:

```text
test_e2e_basicv2_functions.py
test_e2e_basicv2_statements.py
test_e2e_basicv3_functions.py
test_e2e_basicv3_statements.py
test_e2e_basicv35_functions.py
test_e2e_basicv35_statements.py
test_e2e_basicv3_functions_ieee.py
test_e2e_basicv3_statements_ieee.py
```

They belong under `tests/e2e/`. Each module uses the shared `immediate`,
`program`, and `compile` mode parameter. A function such as `SGN`, `ASC`, or
`SPC` has separately named semantic cases and runs in every legal mode.

Statements restricted to immediate mode include positive immediate coverage
and explicit rejection coverage in program and compile modes.

## Markers

Required scope markers:

```text
unit integration functional system e2e
```

Required cross-cutting markers:

```text
smoke static local georam vice hardware
basicv2 basicv3 basicv35 ieee
immediate program compile
```

The `smoke` selection reuses normal authoritative tests. It does not contain
weaker duplicate implementations.

## Regression Tests

Regression cases extend the existing suite that owns the affected behavior.
Treat the defect as an edge case missing from unit, integration, functional,
system, E2E, or hardware coverage. Add it to the relevant module or parameter
table rather than creating a regression directory, marker, top-level file, or
bug-number-specific suite.

A case added for the bug currently being fixed may also be marked `smoke`.
That marker is additive: the test remains in its normal category and retains
all applicable environment, profile, and execution-mode markers.

## System Contract Modules

Use stable whole-system names:

```text
test_system_toolchain.py
test_system_linker_contract.py
test_system_memory_map.py
test_system_banking_vectors.py
test_system_generated_metadata.py
test_system_generated_reference.py
test_system_binary_artifacts.py
test_system_resource_budgets.py
test_system_test_environment.py
```

These tests inspect the complete build or environment. Tests for an individual
build-helper function remain unit tests.

## Stock Reference Fixtures

Stock-compatible keyword expectations come from explicit VICE reference runs:

- C64 `x64sc` with stock BASIC V2 for BASIC V2;
- Plus/4 `xplus4` with stock BASIC V3.5 for BASIC V3.5.

Fixtures live under `tests/fixtures/reference/` and record machine, ROM/VICE
identity, exact source, raw observation, normalized semantics, and generator
version. Compiler 2 compile mode compares with the matching stock program-mode
result.
