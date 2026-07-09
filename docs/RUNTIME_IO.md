# Runtime I/O Contracts

Runtime console and file I/O always traverses the resident KERNAL bridge. The
bridge owns CPU-port and interrupt-state restoration; callers never jump to a
ROM vector directly.

## Console values and INPUT

`io_print_value` receives the adaptive numeric type in A. FLOAT uses the
canonical packed formatter and string arena, INT1 is sign-extended, INT2 is
signed, and INT3 is formatted unsigned. Numeric output retains the stock
leading sign position and trailing space. A string value uses type 4 with an SD
pointer in the first two FAC bytes. Newline and space emit through CHROUT,
semicolon emits nothing, and comma advances to the next ten-column zone.

Both INPUT entries accept one ten-byte `IN` request:

```text
0  "IN"
2  destination VD pointer (u16)
4  prompt pointer (u16)
6  prompt length (u8; zero selects "? ")
7  logical input channel (u8; zero selects keyboard)
8  reserved (u16, zero)
```

Input is bounded to 63 bytes. Numeric INPUT materializes a temporary canonical
SD, parses it through `str_val`, coerces according to the destination VD, and
stores through `var_store_int` or `var_store_float`. String INPUT allocates an
SD and publishes it through `var_store_string`. Untyped pointers are rejected.

## File and channel requests

All pointers are little endian and all filenames must be nonempty. Logical
file, device, secondary-address, filename-length, and channel fields are
unsigned argument bytes. The public numeric-runtime helper `math_to_arg_byte`
produces them after validating an expression as an exact `0..255` value;
argument byte is a shared language operand domain rather than an I/O-specific
type, and it is not `INT1`.

The request-record fields store that already-validated byte directly. They do
not carry a normal numeric type tag and they must not be widened to INT2 merely
because the parser evaluated the source expression through an INT2-compatible
path. Any command with the same contract, including `WAIT`, `POKE`, `CHR$`,
`SPC`, and `TAB`, must use the same public helper instead of a private
file-I/O narrowing routine.

- `RL` (12 bytes): magic, name pointer, length, device, secondary address,
  mode (`0=LOAD`, `1=VERIFY`), load address, and zero reserved word.
- `RS` (11 bytes): magic, name pointer, length, device, secondary address,
  inclusive start and exclusive end. Empty or descending ranges are rejected.
- `RO` (8 bytes): magic, logical file, device, secondary address, filename
  length, and filename pointer.
- `RC` / `RI` (3 bytes): magic and logical-file argument byte for CLOSE or
  channel input.
- `RW` (4 bytes): magic, logical-file argument byte, and output byte.

LOAD/VERIFY call SETNAM, SETLFS, then LOAD with the proper mode. SAVE supplies
the start pointer and exclusive end required by the KERNAL SAVE ABI. OPEN calls
SETNAM, SETLFS, and OPEN. Character input/output selects the requested logical
file, performs CHRIN/CHROUT, and restores default channels with CLRCHN even on
the output error path.
