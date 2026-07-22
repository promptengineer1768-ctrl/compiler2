# System Primitive Runtime

`src/runtime/system.asm` owns compiled access to the real C64 CPU address
space and IRQ-owned jiffy clock. Callers evaluate numeric expressions before
entering this ABI. Addresses use the unsigned 16-bit address contract; POKE
values and WAIT value/mask operands use `math_to_arg_byte`. Code lives in the
`HIBASIC` segment (`$E000+`, visible under normal `$01=$35` banking); BSS and
generated ZP protect tables remain in normal RAM.

## Memory access and protection

`system_peek` reads the byte at the X/Y address. `system_poke` writes A to the
X/Y address unless it falls in generated protected storage.

Protection is a **narrow control-plane** policy (`REQUIREMENTS.md` §3.1,
`DESIGN.md` §3.1). The runtime rejects writes only into integrity-critical
intervals published by the build:

- `$FFF9-$FFFF` — project high-memory guard and 6502 hardware vectors;
- `$CE00-$CEFF` — only while `reu_xip_active` is nonzero (REU primary XIP miss
  slot). When REU XIP is idle the page is ordinary writable RAM;
- pinned IRQ/NMI and resident control blocks from linker policy / placement
  manifests;
- geoRAM gate and selection-mirror state;
- resident arena-directory mirrors that must remain consistent;
- compiler-owned zero-page ranges from
  `build/zp_protected_ranges.inc`.

`reu_xip_active` is a BSS flag exported from `system.asm` (default 0). A future
REU XIP module owns setting and clearing it; this file does not implement XIP.

Ordinary program, variable, string, compiled-image, screen, I/O, and free
dynamic RAM — including hot slots `$C800-$CDFF` and the standalone code budget
range `$0801-$CFFF` when it holds user or compiled payload rather than a listed
control block — remain writable. User `POKE` corruption of those ranges is
allowed (stock-like); the system must fail cleanly rather than silently ignore
the write. Non-compiler zero-page addresses remain writable. Generated map
artifacts (`MAP.md`, protected-range includes) are the only source of concrete
intervals for generated ranges; assembly must not hard-code a blanket
`$0801-$CFFF` protect list.

## SYS, USR, and WAIT

`system_sys` calls the X/Y machine-code address through a patched local JSR and
records that address for invalidation/audit state. `system_usr` dispatches the
FAC argument through the stock-compatible JMP vector at `$0310` and leaves the
user routine's FAC result in place.

`system_wait` accepts a six-byte record: `SW`, address low/high, mask, and XOR
byte. It polls until `((PEEK(address) XOR xor) AND mask) <> 0`. Each unsuccessful
poll calls the bank-safe STOP bridge; STOP returns with carry set.

## TI and TI$

The clock source is the KERNAL 24-bit jiffy counter, not private runtime state.
`system_ti_load` reads the stock register order A=least, X=middle, Y=most
significant through the bank-safe RDTIM bridge, then uses
`math_u24_to_float` to publish the exact value in FAC1. `system_ti_store` is the
raw clock-setting boundary and passes that register order to SETTIM.
`system_ti_string_load` converts 60 Hz jiffies to six ASCII `HHMMSS` digits and
publishes them into the caller's canonical arena-backed SD through
`str_from_bytes`. `system_ti_string_store` exports a validated source SD through
`str_export_bytes`, requires exactly six digits, validates hours `00..23` and
minutes and seconds `00..59`, converts back to jiffies, and publishes the clock
only after all validation succeeds.

## FRE

`src/runtime/fre.asm` owns profile-aware free-byte reporting for the `FRE`
function. Callers evaluate and discard the stock numeric argument before
entry. Query code is placed in `HIBASIC` with BSS state in normal RAM so the
late `$0801-$CFFF` CODE budget stays available for resident control-plane
tables.

- `fre_init` defaults to expansion/development profile and a stock-like export
  free baseline (38912 bytes).
- `fre_set_profile` selects export (`0`) or expansion (`1`).
- `fre_set_export_bytes` publishes the 24-bit little-endian free count used in
  export mode.
- `fre_query` writes free bytes into FAC1 via `math_u24_to_float`. Expansion
  mode reports `page_alloc_count * 256` (allocator-visible free pages as
  bytes). Export mode reports the published normal-RAM dynamic free remaining
  after the image. FRE never reports raw expansion-device capacity.

