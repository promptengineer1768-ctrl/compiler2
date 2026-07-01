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
3. VICE C64 or Plus/4 observation, once the project has a VICE harness.

VICE validation is deferred for this document because Compiler 2 does not yet
have the required harness. Every deferred case must have a test placeholder and
must be resolved before the related behavior is marked implemented.

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
| Tokenized line payload | A tokenized BASIC line is byte-counted and must fit the stock linked-line representation. Compiler 2 must reject or preserve-by-extension any line that cannot round-trip through stock BASIC V2 format. | Stock-only `SAVE` never emits malformed line records. Extended programs use the versioned extension envelope. | Stock format is enforced by the program encoder/decoder and canonical save tests. |
| Variable names | Variable names begin with `A` through `Z`. Later characters may be letters or digits. Longer names are accepted, but only the first two significant name characters participate in the stock variable identity. | `A`, `A1`, `AB`, and longer names are valid when they do not contain a keyword token. `AB`, `ABC`, and `AB9` alias according to the first two significant characters and type suffix. | `basic/variables/array_lookup.s:ptrget` stores only `varnam` and `varnam+1`; `isletc` accepts letters, and the scanner consumes following letters/digits without extending the stored name. |
| Variable type suffixes | No suffix means floating point. `%` means signed 16-bit integer. `$` means string. Type suffix participates in identity, so `AB`, `AB%`, and `AB$` are distinct variables. | Misplaced suffixes or illegal combinations produce stock syntax/type errors. | `basic/variables/array_lookup.s:ptrget` sets `intflg` for `%` and `valtyp` for `$`, with type bits folded into the stored two-byte name. |
| Reserved names | `TI`, `TI$`, and `ST` keep stock special-variable behavior. Names containing tokenized BASIC keywords must follow stock tokenizer behavior and may fail with `?SYNTAX ERROR`. | `TI` and `ST` cannot become ordinary user variables; `TI$` assignment sets the clock through the stock-compatible path. | `basic/variables/array_lookup.s` and `basic/variables/variable_resolution.s` special-case `TI`, `TI$`, and `ST`. |
| String length | String values are limited to `0` through `255` PETSCII bytes. | Concatenation, slicing, input, assignment, and conversion paths that would create a longer string must raise `?STRING TOO LONG` or the stock-equivalent error. | BASIC V2 string lengths are one byte in descriptors; `basic/strings/string_memory.s:midd` uses `lda #255` for the default `MID$` length. |
| Integer variables | `%` variables use signed 16-bit integer storage with range `-32768` through `32767`. | Out-of-range coercions must follow stock overflow or illegal-quantity behavior for the triggering context. | Numeric conversion routines in `basic/numeric/integer_conversion.s` and byte/address helpers in `basic/numeric/parse_and_address.s` are the implementation guides. |
| Byte arguments | Byte-valued arguments such as `CHR$`, `ASC` results, `SPC`, `TAB`, file numbers, device parameters, and secondary addresses are validated through stock byte conversion where applicable. | Values outside `0` through `255`, negative values, or non-integral values must follow stock `?ILLEGAL QUANTITY` behavior for the context. | `basic/numeric/parse_and_address.s:getbyt` converts numeric expressions to a byte and branches to the stock illegal-quantity path on overflow. |
| Address arguments | Address-valued arguments for `PEEK`, `POKE`, `SYS`, `WAIT`, and related paths must accept the C64 address range `0` through `65535`. | Negative values and values above the address range raise the stock illegal-quantity behavior. Compiler 2 protected storage checks apply after stock range validation. | `basic/numeric/parse_and_address.s:getadr` rejects negative and too-large values before forming the address. |
| Arrays | Undimensioned arrays default to stock dimensions. Explicit `DIM` and subscript checks must match BASIC V2, including bad-subscript and redimension behavior. | Redimensioning an existing array reports `?REDIM'D ARRAY`; invalid subscripts report `?BAD SUBSCRIPT`. | `basic/variables/array_dimensions.s` and `basic/variables/array_access.s` are the local source guides. |
| Logical files | At most 10 logical files may be open through the KERNAL logical file tables. Logical file number zero is not a normal openable file. | The 11th open reports `?TOO MANY FILES`; invalid logical-file use follows stock file errors. | `kernal/declare.s` reserves 10 entries for `lat`, `fat`, and `sat`; `kernal/open.s:nopen` checks `ldtnd` against 10 and rejects `la=0`. |
| LOAD and SAVE devices | Stock KERNAL `LOAD` and `SAVE` support cassette devices 1 and 2 and serial bus devices 4 through 31; device 0 and screen device 3 are invalid for these paths. Compiler 2 `COMPILE` is intentionally narrower and supports disk devices 8 through 11. | Device errors must use stock KERNAL/BASIC error numbers where the stock command is being emulated. `COMPILE` reports its documented Compiler 2 error for unsupported export devices. | `kernal/load.s` and `kernal/save.s` reject device 0 and 3 and branch to cassette or serial-device paths. |
| OPEN devices and secondary addresses | `OPEN` uses a logical file number, primary device number, and secondary address byte. Device 0 is keyboard, 3 is screen, 1 and 2 are cassette, and serial devices are 4 through 31. | Invalid files, duplicate logical files, missing names, and unavailable devices follow stock file errors. | `kernal/open.s` records `la`, `fa`, and `sa`; `basic/system/file_commands.s:paoc` parses the byte-sized parameters. |
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
| Tokenization | Extended tokens must never remap or reinterpret a stock BASIC V2 token byte. Extended programs use the versioned envelope described in `REQUIREMENTS.md`. |
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

VICE-derived assertions are deferred until the harness exists. Until then,
tests may encode source-derived expectations from `c64rom`, but must be marked
as needing VICE fixture confirmation before release acceptance.
