# Design Validation Record

## Scope

This record captures the initial validation of Compiler 2 against useful
evidence in the legacy compiler and the rebuildable stock ROM source. It is a
design audit, not a claim that Compiler 2 has already been implemented.
Compiler 2 has no production source tree yet.

## Evidence Reviewed

Legacy compiler at `C:\Users\me\Documents\Coding Projects\compiler`:

- `src/georam/georam_config.s`
- `src/georam/georam_detect.s`
- `src/georam/georam_page_caller.s`
- `src/core/zp.s`
- `src/core/constants.s`
- `src/core/kernal_file.s`
- `src/runtime/graphics_helpers.s`
- `tests/rewrite_compat/emu_wrapper.py`
- `tests/vice_harness.py`
- `tests/test_vice_compiler_startup.py`
- `tools/graphics_bitmap_reference.py`
- `TEST_HARNESS.md`
- `FAST_LOOPS.md`
- `docs/MANUAL.md`
- `docs/KEYWORDS.md`

Stock ROM reference:

- `C:\Users\me\Documents\Coding Projects\c64rom\kernal\declare.s`
- `C:\Users\me\Documents\Coding Projects\c64rom\kernal\time.s`
- `C:\Users\me\Documents\Coding Projects\c64rom\kernal\editor_scroll.s`
- `C:\Users\me\Documents\Coding Projects\c64rom\docs\KERNEL_ZP.md`
- `C:\Users\me\Documents\Coding Projects\c64rom\debug\c64rom.labels`

## Validated Mechanisms

### geoRAM Hardware

The legacy implementation and local emulator agree on the `$DE00` 256-byte
window, `$DFFE` page register, `$DFFF` block register, and 64 pages per 16 KiB
block. The new banking document uses that model.

The legacy detector demonstrates the right basic non-destructive method:
write distinct patterns to distinct selections, test aliasing, restore probe
bytes, and restore the original selection. Compiler 2 strengthens the contract
to include CPU-port, DDR, interrupt state, all exits, and debug false-positive
checks.

### Compact Indexed Calls

The legacy caller proves that compact call sites can resolve a target through
page/offset tables and block thresholds while restoring the caller page after a
nested call. Compiler 2 retains the indexed grouping and generated tables.

Two legacy details are deliberately not copied:

- several names promising register preservation are aliases to the same entry,
  not distinct preservation implementations;
- `georam_jmp` is an alias of the returning call in the primary path, while a
  separate tail-call path contains the real stack fixup.

Compiler 2 therefore has one explicit returning ABI and one separately tested
true tail-transfer ABI.

### Loop Descriptors

The legacy fast-loop work demonstrates useful metadata:

- stable variable descriptors;
- loop kind and partner;
- variable width and bank policy;
- literal start, limit, and step;
- simple condition descriptors and polarity;
- invalidation/dirty masks;
- conservative generic fallback.

This is transported as design, not copied code. The new compiler builds these
descriptors before emission and makes one eligibility decision per fast path.

### Zero-Page Lifetimes

The legacy manual describes lifetime-based sharing and graph coloring, and
`src/core/zp.s` contains intentional overlays among math, tokenizer, editor,
and statement scratch.

The analyzer referenced by that manual is not present in the legacy source
tree, so the claimed conflict proof is not independently reproducible there.
Compiler 2 makes the manifest, graph, allocation, and linker comparison required
build products. Intentional aliases must be data, not comments.

### KERNAL Zero Page

The `c64rom` source resolves important facts that are easy to miss in a project
map:

- `UDTIM` writes `$A0-$A2` and `$91`;
- `SCNKEY` uses `$C5-$C6`, `$CB`, and `$F5-$F6`;
- `GETIN` uses `$99` and `$C6` on the keyboard path;
- `STOP` uses `$91`, flushes `$C6` when pressed, and can enter `CLRCHN`;
- `SETNAM` uses `$B7` and `$BB-$BC`;
- `SETLFS` uses `$B8-$BA`.

These sets are now explicit inputs to zero-page interference.

### Layered Testing

The legacy local wrapper proves direct entry-point execution, RAM/register
inspection, ROM overlays, CPU banking, and persistent geoRAM window behavior.
It does not schedule real interrupts.

The legacy VICE harness already demonstrates the correct test economy:
keyboard injection is a narrow top layer, while normal tests inject atomically
through an editor mailbox. Startup snapshots are fingerprinted from build
artifacts. Compiler 2 adopts and tightens those rules.

### System Contract Test Category

The legacy suite contains a coherent class of tests that is not naturally
unit, integration, functional, or E2E behavior:

- geoRAM phase/table tests inspect generated pages, index tables, and linker
  output;
- runtime-layout and memory-planner tests enforce address, descriptor, and
  capacity contracts;
- RAM-sidecar and compressed-loader tests validate packaged binary structure;
- mailbox-symbol and VICE-startup tests validate test/build environment ABIs;
- no-fast-path and banking checks enforce architectural policy;
- benchmark/snapshot checks enforce resource and provenance contracts;
- emulator-binding tests validate the local execution environment.

Compiler 2 names this category `system contract`. It covers whole-build and
environment invariants while leaving helper algorithms as unit tests and
user-visible workflows as functional/E2E tests.

### Build Toolchain

The legacy build demonstrates the reusable ca65/ld65 sequence: generate build
inputs, assemble normal and geoRAM translation units, link with an explicit
configuration, emit listings/maps, validate segments, package PRG/geoRAM/D64
artifacts, and fingerprint the result.

Compiler 2 keeps that toolchain but removes old auto-porting and permissive
fallback assumptions. `ca65` and `ld65` 2.19 are the known installed baseline,
and any failed generation, assembly, link, or validation step fails the build.

The same post-link structured artifacts are sufficient to generate
`build/API.md` and `build/MAP.md`. This is host-side table rendering and does
not affect the resident C64 footprint. The design avoids a fingerprint cycle:
the references omit their own checksum/final fingerprint, and the final
`build_manifest.json` records their checksums.

### VICE File Utilities

The legacy test-harness guidance and integration tests establish the reusable
VICE utility workflow:

- `c1541 -format "<label>,<id>" d64 <image>` creates a test disk;
- `c1541 -attach <image> -write <host-prg> <cbm-name>` injects a PRG with an
  explicit Commodore filename;
- `c1541 -attach <image> -list` provides a machine-checkable directory listing;
- `petcat -2` lists stock tokenized BASIC V2 and `petcat -3` lists stock
  tokenized BASIC V3.5.

Compiler 2 records these checked PowerShell forms in `docs/VICE_TOOLS.md`.
Temporary images and listings belong in `debug/`.

### Graphics Memory

The legacy graphics runtime and reference model agree on an 8000-byte bitmap
at `$E000-$FF3F` and a 1000-byte screen matrix at `$DC00-$DFE7`. CIA 2 selects
VIC bank `$C000-$FFFF`, and `$D018 = $78` selects those two offsets.

The important banking detail is that `$DC00` names different resources from
the CPU's point of view:

- with I/O visible, `$DC00` is CIA 1;
- with I/O hidden, `$DC00-$DFE7` is the RAM used as the VIC screen matrix;
- `$D800-$DBE7` with I/O visible is physical color RAM, a separate resource.

The legacy implementation clears all 1000 underlying screen bytes while I/O
is hidden. Compiler 2 retains the placement but improves interrupt latency by
using bounded chunks with I/O restored between chunks. The complete contract
is in `docs/GRAPHICS_MEMORY.md`.

## Compatibility Gaps Found

The copied keyword reference does not enumerate the entire stock BASIC V2 token
surface. In particular, a requirements baseline cannot infer completeness only
from that file. `REQUIREMENTS.md` now lists the full stock statements,
operators, and functions explicitly.

The old design also mixed user-visible requirements with placement choices.
The split into `REQUIREMENTS.md` and `DESIGN2.md` prevents a future memory or
overlay refactor from silently changing compatibility.

## Current Feasibility and Bottleneck Audit

The architecture is feasible at the document level. Nothing requires hardware
behavior outside the C64/geoRAM model, and the host-side generators, linker,
reference renderer, and validators are conventional. Feasibility is not yet a
performance proof: Compiler 2 still needs production assembly, generated
contracts, and measurements on the target emulator/VICE profiles.

The highest-risk algorithms and mitigations are:

| Area | Bottleneck or worst case | Design mitigation | Required evidence |
|---|---|---|---|
| Keyword recognition | A linear scan per identifier scales with keyword count and competes with the ~0.5-second line-entry target | Generated first-character-indexed trie with token/dialect/abbreviation/longest-match accepting metadata; no full-table fallback | `keyword_lookup_report.json`, manifest-to-trie coverage, worst-transition and full-line timings |
| Incremental compilation | Structural edits can dirty most lines and force dependency repair plus whole-program relink | Generation-stamped records, reverse dependency indexes, explicit local/structural edit classes, atomic publication | Local-edit and worst-case structural-edit timings by phase and affected-record count |
| Loop analysis | Rescanning every nested loop body for each eligibility check/emitter can become quadratic | One bottom-up IR summary pass cached by generation; parents merge child masks and emitters consume the shared result | Nested-loop stress tests and separate summary/eligibility/emission timings |
| geoRAM native calls | Fine-grained cross-page calls and byte-at-a-time data access can make gate/context switching dominate compiler work | Coarse service boundaries, bulk copy/checksum helpers, size/call-aware page placement, hot-directory cache only when budgeted | Gate-call counts/cycles per phase, page-locality report, long-operation IRQ progress |
| geoRAM page placement | 256-byte packing is NP-hard in general; first-fit can falsely fail through fragmentation | Deterministic size/call-aware packing with bounded local search/backtracking and useful failure diagnostics | Reproducible placement, adversarial packing tests, actual-size post-link validation |
| Zero-page allocation | Aligned contiguous graph coloring is NP-hard; greedy coloring can falsely fail or waste ZP | Deterministic DSATUR/interval placement with bounded backtracking | Adversarial allocator tests, edge-reason audit, linker comparison, stable output |
| Code layout/export | Relocation repair and runtime dependency closure can become whole-program work; standalone image is capped at `$CFFF` | Generation checks, explicit relink phase, dependency manifest, separate code/workspace budgets, fail-before-write export | Phase timings, relocation stress tests, stock-C64 export budget/system tests |
| Compiler working sets | Repeated small geoRAM transfers can dominate parsing/IR/codegen despite ample capacity | Stable handles, page-local batches, bounded normal-RAM staging buffers, serialized phase artifacts | Bytes/transfers per phase, high-water marks, representative large-program compile timings |

The selected lexer search is therefore fast by design: lookup is proportional
to candidate length plus a generated transition bound, rather than total
keyword count. It is not yet accurate to say the current compiler *runs* that
algorithm because no production tokenizer exists in this tree. Implementation
is accepted only after the generated report and timing tests prove the trie is
actually used.

The hard Phase 1 sub-60-jiffy loop target is plausible because emitted native
integer loop code avoids interpreter token dispatch. The more uncertain target
is interactive compile-on-entry: parser/codegen work and structural dependency
repair run on a 1 MHz machine and may cross geoRAM pages. Phase timing,
gate-call counts, and edit classification must be instrumented from the first
implementation milestone rather than added after responsiveness degrades.

## Result

The revised design is internally consistent at the document level and is
informed by legacy source mechanisms that have executable tests in the legacy
project. The generated-reference addition is feasible and has no target-runtime
cost. Compiler 2 implementation validation still requires new source,
generated contracts, measured lexer/incremental/geoRAM performance, and the
test hierarchy described by the requirements.
