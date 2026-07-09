# Compiler 2 Dual GeoRAM/REU Design

## 0. Role and Plan Validation

`REU_REQUIREMENTS.md` is authoritative for the dual-device expansion profile.
`REQUIREMENTS.md` is authoritative for common Compiler 2 behavior and, after
reconciliation, states the dual-device product model (R2, R2.1, R7, R8).
`DESIGN2.md` is the top-level design index that integrates this document into
the overall architecture (§1, §2, §7.4, §8, §13). This file is the **detailed**
design for dual-device selection, REU hardware/DMA, overlays, REU arenas, dual
packaging, and REU verification. On disagreement, the applicable requirements
document wins; `DESIGN2.md` must not reintroduce a geoRAM-only product model.

**Revised model (authoritative):** REU does **not** introduce a separate
service-sized overlay architecture. **geoRAM 256-byte XIP is normative.** REU
stores the same page image and, on each call (or cache miss), DMA-copies one
256-byte page into a designated XIP RAM buffer and executes in place. Only
fetch/stash/call and bulk-DMA helpers differ from geoRAM.

1. One common `BASICV3` startup probes both devices; **prefer geoRAM** when
   both are valid; fall back to REU if geoRAM is unavailable.
2. Build **one** geoRAM-canonical expansion image (fits in **512 KiB**, XIP
   packed **low addresses first**) plus D64 file **`REU`** (versioned patch +
   fixup; fingerprint of `GEORAM`; **no geoRAM size** needed for fixup).
3. XIP slots below I/O with `$01=$35`: primary **`$CE00`**, hot slots
   **`$C800–$CDFF`**. Each slot is a true XIP origin: on DMA-in, fix abs
   `$DExx` → that slot’s high byte and route calls **directly** into the slot
   (not a data cache that recopies into `$CE00`). Prefill hot pages from a
   generated preference list; pin while nested. See `DESIGN2.md` §8.2.
4. Interactive DMA quanta ≤ **one jiffy** (~17 000 cycles); page fills are 256
   bytes. Hot slots pin while nested; prefill invariant hot pages at install.
5. REU DMA also serves large bulk copies (e.g. GC) when size amortizes REC
   setup (~60 cycles).
6. Layered tests: low-level gate contracts per device; bulk language E2E on
   geoRAM; REU smoke + hardware-combination install tests; VICE snapshots for
   geoRAM / REU / both-present pre-installed states.

Hardware semantics are based on the Commodore 1764 programmer's reference,
the REC register contract, and behavior verified in VICE. VICE observations
remain the acceptance authority for emulated operation.

| Requirement group | Design coverage |
|---|---|
| RREU-1 Product | §1, §9 |
| RREU-2 Hardware/capacity | §2, §3 |
| RREU-3 REC/DMA | §2, §4 |
| RREU-4 Detection | §3 |
| RREU-5 Overlays | §5 |
| RREU-6 Arenas/data | §6 |
| RREU-7 Strings/cache | §6.4 |
| RREU-8 Mapping/interrupts | §4.4, §7 |
| RREU-9 Loader/package | §8 |
| RREU-10 Generated build | §9 |
| RREU-11 Recovery | §10 |
| RREU-12 Verification | §11 |
| RREU-13 Acceptance | §12 |

## 1. Architecture

The dual-device profile preserves the five Compiler 2 layers and selects one
physical expansion backend at startup:

1. **Pinned resident kernel** owns IRQ/NMI reachability, GeoRAM selection, REC
   access, device detection/selection, the expansion dispatcher, KERNAL/CPU
   banking bridges, and fatal errors.
2. **Expansion-native services** execute directly through GeoRAM's window when
   GeoRAM is active or through normal-RAM overlay slots loaded from REU when
   REU is active.
3. **Compiled runtime ABI** remains the common stock-compatible interface used
   by emitted programs.
4. **Selected expansion arena storage** owns tokenized source, compiled cache,
   variables, arrays, strings, IR, directories, diagnostics, and scratch data
   through a backend-neutral logical-handle layer.
5. **Host build and verification** generates layouts, images, contracts, maps,
   tests, and release artifacts.

```text
routine ID ──► expansion dispatcher ─┬─ GeoRAM page + entry ─► XIP call
                                     └─ REU overlay + entry ─► RAM-slot call

logical handle ──► selected arena backend ─┬─ GeoRAM page/window access
                                           └─ REU extent/DMA work buffer
```

The stable runtime ABI and serialized compiler boundaries do not contain REU
addresses. This keeps standalone exports and host replay independent of the
selected expansion device. Device-specific placement records are generated
from the same routine and arena identities.

### 1.1 Startup Detection and Selection

The common loader probes both devices before loading either sidecar. Each probe
has its own save/probe/restore transaction and publishes only a temporary
candidate record. Probing order is fixed and is not selection order:

1. establish canonical `$35` mapping and save loader/interrupt state;
2. probe and restore GeoRAM using its `$DE00` window and `$DFFE/$DFFF` selectors;
3. probe and restore REU using the REC and the resident probe buffer;
4. validate each candidate independently against its 512-KiB minimum;
5. choose the only valid device, or apply the generated preference when both
   are valid; the default preference is GeoRAM;
6. publish one active-expansion record and discard candidate probe state;
7. load only `GEORAM` or `REU`, according to the selected type.

An invalid preferred candidate is not fatal when the other candidate is valid.
The selection record includes `device_type`, capacity, capability flags,
fingerprint, preference, and selection/fallback reason. After selection the
unselected hardware is never touched again during the session.

## 2. REU REC Hardware Contract

The RAM Expansion Controller occupies I/O2 at `$DF00-$DF0A`:

| Address | Register | Project use |
|---|---|---|
| `$DF00` | Status | Completion/fault sampling; read side effects modeled |
| `$DF01` | Command | Explicit execute; autoload and `$FF00` trigger disabled by default |
| `$DF02-$DF03` | C64 address | Validated normal-RAM source/destination |
| `$DF04-$DF06` | REU address/bank | Generated physical extent address |
| `$DF07-$DF08` | Length | 1..65535, or encoded zero only for an intentional 65536-byte chunk |
| `$DF09` | Interrupt mask | REC interrupts disabled for synchronous gates |
| `$DF0A` | Address control | Increment/fix policy set per operation |

Supported primitives are copy to REU, copy from REU, and verify. Swap may be
added after independent tests but is never needed for correctness. Production
does not use autoload: fully programming every descriptor makes each transfer
inspectable and avoids hidden dependence on controller post-state.

The gate owns REC registers. Unlike the geoRAM selection mirror, REC data
registers are not treated as persistent global context for ordinary code.
Every transfer is described by a validated software descriptor and programs a
complete known register set immediately before execution.

### 2.1 Transfer Descriptor

The internal descriptor contains:

```text
operation
c64_start, logical_length
reu_start, reu_capacity
c64_increment, reu_increment
owner_arena, owner_generation
completion_policy
```

`reu_submit` validates the descriptor before touching the REC. The chunker
then emits physical commands that cannot cross a forbidden C64 range, the
supported REU address ceiling, or the 64-KiB count boundary. Logical length
zero returns success without DMA; it can never accidentally request 64 KiB.

### 2.2 Normal-RAM Range Classes

Generated policy classifies C64 DMA ranges:

- overlay slots: REU-to-C64 only except controlled image construction tests;
- work buffers: bidirectional;
- disk staging: bidirectional but unavailable during its KERNAL call lifetime;
- resident code/state, stack, zero page, vectors, screen/I/O, and active
  runtime data: forbidden unless a specific routine contract grants access.

The validator works on the entire half-open range before starting DMA. A range
may not merely start in an allowed area and continue through a protected one.

## 3. Detection and Session Profile

Detection runs before any expansion-backed directory is trusted:

1. Establish `$01=$35` with I/O visible and enter the pinned REC exclusion.
2. Initialize the REC to the known synchronous, no-autoload, no-interrupt state.
3. Copy candidate REU bytes into the resident probe buffer.
4. Write distinct patterns from the buffer to separated candidate addresses.
5. Read them back and test address-bit aliasing from low to high capacity.
6. Repeat in reverse order in debug builds.
7. Restore saved REU bytes and verify restoration.
8. Restore CPU/interrupt state and publish the profile only after success.

The status size bit is recorded diagnostically but never establishes capacity.
Supported capacity is the largest contiguous, non-aliased range proven by the
probe and representable by the build's physical address format.

The published REU candidate includes controller signature/version observations,
capacity, address width, alias bitmap, allocator/image versions, fingerprint,
and a valid flag. The common selector copies it into the active-expansion
record only if REU wins selection. All public DMA and REU overlay entries
require active device type `reu` and validate relevant bounds against the
immutable record.

## 4. Resident REU Gate

The gate is small and policy-heavy:

- `reu_detect`
- `reu_copy_to`
- `reu_copy_from`
- `reu_verify`
- `reu_copy_reu` through a bounded staging buffer
- `reu_submit_chunked`
- `reu_status_to_error`
- `reu_profile_validate`

Each callable receives logical handles or validated internal descriptors, not
unbounded raw addresses from ordinary callers. Low-level raw-address entries
remain private or test-only.

The resident expansion dispatcher is the only common caller of public REU and
GeoRAM gates. It checks the immutable active device type and routes calls to
`georam_*` or `reu_*` entries. Device-specific gates never probe for the other
device or change the active record. Dispatch entries cover native calls/tail
calls, range ingress/egress, byte/word access, compare/checksum, allocation,
profile query, and fatal invalidation.

### 4.1 Exclusion and Atomicity

A resident ownership byte prevents nested programming of the REC. Interrupts
are masked only while shared descriptor/context state and REC registers are
being changed. Masking does not make a long DMA more responsive—the CPU is
stalled by hardware—so large foreground operations are chunked and the gate
allows pending IRQ service between chunks.

### 4.2 Results and Status

The gate samples status exactly once at the documented completion point and
stores a normalized software result because status reads clear controller
bits. Carry reports success/error through the default assembly ABI; a stable
error byte distinguishes verify, controller, range, ownership, and profile
failures.

### 4.3 REU-to-REU Copy

The original REC has no direct REU-to-REU command. `reu_copy_reu` uses the
generated staging buffer and ordered chunks. Overlap chooses forward or
backward traversal for memmove semantics. The staging buffer is leased for the
operation and cannot alias an overlay slot or active KERNAL buffer.

### 4.4 Mapping and KERNAL Interaction

Public gates enter and leave with canonical `$35`. REC programming occurs only
with I/O visible. KERNAL bridges and DMA are serialized around shared buffers:
disk reads complete into staging RAM, the bridge restores `$35`, then the REU
gate transfers the bytes. No blocking KERNAL call is made while REC ownership
or an overlay-cache critical section is held.

## 5. REU Overlay System and Dual Native Dispatch

### 5.1 Placement Model

Host tooling groups cold routines into service-sized overlays using linked
sizes and the declared call graph. Strongly connected routines are kept
together where possible. Each overlay is linked for one slot class origin and
must fit that class's capacity.

The generated overlay directory contains:

```text
overlay_id, slot_class, reu_start, image_length, bss_policy,
checksum, abi_version, generation, entry_count

routine_id, overlay_id, entry_offset, inputs, outputs, clobbers,
return_kind, callback_edges
```

The slot layout is generated from `linker_policy.json` after resident, runtime,
graphics, buffers, stack, vectors, and installed working-set reservations are
accounted. The first implementation may use one slot if the call graph proves
all nested behavior can return through resident continuations; otherwise the
generator must allocate compatible additional slots or reject the build.

### 5.2 Dispatch

`reu_call_group_n` performs:

1. Validate the installed profile and routine directory.
2. Resolve routine ID to overlay, class, and entry.
3. Find an existing slot hit or an unpinned deterministic victim.
4. Reserve and pin the slot before any DMA.
5. On a miss, DMA the image and initialize its declared BSS policy.
6. Validate checksum/generation in debug builds.
7. Push a context containing slot, prior pin state, return kind, and ABI state.
8. Call the normal-RAM entry and capture documented results.
9. Pop the context and release the pin on all exits.

The dispatcher executes from resident RAM, so replacing a slot never replaces
the code performing replacement. No overlay directly jumps into another slot;
cross-overlay calls always return through the gate.

The outer `expansion_call_group_n` resolves the active device and enters either
the existing GeoRAM indexed-call directory or the REU overlay directory. Both
records originate from the same routine manifest and promise the same ABI, but
their physical placement and call mechanics remain independent. Build checks
reject a routine that is available to one installed backend but absent or ABI-
incompatible in the other.

### 5.3 Pinning, Nesting, and Tail Calls

A slot is pinned from successful reservation until the last context referring
to it exits. Recursive cycles are rejected unless contained in one overlay or
proven against distinct slot capacity. Resident callbacks may re-enter the
overlay gate only when their manifest edge is declared.

Tail transfer is a separate entry. It resolves the destination first, secures
its slot, then releases or reuses the caller context in a failure-atomic order.
If the destination cannot load, the caller remains valid long enough to unwind
through the normal error path.

### 5.4 Cache Policy and Performance

The initial victim policy is deterministic least-recently-used among unpinned
compatible slots, with ties by slot ID. Build reports record overlay bytes,
call edges, expected misses, loaded bytes, and worst-case pin depth. A simpler
single-slot policy is preferred when it satisfies correctness and measured
latency; resident memory is not spent merely to improve a synthetic hit rate.

## 6. Common Arena Interface and REU Data System

### 6.1 Physical Allocation

The common arena layer exposes typed generation handles and chooses the
physical adapter from the active-expansion record. The GeoRAM adapter retains
page allocation and window gates. The REU adapter maps handles to byte extents:

```text
handle -> arena ID + object ID + generation + logical offset
object -> REU start + logical length + capacity + storage class + owner
```

Allocation uses generated alignment classes appropriate to directories,
overlays, compiler streams, and small payloads. The allocator reserves image
extents first, then metadata, then dynamic arenas. Larger devices expand only
dynamic pools.

### 6.2 Work Buffers and Leases

Parser, compiler, editor, and runtime services acquire bounded work-buffer
leases. A lease records buffer ID, owner, arena generation, logical range,
dirty range, and pin depth. Release either commits the dirty range through DMA
or discards it. A pointer is valid only during its lease.

Sequential compilation artifacts are processed in blocks sized from the
available buffer and measured DMA setup cost. Random metadata receives a small
explicit cache only when its hit rate justifies resident bytes.

### 6.3 Transactions

Mutations write new objects or scratch extents first. The transaction validates
checksums and dependent generations, then atomically replaces the directory
record. Failure frees scratch state and preserves the old record. This is the
same publication principle used by line submission and compiled caches.

### 6.4 Strings

String descriptors retain the common storage-class ABI. REU payloads use
variable extents or generated size classes up to the 255-byte language limit.
Operations materialize bounded ranges into a leased buffer. Concatenation
builds a new extent and publishes it only after success. No REU design rule
requires a string to consume a 256-byte physical page.

Dirty caches are optional. If enabled, owner/generation tagging and a single
flush/invalidate routine cover error, eviction, program replacement, `CLR`,
`NEW`, `RUN`, STOP/CONT invalidation, and exit.

## 7. Interrupt and Responsiveness Model

IRQ/NMI code is resident and REC-independent. During actual DMA the CPU is
unable to run, so timer and keyboard service are delayed, not concurrent.
After each chunk the gate leaves the REC critical section and permits pending
IRQ service before continuing.

Chunk policy is workload-specific and generated/configured from measurements:

- installation may use large chunks because no interactive editor exists yet;
- foreground editor and compiler transfers use the accepted interactive cap;
- small runtime transfers execute as one command when below the cap;
- STOP is polled at normal statement/phase boundaries, never synthesized
  inside a DMA stall.

VICE tests measure maximum uninterrupted DMA duration and resulting jiffy,
keyboard, cursor, and STOP latency. The report, not a guessed byte count,
determines the release chunk cap.

## 8. Loader and Artifact Design

The common dual-device build produces:

| Host artifact | D64 name | Purpose |
|---|---|---|
| `basicv3.prg` | `BASICV3` | Common loader, detectors, dispatcher, and normal-RAM payload |
| `georam.bin` | `GEORAM` | GeoRAM XIP pages, directories, and initial arenas |
| `reu.bin` or compressed stream | `REU` | Overlay images, directories, initial arenas |
| `compiler.d64` | — | Installable dual-device release disk |

The PRG retains `2026 SYS2061` and `$080D` machine-code entry. Install order:

1. enter the common loader and establish safe banking;
2. detect and restore both GeoRAM and REU independently;
3. select and publish one active backend;
4. install/decompress the common normal-RAM payload;
5. open and validate only the selected `GEORAM` or `REU` sidecar;
6. install it through GeoRAM window copies or REU DMA staging;
7. verify the selected image and initialize its arena/execution directories;
8. restore `$35` and enter `compiler_init`.

Each sidecar is self-describing but not self-authoritative. Its directory must
match the common build fingerprint plus its device-specific loader manifest.
Compression uses separate versioned GeoRAM and REU stream types. The D64
package requires both sidecars even though a given startup reads only one.

## 9. Common Build and Generated Contracts

`build.ps1` produces the dual-device artifact. `-ExpansionPreference GeoRam`
or `-ExpansionPreference Reu` sets the generated both-present selection policy;
the default is `GeoRam`. This option never removes either detector, gate,
directory, or sidecar from the release.

Generation order extends the common build:

1. validate common, GeoRAM, REU, and selection-policy manifests;
2. allocate zero page with mutually exclusive GeoRAM/REU foreground lifetimes
   but conservatively concurrent IRQ/NMI and startup-detection lifetimes;
3. assemble GeoRAM XIP units and tentative REU overlay units;
4. solve GeoRAM page placement and REU overlay/slot placement independently;
5. generate matching routine directories and the resident dispatch table;
6. generate GeoRAM page arenas and REU extent arenas from common arena IDs;
7. generate the final ld65 configuration and relink;
8. cross-check symbols, entry offsets, sizes, ranges, and checksums;
9. construct `georam.bin`, `reu.bin`, both loader manifests, common PRG, and D64;
10. generate `API.md`, `MAP.md`, size/performance reports, traceability, and
    the final fingerprint;
11. run system contracts and selected tests.

New or generalized checked-in inputs include expansion-selection policy,
overlay declarations, REU address/capacity policy, DMA range classes, and REU
trace records. Generated outputs include `reu_layout.json`,
`overlay_directory.json`, `reu_loader_manifest.json`, `reu.bin`, a common
device-dispatch directory, and device-selection rows
in the common API/MAP/size/requirements reports.

Every resident delta is compared with the geoRAM baseline by component. The
profile report also records overlay slot bytes, dynamic REU bytes, directory
bytes, loader bytes, maximum pin depth, and representative DMA traffic.

## 10. Failure and Diagnostics

All fatal REU failures converge on resident `fatal_reu`. It first prevents new
gate entry, records the normalized error and bounded context, restores `$35`
and incoming interrupt state, and reports without consulting REU arenas or
overlay code. It does not attempt broad repair after a controller/profile or
directory integrity failure.

Recoverable allocation and transaction failures unwind leases, pins, scratch
extents, and contexts in reverse acquisition order. The old publication remains
visible. Debug builds add descriptor logs, overlay events, controller result,
DMA byte/cycle counters, canaries, checksums, and deterministic fault points.
All diagnostic captures belong under `debug/` and are never release inputs.

## 11. Verification Design

### 11.1 Host and Static

- register/command encoding and chunk-boundary unit tests;
- detection alias-profile fixtures;
- overlay packing and adversarial slot/pin-depth graphs;
- REU extent allocation and overlap validation;
- linker symbol/directory/image cross-checks;
- deterministic image, PRG, D64, API, MAP, and traceability tests;
- resident and slot budget comparisons.

### 11.2 Local 6502 Emulator

The local model implements only documented REC behavior needed by the project,
including register visibility, status clear-on-read effects, execute commands,
address controls, the encoded 64-KiB count, copy/verify results, aliasing, and a
DMA stall event. Direct callable tests cover every gate, detector, allocator,
lease, overlay, and recovery routine.

### 11.3 Integration and Functional

Tests cover full detection/install, arena lifecycle, source edit publication,
compiler phase buffering, overlay miss/hit/eviction, nested/callback/tail call,
KERNAL staging, sidecar round-trip, editor operations, and fatal cleanup.
Cross-profile cases compare serialized compiler boundaries and user-visible
results rather than requiring identical internal traffic.

### 11.4 VICE and Hardware

VICE is configured explicitly for each supported REU capacity. Focused tests
observe REC behavior, aliasing, completion/fault status, large transfer timing,
deferred IRQ service, jiffy/keyboard/STOP latency, loader installation, and
nested overlay execution. Real-hardware smoke repeats non-destructive core
cases when hardware is available.

## 12. Completion and Migration

The dual-device profile is complete only when:

- every `RREU-*` trace record is passing;
- all generated and linked contracts agree;
- the minimum capacity and slot layout run the complete supported workload;
- clean installation and language E2E suites pass in VICE with GeoRAM only,
  REU only, both devices under each preference, and neither device;
- cross-profile semantic differences are absent or explicitly resolved;
- resident, dynamic-memory, DMA-latency, and overlay-miss reports satisfy their
  declared budgets;
- standalone exports pass with all expansion devices disabled.

Neither backend is removed from the common artifact. Shared abstractions are
generalized incrementally; GeoRAM XIP and REU RAM-slot execution retain their
separate generated placement and low-level gates.

## 13. Reference Material

- `REU_REQUIREMENTS.md` — normative dual-device / REU EARS requirements
- `REQUIREMENTS.md` — common product requirements (includes dual-device R2/R8)
- `DESIGN2.md` — top-level design index integrating dual-device architecture
- `docs/GEORAM_BANKING.md` — geoRAM backend hardware and call ABI
- `docs/GEORAM_LOADER_DESIGN.md` — geoRAM install stream (CGS1)
- `TASKS.md` / `REU_TASKS.md` — implementation order and TDD conventions
- `docs/TRACEABILITY.md` — EARS and trace-record format
- [Commodore 1764 RAM Expansion Module User's Guide](https://files.commodore.software/reference-material/manuals/commodore-64-manuals/hardware-manuals/1764-ram-expansion-module-users-guide.pdf),
  especially the programmer's reference
- [VICE source tree](https://sourceforge.net/p/vice-emu/code/HEAD/tree/trunk/)
  and its REU test programs, configuration, and observed behavior
