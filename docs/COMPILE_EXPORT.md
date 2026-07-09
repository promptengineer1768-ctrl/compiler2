# COMPILE Export

`COMPILE` creates a source-free compiled PRG for stock C64 loading and
execution without geoRAM.

## Syntax

```text
COMPILE ["filename" [,device]]
```

If `filename` is omitted, the export filename is `COMPILED`. If `device` is
omitted, the export uses the current disk device. The current disk device is
the stock KERNAL file-device byte `fa` at `$BA`, shared with `SETLFS`, `LOAD`,
and `SAVE`. Compiler 2 supports disk devices 8 through 11; tests normally use
device 8, but a system loaded from device 9 must default subsequent bare
`COMPILE` output to device 9. DOS wedge device-selection commands such as `@10`
update the same current disk device.

The exported program contains:

- a stock BASIC V2 loader line;
- native compiled code;
- the required runtime helpers;
- relocation and version metadata already resolved for the export;
- variable descriptors needed for runtime and direct inspection;
- a source-free standalone direct-mode environment.

The export must not require the Compiler 2 editor, compiler workspace, source
arena, installed Compiler 2 environment, or geoRAM. Any runtime state needed by
the exported program, including string payloads, must be representable in normal
C64 RAM.

## Internal Export Records

The geoRAM export validator consumes fixed records. All 16-bit addresses are
little-endian and all end addresses are exclusive.

- `CP`, `name:u16`, `length:arg-byte`, `device:arg-byte` is canonicalized in
  place to `EO`, `name:u16`, `length`, `device`, `secondary`. Zero length selects
  `COMPILED`; zero device selects KERNAL `fa`. Explicit devices are 8 through 11.
- `ED`, `dependency-flags` admits standalone runtime classes in bits 0 through
  3 and rejects editor, compiler, source, or geoRAM dependencies in bits 4
  through 7.
- `EL`, `link-flags` is admitted only when bit 0 proves that the owning
  standalone linker has resolved relocation and runtime closure. The validator
  does not manufacture a linked image from an unresolved development image.
- `EB`, `image-start:u16`, `image-end:u16`, `workspace-start:u16`,
  `workspace-end:u16` validates the stock load ceiling and range disjointness.
- `EW`, `name:u16`, `length`, `device`, `secondary`, `start:u16`, `end:u16`
  is the final write record. It is emitted through the resident
  `kernal_setnam`, `kernal_setlfs`, and `kernal_save` bridge entries.

The compiler's direct-command record stores the token followed by one
contiguous `CP`, `ED`, `EL`, `EB`, `EW` plan. `direct_execute_command` passes
the plan to `export_compile_command`, which validates it in that order and
writes only after every closure and budget proof succeeds. A failure leaves the
plan unsaved; there is no partial export or validator-only success path.

Filename length, device, and secondary address are dedicated unsigned argument
bytes, not language numeric types. Numeric expressions must be converted through
the public exact `0..255` coercion helper before these records are constructed.

The standalone inspection symbol table is part of the runtime closure. Each
six-byte row contains the uppercase one- or two-character BASIC name, its
optional `$` suffix, the relocated VD address, and one reserved byte. The
linker publishes the table base and row count through `inspect_symbol_table`
and `inspect_symbol_count`. Direct `?` and `PRINT` commands resolve textual
operands through this table; unresolved and compound operands are syntax
errors and are never interpreted as addresses.

Standalone wedge commands operate through the KERNAL bridge. `$` opens and
streams the directory channel, `/` performs an absolute PRG load, bare `@`
streams the command/error channel, `@8` through `@11` update KERNAL `fa`, and
`!` streams a sequential input channel. These paths use SETNAM/SETLFS,
OPEN/CHKIN/CHRIN/CHROUT/CLRCHN/CLOSE, or LOAD rather than a dispatch-only
status record.

## Stock Memory Budget

Primary goal: programs that fit a stock C64 load image within `$0801-$CFFF`.
With `2026 SYS2061`, the conventional payload ends by `$CFFF`. The compiler
continuously reports:

```text
standalone_code_budget = standalone_loader_bytes + compiled_program_bytes
```

Soft warnings (design supersedes hard rejection), **edge-triggered**:

- crossing **up** through 80% of the stock code ceiling → one near-limit
  warning; crossing **down** through 80% → one clear/recovery status;
- crossing the 100% ceiling → `WARNING: EXCEEDS STOCK RAM` (and clear on
  leaving); do not hard-reject solely for size;
- no continuous re-print while remaining on the same side of a threshold;
- never silently truncate.

`compiled_program_bytes` includes user code, required runtime helpers,
relocation or runtime metadata, variable descriptors, the standalone
direct-mode environment, and any other byte loaded as part of the standalone
program image. Tokenized source is excluded. Development may use expansion
memory freely; stock exportability is best-effort with warnings.

Variable/array/string/stack/inspection storage for a true stock run still
must fit remaining normal RAM after the image loads.

## Export Layout Profiles

`COMPILE` selects one of two runtime layouts:

| Profile | Condition | `$CE00` |
|---|---|---|
| **Stock-compatible** | Program + required workspace fit a stock C64 without expansion or developer XIP reservations | **Free** in the export runtime (even though development may reserve `$CE00` for REU XIP) |
| **Developer** | Needs expansion-backed storage or developer-only workspace | **Reserved** (fixed page, matching the installed development layout) |

Hot pages `$C800–$CDFF` are disposable XIP cache under memory pressure and are
not permanent export reservations. Stock exports must not depend on `$CE00`
being occupied or protected. Layout choice is deterministic from measured
budgets and must be covered by export tests. User-visible size messaging
remains the edge-triggered stock budget warnings only; layout profile is
internal/export-metadata and is not a second user banner.

## No Source

The compiled PRG has no tokenized source. `LIST` in standalone direct mode
shell may reveal only the exact stock-compatible loader stub:

```basic
2026 SYS2061
```

Source reconstruction or decompilation is not a feature.

## Standalone Direct Mode

After a compiled program returns to `READY.` with valid state, the exported
runtime provides a source-free direct-mode environment. It is not a general
BASIC immediate environment and does not include a program editor.

For state inspection and continuation, it accepts:

```basic
?A
PRINT A
?A(N)
PRINT A$(N)
CONT
```

The expression after `?` or `PRINT` is one term: a scalar variable, string
variable, or one array element.

The environment also supports `RUN`, `LOAD`, `SAVE`, `VERIFY`, `CLR`, and every
DOS wedge command defined in `DOS_WEDGE.md`. File and wedge operations use the
stock KERNAL current-device state, `fa` at `$BA`; wedge device selection updates
that state for subsequent commands.

Compound expressions, assignment, program editing, and arbitrary BASIC
statements outside this required command set are rejected. `LIST` has the
loader-only behavior defined above.

`CONT` resumes compiled code from a valid STOP keyword or STOP-key interruption
state. Since there is no source, `CONT` depends only on the compiled continuation
frame, runtime state, and variable arenas.
