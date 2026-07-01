# Memory Budgets

Compiler 2 is allowed to use every byte not reserved by hardware, the canonical
banking contract, or a documented runtime invariant.

## Normal RAM

The nominal map is BASIC and KERNAL banked out, I/O visible:

- `$0000-$0001`: 6510 processor port registers;
- `$0002-$00FF`: zero page, allocated by generated lifetime coloring;
- `$0100-$01FF`: CPU stack, reserved for inherent CPU stack operation;
- `$0200-$CFFF`: RAM;
- `$D000-$DFFF`: I/O and geoRAM window/registers while I/O is visible;
- `$E000-$FFF8`: RAM;
- `$FFF9-$FFFF`: reserved guard byte plus hardware vectors.

RAM beneath I/O may be used only through the bounded RAM-under-I/O gate. KERNAL
calls must bank in KERNAL ROM explicitly through the KERNAL bridge.

## Standalone COMPILE Budget

Source-free programs produced by `COMPILE` must run on a stock C64 without
geoRAM. Their PRG load range is limited to `$0801-$CFFF`, including the BASIC
loader line and every loaded byte. With the standard `2026 SYS2061` loader, the
longest contiguous compiled payload range is `$080D-$CFFF`.

The installed Compiler 2 development environment may use geoRAM for editor
state, compiler data, diagnostics, and the physical compiled cache, but the
compiled cache is accepted only when its standalone image accounting fits:

```text
standalone_code_budget = standalone_loader_bytes + compiled_program_bytes
```

Tokenized source is not part of `compiled_program_bytes`. During development,
tokenized source may live entirely in geoRAM and may grow independently of the
standalone compiled-code budget. The maximum normal-RAM compiled-cache payload
range remains `$080D-$CFFF`, with loader bytes accounted from `$0801`.

This budget is the code-image ceiling, not the total runtime-memory ceiling.
Variables, arrays, strings, stack frames, and the standalone direct-mode
environment must fit in stock normal RAM left after the exported image is
loaded. A graphics-mode
export may use `$D000-$D7FF` RAM beneath I/O only through the documented banking
gates and only when the graphics memory contract permits it.

## geoRAM

All geoRAM pages exposed by a supported device may be assigned to arenas,
overlay code, allocator metadata, variables, tokenized programs, compiled
programs, diagnostics, and scratch storage. There is no hidden XIP reserve in
the new design.

## Strings

Strings are limited to 255 characters. The installed Compiler 2 environment
prefers geoRAM-backed string payloads when geoRAM is available, but string
descriptors and runtime helpers must also support normal-RAM-backed payloads so
COMPILE exports run on a stock C64 without geoRAM.

Each string descriptor records the payload storage class, length, capacity,
ownership, and generation. GeoRAM-backed scalar strings and string-array
elements should own one full geoRAM page and must not span pages. Normal-RAM
string payloads are not required to use page-sized allocation, but must provide
equivalent bounds, ownership, and stale-handle validation at runtime and file or
export boundaries.

## Generated Summary

Every build renders the active normal-RAM, zero-page, segment, standalone,
graphics, geoRAM, arena, reserved, dynamic, and free ranges into
`build/MAP.md`. Its rows and totals are generated from validated linker, ZP,
arena, capacity, and size artifacts as specified by
`GENERATED_REFERENCE.md`; this document remains the normative budget policy.
