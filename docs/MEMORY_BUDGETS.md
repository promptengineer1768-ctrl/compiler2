# Memory Budgets

Compiler 2 is allowed to use every byte not reserved by hardware, the canonical
banking contract, or a documented runtime invariant.

## Normal RAM

The nominal map is BASIC and KERNAL banked out, I/O visible:

- `$0000-$0001`: 6510 processor port registers;
- `$0002-$00FF`: zero page, allocated by generated lifetime coloring;
- `$0100-$01FF`: CPU stack, reserved for inherent CPU stack operation;
- `$0200-$CFFF`: RAM;
- `$D000-$DFFF`: I/O, geoRAM window/registers, and REU REC (`$DF00-$DF0A`)
  while I/O is visible;
- `$E000-$FFF8`: RAM;
- `$FFF9-$FFFF`: reserved guard byte plus hardware vectors.

RAM beneath I/O may be used only through the bounded RAM-under-I/O gate. KERNAL
calls must bank in KERNAL ROM explicitly through the KERNAL bridge.

Cold code placement prefers expansion-native storage (geoRAM XIP or REU
overlays), then edit/compile-lifetime `HIBASIC` at `$E000+`, and only then RAM
beneath I/O at `$D000+`. The I/O range incurs a bank transition and conflicts
with hardware visibility commonly needed by KERNAL activity. `HIBASIC` may
overlap graphics only under the lifetime contract in `docs/GRAPHICS_MEMORY.md`.

## Standalone COMPILE Budget

Source-free programs produced by `COMPILE` must run on a stock C64 without
geoRAM or REU. Their PRG load range is limited to `$0801-$CFFF`, including the
BASIC loader line and every loaded byte. With the standard `2026 SYS2061`
loader, the longest contiguous compiled payload range is `$080D-$CFFF`.

The installed development environment may use the selected expansion backend
for editor state, compiler data, diagnostics, and the physical compiled cache,
but the compiled cache is accepted only when its standalone image accounting
fits:

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

The current development ceiling for `build/compile.bin` is 24 KiB. The increase
from the earlier 16 KiB placeholder budget accounts for the resident custom
floating-point arithmetic kernel: add, subtract, negate, multiply, divide, and
`SQR` no longer call ROM and must keep fully rounded C64 packed-float results.

## geoRAM

All geoRAM pages exposed by a supported device may be assigned to arenas,
overlay code, allocator metadata, variables, tokenized programs, compiled
programs, diagnostics, and scratch storage. There is no hidden XIP reserve in
the new design.

## Strings

Strings are limited to 255 bytes. In the installed runtime every nonempty
string owns exactly one 256-byte page in the manifest string arena (arena 5);
the unused byte is deliberate bounded internal fragmentation that keeps every
payload within one `$DE00..$DEFF` banking window. Empty strings own no page.

The sole runtime representation is the caller-owned 12-byte `SD` descriptor:
magic, nonzero descriptor generation, length, arena ID and generation, 16-bit
relative start page, payload offset, page count, and 16-bit owner token. The
current one-page allocation policy requires a zero start-page high byte, zero
payload offset, and a page count of one for nonempty strings. Empty descriptors
retain the current arena ID and generation but have zero length, start page,
offset, page count, and owner token. Payload capacity is therefore the number
of pages in the string arena, while descriptor storage is charged to the owning
scalar, array element, stack frame, or compiler record. Allocation and release
update the arena page-owner table; descriptor generation, arena generation, and
owner-token validation prevent stale or double-free access. Runtime helpers
accept `SD` descriptors or typed request records only and expose no raw
payload-pointer compatibility path.

Standalone `COMPILE` output has a separate source-free direct environment and
must satisfy its normal-RAM budget without changing this installed-runtime ABI;
it does not create a second installed string representation.

## Generated Summary

Every build renders the active normal-RAM, zero-page, segment, standalone,
graphics, geoRAM, arena, reserved, dynamic, and free ranges into
`build/MAP.md`. Its rows and totals are generated from validated linker, ZP,
arena, capacity, and size artifacts as specified by
`GENERATED_REFERENCE.md`; this document remains the normative budget policy.
