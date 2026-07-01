# Generated Build Reference

## Purpose

Every build generates two human-readable references for the exact linked
configuration:

- `build/API.md` — callable production entries and their calling conventions;
- `build/MAP.md` — CPU, zero-page, segment, geoRAM, arena, and standalone
  memory summaries.

These files describe one build. They are generated artifacts, not normative
inputs, and are safe to delete with `build/`. The normative inputs remain the
checked-in manifests and design documents.

## Generator and Inputs

`tools/generate_reference.py` consumes structured, already validated build
artifacts:

- `production_entries.json`;
- `runtime_abi.json`;
- `routine_directory.json`;
- `compiler.map` and `compiler.lbl`;
- `zp_allocation.json`;
- `arena_layout.json`;
- `size_report.json`;
- the generated linker configuration and active build profile.

The generator must not recover contracts by scraping assembly comments,
listings, or hand-written Markdown. Missing, contradictory, or unresolvable
input fails the build.

The references do not embed their own checksum or the final build fingerprint;
doing so would create a hash cycle. `build_manifest.json` records the checksums
of `API.md` and `MAP.md` and ties them to the final build fingerprint.

## `API.md` Format

`API.md` begins with a build-summary table containing the configuration,
runtime ABI version, routine-directory version, and the checksums of the linked
RAM and geoRAM images.

It then contains a calling-convention summary:

| Field | Required content |
|---|---|
| Registers | Default meanings of A, X, and Y |
| Status | carry/error convention and declared N/Z/V results |
| Decimal mode | D clear at every public boundary |
| Stack | normal return, tail-transfer, unwind, and non-returning rules |
| Banking | required entry/exit CPU map and geoRAM selection preservation |
| Interrupts | incoming interrupt-state and IRQ-safety contract |
| Zero page | generated read/write/preserve declarations |

Every production callable appears exactly once in a table with these columns:

| Column | Meaning |
|---|---|
| Entry | Exported symbol |
| Layer/profile | Resident, runtime, geoRAM, loader, or standalone availability |
| Address | CPU address or generated geoRAM group/block/page/offset |
| Inputs | Exact register/record inputs |
| Outputs | Exact register/record and flag outputs |
| Error result | Carry/error meaning and error payload |
| Clobbers/preserves | Registers and flags |
| ZP read/write | Generated zero-page sets |
| Stack/return | Stack delta and return kind |
| Banking/IRQ | CPU-port, geoRAM-selection, and interrupt behavior |
| Side effects | Arena, channel, screen, file, or global-state effects |

A test build may add a clearly separated test-only table generated from
`test_entries.json`. Test-only entries never appear as production API.

## `MAP.md` Format

`MAP.md` begins with the same build-configuration and linked-image checksum
table as `API.md`. It contains:

1. a CPU memory map;
2. linked segment ranges and byte totals;
3. dynamic/free extents for text and graphics profiles;
4. the standalone `$0801-$CFFF` image and workspace summary;
5. zero-page allocations, fixed ROM/KERNAL reservations, aliases, and
   contingency bytes;
6. geoRAM block/page ownership for native code, directories, arenas, and free
   pages;
7. hardware, bitmap, RAM-under-I/O, guard-byte, and vector reservations.

CPU and segment tables use:

| Start | End | Bytes | Profile | Segment/owner | Load/run | Banking | Flags/source |
|---:|---:|---:|---|---|---|---|---|

Zero-page tables use:

| Start | End | Bytes | Symbol/owner | Lifetime | Fixed | Allowed aliases |
|---:|---:|---:|---|---|---|---|

geoRAM tables use:

| First page | Last page | Pages | Block range | Owner/type | Format/generation |
|---:|---:|---:|---|---|---|

Rows are sorted numerically and must explicitly show gaps, free ranges, and
profile-dependent overlays. Totals must agree with `size_report.json` and the
installed capacity profile.

## Build Order and Determinism

Reference generation runs after linking, post-link contract validation, and
size/resource report generation, but before the final build manifest and test
selection. It runs on every build, including narrow developer builds.

For identical validated inputs, `API.md` and `MAP.md` must be byte-identical.
They contain no wall-clock timestamp, host-specific path, unordered dictionary
output, or other nondeterministic value.

## Validation

System contract tests fail the build when:

- either reference is absent, stale, malformed, or nondeterministic;
- a production entry is missing, duplicated, or has an incomplete calling
  convention;
- an API address disagrees with labels, maps, or the geoRAM directory;
- a memory range overlaps illegally, is unsorted, or disagrees with linker,
  zero-page, arena, or size artifacts;
- totals or free extents do not balance;
- a test-only entry leaks into the production API;
- `build_manifest.json` omits either generated reference or its checksum.
