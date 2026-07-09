# geoRAM Banking and Native Calls

## Purpose

This document defines the geoRAM hardware contract used by Compiler 2: window
access, non-destructive detection, selection ownership, and the indexed
native-call directory. When the dual-device profile selects REU instead, see
`../REU_DESIGN.md`; this file remains the geoRAM backend authority.

## Hardware Model

### Nominal CPU Mapping

Compiler 2's normal CPU mapping is fixed at `$01 = $35` under the standard
DDR:

- RAM at `$0000-$CFFF`, except the 6510 port registers at `$0000-$0001`;
- I/O at `$D000-$DFFF`;
- RAM at `$E000-$FFFF`;
- BASIC and KERNAL ROMs banked out.

The geoRAM window and registers are already visible in this mapping. Selecting,
reading, writing, or executing a geoRAM page must not change the CPU-port
mapping.

RAM `$FFF9-$FFFF` is reserved. `$FFF9` is a project guard byte and
`$FFFA-$FFFF` are the NMI, RESET, and IRQ/BRK hardware vectors.

geoRAM exposes one 256-byte window and two selection registers:

| Address | Purpose |
|---|---|
| `$DE00-$DEFF` | selected 256-byte data/code window |
| `$DFFE` | page within a 16 KiB block, normally `0..63` |
| `$DFFF` | 16 KiB block |

A logical page is:

```text
logical_page = block * 64 + page
byte_address = logical_page * 256 + offset
```

Code that needs RAM beneath I/O must use the dedicated RAM-under-I/O gate. That
gate is exceptional: it saves the transition state, temporarily selects the
all-RAM mapping, performs a bounded transfer, and restores `$35`. It masks IRQ
while I/O is hidden and restores the incoming interrupt state only after I/O is
visible again.

Normal geoRAM call and data gates assume the canonical mapping and do not save,
modify, or restore `$00` or `$01`. Debug builds assert `$35` at their public
boundaries.

## Detection

Detection is non-destructive and runs before arenas are trusted.

The detector must:

1. assert or establish the canonical I/O-visible mapping during installation;
2. save processor status, selected block/page, and probe bytes;
3. select two candidate pages;
4. write different patterns and verify that reads persist and remain distinct;
5. probe candidate block address bits to determine aliasing/capacity;
6. restore every modified byte, selection, and processor status on success or
   failure;
7. run a second pattern order in debug builds to catch floating-bus false
   positives.

Interrupts may be masked only during the small save/probe/restore critical
section. The original interrupt state must be restored.

Capacity is accepted only if it meets the build's declared minimum and maps to
a supported whole number of 16 KiB blocks. An aliasing candidate means that
address bit is not implemented; it is not permission to overwrite the mirrored
page.

## Selection Ownership

No module writes `$DFFE` or `$DFFF` directly except the pinned geoRAM gate and
approved diagnostic code.

The gate maintains a software mirror of the selected block/page. Debug builds
compare the mirror with hardware before and after public calls. A mismatch is
an integrity error because it means code bypassed the ownership rule.

IRQ and NMI handlers must not select geoRAM. This makes the foreground selected
page stable across interrupts and permits long native geoRAM routines to run
with normal timer and keyboard service enabled.

## Native Routine Rules

Native routines are assembled for the `$DE00` window.

Each routine must:

- fit completely inside one selected page;
- enter only at a generated entry offset;
- return or tail-transfer through a declared path;
- use resident gates for cross-page calls;
- avoid fallthrough across `$DEFF`;
- avoid self-modifying a shared read-only page;
- declare all zero-page, register, flag, stack, and arena effects.

Routines that need more code are split at explicit call boundaries. Large
read-only tables use data pages and byte/word access helpers.

## Compact Indexed Call Directory

Routine IDs are divided into groups of 256. A call site uses an 8-bit index and
a group-specific resident entry:

```asm
ldx #routine_index
jsr georam_call_group_n
```

For each group, the build generates:

- a 256-byte target-page array;
- a 256-byte entry-offset array;
- a compact block base/threshold descriptor;
- ABI metadata and a checksum.

The arrays normally live in reserved geoRAM directory pages. The gate saves the
caller's selection, maps the directory pages to resolve the tuple, and then maps
the target. A hot group may use an explicitly budgeted RAM cache.

The block-threshold form is retained because packed routines are normally
ordered through a small number of contiguous blocks. If placement becomes too
fragmented, the generator must emit an explicit block table rather than
silently truncating the mapping.

## Returning Call

`georam_call_group_n` is a real returning call:

1. assert the canonical CPU mapping and save caller block/page plus required
   registers/status;
2. resolve the target from generated tables;
3. map and call the target from resident code;
4. capture target result registers/flags;
5. restore caller page/block before control can return into caller geoRAM code;
6. restore the incoming interrupt state;
7. return the documented target results.

The context record is pushed for every nesting level. A fixed-depth context
stack must detect overflow before changing the selected page. The configured
depth is derived from the overlay call graph plus an explicit safety margin.

## Tail Transfer

A tail transfer is not an alias for a returning call. It must resolve the
target from the generated directory, select the destination page, consume the
current context frame, and `JMP` to the geoRAM entry. The destination routine's
normal `RTS` returns directly to the original caller; the resident gate must
therefore reject missing directory entries before consuming the frame.

Build tests inspect stack depth for:

- RAM to geoRAM call;
- geoRAM to geoRAM nested call;
- geoRAM to RAM callback and re-entry;
- geoRAM tail transfer;
- error unwind at every nesting depth.

## Register ABI

One default ABI is preferable to many aliases with unverified names:

- the index register used for dispatch is consumed;
- target inputs and outputs are declared per routine;
- carry is the standard success/error result where applicable;
- decimal mode is clear at public boundaries;
- the incoming interrupt-enable state is restored;
- undocumented preservation is forbidden.

If a wrapper promises to preserve a register or status bit, it must contain
real preservation code and a local-emulator test. Naming an alias
`preserve_x` is not evidence.

## Interrupts

The gate may briefly mask IRQ while changing context-stack state and selection
registers. It should restore the caller's interrupt state before executing an
IRQ-safe target.

Targets marked IRQ-masked must be bounded and cannot contain editor, compiler,
or transcendental work. Long operations are IRQ-safe by construction because
the pinned IRQ does not touch geoRAM.

## Data Access

Data helpers use logical handles and preserve the caller selection:

- read byte/word;
- write byte/word;
- copy between normal RAM and geoRAM;
- copy between geoRAM pages through a bounded resident buffer;
- compare/checksum;
- allocate/free page extents.

The resident `georam_copy_pages` descriptor uses the same leading fields as
the RAM copy helpers. `X/Y` point to the source descriptor, whose offset, page,
and length identify the source span. The source descriptor's pointer fields
point to a destination descriptor; that destination descriptor supplies the
destination offset and page. The helper copies one byte at a time through
resident scratch and restores the incoming geoRAM selection on success or
failure.

No normal code may retain a raw `$DE00` pointer across a gate call.

## Build-Time Proofs

The build rejects:

- a body or instruction crossing the window boundary;
- duplicate or missing routine IDs;
- directory records outside detected/build capacity;
- entry offsets outside their page;
- a cross-page branch not rewritten as a gate call;
- recursion beyond the configured context depth;
- undeclared RAM callbacks;
- stale directory checksums or ABI versions.

Routine placement is a constrained 256-byte bin-packing problem. A simple
first-fit pass can fail because of fragmentation even when a valid placement
exists, and placement that ignores the call graph can amplify gate overhead.
The generator uses deterministic size/call-aware ordering plus bounded local
search/backtracking, preferring strongly connected callers on nearby pages
without weakening any page-boundary or ownership check. Failure reports the
unplaced routines and remaining extents rather than only "out of geoRAM".

## Required Tests

Static tests validate generated placement and call graphs. The local emulator
validates selection persistence, nested calls, returns, tail calls, callbacks,
canonical CPU-port preservation, status/register contracts, and geoRAM data
persistence.
VICE validates real hardware mapping, interrupts during long overlay work, and
at least one nested-call canary on each supported capacity profile.
