# Graphics Memory Design

## Decision

Compiler 2 preserves the bitmap layout proven by the legacy compiler:

| Purpose | Address range | Bytes |
|---|---:|---:|
| Bitmap screen matrix | `$DC00-$DFE7` | 1000 |
| Bitmap pixels | `$E000-$FF3F` | 8000 |
| VIC-II color RAM | `$D800-$DBE7` | 1000 nybbles |
| Guard byte plus NMI, RESET, IRQ/BRK vectors | `$FFF9-$FFFF` | 7 reserved |

The bitmap range is exactly 320 by 200 one-bit pixels. Its final byte is
`$E000 + 8000 - 1 = $FF3F`, safely below the reserved high-memory tail.

## VIC-II Selection

Graphics mode selects VIC bank 3, `$C000-$FFFF`, by setting the low CIA 2
port-A bank bits to `%00`. Within that bank, `$D018 = $78` selects:

- screen matrix offset `$1C00`, giving `$DC00`;
- bitmap offset `$2000`, giving `$E000`.

The 1000 screen bytes contain foreground/background color nybbles for hires
bitmap cells. They are ordinary RAM beneath the CPU I/O window. They are not
the C64's physical color RAM.

Physical color RAM remains at `$D800-$DBE7` while I/O is visible. It supplies
the additional color nybbles required by applicable display modes. Code and
tests must name these two resources distinctly as `bitmap_screen_matrix` and
`vic_color_ram`.

## CPU Banking Consequences

Normal Compiler 2 operation uses `$01 = $35`: KERNAL and BASIC are banked out,
I/O is visible, and RAM at `$E000-$FFFF` is directly writable. Under this map:

- bitmap writes at `$E000-$FF3F` are ordinary RAM writes;
- CPU accesses at `$DC00` reach CIA 1, not the bitmap screen matrix;
- CPU accesses at `$D800` reach physical color RAM.

Screen-matrix access therefore uses the sole RAM-under-I/O gate. The gate:

1. masks interrupts while I/O is hidden;
2. selects the all-RAM mapping;
3. transfers a fixed, validated chunk;
4. restores `$35`;
5. restores the caller's interrupt state.

A full 1000-byte clear or copy is split into bounded chunks with opportunities
for IRQ service between chunks. No ordinary graphics helper writes `$01`
directly. KERNAL bridges must not modify bitmap RAM while KERNAL ROM is visible
at `$E000-$FFFF`.

## Dynamic-Memory Boundary

Entering bitmap mode reserves `$DC00-$FF3F`, so the top of allocatable
normal-RAM dynamic storage becomes `$DBFF`. Leaving graphics mode restores
stock text mode and stock colors, then restores the text-mode ceiling only
after graphics-owned data is invalidated and arena metadata is updated
transactionally. This restore is required on normal program end, BASIC error,
`STOP`, and STOP-key interruption.

The linker and allocator treat the screen matrix, bitmap, guard byte, and
hardware vectors as explicit non-overlapping reservations rather than inferring
them from graphics source labels.

## Required Tests

System contract tests verify:

- the exact screen, bitmap, and vector ranges;
- VIC bank 3 and `$D018 = $78`;
- linker/allocator exclusion of `$DC00-$FF3F` in graphics mode;
- no overlap with `$FFF9-$FFFF`;
- graphics exit restores stock text mode and stock colors after END, error,
  `STOP`, and STOP key;
- only the RAM-under-I/O gate accesses the underlying `$DC00-$DFE7` RAM;
- every public graphics entry returns with `$01 = $35`.

Local geoRAM/emulator tests verify address calculations, top-right and
bottom-right pixel bounds, screen/color fills, chunk bounds, and banking
restoration. Focused VICE tests verify that the VIC-II displays from the
selected matrix and bitmap, that physical color RAM remains distinct, and that
timer/keyboard IRQ service continues during large graphics operations.
