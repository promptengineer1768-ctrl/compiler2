# Compiler 2 Dual GeoRAM/REU Implementation Tasks

This is the resumable implementation plan for `REU_REQUIREMENTS.md` and
`REU_DESIGN.md`. It follows the hybrid TDD gates in `TASKS.md` and adds the REU
profile without reverting unrelated geoRAM work.

## Status Codes

| Code | Meaning |
|---|---|
| `[ ]` | Not started |
| `[~]` | In progress |
| `[x]` | Complete |
| `[-]` | Blocked; record the blocker immediately below the item |
| `[!]` | Skipped; record the approved reason immediately below the item |

## How to Resume

1. Read `REU_REQUIREMENTS.md`, `REU_DESIGN.md`, and the latest checkpoint below.
2. Scan in phase order for the first `[~]`; otherwise select the first `[ ]`
   whose prerequisites are `[x]`.
3. Confirm the working tree before editing and preserve unrelated changes.
4. Complete CONTRACT → RED → GREEN → REFACTOR → TRACE for that task.
5. Put temporary captures, VICE dumps, generated reproducers, and measurements
   under `debug/`.
6. Record commands and results in the task's checkpoint, then mark it `[x]`.
7. Run Graphify incrementally after meaningful source or documentation changes.

## Checkpoint

**Current task:** RT0.1

**Last completed:** REU requirements, design, and task derivation.

**Next action:** Add dual-device requirement trace records and startup-selection
schemas without changing the current GeoRAM-only build output prematurely.

**Known constraints:**

- The working tree contains unrelated user changes; do not normalize or revert
  them.
- Overlay slot origins and sizes are intentionally undecided until the linker
  inventory and workload constraints are generated.
- The release target is one `BASICV3` PRG that detects GeoRAM and REU at startup.
- Either supported device alone must run the complete development environment.
- Both-present selection is generated and deterministic; GeoRAM is the default.
- The D64 carries both `GEORAM` and `REU`, but startup loads only the selected one.

---

## Phase RT0: Contracts and Baseline

> Establish traceability, authoritative hardware fixtures, and unchanged
> geoRAM baselines before introducing REU behavior. **Contract-first.**

### RT0.1 REU Traceability Contract

**Prerequisites:** None

**CONTRACT phase:**

- [ ] Add every `RREU-*` ID to the checked-in traceability source
- [ ] Define design anchors, planned components, test nodes, and status fields
- [ ] Extend trace schemas to accept the `reu` profile without weakening geoRAM
- [ ] Add a coverage validator proving every REU EARS statement is traced once

**RED phase:**

- [ ] Add failing system tests for missing, duplicate, and dangling REU records

**GREEN phase:**

- [ ] Generate REU rows in `requirements_matrix.json` and Markdown output
- [ ] Make REU trace validation pass while the profile remains planned

**REFACTOR/TRACE phase:**

- [ ] Keep common trace generation device-neutral where the schema is shared
- [ ] Update traceability documentation with one REU example

**Verification:**

```powershell
pytest tests/system/test_traceability.py -v
python tools/validate_build.py --manifests
```

### RT0.2 Hardware Semantics Fixtures

**Prerequisites:** RT0.1

**CONTRACT phase:**

- [ ] Record the REC register table, bit meanings, reset assumptions, status
  read effects, transfer types, address controls, and length-zero semantics
- [ ] Record authoritative source and VICE version provenance
- [ ] Define supported 512-KiB and larger capacity/alias fixtures
- [ ] Define C64 memory-range observations during DMA
- [ ] Define four startup matrices: GeoRAM only, REU only, both, and neither
- [ ] Define both-present preference and preferred-device-failure fallback cases

**RED phase:**

- [ ] Add fixture-schema tests and empty expected VICE captures

**GREEN phase:**

- [ ] Capture focused VICE observations for each required hardware behavior
- [ ] Resolve discrepancies against VICE source/tests and document conclusions

**REFACTOR/TRACE phase:**

- [ ] Reduce fixtures to stable observations rather than emulator UI details

**Verification:**

```powershell
pytest tests/fixtures/reu/ -v
pytest tests/hardware/ -v -k reu
```

### RT0.3 GeoRAM Baseline and Cross-Profile Oracle

**Prerequisites:** RT0.1

**CONTRACT phase:**

- [ ] Select representative install, editor, compile, arena, math, and export
  scenarios for later cross-profile comparison
- [ ] Define comparisons at serialized boundaries and user-visible outputs
- [ ] Exclude physical placement and device-specific traffic from equivalence

**RED/GREEN phase:**

- [ ] Capture the current geoRAM build fingerprint, outputs, size report, and
  selected semantic results
- [ ] Validate the baseline can be replayed without rebuilding reference ROM
  semantics

**REFACTOR/TRACE phase:**

- [ ] Store diagnostic runs under `debug/`; keep only versioned oracle fixtures
  as test inputs

**Verification:**

```powershell
pytest tests/integration/ tests/e2e/ -v -m "georam or smoke"
```

---

## Phase RT1: Dual-Device Contract and Local REC Model

> Add the common startup-selection contract and a testable REU controller model
> before production assembly. **Tool/emulator-first.**

### RT1.1 Expansion Detection and Selection Schema

**Prerequisites:** RT0.1

**CONTRACT phase:**

- [ ] Define candidate device types, capability flags, active-device record,
  startup preference, selection reason, and fallback reason
- [ ] Define REU minimum/maximum capacity, address width, image names, REC
  policy, DMA range classes, and generated artifact names
- [ ] Define the common `BASICV3`, `GEORAM`, and `REU` artifact contract
- [ ] Define failure for unsupported preference or inconsistent device records

**RED phase:**

- [ ] Add tool tests for valid, missing, conflicting, and stale selection policy
- [ ] Add all four device-presence combinations and both preference values

**GREEN phase:**

- [ ] Extend manifests and `build.ps1` preference parsing
- [ ] Preserve the existing GeoRAM path while introducing the common artifact
- [ ] Make incomplete dual-device builds fail at the first missing contract

**REFACTOR/TRACE phase:**

- [ ] Centralize device selection; do not scatter loader or PowerShell conditionals

**Verification:**

```powershell
pytest tests/tools/ -v -k "profile or manifest"
powershell -ExecutionPolicy Bypass -File build.ps1 -Validate
```

### RT1.2 Local REC Emulator

**Prerequisites:** RT0.2, RT1.1

**CONTRACT phase:**

- [ ] Define model API for REC registers, REU bytes, aliasing, DMA stall events,
  status side effects, and injected faults
- [ ] Limit the model to authoritative behavior used by Compiler 2

**RED phase:**

- [ ] Add cases for copy directions, verify, fixed/incrementing addresses,
  64-KiB encoded length, status clear-on-read, capacity aliasing, and faults

**GREEN phase:**

- [ ] Implement the model and test-harness bindings

**REFACTOR/TRACE phase:**

- [ ] Differentially compare focused model cases with captured VICE fixtures

**Verification:**

```powershell
pytest tests/unit/test_reu_model.py tests/integration/test_reu_model_vice_fixtures.py -v
```

### RT1.3 Dual-Device Generated Artifact Skeletons

**Prerequisites:** RT1.1

**CONTRACT phase:**

- [ ] Define schemas for `reu_layout.json`, `overlay_directory.json`,
  `reu_loader_manifest.json`, and REU size/performance reports
- [ ] Define schemas for candidate records, active-expansion record, common
  dispatch directory, and GeoRAM/REU sidecar agreement
- [ ] Define empty-valid and unimplemented states without fake placements

**RED/GREEN phase:**

- [ ] Add golden structural tests
- [ ] Generate deterministic skeleton artifacts for the dual-device build
- [ ] Reject hand-edited or stale generated artifacts

**Verification:**

```powershell
pytest tests/tools/ -v -k "reu and (layout or artifact or contract)"
```

---

## Phase RT2: Resident REC Gate and Detection

> Implement bounded, directly tested hardware access before arenas or
> executable overlays depend on it. **Assembly unit-first.**

### RT2.1 REC Register Gate

**Prerequisites:** RT1.2, RT1.3

**CONTRACT phase:**

- [ ] Add routine manifests and generated ZP lifetimes for raw test-only submit,
  copy-to, copy-from, verify, status normalization, and profile validation
- [ ] Define allowed C64 DMA range classes and error codes

**RED phase:**

- [ ] Add direct unit cases for register programming, exclusion, status reads,
  canonical mapping, interrupt state, invalid ranges, and injected faults
- [ ] Verify tests fail against missing assembly

**GREEN phase:**

- [ ] Implement `src/resident/reu_gate.asm` using generated ZP symbols
- [ ] Disable REC interrupts, autoload, and `$FF00` triggering by default
- [ ] Return normalized carry/error results on every path

**REFACTOR/TRACE phase:**

- [ ] Keep raw physical entry points private or test-only
- [ ] Record resident byte delta

**Verification:**

```powershell
pytest tests/unit/test_reu_gate.py -v
python tools/validate_build.py --contracts
```

### RT2.2 Safe Chunking and Data Helpers

**Prerequisites:** RT2.1

**CONTRACT/RED phase:**

- [ ] Define boundary splitting and zero-logical-length cases
- [ ] Add tests for C64/REU wrap, protected ranges, 65535/65536/65537 lengths,
  fixed addresses, and partial-failure reporting
- [ ] Add overlap cases for logical REU-to-REU memmove

**GREEN phase:**

- [ ] Implement chunked ingress, egress, verify, checksum, byte/word access, and
  staged REU-to-REU copy
- [ ] Acquire and release the generated staging-buffer lease on every path

**REFACTOR/TRACE phase:**

- [ ] Measure setup overhead and keep byte/word helpers correct, not presumed
  fast

**Verification:**

```powershell
pytest tests/unit/test_reu_gate.py tests/integration/test_reu_transfers.py -v
```

### RT2.3 Non-Destructive Detection

**Prerequisites:** RT2.2, RT0.2

**CONTRACT/RED phase:**

- [ ] Define supported capacity/address-bit policy and session-profile format
- [ ] Add absence, undersized, 512-KiB, larger, alias, floating-bus, restoration,
  and injected-failure cases

**GREEN phase:**

- [ ] Implement `src/arena/reu_detect.asm`
- [ ] Save/probe/restore candidate REU bytes through the bounded buffer
- [ ] Publish a temporary REU candidate only after verified restoration

**REFACTOR/TRACE phase:**

- [ ] Share only proven generic detector utilities with geoRAM
- [ ] Record detection time and resident byte delta

**Verification:**

```powershell
pytest tests/unit/test_reu_detect.py tests/integration/test_reu_detection.py -v
pytest tests/hardware/ -v -k reu_detect
```

### RT2.3a Common Startup Selection

**Prerequisites:** RT2.3, existing GeoRAM detector, RT1.1

**CONTRACT/RED phase:**

- [ ] Define independent candidate transactions and one immutable active record
- [ ] Add GeoRAM-only, REU-only, both-prefer-GeoRAM, both-prefer-REU, neither,
  preferred-invalid fallback, restoration-failure, and unselected-device-idle cases
- [ ] Verify neither detector leaves its selection/register/probe state changed

**GREEN phase:**

- [ ] Implement resident `expansion_detect_all` and `expansion_select`
- [ ] Default the generated both-present preference to GeoRAM
- [ ] Publish device type, capacity, capabilities, fingerprint, and reason
- [ ] Prevent all later access to the unselected device

**REFACTOR/TRACE phase:**

- [ ] Share save/restore scaffolding only where hardware contracts truly match
- [ ] Record the dual-detector and dispatcher resident byte delta

**Verification:**

```powershell
pytest tests/unit/test_expansion_select.py tests/integration/test_expansion_startup.py -v
pytest tests/hardware/ -v -k "expansion and (detect or select)"
```

### RT2.4 Fatal Path and Fault Injection

**Prerequisites:** RT2.1, RT2.3a

**CONTRACT/RED phase:**

- [ ] Add every `RREU-11.1` error to common constants and trace records
- [ ] Add failure cases at each gate/detector acquisition point

**GREEN phase:**

- [ ] Implement resident `fatal_reu` and recoverable unwind helpers
- [ ] Prevent further DMA/overlay entry after fatal profile or directory failure

**REFACTOR/TRACE phase:**

- [ ] Prove the path has no REU, overlay, or corrupt-directory dependency

**Verification:**

```powershell
pytest tests/unit/test_reu_errors.py tests/integration/test_reu_fault_unwind.py -v
```

---

## Phase RT3: REU Extents and Arena Backend

> Preserve common logical handles while replacing physical GeoRAM pages with
> validated REU extents and buffer leases. **Allocator-first.**

### RT3.1 Extent Allocator

**Prerequisites:** RT1.3, RT2.2

**CONTRACT/RED phase:**

- [ ] Define reserved image, metadata, and dynamic extent classes
- [ ] Add allocation/free/coalescing/alignment/exhaustion/overflow/generation
  cases at minimum and larger capacities

**GREEN phase:**

- [ ] Implement deterministic REU extent allocation and free-space reporting
- [ ] Generate reserved extents from linked images and profile capacity

**REFACTOR/TRACE phase:**

- [ ] Add corruption and adversarial-fragmentation cases

**Verification:**

```powershell
pytest tests/unit/test_reu_extent_alloc.py tests/tools/test_reu_layout.py -v
```

### RT3.2 Arena Handle Adapter

**Prerequisites:** RT3.1

**CONTRACT/RED phase:**

- [ ] Map common handle fields to REU extents without exposing physical address
- [ ] Add stale generation, cross-arena, bounds, ownership, reset, and rollback
  cases

**GREEN phase:**

- [ ] Implement REU arena creation, resolution, reset, destroy, and integrity
- [ ] Preserve common transaction and publication APIs
- [ ] Implement the active-device arena dispatcher without exposing physical type

**REFACTOR/TRACE phase:**

- [ ] Differentially run common arena behavior against geoRAM

**Verification:**

```powershell
pytest tests/unit/test_reu_arena.py tests/integration/test_reu_arena_lifecycle.py -v
```

### RT3.3 Work-Buffer Leases and Transactions

**Prerequisites:** RT3.2

**CONTRACT/RED phase:**

- [ ] Define lease owner/generation/range/dirty/pin fields
- [ ] Add nested lease, stale pointer, partial dirty range, eviction, abort, and
  injected-DMA-failure cases

**GREEN phase:**

- [ ] Implement acquire/materialize/commit/discard/release
- [ ] Route line and compiler publication through failure-atomic scratch extents

**REFACTOR/TRACE phase:**

- [ ] Instrument transfer counts and bytes by compiler phase

**Verification:**

```powershell
pytest tests/unit/test_reu_leases.py tests/integration/test_reu_transactions.py -v
```

### RT3.4 Strings and Small Objects

**Prerequisites:** RT3.3

**CONTRACT/RED phase:**

- [ ] Define variable extent or size-class policy for 0..255-byte strings
- [ ] Add empty/max, concatenate, compare, overwrite, stale descriptor,
  allocation failure, and dirty-cache invalidation cases

**GREEN phase:**

- [ ] Implement REU-backed string materialization and publication
- [ ] Preserve normal-RAM string support for standalone exports

**REFACTOR/TRACE phase:**

- [ ] Report fragmentation and bytes used versus a 256-byte-page baseline

**Verification:**

```powershell
pytest tests/unit/test_strings.py tests/integration/test_reu_strings.py -v
```

---

## Phase RT4: Overlay Generation and Execution

> Replace GeoRAM execute-in-place with generated normal-RAM overlay slots.
> **Graph/placement-first.**

### RT4.1 Overlay and Slot Solver

**Prerequisites:** RT1.3, RT3.1

**CONTRACT/RED phase:**

- [ ] Define overlay declarations, slot classes, BSS policy, entry records,
  callback edges, return kinds, and pin-depth rules
- [ ] Add adversarial size, SCC, recursion, callback, tail, and insufficient-slot
  fixtures

**GREEN phase:**

- [ ] Implement deterministic service grouping and slot placement from actual
  linked sizes and call edges
- [ ] Generate overlay/routine directories and useful failure diagnostics
- [ ] Generate cross-device ABI agreement records against GeoRAM routine IDs

**REFACTOR/TRACE phase:**

- [ ] Prefer fewer resident slot bytes after correctness is proven
- [ ] Report worst-case pin depth and estimated transfer traffic

**Verification:**

```powershell
pytest tests/tools/test_reu_overlays.py -v
python tools/validate_build.py --reu-overlays
```

### RT4.2 Linker and Image Integration

**Prerequisites:** RT4.1

**CONTRACT/RED phase:**

- [ ] Add linker contracts for each slot origin/capacity and overlay image
- [ ] Add symbol/entry/size/checksum/extent mismatch cases

**GREEN phase:**

- [ ] Generate REU-profile ld65 configuration
- [ ] Link overlays for their declared slot origins
- [ ] Build deterministic `reu.bin` with directory and image extents

**REFACTOR/TRACE phase:**

- [ ] Cross-check map, labels, binary, overlay directory, and REU layout

**Verification:**

```powershell
pytest tests/system/test_system_linker_contract.py tests/system/test_binary_artifacts.py -v -k reu
```

### RT4.3 Overlay Dispatcher

**Prerequisites:** RT4.2, RT2.4

**CONTRACT/RED phase:**

- [ ] Add direct tests for resolve, hit, miss, load, pin, release, deterministic
  eviction, checksum, incompatible slot, and depth failure
- [ ] Add nested, callback, resident re-entry, tail-transfer, and error-unwind
  integration cases

**GREEN phase:**

- [ ] Implement resident `reu_call_group_n`, `reu_tail_group_n`, context stack,
  slot cache, and debug validation
- [ ] Implement `expansion_call_group_n` / `expansion_tail_group_n` routing to
  GeoRAM XIP or REU overlay execution from the active-device record
- [ ] Ensure no slot is overwritten while executable or return-reachable

**REFACTOR/TRACE phase:**

- [ ] Record resident/slot byte deltas and hit/miss instrumentation

**Verification:**

```powershell
pytest tests/unit/test_reu_overlay.py tests/integration/test_reu_overlay_cycle.py -v
```

### RT4.4 Port Cold Services

**Prerequisites:** RT4.3, RT3.3

**CONTRACT/RED phase:**

- [ ] Classify editor, compiler, diagnostics, and cold math modules into overlays
- [ ] Add one real integration path per overlay and every callable direct unit
  test before changing placement

**GREEN phase:**

- [ ] Port services incrementally while preserving generated ABI and ZP rules
- [ ] Route bulk artifacts through leases rather than repeated byte DMA

**REFACTOR/TRACE phase:**

- [ ] Run cross-profile serialized-boundary comparisons after each service group

**Verification:**

```powershell
pytest tests/unit/ tests/integration/ -v -m "reu or local"
```

---

## Phase RT5: Loader, Packaging, and Initialization

> Produce an installable REU image only after transfer, allocation, and overlay
> paths are independently proven. **Artifact-first.**

### RT5.1 REU Sidecar Format

**Prerequisites:** RT4.2

**CONTRACT/RED phase:**

- [ ] Define versioned header, capacity, address width, extent directory,
  lengths, checksums, ABI/schema versions, and fingerprint
- [ ] Add truncation, overflow, overlap, order, padding, mismatch, and corruption
  cases

**GREEN phase:**

- [ ] Generate and validate uncompressed `reu.bin`
- [ ] Add round-trip parser independent of the generator

**Verification:**

```powershell
pytest tests/tools/ -v -k "reu and (image or sidecar)"
```

### RT5.2 Common Installer and Startup

**Prerequisites:** RT5.1, RT2.3a, RT4.3

**CONTRACT/RED phase:**

- [ ] Add loader cases for dual detection/selection, selected-sidecar loading,
  KERNAL staging, chunked install, checksum, capacity mismatch, fallback, disk
  failure, and cleanup
- [ ] Add integration case from `SYS2061` to editor-ready state
- [ ] Add cases proving the unselected sidecar and device are never opened/written

**GREEN phase:**

- [ ] Implement common startup plus GeoRAM and REU selected-loader paths
- [ ] Initialize only the selected backend's arena/execution directories
- [ ] Preserve canonical mapping and enter `compiler_init` only after validation

**REFACTOR/TRACE phase:**

- [ ] Measure loader bytes, staging high-water mark, and installation time

**Verification:**

```powershell
pytest tests/unit/test_reu_loader.py tests/integration/test_reu_install.py -v
```

### RT5.3 Dual-Device D64 Packaging and Optional Compression

**Prerequisites:** RT5.2

**CONTRACT/RED phase:**

- [ ] Require `BASICV3`, `GEORAM`, and `REU` D64 entries and manifest agreement
- [ ] Add stale/missing/wrong-name/wrong-profile image cases

**GREEN phase:**

- [ ] Package common `basicv3.prg`, `georam.bin`, `reu.bin`, and `compiler.d64`
- [ ] Where compression is implemented, add a new versioned stream with
  independent round-trip verification and bounded decompression staging

**REFACTOR/TRACE phase:**

- [ ] Keep uncompressed images authoritative for maps and debugging

**Verification:**

```powershell
pytest tests/tools/test_package_d64.py tests/system/test_binary_artifacts.py -v -k reu
```

---

## Phase RT6: Responsiveness and Whole-System Behavior

> Prove that DMA stalls do not make the interactive environment unacceptable
> and that common semantics survive the new physical backend. **VICE-first at
> the hardware boundary.**

### RT6.1 DMA Chunk and IRQ Latency

**Prerequisites:** RT5.2, RT0.2

**CONTRACT/RED phase:**

- [ ] Define measured jiffy, keyboard, cursor, STOP, and maximum uninterrupted
  DMA latency reports
- [ ] Add representative small, medium, large, and installation transfers

**GREEN phase:**

- [ ] Run VICE measurements across supported capacities
- [ ] Select foreground chunk caps from results and encode them in profile policy
- [ ] Permit pending IRQ service between chunks

**REFACTOR/TRACE phase:**

- [ ] Reject regressions above accepted report thresholds

**Verification:**

```powershell
pytest tests/hardware/ -v -k "reu and (irq or timer or keyboard or stop or latency)"
```

### RT6.2 Editor and Compiler Functional Paths

**Prerequisites:** RT4.4, RT5.2, RT6.1

**CONTRACT/RED phase:**

- [ ] Reuse authoritative editor, program lifecycle, compile, diagnostics, and
  numeric functional cases with REU selected
- [ ] Add transfer/high-water instrumentation assertions without changing
  semantic expected results

**GREEN phase:**

- [ ] Make each functional path pass with REU arenas and overlays

**REFACTOR/TRACE phase:**

- [ ] Batch pathological small transfers found by measurements

**Verification:**

```powershell
pytest tests/functional/ tests/integration/ -v -m reu
```

### RT6.3 Cross-Profile Differential Suite

**Prerequisites:** RT0.3, RT6.2

**CONTRACT/RED phase:**

- [ ] Compare tokenized source, serialized compiler boundaries, errors,
  user-visible output, saved programs, and standalone export bytes where
  determinism requires equality
- [ ] Classify physical placement, timing, and traffic as expected differences

**GREEN phase:**

- [ ] Resolve every unexplained REU/geoRAM difference

**REFACTOR/TRACE phase:**

- [ ] Generate a concise cross-profile report tied to both fingerprints
- [ ] Run comparisons from the same `BASICV3` artifact under each selected device

**Verification:**

```powershell
pytest tests/integration/ tests/functional/ -v -k cross_profile
```

---

## Phase RT7: Acceptance and Release

> Close generated contracts, VICE coverage, language E2E, budgets, and release
> documentation. **Contract/measurement-first.**

### RT7.1 System Contracts and Generated References

**Prerequisites:** RT5.3, RT6.3

- [ ] Validate REU linker/map/vector/CPU banking contracts
- [ ] Validate image, sidecar, loader, D64, overlay, arena, and routine contracts
- [ ] Generate REU rows in `API.md`, `MAP.md`, size, performance, and trace reports
- [ ] Validate clean/no-change reproducibility and stale-output rejection
- [ ] Record resident bytes by component and justify every REU delta

**Verification:**

```powershell
pytest tests/system/ -v -m static
powershell -ExecutionPolicy Bypass -File build.ps1
```

### RT7.2 VICE Capacity and Installation Matrix

**Prerequisites:** RT7.1, RT6.1

- [ ] Run GeoRAM-only minimum and larger supported profiles
- [ ] Run REU-only minimum and every larger capacity claimed by the build
- [ ] Run both-present with GeoRAM preference and REU preference
- [ ] Run preferred-device-invalid fallback in both directions
- [ ] Run neither-device and both-undersized clean failures
- [ ] Prove installation, REC behavior, nested overlay canary, IRQ recovery, and
  editor-ready state for each supported profile
- [ ] Prove the unselected device remains byte-for-byte unchanged after detection
- [ ] Reject stale snapshots by complete environment fingerprint

**Verification:**

```powershell
pytest tests/hardware/ tests/e2e/ -v -m "vice and reu"
```

### RT7.3 Language E2E and Standalone Export

**Prerequisites:** RT7.2, RT6.3

- [ ] Run the complete applicable critical language matrix with GeoRAM selected
- [ ] Run the same matrix with REU selected from the identical `BASICV3` PRG
- [ ] Preserve stock fixture provenance and shared immediate/program/compile modes
- [ ] Cold-load standalone exports in VICE with REU and geoRAM disabled
- [ ] Verify exports contain no expansion, editor, source, or private arena dependency

**Verification:**

```powershell
pytest tests/e2e/ -v -m reu
pytest tests/e2e/ -v -m "compile and stock_c64"
```

### RT7.4 Documentation and Release Gate

**Prerequisites:** RT7.1, RT7.2, RT7.3

- [x] Update build, architecture, memory, testing, VICE, generated-reference,
  manual, skeleton, test-plan, and traceability documents for dual-device design
- [x] Reconcile dual-device clauses in `REQUIREMENTS.md` and `DESIGN2.md` with
  the accepted dual-device startup and packaging contract
- [x] Document supported hardware/capacities, D64 usage, expected errors, and
  profile selection
- [ ] Mark all satisfied `RREU-*` records passing with build fingerprints
- [ ] Run the stable smoke selection in under its accepted budget
- [ ] Run a full clean REU release build and archive no debug artifacts as inputs
- [ ] Run Graphify incremental update and verify the project graph includes the
  final REU architecture and trace paths

**Verification:**

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
pytest tests/ -v -m smoke --tb=short
pytest tests/ -v -m reu
```

---

## Phase Summary

| Phase | Tasks | Gate | Outcome |
|---|---:|---|---|
| RT0 | 3 | Contract/fixture-first | Traceability and authoritative baselines |
| RT1 | 3 | Tool/emulator-first | Dual-device contract and local REC model |
| RT2 | 5 | Assembly unit-first | Safe DMA, dual detection/selection, and fatal handling |
| RT3 | 4 | Allocator/transaction-first | REU arenas, leases, and strings |
| RT4 | 4 | Graph/placement-first | Generated RAM overlay execution |
| RT5 | 3 | Artifact-first | Sidecar, loader, and D64 |
| RT6 | 3 | VICE/functional-first | Responsiveness and semantic equivalence |
| RT7 | 4 | Contract/acceptance-first | Release proof and documentation |

Total: 29 tasks across 8 phases.

## Per-Task Completion Checklist

- [ ] Prerequisites are complete
- [ ] Contract/schema/fixture acceptance is explicit
- [ ] Owning RED test failed for the expected reason
- [ ] Minimal implementation passes the owning tests
- [ ] Refactoring preserves affected tests
- [ ] Direct unit coverage exists for every callable assembly routine
- [ ] Generated artifacts and validators agree
- [ ] Resident, slot, REU, transfer, and timing deltas are reported as applicable
- [ ] Traceability and documentation are current
- [ ] No unrelated user changes were overwritten
- [ ] Temporary artifacts are confined to `debug/`
- [ ] Graphify was updated after meaningful changes

## References

- `REU_REQUIREMENTS.md` — normative EARS requirements
- `REU_DESIGN.md` — validated REU architecture
- `REQUIREMENTS.md` — common product requirements
- `DESIGN2.md` — top-level design index (includes dual-device expansion)
- `TASKS.md` — project TDD style and existing implementation plan
- `TESTS.md` — common test inventory
- `docs/TRACEABILITY.md` — EARS trace format
- `docs/TESTING.md` — test layers and fixture policy
- `docs/MEMORY_BUDGETS.md` — generated memory-budget policy
