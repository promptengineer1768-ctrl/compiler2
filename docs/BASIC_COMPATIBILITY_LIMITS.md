# BASIC Compatibility Limits

This document defines implementation contracts for stock Commodore BASIC V2
compatibility and the BASIC 3.5 compatibility subset required by Compiler 2.
`REQUIREMENTS.md` remains the top-level authority; this file makes edge-limit
rules explicit enough to implement and test.

## Source Order

Use this source order when a limit is unclear:

1. Published Commodore references and widely mirrored user/programmer manuals.
2. The local rebuildable C64 ROM source at
   `C:\Users\me\Documents\Coding Projects\c64rom`.
3. Versioned VICE C64 or Plus/4 observations captured by the project harness.

The project has immutable stock fixture corpora for general BASIC V2 and BASIC
V3.5 semantics. The 48 edge cases reserved specifically by
`tests/e2e/cases/basicv2_limits.yaml` remain source-derived and carry
`vice_pending: true`; that flag must be cleared only when each named case gains
its authoritative VICE fixture. This pending state does not weaken the limit
manifest's coverage contract and does not claim that the related production
behavior is implemented.

Useful public references consulted for this contract include the Commodore 64
User's Guide variable-name description, C64-Wiki BASIC and command references,
and Power64's BASIC V2 appendix. They agree on the major user-visible limits:
line numbers `0` through `63999`, two significant variable-name characters,
and maximum 255-character strings.

Reference URLs:

- `https://www.c64-wiki.com/wiki/BASIC`
- `https://www.commodore.ca/manuals/c64_users_guide/c64-users_guide-03-beginning_basic_programming.pdf`
- `https://www.commodore.ca/wp-content/uploads/2018/11/Commodore_Basic_4_Users_Reference-Manual-1.pdf`

## BASIC V2 Contracts

| Area | Contract | Required error or behavior | Local validation |
|---|---|---|---|
| Program line numbers | Stored program line numbers and line-target syntax accept whole-number line numbers from `0` through `63999`. Values above the accepted stock range must raise `?SYNTAX ERROR` or the stock-equivalent error observed for the context. | `0` is valid. `63999` is the highest portable source line number. `64000` and larger are not accepted as source line numbers. | `basic/control/flow_control.s:linget` accumulates decimal line text in `linnum` and rejects once the high byte reaches the stock threshold before another digit is accepted. |
| Tokenized line record | A saved stock line is a linked record: next-line pointer, little-endian line number, tokenized bytes, zero terminator. A zero next-line pointer terminates the program. | `LOAD`, `SAVE`, `LIST`, and tests must observe canonical stock records for stock-only programs. | `basic/parsing/tokenize.s:fndlin` walks linked line records; `REQUIREMENTS.md` section 5 defines the external format. |
| Screen-editor input line | C64 screen entry supports an 80-column logical line through two 40-column physical screen lines. Compiler 2 may store longer generated/tokenized lines only when they are not entered through the stock-compatible editor path. | User line entry must match the editor-visible limit unless a documented Compiler 2 editor extension is enabled. | `kernal/declare.s` defines `llen=40` and `llen2=80`; `kernal/declare.s` also defines the BASIC/monitor input buffer as 89 bytes. |
| Tokenized line payload | A tokenized BASIC line is byte-counted and must fit the stock linked-line representation. Compiler 2 must reject or preserve-by-extension any line that cannot round-trip through stock BASIC V2 format. | Stock-only `SAVE` never emits malformed line records. Extended programs use the versioned C2P1 envelope (`DESIGN.md` §5.2). | Stock format is enforced by the program encoder/decoder and canonical save tests. |
| Variable names | Variable names begin with `A` through `Z`. Later characters may be letters or digits. Longer names are accepted, but only the first two significant name characters participate in the stock variable identity. | `A`, `A1`, `AB`, and longer names are valid when they do not contain a keyword token. `AB`, `ABC`, and `AB9` alias according to the first two significant characters and type suffix. | `basic/variables/array_lookup.s:ptrget` stores only `varnam` and `varnam+1`; `isletc` accepts letters, and the scanner consumes following letters/digits without extending the stored name. |
| Variable type suffixes | No suffix means floating point. `%` means signed 16-bit integer. `$` means string. Type suffix participates in identity, so `AB`, `AB%`, and `AB$` are distinct variables. | Misplaced suffixes or illegal combinations produce stock syntax/type errors. | `basic/variables/array_lookup.s:ptrget` sets `intflg` for `%` and `valtyp` for `$`, with type bits folded into the stored two-byte name. |
| Reserved names | `TI`, `TI$`, and `ST` keep stock special-variable behavior. Names containing tokenized BASIC keywords must follow stock tokenizer behavior and may fail with `?SYNTAX ERROR`. | `TI` and `ST` cannot become ordinary user variables; `TI$` assignment sets the clock through the stock-compatible path. | `basic/variables/array_lookup.s` and `basic/variables/variable_resolution.s` special-case `TI`, `TI$`, and `ST`. |
| String length | String values are limited to `0` through `255` PETSCII bytes. | Concatenation, slicing, input, assignment, and conversion paths that would create a longer string must raise `?STRING TOO LONG` or the stock-equivalent error. | BASIC V2 string lengths are one byte in descriptors; `basic/strings/string_memory.s:midd` uses `lda #255` for the default `MID$` length. |
| Integer variables | `%` variables use signed 16-bit integer storage with range `-32768` through `32767`. | Out-of-range coercions must follow stock overflow or illegal-quantity behavior for the triggering context. | Numeric conversion routines in `basic/numeric/integer_conversion.s` and byte/address helpers in `basic/numeric/parse_and_address.s` are the implementation guides. |
| Byte arguments | Byte-valued arguments such as `CHR$`, `SPC`, `TAB`, the value operand of `POKE`, the value and optional mask operands of `WAIT`, logical-file numbers, device parameters, and secondary addresses are evaluated as numeric expressions and then narrowed through the public `math_to_arg_byte` helper to the dedicated unsigned argument-byte domain. Argument byte is not signed `INT1`, and subsystems must not implement private narrowing. | Exact FLOAT/INT1/INT2/INT3 values `0` through `255` are accepted. Negative, fractional, larger, or unknown-type values must raise stock `?ILLEGAL QUANTITY` before truncation, memory access, or a KERNAL call. | `basic/numeric/parse_and_address.s:getbyt` calls `frmnum`, then `posint`; `conint` requires the high result byte to be zero. Compiler 2 implements that shared boundary in `src/runtime/math_core.asm:math_to_arg_byte`. |
| Address arguments | Address-valued arguments for `PEEK`, `POKE`, `SYS`, `WAIT`, and related paths must accept the C64 address range `0` through `65535`. | Negative values and values above the address range raise the stock illegal-quantity behavior. Compiler 2 protected storage checks apply after stock range validation. | `basic/numeric/parse_and_address.s:getadr` rejects negative and too-large values before forming the address. |
| Arrays | Undimensioned arrays default to stock dimensions. Explicit `DIM` and subscript checks must match BASIC V2, including bad-subscript and redimension behavior. | Redimensioning an existing array reports `?REDIM'D ARRAY`; invalid subscripts report `?BAD SUBSCRIPT`. | `basic/variables/array_dimensions.s` and `basic/variables/array_access.s` are the local source guides. |
| Logical files | The expression range is `0..255`. `OPEN` rejects logical file 0, rejects a duplicate, and permits at most 10 simultaneously open entries. `CLOSE` accepts any byte and an unopened number is a no-op. Channel commands accept any byte syntactically but require a matching open table entry. | Out-of-byte expressions report `?ILLEGAL QUANTITY`; zero/duplicate/overflowing table use follows `?NOT INPUT FILE`, `?FILE OPEN`, or `?TOO MANY FILES` as selected by the stock path. | `basic/system/file_commands.s:paoc` and `basic/io/timer_and_channel_io.s:cmd` use `getbyt`; `kernal/open.s:nopen` rejects zero/duplicates and checks `ldtnd` against 10; `kernal/close.s:nclose` ignores missing entries. |
| LOAD and SAVE devices | The expression range is `0..255`. Documented functional devices are cassette 1 and serial bus 4–31. Devices 0, 2 (RS-232), and 3 (screen) take the illegal-device path. Values 32–255 pass BASIC byte conversion but are outside the documented serial-device range; preserve observed KERNAL/VICE behavior rather than converting them to `?ILLEGAL QUANTITY`. Compiler 2 `COMPILE` is intentionally narrower and supports disk devices 8–11. | Expression range errors occur before KERNAL dispatch. Device errors use stock KERNAL/BASIC error numbers. | `basic/system/file_commands.s:plsv` uses `getbyt`; `kernal/load.s:nload` and `kernal/save.s:nsave` reject 0, 2, and 3, route 1 to cassette, and route values at least 4 to serial code whose documented device space is 4–31. |
| OPEN devices and secondary addresses | The expression range is `0..255`. Device 0 is keyboard, 1 cassette, 2 RS-232, 3 screen, and documented serial devices are 4–31. Higher byte values reach the stock serial-command path and must follow VICE behavior. Secondary addresses use the explicit `0..255` range: LOAD/SAVE/VERIFY default to 0, OPEN defaults to 0 for devices below 3 and `$FF` for devices 3 or above, and for LOAD zero selects the caller's alternate address while any nonzero value selects the file header address. | Invalid/duplicate logical files, unavailable devices, out-of-byte secondary addresses, and device-specific failures use stock file errors rather than argument truncation. Negative, fractional, or values above 255 report `?ILLEGAL QUANTITY`; otherwise preserve all eight bits and command-specific default behavior. | `basic/system/file_commands.s:paoc` and `basic/system/file_commands.s:plsv` use `getbyt`; `kernal/open.s:nopen` branches explicitly for 0, 1, 2, 3, and values at least 4; `kernal/load.s:nload` tests secondary address for zero/nonzero. |
| Filename length | KERNAL filenames are byte strings whose length is stored in one byte. Compiler 2 must preserve stock parsing and KERNAL `SETNAM` behavior. | Missing or too-long filenames follow stock command-specific behavior. | `kernal/declare.s` defines `fnlen` as one byte; BASIC file command parsing calls KERNAL `SETNAM`. |
| DATA and INPUT fields | `INPUT#` and DATA parsing must preserve stock delimiters, quote handling, type checks, and line/field length behavior. | Type mismatch, extra ignored input, file data, and out-of-data errors must match stock fixtures. | `basic/io/data_input.s` and `basic/io/console_input_output.s` are the local source guides. |

## BASIC 3.5 Contracts

Compiler 2's BASIC 3.5 support is an opt-in C64-hosted subset, not a Plus/4
binary compatibility promise. The Plus/4 BASIC 3.5 ROM and VICE Plus/4 behavior
are semantic references for the implemented keyword subset.

| Area | Contract |
|---|---|
| Mode gating | BASIC 3.5 structured tokens are accepted only after `BASIC3.5`. In `BASIC2` mode they must fail like unrecognized stock BASIC V2 input. |
| Inherited V2 behavior | BASIC 3.5 mode inherits every BASIC V2 limit above unless a BASIC 3.5 feature explicitly changes the behavior and the change is documented in `docs/KEYWORDS.md`. |
| Structured loops | `DO`, `LOOP`, `WHILE`, `UNTIL`, `EXIT DO`, and `EXIT FOR` share the loop descriptor model with BASIC V2 `FOR`/`NEXT`. Edge cases must cover nesting, early exit, skipped bodies, and invalid exits. |
| Graphics and sound-adjacent commands | BASIC 3.5/7-style graphics commands are adapted to C64 VIC-II hardware. They must document C64-specific coordinate, color, memory, and mode limits in the owning graphics docs before implementation. |
| Tokenization | Extended tokens must never remap or reinterpret a stock BASIC V2 token byte. Extended programs use the C2P1 envelope described in `REQUIREMENTS.md` / `DESIGN.md` §5.2. |
| Oracle status | Plus/4 VICE fixtures are required before a BASIC 3.5 behavior is marked complete. Until the VICE harness exists, tasks and tests may be placeholders, but implementation cannot be accepted as final. |

## Required Test Coverage

Every row in the BASIC V2 contract table must have at least one named E2E case
in `tests/e2e/` and, where practical, a lower-level unit or integration test.
The E2E case ID must include profile, mode, keyword or feature group, and the
limit name. Examples:

```text
basicv2-program-line_number-63999
basicv2-program-line_number-64000-syntax_error
basicv2-program-variable_name-first_two_alias
basicv2-immediate-string_length-255
basicv2-immediate-string_length-256-string_too_long
basicv2-immediate-open-too_many_files
basicv2-immediate-load-device_0-illegal_device
```

Source-derived limit assertions may remain pending while their named VICE
observations are absent, but must retain `vice_pending: true` and cannot be used
as release-acceptance evidence for the related production behavior.
