# Compiler 2 Dual GeoRAM/REU Requirements

## 0. Status, Scope, and EARS Convention

`REQUIREMENTS.md` is authoritative for language behavior, the runtime ABI,
standalone `COMPILE` exports, the canonical CPU map, KERNAL use, testing, and
build reproducibility. `REQUIREMENTS.md` §§2, 2.1, 7, and 8 state the dual-device
product model at summary level; **this document** is authoritative for the
detailed dual-device EARS requirements (detection, selection, REC/DMA, REU
overlays, REU arenas, packaging, REU verification). The two documents must
agree: neither describes a geoRAM-only release product. This document defines
requirements for one `BASICV3` installation that detects GeoRAM and REU
hardware at startup and runs the Compiler 2 development environment with either
supported device. Design detail is in `REU_DESIGN.md` and the expansion
sections of `DESIGN.md`.

The release D64 contains one common `BASICV3` PRG and the device payloads needed
by both backends. Runtime detection and selection are mandatory; separate
GeoRAM-only and REU-only user-facing builds do not satisfy this document.

Every normative statement below uses an EARS form and has a stable ID:

- ubiquitous: **The dual-device profile shall ...**
- event-driven: **When ... the dual-device profile shall ...**
- state-driven: **While ... the dual-device profile shall ...**
- optional-feature: **Where ... is enabled, the dual-device profile shall ...**
- unwanted behavior: **If ... the dual-device profile shall ...**

The implementation priority remains: correctness, minimum permanently resident
normal-RAM footprint, maximum usable expansion capacity, then execution time.

## RREU-1. Product and Compatibility

**RREU-1.1** The dual-device profile shall provide the same Compiler 2
language, editor, compiler, runtime ABI, and supported numeric profiles when
GeoRAM or REU is selected.

**RREU-1.2** When identical source, options, dialect, and numeric profile are
compiled through GeoRAM and REU backends, the dual-device profile shall preserve all
user-visible semantics required by `REQUIREMENTS.md`.

**RREU-1.3** The dual-device profile shall treat REU memory as DMA-accessible storage
and shall not assume that the 6510 can directly address or execute REU memory.

**RREU-1.4** When `COMPILE` exports a program, the dual-device profile shall produce a
stock-C64-compatible artifact that has no REU, geoRAM, editor, source-arena, or
installed-environment dependency.

**RREU-1.5** The dual-device profile shall use stable logical handles, routine IDs, ABI
records, and publication generations that do not expose physical REU addresses
to compiled programs or user-visible state.

**RREU-1.6** If REU support would require a common-language semantic change,
the dual-device profile shall reject that change until `REQUIREMENTS.md` explicitly
authorizes it.

## RREU-2. Supported Hardware and Capacity

**RREU-2.1** The dual-device profile shall support a Commodore 64-compatible RAM
Expansion Unit whose RAM Expansion Controller is visible at `$DF00-$DF0A`.

**RREU-2.2** The first supported REU backend shall require at least 512 KiB of
non-aliased expansion memory.

**RREU-2.3** When a larger supported REU is detected, the dual-device profile shall use
the additional capacity only for generated overlay storage, arenas, caches,
metadata, or scratch space and shall not change language semantics.

**RREU-2.4** The build shall declare the minimum REU capacity and the maximum
address width supported by its generated allocator and loader.

**RREU-2.5** When installation succeeds with REU selected, the dual-device profile shall publish a
session profile containing detected capacity, aliasing results, controller
compatibility, allocator format version, and an integrity fingerprint.

**RREU-2.6** If no compatible REU is present, the detected capacity is below
the declared minimum, or required address bits alias, the dual-device profile
shall mark REU unavailable and shall continue with a separately detected
supported GeoRAM when one is available.

**RREU-2.7** If the selected REU profile changes after installation, the
dual-device profile shall stop new DMA and allocation, invalidate
expansion-backed state,
restore the canonical machine state, and require reinstallation.

**RREU-2.8** When `BASICV3` starts, the dual-device profile shall probe GeoRAM
and REU non-destructively before selecting an expansion backend.

**RREU-2.9** When exactly one supported expansion device is detected, the
dual-device profile shall select that device and shall load only its payload.

**RREU-2.10** When both supported devices are detected, the dual-device profile
shall select the device specified by the generated startup preference and
shall default to GeoRAM when no preference is configured.

**RREU-2.11** If a preferred device is absent, undersized, aliased, or fails
restoration, the dual-device profile shall select the other independently
validated device when available and shall record the fallback reason.

**RREU-2.12** If neither device passes its minimum-capacity and restoration
checks, the dual-device profile shall abort before trusting any expansion
directory, overlay, editor, or compiler state.

**RREU-2.13** When a backend is selected, the dual-device profile shall publish
one active-expansion record containing device type, capacity, capabilities,
format versions, fingerprint, and selection reason.

**RREU-2.14** While one backend is active, the dual-device profile shall leave
the unselected device unchanged after detection and shall not allocate, load,
execute, or cache state through it.

## RREU-3. REC Register and DMA Contract

**RREU-3.1** The pinned REU gate shall be the only production component that
writes REC registers `$DF01-$DF0A`; approved diagnostics may write them only
under the same exclusion and restoration contract.

**RREU-3.2** When the REU gate programs a transfer, it shall explicitly set the
command, C64 base address, REU base address, transfer length, interrupt mask,
and address-control registers required by that transfer.

**RREU-3.3** The REU gate shall disable `$FF00` command triggering and shall
start production transfers only by an explicit execute write to `$DF01`.

**RREU-3.4** The REU gate shall support C64-to-REU copy, REU-to-C64 copy, and
verify operations; swap shall be optional and shall not be required for
correctness.

**RREU-3.5** When a logical transfer is zero bytes, the REU gate shall perform
no DMA and shall not encode it as the REC's 64-KiB zero-length count.

**RREU-3.6** When a logical transfer is larger than one safe REC operation or
crosses a generated C64/REU boundary, the REU gate shall split it into ordered
chunks without address wrap, protected-range access, or length ambiguity.

**RREU-3.7** Before starting DMA, the REU gate shall validate the complete C64
range, REU range, direction, length, storage ownership, and overlap policy.

**RREU-3.8** The REU gate shall not use REC interrupts for normal synchronous
transfers and shall program the interrupt mask to the generated safe default.

**RREU-3.9** When the gate reads `$DF00`, it shall account for the
read-to-clear end-of-block, verify-fault, and interrupt-pending status bits and
shall not require a later observer to see cleared status.

**RREU-3.10** When a DMA operation completes, the REU gate shall verify the
expected completion state and shall convert controller faults into one
documented error result.

**RREU-3.11** While a gate operation owns the REC, no foreground, IRQ, NMI,
diagnostic, loader, or error path shall reprogram the REC.

**RREU-3.12** The public REU gate ABI shall document inputs, outputs, carry/error
result, registers and flags clobbered, zero-page use, REC side effects, C64 and
REU range effects, CPU-port behavior, and interrupt behavior.

## RREU-4. Detection and Non-Destructive Installation

**RREU-4.1** When installation probes the REU, the detector shall establish or
assert the canonical I/O-visible CPU mapping before accessing `$DF00-$DF0A`.

**RREU-4.2** Before modifying a candidate REU location, the detector shall save
the corresponding data through a bounded normal-RAM probe buffer.

**RREU-4.3** The detector shall determine usable capacity by testing persistence
and address-bit aliasing and shall not infer capacity solely from the REC status
register's size bit.

**RREU-4.4** When detection succeeds or fails, the detector shall restore every
modified C64 byte, every modified REU byte, processor status, CPU-port mapping,
and the gate's documented REC idle configuration.

**RREU-4.5** Where debug detection is enabled, the detector shall repeat probes
with reversed patterns and shall reject floating-bus or mirrored false
positives.

**RREU-4.6** If restoration cannot be verified, the detector shall fail
installation and shall not publish REU as usable; startup may continue only
with a separately validated GeoRAM.

## RREU-5. Normal-RAM Overlay Execution

**RREU-5.1** When REU is selected, the dual-device profile shall execute expansion-backed compiler, editor,
diagnostic, and cold-math code only after copying a complete generated overlay
into a normal-RAM execution slot.

**RREU-5.2** The build shall generate overlay IDs, routine IDs, slot classes,
load addresses, entry offsets, sizes, checksums, ABI versions, return kinds,
and call-graph edges from checked-in manifests and linked symbols.

**RREU-5.3** The linker shall link each overlay for the normal-RAM origin of
its declared slot class.

**RREU-5.4** The build shall derive slot count, origins, and capacities from the
validated linker and memory policy and shall not assume two fixed 8-KiB slots.

**RREU-5.5** The minimum supported slot configuration shall be proven capable
of executing every reachable overlay call path, including nesting, callbacks,
tail transfers, error unwind, and KERNAL bridge use.

**RREU-5.6** When a routine is called, the overlay gate shall resolve its
generated overlay and entry record, ensure the overlay is resident in a
compatible slot, pin the slot, invoke the entry, and release the pin on every
normal or error return.

**RREU-5.7** If no compatible unpinned slot is available, the overlay gate
shall return a deterministic overlay-depth error before overwriting executable
code or changing published state.

**RREU-5.8** While an overlay is executing or may return through a slot, the
slot shall remain pinned and shall not be evicted or overwritten.

**RREU-5.9** When a slot miss occurs, the overlay gate shall DMA the entire
overlay image from its validated REU extent before transferring control to it.

**RREU-5.10** Where debug overlay validation is enabled, the overlay gate shall
verify the loaded checksum and generation before executing the entry point.

**RREU-5.11** Returning calls and tail transfers shall use distinct,
stack-correct paths; a tail transfer shall release or reuse the caller's frame
and pin so the destination returns to the original caller.

**RREU-5.12** The generated call-graph validator shall reject recursion,
re-entry, or nested slot demand that exceeds the declared slot and context
budgets unless an explicit tested spill strategy exists.

**RREU-5.13** The overlay cache replacement policy shall be deterministic for
identical build and execution inputs.

**RREU-5.14** The resident expansion dispatcher shall be the only common
production entry for expansion-native calls, tail transfers, data access,
allocation, and active-profile queries.

**RREU-5.15** When GeoRAM is selected, the expansion dispatcher shall use the
generated GeoRAM execute-in-place directory and shall not reserve or load REU
overlay slots.

**RREU-5.16** When REU is selected, the expansion dispatcher shall use the
generated REU overlay directory and shall not select GeoRAM pages after startup.

**RREU-5.17** The build shall require every dual-device routine ID to have
ABI-compatible GeoRAM and REU records, including inputs, outputs, clobbers,
return kind, callback edges, and error behavior.

## RREU-6. Arenas, Handles, and Data Movement

**RREU-6.1** The dual-device profile shall preserve the typed, generation-stamped arena
model and transactional publication rules defined by `REQUIREMENTS.md`.

**RREU-6.2** The REU allocator shall manage byte extents or generated allocation
units and shall not expose REC bank/address fields outside the expansion-memory
backend.

**RREU-6.3** The allocator shall reserve disjoint extents for overlay images,
overlay metadata, arena directories, tokenized source, compiled cache,
variables, arrays, strings, compiler IR, diagnostics, and scratch storage.

**RREU-6.4** When a REU arena handle is resolved, the dual-device profile shall validate
arena ID, format, generation, logical bounds, physical extent bounds, and
ownership before DMA.

**RREU-6.5** The data API shall provide byte, word, range read/write, compare,
checksum, normal-RAM ingress/egress, and REU-to-REU logical copy operations.

**RREU-6.6** When REU-to-REU data is copied, the implementation shall use a
bounded normal-RAM staging buffer or a separately proven controller operation
and shall preserve memmove semantics where ranges overlap.

**RREU-6.7** The implementation shall batch compiler and editor accesses into
bounded working buffers when measurement shows repeated small DMA setup would
dominate the operation.

**RREU-6.8** No normal code shall retain a pointer into a staging or overlay
buffer after the owning pin, lease, or generation ends.

**RREU-6.9** If allocation, transfer, validation, or publication fails, the
dual-device profile shall leave the previously published source, compiled
image, arena directory, and variable state intact unless the operation was
explicitly documented as destructive.

**RREU-6.10** The common arena API shall dispatch each logical operation only
to the selected backend and shall preserve the same arena IDs, handle fields,
generation rules, ownership, and transaction semantics on GeoRAM and REU.

## RREU-7. Strings and Cached Data

**RREU-7.1** The dual-device profile shall preserve the common string descriptor's
storage class, length, capacity, ownership, and generation fields.

**RREU-7.2** The REU string allocator shall use variable extents or generated
size classes and shall not require one 256-byte allocation per materialized
string solely to imitate geoRAM paging.

**RREU-7.3** When a string operation requires REU-backed payload bytes, the
runtime shall materialize only a bounded range into an owned normal-RAM buffer
and shall commit mutations through the common publication path.

**RREU-7.4** If a dirty REU cache is enabled, the dual-device profile shall tag it with
owner and generation and shall use one tested flush/invalidate path for
eviction, errors, program replacement, `CLR`, `NEW`, `RUN`, STOP/CONT
invalidation, and exit.

## RREU-8. CPU Mapping, Interrupts, and Responsiveness

**RREU-8.1** The dual-device profile shall retain `$01=$35` as the canonical runtime
CPU-port mapping and shall access REC registers only while I/O is visible.

**RREU-8.2** The IRQ and NMI handlers and every routine reachable from them
shall remain pinned in normal RAM and shall not program or depend on the REC.

**RREU-8.3** While REC DMA owns the bus, the dual-device profile shall assume that the
6510 cannot execute IRQ, NMI, editor, timer, or foreground code.

**RREU-8.4** When DMA releases the bus, the dual-device profile shall permit pending
interrupt service without requiring synthetic jiffy or keyboard updates.

**RREU-8.5** The DMA scheduler shall use measured bounded chunk sizes for
interactive foreground operations and shall report worst-case IRQ, jiffy,
keyboard, cursor, and STOP latency for representative transfers.

**RREU-8.6** If measured DMA latency violates the project's accepted
responsiveness budget, the dual-device profile shall reduce foreground chunk size or
restructure the operation before release.

**RREU-8.7** The REU gate shall restore the incoming interrupt-enable state and
canonical CPU mapping on every success and error exit.

**RREU-8.8** While a KERNAL bridge is active, no REU DMA shall target a C64
range whose contents or mapping the bridge may concurrently use.

## RREU-9. Loader, Images, and Packaging

**RREU-9.1** The build shall produce one `basicv3.prg`, `georam.bin`, `reu.bin`,
and an installable D64 containing Commodore files `BASICV3`, `GEORAM`, and
`REU`.

**RREU-9.2** The REU loader shall begin at `$080D` behind the standard
`2026 SYS2061` BASIC loader line.

**RREU-9.3** When the common loader starts, it shall detect both devices,
select one supported backend, install the normal-RAM payload, load only the
selected backend's verified sidecar, initialize its directories and execution
model, restore canonical banking, and enter `compiler_init`.

**RREU-9.4** The REU sidecar shall contain a versioned header, capacity
requirement, overlay and arena extent directory, lengths, checksums, ABI/schema
versions, and build fingerprint sufficient to reject a mismatched loader.

**RREU-9.5** When loading a sidecar through KERNAL file I/O, the loader shall
separate disk-read buffers from DMA destination ranges and shall not assume
that KERNAL ROM calls and REC programming can occur concurrently.

**RREU-9.6** If any sidecar header, extent, checksum, version, capacity, or
fingerprint check fails, the loader shall abort without entering the editor.

**RREU-9.7** Where sidecar compression is enabled, the build shall use a
versioned REU stream format with round-trip verification and a bounded loader
buffer; uncompressed linked images shall remain authoritative for maps,
symbols, and debugging.

**RREU-9.8** The package validator shall verify PRG load ranges, sidecar order
and padding, extent bounds, D64 names, checksums, and agreement among the D64,
loader manifest, overlay directory, arena layout, and build manifest.

## RREU-10. Build and Generated Contracts

**RREU-10.1** The build shall include both GeoRAM and REU startup paths in the
same `BASICV3` artifact and shall expose only the deterministic startup
preference as a build option.

**RREU-10.2** The dual-device profile shall use `ca65` and `ld65` through `build.ps1`
and shall record their actual versions in the build manifest.

**RREU-10.3** The build shall generate and validate the REU memory inventory,
overlay placement, slot layout, routine directory, arena layout, loader
manifest, size report, API, map, and requirement matrix.

**RREU-10.4** The build shall reject overlap, address overflow, unsupported REU
address width, slot overflow, unresolved routine IDs, entry points outside an
overlay, excessive pin depth, stale checksums, or inconsistent ABI versions.

**RREU-10.5** Every permanently resident byte added for REU support shall be
reported by component with a delta and a justification for why it cannot be
overlay-backed.

**RREU-10.6** Clean and no-change incremental dual-device builds with identical inputs
shall produce byte-identical release artifacts.

**RREU-10.7** Generated REU artifacts shall never become normative inputs to
their own generation.

## RREU-11. Errors, Diagnostics, and Recovery

**RREU-11.1** The dual-device profile shall define distinct errors for absent device,
undersized device, aliasing, REC fault, verify mismatch, invalid extent,
overlay-depth exhaustion, corrupt directory, incompatible sidecar, and stale
handle.

**RREU-11.2** If a fatal REU error occurs after REU selection, the dual-device profile
shall prevent further overlay execution and arena DMA before reporting the
error through pinned resident code.

**RREU-11.3** The fatal path shall not depend on REU-resident code, REU-backed
diagnostics, a valid expansion arena directory, or an available overlay slot.

**RREU-11.4** Where debug tracing is enabled, the dual-device profile shall record
bounded DMA descriptors, overlay loads/evictions/pins, arena generations,
controller status, and timing without making trace storage a release input.

**RREU-11.5** If debug fault injection requests a DMA, allocation, verify,
sidecar, or overlay failure, the dual-device profile shall take the same recovery path
as the corresponding real failure.

## RREU-12. Verification and Acceptance

**RREU-12.1** Every callable REU assembly routine shall have direct unit
coverage through production or test-only generated entries.

**RREU-12.2** The local emulator shall model REC registers, execute/autoload
semantics used by the project, status read side effects, address controls,
length-zero meaning 64 KiB, DMA directions, verify faults, aliasing profiles,
and CPU stall boundaries required by the tests.

**RREU-12.3** Integration tests shall cover detection, every DMA direction,
boundary splitting, allocator lifecycle, overlay miss/hit/eviction, nested
calls, callbacks, tail transfers, error unwind, and transactional publication.

**RREU-12.4** System contract tests shall cover generated placement, slot and
pin-depth sufficiency, linker ranges, REU image integrity, packaging,
reproducibility, size budgets, API/MAP consistency, and traceability.

**RREU-12.5** VICE tests shall cover every supported capacity profile, real REC
register visibility, DMA completion and verify behavior, capacity aliasing,
large-transfer timing, pending IRQ service, keyboard/jiffy/STOP responsiveness,
loader installation, and at least one nested overlay canary.

**RREU-12.6** Where practical real REU hardware is available, a hardware smoke
suite shall repeat detection, save/restore, DMA directions, verify, boundary,
and loader tests without replacing VICE or lower-layer coverage.

**RREU-12.7** The dual-device profile shall run the existing critical language E2E
matrix without weakening cases, modes, reference provenance, or expected
semantics.

**RREU-12.8** No REU requirement shall be marked complete solely by a static
source-pattern test.

**RREU-12.9** The generated requirement matrix shall map every `RREU-*` ID to
its design section, implementation component, applicable test layers, status,
and last passing build fingerprint.

**RREU-12.10** The VICE startup matrix shall cover GeoRAM only, REU only, both
devices under each startup preference, invalid preferred-device fallback, and
neither device, using the same `BASICV3` PRG and matching sidecar set.

**RREU-12.11** The cross-device differential suite shall run common editor,
compiler, runtime, save/load, error, and export scenarios once with GeoRAM
selected and once with REU selected and shall report every unexplained
user-visible difference as a failure.

## RREU-13. Acceptance Gate

**RREU-13.1** When the dual-device profile is declared releasable, the build shall pass
all REU unit, integration, functional, system, VICE hardware, smoke, and
applicable language E2E tests from a clean tree.

**RREU-13.2** When the dual-device profile is declared semantically equivalent, the
cross-profile differential suite shall show no unexplained user-visible
difference between geoRAM and REU development environments.

**RREU-13.3** If any requirement, generated contract, test node, or supported
capacity or device-selection profile remains planned or failing, the dual-device profile shall not be
reported as complete.
