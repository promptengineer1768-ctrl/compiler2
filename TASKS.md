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

- [ ] Create `manifests/zero_page.json` — ZP nodes, fixed constraints, lifetimes
- [ ] Create `manifests/routines.json` — public/test entries, ABI, calls, return kind
- [ ] Create `manifests/arenas.json` — arena types, schemas, ownership, reset rules
- [ ] Create `manifests/commands.json` — dialect tokens and direct/program classification
- [ ] Create `manifests/program_formats.json` — stock and extended token/file schemas
- [ ] Create `manifests/linker_policy.json` — fixed banking, reservations, segments
- [ ] Create `manifests/runtime_abi.json` — compiled-code-only stable surface
- [ ] Create `manifests/traceability.json` — EARS requirement-to-design/test records

**Verification:**
```powershell
python tools/validate_build.py --manifests
```

### T0.3 Zero-Page Graph Coloring

**Prerequisites:** T0.2

- [ ] Create `tools/zp_alloc.py` — graph-coloring allocator
- [ ] Generate `build/zp_symbols.inc` from `manifests/zero_page.json`
- [ ] Generate `build/zp_allocation.json` — machine-readable ZP allocation
- [ ] Generate `build/zp_allocation.md` — human-readable report
- [ ] Generate `build/zp_interference.dot` — interference graph
- [ ] Validate no ZP address conflicts
- [ ] Validate all routine clobber lists satisfied

**Verification:**
```powershell
python tools/zp_alloc.py
python -c "import json; d=json.load(open('build/zp_allocation.json')); assert d['valid']
```

### T0.4 geoRAM Page Placement

**Prerequisites:** T0.3

- [ ] Create `tools/georam_pages.py` — page placement and call directory
- [ ] Generate `build/routine_directory.json` — routine ID to placement
- [ ] Generate call directory for each 256-routine group
- [ ] Validate no routine crosses `$DEFF` page boundary
- [ ] Validate all routine IDs unique and complete

**Verification:**
```powershell
python tools/georam_pages.py
python tools/validate_build.py --routine-directory
```

### T0.5 Generated Contracts

**Prerequisites:** T0.4

- [ ] Create `tools/generate_contracts.py` — ABI, arena, command, format exports
- [ ] Generate `build/runtime_abi.json`
- [ ] Generate `build/arena_layout.json`
- [ ] Generate `build/production_entries.json` and `build/test_entries.json`
- [ ] Generate `build/keyword_lookup_report.json`
- [ ] Validate all generated contracts consistent

**Verification:**
```powershell
python tools/generate_contracts.py
python tools/validate_build.py --contracts
```

### T0.6 Linker Configuration

**Prerequisites:** T0.5

- [ ] Create `tools/linker_config.py` — ld65 config from policy + generated segments
- [ ] Create `manifests/linker_policy.json` with fixed banking, segments
- [ ] Generate `build/compiler.cfg` — final ld65 configuration
- [ ] Validate no segment overlaps
- [ ] Validate NMI/RESET/IRQ vectors at `$FFFA-$FFFF`

**Verification:**
```powershell
python tools/linker_config.py
python tools/validate_build.py --linker
```

### T0.6a Host Tool Test Skeletons

**Prerequisites:** T0.6

**CONTRACT phase:**
- [ ] Map every `SKELETON.md` section 7 tool function to a `TESTS.md` Host Tool Tests row
- [ ] Define fixture directories under `tests/fixtures/tools/`
- [ ] Define generated-output comparison rules that ignore timestamps and host paths

**RED phase:**
- [ ] Create `tests/tools/test_zp_alloc.py`
- [ ] Create `tests/tools/test_georam_pages.py`
- [ ] Create `tests/tools/test_generate_contracts.py`
- [ ] Create `tests/tools/test_linker_config.py`
- [ ] Create `tests/tools/test_extract_segments.py`
- [ ] Create `tests/tools/test_prepare_compressor_segments.py`
- [ ] Create `tests/tools/test_package_d64.py`
- [ ] Create `tests/tools/test_validate_build.py`
- [ ] Create `tests/tools/test_test_harness.py`
- [ ] Create `tests/tools/test_generate_reference.py`
- [ ] Verify the tests fail against missing or stubbed behavior

**GREEN phase:**
- [ ] Implement only the tool behavior needed for the fixture-backed tests
- [ ] Wire tool tests into pytest collection without requiring VICE

**REFACTOR phase:**
- [ ] Run `ruff`, `black --check`, and `mypy --strict` on `tools/` and `tests/`
- [ ] Verify tool tests still pass

**Verification:**
```powershell
pytest tests/tools/ -v
ruff check tools/ tests/
black --check tools/ tests/
python -m mypy tools/ tests/ --strict
```

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

### T1.1 Stock BASIC V2 Reference Fixtures

**Prerequisites:** T0.7

**RED phase:**
- [ ] Create `tests/fixtures/reference/` directory structure
- [ ] Define fixture schema (JSON format for VICE observations)
- [ ] Create empty fixture files for each BASIC V2 test case

**GREEN phase:**
- [ ] Generate stock C64 BASIC V2 immediate-mode reference fixtures using VICE
- [ ] Generate stock C64 BASIC V2 program-mode reference fixtures using VICE
- [ ] Record VICE executable version and ROM checksums in fixtures
- [ ] Validate fixtures match `c64rom` source-derived expectations

**Verification:**
```powershell
python tools/test_harness.py --generate-reference basicv2
pytest tests/fixtures/reference/ -v
```

### T1.2 Stock BASIC V3.5 Reference Fixtures

**Prerequisites:** T1.1

**RED phase:**
- [ ] Create Plus/4 VICE machine configuration
- [ ] Define Plus/4 fixture schema

**GREEN phase:**
- [ ] Generate Plus/4 BASIC V3.5 immediate-mode reference fixtures
- [ ] Generate Plus/4 BASIC V3.5 program-mode reference fixtures
- [ ] Validate fixtures against Plus/4 ROM semantics

**Verification:**
```powershell
python tools/test_harness.py --generate-reference basicv35
pytest tests/fixtures/reference/ -v -k "basicv35"
```

### T1.3 Requirements Traceability Matrix

**Prerequisites:** T0.2, T1.1

**RED phase:**
- [ ] Create `tests/system/test_traceability.py` — traceability tests
- [ ] Define expected requirement-to-test mappings

**GREEN phase:**
- [ ] Create `tools/generate_reference.py` — API.md and MAP.md generator
- [ ] Generate `build/requirements_matrix.json`
- [ ] Generate `build/requirements_matrix.md`
- [ ] Validate every requirement maps to at least one test
- [ ] Validate every test maps to at least one requirement

**Verification:**
```powershell
python tools/generate_reference.py
python tools/validate_build.py --traceability
```

---

## Phase 2: Pinned Kernel — IRQ, KERNAL, CPU-Port, geoRAM Gates

> Build the resident foundation. **Test-first** for each routine.

### T2.1 RAM-Under-I/O Gate

**Prerequisites:** T0.3, T0.6

**RED phase:**
- [ ] Create `tests/unit/test_ram_under_io.py`
- [ ] Define test cases for enter/exit/copy operations
- [ ] Add test-only exports to `manifests/test_entries.json`
- [ ] Verify tests fail (no implementation yet)

**GREEN phase:**
- [ ] Create `src/resident/ram_under_io.asm`
- [ ] Implement `ram_under_io_enter` — select all-RAM mapping, mask IRQ
- [ ] Implement `ram_under_io_exit` — restore `$35`, restore IRQ state
- [ ] Implement `ram_under_io_copy_in` — bounded chunk copy into `$D000-$DFFF`
- [ ] Implement `ram_under_io_copy_out` — bounded chunk copy from `$D000-$DFFF`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions in previously passing tests

**Verification:**
```powershell
python tools/validate_build.py --assembled
pytest tests/unit/test_ram_under_io.py -v
```

### T2.2 KERNAL Bridge

**Prerequisites:** T2.1

**RED phase:**
- [ ] Create `tests/unit/test_kernal_bridge.py`
- [ ] Define test cases for each bridge routine (§6.5 SKELETON.md)
- [ ] Define test cases for banking save/restore
- [ ] Define test cases for IRQ state preservation
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/resident/kernal_bridge.asm`
- [ ] Implement all KERNAL bridge routines
- [ ] Implement `$01` save/restore for each bridge call
- [ ] Implement IRQ state save/restore across blocking calls

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_kernal_bridge.py -v
```

### T2.3 Pinned IRQ Handler

**Prerequisites:** T2.2

**RED phase:**
- [ ] Create `tests/unit/test_irq.py`
- [ ] Define test cases for IRQ entry/exit
- [ ] Define test cases for jiffy advance
- [ ] Define test cases for cursor blink
- [ ] Define test cases for keyboard scan
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/resident/irq.asm`
- [ ] Implement `irq_entry` — save A/X/Y/mapping, call UDTIM, cursor, SCNKEY
- [ ] Implement `irq_update_jiffy` — call KERNAL UDTIM
- [ ] Implement `irq_cursor_blink` — toggle cursor visibility
- [ ] Implement `irq_scan_keyboard` — call KERNAL SCNKEY
- [ ] Implement `irq_restore_mapping` — restore `$01` and P before RTI

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_irq.py -v
```

### T2.4 Screen/Cursor Front End

**Prerequisites:** T2.1

**RED phase:**
- [ ] Create `tests/unit/test_screen.py`
- [ ] Define test cases for each screen operation (§6.4 SKELETON.md)
- [ ] Define test cases for cursor movement and wrapping
- [ ] Define test cases for line input with quote mode
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/resident/screen.asm`
- [ ] Implement all screen routines
- [ ] Implement bounded line capture with quote mode

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_screen.py -v
```

### T2.5 geoRAM Detection

**Prerequisites:** T0.4

**RED phase:**
- [ ] Create `tests/unit/test_georam_detect.py`
- [ ] Define test cases for detection with geoRAM present
- [ ] Define test cases for detection with geoRAM absent
- [ ] Define test cases for undersized geoRAM
- [ ] Define test cases for state save/restore round-trip
- [ ] Define test cases for capacity detection
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/arena/georam_detect.asm`
- [ ] Implement `detect_georam` — non-destructive probe
- [ ] Implement `detect_save_state` / `detect_restore_state`
- [ ] Implement `detect_probe_pattern1` / `detect_probe_pattern2`
- [ ] Implement `detect_probe_aliasing` — capacity detection
- [ ] Implement `detect_check_minimum` — 512 KiB threshold
- [ ] Implement `detect_publish_profile` — install profile
- [ ] Implement `detect_validate_profile` — session integrity

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_georam_detect.py -v -k "local"
```

### T2.6 geoRAM Gate and Context Stack

**Prerequisites:** T2.5

**RED phase:**
- [ ] Create `tests/unit/test_georam_gate.py`
- [ ] Define test cases for select writes correct registers
- [ ] Define test cases for context push/pop round-trip
- [ ] Define test cases for nested calls preserve caller state
- [ ] Define test cases for handle-based operations with validation
- [ ] Create `tests/integration/test_georam_cycle.py`
- [ ] Define integration test for full geoRAM call cycle
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/resident/georam_gate.asm`
- [ ] Create `src/arena/context_stack.asm`
- [ ] Implement `georam_select` — write `$DFFE`/`$DFFF`, update mirror
- [ ] Implement `georam_ctx_push` / `georam_ctx_pop` — context save/restore
- [ ] Implement `georam_call_group_n` — generated group dispatch
- [ ] Implement `georam_tail_group_n` — tail transfer
- [ ] Implement handle-based read/write/copy routines
- [ ] Implement `georam_checksum` and `georam_verify_mirror`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify all integration tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_georam_gate.py -v -k "georam"
pytest tests/integration/test_georam_cycle.py -v
```

### T2.7 Fatal Error Path

**Prerequisites:** T2.6

**RED phase:**
- [ ] Create `tests/unit/test_fatal.py`
- [ ] Define test cases for fatal path restores machine state
- [ ] Define test cases for fatal path reports failure
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/resident/fatal.asm`
- [ ] Implement `fatal_georam` — clean failure path
- [ ] Implement `fatal_restore_machine` — shared bounded cleanup

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_fatal.py -v
```

### T2.8 Resident Main Loop

**Prerequisites:** T2.4, T2.6

**RED phase:**
- [ ] Create `tests/unit/test_resident_main.py`
- [ ] Define test cases for input capture and dispatch
- [ ] Define test cases for boundary assertions
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/resident/resident_main.asm`
- [ ] Implement `resident_main` — READY/editor loop
- [ ] Implement `resident_poll_input` — foreground GETIN
- [ ] Implement `resident_submit_line` — transactional handoff
- [ ] Implement `resident_assert_boundary` — debug assertions

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_resident_main.py -v
```

---

## Phase 3: Arena System — Page Allocator, Directory, Handles

> Build the geoRAM memory management layer. **Test-first.**

### T3.1 Page Allocator

**Prerequisites:** T2.5, T2.6

**RED phase:**
- [ ] Create `tests/unit/test_page_alloc.py`
- [ ] Define test cases for allocation and deallocation
- [ ] Define test cases for fragmentation handling
- [ ] Define test cases for bounds checking
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/arena/page_alloc.asm`
- [ ] Implement `page_alloc_init` — initialize free-page bitmap
- [ ] Implement `page_alloc` — allocate pages from free bitmap
- [ ] Implement `page_free` — return pages to free bitmap
- [ ] Implement `page_alloc_count` / `page_alloc_largest`
- [ ] Implement `page_check_in_range` — bounds check

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_page_alloc.py -v -k "georam"
```

### T3.2 Arena Core

**Prerequisites:** T3.1

**RED phase:**
- [ ] Create `tests/unit/test_arena_core.py`
- [ ] Define test cases for arena lifecycle
- [ ] Define test cases for integrity detection
- [ ] Define test cases for generation tracking
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/arena/arena_core.asm`
- [ ] Implement `arena_init_all` — construct arena directory
- [ ] Implement `arena_create` / `arena_destroy`
- [ ] Implement `arena_check_integrity` — canary, checksum, generation
- [ ] Implement `arena_reset` — deterministic reset with generation bump
- [ ] Implement `arena_get_handle` / `arena_handle_valid`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_arena_core.py -v -k "georam"
```

### T3.3 Overlay Dispatch

**Prerequisites:** T3.2

**RED phase:**
- [ ] Create `tests/unit/test_overlay.py`
- [ ] Define test cases for overlay swap cycle
- [ ] Define test cases for routine resolution
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/arena/overlay_dispatch.asm`
- [ ] Implement `overlay_enter` / `overlay_exit`
- [ ] Implement `overlay_resolve` — routine ID to page/offset
- [ ] Implement `overlay_validate` — directory integrity

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_overlay.py -v -k "georam"
```

---

## Phase 4: Tokenized Program Load/Save/Edit

> Implement the transactional program store. **Test-first.**

### T4.1 Program Codec

**Prerequisites:** T2.2, T3.2

**RED phase:**
- [ ] Create `tests/unit/test_program_codec.py`
- [ ] Define test cases for stock format decode/encode round-trip
- [ ] Define test cases for extended format decode/encode round-trip
- [ ] Define test cases for malformed input rejection
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/program_codec.asm`
- [ ] Implement `program_classify_file` — stock vs extended
- [ ] Implement `program_decode_stock` — BASIC V2 import
- [ ] Implement `program_encode_stock` — canonical BASIC V2 export
- [ ] Implement `program_decode_extended` — versioned extension import
- [ ] Implement `program_encode_extended` — extension export

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_program_codec.py -v
```

### T4.2 Program Store

**Prerequisites:** T4.1, T3.2

**RED phase:**
- [ ] Create `tests/unit/test_program_store.py`
- [ ] Define test cases for transaction commit and rollback
- [ ] Define test cases for atomic publication
- [ ] Create `tests/integration/test_program_lifecycle.py`
- [ ] Define integration test for LOAD/SAVE round-trip
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/program_store.asm`
- [ ] Implement `program_tx_begin` — start transaction
- [ ] Implement `program_tx_put_line` / `program_tx_delete_line`
- [ ] Implement `program_tx_commit` — atomic publish
- [ ] Implement `program_tx_abort` — rollback
- [ ] Implement `program_replace_from_load` — transactional LOAD

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify all integration tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_program_store.py -v
pytest tests/integration/test_program_lifecycle.py -v
```

---

## Phase 5: Descriptors and Generic Runtime

> Implement the minimal correct runtime. **Test-first.**

### T5.1 Variable Descriptors

**Prerequisites:** T3.2, T0.5

**RED phase:**
- [ ] Create `tests/unit/test_variables.py`
- [ ] Define test cases for each load/store operation
- [ ] Define test cases for type promotion and coercion
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/variables.asm`
- [ ] Implement `var_resolve` — descriptor to address
- [ ] Implement `var_load_int` / `var_store_int`
- [ ] Implement `var_load_float` / `var_store_float`
- [ ] Implement `var_load_string` / `var_store_string`
- [ ] Implement `var_promote_to_float` / `var_coerce`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_variables.py -v
```

### T5.2 Array Descriptors

**Prerequisites:** T5.1

**RED phase:**
- [ ] Create `tests/unit/test_arrays.py`
- [ ] Define test cases for DIM and element access
- [ ] Define test cases for bounds checking
- [ ] Define test cases for REDIM'D ARRAY error
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/arrays.asm`
- [ ] Implement `arr_dim` — allocation
- [ ] Implement `arr_resolve_element` — bounds check and offset
- [ ] Implement `arr_load_element` / `arr_store_element`
- [ ] Implement `arr_redim` / `arr_free`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_arrays.py -v
```

### T5.3 String Operations

**Prerequisites:** T5.1

**RED phase:**
- [ ] Create `tests/unit/test_strings.py`
- [ ] Define test cases for each string operation
- [ ] Define test cases for stock-compatible PETSCII behavior
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/strings.asm`
- [ ] Implement `str_alloc` / `str_free`
- [ ] Implement `str_assign` / `str_copy` / `str_concat`
- [ ] Implement `str_left` / `str_right` / `str_mid`
- [ ] Implement `str_len` / `str_cmp`
- [ ] Implement `str_chr` / `str_asc` / `str_val` / `str_str`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_strings.py -v
```

### T5.4 Math Core

**Prerequisites:** T0.3

**RED phase:**
- [ ] Create `tests/unit/test_math_core.py`
- [ ] Define test cases for each arithmetic operation
- [ ] Define test cases for stock BASIC V2 numeric compatibility
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/math_core.asm`
- [ ] Implement `math_add` / `math_sub` / `math_mul` / `math_div`
- [ ] Implement `math_negate` / `math_cmp`
- [ ] Implement `math_int` / `math_sgn` / `math_abs` / `math_fpe`
- [ ] Implement `math_int_to_float` / `math_float_to_int`
- [ ] Implement integer arithmetic: `math_add_int` / `math_sub_int` / `math_mul_int` / `math_div_int`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_math_core.py -v
```

### T5.5 Control Flow

**Prerequisites:** T5.1, T5.4

**RED phase:**
- [ ] Create `tests/unit/test_control.py`
- [ ] Define test cases for FOR/NEXT cycle
- [ ] Define test cases for DO/LOOP cycle
- [ ] Define test cases for GOSUB/RETURN cycle
- [ ] Define test cases for STOP/CONT state machine
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/control.asm`
- [ ] Implement `ctrl_for_init` / `ctrl_for_next`
- [ ] Implement `ctrl_do_init` / `ctrl_loop_test` / `ctrl_exit_loop`
- [ ] Implement `ctrl_gosub` / `ctrl_return`
- [ ] Implement `ctrl_on_goto` / `ctrl_on_gosub`
- [ ] Implement `ctrl_stop` / `ctrl_end` / `ctrl_cont`
- [ ] Implement `ctrl_check_stop`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_control.py -v
```

### T5.6 I/O and Errors

**Prerequisites:** T2.2, T5.4

**RED phase:**
- [ ] Create `tests/unit/test_io.py`
- [ ] Create `tests/unit/test_errors.py`
- [ ] Define test cases for PRINT formatting
- [ ] Define test cases for INPUT prompt and read
- [ ] Define test cases for LOAD/SAVE through KERNAL
- [ ] Define test cases for error formatting and unwind
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/io.asm`
- [ ] Create `src/runtime/runtime_io.asm`
- [ ] Create `src/runtime/errors.asm`
- [ ] Implement `io_print_value` / `io_print_newline` / `io_print_space`
- [ ] Implement `io_input_value` / `io_input_string` / `io_get`
- [ ] Implement `rio_load` / `rio_save` / `rio_verify`
- [ ] Implement `rio_open` / `rio_close` / `rio_chrin` / `rio_chrout`
- [ ] Implement `err_raise` / `err_from_kernal` / error shortcuts

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_io.py -v
pytest tests/unit/test_errors.py -v
```

### T5.7 System Primitives

**Prerequisites:** T2.1, T2.2

**RED phase:**
- [ ] Create `tests/unit/test_system.py`
- [ ] Define test cases for PEEK/POKE with protected ranges
- [ ] Define test cases for TI/TI$ read and write
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/system.asm`
- [ ] Implement `system_peek` / `system_poke` with protection
- [ ] Implement `system_sys` / `system_usr`
- [ ] Implement `system_wait`
- [ ] Implement `system_ti_load` / `system_ti_store`
- [ ] Implement `system_ti_string_load` / `system_ti_string_store`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_system.py -v
```

---

## Phase 6: Compiler Pipeline and Native Code Publication

> Implement the eight-boundary compiler. **Test-first for each boundary.**

### T6.1 Tokenizer

**Prerequisites:** T0.5

**RED phase:**
- [ ] Create `tests/unit/test_tokenizer.py`
- [ ] Define test cases for each token type
- [ ] Define test cases for dialect filtering
- [ ] Define test cases for abbreviation handling
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/tokenizer.asm`
- [ ] Implement `token_init` / `token_next` / `token_peek`
- [ ] Implement `token_identifier` — first-character trie traversal
- [ ] Implement `token_number` / `token_string`
- [ ] Implement `token_skip_whitespace` / `token_rem` / `token_data`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_tokenizer.py -v
```

### T6.2 Parser

**Prerequisites:** T6.1, T5.1, T5.4, T5.5

**RED phase:**
- [ ] Create `tests/unit/test_parser.py`
- [ ] Define test cases for statement parsing
- [ ] Define test cases for expression precedence
- [ ] Define test cases for function and array parsing
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/parser.asm`
- [ ] Implement `parse_line` / `parse_statement`
- [ ] Implement `parse_expression` / `parse_primary`
- [ ] Implement `parse_comparison` / `parse_term` / `parse_factor`
- [ ] Implement `parse_function_call` / `parse_array_ref`
- [ ] Implement `parse_for` / `parse_gosub`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_parser.py -v
```

### T6.3 Semantic Analysis

**Prerequisites:** T6.1, T0.5

**RED phase:**
- [ ] Create `tests/unit/test_semantic.py`
- [ ] Define test cases for dialect validation
- [ ] Define test cases for direct/program classification
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/semantic.asm`
- [ ] Implement `semantic_validate_dialect`
- [ ] Implement `semantic_classify_direct`
- [ ] Implement `semantic_validate_line`
- [ ] Implement `semantic_check_for_dialect` / `semantic_set_dialect`
- [ ] Implement `semantic_get_numeric_mode` / `semantic_set_numeric_mode`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_semantic.py -v
```

### T6.4 IR Builder

**Prerequisites:** T6.2

**RED phase:**
- [ ] Create `tests/unit/test_ir_builder.py`
- [ ] Define test cases for each IR emission operation
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/ir_builder.asm`
- [ ] Implement `ir_init` / `ir_finish_line`
- [ ] Implement `ir_emit_stmt` / `ir_emit_expr`
- [ ] Implement `ir_emit_var_ref` / `ir_emit_array_ref` / `ir_emit_string_ref`
- [ ] Implement `ir_emit_branch` / `ir_emit_loop`
- [ ] Implement `ir_emit_literal_int` / `ir_emit_literal_float` / `ir_emit_literal_str`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_ir_builder.py -v
```

### T6.5 Optimizer

**Prerequisites:** T6.4, T0.5

**RED phase:**
- [ ] Create `tests/unit/test_optimizer.py`
- [ ] Define test cases for fast-path eligibility
- [ ] Define test cases for invalidation detection
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/optimizer.asm`
- [ ] Implement `opt_run_passes`
- [ ] Implement `opt_build_effect_summaries`
- [ ] Implement `opt_eligible_for_for_fast` / `opt_eligible_for_do_fast`
- [ ] Implement `opt_check_invalidation` / `opt_check_aliasing`
- [ ] Implement `opt_propagate_dirty` / `opt_select_branch_polarity`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_optimizer.py -v
```

### T6.6 Code Generator

**Prerequisites:** T6.5, T5.1, T5.4, T5.5

**RED phase:**
- [ ] Create `tests/unit/test_codegen.py`
- [ ] Define test cases for each codegen operation
- [ ] Create `tests/integration/test_compile_pipeline.py`
- [ ] Define integration test for full compile pipeline
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/codegen.asm`
- [ ] Implement `codegen_init` / `codegen_finish_line`
- [ ] Implement `codegen_emit_stmt`
- [ ] Implement `codegen_emit_for_fast` / `codegen_emit_for_generic`
- [ ] Implement `codegen_emit_do_fast` / `codegen_emit_do_generic`
- [ ] Implement `codegen_emit_if` / `codegen_emit_gosub` / `codegen_emit_return`
- [ ] Implement `codegen_emit_on` / `codegen_emit_print` / `codegen_emit_input`
- [ ] Implement `codegen_emit_let` / `codegen_emit_dim` / `codegen_emit_data`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify all integration tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_codegen.py -v
pytest tests/integration/test_compile_pipeline.py -v
```

### T6.7 Direct Dispatch

**Prerequisites:** T6.3, T0.5

**RED phase:**
- [ ] Create `tests/unit/test_direct_dispatch.py`
- [ ] Define test cases for wedge prefix detection
- [ ] Define test cases for command classification
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/direct_dispatch.asm`
- [ ] Implement `direct_probe_prefix` — wedge detection
- [ ] Implement `direct_classify` — direct/program policy
- [ ] Implement `direct_execute_command`
- [ ] Implement `direct_execute_temporary` — immediate compiler path

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_direct_dispatch.py -v
```

### T6.8 Compiler Pipeline Coordinator

**Prerequisites:** T6.1-T6.7

**RED phase:**
- [ ] Create `tests/integration/test_compiler_pipeline.py`
- [ ] Define integration test for full pipeline with all eight boundaries
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/compiler_pipeline.asm`
- [ ] Implement `pipeline_compile_line` — per-line compile
- [ ] Implement `pipeline_compile_program` — whole-program compile
- [ ] Implement `pipeline_serialize_boundary` / `pipeline_validate_boundary`
- [ ] Implement `pipeline_report_failure`

**REFACTOR phase:**
- [ ] Verify all integration tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/integration/test_compiler_pipeline.py -v
```

### T6.9 Incremental Compilation

**Prerequisites:** T6.8, T4.2

**RED phase:**
- [ ] Create `tests/unit/test_incremental.py`
- [ ] Create `tests/integration/test_incremental_compile.py`
- [ ] Define test cases for fingerprint computation
- [ ] Define test cases for dirty marking and resolution
- [ ] Define integration test for incremental line entry
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/incremental.asm`
- [ ] Implement `incremental_fingerprint`
- [ ] Implement `incremental_mark_dependents`
- [ ] Implement `incremental_resolve_dirty`
- [ ] Implement `incremental_publish`
- [ ] Implement `incremental_can_run` / `incremental_abort`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify all integration tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_incremental.py -v
pytest tests/integration/test_incremental_compile.py -v
```

### T6.10 Diagnostics

**Prerequisites:** T6.2, T2.4

**RED phase:**
- [ ] Create `tests/unit/test_diagnostics.py`
- [ ] Define test cases for error formatting
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/diagnostics.asm`
- [ ] Implement `diag_format_error` / `diag_format_warning`
- [ ] Implement `diag_format_source_context`
- [ ] Implement `diag_print_error`
- [ ] Implement `diag_error_from_kernal`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_diagnostics.py -v
```

---

## Phase 7: Transcendental Math and Optimizations

> Add performance optimizations. **Test-first with oracle values.**

### T7.1 Transcendental Math

**Prerequisites:** T5.4, T0.4

**RED phase:**
- [ ] Create `tests/unit/test_math_trig.py`
- [ ] Create `tests/unit/test_math_trans.py`
- [ ] Locate legacy trig/transcendental/IEEE source and Python proxy accuracy tests
- [ ] Define test cases for each transcendent against stock BASIC V2 values
- [ ] Define test cases for IEEE functions against oracle
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/math_trig.asm`
- [ ] Create `src/geoasm/math_trans.asm`
- [ ] Port reusable legacy math kernels where they fit Compiler 2 ABI/ZP/geoRAM contracts
- [ ] Implement `math_sin` / `math_cos` / `math_tan` / `math_atn` / `math_acs` / `math_asn`
- [ ] Implement `math_log` / `math_exp` / `math_sqr` / `math_pow` / `math_rnd`
- [ ] Implement IEEE extensions: `math_fma`, `math_remain`, `math_min`, `math_max`
- [ ] Implement IEEE classification: `math_isnan`, `math_isinf`, `math_isfin`, etc.
- [ ] Implement `math_bin32str` / `math_val32`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify ported code no longer depends on legacy fixed addresses or memory map
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_math_trig.py -v -k "georam"
pytest tests/unit/test_math_trans.py -v -k "georam"
```

### T7.2 IEEE State

**Prerequisites:** T0.5

**RED phase:**
- [ ] Create `tests/unit/test_ieee_state.py`
- [ ] Define test cases for mode switching
- [ ] Define test cases for flag behavior
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/ieee_state.asm`
- [ ] Implement `fp_get_mode` / `fp_set_mode`
- [ ] Implement `fp_get_flags` / `fp_clear_flags`
- [ ] Implement `fp_set_rounding` / `fp_test_flags`
- [ ] Implement `fp_load_constant`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_ieee_state.py -v
```

### T7.3 Data Stream

**Prerequisites:** T5.5

**RED phase:**
- [ ] Create `tests/unit/test_data.py`
- [ ] Define test cases for READ advances cursor
- [ ] Define test cases for RESTORE resets cursor
- [ ] Define test cases for generation-checked reads
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/data.asm`
- [ ] Implement `data_read` / `data_restore` / `data_reset`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_data.py -v
```

### T7.4 Inspection Shell

**Prerequisites:** T5.6, T6.7

**RED phase:**
- [ ] Create `tests/unit/test_inspection.py`
- [ ] Define test cases for each inspection command
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/inspection.asm`
- [ ] Implement `inspect_shell` — REPL loop
- [ ] Implement `inspect_parse_command`
- [ ] Implement `inspect_print_var` / `inspect_print_string_var`
- [ ] Implement `inspect_cont` / `inspect_list_loader`
- [ ] Implement `inspect_run` / `inspect_load` / `inspect_save` / `inspect_verify`
- [ ] Implement `inspect_clr` / `inspect_wedge`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_inspection.py -v
```

### T7.5 COMPILE Export

**Prerequisites:** T6.9, T5.6

**RED phase:**
- [ ] Create `tests/unit/test_compile_export.py`
- [ ] Create `tests/functional/test_compile_export.py`
- [ ] Define test cases for standalone PRG generation
- [ ] Define functional test for COMPILE produces runnable PRG
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/compile_export.asm`
- [ ] Implement `export_parse_command`
- [ ] Implement `export_collect_dependencies`
- [ ] Implement `export_link_image`
- [ ] Implement `export_check_budgets`
- [ ] Implement `export_write_prg`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify all functional tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_compile_export.py -v
pytest tests/functional/test_compile_export.py -v
```

---

## Phase 8: Editor Services and DOS Wedge

> Port editor services and DOS wedge. **Test-first.**

### T8.1 Editor Service

**Prerequisites:** T4.2, T6.1, T6.2

**RED phase:**
- [ ] Create `tests/unit/test_editor_svc.py`
- [ ] Create `tests/functional/test_editor.py`
- [ ] Define test cases for line entry and deletion
- [ ] Define test cases for LIST output
- [ ] Define functional test for full editor interaction
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/editor_svc.asm`
- [ ] Implement `editor_submit_line` — transactional submission
- [ ] Implement `editor_delete_line` — deletion with repair
- [ ] Implement `editor_detokenize_line` — LIST conversion
- [ ] Implement `editor_list_range` — range listing
- [ ] Implement `editor_ready_transition` — READY state

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify all functional tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_editor_svc.py -v
pytest tests/functional/test_editor.py -v
```

### T8.2 DOS Wedge

**Prerequisites:** T2.2, T5.6

**RED phase:**
- [ ] Create `tests/unit/test_dos_wedge.py`
- [ ] Create `tests/functional/test_dos_wedge.py`
- [ ] Define test cases for each wedge command
- [ ] Define functional tests for `$` directory, `/` load, `@` status
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/geoasm/dos_wedge.asm`
- [ ] Create `src/runtime/wedge.asm`
- [ ] Implement `wedge_parse` — prefix parser
- [ ] Implement `wedge_dispatch_development` — development dispatcher
- [ ] Implement `wedge_format_directory`
- [ ] Implement `wedge_directory` / `wedge_load_absolute`
- [ ] Implement `wedge_status_or_command` / `wedge_stream_seq`
- [ ] Implement `wedge_confirm_destructive`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify all functional tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_dos_wedge.py -v
pytest tests/functional/test_dos_wedge.py -v
```

### T8.3 Graphics

**Prerequisites:** T2.1, T5.6

**RED phase:**
- [ ] Create `tests/unit/test_graphics.py`
- [ ] Define test cases for graphics enter/exit cycle
- [ ] Define test cases for matrix copy with IRQ opportunities
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/runtime/graphics.asm`
- [ ] Implement `graphics_enter` — bitmap mode entry
- [ ] Implement `graphics_exit` — text mode restore
- [ ] Implement `graphics_matrix_copy` — bounded chunk copy
- [ ] Implement `graphics_validate_bounds`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_graphics.py -v
```

---

## Phase 9: Loader and Compressor Integration

> Build the Phase 1 installer. **Artifact-first hybrid TDD** — package tests
> assert manifests, headers, and round trips before final runnable media.

### T9.1 Loader Core

**Prerequisites:** T2.5, T2.6, T2.7, T3.2

**RED phase:**
- [ ] Create `tests/unit/test_loader.py`
- [ ] Create `tests/integration/test_loader.py`
- [ ] Define test cases for each loader routine
- [ ] Define integration test for full loader sequence
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/loader/loader.asm`
- [ ] Implement `loader_entry` — main entry at `$080D`
- [ ] Implement `loader_detect_georam` — detection wrapper
- [ ] Implement `georam_load_georam_file` — load GEORAM from disk
- [ ] Implement `georam_install_pages` — byte-by-byte install
- [ ] Implement `loader_install_ram_payload` — RAM payload install
- [ ] Implement `loader_restore_banking` — restore `$35`
- [ ] Implement `loader_check_sentinel` — guard byte check

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify all integration tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_loader.py -v
pytest tests/integration/test_loader.py -v
```

### T9.2 Compiler Init

**Prerequisites:** T9.1, T3.2, T2.8

**RED phase:**
- [ ] Create `tests/unit/test_compiler_init.py`
- [ ] Define test cases for BSS clear
- [ ] Define test cases for arena construction
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `src/loader/compiler_init.asm`
- [ ] Implement `compiler_init` — BSS clear, arena init, editor entry
- [ ] Implement `init_clear_bss`
- [ ] Implement `init_arenas`
- [ ] Implement `init_editor` / `init_enter_main_loop`

**REFACTOR phase:**
- [ ] Verify all unit tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/unit/test_compiler_init.py -v
```

### T9.3 Compressor Integration

**Prerequisites:** T9.1

**RED phase:**
- [ ] Create `tests/system/test_compressor.py`
- [ ] Define test cases for CGS1 header validation
- [ ] Define test cases for streaming decompression to geoRAM
- [ ] Define integration test for compressed GEORAM install
- [ ] Define system test for sidecar round-trip verification
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Copy `georam_stream_reader.asm` from compressor project
- [ ] Integrate `georam_stream_load` into loader
- [ ] Allocate `zp_georam_stream` (15 bytes) in loader ZP
- [ ] Create `build/georam_stream.cfg` for compressor
- [ ] Generate `build/segments/compiler_main.bin`
- [ ] Generate `build/compressor_layout.cfg`
- [ ] Generate `build/GEORAM_compressed.prg`
- [ ] Generate `build/GEORAM_compressed.json`
- [ ] Add `-UseCompressor` flag to `build.ps1`

**REFACTOR phase:**
- [ ] Verify all system tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1 -GeoramCompiler -UseCompressor
pytest tests/system/test_compressor.py -v
```

### T9.4 D64 Packaging

**Prerequisites:** T9.3

**RED phase:**
- [ ] Create `tests/system/test_binary_artifacts.py`
- [ ] Define test cases for D64 contents match manifest
- [ ] Define test cases for `basicv3.prg` load address and loader stub
- [ ] Define test cases for `georam.bin` size, order, and padding
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `tools/package_d64.py`
- [ ] Generate `build/basicv3.prg`
- [ ] Generate `build/georam.bin`
- [ ] Generate `build/compiler.d64`
- [ ] Implement `build_d64` — create D64 with BASICV3 and GEORAM
- [ ] Implement `validate_d64` — directory, filenames, sizes
- [ ] Implement `validate_prg_header` — load address and stub

**REFACTOR phase:**
- [ ] Verify all system tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
python tools/package_d64.py
pytest tests/system/test_binary_artifacts.py -v
```

---

## Phase 10: System Verification and Optimization

> Validate the complete system. **Test-first** — these ARE tests.

### T10.1 Build Validation

**Prerequisites:** T0.1-T0.6, T9.4

**RED phase:**
- [ ] Create `tests/system/test_system_toolchain.py`
- [ ] Create `tests/system/test_system_linker_contract.py`
- [ ] Create `tests/system/test_system_memory_map.py`
- [ ] Create `tests/system/test_system_banking_vectors.py`
- [ ] Create `tests/system/test_system_generated_metadata.py`
- [ ] Create `tests/system/test_system_generated_reference.py`
- [ ] Create `tests/system/test_system_binary_artifacts.py`
- [ ] Create `tests/system/test_system_resource_budgets.py`
- [ ] Create `tests/system/test_system_test_environment.py`
- [ ] Define test cases for each validation category
- [ ] Define test cases for `obj/`, `listings/`, and `generated/` output policy
- [ ] Define test cases for `compiler.bin`, `compiler.map`, and `compiler.lbl`
- [ ] Define test cases for `build_manifest.json`, `loader_manifest.json`, and `size_report.json`
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `tools/validate_build.py` — cross-artifact checks
- [ ] Implement tool version validation
- [ ] Implement manifest schema validation
- [ ] Implement routine directory consistency
- [ ] Implement arena layout consistency
- [ ] Implement ZP allocation consistency
- [ ] Implement size report validation
- [ ] Implement program format validation
- [ ] Implement runtime ABI validation
- [ ] Implement keyword lookup validation
- [ ] Implement generated reference validation
- [ ] Implement stale file detection
- [ ] Implement build fingerprint computation
- [ ] Generate and validate `build/compiler.bin`
- [ ] Generate and validate `build/compiler.map`
- [ ] Generate and validate `build/compiler.lbl`
- [ ] Generate and validate `build/build_manifest.json`
- [ ] Generate and validate `build/loader_manifest.json`
- [ ] Generate and validate `build/size_report.json`

**REFACTOR phase:**
- [ ] Verify all system tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
python tools/validate_build.py --all
```

### T10.2 Generated References

**Prerequisites:** T10.1

**RED phase:**
- [ ] Define expected API.md content
- [ ] Define expected MAP.md content
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `tools/generate_reference.py`
- [ ] Generate `build/API.md` — production callable reference
- [ ] Generate `build/MAP.md` — CPU/ZP/segment/geoRAM/arena map
- [ ] Validate API completeness and calling conventions
- [ ] Validate MAP ordering, non-overlap, totals

**REFACTOR phase:**
- [ ] Verify all system tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
python tools/generate_reference.py
python tools/validate_build.py --reference
```

### T10.3 Size Budget Validation

**Prerequisites:** T10.1

**RED phase:**
- [ ] Define expected budget limits
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `tools/extract_segments.py` — RAM payload extraction
- [ ] Create `tools/prepare_compressor_segments.py` — LZSS staging
- [ ] Validate resident byte budget within limit
- [ ] Generate and validate `build/compile.bin`
- [ ] Generate and validate `build/segments/compiler_main.bin`
- [ ] Generate and validate `build/compressor_layout.cfg`
- [ ] Validate geoRAM page budget within limit
- [ ] Validate stack depth within limit
- [ ] Validate context nesting within limit
- [ ] Validate standalone COMPILE budget

**REFACTOR phase:**
- [ ] Verify all system tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
python tools/validate_build.py --budgets
```

### T10.4 Test Harness

**Prerequisites:** T10.1

**RED phase:**
- [ ] Define expected coverage matrix
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create `tools/test_harness.py` — host test collection
- [ ] Implement `collect_assembly_entries` — coverage matrix
- [ ] Implement `replay_boundary` — boundary replay
- [ ] Implement `run_smoke_selection` / `run_full_selection`
- [ ] Validate every callable has unit coverage

**REFACTOR phase:**
- [ ] Verify all system tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
python tools/test_harness.py --validate-coverage
```

---

## Phase 11: E2E Language Tests

> Validate complete BASIC language behavior through VICE. **Test-first.**

### T11.1 VICE Test Infrastructure

**Prerequisites:** T10.1

**RED phase:**
- [ ] Create `tests/hardware/test_vice_infrastructure.py`
- [ ] Define test cases for VICE tool availability
- [ ] Define test cases for snapshot generation
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Create VICE snapshot generation scripts
- [ ] Create VICE editor mailbox injection
- [ ] Create VICE observation collection
- [ ] Create fixture normalization
- [ ] Validate VICE tool paths

**REFACTOR phase:**
- [ ] Verify all hardware tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/hardware/test_vice_infrastructure.py -v
```

### T11.2 BASIC V2 E2E Tests

**Prerequisites:** T11.1, T1.1

**RED phase:**
- [ ] Create `tests/e2e/test_e2e_basicv2_functions.py`
- [ ] Create `tests/e2e/test_e2e_basicv2_statements.py`
- [ ] Define test cases for all BASIC V2 keywords
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Implement immediate mode runner
- [ ] Implement program mode runner
- [ ] Implement compile mode runner
- [ ] Validate all BASIC V2 keywords covered

**REFACTOR phase:**
- [ ] Verify all E2E tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/e2e/test_e2e_basicv2_*.py -v
```

### T11.3 BASIC V3.5 E2E Tests

**Prerequisites:** T11.1, T1.2

**RED phase:**
- [ ] Create `tests/e2e/test_e2e_basicv35_functions.py`
- [ ] Create `tests/e2e/test_e2e_basicv35_statements.py`
- [ ] Define test cases for all BASIC V3.5 keywords
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Validate all BASIC V3.5 keywords covered

**REFACTOR phase:**
- [ ] Verify all E2E tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/e2e/test_e2e_basicv35_*.py -v
```

### T11.4 IEEE E2E Tests

**Prerequisites:** T11.1, T7.2

**RED phase:**
- [ ] Create `tests/e2e/test_e2e_basicv3_functions_ieee.py`
- [ ] Create `tests/e2e/test_e2e_basicv3_statements_ieee.py`
- [ ] Define test cases for IEEE functions against oracle
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Validate IEEE functions against oracle

**REFACTOR phase:**
- [ ] Verify all E2E tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/e2e/test_e2e_basicv3_*_ieee.py -v
```

### T11.5 Hardware Tests

**Prerequisites:** T11.1

**RED phase:**
- [ ] Create `tests/hardware/test_keyboard.py`
- [ ] Create `tests/hardware/test_irq.py`
- [ ] Create `tests/hardware/test_devices.py`
- [ ] Define test cases for keyboard full path
- [ ] Define test cases for IRQ timing
- [ ] Define test cases for device load/save
- [ ] Verify tests fail

**GREEN phase:**
- [ ] Validate keyboard full path: key -> CIA -> IRQ -> SCNKEY -> GETIN -> editor
- [ ] Validate IRQ timing and restoration
- [ ] Validate device load/save

**REFACTOR phase:**
- [ ] Verify all hardware tests pass
- [ ] Verify no regressions

**Verification:**
```powershell
pytest tests/hardware/ -v
```

---

## Phase 12: Resident Size Minimization

> Optimize resident code size. **Measurement-first.**

### T12.1 Size Measurement

**Prerequisites:** T10.3

- [ ] Add resident byte budget tracking to build
- [ ] Add geoRAM page budget tracking to build
- [ ] Generate size deltas for each commit
- [ ] Identify hot paths justifying resident placement

**Verification:**
```powershell
python tools/validate_build.py --size-report
```

### T12.2 Profile-Guided Optimization

**Prerequisites:** T12.1, T11.2

- [ ] Measure call frequency for each runtime helper
- [ ] Move cold helpers to geoRAM
- [ ] Verify no regression in Phase 1 benchmark
- [ ] Update resident byte budget

**Verification:**
```powershell
pytest tests/e2e/test_e2e_basicv2_*.py -v -k "FOR"
# Phase 1 benchmark must complete in < 60 jiffies
```

---

## Phase 13: Smoke Test Selection

> Define and validate the stable smoke test subset. **Test-first.**

### T13.1 Smoke Selection

**Prerequisites:** T11.2, T10.4

**RED phase:**
- [ ] Define smoke test criteria
- [ ] Verify smoke selection is empty

**GREEN phase:**
- [ ] Mark stable unit tests as `smoke`
- [ ] Mark stable integration tests as `smoke`
- [ ] Mark stable system contract tests as `smoke`
- [ ] Mark stable E2E tests as `smoke`
- [ ] Validate smoke selection covers all critical paths
- [ ] Validate smoke selection runs in < 60 seconds

**REFACTOR phase:**
- [ ] Verify smoke selection is stable across runs

**Verification:**
```powershell
pytest tests/ -v -m smoke --tb=short
```

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

Total: 79 tasks across 13 phases.

## Hybrid TDD Checklist

For each implementation task:

- [ ] Contract, fixture, schema, or test gate identified before implementation
- [ ] Owning tests or validators defined for all documented behavior
- [ ] Expected failure verified where a runnable RED test exists
- [ ] Source/tool/build change implemented to make the gate pass
- [ ] Code and generated outputs cleaned up while affected tests still pass
- [ ] Traceability, generated references, and docs updated when behavior changes
- [ ] No regressions in previously passing tests

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
