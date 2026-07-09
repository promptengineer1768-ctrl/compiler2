# Compiler 2 Architecture

This document is the high-level architecture map for Compiler 2. It summarizes
load-bearing design decisions and points to the normative documents that own
the details. `../REQUIREMENTS.md` is the compatibility authority,
`../DESIGN2.md` is the main design authority, `../REU_DESIGN.md` owns dual-device
expansion detail, and `../SKELETON.md` maps responsibilities to source files,
manifests, generated artifacts, and tests.

Compiler 2 is a new project. Its manifests, generated memory map, ABI, dual
expansion model, and test contracts are authoritative. Implementation work may
consult external code for proven algorithms (especially math), but placement,
ABI, and semantics always follow this tree's design.

## Architectural Principles

- Keep stock Commodore BASIC V2 behavior compatible unless an extension is
  explicitly enabled.
- Compile every executable BASIC path through one compiler pipeline: stored
  programs, immediate commands, and per-line compile-on-entry use the same
  machinery.
- Keep resident normal-RAM code small, pinned, and hardware-facing; move cold
  compiler/editor/math services to geoRAM by default.
- Use generated contracts for addresses, routine IDs, ABI records, zero-page
  allocation, geoRAM placement, command tables, and traceability.
- Make every important boundary inspectable, replayable, and testable.
- Fail before publishing partially valid state: source edits, compiled code,
  exports, and generated artifacts publish atomically.

## Runtime Layers

Compiler 2 is organized into five practical layers under a **dual-device**
expansion model (geoRAM or REU selected at startup; see `DESIGN2.md` §1 and
`REU_DESIGN.md`).

| Layer | Location | Responsibility |
|---|---|---|
| Common | `src/common/` | Constants, macros, and generated zero-page include plumbing |
| Resident | `src/resident/`, `src/loader/` | IRQ, screen front end, KERNAL bridge, expansion dispatcher, geoRAM gate, REU/REC gate, dual-device detection, RAM-under-I/O gate, loader, fatal path |
| Expansion-native services | `src/geoasm/` (and REU overlay images) | Editor service, tokenizer, parser, semantic checks, compiler pipeline, optimizer, codegen, diagnostics, slow math — XIP under geoRAM, RAM-slot overlays under REU |
| Runtime ABI | `src/runtime/` | Compiled-program helpers for variables, arrays, strings, math, control flow, I/O, errors, inspection, graphics |
| Arena/overlay | `src/arena/` | Dual-device selection record, geoRAM page allocation, REU extent allocation, typed arenas, overlay dispatch, nested call context |

Resident code is the trusted hardware-facing core. It owns IRQ/NMI reachability,
KERNAL banking, visible I/O access, expansion selection, device gates, and clean
failure paths. Expansion-native code is larger and colder; it must enter through
generated gate/dispatcher records and must not assume a stable physical page or
REU address outside its declared call.

## Memory Model

The canonical runtime CPU mapping is `$35`: RAM at `$A000-$BFFF` and
`$E000-$FFFF`, visible I/O at `$D000-$DFFF`, and KERNAL/BASIC ROM hidden. Two
bounded exceptions exist:

- the KERNAL bridge temporarily selects the ROM/I/O map required for approved
  KERNAL calls;
- the RAM-under-I/O gate temporarily exposes RAM under `$D000-$DFFF` for
  graphics-owned memory.

Zero page is generated, not hand assigned. `manifests/zero_page.json` describes
live ranges, fixed reservations, aliases, and KERNAL/IRQ domains.
`tools/zp_alloc.py` builds the interference graph and emits
`build/zp_symbols.inc`, reports, and validation artifacts. Assembly imports
symbols from the generated include rather than using literal project ZP
addresses.

Exact normal-RAM and geoRAM ranges are generated from linker policy and
manifests. `build/MAP.md` is the current-build memory reference; prose docs
describe policies, not final addresses.

## geoRAM Architecture

geoRAM provides a 256-byte window at `$DE00-$DEFF` and selection registers at
`$DFFE`/`$DFFF`. Selecting geoRAM does not change CPU-port banking. Compiler 2
requires a supported profile of at least 512 KiB and treats the installed
capacity/fingerprint as immutable for the session.

The shared page allocator consumes five-byte extent requests containing a
16-bit page count, a 16-bit power-of-two page alignment, and a nonzero arena
owner. It returns an opaque two-byte handle (`slot`, `generation`), not a raw
physical page. Allocator-owned metadata records the extent's start, count, and
owner; generation checks reject stale or double-freed handles. A free-page
bitmap supports arbitrary-order release, first-fit reuse of interior holes,
and exact free-page/largest-run queries across the detected 512 KiB profile.

`arena_init_all` materializes the eight types from generated
`arena_layout.inc`; the current minimum capacities reserve 512 pages in total.
Each directory entry owns an opaque allocator extent plus type, capacity,
generation, canary, and metadata checksum. Arena handles encode directory ID
and generation. Validation checks all metadata and the backing extent, while
reset clears every owned GeoRAM page through the pinned selection gate,
restores the caller's selected block/page, and advances both arena and directory
generations.

Overlay resolution consumes the generated `georam_pages.inc` tables used by
the pinned call gate and the packaged sidecar. Runtime code does not maintain a
parallel hand-written directory. The generator emits the group count, CRC32,
and an eight-bit runtime checksum; `overlay_validate` folds the linked block,
page, and offset tables and rejects drift. `overlay_enter` maintains an
eight-deep selection stack and maps the generated target through
`georam_select`; `overlay_exit` restores the exact caller block/page and reports
underflow.

The program codec accepts only eight-byte `PS` whole-program descriptors. Each
descriptor carries a 16-bit byte length, typed arena ID and generation, starting
relative page, and a zero reserved byte. Entry points validate descriptor
identity, generation, reserved fields, and the complete claimed page extent
before reading or mutating payload bytes; the removed one-byte CPU-record ABI is
rejected.

Decoded programs use one normalized logical representation in geoRAM: repeated
records of `record_length:u16`, `line_number:u16`, token body bytes ending in
zero, followed by a zero `record_length`. Stock import accepts `$0801` BASIC V2
images only after walking the entire linked-line structure across arena pages:
each absolute next pointer must match the actual record boundary, line numbers
must increase, every body must terminate, and the final zero link must consume
the input exactly. Import then normalizes away stock absolute links. Stock
export validates normalized records, clones non-scratch inputs to the scratch
arena, prepends the `$0801` load address, and recomputes every BASIC link
without mutating the published logical arena. Extended-token programs use the
**C2P1** envelope (`DESIGN2.md` §5.2, `manifests/program_formats.json`): magic
`C2P1`, format and ABI versions, a 16-bit body length, an eight-bit additive
checksum stored in a 16-bit field, and six zero reserved bytes; all fields are
validated before in-place body publication. **CGS1** remains the compressed
geoRAM install-stream magic only and must not be reused for program files.

The program store publishes and edits only normalized `PS` streams. The
published root lives in the tokenized-program arena; transactions clone it into
the dedicated program-staging arena and return a typed `PT` handle. `PP`
requests carry the active `PT` pointer plus a one-line normalized `PS`, while
`PD` requests carry the active `PT` pointer plus a line number. Put replaces or
sorted-inserts by line number, delete scans the complete staged stream, and
abort invalidates the transaction without changing publication. Commit
validates the optimistic transaction generation, validates staging, copies all
staged bytes to the published arena, then publishes the descriptor length and
source generation. LOAD uses the same validate-stage-publish rule. Malformed
streams, staging aliases, overflow, forged or stale handles, and failed edits
leave the prior published stream unchanged.

Only the pinned geoRAM gate and approved diagnostics write the selection
registers. The gate maintains a software mirror, saves caller selection and
context, resolves generated routine-directory records, calls or tail-transfers
to the target, and restores the caller page before returning. IRQ/NMI handlers
never select geoRAM.

Every geoRAM-native routine has a generated routine ID, ABI record, page,
entry offset, checksum, return kind, and call-graph edge. Routines fit within
one selected page and do not fall through across `$DEFF`; larger behavior is
split at explicit call boundaries.

## Compiler Pipeline

Compilation has eight explicit boundaries:

1. canonical tokenized source;
2. lexical and statement records;
3. symbols and variable descriptors;
4. control-flow and loop descriptors;
5. typed IR;
6. optimized IR;
7. emitted code, relocations, and runtime dependencies;
8. installed compiled image.

Each boundary has a versioned serialization suitable for host replay tests.
The same pipeline handles stored `RUN`, immediate executable commands wrapped
as temporary programs, and per-line compile-on-entry. There is no interpreter
fallback for dirty code: executable compiled records must match the current
source generation, options, ABI version, dialect, numeric mode, and dependency
fingerprints.

Tokenization uses a generated first-character-indexed trie with token ID,
dialect mask, abbreviation, and longest-match metadata at accepting nodes. The
compiler records lookup size and timing in `keyword_lookup_report.json` so a
linear-scan regression is visible.

Variable runtime helpers operate on typed descriptors rather than raw cell
pointers. A `VD` descriptor records the variable kind, a nonzero descriptor
generation, storage class, and either a direct normal-RAM cell pointer or an
arena handle/page/offset. Direct descriptors require all arena fields to be
zero; arena-backed descriptors validate the scalar or string arena generation
before selecting the page. Store helpers use typed request records (`VI`, `VF`,
and `VS`) that point at a `VD` descriptor and carry only the value metadata
needed for that store. Type mismatches, malformed descriptors, stale arena
handles, unsupported coercions, and lossy numeric coercions return carry set
without writing the target cell.

## Publication and Editing

Line entry is transactional. The editor captures a line, tokenizes and
validates it in scratch storage, compiles it into scratch records, updates
dependency fingerprints, resolves layout, and publishes source plus compiled
records together. Failure leaves the previously published source and compiled
cache intact.

Program load/save uses canonical stock BASIC V2 linked-line format at external
boundaries for stock-only programs. Extended-token programs use the C2P1
envelope that cannot be mistaken for stock linked lines. Loading validates into
scratch storage before replacing the current program directory.

## Runtime ABI and Standalone Export

Compiled code calls only the documented runtime ABI. It never depends on
private compiler workspace addresses, editor state, or physical geoRAM
placement. The ABI covers variables, arrays, strings, math, control flow,
screen/keyboard/file I/O, errors, STOP/CONT, graphics, and inspection.

Runtime error text does not call the stock BASIC error handler. Compiler 2 RAM
occupies the address range hidden by BASIC ROM, and standalone exports must not
depend on that ROM being visible. Instead, the runtime carries the authoritative
stock BASIC V2 error table in its original packed representation: each message
has bit 7 set on its final character. The formatter masks that bit while copying
into a bounded buffer, appends the stock ` ERROR` and optional ` IN <line>`
suffixes, restores channels and text graphics, invalidates continuation/control
state, and enters the active READY environment through resident bridges.

All static output text uses that same packed convention, not only errors. The
last character carries bit 7 and `kernal_print_packed` is the sole emitter; it
masks the marker before output. NUL-terminated and length-prefixed static output
literals, and module-private static-string print loops, are not valid designs.
Dynamic BASIC strings and non-output records are unaffected.

Scalar variables are addressed through stable 12-byte `VD` descriptors. A
descriptor names the variable kind, a non-zero descriptor generation, and a
direct RAM cell or arena-backed cell handle. Runtime variable helpers reject
malformed descriptors, stale arena generations, reserved-byte drift, and type
mismatches before touching payload memory. Arena-backed scalar payloads must
fit wholly inside the selected `$DE00..$DEFF` geoRAM window for their type, so
an integer, float, or string descriptor cell can never spill into ordinary RAM
or a different banking view. Integer, float, and string stores use typed
request records so compiled code never passes an unvalidated raw cell pointer
as a variable handle.

Arrays use one 16-byte `AD` descriptor and no alternate representation. The
descriptor records element kind and size, one- or two-dimensional inclusive
bounds, total element count, descriptor generation, and a contiguous extent in
the manifest array arena. `AM`, `AE`, and `AS` requests provide dimension,
element-access, and typed-store operands. Runtime validation recomputes the
shape and required page count, verifies every owned page, and selects geoRAM
again while copying any element that crosses a 256-byte page boundary.
`arr_free` returns the complete extent to the page allocator and invalidates
the descriptor; stale, malformed, and redimensioned descriptors are rejected.

Strings use one caller-owned 12-byte `SD` descriptor and no raw-pointer or
alternate representation. Bytes 0-1 contain `SD`, byte 2 is a nonzero
descriptor generation, byte 3 is the length, bytes 4-5 identify the string
arena and its generation, bytes 6-7 are the 16-bit relative start page, byte 8
is the payload offset, byte 9 is the page count, and bytes 10-11 hold the
16-bit page-owner token. The current arena has fewer than 256 relative pages,
so the start-page high byte and payload offset are zero. A canonical empty
descriptor retains the current arena ID and generation while its length,
start page, offset, page count, and owner token are zero. Every nonempty string
owns exactly one page in arena 5, so its complete 1-255-byte payload is
selected through a validated arena generation and never crosses a
banking-window boundary.

Compiled callers pass typed records rather than payload pointers: `SA`
allocates a destination and length; `SX` copies source to destination; `SC`
concatenates two sources; `SL`, `SR`, and `SM` perform substring operations;
`SP` compares; `SH` constructs `CHR$`; and `ST` formats FAC into `STR$`.
`str_free`, `str_len`, `str_asc`, and `str_val` accept an `SD` directly. All
mutating operations are alias-safe and publish the destination descriptor only
after successful validation, allocation, and copying. Malformed descriptors,
stale arena generations, wrong owner tokens, double frees, and results longer
than 255 bytes fail with carry set without changing a live destination.

`COMPILE` emits a stock-loadable PRG with a BASIC V2 loader line, native code,
required runtime helpers, relocation/version metadata, variable descriptors,
and the source-free standalone direct environment. A standalone export must
run on a stock C64 without geoRAM. A compiled image accepted in the installed
geoRAM-backed environment is not valid unless the same bytes fit the standalone
budget and pass export system tests.

## Numeric Architecture

Resident `math_core.asm` owns fast compiled arithmetic used by hot paths.
Slower trigonometric, transcendental, and IEEE extension routines are
geoRAM-resident by default.

`math_core.asm` also owns the public `math_to_arg_byte` conversion boundary.
It accepts typed FLOAT/INT1/INT2/INT3 input and returns an unsigned byte only
for exact values in `0..255`; all negative, fractional, larger, or unknown-type
inputs return `ERR_ILLEGAL_QUANTITY` with carry set. The result is a language
operand domain, not an additional numeric variable type. File/channel
arguments, `POKE` values, `WAIT` values and masks, and every future BASIC
operand governed by the stock byte-argument contract must call this helper
instead of implementing subsystem-local narrowing. Address operands remain a
separate unsigned 16-bit conversion contract.

Adaptive arithmetic uses `FLOAT`, `INT1`, `INT2`, and `INT3` variable payload
types, but those tags do not automatically become command argument or loop
control field types. FOR/NEXT control operands are signed INT2 start, limit,
and step values; the loop variable may still be FLOAT, INT1, INT2, or INT3 and
must be stored and compared according to its assigned payload type. Numeric
comparison helpers sign-extend narrower signed operands before mixed-width
ordering, compare INT3 operands unsigned, and promote mixed signed/unsigned or
float cases when that is required to preserve BASIC-visible ordering.

Trig, transcendental, and IEEE routines must satisfy Compiler 2 accuracy and
ABI contracts (`docs/IEEE754.md`, generated runtime ABI). Implementations may
reuse proven external algorithm sources when they fit those contracts, but
must use Compiler 2 generated ZP symbols, manifests, expansion placement, and
ABI — never fixed addresses from another project.

IEEE mode changes arithmetic/classification behavior while keeping the stock
BASIC-compatible internal numeric layout and stock-compatible formatting.
Core arithmetic is exactly rounded to the Compiler 2 destination format;
transcendentals target the documented 2 ULP accuracy bound.

## Build and Generated Contracts

The canonical build entry point is `build.ps1`. Production assembly uses
`ca65` and `ld65`; Python tools generate inputs, validate outputs, and render
current-build references.

Build order is contract-first:

1. validate tool paths, versions, and manifests;
2. generate zero-page symbols, interference reports, dual-device routine
   directories (geoRAM + REU overlays), expansion dispatch, runtime ABI, arena
   layout, command tables, test entries, and keyword trie reports;
3. generate the ld65 configuration from checked-in linker policy plus generated
   geoRAM page and REU slot/overlay placement;
4. assemble and link;
5. validate maps, labels, manifests, binaries, budgets, and stale generated
   files;
6. package `BASICV3`, `GEORAM`, `REU`, and D64 artifacts;
7. generate `build/API.md`, `build/MAP.md`, and traceability matrices;
8. run system contracts and the selected test suite (including dual-device
   selection cases when enabled).

`build/` is generated and safe to delete. `debug/` holds temporary captures and
is never a release input.

## Testing Architecture

Tests are layered by scope and environment:

- host tool, format, static, and generated-artifact tests;
- local 6502 emulator unit tests for callable assembly entries;
- local emulator integration tests with geoRAM and REU models;
- VICE snapshot-backed application tests;
- focused VICE hardware tests for keyboard, IRQ, timers, banking, expansion
  devices, and dual-device selection.

Every callable assembly routine appears in the production entry manifest or
test-entry manifest and has direct unit coverage. System contract tests verify
whole-build invariants such as toolchain versions, deterministic generation,
linker/memory maps, banking policy, generated metadata, binary artifacts,
resource budgets, test environment assumptions, and traceability.

E2E language tests are organized by profile (`basicv2`, `basicv3`,
`basicv35`, `ieee`), by functions versus statements, and by shared execution
modes (`immediate`, `program`, `compile`). Stock BASIC behavior comes from
versioned VICE fixtures; Compiler 2-only IEEE behavior uses the specification
and an independent IEEE oracle.

## Ownership Map

| Concern | Primary documents |
|---|---|
| Requirements and compatibility | `../REQUIREMENTS.md`, `../REU_REQUIREMENTS.md` |
| Detailed architecture | `../DESIGN2.md`, `../REU_DESIGN.md`, this document |
| Source/module skeleton | `../SKELETON.md` |
| Build and artifacts | `BUILD.md`, `GENERATED_REFERENCE.md` |
| geoRAM banking and loader | `GEORAM_BANKING.md`, `GEORAM_LOADER_DESIGN.md` |
| REU / dual-device expansion | `../REU_DESIGN.md`, `../REU_REQUIREMENTS.md` |
| Memory and zero page | `MEMORY_BUDGETS.md`, `ZERO_PAGE.md` |
| KERNAL/IRQ banking | `KERNAL_ABI.md` |
| Compiler pipeline | `INCREMENTAL_COMPILATION.md`, `LOOP_OPTIMIZATION.md` |
| Standalone export | `COMPILE_EXPORT.md` |
| Testing and traceability | `TESTING.md`, `TRACEABILITY.md`, `../TESTS.md` |
| Implementation order | `../TASKS.md` |
