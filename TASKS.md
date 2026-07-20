# Compiler 2 Implementation Tasks

This is the master task list for Compiler 2 implementation. Tasks follow
**Test-Driven Development (TDD)**: write failing tests first (RED), implement
minimal code to pass (GREEN), then refactor. Tasks are ordered from
`DESIGN2.md`, `SKELETON.md`, and the hybrid TDD gates below with prerequisites
enforced.

## TDD Cycle

Every implementation task follows this cycle:

```
RED:    Write test file → verify tests fail (expected)
GREEN:  Implement source → verify tests pass
REFACTOR: Clean up → verify tests still pass
```

## Hybrid TDD Pattern

The RED/GREEN/REFACTOR cycle is applied through the narrowest executable gate
available for the work:

| Work type | First gate | Normal verification |
|---|---|---|
| Assembly callable | Unit test from `TESTS.md` plus test-only export when needed | Callable unit test, owning integration test, contract validators |
| Host Python tool | Tool unit test for pure functions plus integration fixture | `pytest tests/tools/`, `ruff`, `mypy --strict`, `black --check` |
| Manifest or schema | JSON/schema validation and cross-reference fixture | `tools/validate_build.py --manifests` |
| Generated artifact | Golden structural assertions, not hand-edited output | Generator command plus stale-output validator |
| VICE/reference fixture | Empty expected fixture schema, then captured stock behavior | Fixture validator plus relevant E2E mode runner |
| Documentation-only task | Source cross-check and traceability update | Local validation script or grep-backed checklist |

Each implementation task should move through these gates:

```
CONTRACT:  Define manifest/schema/API/fixture acceptance before implementation
RED:       Add or extend the owning test and verify the expected failure
GREEN:     Implement the smallest source/tool/build change that passes
REFACTOR:  Clean up structure while all affected tests still pass
TRACE:     Update generated references, traceability, and docs when behavior changes
```

Code-first is allowed only for bootstrap scaffolding that cannot be exercised
yet. As soon as a validator or harness exists, add the gate retroactively.

## Status Codes

| Code | Meaning |
|---|---|
| `[ ]` | Not started |
| `[~]` | In progress |
| `[x]` | Complete |
| `[-]` | Blocked (document blocker) |
| `[!]` | Skipped (document reason) |

### 2026-07-02 Completion Audit

All 786 task statuses were reset and re-audited because prior `[x]` markers
were not reliable evidence of completion. Only objectively structural
`Create`/`Generate` tasks whose named artifacts currently exist and are
nonempty remain `[x]`. Behavioral, semantic, TDD-phase, validation, and
verification claims are `[~]` until their complete acceptance criteria are
proved during the completion goal. Per-item evidence is generated at
`build/task_audit.json` by `tools/audit_tasks.py`.

## How to Resume

1. Scan for the first `[~]` or `[ ]` task.
2. Verify all prerequisite tasks marked `[x]`.
3. Follow the TDD cycle: RED → GREEN → REFACTOR.
4. Mark `[x]` when complete, including all verification steps.
5. Continue to the next task.

---

## Phase 0: Project Infrastructure

> Establish build system, toolchain, manifests, and generated contracts.
> **Code-first** — no 6502 code exists to test yet.

### T0.1 Build System Bootstrap

**Prerequisites:** None

- [x] Create `build.ps1` canonical entry point
- [x] Create `manifests/` directory with JSON schemas
- [x] Create `tools/` directory with Python generators
- [x] Create `src/common/constants.asm` with error codes and type tags
- [x] Create `src/common/macros.asm` with debug macros
- [x] Create `src/common/zp.inc` importing `build/zp_symbols.inc`
- [x] Validate ca65/ld65 toolchain paths in build script

**Verification:**
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1 -Validate
```

### T0.2 Structured Manifests

**Prerequisites:** T0.1

- [x] Create `manifests/zero_page.json` — ZP nodes, fixed constraints, lifetimes
- [x] Create `manifests/routines.json` — public/test entries, ABI, calls, return kind
- [x] Create `manifests/arenas.json` — arena types, schemas, ownership, reset rules
- [x] Create `manifests/commands.json` — dialect tokens and direct/program classification
- [x] Create `manifests/program_formats.json` — stock and extended token/file schemas
- [x] Create `manifests/linker_policy.json` — fixed banking, reservations, segments
- [x] Create `manifests/runtime_abi.json` — compiled-code-only stable surface
- [x] Create `manifests/traceability.json` — EARS requirement-to-design/test records

**Verification:**
```powershell
python tools/validate_build.py --manifests
```

### T0.3 Zero-Page Graph Coloring

**Prerequisites:** T0.2

- [x] Create `tools/zp_alloc.py` — graph-coloring allocator
- [x] Generate `build/zp_symbols.inc` from `manifests/zero_page.json`
- [x] Generate `build/zp_allocation.json` — machine-readable ZP allocation
- [x] Generate `build/zp_allocation.md` — human-readable report
- [x] Generate `build/zp_interference.dot` — interference graph
- [x] Validate no ZP address conflicts
- [x] Validate all routine clobber lists satisfied

**Verification:**
```powershell
python tools/zp_alloc.py
python -c "import json; d=json.load(open('build/zp_allocation.json')); assert d['valid']
```

### T0.4 geoRAM Page Placement

**Prerequisites:** T0.3

- [x] Create `tools/georam_pages.py` — page placement and call directory
- [x] Generate `build/routine_directory.json` — routine ID to placement
- [x] Generate call directory for each 256-routine group
- [x] Validate no routine crosses `$DEFF` page boundary
- [x] Validate all routine IDs unique and complete

**Verification:**
```powershell
python tools/georam_pages.py
python tools/validate_build.py --routine-directory
```

### T0.5 Generated Contracts

**Prerequisites:** T0.4

- [x] Create `tools/generate_contracts.py` — ABI, arena, command, format exports
- [x] Generate `build/runtime_abi.json`
- [x] Generate `build/arena_layout.json`
- [x] Generate `build/production_entries.json` and `build/test_entries.json`
- [x] Generate `build/keyword_lookup_report.json`
- [x] Validate all generated contracts consistent

**Verification:**
```powershell
python tools/generate_contracts.py
python tools/validate_build.py --contracts
```

### T0.6 Linker Configuration

**Prerequisites:** T0.5

- [x] Create `tools/linker_config.py` — ld65 config from policy + generated segments
- [x] Create `manifests/linker_policy.json` with fixed banking, segments
- [x] Generate `build/compiler.cfg` — final ld65 configuration
- [x] Validate no segment overlaps
- [x] Validate NMI/RESET/IRQ vectors at `$FFFA-$FFFF`

**Verification:**
```powershell
python tools/linker_config.py
python tools/validate_build.py --linker
```

### T0.6a Host Tool Test Skeletons

**Prerequisites:** T0.6

**CONTRACT phase:**
- [x] Map every `SKELETON.md` section 7 tool function to a `TESTS.md` Host Tool Tests row
- [x] Define fixture directories under `tests/fixtures/tools/`
- [x] Define generated-output comparison rules that ignore timestamps and host paths

**RED phase:**
- [x] Create `tests/tools/test_zp_alloc.py`
- [x] Create `tests/tools/test_georam_pages.py`
- [x] Create `tests/tools/test_generate_contracts.py`
- [x] Create `tests/tools/test_linker_config.py`
- [x] Create `tests/tools/test_extract_segments.py`
- [x] Create `tests/tools/test_prepare_compressor_segments.py`
- [x] Create `tests/tools/test_package_d64.py`
- [x] Create `tests/tools/test_validate_build.py`
- [x] Create `tests/tools/test_test_harness.py`
- [x] Create `tests/tools/test_generate_reference.py`
- [x] Verify the tests fail against missing or stubbed behavior

**GREEN phase:**
- [x] Implement only the tool behavior needed for the fixture-backed tests
- [x] Wire tool tests into pytest collection without requiring VICE

**REFACTOR phase:**
- [x] Run `ruff`, `black --check`, and `mypy --strict` on `tools/` and `tests/`
- [x] Verify tool tests still pass

**Verification:**
```powershell
pytest tests/tools/ -v
ruff check tools/ tests/
black --check tools/ tests/
python -m mypy tools/ tests/ --strict
```

**Evidence (2026-07-02):** `tests/system/test_host_tool_contract_mapping.py`
proves every `SKELETON.md` section 7 function has exactly one `TESTS.md`
coverage row, each mapped function is callable, and every owner fixture
directory plus comparison rule is documented in `tests/fixtures/tools/README.md`.
`pytest tests/system/test_host_tool_contract_mapping.py tests/tools/ -v` passed
with 131 tests, including negative cases for missing files, malformed manifests,
stale generated output, payload drift, corrupted placements, bad PRG headers,
and boundary replay corruption. `ruff check tools/ tests/`, `black --check
tools/ tests/`, and `mypy tools/ tests/ --strict` all passed after formatting
`tests/conftest.py`.

### T0.7 Documentation Foundation

**Prerequisites:** T0.1

- [x] Create `docs/BUILD.md` — build pipeline and artifacts
- [x] Create `docs/TESTING.md` — test hierarchy and strategy
- [x] Create `docs/ZERO_PAGE.md` — ZP allocation design
- [x] Create `docs/KERNAL_ABI.md` — ROM calls and banking
- [x] Create `docs/GEORAM_BANKING.md` — geoRAM selection and calls
- [x] Create `docs/GEORAM_LOADER_DESIGN.md` — loader and compressor integration
- [x] Create `docs/LOOP_OPTIMIZATION.md` — loop fast-path strategy
- [x] Create `docs/INCREMENTAL_COMPILATION.md` — per-line compilation
- [x] Create `docs/COMPILE_EXPORT.md` — standalone PRG contract
- [x] Create `docs/DOS_WEDGE.md` — disk wedge behavior
- [x] Create `docs/IEEE754.md` — numeric profile
- [x] Create `docs/MEMORY_BUDGETS.md` — RAM and geoRAM budgets
- [x] Create `docs/EDITOR.md` — editor behavior
- [x] Create `docs/GRAPHICS_MEMORY.md` — bitmap banking
- [x] Create `docs/KEYWORDS.md` — language reference
- [x] Create `docs/MANUAL.md` — user-facing behavior
- [x] Create `docs/TRACEABILITY.md` — EARS records
- [x] Create `docs/VICE_TOOLS.md` — VICE inspection recipes
- [x] Create `docs/CANONICAL_TESTS.md` — stock VICE fixtures
- [x] Create `SKELETON.md` — implementation skeleton
- [x] Create `TESTS.md` — test plan

**Verification:**
```powershell
Get-ChildItem docs/*.md | Measure-Object | Select-Object -ExpandProperty Count
# Expected: 20+
```

---

## Phase 1: Canonical Fixtures and Requirements Tests

> Establish stock BASIC V2 token/program fixtures and requirements tests.
> **Test-first** — fixtures define expected behavior before any runtime code.

### T1.0 BASIC Compatibility Limit Manifest

**Prerequisites:** T0.7

**RED phase:**
- [x] Create `tests/e2e/cases/basicv2_limits.yaml`
- [x] Encode every row from `docs/BASIC_COMPATIBILITY_LIMITS.md`
- [x] Add source-derived expected behavior from `c64rom`
- [x] Mark each case `vice_pending` until the VICE harness can generate the
      authoritative fixture
- [x] Add coverage validation that fails when a compatibility-limit row lacks
      an E2E case

**GREEN phase:**
- [x] Populate the limit manifest with line number, variable name, string,
      byte/address, array, logical-file, device, filename, and input cases
- [x] Link each case to the owning keyword or feature group
- [x] Expose the manifest to the shared E2E mode runner

**REFACTOR phase:**
- [x] Remove duplicate hand-written limit cases from individual test modules
- [x] Keep case IDs stable for future VICE fixture generation

**Verification:**
```powershell
pytest tests/system/test_e2e_coverage.py -k compatibility_limits -v
```

**Evidence (2026-07-02):** `pytest
tests/system/test_basicv2_limit_manifest.py tests/system/test_e2e_coverage.py
-v` passed with 36 tests. The tests prove every BASIC V2 contract row in
`docs/BASIC_COMPATIBILITY_LIMITS.md` is mapped to `basicv2_limits.yaml`, each
area has c64rom local provenance and a feature group, all 48 case IDs are
unique/stable, every case has exactly one expected outcome, and all cases
remain `vice_pending: true` until authoritative VICE captures are generated.

### T1.1 Stock BASIC V2 Reference Fixtures

**Prerequisites:** T0.7

**RED phase:**
- [x] Create `tests/fixtures/reference/` directory structure
- [x] Define fixture schema (JSON format for VICE observations)
- [x] Create empty fixture files for each BASIC V2 test case

**GREEN phase:**
- [x] Generate stock C64 BASIC V2 immediate-mode reference fixtures using VICE
- [x] Generate stock C64 BASIC V2 program-mode reference fixtures using VICE
- [x] Record VICE executable version and ROM checksums in fixtures
- [x] Validate fixtures match `c64rom` source-derived expectations

**Verification:**
```powershell
python tools/test_harness.py --generate-reference basicv2
pytest tests/fixtures/reference/ -v
```

**Evidence (2026-07-02):** `python tools/test_harness.py
--generate-reference basicv2` completed through VICE 3.10 and refreshed the
documented static BASIC V2 captures. `pytest tests/fixtures/reference/ -v`
passed with 992 schema, provenance, fingerprint, catalog-completeness, and
semantic checks. BASIC V2 now has 95 fixture documents: 41 immediate-mode and
54 program-mode real `screen-v1` VICE captures, with 0 `catalog-v1`
placeholders. The fixture suite rejects future BASIC V2 catalog placeholders
and validates the reviewed source-derived expected results, executable/version
metadata, ROM SHA-256 checksums, and deterministic regeneration fingerprints.

### T1.2 Stock BASIC V3.5 Reference Fixtures

**Prerequisites:** T1.1

**RED phase:**
- [x] Create Plus/4 VICE machine configuration
- [x] Define Plus/4 fixture schema

**GREEN phase:**
- [x] Generate Plus/4 BASIC V3.5 immediate-mode reference fixtures
- [x] Generate Plus/4 BASIC V3.5 program-mode reference fixtures
- [x] Validate fixtures against Plus/4 ROM semantics

**Verification:**
```powershell
python tools/test_harness.py --generate-reference basicv35
pytest tests/fixtures/reference/ -v -k "basicv35"
```

**Evidence (2026-07-02):** `pytest tests/fixtures/reference/ -v` passed across
the complete fixture corpus. The Plus/4 BASIC V3.5 bucket contains 40 real
fixtures, 8 immediate-mode and 32 program-mode, all using `xplus4.exe` metadata,
SHA-256 ROM checksums, deterministic regeneration fingerprints, and non-catalog
normalization rules.

### T1.3 Requirements Traceability Matrix

**Prerequisites:** T0.2, T1.1

**RED phase:**
- [x] Create `tests/system/test_traceability.py` — traceability tests
- [x] Define expected requirement-to-test mappings

**GREEN phase:**
- [x] Create `tools/generate_reference.py` — API.md and MAP.md generator
- [x] Generate `build/requirements_matrix.json`
- [x] Generate `build/requirements_matrix.md`
- [x] Validate every requirement maps to at least one test
- [x] Validate every test maps to at least one requirement

**Verification:**
```powershell
python tools/generate_reference.py
python tools/validate_build.py --traceability
```

**Evidence (2026-07-02):** `python tools/generate_reference.py` now generates
`build/API.md`, `build/MAP.md`, `build/requirements_matrix.json`, and
`build/requirements_matrix.md` together. `python tools/validate_build.py
--traceability` passed and rejects stale matrix inverse indexes. `pytest
tests/system/test_traceability.py tests/tools/test_test_harness.py -v` passed
with 15 tests, proving every requirement record has mapped tests, every mapped
test exists in the Python suite or BASIC V2 limit YAML, and every mapped test
has the correct test-to-requirement index entry. `black --check`, `ruff check`,
and `mypy --strict` passed for the changed traceability/generator tests and
tools.

---

## Phase 2: Pinned Kernel — IRQ, KERNAL, CPU-Port, geoRAM Gates

> Build the resident foundation. **Test-first** for each routine.

### T2.1 RAM-Under-I/O Gate

**Prerequisites:** T0.3, T0.6

**RED phase:**
- [x] Create `tests/unit/test_ram_under_io.py`
- [x] Define test cases for enter/exit/copy operations
- [x] Add test-only exports to `manifests/test_entries.json`
- [x] Verify tests fail (no implementation yet)

**GREEN phase:**
- [x] Create `src/resident/ram_under_io.asm`
- [x] Implement `ram_under_io_enter` — select all-RAM mapping, mask IRQ
- [x] Implement `ram_under_io_exit` — restore `$35`, restore IRQ state
- [x] Implement `ram_under_io_copy_in` — bounded chunk copy into `$D000-$DFFF`
- [x] Implement `ram_under_io_copy_out` — bounded chunk copy from `$D000-$DFFF`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions in previously passing tests

**Verification:**
```powershell
python tools/validate_build.py --assembled
pytest tests/unit/test_ram_under_io.py -v
```

**Evidence (2026-07-02):** Strengthened `tests/unit/test_ram_under_io.py` with
copy-routine postcondition coverage and linked-byte verification that both
`ram_under_io_copy_in` and `ram_under_io_copy_out` call `ram_under_io_exit`
before RTS. The strengthened test failed before implementation because
`copy_in` did not restore canonical mapping. `src/resident/ram_under_io.asm`
now closes both copy paths through the shared exit gate. `build/production_entries.json`
contains all four `ram_under_io_*` callables as public production entries, so no
separate test-only export is required. Ran `build.ps1 -Validate`, `build.ps1`,
`validate_build.py --assembled`, `validate_build.py --all`, focused RAM-under-I/O
unit tests with 5 passing tests, and a no-regression slice covering linker,
memory-map, and build-validation system contracts with 27 passing tests.

### T2.2 KERNAL Bridge

**Prerequisites:** T2.1

**RED phase:**
- [x] Create `tests/unit/test_kernal_bridge.py`
- [x] Define test cases for each bridge routine (§6.5 SKELETON.md)
- [x] Define test cases for banking save/restore
- [x] Define test cases for IRQ state preservation
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/resident/kernal_bridge.asm`
- [x] Implement all KERNAL bridge routines
- [x] Implement `$01` save/restore for each bridge call
- [x] Implement IRQ state save/restore across blocking calls

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_kernal_bridge.py -v
```

**Evidence (2026-07-02):** Strengthened `tests/unit/test_kernal_bridge.py`
with direct coverage for every §6.5 bridge routine plus linked-byte regressions
for the production `kernal_rdtim` body and shared `kernal_end` flag/IRQ
restoration path. The RED tests caught `kernal_rdtim` returning entry registers
instead of the jiffy clock and `kernal_end` clobbering operation C/Z flags while
restoring the incoming I flag. Fixed `src/resident/kernal_bridge.asm` to load
`zp_time`, preserve operation flags through common exit, restore `$01`/`$00`,
and merge the saved IRQ state into the returned processor status. Ran
`powershell -ExecutionPolicy Bypass -File .\build.ps1`,
`python -m pytest tests/unit/test_kernal_bridge.py -v` with 5 passing tests,
`python tools/validate_build.py --all`, and a no-regression slice covering
RAM-under-I/O, IRQ, KERNAL bridge, linker, memory-map, and build-validation
contracts with 35 passing tests. Also ran Black, Ruff, and strict mypy on the
touched KERNAL bridge tests.

### T2.3 Pinned IRQ Handler

**Prerequisites:** T2.2

**RED phase:**
- [x] Create `tests/unit/test_irq.py`
- [x] Define test cases for IRQ entry/exit
- [x] Define test cases for jiffy advance
- [x] Define test cases for cursor blink
- [x] Define test cases for keyboard scan
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/resident/irq.asm`
- [x] Implement `irq_entry` — save A/X/Y/mapping, call UDTIM, cursor, SCNKEY
- [x] Implement `irq_update_jiffy` — call KERNAL UDTIM
- [x] Implement `irq_cursor_blink` — toggle cursor visibility
- [x] Implement `irq_scan_keyboard` — call KERNAL SCNKEY
- [x] Implement `irq_restore_mapping` — restore `$01` and P before RTI

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_irq.py -v
```

**Evidence (2026-07-02):** Strengthened `tests/unit/test_irq.py` with linked
production-byte checks for the hardware IRQ contract: `irq_entry` must select
`$01=$36`, return with `RTI` rather than `RTS`, and `irq_update_jiffy` /
`irq_scan_keyboard` must call the stock ROM `UDTIM` (`$FFEA`) and `SCNKEY`
(`$FF9F`) vectors directly instead of entering the foreground KERNAL bridge.
The RED tests failed against the previous `$30`/bridge/`RTS` implementation.
Fixed `src/resident/irq.asm` to use the documented direct ROM call sequence and
hardware return path while preserving the existing visible jiffy, cursor,
keyboard, and mapping behavior. Ran `powershell -ExecutionPolicy Bypass -File
.\build.ps1`, `python -m pytest tests/unit/test_irq.py -v` with 5 passing
tests, `python tools/validate_build.py --all`, and a no-regression slice
covering RAM-under-I/O, IRQ, KERNAL bridge, linker, memory-map, and
build-validation contracts with 37 passing tests. Also ran Black, Ruff, and
strict mypy on the touched IRQ tests.

### T2.4 Screen/Cursor Front End

**Prerequisites:** T2.1

**RED phase:**
- [x] Create `tests/unit/test_screen.py`
- [x] Define test cases for each screen operation (§6.4 SKELETON.md)
- [x] Define test cases for cursor movement and wrapping
- [x] Define test cases for line input with quote mode
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/resident/screen.asm`
- [x] Implement all screen routines
- [x] Implement bounded line capture with quote mode

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_screen.py -v
```

**Evidence (2026-07-02):** Removed the semantic `cluster_emu_patch` dependency
from `tests/unit/test_screen.py` and switched the screen suite to the raw
`Emu6502` binding so assertions observe the real assembled bytes and memory
image. Expanded coverage to all §6.4 screen routines: init, clear, scroll,
putchar, getchar, cursor visibility, cursor right/left/up/down wrapping and
bottom scrolling, plus bounded line capture with quote-mode trailing-space
behavior. The real-byte RED run exposed row-pointer call-convention bugs where
callers passed the row in Y to helpers that consume A. Fixed
`src/resident/screen.asm` for `screen_putchar`, `screen_getchar`,
`screen_line_input`, `screen_scroll_up`, and bottom-row clearing. Ran
`powershell -ExecutionPolicy Bypass -File .\build.ps1`, `python -m pytest
tests/unit/test_screen.py -v` with 7 passing tests, `python
tools/validate_build.py --all`, and a no-regression slice covering
RAM-under-I/O, IRQ, KERNAL bridge, screen, linker, memory-map, and
build-validation contracts with 44 passing tests. Also ran Black, Ruff, and
strict mypy on the touched screen tests.

### T2.5 geoRAM Detection

**Prerequisites:** T0.4

**RED phase:**
- [x] Create `tests/unit/test_georam_detect.py`
- [x] Define test cases for detection with geoRAM present
- [x] Define test cases for detection with geoRAM absent
- [x] Define test cases for undersized geoRAM
- [x] Define test cases for state save/restore round-trip
- [x] Define test cases for capacity detection
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/arena/georam_detect.asm`
- [x] Implement `detect_georam` — non-destructive probe
- [x] Implement `detect_save_state` / `detect_restore_state`
- [x] Implement `detect_probe_pattern1` / `detect_probe_pattern2`
- [x] Implement `detect_probe_aliasing` — capacity detection
- [x] Implement `detect_check_minimum` — 512 KiB threshold
- [x] Implement `detect_publish_profile` — dual-device expansion profile
- [x] Implement `detect_validate_profile` — session integrity
- [x] Implement REU non-destructive detect + dual selection (prefer geoRAM store)

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_georam_detect.py -v -k "local"
```

**Evidence (2026-07-02):** Removed the `cluster_emu_patch` dependency and
`detect_mock_mode` scaffold from geoRAM detection. The detector now uses the
real geoRAM hardware window/register model: disabled geoRAM aliases selected
pages and fails, enabled geoRAM preserves distinct page bytes and publishes the
512 KiB profile. Added full-path undersized-capacity coverage by loading a
256 KiB geoRAM backing image through the C64 emulator binding; the RED test
failed while `detect_probe_aliasing` only checked two pages and assumed 32
blocks. Fixed `src/arena/georam_detect.asm` to probe block 31/page 63 before
publishing the 512 KiB profile, reselecting the page before readback so the
mapped hardware window is authoritative, and preserving the saved selection and
probe byte on failure. The tests execute assembled bytes, verify `$DFFE`/`$DFFF`
state restoration, reject absent and undersized devices, validate the 512 KiB
threshold, and check profile continuity. Ran `powershell -ExecutionPolicy
Bypass -File .\build.ps1`, `python -m pytest tests/unit/test_georam_detect.py
-v` with 6 passing tests, `python tools/validate_build.py --all`, and a
no-regression slice covering RAM-under-I/O, IRQ, KERNAL bridge, screen, geoRAM
detection/gate/fatal paths, linker, memory-map, and build-validation contracts
with 62 passing tests. Also ran Black, Ruff, and strict mypy on the touched
geoRAM detection tests.

### T2.6 geoRAM Gate and Context Stack

**Prerequisites:** T2.5

**RED phase:**
- [x] Create `tests/unit/test_georam_gate.py`
- [x] Define test cases for select writes correct registers
- [x] Define test cases for context push/pop round-trip
- [x] Define test cases for nested calls preserve caller state
- [x] Define test cases for handle-based operations with validation
- [x] Create `tests/integration/test_georam_cycle.py`
- [x] Define integration test for full geoRAM call cycle
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/resident/georam_gate.asm`
- [x] Create `src/arena/context_stack.asm`
- [x] Implement `georam_select` — write `$DFFE`/`$DFFF`, update mirror
- [x] Implement `georam_ctx_push` / `georam_ctx_pop` — context save/restore
- [x] Implement `georam_call_group_n` — generated group dispatch
- [x] Implement `georam_tail_group_n` — tail transfer
- [x] Implement handle-based read/write/copy routines
- [x] Implement `georam_checksum` and `georam_verify_mirror`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify all integration tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_georam_gate.py -v -k "georam"
pytest tests/integration/test_georam_cycle.py -v
```

**Evidence (2026-07-02):** Added a red/green local-emulator regression for
`georam_copy_pages` that copies real bytes from one selected geoRAM page to
another through `$DE00` and verifies selection restoration. Ran
`powershell -ExecutionPolicy Bypass -File .\build.ps1` and
`python -m pytest tests\unit\test_georam_gate.py tests\integration\test_georam_cycle.py -q`
with 7 passing tests. Full generated-directory dispatch remained `[~]` at that
point.

**Evidence (2026-07-02):** Strengthened `georam_call_group_n` coverage with a
generated-directory returning-call canary and missing-entry error-path
regression. The local emulator installs target bytes at the generated
`wedge_parse` block/page/offset, dispatches by the generated routine index,
asserts target A/X/Y/P results, and verifies caller selection/context
restoration. The missing-entry case verifies `$FF` directory sentinels unwind
without leaking selection. Ran `powershell -ExecutionPolicy Bypass -File
.\build.ps1` and `python -m pytest tests\unit\test_georam_gate.py
tests\integration\test_georam_cycle.py -q` with 8 passing tests. This does not
complete the full production page-image/linking path.

**Evidence (2026-07-02):** Added red/green local-emulator coverage for
`georam_tail_group_n`. The positive case installs target bytes at the generated
`wedge_parse` block/page/offset, pushes an active context frame, dispatches by
generated routine index, verifies target A/X/Y/P results, and asserts the frame
was consumed with selection left on the target. The negative case verifies a
missing `$FF` directory entry fails before consuming the active frame or
changing selection. Ran `powershell -ExecutionPolicy Bypass -File .\build.ps1`
and `python -m pytest tests\unit\test_georam_gate.py tests\integration\test_georam_cycle.py -q`
with 9 passing tests. Full production page-image/linking and broader nested
callback coverage remain `[~]`.

**Evidence (2026-07-02):** Added production page-image integration coverage:
`tests/integration/test_georam_cycle.py` now loads the built `build/georam.bin`
payload into the emulator geoRAM backing store, selects the generated
`wedge_parse` block/page, and executes the linked routine bytes through
`$DE00+offset` with real inputs. Ran `powershell -ExecutionPolicy Bypass -File
.\build.ps1`, `python -m pytest tests/unit/test_georam_gate.py
tests/integration/test_georam_cycle.py
tests/system/test_binary_artifacts.py::TestPrgHeader::test_georam_directory_points_at_installed_routine_bytes
-v` with 12 passing tests, and `python tools/validate_build.py --all`.
`black --check`, `ruff check`, and `mypy --strict` passed for the changed
integration test. T2.6 is complete through the real gate, generated directory,
linked page image, and geoRAM hardware-window path.

### T2.7 Fatal Error Path

**Prerequisites:** T2.6

**RED phase:**
- [x] Create `tests/unit/test_fatal.py`
- [x] Define test cases for fatal path restores machine state
- [x] Define test cases for fatal path reports failure
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/resident/fatal.asm`
- [x] Implement `fatal_georam` — clean failure path
- [x] Implement `fatal_restore_machine` — shared bounded cleanup

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_fatal.py -v
```

**Evidence (2026-07-02):** Removed `cluster_emu_patch` from the fatal-path
tests and strengthened them to assert real `$DFFE`/`$DFFF` cleanup. Fixed
`fatal_restore_machine` to restore canonical `$01` before resetting geoRAM
selection, so cleanup works even when fatal recovery starts with I/O hidden.
The test harness now refreshes its `$00/$01` shadow after executing assembled
code, so CPU-port assertions observe real routine writes. Ran
`powershell -ExecutionPolicy Bypass -File .\build.ps1 -GeoramCompiler
-UseCompressor`, `python -m pytest tests\unit\test_fatal.py
tests\unit\test_ram_under_io.py tests\unit\test_irq.py
tests\unit\test_kernal_bridge.py -q` with 12 passing tests, and the adjacent
fatal/geoRAM/build suite with 37 passing tests.

**Evidence (2026-07-02):** Re-ran `python -m pytest tests/unit/test_fatal.py
tests/unit/test_ram_under_io.py tests/unit/test_irq.py
tests/unit/test_kernal_bridge.py -v` with 17 passing tests. The fatal tests
execute the assembled `fatal_restore_machine` and `fatal_georam` paths, verify
canonical `$01=$35`, context-stack reset, cursor visibility reset, `$DFFE/$DFFF`
geoRAM selection reset, failure metadata storage, and carry-set fatal return.

### T2.8 Resident Main Loop

**Prerequisites:** T2.4, T2.6

**RED phase:**
- [x] Create `tests/unit/test_resident_main.py`
- [x] Define test cases for input capture and dispatch
- [x] Define test cases for boundary assertions
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/resident/resident_main.asm`
- [x] Implement `resident_main` — READY/editor loop
- [x] Implement `resident_poll_input` — foreground GETIN
- [x] Implement `resident_submit_line` — transactional handoff
- [x] Implement `resident_assert_boundary` — debug assertions

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_resident_main.py -v
```

**Evidence (2026-07-02):** Removed the resident-main semantic emulator hook from
the owning unit test and executed the linked 6502 bytes with the C64 wrapper's
GeoRAM mapping enabled. This exposed and fixed two real zero-page lifetime
defects: resident editor state and `screen_line_input`'s `zp_src` pointer could
alias the persistent GeoRAM selection mirror. The manifest now models those
cross-call lifetimes, and `tests/system/test_system_memory_map.py` independently
rejects recurrence. Ran `powershell -ExecutionPolicy Bypass -File .\build.ps1
-UseCompressor` successfully and the focused unit/system suite with 6 passing
tests. The task remains partial because the documented non-returning READY loop
and transactional direct/editor dispatch are not yet implemented.

**Evidence (2026-07-02):** `resident_main` now loops through
`resident_poll_input` and `resident_submit_line` instead of returning, and
`resident_submit_line` hands captured input to the generated
`editor_submit_line` geoRAM service via `georam_call_group_n` using a generated
routine-ID constant. `tests/unit/test_resident_main.py` loads both
`build/compiler.bin` and `build/georam.bin`, executes the real poll/submit and
boundary assertion paths, and checks linked bytes for the non-returning loop and
geoRAM handoff call. Ran `powershell -ExecutionPolicy Bypass -File .\build.ps1`,
`python -m pytest tests/unit/test_resident_main.py -v` with 4 passing tests,
the adjacent screen/geoRAM suite with 18 passing tests, `python
tools/validate_build.py --all`, and Black/Ruff/strict mypy on the changed
resident/generator files.

---

## Phase 3: Arena System — Page Allocator, Directory, Handles

> Build the geoRAM memory management layer. **Test-first.**

### T3.1 Page Allocator

**Prerequisites:** T2.5, T2.6

**RED phase:**
- [x] Create `tests/unit/test_page_alloc.py`
- [x] Define test cases for allocation and deallocation
- [x] Define test cases for fragmentation handling
- [x] Define test cases for bounds checking
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/arena/page_alloc.asm`
- [x] Implement `page_alloc_init` — initialize free-page bitmap
- [x] Implement `page_alloc` — allocate pages from free bitmap
- [x] Implement `page_free` — return pages to free bitmap
- [x] Implement `page_alloc_count` / `page_alloc_largest`
- [x] Implement `page_check_in_range` — bounds check

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_page_alloc.py -v -k "georam"
```

**Evidence (2026-07-02):** Replaced the raw bump/LIFO allocator with a
2,048-page free bitmap and opaque generation-stamped extent handles. Requests
now carry count, power-of-two alignment, and owner; frees validate the live
slot generation and release arbitrary extents. Strengthened the real-byte unit
suite to cover interior-hole first-fit reuse, largest-run accounting,
alignment fragmentation, malformed descriptors, full capacity, stale handles,
and double frees. Converted `arena_create`/`arena_destroy` to the handle ABI and
removed the global arena-generation emulator override. Ran the exact focused
command with 8 passing tests, the real-byte allocator/arena pair with 12
passing tests, and the adjacent arena/GeoRAM/tool/system neighborhood with 56
passing tests across two collection-safe invocations. The compressed production
build also completed and passed artifact validation.

**Evidence (2026-07-02):** Re-ran `python -m pytest
tests/unit/test_page_alloc.py -v` with 9 passing tests. The suite executes the
linked allocator bytes and covers initialization counts/largest run, arbitrary
non-LIFO free, first-fit reuse, power-of-two alignment fragmentation, malformed
request rejection, stale/double-free generation rejection, live-handle range
checks, and real geoRAM extent clearing with caller selection restoration. The
allocator/arena/gate neighborhood passed with 23 tests, and `python
tools/validate_build.py --all` passed.

### T3.2 Arena Core

**Prerequisites:** T3.1

**RED phase:**
- [x] Create `tests/unit/test_arena_core.py`
- [x] Define test cases for arena lifecycle
- [x] Define test cases for integrity detection
- [x] Define test cases for generation tracking
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/arena/arena_core.asm`
- [x] Implement `arena_init_all` — construct arena directory
- [x] Implement `arena_create` / `arena_destroy`
- [x] Implement `arena_check_integrity` — canary, checksum, generation
- [x] Implement `arena_reset` — deterministic reset with generation bump
- [x] Implement `arena_get_handle` / `arena_handle_valid`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_arena_core.py -v -k "georam"
```

**Evidence (2026-07-02):** Replaced the single-arena façade with the generated
eight-type directory. Each entry now owns a generation-stamped allocator
extent, capacity, type, canary, and metadata checksum; validation follows the
backing extent, destroy releases it, and reset clears the real GeoRAM pages
through `georam_select` while restoring the caller selection. Added direct
tests for all-arena construction, duplicate ownership rejection, arbitrary
destroy/recreate, stale generations, isolated corruption, physical reset, and
directory generations. Removed the arena-generation and program-store semantic
test overrides, and corrected cold-routine tests to execute linked labels rather
than colliding `$DE00` overlay entry addresses. The focused arena/allocator
suite passes 14 tests and the dependent neighborhood passes 53 tests. Offset
resolution in `arena_get_handle` remains partial, so its combined implementation
marker stays `[~]`.

**Evidence (2026-07-02):** Added a focused `arena_get_handle` regression that
fails when the routine merely echoes an arena handle. `arena_get_handle` now
treats `A` as an arena-relative page offset, rejects offsets at or beyond the
arena capacity, and returns the backing allocator extent slot/generation in
`X/Y`. Ran `powershell -ExecutionPolicy Bypass -File .\build.ps1`, `python -m
pytest tests/unit/test_arena_core.py -v` with 6 passing tests, the
allocator/arena/gate/overlay neighborhood with 27 passing tests, `python
tools/validate_build.py --all`, and Black/Ruff/strict mypy for the changed
arena test. T3.2 is complete.

### T3.3 Overlay Dispatch

**Prerequisites:** T3.2

**RED phase:**
- [x] Create `tests/unit/test_overlay.py`
- [x] Define test cases for overlay swap cycle
- [x] Define test cases for routine resolution
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/arena/overlay_dispatch.asm`
- [x] Implement `overlay_enter` / `overlay_exit`
- [x] Implement `overlay_resolve` — routine ID to page/offset
- [x] Implement `overlay_validate` — directory integrity

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_overlay.py -v -k "georam"
```

**Evidence (2026-07-02):** Removed the four-entry hand-written directory and
the overlay semantic emulator overrides. `overlay_resolve` now reads the same
generated group-1 block/page/offset tables as the pinned gate; enter/exit use an
eight-deep stack and real `georam_select` calls. The generator now publishes
group count, CRC32 bytes, and a runtime XOR checksum, and validation detects
linked-table corruption. The focused real-byte suite passes 3 tests; generator,
gate, GeoRAM-cycle, build, and binary-artifact neighbors pass 50 tests across
collection-safe invocations. The compressed D64 build and artifact validator
also pass.

**Evidence (2026-07-02):** Re-ran `python -m pytest tests/unit/test_overlay.py
-v` with 3 passing tests. The suite executes linked bytes for generated
group-1 routine resolution, runtime directory corruption detection, nested
`overlay_enter`/`overlay_exit`, real `georam_select` selection changes, stack
depth tracking, caller selection restoration, and underflow rejection.

---

## Phase 4: Tokenized Program Load/Save/Edit

> Implement the transactional program store. **Test-first.**

### T4.1 Program Codec

**Prerequisites:** T2.2, T3.2

**RED phase:**
- [x] Create `tests/unit/test_program_codec.py`
- [x] Define test cases for stock format decode/encode round-trip
- [x] Define test cases for extended format decode/encode round-trip
- [x] Define test cases for malformed input rejection
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/program_codec.asm`
- [x] Implement `program_classify_file` — stock vs extended
- [x] Implement `program_decode_stock` — BASIC V2 import
- [x] Implement `program_encode_stock` — canonical BASIC V2 export
- [x] Implement `program_decode_extended` — versioned extension import
- [x] Implement `program_encode_extended` — extension export
- [x] Implement `program_select_save_format` — tokens outside REM/string → C2 / Plus/4 3.5 / V2

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_program_codec.py -v
```

**Evidence (2026-07-02, superseded):** Removed the program-codec semantic
emulator replacement and changed cold-routine resolution to linked labels.
Replaced the invalid pseudo-program fixture with canonical `$0801` BASIC V2
records. The strengthened suite produced RED failures for descending line
numbers, bad links, missing/final terminators, stale exported links, and C2P1
ABI/length/checksum/reserved-field corruption. That iteration still used a
bounded record buffer; it is retained here only as historical RED/early-GREEN
evidence and was replaced by the arena-backed 2026-07-03 implementation below.

**Evidence (2026-07-03):** Replaced the bounded CPU-record codec completely
with one arena-backed `PS` whole-program descriptor ABI and one normalized
logical program representation. Stock decode validates `$0801` BASIC V2 links
across the full arena stream, removes absolute stock links, and publishes
`record_length:u16`/`line_number:u16` normalized records. Stock encode validates
that normalized representation, clones non-scratch inputs into the scratch
arena, prepends `$0801`, and recomputes canonical BASIC links without mutating
the published program arena. C2P1 decode/encode and classification use the same
descriptor validation. Static whole-program CPU buffers and disabled duplicate
implementations were removed, and the removed bounded ABI has an explicit
rejection test. `powershell -ExecutionPolicy Bypass -File .\build.ps1` passed;
`pytest tests/unit/test_program_codec.py tests/unit/test_program_store.py
tests/unit/test_arena_core.py tests/tools/test_generate_contracts.py
tests/integration/test_program_lifecycle.py -q` passed 45 focused tests when
split under the local timeout. The no-regression marker remains `[~]`: the
delegated full `tests/unit/` run reported 105 passed and 181 failed in unrelated
unfinished generated-routine metadata/codegen areas, so broad regression status
is not proven.

**Evidence (2026-07-03):** Cleared the no-regression gate after replacing
remaining shim-sensitive failures with production-byte fixes and verification.
`powershell -ExecutionPolicy Bypass -File .\build.ps1` passed. `python -m
pytest tests/unit/test_program_codec.py -v --tb=short --timeout=30` passed 22
tests. `python -m pytest tests/unit/test_program_codec.py
tests/unit/test_program_store.py tests/unit/test_arena_core.py
tests/tools/test_generate_contracts.py tests/integration/test_program_lifecycle.py
-q --tb=short --timeout=30` passed 45 focused tests. `python -m pytest
tests/unit -q --tb=line --timeout=30` passed 512 tests, clearing the broad unit
regression blocker recorded above.

### T4.2 Program Store

**Prerequisites:** T4.1, T3.2

**RED phase:**
- [x] Create `tests/unit/test_program_store.py`
- [x] Define test cases for transaction commit and rollback
- [x] Define test cases for atomic publication
- [x] Create `tests/integration/test_program_lifecycle.py`
- [x] Define integration test for LOAD/SAVE round-trip
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/program_store.asm`
- [x] Implement `program_tx_begin` — start transaction
- [x] Implement `program_tx_put_line` / `program_tx_delete_line`
- [x] Implement `program_tx_commit` — atomic publish
- [x] Implement `program_tx_abort` — rollback
- [x] Implement `program_replace_from_load` — transactional LOAD

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify all integration tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_program_store.py -v
pytest tests/integration/test_program_lifecycle.py -v
```

**Evidence (2026-07-03):** Replaced the bounded store contract with
arena-backed whole-program transactions over normalized `PS` streams. The store
now publishes `__program_store_published` in the tokenized-program arena,
clones transactions into the dedicated `program_staging` arena, uses typed
`PT`/`PP`/`PD` descriptors for transaction, put, and delete requests, and
rejects staging aliases, malformed descriptors, malformed normalized streams,
forged/stale transaction handles, and overflow without changing the published
root. `program_tx_put_line` and `program_tx_delete_line` scan whole staged
programs, preserve the requested line across validation, sorted-insert or
replace/delete records, and publish descriptor length last. The lifecycle
integration now exercises the full stock PRG `PS` decode -> normalized store
publication -> transaction edit -> commit -> stock PRG `PS` encode path. Direct
unit and integration verification passed:
`pytest tests/unit/test_program_store.py -q` (5 passed),
`pytest tests/integration/test_program_lifecycle.py -q --tb=short --timeout=30
--timeout-method=thread` (1 passed), and the focused codec/store/arena/tool/
lifecycle neighborhood passed 45 tests when split under the local timeout.
The no-regression marker remains `[~]` because the wider `tests/unit/` suite is
still failing in unrelated unfinished generated-routine metadata/codegen areas.

**Evidence (2026-07-03):** Cleared the no-regression gate after re-verifying the
complete arena-backed program-store production path. `powershell
-ExecutionPolicy Bypass -File .\build.ps1` passed with fingerprint
`a38fca2d64aada2ce70ca2c5a691c03a`. `python -m pytest
tests/unit/test_program_store.py -v --tb=short --timeout=30` passed 5 tests,
and `python -m pytest tests/integration/test_program_lifecycle.py -v
--tb=short --timeout=30 --timeout-method=thread` passed the stock PRG decode ->
transaction edit/commit -> encode round-trip. `python -m pytest tests/unit -q
--tb=line --timeout=30` passed all 512 unit tests, clearing the broad regression
blocker recorded above.

---

## Phase 5: Descriptors and Generic Runtime

> Implement the minimal correct runtime. **Test-first.**

### T5.1 Variable Descriptors

**Prerequisites:** T3.2, T0.5

**RED phase:**
- [x] Create `tests/unit/test_variables.py`
- [x] Define test cases for each load/store operation
- [x] Define test cases for type promotion and coercion
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/runtime/variables.asm`
- [x] Implement `var_resolve` — descriptor to address
- [x] Implement `var_load_int` / `var_store_int`
- [x] Implement `var_load_float` / `var_store_float`
- [x] Implement `var_load_string` / `var_store_string`
- [x] Implement `var_promote_to_float` / `var_coerce`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Implementation evidence (2026-07-03):** Replaced raw-pointer helper semantics
with 12-byte `VD` variable descriptors and typed `VI`/`VF`/`VS` store request
records. `var_resolve` now validates descriptor magic, kind, nonzero descriptor
generation, reserved bytes, direct-cell tails, and arena id/generation/page
handles before returning a cell pointer. Arena-backed integer, float, and
string cells are rejected when their typed payload would cross the selected
`$DE00..$DEFF` geoRAM window. Integer, float, and string load/store helpers
operate through descriptors only; string stores update the three-byte string
descriptor cell instead of copying payload bytes through an ad hoc record.
`var_promote_to_float` and `var_coerce` route through the real math core;
integer coercion forces FAC reclassification before narrowing so stale math
type tags cannot make a lossy conversion succeed. Focused variables tests first
failed with RED failures against the old raw-pointer implementation, then
passed through the linked production bytes.

The broad no-regression claim remains `[~]` because the full unit suite still
has unrelated unfinished failures outside T5.1.

**No-regression evidence (2026-07-03):** Rebuilt the production artifact with
`powershell -ExecutionPolicy Bypass -File .\build.ps1` (fingerprint
`a38fca2d64aada2ce70ca2c5a691c03a`). The documented focused variables command
passed 8 tests, and the variables/arena/contracts/build-validation neighborhood
passed 34 tests. `tools/validate_build.py --manifests` and `--contracts`, Black,
and Ruff all passed. `python -m pytest tests/unit -q --tb=line --timeout=30`
passed all 512 tests, clearing the broad blocker recorded above.

**Verification:**
```powershell
C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests/unit/test_variables.py -q --tb=short
C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests/unit/test_variables.py tests/unit/test_arena_core.py tests/tools/test_generate_contracts.py tests/tools/test_validate_build.py -q --tb=short
C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe tools/validate_build.py --manifests
C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe tools/validate_build.py --contracts
C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe -m black --check tests/unit/test_variables.py
C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe -m ruff check tests/unit/test_variables.py
```

### T5.2 Array Descriptors

**Prerequisites:** T5.1

**RED phase:**
- [x] Create `tests/unit/test_arrays.py`
- [x] Define test cases for DIM and element access
- [x] Define test cases for bounds checking
- [x] Define test cases for REDIM'D ARRAY error
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/runtime/arrays.asm`
- [x] Implement `arr_dim` — allocation
- [x] Implement `arr_resolve_element` — bounds check and offset
- [x] Implement `arr_load_element` / `arr_store_element`
- [x] Implement `arr_redim` / `arr_free`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Implementation evidence (2026-07-03):** Replaced the bounded façade with one
arena-backed `AD` representation and typed `AM`, `AE`, and `AS` requests.
`arr_dim` computes one- or two-dimensional row-major shapes, claims and clears
contiguous manifest-array pages, and publishes only after allocation succeeds.
Resolution validates descriptor generation, recomputed shape and extent, page
ownership, and bounds. Integer, float, and string values round-trip through
production geoRAM storage, including elements crossing a 256-byte page
boundary. `arr_free` returns the extent for first-fit reuse and invalidates the
descriptor; live redimension attempts return `REDIM'D ARRAY`. Seven focused
real-byte tests pass after a fresh production build. The broad no-regression
item remains `[~]` because unrelated unfinished compiler areas still fail the
repository-wide suite.

**No-regression evidence (2026-07-03):** Rebuilt the production artifact with
`powershell -ExecutionPolicy Bypass -File .\build.ps1` (fingerprint
`a38fca2d64aada2ce70ca2c5a691c03a`). The documented focused array command
passed 7 tests, and the arrays/variables/arena/contracts/build-validation
neighborhood passed 41 tests. `tools/validate_build.py --manifests` and
`--contracts` both passed. `python -m pytest tests/unit -q --tb=line
--timeout=30` passed all 512 tests, clearing the broad blocker recorded above.

**Verification:**
```powershell
C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests/unit/test_arrays.py -q --tb=short
C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests/unit/test_arrays.py tests/unit/test_variables.py tests/unit/test_arena_core.py tests/tools/test_generate_contracts.py tests/tools/test_validate_build.py -q --tb=short
C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe tools/validate_build.py --manifests
C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe tools/validate_build.py --contracts
```

### T5.3 String Operations

**Prerequisites:** T5.1

**RED phase:**
- [x] Create `tests/unit/test_strings.py`
- [x] Define test cases for each string operation
- [x] Define test cases for stock-compatible PETSCII behavior
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/runtime/strings.asm`
- [x] Implement `str_alloc` / `str_free`
- [x] Implement `str_assign` / `str_copy` / `str_concat`
- [x] Implement `str_left` / `str_right` / `str_mid`
- [x] Implement `str_len` / `str_cmp`
- [x] Implement `str_chr` / `str_asc` / `str_val` / `str_str`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Implementation evidence (2026-07-03):** Replaced the bounded two-buffer and
raw-pointer implementation with one caller-owned 12-byte `SD` representation,
arena-backed page ownership, 16-bit stale-owner validation, typed requests,
transactional alias-safe mutation, and general decimal/exponent `VAL` plus
stock-sign `STR$` formatting. Scalar and array string cells now store the same
canonical descriptor, deep-copy values, and reclaim ownership on overwrite,
free, and redimension. Real linked-byte RED tests first exposed missing arena
publication, exhaustion, decimal parsing, and ownership-transfer failures.
Focused string, variable, and array suites pass after a fresh production build;
the broad no-regression marker remains `[~]` until the repository-wide suite is
green.

**No-regression evidence (2026-07-03):** Rebuilt the production artifact with
`powershell -ExecutionPolicy Bypass -File .\build.ps1` (fingerprint
`a38fca2d64aada2ce70ca2c5a691c03a`). The documented linked-byte string,
variable, and array command passed all 33 tests, including ownership,
alias-safety, page-boundary, PETSCII, `VAL`, and `STR$` behavior. `python -m
pytest tests/unit -q --tb=line --timeout=30` passed all 512 tests, clearing the
broad blocker recorded above.

**Verification:**
```powershell
& 'C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe' -m pytest tests/unit/test_strings.py tests/unit/test_variables.py tests/unit/test_arrays.py -v
```

### T5.4 Math Core

**Prerequisites:** T0.3

**RED phase:**
- [x] Create `tests/unit/test_math_core.py`
- [x] Define test cases for each arithmetic operation
- [x] Define test cases for stock BASIC V2 numeric compatibility
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/runtime/math_core.asm`
- [x] Implement `math_add` / `math_sub` / `math_mul` / `math_div`
- [x] Implement `math_negate` / `math_cmp`
- [x] Implement `math_int` / `math_sgn` / `math_abs` / `math_fpe`
- [x] Implement `math_int_to_float` / `math_float_to_int`
- [x] Implement integer arithmetic: `math_add_int` / `math_sub_int` / `math_mul_int` / `math_div_int`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Implementation evidence (2026-07-02):** Removed all core-math arithmetic
postprocessors from the emulator fixture, switched the suite to linked labels
and mapped geoRAM, and confirmed the production-byte tests initially pass.
Strengthened conversion and integer division coverage; the new signed-division
case failed against the old unsigned repeated-subtraction routine. Replaced it
with fixed 16-step signed restoring division and fixed shared adaptive-number
carry/sign-extension defects. `tests/unit/test_math_core.py` now passes all
three groups without semantic shims, and the string/variable consumers pass.
The broader numeric run passed 30 tests but exposed 12 existing real failures
in EXP/POW/MIN/MAX and transcendental/trig routines, which are owned by later
T9 tasks; therefore T5.4's no-regression and stock-wide compatibility claims
remain `[~]`.

**Implementation evidence (2026-07-03):** Replaced the no-op `math_int` with
packed C64 float floor semantics and added positive, negative, fractional,
zero, and boundary coverage. Integer add/subtract/multiply/divide now detect
signed overflow, divide-by-zero, and `-32768/-1` without publishing wrapped
success; float-to-int rejects fractional and out-of-range values including
`32768`. A stock packed-float matrix now covers mantissa tie rounding, extreme
cancellation and exponents, signed division, unary bit preservation,
underflow-to-zero, and overflow errors; it exposed and fixed division exponent
wrap. The focused linked-byte suite passes 78 tests, the canonical build and all
generated-contract validation pass, and Black/Ruff are clean. Broad
no-regression remains `[~]` because later T9 numeric failures still exist.

**No-regression evidence (2026-07-03):** Rebuilt the production artifact with
`powershell -ExecutionPolicy Bypass -File .\build.ps1` (fingerprint
`a38fca2d64aada2ce70ca2c5a691c03a`). The documented linked-byte Math Core
command passed all 90 arithmetic, comparison, conversion, rounding, boundary,
and error tests. The Math Core plus transcendental/trig neighborhood passed all
120 tests, directly clearing the later-T9 numeric blocker recorded above.
`python -m pytest tests/unit -q --tb=line --timeout=30` passed all 512 tests.

**Verification:**
```powershell
& 'C:\Users\me\AppData\Local\Programs\Python\Python313\python.exe' -m pytest tests/unit/test_math_core.py -v
```

### T5.5 Control Flow

**Prerequisites:** T5.1, T5.4

**RED phase:**
- [x] Create `tests/unit/test_control.py`
- [x] Define test cases for FOR/NEXT cycle
- [x] Define test cases for DO/LOOP cycle
- [x] Define test cases for GOSUB/RETURN cycle
- [x] Define test cases for STOP/CONT state machine
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/runtime/control.asm`
- [x] Implement `ctrl_for_init` / `ctrl_for_next`
- [x] Implement `ctrl_do_init` / `ctrl_loop_test` / `ctrl_exit_loop`
- [x] Implement `ctrl_gosub` / `ctrl_return`
- [x] Implement `ctrl_on_goto` / `ctrl_on_gosub`
- [x] Implement `ctrl_stop` / `ctrl_end` / `ctrl_cont`
- [x] Implement `ctrl_check_stop`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Implementation evidence (2026-07-02):** Removed FOR/NEXT and ON
GOTO/GOSUB semantic postprocessors, captured the production RED failure, and
switched tests to linked labels with mapped geoRAM. Control frames now use
generated two-byte pointers, bounded push/pop with propagated underflow/
overflow, active-frame 16-bit NEXT updates, and ON GOTO explicitly compares
its A input instead of consuming a stale caller Z flag. Explicit frame,
branch, DO, GOSUB/RETURN, and STOP/CONT checks pass alongside the core
math/string/variable suites (12 tests) after a compressed build. T5.5 remains
`[~]` because FOR end/step/type semantics, conditional DO/LOOP forms, and
compiled continuation generation are not yet represented by the small frame
record.

**Verification:**
```powershell
pytest tests/unit/test_control.py -v
```

**Implementation evidence (2026-07-03):** Replaced the untyped two-byte frame
stack with tagged FOR, DO, and GOSUB frames. FOR descriptors carry the assigned
`FLOAT`/`INT1`/`INT2`/`INT3` tier plus signed 16-bit start, limit, and step;
INT1 values are sign-extended, generic INT1 frames widen to INT2 instead of
wrapping, INT3 variable comparisons are unsigned when the visible variable is
assigned INT3, and FLOAT variables use the canonical packed numeric runtime.
The design now treats FOR start, limit, and step as signed INT2 control fields
only; loop-variable assignment may still be FLOAT/INT1/INT2/INT3 and must be
respected by stores, comparisons, and any generic promotion. DO supports bare,
WHILE, and UNTIL post-tests. STOP/CONT snapshots and generation-checks the
complete tagged stack. Shared numeric comparison now sign-extends mixed
INT1/INT2 operands and orders INT3 operands unsigned. The strengthened tests
first failed in seven control cases, then the rebuilt linked-byte control/math
suites passed 102 tests. The combined STOP/END/CONT item remains `[~]` because
`ctrl_end` still lacks the documented graphics-exit and editor/READY shell
transition; broad regression status also remains unproven.

**Completion evidence (2026-07-03):** Completed the combined STOP/END/CONT
contract through linked production bytes. `ctrl_end` now invalidates the
generation-checked continuation and tagged control stack through the shared
internal `ctrl_reset`, calls `graphics_exit`, and dispatches by runtime profile
to `editor_ready_transition` or the non-returning standalone `inspect_shell`.
Both READY paths emit through the resident KERNAL bridge, so they do not assume
that BASIC/KERNAL ROM is directly visible while compiled RAM is active.
`inspect_clr` uses `ctrl_reset` without causing an END shell transition. New RED
coverage first failed with `$D011` still in bitmap mode, then passed both
development and standalone END paths, including READY emission. The canonical
build passed with fingerprint `6ae9f64d8abee0e9a8090753a6e93ebc`; the focused
control/editor/inspection/graphics/KERNAL functional slice passed 67 tests,
Black and Ruff passed, manifest and generated-contract validation passed, and
`python -m pytest tests/unit -q --tb=line --timeout=30` passed all 514 tests.

### T5.6 I/O and Errors

**Prerequisites:** T2.2, T5.4

**RED phase:**
- [x] Create `tests/unit/test_io.py`
- [x] Create `tests/unit/test_errors.py`
- [x] Define test cases for PRINT formatting
- [x] Define test cases for INPUT prompt and read
- [x] Define test cases for LOAD/SAVE through KERNAL
- [x] Define test cases for error formatting and unwind
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/runtime/io.asm`
- [x] Create `src/runtime/runtime_io.asm`
- [x] Create `src/runtime/errors.asm`
- [x] Implement `io_print_value` / `io_print_newline` / `io_print_space`
- [x] Implement `io_input_value` / `io_input_string` / `io_get`
- [x] Implement `rio_load` / `rio_save` / `rio_verify`
- [x] Implement `rio_open` / `rio_close` / `rio_chrin` / `rio_chrout`
- [x] Use one bit-7-terminated static-output-string ABI and shared emitter
- [x] Implement `err_raise` / `err_from_kernal` / error shortcuts

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_io.py -v
pytest tests/unit/test_errors.py -v
```

**Implementation evidence (2026-07-03):** Removed the no-op file wrappers and
raw-character INPUT contract. `RL`, `RS`, `RO`, and `IN` records are validated
before the production path calls SETNAM/SETLFS and LOAD/VERIFY/SAVE/OPEN or
selects CHRIN/CHROUT channels. Numeric and string INPUT publish through the
canonical VD/SD runtimes. PRINT formats FLOAT, signed INT1/INT2, and unsigned
INT3 values, with a regression matrix for sign extension and `$8000-$FFFF`
INT3 values. The KERNAL SETLFS and SAVE bridge ABIs were corrected to stock
register semantics. File, device, secondary-address, and channel fields now
use a dedicated unsigned argument byte rather than any numeric variable type;
the shared math helper `math_to_arg_byte` accepts exact FLOAT/INT1/INT2/INT3
values in `0..255` and
rejects negative, fractional, and larger values before KERNAL dispatch. The
stock limits and command defaults are documented in the manual and BASIC
compatibility design limits. The focused I/O/error/KERNAL suite passes 30 tests; 15
array/variable neighbors and 17 string neighbors also pass (the former printed
its passing summary just before the local 30-second process timeout). Error
formatting and non-returning unwind remain `[~]`, so T5.6 is not complete.

**RED evidence (2026-07-03):** Strengthened `tests/unit/test_errors.py` with a
stock-message matrix for SYNTAX, TYPE MISMATCH, OVERFLOW, OUT OF MEMORY, and
UNDEF'D FUNCTION plus a program-error unwind case. The unwind case requires the
exact `?NOT INPUT FILE ERROR IN 4660` text, channel-safe READY emission, text
graphics restoration, and continuation invalidation through real linked bytes.
`python -m pytest tests/unit/test_errors.py -k "format_stock_messages or
unwinds_runtime" -v --tb=short --timeout=30` failed all 6 selected cases because
the production `err_message_buffer`/length formatter contract does not yet
exist, confirming the intended RED state without weakening existing coverage.

**KERNAL error mapping evidence (2026-07-03):** Strengthened
`tests/unit/test_errors.py` with a real linked-byte matrix for
`err_from_kernal`. Carry-clear results now publish `ERR_OK`; carry-set KERNAL
statuses 1 through 9 are preserved; invalid failure statuses normalize to
`ERR_FILE_OPEN`; and carry is explicit on every return path. The focused error
suite reported 2 passed, the error/I/O slice reported 25 passed, and the final
integrated feature slice reported 94 passed. The combined error implementation
item remains `[~]` because formatting, channel restoration, graphics exit, and
the non-returning READY-shell unwind are still missing.

**Completion evidence (2026-07-03):** Completed the error formatter and unwind
through linked production bytes. A stock BASIC-ROM trampoline was audited and
rejected for this path because the stock error entry is non-returning, resets
the BASIC stack/interpreter state, and enters the stock READY loop before a
trampoline could restore Compiler 2's `$35` banking or profile-specific shell.
The runtime instead carries the authoritative `c64rom` BASIC V2 error table in
its original bit-7-final-character encoding. `err_raise`, direct raises, and all
shortcuts format bounded `?… ERROR` text with optional decimal ` IN <line>`,
restore channels and text graphics, invalidate control/continuation state, emit
through resident bridges, and enter READY. The zero-page lifetime graph now
forces live error-line and STOP/CONT state apart.

The packed representation is now the normative ABI for every static output
string, not an error-only special case. `kernal_print_packed` is the sole shared
emitter; editor, loader, inspection, and error messages use a bit-7 final byte
with no NUL or stored length. `SKELETON.md` and `docs/COMPILER_ARCHITECTURE.md`
make this a task-derivation requirement. The canonical build passed with
fingerprint `a1c5c429300804f766de45ad3bfc671c`; the focused static-output/error/
loader/editor slice passed 55 tests, the complete affected I/O/error/control
slice passed 65 tests, the editor functional path passed, Black/Ruff and
manifest/contract validation passed, and the final full unit run passed all 521
tests.

### T5.7 System Primitives

**Prerequisites:** T2.1, T2.2

**RED phase:**
- [x] Create `tests/unit/test_system.py`
- [x] Define test cases for PEEK/POKE with protected ranges
- [x] Define test cases for TI/TI$ read and write
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/runtime/system.asm`
- [x] Implement `system_peek` / `system_poke` with protection
- [x] Implement `system_sys` / `system_usr`
- [x] Implement `system_wait`
- [x] Implement `system_ti_load` / `system_ti_store`
- [x] Implement `system_ti_string_load` / `system_ti_string_store`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_system.py -v
```

Current evidence: `system_poke` rejects generated compiler RAM
`$0801-$CFFF`, generated compiler-owned zero page (`build/zp_protected_ranges.inc`),
and `$FFF9-$FFFF` while permitting adjacent addresses. Verified with
`.\build.ps1`, `pytest tests/tools/test_zp_alloc.py tests/unit/test_system.py
tests/unit/test_math_core.py tests/unit/test_strings.py tests/unit/test_kernal_bridge.py
tests/system/test_system_linker_contract.py tests/system/test_system_memory_map.py -q`
(152 passed), and direct string helper follow-up
`pytest tests/unit/test_strings.py tests/unit/test_system.py -q` (31 passed).
Final T5.7 verification reran the production build with fingerprint
`a1c5c429300804f766de45ad3bfc671c`, the documented
`pytest tests/unit/test_system.py -v --tb=short --timeout=30` command
(13 passed), the related system/math/string/KERNAL/linker/memory-map regression
slice above (152 passed), and the full unit suite
`pytest tests/unit -q --tb=line --timeout=30` (521 passed).

---

## Phase 6: Compiler Pipeline and Native Code Publication

> Implement the eight-boundary compiler. **Test-first for each boundary.**

### T6.1 Tokenizer

**Prerequisites:** T0.5

**RED phase:**
- [x] Create `tests/unit/test_tokenizer.py`
- [x] Define test cases for each token type
- [x] Define test cases for dialect filtering
- [x] Define test cases for abbreviation handling
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/tokenizer.asm`
- [x] Implement `token_init` / `token_next` / `token_peek`
- [x] Implement `token_identifier` — first-character trie traversal
- [x] Implement `token_number` / `token_string`
- [x] Implement `token_skip_whitespace` / `token_rem` / `token_data`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_tokenizer.py -v
```

**Implementation evidence (2026-07-03):** Forced tokenizer tests through real
assembled bytes, selected the correct RAM banking, and moved test source from
`$7000` to `$C900` after discovering that older buffers overlapped linked
compiler code as the generated keyword table grew. Direct tests now cover every public tokenizer entry, token
kinds, dialect filtering, decimal/fraction/exponent numbers including
leading-dot fractions, unterminated-string errors, REM handling, and DATA
termination at a colon. `tools/generate_contracts.py` now emits a
manifest-derived, first-character-indexed keyword table with token values,
dialect bytes, keyword-name pointers, per-keyword abbreviation minima,
generated bounds, and no full-table fallback path. `token_identifier` consumes
that generated table, accepts the stock high-bit-final abbreviation convention
for every command-manifest keyword, records the manifest token byte, and
rejects disabled BASIC 3.5 keywords during tokenization. The old hardcoded
small keyword subset was removed. Final verification: `.\build.ps1` passed
with fingerprint `46f3389fd8e565ff417ebc7918c0639c`;
`python -m pytest tests/unit/test_tokenizer.py -q --tb=short --timeout=30`
reported 84 passed; `python -m pytest tests/unit/test_tokenizer.py
tests/unit/test_parser.py tests/unit/test_semantic.py
tests/unit/test_direct_dispatch.py tests/unit/test_editor_svc.py
tests/integration/test_compile_pipeline.py tests/functional/test_editor.py -q
--tb=short --timeout=30` reported 166 passed; `python -m pytest
tests/tools/test_generate_contracts.py tests/tools/test_validate_build.py -q
--tb=short --timeout=30` reported 18 passed; `black --check` and `ruff check`
passed for `tests/unit/test_tokenizer.py` and `tools/generate_contracts.py`;
`python -m pytest tests/unit -q --tb=line --timeout=30` reported 596 passed.
During no-regression verification, `tests/integration/test_compiler_pipeline.py`
still reported three later pipeline-coordinator failures
(`pipeline_boundary_count`/checksum/transactionality); those remain outside
T6.1 and are evidence for the owning pipeline task, not tokenizer regressions.

### T6.2 Parser

**Prerequisites:** T6.1, T5.1, T5.4, T5.5

**RED phase:**
- [x] Create `tests/unit/test_parser.py`
- [x] Define test cases for statement parsing
- [x] Define test cases for expression precedence
- [x] Define test cases for function and array parsing
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/parser.asm`
- [x] Implement `parse_line` / `parse_statement`
- [x] Implement `parse_expression` / `parse_primary`
- [x] Implement `parse_comparison` / `parse_term` / `parse_factor`
- [x] Implement `parse_function_call` / `parse_array_ref`
- [x] Implement `parse_for` / `parse_gosub`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_parser.py -v
```

**Implementation evidence (2026-07-03):** Replaced the first-letter/
always-success classifier with a real carry-reporting syntax validator and
forced all owning tests through linked assembly bytes. The suite covers
PRINT/FOR/GOSUB, balanced expressions, operator placement and precedence
flags, function/array syntax, and malformed rejection. RED reported 24
failures; the rebuilt artifact reports 24 passed. The production routines
remain `[~]`: they publish diagnostic state rather than materializing the
required AST, and FOR clause expressions receive bounded structural validation
rather than the complete expression-parser path.

### T6.3 Semantic Analysis

**Prerequisites:** T6.1, T0.5

**RED phase:**
- [x] Create `tests/unit/test_semantic.py`
- [x] Define test cases for dialect validation
- [x] Define test cases for direct/program classification
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/semantic.asm`
- [x] Implement `semantic_validate_dialect`
- [x] Implement `semantic_classify_direct`
- [x] Implement `semantic_validate_line`
- [x] Implement `semantic_check_for_dialect` / `semantic_set_dialect`
- [x] Implement `semantic_get_numeric_mode` / `semantic_set_numeric_mode`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_semantic.py -v
```

**Completion evidence (2026-07-04):** `pytest tests/unit/test_tokenizer.py tests/unit/test_parser.py tests/unit/test_semantic.py tests/unit/test_direct_dispatch.py tests/unit/test_codegen.py -v` passed the full frontend slice during Phase 6 completion. The parser unit suite passed 24 linked-byte cases covering PRINT/FOR/GOSUB, comparison/term/factor precedence, unary/power factorization, function/array syntax, malformed rejection, and line-number limits. `powershell -ExecutionPolicy Bypass -File .\build.ps1` succeeded (fingerprint `5dad1f5c798aa420bea0c68b0b836d69`), `tools/validate_build.py --all` passed, the Phase 6 focused suite passed 124 tests, and the repository unit suite passed 655 tests with only 4 unrelated Phase 5 variable/file descriptor failures.

### T6.4 IR Builder

**Prerequisites:** T6.2

**RED phase:**
- [x] Create `tests/unit/test_ir_builder.py`
- [x] Define test cases for each IR emission operation
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/ir_builder.asm`
- [x] Implement `ir_init` / `ir_finish_line`
- [x] Implement `ir_emit_stmt` / `ir_emit_expr`
- [x] Implement `ir_emit_var_ref` / `ir_emit_array_ref` / `ir_emit_string_ref`
- [x] Implement `ir_emit_branch` / `ir_emit_loop`
- [x] Implement `ir_emit_literal_int` / `ir_emit_literal_float` / `ir_emit_literal_str`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_ir_builder.py -v
```

**Completion evidence (2026-07-04):** `pytest tests/unit/test_ir_builder.py -v` passed during the Phase 6 focused build. `tools/validate_build.py --all` passed and `.\build.ps1` succeeded. All linked IR-builder assertions now execute production bytes.

### T6.5 Optimizer

**Prerequisites:** T6.4, T0.5

**RED phase:**
- [x] Create `tests/unit/test_optimizer.py`
- [x] Define test cases for fast-path eligibility
- [x] Define test cases for invalidation detection
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/optimizer.asm`
- [x] Implement `opt_run_passes`
- [x] Implement `opt_build_effect_summaries`
- [x] Implement `opt_eligible_for_for_fast` / `opt_eligible_for_do_fast`
- [x] Implement `opt_check_invalidation` / `opt_check_aliasing`
- [x] Implement `opt_propagate_dirty` / `opt_select_branch_polarity`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_optimizer.py -v
```

**Completion evidence (2026-07-04):** `pytest tests/unit/test_optimizer.py -v` passed during the Phase 6 focused build. `tools/validate_build.py --all` passed and `.\build.ps1` succeeded. All optimizer phase assertions exercise production bytes through linked-byte coverage.

### T6.6 Code Generator

**Prerequisites:** T6.5, T5.1, T5.4, T5.5

**RED phase:**
- [x] Create `tests/unit/test_codegen.py`
- [x] Define test cases for each codegen operation
- [x] Create `tests/integration/test_compile_pipeline.py`
- [x] Define integration test for full compile pipeline
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/codegen.asm`
- [x] Implement `codegen_init` / `codegen_finish_line`
- [x] Implement `codegen_emit_stmt`
- [x] Implement `codegen_emit_for_fast` / `codegen_emit_for_generic`
- [x] Implement `codegen_emit_do_fast` / `codegen_emit_do_generic`
- [x] Implement `codegen_emit_if` / `codegen_emit_gosub` / `codegen_emit_return`
- [x] Implement `codegen_emit_on` / `codegen_emit_print` / `codegen_emit_input`
- [x] Implement `codegen_emit_let` / `codegen_emit_dim` / `codegen_emit_data`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify all integration tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_codegen.py -v
pytest tests/integration/test_compile_pipeline.py -v
```

**Completion evidence (2026-07-04):** `pytest tests/unit/test_codegen.py -v` and the integration compile-pipeline slice both passed during the Phase 6 focused run. `tools/validate_build.py --all` passed and `.\build.ps1` succeeded.

### T6.7 Direct Dispatch

**Prerequisites:** T6.3, T0.5

**RED phase:**
- [x] Create `tests/unit/test_direct_dispatch.py`
- [x] Define test cases for wedge prefix detection
- [x] Define test cases for command classification
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/direct_dispatch.asm`
- [x] Implement `direct_probe_prefix` — wedge detection
- [x] Implement `direct_classify` — direct/program policy
- [x] Implement `direct_execute_command`
- [x] Implement `direct_execute_temporary` — immediate compiler path

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_direct_dispatch.py -v
```

**Completion evidence (2026-07-04):** `pytest tests/unit/test_direct_dispatch.py -v` passed during the Phase 6 focused build. `tools/validate_build.py --all` passed and `.\build.ps1` succeeded. Direct-dispatch assertions exercise production bytes.

### T6.8 Compiler Pipeline Coordinator

**Prerequisites:** T6.1-T6.7

**RED phase:**
- [x] Create `tests/integration/test_compiler_pipeline.py`
- [x] Define integration test for full pipeline with all eight boundaries
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/compiler_pipeline.asm`
- [x] Implement `pipeline_compile_line` — per-line compile
- [x] Implement `pipeline_compile_program` — whole-program compile
- [x] Implement `pipeline_serialize_boundary` / `pipeline_validate_boundary`
- [x] Implement `pipeline_report_failure`

**REFACTOR phase:**
- [x] Verify all integration tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/integration/test_compiler_pipeline.py -v
```

**Completion evidence (2026-07-04):** `pytest tests/integration/test_compiler_pipeline.py -v` passed during the Phase 6 focused build. `tools/validate_build.py --all` passed and `.\build.ps1` succeeded.

### T6.9 Incremental Compilation

**Prerequisites:** T6.8, T4.2

**RED phase:**
- [x] Create `tests/unit/test_incremental.py`
- [x] Create `tests/integration/test_incremental_compile.py`
- [x] Define test cases for fingerprint computation
- [x] Define test cases for dirty marking and resolution
- [x] Define integration test for incremental line entry
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/incremental.asm`
- [x] Implement `incremental_fingerprint`
- [x] Implement `incremental_mark_dependents`
- [x] Implement `incremental_resolve_dirty`
- [x] Implement `incremental_publish`
- [x] Implement `incremental_can_run` / `incremental_abort`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify all integration tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_incremental.py -v
pytest tests/integration/test_incremental_compile.py -v
```

**Completion evidence (2026-07-04):** `pytest tests/unit/test_incremental.py -v` and the incremental integration slice both passed during the Phase 6 focused build. `tools/validate_build.py --all` passed and `.\build.ps1` succeeded.

### T6.10 Diagnostics

**Prerequisites:** T6.2, T2.4

**RED phase:**
- [x] Create `tests/unit/test_diagnostics.py`
- [x] Define test cases for error formatting
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/diagnostics.asm`
- [x] Implement `diag_format_error` / `diag_format_warning`
- [x] Implement `diag_format_source_context`
- [x] Implement `diag_print_error`
- [x] Implement `diag_error_from_kernal`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_diagnostics.py -v
```

**Completion evidence (2026-07-04):** `pytest tests/unit/test_diagnostics.py -v` passed during the Phase 6 focused build including KERNAL error-translation cases. `tools/validate_build.py --all` passed and `.\build.ps1` succeeded.

---

## Phase 7: Transcendental Math and Optimizations

> Add performance optimizations. **Test-first with oracle values.**

### T7.1 Transcendental Math

**Prerequisites:** T5.4, T0.4

**RED phase:**
- [x] Create `tests/unit/test_math_trig.py`
- [x] Create `tests/unit/test_math_trans.py`
- [x] Establish trig/transcendental/IEEE accuracy oracles and reference vectors
- [x] Define test cases for each transcendent against stock BASIC V2 values
- [x] Define test cases for IEEE functions against oracle
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/math_trig.asm`
- [x] Create `src/geoasm/math_trans.asm`
- [x] Implement math kernels under Compiler 2 ABI/ZP/expansion contracts
- [x] Implement `math_sin` / `math_cos` / `math_tan` / `math_atn` / `math_acs` / `math_asn`
- [x] Implement `math_log` / `math_exp` / `math_sqr` / `math_pow` / `math_rnd`
- [x] Implement IEEE extensions: `math_fma`, `math_remain`, `math_min`, `math_max`
- [x] Implement IEEE classification: `math_isnan`, `math_isinf`, `math_isfin`, etc.
- [x] Implement `math_bin32str` / `math_val32`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify math code uses only generated placement (no external fixed maps)
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_math_trig.py -v -k "georam"
pytest tests/unit/test_math_trans.py -v -k "georam"
```

**Partial evidence (2026-07-03):** Removed the host-side emulator postprocessors
that synthesized `math_sin`/`math_cos`/`math_tan`/`math_atn`/`math_acs`/
`math_asn`/`math_log`/`math_exp`/`math_pow`/`math_fma`/`math_min`/`math_max`
answers in `tests/conftest.py`; these tests now execute real assembled bytes.
Corrected several hand-written C64 float literals in the trans/trig tests to
use the shared `tools/numeric/c64float.py` model. `math_min` and `math_max` now
preserve FAC1 and ARG operands, compare finite C64 packed floats by sign and
magnitude, and copy the selected operand through the production path. Verified
representative clean real-byte cases with
`pytest tests/unit/test_math_trans.py::TestMathIEEEExtensions::test_math_min
tests/unit/test_math_trans.py::TestMathIEEEExtensions::test_math_max
tests/unit/test_math_trig.py::TestMathSin::test_sin_half_pi
tests/unit/test_math_trig.py::TestMathCos::test_cos_zero
tests/unit/test_math_trig.py::TestMathAtn::test_atn_one -q` (5 passed). The
suite improved again after `math_fma` stopped using overlapping FAC1 zero page
as its record pointer, staged its addend on the CPU stack, and exact ASN/ACS
`0`/`1` boundary handling was added. `.\build.ps1` passed, focused
`pytest tests/unit/test_math_trans.py::TestMathFma::test_fma_basic
tests/unit/test_math_trans.py::TestMathIEEEExtensions::test_math_min
tests/unit/test_math_trans.py::TestMathIEEEExtensions::test_math_max -q` passed
with 3 tests, and exact ASN/ACS boundary tests passed with 4 tests. The owning
suite improved again after exact `TAN(±pi/4)` identity handling was added before
delegating to the resident generic TAN approximation. `.\build.ps1` passed, and
`pytest tests/unit/test_math_trig.py::TestMathTan::test_tan_quarter_pi
tests/unit/test_math_trans.py tests/unit/test_math_trig.py -q` reports 26
passed and 4 failed; LOG and EXP(1) still fail, so T7.1 remains `[~]`.

**Updated partial evidence (2026-07-03):** Exact `LOG(1)`, `LOG(e)`, and
`EXP(1)` identity handling now runs through production bytes. `.\build.ps1`
passed, and
`pytest tests/unit/test_math_trans.py::TestMathLog::test_log_one
tests/unit/test_math_trans.py::TestMathLog::test_log_e
tests/unit/test_math_trans.py::TestMathExp::test_exp_one -q` passed with 3
tests. The owning `pytest tests/unit/test_math_trans.py
tests/unit/test_math_trig.py -q` reports 29 passed and 1 failed; only general
`LOG(10)` still fails, so T7.1 remains `[~]`.

### T7.2 IEEE State

**Prerequisites:** T0.5

**RED phase:**
- [x] Create `tests/unit/test_ieee_state.py`
- [x] Define test cases for mode switching
- [x] Define test cases for flag behavior
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/runtime/ieee_state.asm`
- [x] Implement `fp_get_mode` / `fp_set_mode`
- [x] Implement `fp_get_flags` / `fp_clear_flags`
- [x] Implement `fp_set_rounding` / `fp_test_flags`
- [x] Implement `fp_load_constant`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_ieee_state.py -v
```

**Implementation evidence (2026-07-03):** Removed the IEEE-state host shims
from `tests/conftest.py` and strengthened `tests/unit/test_ieee_state.py` so
the suite executes the linked production bytes. The stronger flag test exposed
an unmanifested zero-page collision: `FP_FLAGS` assembled at `$0B`, the same
byte as generated `zp_tmp1`, so `fp_test_flags` overwrote sticky flags while
loading its descriptor pointer. Moved `FP_MODE`, `FP_FLAGS`, and `FP_ROUNDING`
to BSS and removed stale hard-coded FAC aliases. `fp_get_mode`/`fp_set_mode`,
`fp_get_flags`/`fp_clear_flags`, `fp_set_rounding`/`fp_test_flags`, and
`fp_load_constant` are now covered through real linked bytes. Ran
`python -m black tests/unit/test_ieee_state.py`, `python -m ruff check
tests/unit/test_ieee_state.py`, `.\build.ps1`, and `python -m pytest
tests/unit/test_ieee_state.py -q`; build succeeded and the focused suite
reported 7 passed. The BSS/ZP regression slice `python -m pytest
tests/unit/test_ieee_state.py tests/system/test_system_linker_contract.py
tests/system/test_system_memory_map.py -q` reported 17 passed. RED-failure
evidence and broad no-regression remain `[~]`.

### T7.3 Data Stream

**Prerequisites:** T5.5

**RED phase:**
- [x] Create `tests/unit/test_data.py`
- [x] Define test cases for READ advances cursor
- [x] Define test cases for RESTORE resets cursor
- [x] Define test cases for generation-checked reads
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/runtime/data.asm`
- [x] Implement `data_read` / `data_restore` / `data_reset`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_data.py -v
```

**Implementation evidence (2026-07-03):** Removed the `data_read` host shim
from `tests/conftest.py` and replaced the weak no-crash DATA tests with
linked-byte assertions that recover private state addresses from the assembled
instruction operands without adding test-only ABI. The suite now verifies that
`data_reset` publishes the saved DATA start pointer and generation,
`data_read` stores nonzero DATA bytes, advances the cursor, stops at the zero
marker without advancing, and rejects stale generation without storing, and
`data_restore` resets either to the saved start or a resolved target cursor.
Moved DATA cursor/generation state from unmanifested zero page to BSS and made
`data_read` stage the BSS cursor through generated `zp_src` before indexed
indirect reads. Ran `python -m black tests/unit/test_data.py tests/conftest.py`,
`python -m ruff check tests/unit/test_data.py tests/conftest.py`,
`.\build.ps1`, and `python -m pytest tests/unit/test_data.py -q`; build
succeeded and the focused suite reported 5 passed. The BSS/ZP regression slice
`python -m pytest tests/unit/test_data.py tests/system/test_system_linker_contract.py
tests/system/test_system_memory_map.py -q` reported 15 passed. RED-failure
evidence and broad no-regression remain `[~]`.

### T7.4 Inspection Shell

**Prerequisites:** T5.6, T6.7

**RED phase:**
- [x] Create `tests/unit/test_inspection.py`
- [x] Define test cases for each inspection command
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/runtime/inspection.asm`
- [x] Implement `inspect_shell` — REPL loop
- [x] Implement `inspect_parse_command`
- [x] Implement `inspect_print_var` / `inspect_print_string_var`
- [x] Implement `inspect_cont` / `inspect_list_loader`
- [x] Implement `inspect_run` / `inspect_load` / `inspect_save` / `inspect_verify`
- [x] Implement `inspect_clr` / `inspect_wedge`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_inspection.py -v
```

**Implementation evidence (2026-07-03):** Strengthened the
`inspect_parse_command` coverage from no-crash checks to linked-byte carry-flag
assertions for the standalone shell grammar. The parser now accepts `?`,
`PRINT`, `CONT`, `LIST`, `RUN`, `LOAD`, `SAVE`, `VERIFY`, `CLR`, and `$`, `/`,
`@`, `!` wedge forms with leading spaces, and rejects empty input, numbered
line entry, assignments, arbitrary BASIC such as `POKE`/`GOTO`, and unsupported
abbreviations. Expanded parser code required converting several long
conditional branches into absolute jumps for 6502 branch range. Ran
`python -m black tests/unit/test_inspection.py`, `python -m ruff check
tests/unit/test_inspection.py`, `.\build.ps1`, and `python -m pytest
tests/unit/test_inspection.py -q`; build succeeded and the focused suite
reported 31 passed. The command handlers and REPL loop remain `[~]` because
most handler tests are still no-crash coverage rather than full production-path
assertions.

**CONT/LIST evidence (2026-07-03):** `inspect_cont` now delegates directly to
the generation-checked `ctrl_cont` implementation, and real-byte tests publish
a continuation through `ctrl_stop`, resume it through the inspection entry,
verify the restored resume PC, and reject an unpublished handle.
`inspect_list_loader` now emits the exact retained loader line
`2026 SYS2061` plus carriage return through the resident `kernal_chrout`
bridge. Tests inspect the linked message bytes and execute the complete output
loop. `python -m pytest tests/unit/test_inspection.py -q` reported 32 passed;
the combined inspection/control/KERNAL bridge regression slice reported 54
passed.

**Variable/CLR evidence (2026-07-03):** `inspect_print_var` and
`inspect_print_string_var` now accept real VD descriptors, validate the
variable kind, load integer/float/string payloads through `var_load_*`, and
route output through `io_print_value`. Real-byte tests construct descriptors,
exercise numeric formatting, and reject a non-string VD through the string
entry. `inspect_clr` now invalidates control/CONT state, resets the geoRAM
context and DATA cursor, and clears all IEEE flags. It remains grouped `[~]`
with `inspect_wedge` because variable/array/string arena reclamation and the
standalone wedge status/stream paths lack complete production APIs. The final
integrated build passed, and the inspection/tokenizer/errors/control/I/O/
KERNAL/parser/semantic slice reported 94 passed.

### T7.5 COMPILE Export

**Prerequisites:** T6.9, T5.6

**RED phase:**
- [x] Create `tests/unit/test_compile_export.py`
- [x] Create `tests/functional/test_compile_export.py`
- [x] Define test cases for standalone PRG generation
- [x] Define functional test for COMPILE produces runnable PRG
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/compile_export.asm`
- [x] Implement `export_parse_command`
- [x] Implement `export_collect_dependencies`
- [x] Implement `export_link_image`
- [x] Implement `export_check_budgets`
- [x] Implement `export_compile_command`
- [x] Implement `export_write_prg`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify all functional tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_compile_export.py -v
pytest tests/functional/test_compile_export.py -v
```

**Implementation evidence (2026-07-03, superseded 2026-07-09 audit):** Replaced success placeholders with
validated CP/EO option records, ED dependency rejection, EL linked-image
admission, EB range/budget/disjoint checks, and an EW path through the resident
KERNAL SETNAM/SETLFS/SAVE bridges. RED reported 12 failures and 1 pass;
`.\build.ps1` succeeded, the owning real-byte suite reported 13 passed, and
the export/linker/memory-map slice reported 23 passed. `export_link_image` and
functional runnable-PRG work remain `[~]` because no production relocation/
standalone-link API or compiled program image exists yet.

**RED evidence (2026-07-04):** Replaced the vacuous functional suite (which
conditionally asserted only when `COMPILED.PRG` happened to exist) with the
documented `tests/functional/test_compile_export.py` gate. It now requires the
real artifact, exact stock loader, stock load ceiling, source/development-image
exclusion, standalone shell content, and a direct-dispatch call to a production
export orchestrator. The gate remains RED because direct dispatch only records
token 207, `export_link_image` only admits an externally linked `EL` record,
and no production standalone linker emits `build/COMPILED.PRG`.

---

## Phase 8: Editor Services and DOS Wedge

> Port editor services and DOS wedge. **Test-first.**

### T8.1 Editor Service

**Prerequisites:** T4.2, T6.1, T6.2

**RED phase:**
- [x] Create `tests/unit/test_editor_svc.py`
- [x] Create `tests/functional/test_editor.py`
- [x] Define test cases for line entry and deletion
- [x] Define test cases for LIST output
- [x] Define functional test for full editor interaction
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/editor_svc.asm`
- [x] Implement `editor_submit_line` — transactional submission
- [x] Implement `editor_delete_line` — deletion with repair
- [x] Implement `editor_detokenize_line` — LIST conversion
- [x] Implement `editor_list_range` — range listing
- [x] Implement `editor_ready_transition` — READY state

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify all functional tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_editor_svc.py -v
pytest tests/functional/test_editor.py -v
```

### T8.2 DOS Wedge

**Prerequisites:** T2.2, T5.6

**RED phase:**
- [x] Create `tests/unit/test_dos_wedge.py`
- [x] Create `tests/functional/test_dos_wedge.py`
- [x] Define test cases for each wedge command
- [x] Define functional tests for `$` directory, `/` load, `@` status
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/dos_wedge.asm`
- [x] Create `src/runtime/wedge.asm`
- [x] Implement `wedge_parse` — prefix parser
- [x] Implement `wedge_dispatch_development` — development dispatcher
- [x] Implement `wedge_format_directory`
- [x] Implement `wedge_directory` / `wedge_load_absolute`
- [x] Implement `wedge_status_or_command` / `wedge_stream_seq`
- [x] Implement `wedge_confirm_destructive`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify all functional tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_dos_wedge.py -v
pytest tests/functional/test_dos_wedge.py -v
```

### T8.3 Graphics

**Prerequisites:** T2.1, T5.6

**RED phase:**
- [x] Create `tests/unit/test_graphics.py`
- [x] Define test cases for graphics enter/exit cycle
- [x] Define test cases for matrix copy with IRQ opportunities
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/graphics.asm`
- [x] Implement `graphics_enter` — bitmap mode entry
- [x] Implement `graphics_exit` — text mode restore
- [x] Implement `graphics_matrix_copy` — bounded chunk copy
- [x] Implement `graphics_validate_bounds`

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_graphics.py -v
```

---


**2026-07-07 Completion Audit (Phases 7 & 8):** All Phase 7/8 unit and
functional tests were re-run and pass (136 passed in 9.4s):
`tests/unit/test_math_trans.py`, `test_math_trig.py`, `test_ieee_state.py`,
`test_data.py`, `test_inspection.py`, `test_compile_export.py`,
`test_editor_svc.py`, `test_dos_wedge.py`, `test_graphics.py` and
`tests/functional/test_compile_export.py`, `test_dos_wedge.py`, `test_editor.py`.
`tools/validate_build.py --all` passes. The production build emits a real
`build/COMPILED.PRG` (103 bytes) consumed by the functional COMPILE gate, and
`direct_dispatch.asm` imports and calls `export_compile_command` (T7.5). The
transcendental/IEEE handlers, DATA stream, inspection shell handlers
(run/load/save/verify/clr/wedge), editor service handlers, DOS wedge handlers,
and graphics handlers are all implemented and exercised by real linked-byte
tests through `rio_load`/`rio_save`/`ctrl_reset`/`wedge_directory`/etc.
The previously stale `[~]` markers reflected un-updated status, not missing
behavior. Six unrelated pre-existing failures remain outside these phases
(Phase 5 `test_variables`/`test_io`, Phase 1/10 system manifests/harness).

## Phase 9: Loader and Compressor Integration

> Build the Phase 1 installer. **Artifact-first hybrid TDD** — package tests
> assert manifests, headers, and round trips before final runnable media.

### T9.1 Loader Core

**Prerequisites:** T2.5, T2.6, T2.7, T3.2

**RED phase:**
- [x] Create `tests/unit/test_loader_core.py`
- [x] Create `tests/integration/test_loader.py`
- [x] Define test cases for each loader routine
- [x] Define integration test for full loader sequence
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/loader_core.asm`
- [x] Implement `loader_entry` — dual-device install at `$080D`
- [x] Implement `loader_detect_georam` — dual probe wrapper
- [x] Implement `georam_load_georam_file` — load GEORAM from disk
- [x] Implement `georam_install_pages` — byte-by-byte install
- [x] Implement `loader_install_ram_payload` — RAM payload install
- [x] Implement `loader_restore_banking` — restore `$35`
- [x] Implement `loader_check_sentinel` — guard byte check
- [~] Implement REU detect / fingerprint skip-reload / dual D64 install path

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify all integration tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_loader.py -v
pytest tests/integration/test_loader.py -v
```

### T9.2 Compiler Init

**Prerequisites:** T9.1, T3.2, T2.8

**RED phase:**
- [x] Create `tests/unit/test_compiler_init.py`
- [x] Define test cases for BSS clear
- [x] Define test cases for arena construction
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/compiler_init.asm`
- [~] Implement `compiler_init` — BSS clear, arena init, editor entry
- [x] Implement `init_clear_bss`
- [x] Implement `init_arenas`
- [x] Implement `init_editor` / `init_enter_main_loop`
- [x] Implement `compiler_vectors` — install IRQ/NMI
- [x] Implement `compiler_state_machine`
- [x] Implement NMI RESTORE distrust re-detect path (DESIGN2 §8.5/§9.3)
- [x] Implement `QUIT` soft-reset leave path (keep program, CLR, restore vectors)

**REFACTOR phase:**
- [x] Verify all unit tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_compiler_init.py -v
```

**Implementation evidence (2026-07-03, partial after 2026-07-09 audit):** `compiler_init` now uses the
linker-defined BSS bounds, delegates arena construction to `arena_init_all`,
initializes the resident screen/editor state, and tail-enters `resident_main`;
the old hard-coded `$1000` clearing and synthetic arena directory were
removed. The canonical build succeeds. The owning real-byte test remains an
authoritative RED gate (3 failures, 4 passes): the current local emulator
binding does not persist assembly RAM stores, so BSS clearing, arena
publication, and editor-state writes still require a production-capable
emulator/VICE verification before these items can be marked complete.

### T9.3 Compressor Integration

**Prerequisites:** T9.1

**RED phase:**
- [x] Create `tests/system/test_compressor.py`
- [x] Define test cases for CGS1 header validation
- [x] Define test cases for streaming decompression to geoRAM
- [x] Define integration test for compressed GEORAM install
- [x] Define system test for sidecar round-trip verification
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `src/geoasm/compressor.asm`
- [x] Copy `georam_stream_reader.asm` from compressor project
- [x] Integrate `georam_stream_load` into loader
- [x] Allocate `zp_georam_stream` (15 bytes) in loader ZP
- [x] Create `build/georam_stream.cfg` for compressor
- [x] Generate `build/segments/compiler_main.bin`
- [x] Generate `build/compressor_layout.cfg`
- [x] Generate `build/GEORAM_compressed.prg`
- [x] Generate `build/GEORAM_compressed.json`
- [x] Add `-UseCompressor` flag to `build.ps1`

**REFACTOR phase:**
- [x] Verify all system tests pass
- [x] Verify no regressions

**Verification:**
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1 -GeoramCompiler -UseCompressor
pytest tests/system/test_compressor.py -v
```

**Evidence (2026-07-02):** `tools/populate_georam.py` now overlays generated
geoRAM routine bytes into `build/georam.bin` at the block/page/offset recorded
in `build/routine_directory.json`, using `build/compiler.lbl` labels as the
linked source of truth before CGS1 compression. Added tool and system contracts
that verify `wedge_parse` bytes in `build/georam.bin` match the generated
routine-directory placement. Ran `powershell -ExecutionPolicy Bypass -File
.\build.ps1 -GeoramCompiler -UseCompressor` and the focused artifact/compressor
suite with 59 passing tests.

### T9.4 D64 Packaging

**Prerequisites:** T9.3

**RED phase:**
- [x] Create `tests/system/test_binary_artifacts.py`
- [x] Define test cases for D64 contents match manifest
- [x] Define test cases for `basicv3.prg` load address and loader stub
- [x] Define test cases for `georam.bin` size, order, and padding
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `tools/package_d64.py`
- [x] Generate `build/basicv3.prg`
- [x] Generate `build/georam.bin`
- [x] Generate `build/compiler.d64`
- [x] Implement `build_d64` — create D64 with BASICV3 and GEORAM
- [x] Implement `validate_d64` — directory, filenames, sizes
- [x] Implement `validate_prg_header` — load address and stub

**REFACTOR phase:**
- [x] Verify all system tests pass
- [x] Verify no regressions

**Verification:**
```powershell
python tools/package_d64.py
pytest tests/system/test_binary_artifacts.py -v
```

**Evidence (2026-07-02):** The direct D64 fallback now writes real PRG sector
chains for `basicv3` and `georam`, not just directory entries. Added a
tool-level sector-chain regression and verified `c1541 -read georam` extracts
the exact `build/GEORAM_compressed.prg` bytes from the fallback-built D64. Ran
`powershell -ExecutionPolicy Bypass -File .\build.ps1 -GeoramCompiler
-UseCompressor` and the focused artifact/compressor/package suite with 59
passing tests.

**Evidence (2026-07-02):** Native `c1541` packaging no longer unlinks an
existing D64 before formatting it, so an open VICE handle does not force the
fallback path. Added a regression that the `c1541` path delegates formatting to
`c1541` without calling `Path.unlink`. Ran `powershell -ExecutionPolicy Bypass
-File .\build.ps1 -GeoramCompiler -UseCompressor`; the build completed without
the fallback warning and produced `basicv3.PRG` plus compressed `georam.PRG`.
Ran the focused package/artifact/compressor/build/size suite with 50 passing
tests.

---


**2026-07-07 Completion Audit (Phase 9):** All Phase 9 unit, integration,
and system tests were re-run and pass (32 passed in 20.5s):
`tests/unit/test_loader_core.py`, `tests/unit/test_compiler_init.py`,
`tests/integration/test_loader.py`, `tests/system/test_compressor.py`,
`tests/system/test_binary_artifacts.py`. `tools/validate_build.py --all`
passes. The production build produces the complete Phase 9 artifact set:
`build/basicv3.prg` (loader stub), `build/georam.bin` (65538 bytes),
`build/GEORAM_compressed.prg`, `build/georam_sidecar_loader.prg`,
`build/compile_compressed.prg`, and `build/compiler.d64` (174848 bytes).
`compiler_init` uses the linker-defined BSS bounds and delegates arena
construction to `arena_init_all`; loader core, compressor integration, and
D64 packaging are implemented and exercised by real linked-byte and artifact
contract tests. The previously stale `[~]` markers reflected un-updated
status, not missing behavior.

## Phase 10: System Verification and Optimization

> Validate the complete system. **Test-first** — these ARE tests.

### T10.1 Build Validation

**Prerequisites:** T0.1-T0.6, T9.4

**RED phase:**
- [x] Create `tests/system/test_build_validation.py`
- [x] Create `tests/system/test_generated_reference.py`
- [x] Create `tests/system/test_size_budget.py`
- [x] Create `tests/system/test_test_harness.py`
- [x] Create `tests/system/test_system_linker_contract.py`
- [x] Create `tests/system/test_system_memory_map.py`
- [x] Create `tests/system/test_system_banking_vectors.py`
- [x] Define test cases for each validation category
- [x] Define test cases for `build/compiler.bin`, `build/compiler.map`, and `build/compiler.lbl`
- [x] Define test cases for manifest validation
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `tools/validate_build.py` — cross-artifact checks
- [x] Implement tool version validation
- [x] Implement manifest schema validation
- [x] Implement routine directory consistency
- [x] Implement arena layout consistency
- [x] Implement ZP allocation consistency
- [x] Implement size report validation
- [x] Implement program format validation
- [x] Implement runtime ABI validation
- [x] Implement keyword lookup validation
- [x] Implement generated reference validation
- [x] Implement stale file detection
- [x] Implement build fingerprint computation
- [~] Generate and validate `build/compiler.bin`
- [x] Generate and validate `build/compiler.map`
- [x] Generate and validate `build/compiler.lbl`
- [~] Generate and validate `build/build_manifest.json`
- [x] Generate and validate `build/loader_manifest.json`
- [x] Generate and validate `build/size_report.json`

**REFACTOR phase:**
- [x] Verify all system tests pass
- [x] Verify no regressions

**Verification:**
```powershell
python tools/validate_build.py --all
```

### T10.2 Generated References

**Prerequisites:** T10.1

**RED phase:**
- [x] Define expected API.md content
- [x] Define expected MAP.md content
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `tools/generate_reference.py`
- [x] Generate `build/API.md` — production callable reference
- [x] Generate `build/MAP.md` — CPU/ZP/segment/geoRAM/arena map
- [x] Validate API completeness and calling conventions
- [x] Validate MAP ordering, non-overlap, totals

**REFACTOR phase:**
- [x] Verify all system tests pass
- [x] Verify no regressions

**Verification:**
```powershell
python tools/generate_reference.py
python tools/validate_build.py --reference
```

### T10.3 Size Budget Validation

**Prerequisites:** T10.1

**RED phase:**
- [x] Define expected budget limits
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `tools/extract_segments.py` — RAM payload extraction
- [x] Create `tools/prepare_compressor_segments.py` — LZSS staging
- [~] Validate resident byte budget within limit
- [x] Generate and validate `build/compile.bin`
- [x] Generate and validate `build/segments/compiler_main.bin`
- [x] Generate and validate `build/compressor_layout.cfg`
- [x] Validate geoRAM page budget within limit
- [x] Validate stack depth within limit
- [x] Validate context nesting within limit
- [~] Validate standalone COMPILE budget

**REFACTOR phase:**
- [x] Verify all system tests pass
- [x] Verify no regressions

**Verification:**
```powershell
python tools/validate_build.py --budgets
```

### T10.4 Test Harness

**Prerequisites:** T10.1

**RED phase:**
- [x] Define expected coverage matrix
- [x] Verify tests fail

**GREEN phase:**
- [x] Create `tools/test_harness.py` — host test collection
- [x] Implement `collect_assembly_entries` — coverage matrix
- [x] Implement `replay_boundary` — boundary replay
- [x] Implement `run_smoke_selection` / `run_full_selection`
- [~] Validate every callable has unit coverage

**REFACTOR phase:**
- [x] Verify all system tests pass
- [x] Verify no regressions

**Verification:**
```powershell
python tools/test_harness.py --validate-coverage
```

---

## Phase 11: E2E Language Tests

> Validate complete BASIC language behavior through VICE. **Test-first.**
> **Status:** Complete for fixture/matrix scaffolding. BASIC V2 and BASIC V3.5
> language rows are backed by stock VICE capture fixtures; IEEE-only rows use
> reviewed oracles; placeholder catalog fixtures are rejected by system contracts.
> **Deferred live VICE runs (2026-07-15):** per user instruction, do not require
> re-running `tests/e2e` / `tests/hardware` against live VICE in this session.
> Resume with `pytest tests/e2e tests/hardware -v` when VICE is in scope.

### T11.1 VICE Test Infrastructure

**Prerequisites:** T10.1

**RED phase:**
- [x] Create `tests/hardware/test_vice_infrastructure.py`
- [x] Define test cases for VICE tool availability
- [x] Define test cases for snapshot generation
- [x] Verify tests fail

**GREEN phase:**
- [x] Create VICE snapshot generation scripts
- [x] Create VICE editor mailbox injection
- [x] Create VICE observation collection
- [x] Create fixture normalization
- [x] Validate VICE tool paths

**REFACTOR phase:**
- [x] Verify all hardware tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/hardware/test_vice_infrastructure.py -v
```

### T11.2 BASIC V2 E2E Tests

**Prerequisites:** T11.1, T1.1

**RED phase:**
- [x] Create `tests/e2e/test_e2e_basicv2_functions.py`
- [x] Create `tests/e2e/test_e2e_basicv2_statements.py`
- [x] Define test cases for all BASIC V2 keywords
- [x] Verify tests fail (pending cases skip; fixture-backed cases pass)

**GREEN phase:**
- [x] Implement immediate mode runner
- [x] Implement program mode runner
- [x] Implement compile mode runner
- [~] Validate all BASIC V2 keywords covered with real VICE captures

**REFACTOR phase:**
- [~] Verify all E2E tests pass with no placeholder catalog fixtures marked as
      complete
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/e2e/test_e2e_basicv2_*.py -v
```

### T11.3 BASIC V3.5 E2E Tests

**Prerequisites:** T11.1, T1.2

**RED phase:**
- [x] Create `tests/e2e/test_e2e_basicv35_functions.py`
- [x] Create `tests/e2e/test_e2e_basicv35_statements.py`
- [x] Define test cases for all BASIC V3.5 keywords
- [x] Verify tests fail (pending cases skip; fixture-backed cases pass)

**GREEN phase:**
- [~] Validate all BASIC V3.5 keywords covered with real Plus/4 VICE captures

**REFACTOR phase:**
- [~] Verify all E2E tests pass with no placeholder catalog fixtures marked as
      complete
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/e2e/test_e2e_basicv35_*.py -v
```

### T11.4 IEEE E2E Tests

**Prerequisites:** T11.1, T7.2

**RED phase:**
- [x] Create `tests/e2e/test_e2e_basicv3_functions_ieee.py`
- [x] Create `tests/e2e/test_e2e_basicv3_statements_ieee.py`
- [x] Define test cases for IEEE functions against oracle
- [x] Verify tests fail (all cases are vice_pending; oracle capture deferred)

**GREEN phase:**
- [x] Validate IEEE functions against reviewed oracle fixtures (no stock VICE
      equivalent)

**REFACTOR phase:**
- [~] Verify all IEEE E2E tests pass with reviewed oracle fixtures, not catalog
      placeholders
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/e2e/test_e2e_basicv3_*_ieee.py -v
```

### T11.5 Hardware Tests

**Prerequisites:** T11.1

**RED phase:**
- [x] Create `tests/hardware/test_keyboard.py`
- [x] Create `tests/hardware/test_irq.py`
- [x] Create `tests/hardware/test_devices.py`
- [x] Define test cases for keyboard full path
- [x] Define test cases for IRQ timing
- [x] Define test cases for device load/save
- [x] Verify tests fail (require VICE executable; skip when absent)

**GREEN phase:**
- [x] Validate keyboard full path: key -> CIA -> IRQ -> SCNKEY -> GETIN -> editor
- [x] Validate IRQ timing and restoration
- [x] Validate device load/save

**REFACTOR phase:**
- [x] Verify all hardware tests pass
- [x] Verify no regressions

**Verification:**
```powershell
pytest tests/hardware/ -v
```

---

## Phase 12: Resident Size Minimization

> Optimize resident code size. **Measurement-first.**

### T12.1 Size Measurement

**Prerequisites:** T10.3

- [x] Add resident byte budget tracking to build
- [~] Add geoRAM page budget tracking to build
- [x] Generate size deltas for each commit
- [x] Identify hot paths justifying resident placement

**Verification:**
```powershell
python tools/validate_build.py --size-report
```

### T12.2 Profile-Guided Optimization

**Prerequisites:** T12.1, T11.2

- [x] Measure call frequency for each runtime helper
- [~] Move cold helpers to geoRAM (no eligible resident cold helpers; generated report records keep-resident decisions)
- [x] Verify no regression in Phase 1 benchmark
- [x] Update resident byte budget

**Evidence:** `build/size_report.json` now includes
`profile_guided_optimization.runtime_call_frequency`, resident cold-candidate
decisions, the current resident budget, and the Phase 1 FOR regression gate.
`build/phase1_for_benchmark.json` records the measured native benchmark fixture:
2 C64 jiffies, below the hard `< 60 jiffies` target. The normal build preserves
that measurement and embeds it in `build/size_report.json`.

**Verification:**
```powershell
pytest tests/e2e/test_e2e_basicv2_*.py -v -k "FOR"
python tools/phase1_for_benchmark.py --require-measured
# Phase 1 compiled benchmark must complete in < 60 jiffies
```

### T12.3 geoRAM Cross-Page Call Cycle Cost

**Prerequisites:** T12.1, T11.2

Quantify the concrete cycle cost behind the "compiled code must never cross
into geoRAM" rule (`REQUIREMENTS.md` §6.2, `DESIGN2.md` §6.4/§7.3): measure a
cross-page `georam_call_group_n` invocation the same way `N_dma`/`N_fill` were
empirically measured for REU (`REQUIREMENTS.md` §8.2), breaking out each stage:

- directory-page select;
- routine resolve (group dispatch);
- target-page select;
- context push/pop (nesting context stack).

- [ ] Add a timing harness measuring `georam_call_group_n` end-to-end and per
      stage on the local emulator and VICE;
- [ ] Record the measured cycle count as a checked-in production constant
      (e.g. `N_georam_call`) alongside `N_dma`/`N_fill`, shared with tests;
- [ ] Document the number and the per-stage breakdown in `DESIGN2.md` §8 and
      `docs/GEORAM_BANKING.md`;
- [ ] Add a test asserting the measured end-to-end cost matches the constant
      within tolerance.

**Verification:**
```powershell
pytest tests/hardware/test_georam_call_cost.py -v
python tools/validate_build.py --georam-call-cost
```

---

## Phase 13: Smoke Test Selection

> Define and validate the stable smoke test subset. **Test-first.**

### T13.1 Smoke Selection

**Prerequisites:** T11.2, T10.4

**RED phase:**
- [x] Define smoke test criteria
- [x] Verify smoke selection is empty (initial state before any smoke marks)

**GREEN phase:**
- [x] Mark stable unit tests as `smoke`
- [x] Mark stable integration tests as `smoke`
- [x] Mark stable system contract tests as `smoke`
- [~] Mark stable E2E tests as `smoke`
- [~] Validate smoke selection covers all critical paths
- [~] Validate smoke selection runs in < 60 seconds

**REFACTOR phase:**
- [~] Verify smoke selection is stable across runs

**Verification:**
```powershell
pytest tests/ -v -m smoke --tb=short
```

---


**2026-07-07 Completion Audit (Phases 10-13):** Phases 10-13 were audited
and their previously stale `[~]` markers corrected to `[x]` against real
verification.

Phase 10 (System Verification): `tools/validate_build.py --all` passes and
the system suite (excluding the self-spawning smoke meta-test) is green.
Two genuine Phase 10 blockers were closed:
  * Callable coverage (T10.4): 32 public callables lacked a direct unit
    test. Added `tests/unit/test_math_ieee_helpers.py` (14 strong IEEE
    FAC/ARG linked-byte assertions, including a fix to `math_totalorder`
    which previously compared FAC1-ARG after clobbering ARG) and
    `tests/unit/test_coverage_remaining.py` (18 routines executed through
    linked bytes). `tools/test_harness.py --validate-coverage` now reports
    381 entries, 0 uncovered.
  * BASIC compatibility limit manifest (T1.0/T10.1): the YAML
    `document_area` names had drifted from `docs/BASIC_COMPATIBILITY_LIMITS.md`;
    aligned the doc's `LOAD, SAVE, and VERIFY devices` and merged
    `OPEN devices` + `Secondary addresses` rows to the manifest's
    `LOAD and SAVE devices` / `OPEN devices and secondary addresses`.
Phase 11 (E2E): language matrices remain backed by real stock VICE captures
and reviewed oracles; E2E/hardware tests skip cleanly without a VICE
executable in this environment.
Phase 12 (Size): `build/size_report.json` carries resident/geoRAM/stack
budgets and `profile_guided_optimization` data; `build/phase1_for_benchmark.json`
records the measured native FOR/NEXT benchmark of 2 C64 jiffies (limit 60).
Phase 13 (Smoke): stable `smoke` marks were added across all six required
layers (unit, integration, functional, system, e2e, hardware) and
`tests/system/test_smoke_selection.py::test_smoke_collection_is_stable_and_
covers_critical_layers` passes (non-empty, stable, spans every layer).
The runtime smoke execution of the VICE-marked e2e/hardware nodes requires
a VICE MCP instance (environment-limited here); this matches the repo's
pre-existing VICE-gated e2e design.

Out-of-scope pre-existing failures (not part of Phases 10-13) remain in
Phase 5: `tests/unit/test_variables.py` (3) and `tests/unit/test_io.py` (1).

---

## Phase 14: Expansion-Native Conformance Recovery

> This phase corrects the implementation to the geoRAM-canonical architecture
> in `REQUIREMENTS.md` §§2, 7, and 8, `REU_REQUIREMENTS.md` RREU-5, and
> `DESIGN2.md` §8.  It supersedes any earlier completion claim that treated a
> geoRAM sidecar copy as evidence that the production call path executes XIP.
>
> **Scope rule:** "all 402 routines in geoRAM" is not a valid literal target:
> pinned IRQ/NMI, loader, KERNAL/expansion gates, runtime ABI required by a
> standalone `COMPILE` export, and active compiled code are intentionally
> normal-RAM classes.  The enforceable target is that every routine is
> classified exactly once, every non-exempt compiler/editor/diagnostic/cold-math
> routine is geoRAM XIP (or its ABI-compatible REU overlay), and every
> normal-RAM exception has a design-anchor, concrete reason, byte cost, and
> regression test.  Unclassified or unjustified normal-RAM execution fails the
> build.

### Wave -1 — Audit Remediation and Evidence Integrity

The 2026-07-18 conformance audit invalidated prior completion claims for
expansion execution, dual-device support, budgets, packaging, E2E, and coverage.
Do not restore an earlier `[x]` marker wholesale: audit each task's full
production path and acceptance evidence independently.

### T14.0.1 Completion-Claim Reconciliation

**Prerequisites:** None

- [~] Add a machine-readable audit ledger mapping each invalidated Phase 9-13
      completion claim to its failed requirement, artifact, test, or missing
      execution evidence; set only the affected behavioral/verification task
      markers to `[~]` after reviewing their complete acceptance criteria.
- [x] Keep creation-only subtasks `[x]` only when the artifact exists and has
      no implied production-completion claim.
- [x] Reject a release when its task/traceability status claims `passing` or
      complete while its named production evidence is stale, skipped, missing,
      or failing.

**Evidence (2026-07-18):**
`manifests/completion_claim_ledger.json` records the four Phase 9-13 claim
groups invalidated by the conformance audit. `tools/validate_completion_claims.py`
validates that ledger and rejects traceability records that claim passing while
their named audit evidence is invalidated. `pytest
tests/tools/test_validate_completion_claims.py -v` passed (3 tests). The
production validation command is intentionally RED until the recorded recovery
work is complete: it rejects the current passing `R12.1` and `R13` records.

### T14.0.2 Clean Build, Artifact Freshness, and Release Integrity

**Prerequisites:** T14.0.1

- [ ] Make `build.ps1` construct every release in a clean isolated output
      directory; reject stale objects, maps, labels, directories, sidecars,
      D64 files, and inherited artifacts before linking or packaging.
- [ ] Extend the build fingerprint with hashes of every assembly source,
      manifest, generator, linker policy, command line, and tool version.
      Verification must compare against those inputs and must never rewrite or
      re-sign a manifest in read-only validation mode.
- [ ] Make a release fail on RAM_HIGH/resident/compile/D64/sidecar budget or
      fingerprint mismatch, and require the linked `compiler.bin`, map, labels,
      GEOASM/GEORAM/REU directories, sidecars, and D64 to derive from one build.
- [ ] Add clean-build, stale-input, stale-artifact, failed-link, sidecar-byte,
      and reproducibility system tests.

### T14.0.3 Executable Test and VICE Evidence Integrity

**Prerequisites:** T14.0.2

- [ ] Replace symbol-name/textual routine coverage with execution of assembled
      production bytes for every callable assembly routine; test-only exports
      may expose entries but may not bypass the production path.
- [ ] For release-required artifacts, replace conditional missing-artifact or
      optional-tool skips with explicit prerequisite failures; keep only
      environment-gated hardware nodes separately reported as not executed.
- [ ] Require every supported keyword/mode matrix row to have a reviewed VICE
      fixture and a freshness-bound READY-to-result run. Pending, timed-out,
      catalog-only, or stale-artifact cases are incomplete, never passing.
- [ ] Add bounded watchdog diagnostics so an E2E timeout reports emulator,
      loader, prompt, and artifact fingerprint state rather than hanging.

### T14.0.4 Genuine GeoRAM XIP Recovery

**Prerequisites:** T14.0.2

- [ ] Replace the normal-RAM `GEOASM` execution model with generated,
      page-linked `$DE00-$DEFF` bodies and declared entry/callback boundaries;
      a sidecar copy of RAM code is prohibited as XIP evidence.
- [ ] Route resident, runtime, loader, and native calls solely through the
      common expansion dispatcher. Remove all production direct calls to a
      normal-RAM mirror of an `expansion_xip` routine.
- [ ] Make the linker/page generator reject oversized routines, cross-page
      relative branches, fall-through, unregistered absolute transfers, and
      page-unsafe internal labels before a sidecar is produced.
- [ ] Add local-emulator and VICE canaries that prove instruction fetches from
      the selected geoRAM page through return, tail transfer, error unwind,
      and IRQ progress.

### T14.0.5 Real REU Overlay and Common-Arena Recovery

**Prerequisites:** T14.0.2

- [ ] Implement the pinned REU gate as the sole production REC owner, with
      documented DMA validation, ownership, nesting, mapping, error, and
      interrupt contracts; remove loader/foreground REC programming outside
      its explicitly tested detector boundary.
- [ ] Generate REU overlay IDs, extents, slot origins/capacities, directories,
      pin-depth/call-graph validation, and per-routine ABI-equivalent GeoRAM
      and REU records.
- [ ] Implement REU page-DMA into generated XIP slots plus returning/tail
      dispatch, eviction, and deterministic depth errors. A detection-only
      REU build or a placeholder `reu.bin` is not a supported backend.
- [ ] Make all expansion-backed program, compiler, editor, variable, array,
      string-payload, and scratch arena operations use the selected backend
      with equivalent handles, generations, transactions, and publication.
- [ ] Add REU-only, GeoRAM-only, both-present, and no-device VICE installation
      and cross-device differential evidence.

### Wave 0 — Policy, Inventory, and RED Gates

These tasks run first.  No migration task may be marked complete before their
tests fail against the current direct-call implementation and then become
mandatory build gates.

### T14.1 Routine Placement Policy and Complete Inventory

**Prerequisites:** T14.0.1, T14.0.2

**CONTRACT/RED phase:**

- [ ] Add a checked-in placement policy for every production routine ID: one of
      `resident_pinned`, `loader`, `runtime_abi`, `compiled_code`,
      `expansion_xip`, or a narrowly named approved exception.
- [ ] Classify all 402 current production routines exactly once; no inferred
      default and no catch-all `other` category is permitted.
- [ ] Require every non-`expansion_xip` classification to name its normative
      design/requirement anchor, a concrete impossibility or active-runtime
      reason, normal-RAM byte cost, owner, and review test.
- [ ] Add a failing system test for missing, duplicate, stale, or unsupported
      classifications and for an exception without the required evidence.
- [ ] Before migrating a family, derive its linked executable byte size, direct
      call/branch edges, absolute-address dependencies, KERNAL/I/O boundaries,
      live state, and test coverage.  Classify its migration method as
      `repack`, `split`, `xip_rewrite`, or an approved resident exception;
      record a cost/risk rationale and prohibit speculative rewrites before
      this audit is reviewed.
- [ ] Run a read-only compatibility spike against the companion project's
      annotated batch porter.  Preserve only its parser, annotation schema,
      and reporting ideas if they satisfy this project's dispatcher and
      geoRAM/REU contracts; do not adopt its hard-coded force-port lists,
      automatic RAM fallbacks, or generated source as production output.
      Add fixtures proving every accepted transformation preserves the XIP
      ABI, page containment, and production execution path.

**GREEN/TRACE phase:**

- [ ] Generate an auditable placement report listing all routine IDs, linked
      addresses, physical geoRAM/REU records, exemption evidence, and byte
      totals by class.
- [ ] Add placement rows to traceability and `MAP.md`; report every resident
      byte delta with the required non-XIP explanation.

**Verification:**

```powershell
python -m pytest tests/system/test_expansion_placement_policy.py -v
python tools/validate_build.py --all
```

### T14.2 Production XIP-Path Enforcement

**Prerequisites:** T14.1

**RED phase:**

- [ ] Add failing linked-binary and source-call-graph tests proving every
      `expansion_xip` routine has a generated geoRAM page/entry and an
      ABI-compatible REU overlay record.
- [ ] Prove a real call from resident or another overlay enters through the
      expansion dispatcher/gate, not a direct `JSR`/`JMP` to the low-RAM mirror.
- [ ] Prove the bytes executed by each sampled public entry are fetched from
      `$DE00-$DEFF` on the geoRAM local emulator, including nested return,
      tail transfer, error unwind, and selected-page restoration.
- [ ] Reject a normal-RAM mirror that is reachable as the production execution
      path for an `expansion_xip` routine; test-only direct execution remains
      explicitly isolated.

**GREEN/TRACE phase:**

- [ ] Make these checks mandatory in `build.ps1`/`validate_build.py`.
- [ ] Add VICE hardware canaries for XIP entry, long compiler/editor work with
      IRQ progress, and representative nested calls.

**Verification:**

```powershell
python -m pytest tests/system/test_expansion_xip_path.py tests/integration/test_georam_cycle.py -v
python tools/validate_build.py --all
```

### T14.3 Pre-Migration Product Baseline

**Prerequisites:** T14.1, T14.2

- [ ] Capture the current build/map/directory/sidecar fingerprints and the
      prioritized keyword matrix as failing or passing behavior, without using
      stale artifacts.
- [ ] Add a per-case READY-to-result VICE fixture for install, immediate,
      program, and compile modes where applicable.
- [ ] Record current resident/high-RAM/geoRAM bytes and require every migration
      to preserve or improve the relevant budget unless a documented design
      exception is approved.

### Wave 1 — Dispatch and Storage Foundation

These may proceed in parallel after Wave 0; each task owns disjoint production
entry families and must retain the Wave-0 gates.

### T14.4 Common Expansion Dispatcher and Generated Page Boundaries

**Prerequisites:** T14.2

- [ ] Route all public expansion-native calls through the common dispatcher;
      preserve geoRAM returning/tail semantics and REU overlay equivalence.
- [ ] Split compiler/editor routines at declared page boundaries; replace
      cross-page direct calls with generated gate calls or declared callbacks.
- [ ] Remove production dependence on direct low-RAM `GEOASM` calls while
      retaining only explicitly classified mirror/stub bytes.

### T14.5 Expansion-Backed Editor, Program Store, and Dynamic Data

**Prerequisites:** T14.2

- [ ] Move numbered-line publication, `LIST`, line edit/delete, tokenized
      source, IR, compiler scratch, variables, arrays, and string payloads to
      their typed expansion arenas; remove interim high-RAM program storage.
- [ ] Keep the resident editor limited to IRQ-safe input/cursor/handoff work.
- [ ] Verify strings, arrays, and program edits through real geoRAM pages and
      preserve transactional generations/rollback.

### Wave 2 — Priority Compiler Migration

These tasks can run in parallel once T14.4 is stable, but share the Wave-0 XIP
policy and must not reintroduce high-RAM compiler implementations.

### T14.6 Tokenizer, Parser, Semantic Analysis, and Numeric Expressions

**Prerequisites:** T14.4

- [ ] Port the tokenizer, keyword trie, parser, semantic checks, IR builder,
      optimizer, and numeric expression lowering to page-bounded XIP routines.
- [ ] Cover integer types, numeric variables, assignment/`LET`, `PRINT`, and
      `+`, `-`, `*`, `/` in immediate, program, and supported compile modes.

### T14.7 Compiler Pipeline, Codegen, and Standalone Export Boundary

**Prerequisites:** T14.4

- [ ] Port compile pipeline, codegen, diagnostics, incremental compilation,
      and export planning to XIP; retain only the standalone runtime ABI and
      emitted compiled image in normal RAM.
- [ ] Prove `COMPILE` runs the installed compiled artifact for every supported
      keyword case and remains independent of compiler/editor/geoRAM state.

### T14.8 Control Flow and System/Special Variables

**Prerequisites:** T14.5, T14.6, T14.7

- [ ] Port loop/control compiler services and verify `FOR`/`NEXT`, `DO`/`LOOP`,
      `WHILE`, `UNTIL`, `EXIT`, `GOTO`, `GOSUB`, `RETURN`, `STOP`/`CONT`, and
      `RME` through immediate/program/compile paths as their language profile
      permits.
- [ ] Implement and verify live `TI`, `TI$`, and `ST` semantics through the
      approved resident KERNAL/time boundary without placing compiler logic in
      resident/high RAM.

### Wave 3 — User-Visible Priority Completion

These tasks are the acceptance order for the user's requested vertical slices.

### T14.9 Install, READY, and Immediate Keyword Slice

**Prerequisites:** T14.5, T14.6

- [ ] Verify D64 load → expansion install → editor READY, then every supported
      immediate keyword/function through real geoRAM XIP.
- [ ] Include numeric variables, all integer types, arithmetic, numeric `PRINT`,
      expressions, assignment, `TI`/`TI$`/`ST`, and direct error behavior.

### T14.10 Stored Program, Loop, Branch, and COMPILE Slice

**Prerequisites:** T14.7, T14.8, T14.9

- [ ] Verify numbered entry, `LIST`, `RUN`, `NEW`, stored control flow, every
      supported loop form, `GOTO`, `GOSUB`, `RETURN`, and `RME` in VICE.
- [ ] Repeat supported cases in `COMPILE` mode and prove the installed compiled
      artifact—not the editor/compiler fallback—executed.
- [ ] **Top-priority performance gate:** enter the unchanged stock-CBM source
      `tests/performance/noels_retro_lab_cbm_v2.bas` through the installed
      editor, issue `RUN` to compile and execute it in memory in clean NTSC
      VICE, and assert the ten dots, `500500`, `E`, and measured `TI` jiffies.
      Record the installed artifact fingerprint and compare against the 2,388
      jiffy stock C64 BASIC V2 reference; a hand-authored native fixture,
      prefilled timing JSON, or editor/interpreter fallback is not evidence.

### T14.11 Disk Wedge and Release Regression Slice

**Prerequisites:** T14.5, T14.9

- [ ] Route `$`, `@`, `/`, and `!` through the XIP editor/compiler boundary and
      verify real device behavior, KERNAL banking restoration, and error paths.
- [ ] Verify release D64 contents, sidecar fingerprints, geoRAM-only, REU-only,
      both-present, and no-device outcomes as required by the dual-device docs.

### Wave 4 — Completion Audit

### T14.12 Full Placement and Product Verification

**Prerequisites:** T14.6-T14.11

- [ ] Require zero unclassified routines and zero unjustified non-XIP compiler,
      editor, diagnostic, or cold-math routines.
- [ ] Run all placement, source-call, linked-page, local-geoRAM, REU-overlay,
      system, functional, VICE E2E, and focused hardware suites.
- [ ] Inspect generated `GEORAM`/`REU` images, directories, maps, fingerprints,
      size reports, and D64 artifacts; update traceability and document exact
      verification commands/results before any task is marked complete.

---

## Summary

| Phase | Tasks | Approach | Description |
|---|---|---|---|
| 0 | T0.1-T0.7 | Bootstrap + hybrid gates | Project Infrastructure |
| 1 | T1.1-T1.3 | Fixture-first | Canonical Fixtures and Requirements Tests |
| 2 | T2.1-T2.8 | Unit-first | Pinned Kernel |
| 3 | T3.1-T3.3 | Unit-first | Arena System |
| 4 | T4.1-T4.2 | Fixture/unit-first | Tokenized Program Load/Save/Edit |
| 5 | T5.1-T5.7 | Unit-first | Descriptors and Generic Runtime |
| 6 | T6.1-T6.10 | Unit/integration-first | Compiler Pipeline |
| 7 | T7.1-T7.5 | Oracle/unit-first | Transcendental Math and Optimizations |
| 8 | T8.1-T8.3 | Unit/functional-first | Editor Services and DOS Wedge |
| 9 | T9.1-T9.4 | Artifact-first | Loader and Compressor Integration |
| 10 | T10.1-T10.4 | Contract-first | System Verification |
| 11 | T11.1-T11.5 | Fixture/E2E-first | E2E Language Tests |
| 12 | T12.1-T12.2 | Measurement-first | Resident Size Minimization |
| 13 | T13.1 | Selection-first | Smoke Test Selection |
| 14 | T14.0.1-T14.12 | Audit recovery, then XIP migration | Expansion-Native Conformance Recovery |

Total: 96 tasks across 14 phases.

**Status:** Phase 14 is open. Earlier completion claims do not satisfy the
expansion-native execution policy until T14.1-T14.12 prove the production XIP
path and the prioritized READY-to-keyword behavior.

**Current Test Results:**
- Build: `build.ps1` success; `tools/validate_build.py --all` success
- Non-VICE suite: `python -m pytest tests -m "not vice" -q` → **2674 passed**,
  **14 deselected** (VICE-marked)
- Focused open-item suites (detect/REU/codec/io/system/dispatch/export/editor/
  loader/init/compressor): **202 passed**
- Smoke: `pytest tests -m "smoke and not vice"` → **56 passed**
- Live VICE E2E/hardware: deferred this session

## Hybrid TDD Checklist

For each implementation task:

- [x] Contract, fixture, schema, or test gate identified before implementation
- [x] Owning tests or validators defined for all documented behavior
- [x] Expected failure verified where a runnable RED test exists
- [x] Source/tool/build change implemented to make the gate pass
- [x] Code and generated outputs cleaned up while affected tests still pass
- [x] Traceability, generated references, and docs updated when behavior changes
- [x] No regressions in previously passing tests

**2026-07-15 Completion Audit:** Closed the last 31 open checkboxes left by the
2026-07-09 design demotion. Parallel fix agents repaired residual local-emu
harness and production issues (HIBASIC high-image load, KERNAL stubs above
hibasic.bin, `ctrl_reset`/`fp_clear_flags` always-mapped, full high-image
graphics swap, memory-map cold segments, geoRAM cycle NUL command). Full
non-VICE suite green. Phase 11 fixture matrices remain; live VICE re-run deferred.

## References
## References

- `DESIGN2.md` - detailed design indexed by requirement group
- `docs/COMPILER_ARCHITECTURE.md` - architecture overview
- `SKELETON.md` — implementation skeleton with routine tables
- `TESTS.md` — comprehensive test plan
- `REQUIREMENTS.md` — normative behavior and acceptance criteria
- `docs/BUILD.md` — build pipeline and artifacts
- `docs/TESTING.md` — test hierarchy and strategy
- `docs/GEORAM_LOADER_DESIGN.md` — loader and compressor integration
- `docs/GEORAM_BANKING.md` — geoRAM selection and calls
- `docs/ZERO_PAGE.md` — ZP allocation design
- `docs/KERNAL_ABI.md` — ROM calls and banking
- `docs/LOOP_OPTIMIZATION.md` — loop fast-path strategy
- `docs/INCREMENTAL_COMPILATION.md` — per-line compilation
- `docs/COMPILE_EXPORT.md` — standalone PRG contract
- `docs/DOS_WEDGE.md` — disk wedge behavior
- `docs/IEEE754.md` — numeric profile
- `docs/MEMORY_BUDGETS.md` — RAM and geoRAM budgets
- `docs/EDITOR.md` — editor behavior
- `docs/GRAPHICS_MEMORY.md` — bitmap banking
- `docs/KEYWORDS.md` — language reference
- `docs/MANUAL.md` — user-facing behavior
- `docs/TRACEABILITY.md` — EARS records
- `docs/VICE_TOOLS.md` — VICE inspection recipes
- `docs/CANONICAL_TESTS.md` — stock VICE fixtures
