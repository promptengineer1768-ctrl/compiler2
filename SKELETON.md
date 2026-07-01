# Compiler 2 Source Skeleton

This document is the implementation skeleton for `DESIGN2.md`. It assigns
every design responsibility to a checked-in manifest, assembly module, host
tool, generated artifact, and test layer. It is not itself an implementation:
a row in a routine table is an implementation obligation, not evidence that
the behavior exists.

`REQUIREMENTS.md` remains authoritative. Focused documents named by
`DESIGN2.md` refine the contracts summarized here. Generated manifests are the
source of truth for concrete addresses, IDs, ABI records, and sizes; prose in
this file must not duplicate generated values as if they were current output.

## 0. Validation Status

The original skeleton did **not** completely realize the design. This revision
closes the structural gaps found during the design audit:

| Design responsibility | Owning implementation |
|---|---|
| Stock/extended tokenized file formats and transactional replacement | `geoasm/program_codec.asm`, `geoasm/program_store.asm`, `manifests/program_formats.json` |
| Eight replayable compiler boundaries and atomic source/code publication | `geoasm/compiler_pipeline.asm`, `geoasm/incremental.asm` |
| Direct/program classification and one immediate/program compiler path | `geoasm/direct_dispatch.asm`, generated command table |
| Source-free `COMPILE` export and its restricted shell | `geoasm/compile_export.asm`, `runtime/inspection.asm`, standalone linker profile |
| DOS wedge before BASIC tokenization | `geoasm/dos_wedge.asm`, `runtime/wedge.asm`, resident input dispatch |
| Graphics ownership and one exit path | `runtime/graphics.asm`, generated memory policy |
| geoRAM profile continuity and fatal integrity handling | `arena/georam_detect.asm`, `resident/fatal.asm` |
| Generated ABI, arena, ZP, placement, test-entry, and traceability contracts | structured manifests and `tools/` generators |
| Current-build API and memory-map references | `tools/generate_reference.py`, `build/API.md`, `build/MAP.md` |

One defect is in `DESIGN2.md` itself: §1 describes 512 KiB as eight 64 KiB
"blocks", while the authoritative hardware contract defines `$DFFF` blocks
as 16 KiB. This skeleton follows `REQUIREMENTS.md` and
`docs/GEORAM_BANKING.md`: the minimum is 512 KiB = 32 hardware blocks =
2,048 256-byte pages. `DESIGN2.md` should be corrected separately.

The routine tables below are a coverage inventory. Before an assembly entry is
implemented, its machine ABI must be expressible without placeholders such as
"target-dependent", "on stack", or two simultaneous meanings for the same
register. `manifests/routines.json` owns those exact contracts and the build
rejects an implemented public/test entry whose contract is incomplete.

---

## 1. File Layout

```text
build.ps1
manifests/
  arenas.json               arena types, schemas, ownership, reset rules
  commands.json             dialect tokens and direct/program classification
  linker_policy.json        fixed banking, reservations, segment constraints
  program_formats.json      stock and extended token/file envelope schemas
  routines.json             public/test entries, ABI, calls, return kind
  runtime_abi.json          compiled-code-only stable runtime surface
  traceability.json         EARS requirement-to-design/test records
  zero_page.json            ZP nodes, fixed constraints, lifetimes, aliases

src/
  common/
    constants.asm           project-wide equates, error codes, version bytes
    macros.asm              assemble-time helpers (facility macros, debug traps)
    zp.inc                  imports generated `build/zp_symbols.inc`

  resident/                 Layer 1 — always-RAM-resident (smallest set)
    irq.asm                 pinned IRQ handler: jiffy, keyboard, cursor
    screen.asm              bounded screen/cursor front end (resident half)
    kernal_bridge.asm       bank-safe KERNAL call wrapper
    georam_gate.asm         geoRAM call gate (resident dispatch, context stack)
    ram_under_io.asm        RAM-under-I/O gate ($D000-$DFFF access)
    fatal.asm               one geoRAM/profile/integrity fatal cleanup path
    resident_main.asm       common resident entry/exit, debug assertions

  loader/
    loader.asm              Phase 1 install: detect geoRAM, load payload, jump
    compiler_init.asm       post-install entry: BSS clear, arena init, enter editor

  common/
    georam_stream_reader.asm    CGS1 sidecar stream reader (from compressor project)

  geoasm/                   Layer 2 — geoRAM-resident services (compiled to
                            geoRAM pages; assembled as separate .o, linked by
                            generated page map)
    editor_svc.asm          tokenization, detokenization, LIST, line insert/delete
    tokenizer.asm           lexical scanner and keyword trie
    program_codec.asm       stock linked-line and versioned extended file codec
    program_store.asm       canonical logical line directory and transactions
    parser.asm              statement parser, expression parser
    semantic.asm            dialect/mode gating, direct/program classification
    direct_dispatch.asm     direct commands and temporary-program execution
    compiler_pipeline.asm   eight deterministic, serializable phase boundaries
    incremental.asm         fingerprints, dirty repair, atomic publication
    ir_builder.asm          typed IR emission
    optimizer.asm           optimization passes (loop fast-path eligibility)
    codegen.asm             native 6502 code emission, relocations
    compile_export.asm      source-free stock-C64 export construction
    dos_wedge.asm           $, /, @, ! direct editor commands
    diagnostics.asm         error/warning formatting, source-line context
    math_trig.asm           SIN COS TAN ATN ACS ASN (geoRAM-resident)
    math_trans.asm          EXP LOG SQR RND and IEEE transcendentals

  runtime/                  Layer 3 — compiled program runtime ABI
    variables.asm           scalar resolution, load, store, type promotion
    arrays.asm              array resolution, DIM, element access
    strings.asm             string alloc, assign, slice, compare, reclaim
    math_core.asm           resident arithmetic: + - * / CMP, INT, SGN, ABS, etc.
    ieee_state.asm          IEEE mode, flags, rounding, constants/classification
    control.asm             FOR/NEXT generic frame, GOSUB/RETURN, ON GOTO/GOSUB
    data.asm                DATA/READ/RESTORE cursor and typed conversion
    system.asm              PEEK/POKE/SYS/USR/WAIT, TI/TI$, protected ranges
    io.asm                  PRINT, INPUT, GET, CMD, file channel helpers
    runtime_io.asm          KERNAL-bridged file I/O (LOAD/SAVE/OPEN/CLOSE)
    wedge.asm               normal-RAM wedge core used by standalone exports
    errors.asm              error construction, unwind, STOP/CONT state
    inspection.asm          minimal inspection shell (for COMPILE export)
    graphics.asm            bitmap entry/exit and graphics-owned reservations

  arena/                    Layer 4 — geoRAM arena and overlay manager
    arena_core.asm          typed arena create/destroy/check, generation stamp
    page_alloc.asm          geoRAM page allocator (free-page bitmap)
    overlay_dispatch.asm    overlay entry/exit, page swap, ID resolution
    georam_detect.asm       non-destructive geoRAM detection and capacity probe
    context_stack.asm       geoRAM call nesting context stack

tools/
  zp_alloc.py                       zero-page graph-coloring allocator
  georam_pages.py                   geoRAM placement/IDs/call directories
  generate_contracts.py             ABI, arena, command, format, test exports
  linker_config.py                  ld65 config from checked-in policy
  extract_segments.py               file-backed RAM payload extraction
  prepare_compressor_segments.py    optional LZSS staging
  package_d64.py                    D64 packaging
  generate_reference.py             current-build API.md and MAP.md
  validate_build.py                 cross-artifact contract checks
  test_harness.py                   host test collection and trace matrix
```

---

## 2. Standard Calling Convention

All public 6502 subroutines in Compiler 2 follow this convention unless
documented otherwise in the per-routine table.

### 2.1 Register Protocol

| Register | Usage |
|---|---|
| A | Primary 8-bit input and output; also used for 16-bit lo byte |
| X | Secondary 8-bit input / 16-bit hi byte; also used for array dims |
| Y | Tertiary input / 16-bit offset; loop index for block copies |
| C (carry) | Standard success/failure flag where the routine can fail |
| Z (zero) | Result only when the routine contract explicitly declares it |
| V (overflow) | Result only for a declared signed comparison/arithmetic ABI |
| N (negative) | Result only for a declared comparison/sign-test ABI |
| D (decimal) | Always clear at every public entry and exit boundary |

Flags not named as outputs are clobbered. A routine may document another carry
meaning (for example loop-complete), but then it is not also an error flag;
errors must use a separately declared path. Exact preservation and result
flags come from `manifests/routines.json`.

### 2.2 Stack Discipline

- Every normally returning public subroutine restores SP to its entry value
  before `RTS`.
- `JSR` pushes a 2-byte return address; internal `JSR` calls are balanced
  by `RTS` within the same routine.
- Tail transfers, fatal/error unwinds, program entry, and non-returning editor
  loops declare a non-`return` return kind and a tested destination stack
  invariant instead.
- `RTI` is reserved for IRQ/NMI paths. `BRK` is permitted only in an explicit
  debug-trap build and is never a production control-flow mechanism.
- Subroutines that call KERNAL routines do so through `kernal_bridge` which
  handles serialization, interrupt-state save/restore, and `$01` banking.
  The pinned IRQ is the sole exception and directly invokes only its approved
  `UDTIM`/`SCNKEY` calls in the fixed IRQ sequence.

### 2.3 Zero-Page Clobber Contract

Every subroutine declares which ZP bytes it writes (clobbers). A routine that
reads ZP bytes not listed as inputs or clobbers is a bug. The graph-coloring
allocator uses these clobber lists to build the interference graph.

ZP reads and writes are listed per routine in the tables below using symbols
imported through `src/common/zp.inc` from `build/zp_symbols.inc`.

### 2.4 Branch Conventions

- The 6502 has a 16-bit address space; there is no 24-bit branch form.
- Relative and absolute control flow is permitted within one linked 256-byte
  geoRAM routine page when the placement validator proves the instruction and
  target both remain in `$DE00-$DEFF`.
- Every cross-page call or jump uses a generated resident gate entry. No raw
  branch, `JSR`, or `JMP` may cross a page-selection boundary.

### 2.5 GeoRAM Routine Constraints

- Each routine fits entirely within one selected geoRAM page.
- Entry is only at a generated offset within that page.
- Routine must not fall through `$DEFF` (end of 256-byte geoRAM window).
- Tail transfers use `context_stack` push/pop, not raw `JSR`-return
  manipulation.
- The geoRAM gate (`georam_gate.asm`) is the sole normal entry into geoRAM
  from resident code. Group-specific entries consume an 8-bit routine index,
  resolve generated page/block/offset metadata, save the declared caller
  state, call the target, capture declared results, and restore state before
  returning.

---

## 3. CPU Memory Map

```
$0000-$0001  6510 CPU port registers (always live, never allocated)
$0002-$00FF  Zero page — graph-coloring allocated (see §5)
$0100-$01FF  CPU hardware stack
$0200-$CFFF  Normal RAM pool — generated, non-overlapping resident/runtime,
             no-load workspace, compiled-code, and dynamic-data extents
$D000-$DFFF  I/O: VIC-II, SID, CIA, geoRAM window ($DE00-$DEFF),
             geoRAM registers ($DFFE, $DFFF), color RAM ($D800-$DBFF)
$E000-$FFF8  Normal RAM pool when graphics is inactive; KERNAL ROM overlays
             this range only while a KERNAL bridge selects $01=$36
$FFF9        Project guard byte ($A9 or build-defined sentinel)
$FFFA-$FFFB  NMI vector (RAM, managed by loader)
$FFFC-$FFFD  RESET vector (RAM, managed by loader)
$FFFE-$FFFF  IRQ/BRK vector (RAM, points to pinned resident irq entry)
```

The checked-in linker policy and generated allocation report define the exact
partition inside the two normal-RAM pools. This document deliberately does not
invent fixed resident/runtime ranges. File-backed segments, `COMPILER_BSS`,
compiled code, runtime workspace, and dynamic arenas must be disjoint in each
build profile, and the post-link validator proves the partition against the
map and manifests.

### 3.1 Graphics Mode Overlay

When bitmap mode is active (VIC bank 3, `$D018=$78`):
- `$E000-$FF3F` is bitmap pixels — not available for general RAM.
- `$DC00-$DFE7` holds the screen/color matrix (1000 bytes) — accessible
  only through the RAM-under-I/O gate.
- `$D800-$DBE7` is physical VIC-II color RAM.
- Dynamic RAM ceiling drops to `$DBFF`.
- Graphics mode is left (text mode restored) on END, error, STOP, and
  STOP-key interruption.

### 3.2 Standalone COMPILE Budget

- PRG load address: `$0801`
- Loader stub `2026 SYS2061` occupies `$0801-$080C`
- Compiled payload range: `$080D-$CFFF` (51,187 bytes maximum)
- Budget = user code + runtime helpers + relocation metadata +
  variable descriptors + inspection shell
- Tokenized source is NOT counted against this budget.
- Runtime variables, arrays, strings, control frames, and shell workspace are
  separately allocated from legal stock-C64 RAM not occupied by the loaded
  image. The export linker profile proves that image and workspace do not
  overlap.

### 3.3 geoRAM Window

- Data/code window: `$DE00-$DEFF` (256 bytes, selected geoRAM page)
- Page register: `$DFFE` (0..63, selects page within 16 KiB block)
- Block register: `$DFFF` (0..N, selects 16 KiB block)
- Logical page = block × 64 + page
- Only `georam_gate` and approved diagnostics write `$DFFE`/`$DFFF`

---

## 4. Linker Segment Policy

The checked-in policy owns invariant reservations and segment classes. The
generated configuration assigns concrete, non-overlapping extents:

| Segment class | Placement rule | Purpose |
|---|---|---|
| `BASIC_STUB` | packaged at `$0801-$080C`, entry `$080D` | exact `2026 SYS2061` linked-line stub |
| `INSTALL_LOADER` | generated development-profile staging extent from `$080D` | detector, payload installer/decompressor, `GEORAM` loader |
| `STANDALONE_IMAGE` | export profile within `$080D-$CFFF` | source-free compiled code/runtime/shell image |
| `RESIDENT` | pinned below `$D000` in generated normal-RAM extent | IRQ/NMI reachable while KERNAL ROM is visible, screen front end, gates, fatal path |
| `RUNTIME` | generated normal-RAM extent | stable compiled-program ABI |
| `COMPILER_BSS` | generated `NOLOAD` extent | cleared post-install workspace |
| `COMPILED_CODE` | generated dynamic extent | current compiled image; never overlaps runtime/data |
| `DYNAMIC_DATA` | one or more explicit free extents | variables, arrays, strings, frames, editor buffer |
| `GEOCODE_*` | one segment per generated geoRAM page | compiler/editor/math native routines |
| `GEODATA_*` | generated geoRAM pages | directories, arenas, read-only data |
| `BITMAP` | `$E000-$FF3F` when graphics profile is active | bitmap pixels |
| `BITMAP_MATRIX` | `$DC00-$DFE7` under I/O | bitmap screen matrix |
| `GUARD` | `$FFF9` | project sentinel |
| `VECTORS` | `$FFFA-$FFFF` | NMI/RESET/IRQ-BRK vectors |

`DYNAMIC_DATA` is allocator-owned free space, not an `ld65` segment laid over
`RESIDENT`, `RUNTIME`, or `COMPILED_CODE`. Text and graphics profiles have
different generated free-extent lists; entering graphics transactionally
removes `$DC00-$FF3F`, and exit restores it only after graphics state is
invalidated. `tools/linker_config.py` adds the current geoRAM inventory and
the development/standalone profile-specific segments.

---

## 5. Zero-Page Allocation Manifest

Every project allocation below is a node in the graph-coloring interference
model. Addresses are generated by `tools/zp_alloc.py` and written to
`build/zp_symbols.inc`. Stock KERNAL/IRQ workspace is different:
its addresses are architectural constraints imported from `c64rom`, not
colors the project may move. The generated graph reserves those fixed ranges
and overlays project storage only when its lifetime is proven disjoint.

### 5.1 Lifetime Domains

| Domain | Description | IRQ-safe |
|---|---|---|
| `cpu_port` | `$00-$01` — always live, never allocated | yes |
| `irq_state` | Concurrently live with foreground (keyboard, timer) | yes |
| `georam_gate` | geoRAM call gate, context stack, selected state | no |
| `kernal_bridge` | KERNAL bridge call-scoped ZP effects | no |
| `runtime_abi` | Compiled runtime ABI call pointers | no |
| `expression` | Expression evaluator temporaries | no |
| `math_fac` | Numeric FAC/ARG/extended math | no |
| `stmt_scratch` | Statement-local scratch | no |
| `tokenizer` | Tokenizer/lexer state | no |
| `parser` | Parser/compiler phase temporaries | no |
| `editor` | Editor foreground state (screen, cursor) | no |
| `loader` | Loader/install-only (overlaid post-install) | no |
| `error_unwind` | Error unwind state | no |
| `stop_cont` | STOP/CONT resumable state | no |

### 5.2 Fixed Architectural Reservations

| Symbol | Fixed range | Domain | Notes |
|---|---:|---|---|
| `zp_cpu_port` | `$00-$01` | `cpu_port` | 6510 DDR and data |
| `zp_stkey` | `$91` | `irq_state` | STOP key flag, `UDTIM`/`STOP` |
| `zp_time` | `$A0-$A2` | `irq_state` | Jiffy clock, `UDTIM`/`RDTIM`/`SETTIM` |
| `zp_lstx` | `$C5` | `irq_state` | Current key from matrix |
| `zp_ndx` | `$C6` | `irq_state` | Keyboard buffer count |
| `zp_sfdx` | `$CB` | `irq_state` | Keyboard shift state |
| `zp_keytab` | `$F5-$F6` | `irq_state` | Keyboard decode-table pointer |

### 5.3 KERNAL Bridge ZP Set

These fixed locations seed broader generated call-domain sets. The table is a
minimum address map, not a complete clobber contract; device-specific paths
are derived from the labeled `c64rom` call graph and can reserve additional
workspace.

| Symbol | Fixed range | KERNAL use |
|---|---:|---|
| `zp_status` | `$90` | I/O status (`READST` and device paths) |
| `zp_ldtnd` | `$98` | open-file table count/index |
| `zp_dfltn` | `$99` | default input device/channel paths |
| `zp_dflto` | `$9A` | default output device/channel paths |
| `zp_sal` / `zp_sah` | `$AC-$AD` | save/load start address workspace |
| `zp_eal` / `zp_eah` | `$AE-$AF` | save/load end address workspace |
| `zp_fnlen` | `$B7` | filename length |
| `zp_la` | `$B8` | logical file number |
| `zp_sa` | `$B9` | secondary address |
| `zp_fa` | `$BA` | device; persistent current-disk state |
| `zp_fnadr` | `$BB-$BC` | filename pointer |
| `zp_pntr` | `$D3` | screen cursor column on applicable paths |

`zp_fa` remains live between direct commands and therefore cannot overlay
project scratch merely because no KERNAL call is currently active.

### 5.4 geoRAM Gate ZP

| Symbol | Size | Domain | Notes |
|---|---|---|---|
| `zp_gr_block` | 1 | `georam_gate` | Current selected block (mirror) |
| `zp_gr_page` | 1 | `georam_gate` | Current selected page (mirror) |
| `zp_gr_ctx_sp` | 1 | `georam_gate` | Context stack pointer |
| `zp_gr_call_id` | 1 | `georam_gate` | Current call target ID (during dispatch) |

### 5.5 Expression Evaluator ZP

| Symbol | Size | Domain | Notes |
|---|---|---|---|
| `zp_expr_ptr1` | 2 | `expression` | Primary expression pointer |
| `zp_expr_ptr2` | 2 | `expression` | Secondary expression pointer |
| `zp_expr_tmp1` | 2 | `expression` | Temp 1 for expression work |
| `zp_expr_tmp2` | 2 | `expression` | Temp 2 for expression work |
| `zp_expr_type` | 1 | `expression` | Current expression result type tag |
| `zp_prec` | 1 | `expression` | Operator precedence (shunting) |

### 5.6 Numeric FAC/ARG/Extended Math ZP

| Symbol | Size | Domain | Notes |
|---|---|---|---|
| `zp_fac1` | 5 | `math_fac` | FAC1: primary floating accumulator (stock layout) |
| `zp_fac2` | 5 | `math_fac` | FAC2/FACARG: secondary accumulator |
| `zp_arg` | 5 | `math_fac` | ARG: argument register for binary ops |
| `zp_sign` | 1 | `math_fac` | Sign of FAC1 result |
| `zp_valtmp` | 1 | `math_fac` | Temporary for VAL/STR |
| `zp_facov` | 1 | `math_fac` | FAC overflow byte |
| `zp_iesstp` | 5 | `math_fac` | IEEE extended temp (when IEEE mode) |
| `zp_bitst` | 1 | `math_fac` | Bit test scratch |

### 5.7 Parser/Lexer ZP

| Symbol | Size | Domain | Notes |
|---|---|---|---|
| `zp_txtptr` | 2 | `parser` | Current parse position in token stream |
| `zp_tmptr` | 2 | `tokenizer` | Token scan pointer |
| `zp_lptr` | 2 | `parser` | Line pointer for recursive descent |
| `zp_opptr` | 2 | `parser` | Operator/function operand pointer |
| `zp_duck` | 1 | `parser` | Parser temporary for duck-typing |
| `zp_duck2` | 1 | `parser` | Parser temporary 2 |
| `zp_forlev` | 1 | `parser` | Current FOR/DO nesting level |
| `zp_sublev` | 1 | `parser` | Current GOSUB nesting level |

### 5.8 Statement Scratch ZP

| Symbol | Size | Domain | Notes |
|---|---|---|---|
| `zp_stmt_op` | 1 | `stmt_scratch` | Current opcode/statement ID |
| `zp_stmt_arg` | 2 | `stmt_scratch` | Current statement argument pointer |
| `zp_tmp1` | 1 | `stmt_scratch` | General scratch byte 1 |
| `zp_tmp2` | 1 | `stmt_scratch` | General scratch byte 2 |
| `zp_tmp3` | 1 | `stmt_scratch` | General scratch byte 3 |
| `zp_tmp4` | 1 | `stmt_scratch` | General scratch byte 4 |

### 5.9 Editor Foreground ZP

| Symbol | Size | Domain | Notes |
|---|---|---|---|
| `zp_crsr_x` | 1 | `editor` | Cursor column (resident, IRQ-visible) |
| `zp_crsr_y` | 1 | `editor` | Cursor row (resident, IRQ-visible) |
| `zp_crsr_vis` | 1 | `editor` | Cursor visible flag |
| `zp_linebuf` | 2 | `editor` | Pointer to resident line capture buffer |
| `zp_line_len` | 1 | `editor` | Current line length in buffer |
| `zp_quotemode` | 1 | `editor` | Quote mode toggle |

### 5.10 STOP/CONT Resumable State ZP

| Symbol | Size | Domain | Notes |
|---|---|---|---|
| `zp_cont_handle` | 2 | `stop_cont` | Handle of persistent continuation descriptor |
| `zp_cont_generation` | 2 | `stop_cont` | Runtime/source generation checked by CONT |
| `zp_stop_flag` | 1 | `stop_cont` | STOP/STOP-key validity and reason bits |

The continuation descriptor owns the resumable PC plus the saved runtime
control/stack state required by the generated code. A raw hardware SP value is
not a sufficient continuation and is never the whole persisted state.

### 5.11 Error Unwind ZP

| Symbol | Size | Domain | Notes |
|---|---|---|---|
| `zp_errnum` | 1 | `error_unwind` | Current BASIC error number |
| `zp_errline` | 2 | `error_unwind` | Source line of error |
| `zp_errptr` | 2 | `error_unwind` | Pointer into source for error context |

### 5.12 Loader-Only ZP (overlaid post-install)

These overlap with post-install domains since the loader runs once and
does not coexist with editor/compiler/runtime.

| Symbol | Size | Domain | Notes |
|---|---|---|---|
| `zp_ldr_src` | 2 | `loader` | Source pointer during payload copy |
| `zp_ldr_dst` | 2 | `loader` | Destination pointer during payload copy |
| `zp_ldr_len` | 2 | `loader` | Block length during payload copy |
| `zp_ldr_blk` | 1 | `loader` | geoRAM block counter during load |
| `zp_ldr_pge` | 1 | `loader` | geoRAM page counter during load |
| `zp_georam_stream` | 15 | `loader` | CGS1 stream reader decompressor state |

### 5.13 Graph-Coloring Solver Input

The `tools/zp_alloc.py` solver consumes a JSON manifest with these fields
per node:

```json
{
  "name": "zp_fac1",
  "size": 5,
  "alignment": 1,
  "domain": "math_fac",
  "lifetimes": ["runtime_abi", "math_fac"],
  "aliases_allowed": [],
  "interference_overrides": [],
  "notes": "Stock FAC1 layout, 5 bytes at contiguous addresses"
}
```

Interference edges are auto-generated when:
- Two nodes have overlapping lifetime domains
- One node is live across a call that clobbers the other
- One is `irq_state` and the other is not IRQ-safe
- A KERNAL bridge call scope includes the node's domain
- An explicit `interference_overrides` entry lists a conflicting node

Solver output format:

```json
{
  "addresses": {"zp_fac1": {"addr": "$64", "size": 5}, ...},
  "interference_edges": [{"a": "zp_fac1", "b": "zp_tmp1", "reason": "domain:math_fac overlaps stmt_scratch"}],
  "peak_live_bytes": {"math_fac": 16, "expression": 8, "parser": 7, ...},
  "unused_bytes": ["$C0-$C4", ...]
}
```

---

## 6. Routine Tables

Every exported public routine is declared in `manifests/routines.json`;
`tools/generate_contracts.py` emits the production and test-build entry
manifests. Internal helpers become callable only in a test build through an
explicit test-only manifest entry; this never enlarges the production ABI.

Legend:
- **In** — logical inputs; a multi-field input is passed by one typed record
  handle unless explicit registers are shown
- **Out** — logical outputs; exact returned registers/flags are generated from
  `manifests/routines.json`
- **Clob** — registers and ZP bytes modified (never restored)
- **Side** — observable side effects beyond register/ZP changes
- **ZP** — zero-page symbols read (R) or written (W) by this routine

---

### 6.1 `src/common/constants.asm`

No subroutines. Exports equates only.

| Symbol | Value | Notes |
|---|---|---|
| `ERR_TOO_MANY_FILES` | $01 | Stock BASIC V2 error-table index |
| `ERR_FILE_OPEN` | $02 | Stock BASIC V2 error-table index |
| `ERR_FILE_NOT_OPEN` | $03 | Stock BASIC V2 error-table index |
| `ERR_FILE_NOT_FOUND` | $04 | Stock BASIC V2 error-table index |
| `ERR_DEVICE_NOT_PRESENT` | $05 | Stock BASIC V2 error-table index |
| `ERR_NOT_INPUT_FILE` | $06 | Stock BASIC V2 error-table index |
| `ERR_NOT_OUTPUT_FILE` | $07 | Stock BASIC V2 error-table index |
| `ERR_MISSING_FILE_NAME` | $08 | Stock BASIC V2 error-table index |
| `ERR_ILLEGAL_DEVICE_NUMBER` | $09 | Stock BASIC V2 error-table index |
| `ERR_NEXT_WITHOUT_FOR` | $0A | Stock BASIC V2 error-table index |
| `ERR_SYNTAX` | $0B | Stock BASIC V2 `errsn` |
| `ERR_RETURN_WITHOUT_GOSUB` | $0C | Stock BASIC V2 error-table index |
| `ERR_OUT_OF_DATA` | $0D | Stock BASIC V2 error-table index |
| `ERR_ILLEGAL_QUANTITY` | $0E | Stock BASIC V2 `errfc` |
| `ERR_OVERFLOW` | $0F | Stock BASIC V2 `errov` |
| `ERR_OUT_OF_MEMORY` | $10 | Stock BASIC V2 `errom` |
| `ERR_UNDEFINED_STATEMENT` | $11 | Stock BASIC V2 error-table index |
| `ERR_BAD_SUBSCRIPT` | $12 | Stock BASIC V2 `errbs` |
| `ERR_REDIM_ARRAY` | $13 | Stock BASIC V2 `errdd` |
| `ERR_DIVISION_BY_ZERO` | $14 | Stock BASIC V2 `errdvo` |
| `ERR_ILLEGAL_DIRECT` | $15 | Stock BASIC V2 `errid` |
| `ERR_TYPE_MISMATCH` | $16 | Stock BASIC V2 `errtm` |
| `ERR_STRING_TOO_LONG` | $17 | Stock BASIC V2 `errls` |
| `ERR_FILE_DATA` | $18 | Stock BASIC V2 `errbd` |
| `ERR_FORMULA_TOO_COMPLEX` | $19 | Stock BASIC V2 `errst` |
| `ERR_CANT_CONTINUE` | $1A | Stock BASIC V2 `errcn` |
| `ERR_UNDEFINED_FUNCTION` | $1B | Stock BASIC V2 `erruf` |
| `ERR_VERIFY` | $1C | Stock BASIC V2 error-table index |
| `ERR_LOAD` | $1D | Stock BASIC V2 error-table index |
| `ERR_BREAK` | $1E | Stock BASIC V2 break-table index |
| `TYPE_NONE` | $00 | Expression type: no value |
| `TYPE_INTEGER` | $01 | 16-bit signed integer |
| `TYPE_FLOAT` | $02 | 5-byte float (stock layout) |
| `TYPE_STRING` | $03 | String pointer + length |
| `TYPE_ARRAY` | $04 | Array descriptor reference |
| `TYPE_FUNCTION` | $05 | DEF FN reference |
| `BASIC2_DIALECT` | $00 | Active dialect flag value |
| `BASIC35_DIALECT` | $01 | Active dialect flag value |
| `IEEE_MODE_LEGACY` | $00 | Numeric mode flag value |
| `IEEE_MODE_IEEE` | $01 | Numeric mode flag value |
| `BASIC_VERSION` | (build) | Recorded in compiled export header |
| `RUNTIME_ABI_VERSION` | (build) | Recorded in compiled export header |
| `GUARD_BYTE` | $A9 | Sentinel at `$FFF9` |
| `GEORAM_MIN_BLOCKS` | 32 | 512 KiB minimum (32 × 16 KiB blocks) |

The numeric mode is policy on the stock-layout floating value, not a separate
runtime value type. Error values above are indices verified from
`c64rom/basic/lexing/token_strings.s`; extensions use a separately versioned
range and never renumber stock errors.

---

### 6.2 `src/common/macros.asm`

No subroutines. Exports assemble-time macros.

| Macro | Purpose |
|---|---|
| `assert_canonical` | Debug: assert `$01=$35` at entry/exit |
| `assert_irq_disabled` | Debug: assert I flag set (IRQ masked) |
| `debug_trap` | `BRK` with facility ID for diagnostics |
| `zp_clobber_check` | Debug: poison non-live ZP, verify caller's clobber list |
| `page_check` | Debug: verify geoRAM page boundary not crossed |
| `stack_balance` | Debug: verify SP restored after call |

---

### 6.3 `src/resident/irq.asm`

Pinned resident IRQ handler. It does not enter the serialized foreground
bridge. It saves the interrupted CPU-port value, selects KERNAL+I/O, directly
calls only `UDTIM` and `SCNKEY` in the approved order, performs bounded cursor
service, acknowledges CIA state, and restores the exact interrupted mapping
and registers.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `irq_entry` | hardware IRQ frame (CPU has pushed PC/P; A/X/Y are live) | interrupted A/X/Y/P/PC and mapping restored | internal IRQ save set | Advances jiffy clock, updates keyboard state, blinks cursor | Pinned entry: save A/X/Y/mapping, UDTIM, cursor, SCNKEY, CIA ack, restore, RTI |
| `irq_update_jiffy` | IRQ-private call | — | A X Y, declared flags | Calls KERNAL `UDTIM` directly while IRQ entry owns `$01=$36` | Called only from `irq_entry` |
| `irq_cursor_blink` | — | — | A | Toggles cursor visibility state in `zp_crsr_vis` | Bounded resident cursor service; no geoRAM dependency |
| `irq_scan_keyboard` | IRQ-private call | — | A X Y, declared flags | Calls KERNAL `SCNKEY` directly after cursor service | Called only from `irq_entry` |
| `irq_restore_mapping` | saved interrupted `$01`/P | exact interrupted mapping/P restored | A | Does not touch geoRAM selection | Called before `RTI` |

---

### 6.4 `src/resident/screen.asm`

Bounded screen/cursor management. Resident half only — heavy editor
services (tokenize, list) go through `editor_svc` in geoRAM.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `screen_init` | — | — | A X Y | Initializes screen editor state, clears screen | Cold-start screen setup |
| `screen_clear` | — | — | A X Y | Clears screen, homes cursor | CLR/HOME |
| `screen_scroll_up` | — | — | A X Y | Scrolls screen memory up one line | When cursor below bottom |
| `screen_putchar` | A=char | — | A | Writes character at cursor, advances cursor | Resident output primitive |
| `screen_getchar` | — | A=char or $00 | A X | Reads character at cursor position | For LIST display |
| `screen_cursor_on` | — | — | A | Sets cursor visible flag | |
| `screen_cursor_off` | — | — | A | Clears cursor visible flag | |
| `screen_cursor_right` | — | — | A | Advances cursor column, wraps to next line | |
| `screen_cursor_left` | — | — | A | Retreats cursor column, wraps to prev line | |
| `screen_cursor_down` | — | — | A | Advances cursor row, scrolls if needed | |
| `screen_cursor_up` | — | — | A | Retreats cursor row | |
| `screen_line_input` | `zp_linebuf`=buffer ptr | `zp_line_len`=length | A X Y | Captures one logical line from screen into buffer | Bounded line capture for editor; respects quote mode |

---

### 6.5 `src/resident/kernal_bridge.asm`

Bank-safe wrapper for every foreground KERNAL ROM call. It serializes KERNAL
workspace use, installs/validates the pinned RAM-indirect IRQ vector, selects
`$01=$36`, and restores `$35` plus the incoming interrupt state. Short,
proven-bounded calls may keep IRQ masked for their complete mapping window.
Blocking file/channel calls must re-enable the incoming IRQ state while ROM is
visible; masking interrupts for an entire blocking call is forbidden.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `kernal_readst` | — | A=status | A | Reads KERNAL status | `zp_status` | READST bridge |
| `kernal_setlfs` | A=lf, X=dev, Y=sa | — | A X Y | Sets logical/device/secondary parameters; does not open | `zp_la`, `zp_sa`, `zp_fa` | SETLFS bridge |
| `kernal_setnam` | A=len, X/Y=name | — | A X Y | Sets filename for next OPEN/LOAD/SAVE | `zp_fnlen`, `zp_fnadr` | SETNAM bridge |
| `kernal_open` | prior SETLFS/SETNAM | C=error | A X Y | Opens file/channel | device workspace | OPEN bridge |
| `kernal_close` | A=lf | C=error | A X Y | Closes logical file | `zp_ldtnd`, device workspace | CLOSE bridge |
| `kernal_chkin` | X=lf | C=error | A X Y | Sets input channel | `zp_status`, channel workspace | CHKIN bridge |
| `kernal_chkout` | X=lf | C=error | A X Y | Sets output channel | `zp_status`, channel workspace | CHKOUT bridge |
| `kernal_clrchn` | — | — | A X Y | Restores default channels | `zp_c3po`, `zp_d7`, channel workspace | CLRCHN bridge |
| `kernal_chrin` | — | A=byte | A X Y | Reads byte from input channel | `zp_pntr`, channel workspace | CHRIN bridge |
| `kernal_chrout` | A=byte | C=error | A X Y | Writes byte to output channel | generated channel workspace | CHROUT bridge |
| `kernal_load` | A=mode, X/Y=addr | C=error, X/Y=ended addr | A X Y | Loads from device | `zp_status`, `zp_fa`, `zp_eal` | LOAD bridge |
| `kernal_save` | A=ZP-ptr, X/Y=end | C=error | A X Y | Saves to device | `zp_fa`, `zp_sal`, `zp_eal` | SAVE bridge |
| `kernal_settim` | A=lo, X=mid, Y=hi | — | A X Y | Sets jiffy clock | `zp_time` | SETTIM bridge |
| `kernal_rdtim` | — | A=lo, X=mid, Y=hi | A X Y | Reads jiffy clock | `zp_time` | RDTIM bridge |
| `kernal_stop` | — | Z=1 if STOP pressed | A | Checks STOP key | `zp_stkey`, `zp_ndx` | STOP bridge |
| `kernal_getin` | — | A=byte or $00 | A X Y | Reads from keyboard buffer | `zp_ndx`, `zp_status` | GETIN bridge |
| `kernal_udtim` | — | — | A X Y | Advances jiffy clock one tick | `zp_time`, `zp_stkey` | UDTIM bridge |
| `kernal_scnkey` | — | — | A X Y | Scans keyboard matrix | `zp_lstx`, `zp_ndx`, `zp_sfdx`, `zp_keytab` | SCNKEY bridge |

The ZP column above names only recognizable anchors. The generated bridge
contract contains complete read/write/preserve sets (including
device-dependent workspace), CPU-port behavior, IRQ policy, blocking status,
and returned flags derived from `c64rom`; the build rejects a hand-written
subset that disagrees with it.

---

### 6.6 `src/resident/georam_gate.asm`

Sole resident entry into geoRAM-resident code. Maintains a software
mirror of `$DFFE`/`$DFFF`. Uses the context stack for nested calls.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `georam_call_group_n` | X=routine index; target inputs per generated ABI | target outputs per generated ABI | dispatch X plus generated target clobbers | Resolves group tables, calls target, captures results, restores caller selection/P | `zp_gr_block`, `zp_gr_page`, `zp_gr_ctx_sp`, `zp_gr_call_id` | Generated returning entry for each 256-ID group |
| `georam_tail_group_n` | X=routine index; target inputs per generated ABI | does not return to current frame | dispatch X plus generated target clobbers | Reuses/removes current context frame before transfer | `zp_gr_block`, `zp_gr_page`, `zp_gr_ctx_sp`, `zp_gr_call_id` | Generated tail-transfer entry; not an alias of returning call |
| `georam_ctx_push` | — | — | A | Pushes current block/page/registers onto context stack | `zp_gr_ctx_sp`, `zp_gr_block`, `zp_gr_page` | Internal: save caller geoRAM state before nesting |
| `georam_ctx_pop` | — | — | A | Pops and restores caller block/page/registers from context stack | `zp_gr_ctx_sp`, `zp_gr_block`, `zp_gr_page` | Internal: restore before returning to caller |
| `georam_select` | A=page, X=block | — | A X, flags | Writes `$DFFE` and `$DFFF`; updates software mirror | `zp_gr_block`, `zp_gr_page` | Internal/diagnostic only: selects geoRAM page |
| `georam_read_byte` | X/Y=stable logical byte handle | A=byte, C=error | A X Y | Maps, validates, and restores caller selection | — | Handle-based byte read |
| `georam_read_word` | X/Y=stable logical word handle | X/Y=word, C=error | A X Y | Rejects boundary/owner/generation errors; restores selection | — | Handle-based word read |
| `georam_write_byte` | X/Y=typed handle/value record | C=error | A X Y | Maps, validates, writes, restores caller selection | — | Handle-based byte write |
| `georam_write_word` | X/Y=typed handle/value record | C=error | A X Y | Rejects cross-boundary/owner/generation errors | — | Handle-based word write |
| `georam_copy_from_ram` | X/Y=bounded copy descriptor | C=error | A X Y | Copies normal RAM to geoRAM and restores selection | — | Bulk ingress |
| `georam_copy_to_ram` | X/Y=bounded copy descriptor | C=error | A X Y | Copies geoRAM to normal RAM and restores selection | — | Bulk egress |
| `georam_copy_pages` | X/Y=validated source/destination extent record | C=error | A X Y | Uses bounded resident buffer; no raw window pointer escapes | — | geoRAM-to-geoRAM copy |
| `georam_checksum` | X/Y=validated extent record | X/Y=checksum, C=error | A X Y | Restores caller selection | — | Integrity helper |
| `georam_verify_mirror` | — | C=1 if mismatch | A | Debug-only: compares software mirror against `$DFFE`/`$DFFF` | `zp_gr_block`, `zp_gr_page` | Integrity check for selection ownership |

---

### 6.7 `src/resident/ram_under_io.asm`

Gate for accessing RAM at `$D000-$DFFF` (bitmap screen matrix, graphics
memory). Masks IRQ for the full critical section.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `ram_under_io_enter` | — | — | A | Selects all-RAM mapping; masks IRQ | Opens gate: `$01` → all-RAM; IRQ disabled |
| `ram_under_io_exit` | — | `$01` restored to `$35` | A | Restores `$35` mapping; restores incoming IRQ state | Closes gate: restore canonical mapping |
| `ram_under_io_copy_in` | X/Y=dest, A=len, src pointer set | — | A X Y | Copies bytes from normal RAM into `$D000-$DFFF` region through gate | Bounded chunk copy for screen matrix |
| `ram_under_io_copy_out` | X/Y=src, A=len, dest pointer set | — | A X Y | Copies bytes from `$D000-$DFFF` region out to normal RAM through gate | Read-back for screen matrix |

---

### 6.8 `src/loader/loader.asm`

Phase 1 loader. Starts from `SYS2061` (`$080D`). Detects geoRAM, loads
payload from disk, installs to runtime locations, jumps to `compiler_init`.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `loader_entry` | BASIC cold-start state | jumps to `compiler_init` | A X Y | Full install sequence | Main loader entry at `$080D` |
| `loader_detect_georam` | — | C=0 supported profile, C=1 absent/unsupported | A X Y | Calls normal-RAM `detect_georam`; trusts no arena state before success | Installation wrapper for the single detector implementation |
| `georam_load_georam_file` | — | C=error | A X Y | Loads `GEORAM` file from disk into geoRAM pages via `kernal_load` | Reads the geoRAM page image from D64 |
| `georam_install_pages` | — | C=error | A X Y | Copies loaded image into geoRAM pages, byte-by-byte through window | Installs geoRAM payload |
| `georam_stream_load` | A=filename length, X/Y=filename pointer | C=0 success, C=error | A X Y | Opens CGS1 sidecar, reads chunks, decompresses directly to geoRAM | Compressed GEORAM streaming installation |
| `loader_install_ram_payload` | — | — | A X Y | Copies/decompresses RAM payload to runtime locations | Resident + runtime code installation |
| `loader_restore_banking` | — | — | A | Restores `$01=$35` canonical runtime mapping | Post-install banking restore |
| `loader_check_sentinel` | — | C=0 valid, C=1 missing | A | Verifies `$FFF9` guard byte | Sanity check after install |

The `georam_stream_load` routine is sourced from the compressor project's
`src/6502/decompressor/georam_stream_reader.asm`. It uses 15 bytes of
loader-only zero page for decompressor state.

---

### 6.9 `src/loader/compiler_init.asm`

Post-install initialization. Clears BSS, constructs arenas, enters editor.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `compiler_init` | jump from loader | enters editor main loop | A X Y | Clears BSS, inits arenas, inits editor, enters main loop | System entry after successful install |
| `init_clear_bss` | — | — | A X Y | Zeroes `COMPILER_BSS` segment | Clears all uninitialized workspace |
| `init_arenas` | — | — | A X Y | Constructs arena directory, stamps generations | Arena initialization: tokenized program, compiled, variables, arrays, strings, symbols, overlay, scratch |
| `init_editor` | — | — | A X Y | Initializes editor state, clears screen | Editor cold-start |
| `init_enter_main_loop` | — | (never returns) | — | Enters editor main loop | Forever: capture line, dispatch |

---

### 6.10 `src/geoasm/tokenizer.asm`

Lexical scanner. Resides in geoRAM. Uses a generated
first-character-indexed trie whose accepting nodes carry token ID, dialect
mask, abbreviation policy, and longest-match metadata. It never falls back to
a full keyword-table scan.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `token_init` | X/Y=source ptr | — | A X Y | Sets up tokenizer state for a new line | `zp_tmptr` | Initialize tokenizer for line |
| `token_next` | — | A=token, C=1 if end-of-line | A X Y | Advances to next token; updates scan pointer | `zp_tmptr`, `zp_tmp1` | Primary tokenizer entry: scan and return next token |
| `token_peek` | — | A=token, C=1 if end-of-line | A X | Looks ahead one token without advancing | `zp_tmptr` | Peek for parser |
| `token_identifier` | active dialect table and scan state | A=keyword ID or `$00`; identifier in scratch | A X Y | Traverses generated first-character trie; accepts only enabled dialect nodes | `zp_tmptr`, `zp_tmp1`, `zp_tmp2` | O(candidate length + declared transition bound), with no full-table fallback |
| `token_number` | — | value in FAC1 or integer register | A X Y | Scans numeric literal, converts to internal form | `zp_tmptr`, `zp_fac1` | Numeric literal tokenization |
| `token_string` | — | string data in buffer, length | A X Y | Scans quoted string literal (respects quote mode) | `zp_tmptr` | String literal tokenization |
| `token_skip_whitespace` | — | — | A | Advances past spaces/tabs | `zp_tmptr` | Whitespace consumption |
| `token_rem` | — | — | A X Y | Skips rest of line (REM content) | `zp_tmptr` | REM handler: pass through verbatim |
| `token_data` | — | — | A X Y | Collects DATA values as raw tokens until EOL | `zp_tmptr` | DATA handler: stores uninterpreted |

---

### 6.11 `src/geoasm/parser.asm`

Statement and expression parser. Recursive descent with Pratt-style
expression parsing.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `parse_line` | X/Y=token stream | C=error, error code in A | A X Y | Parses one complete program or direct line | `zp_txtptr`, `zp_lptr`, `zp_forlev`, `zp_sublev` | Top-level line parser |
| `parse_statement` | — | A=stmt ID, C=error | A X Y | Parses one statement, dispatches to statement handler | `zp_txtptr`, `zp_stmt_op`, `zp_stmt_arg` | Statement parser dispatcher |
| `parse_expression` | — | type in `zp_expr_type`, value in FAC1 or accumulator | A X Y | Full expression parser (Pratt: handles precedence, functions, operators) | `zp_txtptr`, `zp_expr_ptr1`, `zp_expr_ptr2`, `zp_fac1`, `zp_prec` | Primary expression parser |
| `parse_primary` | — | value in FAC1 or string ptr | A X Y | Parses primary: number, string, variable, function call, (expr) | `zp_txtptr`, `zp_fac1` | Primary (atom) parser |
| `parse_comparison` | left value loaded | result in A (boolean), C=error | A X Y | Parses =, <>, <, >, <=, >= | `zp_txtptr`, `zp_fac1`, `zp_fac2` | Comparison operator parser |
| `parse_term` | — | value in FAC1 | A X Y | Parses *, / | `zp_txtptr`, `zp_fac1`, `zp_arg` | Term-level parser |
| `parse_factor` | — | value in FAC1 | A X Y | Parses unary -, NOT, ^ | `zp_txtptr`, `zp_fac1` | Factor-level parser |
| `parse_function_call` | A=func ID | value in FAC1 or string | A X Y | Parses function argument list, calls function | `zp_txtptr`, `zp_fac1`, `zp_opptr` | Built-in function parser |
| `parse_array_ref` | X/Y=var descriptor | element address | A X Y | Parses array subscript(s), resolves element | `zp_txtptr`, `zp_expr_ptr1` | Array element reference parser |
| `parse_for` | — | loop descriptor set up | A X Y | Parses FOR var=start TO end [STEP inc], pushes loop frame | `zp_txtptr`, `zp_forlev` | FOR statement parser |
| `parse_gosub` | — | — | A X Y | Parses GOSUB line, validates target | `zp_txtptr`, `zp_sublev` | GOSUB statement parser |

---

### 6.12 `src/geoasm/semantic.asm`

Dialect/mode gating and direct/program classification. Validates syntax
against active dialect before compilation.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `semantic_validate_dialect` | A=token | C=1 if invalid in current dialect | A | Defense-in-depth for loaded/versioned token streams | — | Tokenizer already prevents disabled extended tokens from being stored |
| `semantic_classify_direct` | A=stmt ID | C=1 if direct-only in program line | A | Rejects direct-only commands in stored-program context | — | Direct/program classification per §4 table |
| `semantic_validate_line` | X/Y=token stream | C=error, A=error code | A X Y | Full syntax/dialect validation of one line | `zp_txtptr`, `zp_forlev`, `zp_sublev` | Transactional syntax validation (step 3 of line entry) |
| `semantic_check_for_dialect` | — | A=current dialect | A | Returns BASIC2_DIALECT or BASIC35_DIALECT | — | Dialect query for compiler passes |
| `semantic_set_dialect` | A=dialect | — | A | Sets active dialect mode | — | BASIC2 / BASIC3.5 direct command handler |
| `semantic_get_numeric_mode` | — | A=current numeric mode | A | Reads legacy/IEEE mode independently of dialect | — | `FPMODE()` query |
| `semantic_set_numeric_mode` | A=mode | C=error if unsupported | A, flags | Changes numeric policy and invalidates mode-keyed compiled records | — | `FPMODE0` / `FPMODE1` |

---

### 6.13 `src/geoasm/ir_builder.asm`

Typed intermediate representation emission. Boundary 5 of the pipeline.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `ir_init` | — | — | A X Y | Clears IR buffer, resets write pointer | — | Initialize IR builder for new compilation |
| `ir_emit_stmt` | A=stmt type, X/Y=args | — | A X Y | Writes one statement record to IR buffer | `zp_tmp1`, `zp_tmp2` | Statement boundary emitter |
| `ir_emit_expr` | A=op, operands referenced | — | A X Y | Writes expression tree node | `zp_tmp1`, `zp_tmp2` | Expression tree emitter |
| `ir_emit_var_ref` | X/Y=var descriptor | — | A X Y | Writes variable reference node | — | Variable reference emitter |
| `ir_emit_array_ref` | X/Y=arr descriptor, subscript | — | A X Y | Writes array element reference | — | Array reference emitter |
| `ir_emit_string_ref` | X/Y=string descriptor | — | A X Y | Writes string reference node | — | String reference emitter |
| `ir_emit_branch` | A=type, X/Y=target | — | A X Y | Writes GOTO/GOSUB/IF-THEN branch | — | Branch emitter |
| `ir_emit_loop` | A=kind, loop params | — | A X Y | Writes loop descriptor (FOR, DO, etc.) | `zp_forlev` | Loop descriptor emitter |
| `ir_emit_literal_int` | X/Y=16-bit value | — | A X Y | Writes integer literal node | — | Integer literal emitter |
| `ir_emit_literal_float` | FAC1=value | — | A X Y | Writes float literal node | `zp_fac1` | Float literal emitter |
| `ir_emit_literal_str` | X/Y=string data, A=len | — | A X Y | Writes string literal node | — | String literal emitter |
| `ir_finish_line` | — | C=error | A | Validates IR completeness for line, returns to caller | — | End-of-line IR finalization |
| `ir_get_buf_ptr` | — | X/Y=current write ptr | X Y | Returns current IR buffer position | — | Query for tests/replay |

---

### 6.14 `src/geoasm/optimizer.asm`

Optimization passes. Consults loop descriptors and invalidation masks to
select fast paths or fall back to generic code.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `opt_run_passes` | — | — | A X Y | Runs all optimization passes over current IR | — | Top-level optimization driver |
| `opt_build_effect_summaries` | X/Y=typed IR generation | X/Y=summary table, C=error | A X Y | One bottom-up pass; parent loops merge child masks | `zp_expr_ptr1`, `zp_tmp1`, `zp_tmp2` | Generation-cached read/write/escape/invalidation summaries |
| `opt_eligible_for_for_fast` | loop descriptor in X/Y | C=1 if eligible | A | Checks all FOR/NEXT fast-path eligibility conditions per §11 | `zp_expr_ptr1`, `zp_tmp1` | FOR/NEXT fast-path eligibility predicate |
| `opt_eligible_for_do_fast` | loop descriptor in X/Y | C=1 if eligible | A | Checks DO/LOOP fast-path eligibility (bare, WHILE, UNTIL) | `zp_expr_ptr1`, `zp_tmp1` | DO/LOOP fast-path eligibility predicate |
| `opt_check_invalidation` | X/Y=loop effect-summary record | A=dirty mask | A | Reads cached POKE/SYS/CLR/DIM/callback/string barriers | `zp_tmp1` | Shared invalidation predicate; no body rescan |
| `opt_check_aliasing` | X/Y=variable/summary record | C=1 if aliased write found | A | Reads cached alias/escape/bank-change facts | `zp_tmp1` | Shared alias predicate; no body rescan |
| `opt_propagate_dirty` | dirty mask in A | — | A | Propagates dirty masks through nested loop descriptors | — | Dirty mask propagation through nesting |
| `opt_select_branch_polarity` | condition type in A | A=branch opcode | A | Selects branch polarity (UNTIL is NOT inverted by scattered NOT) | — | Polarity selection for WHILE/UNTIL conditions |
| `opt_check_stop_poll` | loop descriptor in X/Y | C=1 if long loop needing poll | A | Determines if loop body is long enough to require STOP polling | — | STOP polling eligibility for long loops |

---

### 6.15 `src/geoasm/codegen.asm`

Native 6502 code emission. Boundary 7 of the pipeline.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `codegen_init` | — | — | A X Y | Resets code emitter state, clears relocation list | — | Initialize code generator |
| `codegen_emit_stmt` | IR statement record | — | A X Y | Emits native code for one statement | `zp_tmp1`-`zp_tmp4` | Statement code emitter |
| `codegen_emit_for_fast` | eligible loop descriptor | — | A X Y | Emits direct integer FOR/NEXT fast path: init var, compare, branch, update | `zp_tmp1`-`zp_tmp4` | FOR/NEXT optimized emitter |
| `codegen_emit_for_generic` | loop descriptor | — | A X Y | Emits frame-based generic FOR/NEXT with full error handling | `zp_tmp1`-`zp_tmp4` | FOR/NEXT generic emitter |
| `codegen_emit_do_fast` | eligible loop descriptor | — | A X Y | Emits native backedge for bare DO/LOOP or native pretest/posttest | `zp_tmp1`-`zp_tmp4` | DO/LOOP optimized emitter |
| `codegen_emit_do_generic` | loop descriptor | — | A X Y | Emits frame-based generic DO/LOOP with full condition evaluation | `zp_tmp1`-`zp_tmp4` | DO/LOOP generic emitter |
| `codegen_emit_exit` | exit descriptor | — | A X Y | Emits EXIT DO/FOR: resolves descriptor target or generic control stack | `zp_tmp1`, `zp_tmp2` | EXIT DO/FOR emitter |
| `codegen_emit_if` | IR if-statement | — | A X Y | Emits IF cond THEN stmt [ELSE stmt] | `zp_tmp1`, `zp_tmp2` | IF/THEN/ELSE emitter |
| `codegen_emit_gosub` | target line | — | A X Y | Emits GOSUB with push return address, validate line exists | `zp_tmp1` | GOSUB emitter |
| `codegen_emit_return` | — | — | A X Y | Emits RETURN: pop return address, validate nesting | `zp_tmp1` | RETURN emitter |
| `codegen_emit_on` | ON expr GOTO/GOSUB | — | A X Y | Emits multi-way branch | `zp_tmp1`, `zp_tmp2` | ON GOTO/GOSUB emitter |
| `codegen_emit_print` | PRINT expression list | — | A X Y | Emits PRINT with formatting, semicolons, commas, TAB, SPC | `zp_tmp1`, `zp_tmp2` | PRINT statement emitter |
| `codegen_emit_input` | INPUT prompt, var list | — | A X Y | Emits INPUT with prompt, channel select, type coercion | `zp_tmp1`, `zp_tmp2` | INPUT statement emitter |
| `codegen_emit_let` | assignment target, expr | — | A X Y | Emits assignment with type promotion if needed | `zp_tmp1`, `zp_tmp2` | LET/assignment emitter |
| `codegen_emit_dim` | DIM var(sizes) | — | A X Y | Emits array dimension allocation call | `zp_tmp1` | DIM emitter |
| `codegen_emit_data` | DATA values | — | A X Y | Emits DATA record into data section | — | DATA emitter |
| `codegen_emit_read` | READ var list | — | A X Y | Emits READ with type coercion from DATA stream | `zp_tmp1` | READ emitter |
| `codegen_emit_reloc` | address, fixup type | — | A X Y | Records a relocation entry for linker | — | Relocation entry emitter |
| `codegen_finish_line` | — | C=error | A | Validates code size, updates code layout, commits relocations | — | End-of-line code finalization |
| `codegen_get_code_ptr` | — | X/Y=current code ptr | X Y | Returns current code emission position | — | Query for tests/replay |

---

### 6.16 `src/geoasm/diagnostics.asm`

Error and warning formatting. Produces source-line context for error output.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `diag_format_error` | A=error code, X/Y=source line ptr | — | A X Y | Formats error string with line number and context | Formats "?SYNTAX ERROR IN 10" type message |
| `diag_format_warning` | A=warning code, X/Y=source line ptr | — | A X Y | Formats non-fatal warning | Warning formatter (for future use) |
| `diag_format_source_context` | X/Y=source line ptr, A=cursor offset | — | A X Y | Extracts and formats source context around error point | Error context display |
| `diag_print_error` | formatted error in buffer | — | A X Y | Outputs formatted error to current channel | Error output to screen |
| `diag_error_from_kernal` | KERNAL error in C/A | A=basic error code | A | Converts KERNAL carry/error to BASIC error code | KERNAL error translation |

---

### 6.17 `src/geoasm/math_trig.asm`

Trigonometric functions, geoRAM-resident. IEEE 754 variants use the active
numeric policy and sticky-flag machinery.

Prefer porting the legacy project's proven trig kernels when they satisfy the
routine contracts below. The legacy algorithms and source are reusable; the
legacy memory map, fixed addresses, and ZP choices are porting references only
and must be adapted to Compiler 2 generated placement and ZP manifests.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `math_sin` | FAC1=angle (radians) | FAC1=sin(angle) | A X Y | — | `zp_fac1`, `zp_arg` | SIN function |
| `math_cos` | FAC1=angle (radians) | FAC1=cos(angle) | A X Y | — | `zp_fac1`, `zp_arg` | COS function |
| `math_tan` | FAC1=angle (radians) | FAC1=tan(angle) | A X Y | — | `zp_fac1`, `zp_arg` | TAN function |
| `math_atn` | FAC1=value | FAC1=atan(value) | A X Y | — | `zp_fac1`, `zp_arg` | ATN function |
| `math_acs` | FAC1=value | FAC1=acos(value) | A X Y | — | `zp_fac1`, `zp_arg` | ACS function |
| `math_asn` | FAC1=value | FAC1=asin(value) | A X Y | — | `zp_fac1`, `zp_arg` | ASN function |

---

### 6.18 `src/geoasm/math_trans.asm`

Transcendental and IEEE 754 extended operations. Legacy `EXP`, `LOG`, `SQR`,
`RND`, and power remain callable in legacy mode; IEEE-specific entries are
enabled only when `FPMODE1` is selected.

Prefer reusing the legacy project's transcendental and IEEE extension
algorithms/source where practical. Their numerical behavior has already been
validated with Python proxy models and accuracy tests, but their storage
layout is not authoritative for Compiler 2.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `math_log` | FAC1=value | FAC1=log(value) | A X Y | Updates IEEE flags when enabled | `zp_fac1`, `zp_arg` | LOG (natural) |
| `math_exp` | FAC1=value | FAC1=exp(value) | A X Y | Updates IEEE flags when enabled | `zp_fac1`, `zp_arg` | EXP |
| `math_sqr` | FAC1=value | FAC1=sqrt(value) | A X Y | Updates IEEE flags when enabled | `zp_fac1`, `zp_arg` | SQR |
| `math_pow` | FAC1=base, ARG=exponent | FAC1=result | A X Y | Updates IEEE flags when enabled | `zp_fac1`, `zp_arg` | Exponentiation |
| `math_rnd` | FAC1=argument | FAC1=random value | A X Y | Updates deterministic RND state per profile | `zp_fac1`, `zp_arg` | RND |
| `math_fma` | X/Y=typed `(a,b,c)` operand record | FAC1=(a×b)+c | A X Y | — | `zp_fac1`, `zp_arg`, `zp_iesstp` | Fused multiply-add |
| `math_remain` | FAC1=a, ARG=b | FAC1=remainder(a/b) | A X Y | — | `zp_fac1`, `zp_arg` | IEEE remainder |
| `math_min` | FAC1=a, ARG=b | FAC1=min(a,b) | A X Y | — | `zp_fac1`, `zp_arg` | IEEE minimum |
| `math_max` | FAC1=a, ARG=b | FAC1=max(a,b) | A X Y | — | `zp_fac1`, `zp_arg` | IEEE maximum |
| `math_scalb` | FAC1=value, X=exponent | FAC1=value×2^exp | A X Y | — | `zp_fac1` | Scale by power of 2 |
| `math_logb` | FAC1=value | FAC1=unbiased exponent | A X Y | — | `zp_fac1` | Unbiased base-2 exponent |
| `math_mant` | FAC1=value | FAC1=mantissa | A X Y | — | `zp_fac1` | Extract mantissa |
| `math_rint` | FAC1=value | FAC1=rounded integer | A X Y | — | `zp_fac1` | Round to integer per rounding mode |
| `math_nextup` | FAC1=value | FAC1=next larger representable | A X Y | — | `zp_fac1` | NextUp |
| `math_nextdown` | FAC1=value | FAC1=next smaller representable | A X Y | — | `zp_fac1` | NextDown |
| `math_copysign` | FAC1=value1, ARG=value2 | FAC1=abs(value1) with sign(value2) | A X Y | — | `zp_fac1`, `zp_arg` | Copy sign |
| `math_totalorder` | FAC1=a, ARG=b | A=comparison result | A X Y | — | `zp_fac1`, `zp_arg` | Total ordering comparison |
| `math_isnan` | FAC1=value | A=0/1 | A | — | `zp_fac1` | Is NaN |
| `math_issnan` | FAC1=value | A=0/1 | A | — | `zp_fac1` | Is signaling NaN |
| `math_isinf` | FAC1=value | A=0/1 | A | — | `zp_fac1` | Is infinite |
| `math_isfin` | FAC1=value | A=0/1 | A | — | `zp_fac1` | Is finite |
| `math_isnorm` | FAC1=value | A=0/1 | A | — | `zp_fac1` | Is normalized |
| `math_iszero` | FAC1=value | A=0/1 | A | — | `zp_fac1` | Is zero |
| `math_sgnbit` | FAC1=value | A=sign bit (0/1) | A | — | `zp_fac1` | Sign bit extraction |
| `math_isunord` | FAC1=a, ARG=b | A=0/1 | A | — | `zp_fac1`, `zp_arg` | Is unordered (either NaN) |
| `math_bin32str` | FAC1=value | string in buffer | A X Y | Converts to IEEE 754 binary32 hex string | `zp_fac1` | BIN32$: value → "XXXXXXXX" hex |
| `math_val32` | string in buffer | FAC1=numeric value | A X Y | Parses 8-digit hex string → numeric | `zp_fac1` | VAL32$: hex string → value |

---

### 6.19 `src/runtime/variables.asm`

Scalar variable resolution, load, store, type promotion. Compiled code
calls these for every variable access.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `var_resolve` | X/Y=variable descriptor | X/Y=cell address | A X Y | Resolves variable descriptor to live memory cell | `zp_tmp1`, `zp_tmp2` | Variable resolution: descriptor → address |
| `var_load_int` | X/Y=cell address | X/Y=16-bit value | A X Y | Loads 16-bit integer from cell | — | Integer variable load |
| `var_store_int` | X/Y=typed cell/value record | C=error | A X Y | Stores 16-bit integer to cell | — | Integer variable store |
| `var_load_float` | X/Y=cell address | FAC1=float value | A X Y | Loads 5-byte float from cell | `zp_fac1` | Float variable load |
| `var_store_float` | X/Y=cell address, FAC1=value | — | A X Y | Stores 5-byte float to cell | `zp_fac1` | Float variable store |
| `var_load_string` | X/Y=cell address | X/Y=ptr, A=len | A X Y | Loads string descriptor from cell | — | String variable load |
| `var_store_string` | X/Y=typed cell/source descriptor record | C=error | A X Y | Stores string descriptor to cell | — | String variable store |
| `var_promote_to_float` | X/Y=integer value | FAC1=float equivalent | A X Y | Promotes integer to float | `zp_fac1` | Type promotion: int → float |
| `var_coerce` | FAC1=float, target type in A | result in FAC1 or X/Y | A X Y | Coerces value to target type with BASIC V2 error behavior | `zp_fac1` | Type coercion with error on loss |
| `var_set_type` | X/Y=descriptor, A=type tag | — | A | Updates type tag in variable descriptor | — | Variable type annotation |

---

### 6.20 `src/runtime/arrays.asm`

Array resolution, DIM, element access.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `arr_dim` | X/Y=typed array/dimensions request | C=error | A X Y | Allocates array storage, sets dimensions in descriptor | `zp_tmp1`, `zp_tmp2` | DIM handler |
| `arr_resolve_element` | X/Y=typed descriptor/subscripts request | X/Y=element handle, C=error | A X Y | Bounds-checks subscripts, computes element offset | `zp_tmp1`, `zp_tmp2` | Array element resolution |
| `arr_load_element` | X/Y=element address, type in descriptor | value in FAC1 or X/Y | A X Y | Loads typed element from resolved address | `zp_fac1` | Array element load |
| `arr_store_element` | X/Y=typed element/value request | C=error | A X Y | Stores typed element to resolved address | `zp_fac1` | Array element store |
| `arr_redim` | X/Y=descriptor and requested dimensions record | C=error | A X Y | Rejects an already dimensioned array with stock `REDIM'D ARRAY` behavior | `zp_tmp1`, `zp_tmp2` | Existing-array guard |
| `arr_free` | X/Y=descriptor | — | A X Y | Releases array storage back to arena | — | Array deallocation |
| `arr_check_bounds` | subscript in X/Y, dimension limit | C=1 if out of bounds | A | Bounds check without resolution | — | Bounds-only check helper |

---

### 6.21 `src/runtime/strings.asm`

String allocation, assignment, slicing, comparison, and reclamation.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `str_alloc` | A=length | X/Y=ptr, C=error | A X Y | Allocates string payload (geoRAM page or normal RAM) | `zp_tmp1` | String allocation |
| `str_free` | X/Y=descriptor | — | A X Y | Reclaims string storage | — | String deallocation |
| `str_assign` | X/Y=typed destination/source descriptor record | C=error | A X Y | Assigns string value (copy or handle swap) | `zp_tmp1`, `zp_tmp2` | String assignment with copy semantics |
| `str_copy` | X/Y=typed source/destination slice record | C=error | A X Y | Copies string bytes between validated storage classes | — | Raw string copy |
| `str_concat` | X/Y=typed left/right descriptor record | X/Y=result descriptor, C=error | A X Y | Concatenates into new allocation | `zp_tmp1`, `zp_tmp2` | String concatenation (+) |
| `str_left` | X/Y=typed string/count record | X/Y=result descriptor, C=error | A X Y | LEFT$(str, n) | — | LEFT$ function |
| `str_right` | X/Y=typed string/count record | X/Y=result descriptor, C=error | A X Y | RIGHT$(str, n) | — | RIGHT$ function |
| `str_mid` | X/Y=typed string/start/count record | X/Y=result descriptor, C=error | A X Y | MID$(str, start [,len]) | — | MID$ function |
| `str_len` | X/Y=ptr | A=length | A | Returns string length | — | LEN function |
| `str_cmp` | X/Y=typed left/right descriptor record | A=three-way result, C=error | A X Y | PETSCII bytewise comparison per stock semantics | — | String comparison |
| `str_chr` | A=character code | X/Y=ptr, A=1 | A X Y | Creates one-character string using C64 PETSCII byte semantics | — | CHR$ function |
| `str_asc` | X/Y=ptr, A=len | A=first PETSCII byte | A | Errors on an empty string per stock behavior | — | ASC function |
| `str_val` | X/Y=ptr, A=len | FAC1=numeric value | A X Y | Parses numeric string to float | `zp_fac1` | VAL function |
| `str_str` | FAC1=numeric value | X/Y=ptr, A=len | A X Y | Formats float to numeric string | `zp_fac1` | STR$ function |

---

### 6.22 `src/runtime/math_core.asm`

Resident numeric arithmetic. Always in normal RAM (not geoRAM) for
compiled-program speed.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `math_add` | FAC1=left, ARG=right | FAC1=result | A X Y | — | `zp_fac1`, `zp_arg` | Float addition (+) |
| `math_sub` | FAC1=left, ARG=right | FAC1=result | A X Y | — | `zp_fac1`, `zp_arg` | Float subtraction (-) |
| `math_mul` | FAC1=left, ARG=right | FAC1=result | A X Y | — | `zp_fac1`, `zp_arg` | Float multiplication (*) |
| `math_div` | FAC1=left, ARG=right | FAC1=result, C=error | A X Y | C=1 on division by zero | `zp_fac1`, `zp_arg` | Float division (/) |
| `math_negate` | FAC1=value | FAC1=-value | A | — | `zp_fac1` | Float negation (unary -) |
| `math_cmp` | FAC1=a, ARG=b | N/Z/V flags | A X Y | — | `zp_fac1`, `zp_arg` | Float comparison (=, <>, <, >) |
| `math_int` | FAC1=value | FAC1=floor(value) | A X Y | — | `zp_fac1` | Stock BASIC `INT`: greatest integer not greater than the operand |
| `math_sgn` | FAC1=value | FAC1=sgn(value) | A | — | `zp_fac1` | SGN function (-1, 0, +1) |
| `math_abs` | FAC1=value | FAC1=abs(value) | A | — | `zp_fac1` | ABS function |
| `math_fpe` | FAC1=value | — | A | Sets flags: N=negative, Z=zero | `zp_fac1` | Floating-point examine (set N/Z for branching) |
| `math_int_to_float` | X/Y=integer | FAC1=float | A X Y | — | `zp_fac1` | 16-bit integer to float conversion |
| `math_float_to_int` | FAC1=float | X/Y=integer | A X Y | Truncates toward zero | `zp_fac1` | Float to 16-bit integer conversion |
| `math_add_int` | X/Y=typed 16-bit operand record | X/Y=result, C=overflow/error | A X Y | — | — | Integer addition |
| `math_sub_int` | X/Y=typed 16-bit operand record | X/Y=result, C=overflow/error | A X Y | — | — | Integer subtraction |
| `math_mul_int` | X/Y=typed 16-bit operand record | X/Y=result, C=overflow/error | A X Y | — | — | Integer multiplication |
| `math_div_int` | X/Y=typed dividend/divisor record | result record, C=error | A X Y | Division-by-zero and overflow follow numeric profile | — | Integer division with remainder |

---

### 6.23 `src/runtime/control.asm`

Control flow: FOR/NEXT generic frame, GOSUB/RETURN, ON GOTO/GOSUB,
STOP, CONT, END.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `ctrl_for_init` | var desc, start/limit/step in FAC1 | — | A X Y | Pushes FOR frame onto control stack, initializes variable | `zp_tmp1`, `zp_tmp2` | FOR statement initialization |
| `ctrl_for_next` | var desc, loop descriptor | C=1 loop done, C=0 loop continues | A X Y | Increments variable, compares to limit, branches or pops | `zp_tmp1`, `zp_tmp2` | NEXT statement: update and test |
| `ctrl_do_init` | loop descriptor | — | A X Y | Pushes DO frame onto control stack | `zp_tmp1` | DO statement initialization |
| `ctrl_loop_test` | loop descriptor, condition result | C=1 exit, C=0 continue | A X Y | Tests WHILE/UNTIL condition at loop bottom (posttest) | `zp_tmp1` | LOOP condition test |
| `ctrl_exit_loop` | loop descriptor | — | A X Y | Pops control stack to matching DO, jumps past LOOP | `zp_tmp1` | EXIT DO/FOR |
| `ctrl_gosub` | target line address | — | A X Y | Pushes return address, jumps to target | `zp_tmp1`, `zp_sublev` | GOSUB implementation |
| `ctrl_return` | — | — | A X Y | Pops return address, validates GOSUB nesting | `zp_tmp1`, `zp_sublev` | RETURN implementation |
| `ctrl_on_goto` | expr result in A, table ptr | — | A X Y | Multi-way branch: select line from table | `zp_tmp1` | ON ... GOTO implementation |
| `ctrl_on_gosub` | expr result in A, table ptr | — | A X Y | Multi-way subroutine call | `zp_tmp1`, `zp_sublev` | ON ... GOSUB implementation |
| `ctrl_stop` | generated continuation point and runtime frame handle | — | A X Y | Publishes a generation-checked continuation descriptor, returns to shell | `zp_cont_handle`, `zp_cont_generation`, `zp_stop_flag` | STOP statement |
| `ctrl_end` | runtime profile | does not return to caller | declared unwind set | Calls unified graphics exit, then development editor or standalone READY shell | — | END statement |
| `ctrl_cont` | valid continuation handle/generation | — | A X Y | Validates/restores compiled PC and runtime control/stack state | `zp_cont_handle`, `zp_cont_generation` | CONT statement |
| `ctrl_check_stop` | — | Z=1 if STOP pressed | A | Polls STOP key via KERNAL bridge; bounded iteration check | `zp_stkey` | STOP polling in long loops |
| `ctrl_push_loop_frame` | loop descriptor | — | A X Y | Pushes loop frame (FOR/DO) onto control stack | `zp_tmp1`, `zp_tmp2` | Internal: push loop frame |
| `ctrl_pop_loop_frame` | — | loop descriptor restored | A X Y | Pops loop frame from control stack | `zp_tmp1`, `zp_tmp2` | Internal: pop loop frame |

---

### 6.24 `src/runtime/io.asm`

PRINT, INPUT, GET, CMD — compiled runtime I/O through the KERNAL bridge.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `io_print_value` | value in FAC1, type tag in A | — | A X Y | Formats and outputs value (numeric or string) to current channel | `zp_fac1` | PRINT value output |
| `io_print_newline` | — | — | A | Outputs CR (carriage return) | — | PRINT newline |
| `io_print_space` | — | — | A | Outputs space character | — | PRINT space (SPC) |
| `io_print_tab` | A=column | — | A X Y | Outputs spaces to reach tab stop | — | TAB function |
| `io_print_comma` | — | — | A | Outputs spaces to next 10-column zone | — | PRINT comma zone advance |
| `io_print_semicolon` | — | — | A | Suppresses newline/space (no output) | — | PRINT semicolon: no separator |
| `io_input_value` | X/Y=typed destination/prompt/channel record | C=error | A X Y | Prints prompt "? ", reads value, coerces, stores | `zp_fac1` | INPUT statement value read |
| `io_input_string` | X/Y=typed destination/prompt/channel record | C=error | A X Y | Prints prompt, reads string line | `zp_tmp1` | INPUT statement string read |
| `io_get` | var descriptor | — | A X Y | Reads single character from keyboard buffer into variable | — | GET statement |
| `io_cmd` | channel number, expr list | — | A X Y | CMD: redirects output to channel | — | CMD statement |

---

### 6.25 `src/runtime/runtime_io.asm`

KERNAL-bridged file I/O for LOAD, SAVE, OPEN, CLOSE as used by compiled
programs.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `rio_load` | X/Y=typed filename/device/address record | X/Y=load result, C=error | A X Y | KERNAL-bridged direct program load | LOAD implementation |
| `rio_save` | X/Y=typed filename/device/range record | C=error | A X Y | KERNAL-bridged direct program save | SAVE implementation |
| `rio_verify` | X/Y=typed filename/device/range record | C=error | A X Y | KERNAL-bridged compare without replacement | VERIFY implementation |
| `rio_open` | X/Y=typed LF/device/SA/name record | C=error | A X Y | KERNAL-bridged file open | OPEN implementation |
| `rio_close` | A=lf | C=error | A X Y | KERNAL-bridged file close | Compiled CLOSE implementation |
| `rio_chrin` | A=lf | A=byte | A X Y | KERNAL-bridged character input | Compiled channel read |
| `rio_chrout` | A=byte, X=lf | C=error | A X Y | KERNAL-bridged character output | Compiled channel write |
| `rio_clrchn` | — | — | A X Y | KERNAL-bridged channel restore | Compiled CLRCHN |

---

### 6.26 `src/runtime/errors.asm`

BASIC error construction, unwind, and the STOP/CONT resumable state machine.

| Routine | In | Out | Clob | Side | ZP (W) | Purpose |
|---|---|---|---|---|---|---|
| `err_raise` | A=error code, X/Y=error-context record | does not return to caller | declared unwind set | Closes/restores channels, calls unified graphics exit, formats stock message, enters profile READY shell | `zp_errnum`, `zp_errline`, `zp_errptr` | BASIC error raise |
| `err_raise_direct` | A=error code | (never returns) | — | Formats error for direct mode: "?CODE ERROR" | `zp_errnum` | Direct-mode error raise |
| `err_from_kernal` | KERNAL error in carry | A=basic error code | A | Translates KERNAL carry/status to BASIC error code | — | KERNAL error translation |
| `err_syntax` | — | (never returns) | — | Shortcut: raises ?SYNTAX ERROR | — | Syntax error shortcut |
| `err_type` | — | (never returns) | — | Shortcut: raises ?TYPE MISMATCH ERROR | — | Type mismatch error shortcut |
| `err_overflow` | — | (never returns) | — | Shortcut: raises ?OVERFLOW ERROR | — | Overflow error shortcut |
| `err_outofmemory` | — | (never returns) | — | Shortcut: raises ?OUT OF MEMORY ERROR | — | Out of memory error shortcut |
| `err_undefdfunction` | X/Y=fn name | (never returns) | — | Shortcut: raises ?UNDEF'D FUNCTION ERROR | — | Undefined function error |
| `err_break` | continuation point/runtime frame | (never returns to caller) | declared unwind set | Raises `?BREAK IN line`, publishes CONT descriptor | `zp_cont_handle`, `zp_cont_generation`, `zp_stop_flag` | STOP-key break |
| `err_save_cont` | continuation point/runtime frame | X/Y=continuation handle, C=error | A X Y | Copies all required resumable state before stack unwind | `zp_cont_handle`, `zp_cont_generation`, `zp_stop_flag` | Save generation-checked CONT state |

---

### 6.27 `src/runtime/inspection.asm`

Source-free shell for standalone `COMPILE` exports. The generated command table
accepts one-term `?`/`PRINT`, `CONT`, loader-only `LIST`, `RUN`, `LOAD`,
`SAVE`, `VERIFY`, `CLR`, and every `$`/`/`/`@`/`!` wedge form. It rejects
assignment, compound expressions, numbered-line entry, editing, and arbitrary
BASIC statements.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `inspect_shell` | (never returns normally) | — | A X Y | Main REPL loop: reads input, dispatches restricted grammar | Inspection shell main loop |
| `inspect_parse_command` | input buffer | C=1 invalid | A X Y | Validates input against restricted grammar | Grammar gate for inspection shell |
| `inspect_print_var` | variable name token | — | A X Y | Resolves and prints scalar or array element | ?A / PRINT A handler |
| `inspect_print_string_var` | variable name token | — | A X Y | Resolves and prints string variable or array element | ?A$(N) / PRINT A$(N) handler |
| `inspect_cont` | valid continuation handle/generation | — | A X Y | Restores compiled continuation descriptor and runtime state | CONT in inspection shell |
| `inspect_list_loader` | optional whitespace only | — | A X Y | Prints exactly `2026 SYS2061` | Source-free LIST behavior |
| `inspect_run` | optional whitespace only | does not return on success | A X Y | Reinitializes and enters current compiled image | RUN |
| `inspect_load` | generated LOAD grammar | C=error | A X Y | Uses standalone KERNAL file path/current `fa` | LOAD |
| `inspect_save` | generated SAVE grammar | C=error | A X Y | Uses standalone KERNAL file path/current `fa` | SAVE |
| `inspect_verify` | generated VERIFY grammar | C=error | A X Y | Uses standalone KERNAL file path/current `fa` | VERIFY |
| `inspect_clr` | optional whitespace only | — | A X Y | Clears variables, arrays, strings, frames, continuation | CLR |
| `inspect_wedge` | validated prefix command | C=error | A X Y | Calls standalone wedge service; shares `fa` | `$`, `/`, `@`, `!` |

---

### 6.28 `src/arena/arena_core.asm`

Typed arena create/destroy/check, generation stamp. Manages the typed
arena directory described in DESIGN2 §7.4.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `arena_init_all` | — | — | A X Y | Constructs arena directory, stamps initial generations for all arenas | Arena directory cold-start initialization |
| `arena_create` | A=type, X/Y=capacity | X/Y=arena handle | A X Y | Creates one typed arena, allocates pages | Single arena construction |
| `arena_destroy` | X/Y=arena handle | — | A X Y | Destroys arena, frees pages | Arena teardown |
| `arena_check_integrity` | X/Y=arena handle | C=1 corruption | A X Y | Validates canary, checksum, generation | Arena integrity verification |
| `arena_reset` | X/Y=arena handle | — | A X Y | Deterministic reset: clears data, increments generation | Arena reset for NEW/RUN |
| `arena_invalidate_generation` | X/Y=arena handle | — | A | Increments generation, invalidates stale handles | Generation bump |
| `arena_get_handle` | X/Y=arena handle, offset | X/Y=stable handle | A X Y | Resolves arena-relative offset to stable handle | Handle resolution |
| `arena_handle_valid` | X/Y=handle | C=0 valid, C=1 stale/out-of-bounds | A, flags | Checks type, owner, bounds, generation | Stale-handle detection |

---

### 6.29 `src/arena/page_alloc.asm`

GeoRAM free-page bitmap allocator. Shared by all arenas.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `page_alloc_init` | — | — | A X Y | Initializes free-page bitmap from detected geoRAM capacity | Page allocator cold-start |
| `page_alloc` | X/Y=extent request (16-bit count/alignment/owner) | X/Y=extent handle, C=error | A X Y | Allocates pages from free bitmap | Page allocation |
| `page_free` | X/Y=validated extent handle | C=error | A X Y | Returns pages to free bitmap and checks ownership/generation | Page deallocation |
| `page_alloc_count` | — | X/Y=16-bit pages free | A X Y | Supports at least 2,048 pages at the 512 KiB minimum | Free page count query |
| `page_alloc_largest` | — | X/Y=16-bit largest run | A X Y | Returns largest contiguous extent | Fragmentation query |
| `page_check_in_range` | X/Y=extent descriptor | C=1 if out of profile/owner bounds | A X Y | Uses logical page/block capacity from installed profile | Bounds check |

---

### 6.30 `src/arena/overlay_dispatch.asm`

Overlay code dispatch: swaps geoRAM pages for overlay routines.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `overlay_enter` | A=overlay ID | — | A X Y | Swaps in overlay page, adjusts dispatch table | Overlay page swap-in |
| `overlay_exit` | — | — | A X Y | Restores previous overlay page | Overlay page swap-out |
| `overlay_resolve` | A=routine ID | X=page, Y=offset | A X Y | Resolves routine ID to geoRAM page and entry offset | ID → physical address resolution |
| `overlay_validate` | — | C=1 if directory corrupt | A X Y | Validates overlay directory checksums and ABI versions | Directory integrity check |

---

### 6.31 `src/arena/georam_detect.asm`

Non-destructive geoRAM detection and capacity measurement. Separated from
the loader so it can be called from the installed environment if needed.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `detect_georam` | build-declared minimum/profile schema | X/Y=profile record, C=error | A X Y | Full non-destructive probe before arenas are trusted | Sole installation detector |
| `detect_save_state` | — | — | A X Y | Saves current geoRAM selection, probe bytes, processor status | State preservation before probe |
| `detect_probe_pattern1` | — | — | A X Y | Writes and verifies pattern order 1 on candidate pages | First probe pattern |
| `detect_probe_pattern2` | — | — | A X Y | Writes and verifies pattern order 2 (debug: catches floating bus) | Second probe pattern (debug) |
| `detect_probe_aliasing` | — | capacity | A X Y | Probes address-bit aliasing to bound total capacity | Aliasing/capacity detection |
| `detect_restore_state` | — | — | A X Y | Restores all saved bytes, selection, and processor status | State restoration (success or failure) |
| `detect_check_minimum` | — | C=1 if below minimum | A | Compares detected capacity against build-declared minimum | Capacity threshold check |
| `detect_publish_profile` | X/Y=validated detection result | X/Y=immutable profile | A X Y | Records 16 KiB block count, alias result, integrity fingerprint | Install profile |
| `detect_validate_profile` | X/Y=installed profile | C=1 mismatch/corruption | A X Y | Bounded continuity check; mismatch calls fatal path, never resizes | Session integrity |

---

### 6.32 `src/arena/context_stack.asm`

Fixed-depth context stack for geoRAM call nesting.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `ctx_init` | — | — | A | Resets context stack pointer to empty | Context stack initialization |
| `ctx_push` | X/Y=context-record pointer | C=error | A X Y | Pushes selected block/page, P, declared registers/results; checks first | Context save for nesting |
| `ctx_pop` | X/Y=destination record | C=error | A X Y | Pops complete caller context; detects underflow | Context restore |
| `ctx_depth` | — | A=current depth | A | Returns current nesting depth (for debug) | Depth query |
| `ctx_check_overflow` | — | C=1 if full | A | Checks if next push would overflow | Overflow guard |

---

### 6.33 `src/resident/resident_main.asm`

Resident editor loop and boundary assertions. It drains the KERNAL queue with
`GETIN`; it never scans the keyboard or advances the clock.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `resident_main` | initialized environment | does not return | A X Y | Captures editor input and dispatches complete lines | READY/editor loop |
| `resident_poll_input` | mailbox handle in X/Y | A=byte or zero | A X Y | Calls foreground `GETIN` bridge only | Nonblocking input drain |
| `resident_submit_line` | X/Y=line mailbox handle | C=error | A X Y | Calls direct-prefix dispatch or geoRAM editor service | Transactional handoff |
| `resident_assert_boundary` | public-boundary ID | C=error in debug | A, flags | Checks `$01=$35`, D clear, gate mirror, stack watermark | Common debug assertion |

### 6.34 `src/resident/fatal.asm`

One clean failure path for absent/changed geoRAM profiles and corrupt arena or
dispatch metadata.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `fatal_georam` | A=reason, X/Y=diagnostic record | does not return to service | declared unwind set | Stops allocation/execution, restores selection/mapping/P, closes channels, reports reinstall requirement | Fatal integrity exit |
| `fatal_restore_machine` | saved gate/bridge context | canonical editor-safe state | A X Y, flags | Restores page selection, `$01`, channels, graphics, IRQ state | Shared bounded cleanup |

### 6.35 `src/geoasm/editor_svc.asm`

The geoRAM half of the editor. It owns logical lines and invokes the same
transactional compiler path used by immediate execution.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `editor_submit_line` | X/Y=captured-line handle | C=error, A=error | A X Y | Parses optional line number; publishes source/code together or changes nothing | Numbered/direct submission |
| `editor_delete_line` | X/Y=line number record | C=error | A X Y | Runs dependency repair and one-generation deletion publish | Delete numbered line |
| `editor_detokenize_line` | X/Y=canonical line handle | X/Y=text handle, C=error | A X Y | Allocates scratch text only | LIST conversion |
| `editor_list_range` | X/Y=validated range record | C=error | A X Y | Streams canonical detokenization through output path | LIST and ranges |
| `editor_ready_transition` | publication result handle | — | A X Y | Atomically changes mailbox/editor state to READY or error | Observable synchronization point |

### 6.36 `src/geoasm/program_codec.asm`

External program codec. Decode always completes in scratch storage before the
current program can be replaced.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `program_classify_file` | X/Y=input byte-stream handle | A=stock/extended, C=error | A X Y | Reads only bounded header bytes | Classify before extension decoding |
| `program_decode_stock` | X/Y=input handle | X/Y=scratch program handle, C=error | A X Y | Validates `$0801`, links, ordering, terminators, stock tokens/contexts | BASIC V2 import |
| `program_encode_stock` | X/Y=logical program handle | X/Y=byte-stream handle, C=error | A X Y | Canonically recomputes every next-line pointer | Byte-compatible BASIC V2 SAVE |
| `program_decode_extended` | X/Y=input handle | X/Y=scratch program handle, C=error | A X Y | Validates magic, format/ABI version, token namespace, bounds | Versioned extension import |
| `program_encode_extended` | X/Y=logical program handle | X/Y=byte-stream handle, C=error | A X Y | Writes unambiguous versioned envelope | Extension SAVE |

### 6.37 `src/geoasm/program_store.asm`

Logical tokenized-program directory and copy-on-publish transactions.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `program_tx_begin` | current source generation | X/Y=transaction handle, C=error | A X Y | Allocates scratch directory/records | Begin isolated edit |
| `program_tx_put_line` | X/Y=transaction + line record | C=error | A X Y | Replaces/inserts only scratch record | Stage line |
| `program_tx_delete_line` | X/Y=transaction + line number | C=error | A X Y | Removes only scratch record | Stage deletion |
| `program_tx_commit` | X/Y=validated transaction | X/Y=new generation record, C=error | A X Y | Atomically swaps directory root | Publish source generation |
| `program_tx_abort` | X/Y=transaction | — | A X Y | Frees scratch; published root unchanged | Roll back |
| `program_replace_from_load` | X/Y=fully decoded scratch program | C=error | A X Y | Publishes only after format and dependency validation | Transactional LOAD |

### 6.38 `src/geoasm/direct_dispatch.asm`

Generated direct-command classifier. Prefix commands are recognized before
BASIC tokenization; executable BASIC direct input uses a temporary program.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `direct_probe_prefix` | X/Y=captured text | A=wedge/normal, C=error | A X Y | Does not tokenize wedge input | `$`, `/`, `@`, `!` front door |
| `direct_classify` | X/Y=validated statement record | A=command class, C=error | A X Y | Uses generated table only | Direct/program policy |
| `direct_execute_command` | X/Y=direct-command record | C=error | A X Y | Dispatches NEW/RUN/CONT/CLR/LIST/COMPILE/file/mode commands | Direct-only commands |
| `direct_execute_temporary` | X/Y=tokenized direct line | C=error | A X Y | Compiles, executes, and discards one-line temporary generation | Single immediate compiler path |

### 6.39 `src/geoasm/compiler_pipeline.asm`

Coordinator for all eight deterministic compiler boundaries.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `pipeline_compile_line` | X/Y=canonical source record | X/Y=scratch compiled record, C=error | A X Y | Runs boundaries 1-7 without publication | Per-line compile |
| `pipeline_compile_program` | X/Y=source-generation handle | X/Y=scratch image, C=error | A X Y | Resolves all dirty records/layout/dependencies | Whole-program compile/relink |
| `pipeline_serialize_boundary` | A=boundary ID, X/Y=record handle | X/Y=versioned byte record, C=error | A X Y | Debug/host replay artifact | Boundaries 1-8 |
| `pipeline_validate_boundary` | A=boundary ID, X/Y=record handle | C=error | A X Y | Checks schema/version/checksum | Deterministic replay guard |
| `pipeline_report_failure` | phase/line/error record | does not return to caller | A X Y | Leaves all published outputs unchanged | Phase-localized failure |

### 6.40 `src/geoasm/incremental.asm`

Dependency fingerprints, dirty repair, and atomic source/compiled publication.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `incremental_fingerprint` | X/Y=source and dependency record | X/Y=fingerprint handle | A X Y | Includes all generations named by `DESIGN2.md` §6.2 | Cache key |
| `incremental_mark_dependents` | X/Y=edit descriptor | X/Y=dirty-set handle, C=error | A X Y | Tracks branch, DATA, loop, subroutine, variable, layout effects | Structural invalidation |
| `incremental_resolve_dirty` | X/Y=transaction/dirty set | C=error | A X Y | Recompiles or relinks every required record | No interpreter fallback |
| `incremental_publish` | X/Y=validated source/code transaction | X/Y=new generation record, C=error | A X Y | Atomically swaps both roots and image checksum | Publication rule |
| `incremental_can_run` | X/Y=current generation | C=0 executable, C=1 blocked | A X Y | Checks no dirty records, verified layout/checksum | RUN guard |
| `incremental_abort` | X/Y=transaction | — | A X Y | Frees scratch, preserves last valid generation | Rollback |

### 6.41 `src/geoasm/compile_export.asm`

Constructs a source-free standalone image against the normal-RAM runtime
profile; it never copies a development image merely because that image runs.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `export_parse_command` | X/Y=COMPILE command record | X/Y=options, C=error | A X Y | Defaults filename `COMPILED`, device from persistent `fa` | Syntax/defaults |
| `export_collect_dependencies` | X/Y=compiled image | X/Y=runtime dependency set, C=error | A X Y | Rejects editor/compiler/source/geoRAM dependencies | Standalone closure |
| `export_link_image` | X/Y=image/options | X/Y=standalone image, C=error | A X Y | Resolves runtime helpers, metadata, descriptors, shell | Export link |
| `export_check_budgets` | X/Y=standalone image/workspace plan | C=error | A X Y | Proves `$0801-$CFFF` load range and disjoint workspace | Code/workspace budgets |
| `export_write_prg` | X/Y=validated image/options | C=error | A X Y | Saves through KERNAL sequence to devices 8-11 | COMPILE output |

### 6.42 `src/geoasm/dos_wedge.asm`

Development-environment wedge parser/orchestrator. It uses the same generated
grammar and normal-RAM wedge core as standalone exports, while keeping editor
formatting and large scratch work in geoRAM.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `wedge_parse` | X/Y=raw prefix command | X/Y=validated command record, C=error | A X Y | Enforces direct-only grammar and confirmation flags | Prefix parser |
| `wedge_dispatch_development` | X/Y=validated command record | C=error | A X Y | Binds editor output/scratch and calls normal-RAM core | Development dispatcher |
| `wedge_format_directory` | X/Y=directory stream/format record | C=error | A X Y | Formats directory without replacing tokenized program | Development formatting |

### 6.43 `src/runtime/graphics.asm`

Graphics lifecycle and the single restore path shared by END, error, STOP, and
STOP-key interruption.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `graphics_enter` | X/Y=validated graphics allocation plan | C=error | A X Y | Transactionally reserves `$DC00-$FF3F`, selects VIC bank 3/`$D018=$78` | Enter bitmap mode |
| `graphics_exit` | A=exit reason | — | A X Y | Restores stock text/colors, invalidates graphics data, then restores ceiling | Sole exit path |
| `graphics_matrix_copy` | X/Y=bounded transfer record | C=error | A X Y | Uses chunked RAM-under-I/O gate with IRQ opportunities | `$DC00-$DFE7` access |
| `graphics_validate_bounds` | X/Y=pixel/cell descriptor | C=error | A X Y | Checks bitmap/matrix/color limits | Untrusted boundary |

### 6.44 `src/runtime/ieee_state.asm`

Numeric-mode state is independent of dialect and uses the normal floating
layout. This module owns IEEE status/rounding behavior missing from pure math
operations.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `fp_get_mode` / `fp_set_mode` | generated mode record | current/new mode, C=error | A X Y | Updates mode-keyed compilation generation | FPMODE/FPMODE0/FPMODE1 |
| `fp_get_flags` / `fp_clear_flags` | flag mask | current flags | A, flags | Sticky invalid/div-zero/overflow/underflow/inexact state | FPFLAGS/FPCLR |
| `fp_set_rounding` | A=rounding ID | C=error | A, flags | Sets one of five specified rounding modes | FPSET |
| `fp_test_flags` | X/Y=test descriptor | boolean result | A X Y | Tests current/sticky flags | FPTEST/FPTTEST |
| `fp_load_constant` | A=INF/NAN/SNAN ID | FAC1=value | A X Y | Produces specified special value/printed form | IEEE constants |

### 6.45 `src/runtime/data.asm`

Runtime data-stream state is generation checked so an edit that reorders
`DATA` cannot leave a compiled `READ` cursor bound to stale records.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `data_read` | X/Y=typed destination descriptor | C=error | A X Y | Advances generation-checked DATA cursor and coerces stock-compatible value | READ |
| `data_restore` | optional line-target descriptor | C=error | A X Y | Resolves first applicable DATA record and resets cursor | RESTORE |
| `data_reset` | current source generation | — | A X Y | Initializes stream state for RUN/CLR policy | Runtime initialization |

### 6.46 `src/runtime/system.asm`

Stock machine/system primitives and special timer variables. Protected ranges
come from generated linker/arena policy and are absent from standalone exports
except for that export's real loaded/protected ranges.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `system_peek` | X/Y=16-bit address | A=byte | A X Y | Reads real C64 CPU address space under documented banking policy | PEEK |
| `system_poke` | X/Y=address/value record | C=error | A X Y | Writes real C64 address unless generated protection denies it | POKE |
| `system_sys` | X/Y=call descriptor | returned registers per stock-visible policy, C=error | A X Y | Calls user machine code with invalidation barrier | SYS |
| `system_usr` | FAC1=argument, generated USR vector | FAC1=result, C=error | A X Y | Calls user routine with declared compatibility ABI | USR |
| `system_wait` | X/Y=address/mask/xor record | C=error/STOP | A X Y | Polls real address and bank-safe STOP at bounded cadence | WAIT |
| `system_ti_load` | — | FAC1=current 24-bit jiffy value | A X Y | Reads IRQ-owned clock atomically | TI |
| `system_ti_store` | FAC1=new jiffy value | C=error | A X Y | Validates and sets clock through approved path | TI assignment |
| `system_ti_string_load` | — | X/Y=HHMMSS string descriptor | A X Y | Formats current clock with stock behavior | TI$ |
| `system_ti_string_store` | X/Y=validated HHMMSS string | C=error | A X Y | Parses/sets clock with stock behavior | TI$ assignment |

### 6.47 `src/runtime/wedge.asm`

Normal-RAM wedge core included in both installed-runtime and standalone export
profiles. It has no source/editor/compiler/geoRAM dependency.

| Routine | In | Out | Clob | Side | Purpose |
|---|---|---|---|---|---|
| `wedge_directory` | X/Y=validated options/output binding | C=error | A X Y | Streams directory; never loads over current program/image | `$` / `@$` |
| `wedge_load_absolute` | X/Y=filename/current-device record | C=error | A X Y | Equivalent to `LOAD name,fa,1` | `/` |
| `wedge_status_or_command` | X/Y=validated command record | C=error | A X Y | Reads status, selects device 8-11, or sends command | `@` |
| `wedge_stream_seq` | X/Y=filename/output record | C=error | A X Y | Streams PETSCII; STOP closes channel | `!` |
| `wedge_confirm_destructive` | X/Y=scratch/format command | C=0 confirmed, C=1 declined | A X Y | Requires explicit confirmation | Destructive guard |

---

## 7. Build System Python Tools

### 7.1 `tools/zp_alloc.py`

Zero-page graph-coloring allocator.

| Function | Input | Output | Purpose |
|---|---|---|---|
| `load_manifest` | `manifests/zero_page.json` + generated ROM call domains | Node list with fixed/movable constraints | Loads authoritative ZP inputs |
| `build_interference_graph` | Node list + interference rules | Adjacency list with edge reasons | Builds the interference graph |
| `color_graph` | Interference graph | Color assignment: node → address | Deterministic DSATUR/interval placement with bounded backtracking; avoids greedy false failures |
| `generate_output` | Color assignment | `build/zp_symbols.inc`, `.json`, `.md`, `.dot` | Produces all required zero-page artifacts |
| `validate_no_overlap` | Color assignment | Pass/fail with conflict list | Verifies no two live nodes share an address |
| `validate_contracts` | Color assignment + routine clobber lists | Pass/fail with missing-contract list | Verifies every routine's declared clobbers are in the coloring |

### 7.2 `tools/georam_pages.py`

GeoRAM page placement, routine IDs, and call directory generation.

| Function | Input | Output | Purpose |
|---|---|---|---|
| `load_routine_manifest` | `manifests/routines.json` | Versioned ABI/call/size-ceiling records | Loads contracts without scraping prose/listings |
| `assign_page_placement` | Routine records, size ceilings, call graph, capacity profile | Page assignments, entry offsets | Deterministic size/call-aware packing with bounded backtracking; must not cross `$DEFF` |
| `generate_call_directory` | Page assignments | Per-group page/offset arrays, block base/threshold or explicit block table, ABI metadata, checksum | Builds compact indexed call directory |
| `generate_routine_ids` | Routine list | Sequential IDs grouped in 256s | Assigns globally unique routine IDs |
| `generate_test_exports` | Routine list, test manifest | Test-only export symbols | Adds `test_export` labels for internal routines |
| `validate_no_cross_boundary` | Page assignments | Pass/fail | Ensures no routine crosses a 256-byte page boundary |
| `validate_linked_placement` | linker labels/map + generated directory | Pass/fail | Checks actual body size, entry offset, call edge, checksum, and declared ceiling |

### 7.3 `tools/generate_contracts.py`

Generates all non-ZP structured contracts before assembly.

| Function | Input | Output | Purpose |
|---|---|---|---|
| `generate_command_tables` | `manifests/commands.json` | token/direct-mode tables, first-character trie, `keyword_lookup_report.json` | One bounded dialect/mode classifier with reported depth/fan-out/bytes |
| `generate_runtime_abi` | `manifests/runtime_abi.json` | ABI include/JSON/version | Stable compiled-code dependency surface |
| `generate_arena_layout` | `manifests/arenas.json`, capacity profile | arena constants and `arena_layout.json` | Typed ownership and page extents |
| `generate_entry_manifests` | `manifests/routines.json` | production/test entry JSON/includes | Coverage and test-only exports |
| `generate_format_tables` | `manifests/program_formats.json` | stock/extended codec constants | Versioned program boundaries |

### 7.4 `tools/linker_config.py`

Generates the `ld65` `.cfg` file from checked-in linker policy plus
generated segments.

| Function | Input | Output | Purpose |
|---|---|---|---|
| `load_linker_policy` | `manifests/linker_policy.json` | Policy struct | Loads canonical banking assumptions, segment rules |
| `merge_generated_segments` | Policy + generated geoRAM/page data | Full `.cfg` content | Merges dynamic segments into policy template |
| `validate_no_overlap` | `.cfg` memory regions | Pass/fail with conflict list | Ensures no segment overlaps another |
| `validate_vectors` | `.cfg` + vector addresses | Pass/fail | Verifies NMI/RESET/IRQ vectors at `$FFFA-$FFFF` |
| `write_config` | `.cfg` content | `build/compiler.cfg` | Writes final linker configuration |

### 7.5 `tools/extract_segments.py`

Extracts file-backed RAM segments into the loader payload.

| Function | Input | Output | Purpose |
|---|---|---|---|
| `extract_payload` | Linker map, segment list | `build/compile.bin` | Writes only file-backed segments; skips BSS |
| `validate_payload` | Payload + manifest | Pass/fail | Validates payload ranges match manifest |

### 7.6 `tools/prepare_compressor_segments.py`

Stages segments for optional LZSS compression.

| Function | Input | Output | Purpose |
|---|---|---|---|
| `stage_segments` | `build/compile.bin`, size hints | `segments/compiler_main.bin`, `build/compressor_layout.cfg` | Prepares compressor input |
| `build_simple_prg` | `build/compile.bin` | `build/basicv3.prg` | Fallback uncompressed PRG builder |

### 7.7 `tools/package_d64.py`

Builds the D64 disk image.

| Function | Input | Output | Purpose |
|---|---|---|---|
| `build_d64` | `build/basicv3.prg`, `build/georam.bin` | `build/compiler.d64` | Creates D64 with BASICV3 and GEORAM files |
| `validate_d64` | D64 image, manifest | Pass/fail | Validates directory, file names, load addresses, sizes |
| `validate_prg_header` | `build/basicv3.prg` | Pass/fail | Validates PRG load address `$0801` and loader stub |

### 7.8 `tools/validate_build.py`

Cross-artifact contract checks.

| Function | Input | Output | Purpose |
|---|---|---|---|
| `validate_tool_versions` | Tool paths | Pass/fail + version record | Checks ca65/ld65 versions against baseline |
| `validate_manifests` | All JSON manifests | Pass/fail | Schema and cross-reference validation |
| `validate_routine_directory` | `routine_directory.json`, linker map | Pass/fail | Routine ID ↔ placement ↔ directory consistency |
| `validate_arena_layout` | `arena_layout.json`, linker map | Pass/fail | Arena ID ↔ layout ↔ linker segment consistency |
| `validate_zp_allocation` | `zp_allocation.json`, linker map | Pass/fail | ZP allocation ↔ linker symbol consistency |
| `validate_size_report` | `size_report.json`, linker map | Pass/fail | Resident/geoRAM byte counts within budget |
| `validate_program_formats` | stock/extended fixtures and manifests | Pass/fail | Canonical stock relinking and extension version rejection |
| `validate_runtime_abi` | emitted dependencies + ABI manifest | Pass/fail | No private compiler/editor/geoRAM dependency in exports |
| `validate_keyword_lookup` | command manifest + trie/report + tokenizer timings | Pass/fail | Proves coverage, abbreviation/dialect behavior, no scan fallback, and reported bounds |
| `validate_generated_reference` | `API.md`, `MAP.md`, structured build artifacts | Pass/fail | API completeness/calling conventions and memory-map consistency |
| `validate_no_stale_generated` | source manifests + declared generated outputs | Pass/fail | No stale, missing, or undeclared generated file |
| `compute_build_fingerprint` | All inputs, tool versions, artifacts | Fingerprint hash | Reproducibility fingerprint |

### 7.9 `tools/test_harness.py`

Host-side test collection and runner.

| Function | Input | Output | Purpose |
|---|---|---|---|
| `collect_assembly_entries` | Public entry manifest + test entry manifest | Test coverage matrix | Verifies every callable has unit coverage |
| `replay_boundary` | Boundary serialization file | Replayed state | Replays one compilation boundary for host tests |
| `run_smoke_selection` | Test suite, smoke markers | Subset results | Runs smoke-tagged tests only |
| `run_full_selection` | Test suite, selection filter | Full results | Runs all or filtered test selection |
| `generate_requirements_matrix` | Trace records, test results | `requirements_matrix.json` | Builds machine-readable traceability matrix |

### 7.10 `tools/generate_reference.py`

Generates the two deterministic current-build references defined by
`docs/GENERATED_REFERENCE.md`.

| Function | Input | Output | Purpose |
|---|---|---|---|
| `load_reference_inputs` | validated entries/ABI/directory/map/labels/ZP/arena/size/profile artifacts | normalized reference model | Rejects missing or contradictory structured inputs |
| `generate_api` | normalized model | `build/API.md` | Emits calling-convention summary and one table row per production callable |
| `generate_map` | normalized model | `build/MAP.md` | Emits sorted CPU/ZP/segment/geoRAM/arena/standalone ranges, gaps, and totals |
| `validate_reference_model` | normalized model + linked artifacts | Pass/fail | Checks uniqueness, addresses, contracts, ranges, totals, and profiles before rendering |
| `write_deterministic` | rendered Markdown | output file | UTF-8/LF, stable ordering, no timestamps/host paths/fingerprint cycle |

---

## 8. Generated Artifacts Summary

Every full build must produce the required `docs/BUILD.md` artifacts under
`build/`. A narrowly selected developer build may omit only the D64 where that
document permits it.

| Artifact | Generator | Purpose |
|---|---|---|
| `obj/`, `listings/`, `generated/` | build/generators/ca65 | Objects, per-unit listings, generated includes/tables |
| `zp_symbols.inc` | `zp_alloc.py` | ZP symbol definitions for assembly |
| `zp_allocation.json` | `zp_alloc.py` | Machine-readable ZP allocation |
| `zp_allocation.md` | `zp_alloc.py` | Human-readable ZP allocation report |
| `zp_interference.dot` | `zp_alloc.py` | Graphviz interference graph |
| `routine_directory.json` | `georam_pages.py` | Routine ID → group/block/page/offset/ABI/checksum |
| `arena_layout.json` | `generate_contracts.py` | Arena type/schema/owner → page extents |
| `runtime_abi.json` | `generate_contracts.py` | Versioned compiled-code ABI |
| `production_entries.json` | `generate_contracts.py` | Callable production entries |
| `test_entries.json` | `generate_contracts.py` | Test-only callable entries |
| `compiler.cfg` | `linker_config.py` | Generated ld65 configuration |
| `compile.bin` | `extract_segments.py` | RAM payload for loader |
| `segments/compiler_main.bin` | `prepare_compressor_segments.py` | Compressor staging input (compressed mode) |
| `compressor_layout.cfg` | `prepare_compressor_segments.py` | Compressor configuration (compressed mode) |
| `compiler.bin` | `ld65` | Authoritative linked normal-RAM image |
| `basicv3.prg` | `build.ps1` / compressor staging tool | Installable BASIC-loadable PRG |
| `georam.bin` | (assembled from geoasm/) | geoRAM page image |
| `GEORAM_compressed.prg` | `lzss_compressor.exe --georam-stream` | Compressed GEORAM sidecar (CGS1) |
| `GEORAM_compressed.json` | `lzss_compressor.exe --georam-stream` | Sidecar metadata |
| `compiler.d64` | `package_d64.py` | Disk image for VICE testing |
| `build_manifest.json` | `build.ps1` | Build metadata and fingerprint |
| `loader_manifest.json` | `build.ps1` | Loader/installer metadata |
| `size_report.json` | `validate_build.py` | Resident and geoRAM byte counts |
| `keyword_lookup_report.json` | `generate_contracts.py` | Trie bytes, depth/fan-out bounds, lookup/tokenizer timing |
| `API.md` | `generate_reference.py` | Current production callable API and calling conventions |
| `MAP.md` | `generate_reference.py` | Current CPU/ZP/segment/geoRAM/arena/standalone map |
| `requirements_matrix.json` | `test_harness.py` | Machine-readable traceability |
| `requirements_matrix.md` | `test_harness.py` | Human-readable traceability |
| `compiler.map` | `ld65` | Linker map |
| `compiler.lbl` | `ld65` | Linker labels |

---

## 9. Assembly Source Conventions

### 9.1 File Header

Every `.asm` file begins with:

```asm
; <filename>.asm — <purpose>
; Compiler 2 — <layer name>
;
; Public entry: <list of exported labels>
; Internal helpers: <list of non-exported labels>
; Zero-page read:  <list of ZP symbols read>
; Zero-page write: <list of ZP symbols written>
; Clobbers: <registers clobbered by public entries>
```

### 9.2 Include Order

```asm
.include "common/zp.inc"         ; imports build/zp_symbols.inc
.include "common/constants.asm"  ; project-wide equates
.include "common/macros.asm"     ; assemble-time helpers
```

### 9.3 Label Naming

- Public exports: `snake_case` (e.g., `var_resolve`, `kernal_bridge_chrin`)
- Internal helpers: `_snake_case` with leading underscore (e.g., `_push_loop_frame`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `TYPE_FLOAT`, `ERR_SYNTAX`)
- Generated symbols: prefixed with `zp_` (e.g., `zp_fac1`, `zp_gr_block`)

### 9.4 Debug Sections

Debug-only code is wrapped in:

```asm
.if DEBUG
    ; debug-only checks
.endif
```

### 9.5 GeoRAM Routine Constraints

Each geoRAM routine file must:

1. Use its generated relocatable ca65 segment; source must not hard-code
   placement with `.org`.
2. Export only entries declared in `manifests/routines.json`.
3. Fit every declared routine body and entry in one 256-byte window; the
   linked body and every instruction must remain within `$DE00-$DEFF`.
4. Use the manifest-declared return kind (`RTS`, resident tail transfer, or
   non-returning unwind).
5. Declare which entries it may call (resident runtime helpers or other
   geoRAM routines through the gate).
6. Declare exact inputs, outputs, flags, stack delta, ZP read/write sets,
   arena effects, IRQ policy, and error returns. The generator rejects vague
   or register-conflicting contracts.

---

## 10. Design Coverage and Completion Gates

This trace is the validation checklist for the skeleton. “Owned” means the
design has an implementation home; it does not mean assembly or tests already
exist.

| Design area | Primary owners | Required proof before complete |
|---|---|---|
| R2/R2.1 product and install slice | loader, resident front end, geoRAM profile, Phase 1 runtime | D64 cold install; absent/undersized rejection; benchmark under 60 jiffies |
| R3 dialect/language surface | generated command/token tables, tokenizer, parser, semantic/runtime handlers | every implemented keyword maps to a handler and E2E case; disabled tokens fail at tokenization |
| R4 direct/program modes | `direct_dispatch.asm`, generated classifier | positive immediate and negative stored/compile cases for every direct-only command |
| R5 program compatibility | `program_codec.asm`, `program_store.asm` | stock V2 canonical load/save byte fixtures; malformed/unknown extension rollback |
| R6 compilation/runtime/export | pipeline, incremental publisher, runtime ABI, export linker | eight replayable boundaries; failure rollback; no dirty RUN; geoRAM-free export dependency proof |
| R7 memory/arenas | linker policy, arena/page allocator, strings, graphics | non-overlap map; generation/owner/bounds faults; separate export code/workspace budgets |
| R8 geoRAM | detector/profile, gate, directory generator, context stack | capacity/alias tests; nested/tail/callback/error-unwind tests; no IRQ selection writes |
| R9 editor/IRQ/wedge | resident loop/IRQ/screen, editor service, wedge | transactional lines; stock editing fixtures; focused VICE IRQ/keyboard/timer/wedge tests |
| R10 KERNAL | generated ROM contracts and bridge | source-audited clobbers; bank/vector/IRQ/blocking-call tests; canonical error cleanup |
| R11 optimization | descriptors, optimizer, codegen, generic runtime loops | differential fast/generic/VICE cases and explicit fallback for every fast path |
| R12 observability | debug macros, dumps/traces/fault injection, validators, generated references | canary, poison, watermark, fault-injection tests; resident size delta; complete `API.md`/`MAP.md` |
| R12.1 build | `build.ps1`, host tools, artifact/reference validators | clean/no-change byte identity; all required artifacts, deterministic references, and system contracts |
| R13 tests | generated entry manifests and pytest hierarchy | direct unit coverage for every callable plus integration/functional/system/E2E layers |
| R14 traceability | trace manifest and matrix generator | no implemented requirement, keyword, test, or stock fixture lacks provenance |
| ZP/IEEE cross-cutting | ZP allocator/ROM domains; IEEE state/math modules | generated interference proof and poison tests; independent IEEE oracle/rounding/flags coverage |

The build must also compare `manifests/routines.json` with linked exports and
these routine tables. A source entry absent from the manifest, a manifest entry
without a linked symbol, an incomplete ABI, or a callable entry without direct
unit metadata is a collection/build failure. That check prevents this document
from drifting into a persuasive but non-executable wish list.
