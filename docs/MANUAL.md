# BASIC V3 User Manual

> Status: this manual is a user-facing language reference carried forward from
> the legacy project. `../REQUIREMENTS.md` is the compatibility authority,
> `../DESIGN2.md` and `COMPILER_ARCHITECTURE.md` are the architecture
> authorities, and entries here do not prove
> implementation status unless the requirements matrix and tests also mark them
> implemented.

Legacy source build: `14-dirty`
Legacy source date: 2026-05-07 UTC

## Table of Contents

1. [Introduction](#introduction)
2. [Runtime Optimizations](#runtime-optimizations)
3. [Direct-Mode BASIC 2 Keyword Surface](#direct-mode-basic-2-keyword-surface)
4. [DOS Wedge Extensions](#dos-wedge-extensions)
   - [`$` Directory](#-directory)
   - [`/` Load Alias](#-load-alias)
6. [BASIC 3 Extensions](#basic-3-extensions)
   - [`BASIC`](#basic)
   - [`BASIC()`](#basic-1)
   - [`COMPILE`](#compile)
   - [`FPMODE`](#fpmode)
7. [BASIC 3.5 / 7 Extensions](#basic-35--7-extensions)
   - [`ELSE`](#else)
   - [`DO`](#do)
   - [`LOOP`](#loop)
   - [`EXIT`](#exit)
   - [`UNTIL`](#until)
   - [`WHILE`](#while)
8. [IEEE 754 Numeric Extensions](#ieee-754-numeric-extensions)
   - [IEEE Mode Overview](#ieee-mode-overview)
   - [IEEE Constants and Printed Values](#ieee-constants-and-printed-values)
   - [`FPMODE`](#fpmode)
   - [`FPFLAGS`](#fpflags)
   - [`FPCLR`](#fpclr)
   - [`FPSET`](#fpset)
   - [`FPTEST`](#fptest)
   - [`FPTTEST`](#fpttest)
   - [`ISNAN`](#isnan)
   - [`ISSNAN`](#issnan)
   - [`ISINF`](#isinf)
   - [`ISFIN`](#isfin)
   - [`ISNORM`](#isnorm)
   - [`ISZERO`](#iszero)
   - [`SGNBIT`](#sgnbit)
   - [`ISUNORD`](#isunord)
   - [`COPYSGN`](#copysgn)
   - [`TOTALORDER`](#totalorder)
   - [`BIN32$`](#bin32)
   - [`VAL32`](#val32)
   - [`FMA`](#fma)
   - [`REMAIN`](#remain)
   - [`MIN`](#min)
   - [`MAX`](#max)
   - [`SCALB`](#scalb)
   - [`LOGB`](#logb)
   - [`MANT`](#mant)
   - [`RINT`](#rint)
   - [`NEXTUP`](#nextup)
   - [`NEXTDOWN`](#nextdown)
8. [Appendix A: Measured Numeric Accuracy](#appendix-a-measured-numeric-accuracy)
9. [Appendix B: New BASIC Tokens](#appendix-b-new-basic-tokens)
10. [Appendix C: IEEE 754 Notes](#appendix-c-ieee-754-notes)
11. [Appendix D: Adaptive Numeric Types](#appendix-d-adaptive-numeric-types)
12. [Appendix E: Zero-Page Usage Design](#appendix-e-zero-page-usage-design)
13. [Appendix F: Numeric Benchmarks](#appendix-f-numeric-benchmarks)

## Introduction

BASIC V3 starts as a Commodore BASIC 2.0 compatible system. New language features are opt-in so existing BASIC 2.0 programs keep their expected syntax, tokenization, math errors, and disk behavior.

Feature summary:

- DOS wedge commands add direct-mode `$`, `/`, and `@` prefix recognition. The resident handler accepts the prefixes at startup; full KERNAL-backed directory/load/command behavior is staged behind the disk bridge.
- BASIC 3 extensions provide the resident gateway commands `BASIC2`, `BASIC3.5`, `BASIC()`, `COMPILE`, `FPMODE0`, `FPMODE1`, and `FPMODE()`.
- BASIC 3.5 / 7 extensions add opt-in structured keywords: `ELSE`, `DO`, `LOOP`, `EXIT`, `UNTIL`, and `WHILE`.
- IEEE 754 numeric mode adds special values, rounding control, sticky exception flags, classification functions, and binary32 conversion support.
- Adaptive numeric types let common integer values use `INT1`, `INT2`, and unsigned `INT3` fast paths before promoting to the existing 5-byte float format when needed.
- Zero-page usage is lifetime-managed: each routine's scratch/state is classified, and graph coloring is used to share locations only when live ranges do not conflict.

The BASIC 3.5 / 7 subset is enabled with `BASIC3.5` and disabled with `BASIC2`. BASIC starts in 2.0 mode. The gateway statements `BASIC3.5` and `BASIC2`, and the no-argument query function `BASIC()`, are active immediately at startup. In BASIC 2.0 mode, all other BASIC 3.5 structured keywords (`ELSE`, `DO`, `LOOP`, `EXIT`, `UNTIL`, and `WHILE`) produce `?SYNTAX ERROR`.

IEEE numeric mode is enabled with `FPMODE1` and disabled with `FPMODE0`. In normal startup mode, legacy Commodore-style numeric behavior remains active. The gateway statements `FPMODE1` and `FPMODE0`, and the no-argument query function `FPMODE()`, are active immediately at startup and can be used independently of the BASIC 3.5 dialect mode.

## Runtime Optimizations

BASIC V3 keeps stored BASIC programs in the normal tokenized form, then compiles executable BASIC through the compiler path before execution. Stored programs are compiled for `RUN`; most immediate statements are tokenized as a temporary line and compiled through the same runtime path. A few commands remain direct-mode-only because they control the editor, compiler, disk wedge, or session state.

The main techniques are:

- Numeric constant lowering: decimal literals are parsed during compilation, so compiled loops do not repeatedly call the float input routine for the same literal.
- Variable allocation and binding: variables referenced by compiled code carry typed payloads that can be loaded through the runtime variable helpers.
- Branch resolution: compiled control flow naturally uses resolved code paths instead of reinterpreting source tokens for every branch.
- FOR/NEXT execution: compiled loop control keeps loop state in runtime frames and returns through compiled code paths.
- Loop fast paths: safe literal `FOR`/`NEXT` integer loops can use descriptor-gated direct runtime-cell helpers, and safe bare `DO`/`LOOP` pairs can compile to a direct native backedge. Conditional `DO WHILE`, `DO UNTIL`, `LOOP WHILE`, and `LOOP UNTIL` currently retain the generic condition path unless a later build proves and enables their descriptor-gated native condition branch.
- Program preservation: the original tokenized program is not rewritten. `LIST`, `SAVE`, editing, and compatibility behavior continue to see ordinary BASIC text.

Adaptive numeric types give compiled code compact integer fast paths. When the compiler or runtime sees a safe integer value, it can keep it as `INT1`, `INT2`, or `INT3` instead of a float. At runtime, integer-only arithmetic is tried first for operations that have a safe fast path:

- Addition, subtraction, multiplication, and comparison have integer fast paths for `INT1`, `INT2`, and selected `INT3` operands. If the integer result would overflow or leave the safe integer domain, the runtime promotes the operation to the normal float path.
- Division has a narrower fast path. It is used only when the dividend is between `-32768` and `+32768`, the divisor is between `-128` and `+127`, and the division has no remainder. In plain terms, `96/2` can stay integer-fast, but `5/2` falls back to float so it can still produce `2.5`.
- `SQR` has a small `INT1` shortcut for perfect squares. Values that are not exact small integer squares use the normal float square-root routine.
- `^` has a tiny shortcut for `2^x` when `x` is an integer from `0` through `7`. Other exponentiation cases use the general power path.

The compiled cache is invalidated when the program changes, such as after editing a line, loading a new program, or `NEW`. A later `CONT` can continue only when the source generation and runtime state are still compatible.

## Direct-Mode BASIC 2 Keyword Surface

At the `READY.` prompt, BASIC V3 accepts numbered program lines and immediate
commands. Numbered lines are tokenized into stored program records. Non-numbered
commands enter the direct runtime.

Resident direct commands are kept deliberately small: `NEW`, `RUN`, `CONT`,
`COMPILE`, `CLR`, bare `LIST`, BASIC/FPMODE gateway commands, and the disk
wedge prefixes are handled directly. `LOWMEM` is not part of Compiler 2.
Executable BASIC statements such as
assignment, `PRINT`, `IF`, `FOR`/`NEXT`, `POKE`, `VERIFY`, and `DEF FN` are
tokenized as a temporary line and run through the same compiler path used by
stored programs.

Examples:

```basic
?1
PRINT 2+3
LET A=7
A=A+1
PRINT A
A$="HI"
?A$
B=4:PRINT B
IF 1 THEN PRINT 9
FOR I=1 TO 2:PRINT I:NEXT I
POKE 1024,1:PRINT PEEK(1024)
DEF FN A(X)=X+1
PRINT FN A(2)
TI$="000001"
PRINT TI$
```

`LIST` currently accepts the bare form and lists all stored program lines.
Line-range forms are not part of the resident direct handler yet. BASIC-visible
file/device statements such as `LOAD`, `SAVE`, and `VERIFY` are part of the
temporary compiled direct-command path rather than the tiny resident shortcut
set.

## DOS Wedge Extensions

The DOS wedge commands are direct-mode conveniences. They are typed at the `READY.` prompt, are not program statements, and are active by default in startup BASIC 2 mode.

The wedge writes to the current text screen. There is no special restoration of
cursor, color, or screen contents beyond normal BASIC output behavior.

### `$` Directory

Syntax:

```basic
$
```

Displays the current disk directory without loading the directory over the
stored BASIC program. `@$` is accepted as the equivalent directory form.

Examples:

```basic
$
```

Notes:

- Direct mode only.
- Program use reports the direct-mode-only error.
- This command follows the common Action Replay / DOS wedge style where `$` or `@$` displays a directory.

### `/` Load Alias

Syntax:

```basic
/filename
/"filename"
```

Loads a program from the current disk device with absolute PRG load
semantics, equivalent to `LOAD "filename",device,1`.

Examples:

```basic
/HELLO
/"HELLO"
```

Notes:

- Direct mode only.
- Unquoted names end at comma or end-of-line.
- Quoted names follow normal BASIC string filename rules.

### `@` Status / Command

Syntax:

```basic
@
@command
```

Accepts the command-channel prefix. A bare `@` returns:

```text
00, OK, 00, 00
```

`@8`, `@9`, `@10`, and `@11` select the current disk device. `@command` sends a
disk command to the current disk device and reports status. Destructive
commands require confirmation.

### `!` SEQ File Stream

Syntax:

```basic
!filename
!"filename"
```

Accepts the disk-SEQ-stream prefix and reads the given `filename` as a sequential file, streaming its PETSCII contents to the main screen output. This is a direct-mode convenience for debugging or quick text inspection of data files.

Behavior:

- Opens the SEQ file and reads it byte-by-byte, passing each byte through the shared screen-output routine (same as LIST and PRINT).
- The output stream is subject to CTRL slow-scroll throttling and STOP abortion like other screen output.
- STOP during `!` streaming aborts output immediately and closes the file.
- There is no screen-state restoration. PETSCII clear-screen, color-change,
  cursor movement, scrolling, and other output effects remain visible after EOF
  or STOP.
- The `!` command follows the common Action Replay / DOS wedge style where `!` or `!`filename reads sequential data to screen.

Examples:

```basic
!myfile.txt
!"debug_data.seq"
```

Notes:

- Direct mode only.
- Program use reports the direct-mode-only error.
- File is opened using the KERNAL sequential file routines with default device and logical file number.
- Output is subject to the same screen throttle and STOP polling as LIST and PRINT statements.
- File errors during opening or reading report `?FILE NOT FOUND` or `?ILLEGAL DEVICE NUMBER` as appropriate.

## BASIC 3 Extensions

BASIC 3 extensions are the always-resident gateway commands that keep BASIC V3
usable from the startup `READY.` prompt. They are available in BASIC 2 mode and
do not require BASIC 3.5 / 7 structured-token mode.

### BASIC

Syntax:

```basic
BASIC2
BASIC3.5
```

Changes the active BASIC dialect.

`BASIC2` restores BASIC 2.0 compatibility. `BASIC3.5` enables the structured
keywords in the BASIC 3.5 / 7 section. These gateway statements are direct-mode
commands and are accepted in both BASIC 2 and BASIC 3.5 modes.

### BASIC()

Syntax:

```basic
BASIC()
```

Returns the active BASIC dialect as `2` or `3.5`. This resident query accepts no
expression argument.

Examples:

```basic
?BASIC()
BASIC3.5
PRINT BASIC()
BASIC2
PRINT BASIC()
```

Expected output:

```text
 2
 3.5
 2
```

### COMPILE

Syntax:

```basic
COMPILE ["filename" [,device]]
```

Compiles the current stored BASIC program to native 6502 code.

If omitted, the filename defaults to `COMPILED` and the device defaults to the
current disk device. The current disk device follows stock KERNAL `fa` at `$BA`
and is changed by file commands or DOS wedge selection such as `@10`.

The resulting PRG is independent and stock-loadable. It contains the compiled
program, required runtime, and a source-free standalone direct-mode environment,
but no tokenized source. The environment supports simple `?` or `PRINT`
inspection of one scalar, string, or array-element term, and `CONT` when its
continuation state is valid. It also supports `RUN`, `LOAD`, `SAVE`, `VERIFY`,
`CLR`, and the DOS wedge commands described in this manual. Assignment,
compound expressions, program editing, and arbitrary BASIC statements outside
this command set are rejected. `LIST` may show only:

```basic
2026 SYS2061
```

It does not list tokenized source or decompile the native program image.

### FPMODE

Syntax:

```basic
FPMODE0
FPMODE1
FPMODE()
```

`FPMODE1` enables IEEE numeric semantics. `FPMODE0` restores legacy numeric
semantics. `FPMODE()` returns the current mode, `1` for enabled or `0` for
disabled. The query form accepts no expression argument.

## BASIC 3.5 / 7 Extensions

These commands add a partial structured BASIC 3.5 / BASIC 7 programming model.
They require active BASIC 3.5 mode.

Examples:

```basic
BASIC3.5
10 DO
20 PRINT "HELLO"
30 EXIT
40 LOOP
RUN

BASIC2
10 DO
RUN
```

The second `RUN` reports `?SYNTAX ERROR` because `DO` is no longer available.

Notes:

- BASIC starts in 2.0 mode.
- Structured tokens are available only after `BASIC3.5`.
- In BASIC 2.0 mode, structured tokens report `?SYNTAX ERROR`.

### ELSE

Syntax:

```basic
IF condition THEN true-statements ELSE false-statements
IF condition GOTO line ELSE false-statements
```

Adds an alternate branch to `IF`. If the condition is true, BASIC executes the `THEN` branch and skips the `ELSE` branch. If the condition is false, BASIC skips to `ELSE` and executes the false branch.

Examples:

```basic
BASIC3.5
10 INPUT "NUMBER";N
20 IF N<0 THEN PRINT "NEGATIVE" ELSE PRINT "ZERO OR POSITIVE"
RUN
```

```basic
BASIC3.5
10 A=5
20 IF A=5 THEN PRINT "MATCH":PRINT "DONE" ELSE PRINT "NO MATCH"
RUN
```

Notes:

- Outside a valid `IF` context, `ELSE` ignores the rest of the line, similar to `REM`.
- In BASIC 2.0 mode, `ELSE` reports `?SYNTAX ERROR`.

### DO

Syntax:

```basic
DO
DO WHILE condition
DO UNTIL condition
```

Starts a structured loop. A bare `DO` repeats until `EXIT`, `END`, `STOP`, an error, or a matching conditional `LOOP` ends it.

Examples:

```basic
BASIC3.5
10 I=1
20 DO
30 PRINT I
40 I=I+1
50 LOOP UNTIL I=4
RUN
```

Expected output:

```text
 1
 2
 3
```

Pre-test example:

```basic
BASIC3.5
10 I=1
20 DO WHILE I<4
30 PRINT I
40 I=I+1
50 LOOP
RUN
```

### LOOP

Syntax:

```basic
LOOP
LOOP WHILE condition
LOOP UNTIL condition
```

Ends a `DO` loop. If no condition is supplied, control returns to the matching `DO`. `LOOP WHILE` repeats while the condition is true. `LOOP UNTIL` repeats until the condition becomes true.

Examples:

```basic
BASIC3.5
10 I=0
20 DO
30 I=I+1
40 PRINT I
50 LOOP WHILE I<3
RUN
```

```basic
BASIC3.5
10 I=0
20 DO
30 I=I+1
40 PRINT I
50 LOOP UNTIL I=3
RUN
```

Both examples print `1`, `2`, and `3`.

### EXIT

Syntax:

```basic
EXIT
```

Leaves the innermost active `DO` loop immediately and resumes after the matching `LOOP`.

Examples:

```basic
BASIC3.5
10 I=0
20 DO
30 I=I+1
40 IF I=3 THEN EXIT
50 PRINT I
60 LOOP
70 PRINT "AFTER LOOP"
RUN
```

Expected output:

```text
 1
 2
AFTER LOOP
```

Nested example:

```basic
BASIC3.5
10 I=0
20 DO
30 J=0
40 DO
50 J=J+1
60 IF J=2 THEN EXIT
70 LOOP
80 I=I+1
90 IF I=3 THEN EXIT
100 LOOP
```

`EXIT` always applies to the innermost active `DO`.

### UNTIL

Syntax:

```basic
DO UNTIL condition
LOOP UNTIL condition
```

`UNTIL` repeats a loop until its condition becomes true.

With `DO UNTIL`, the condition is checked before the loop body runs. If the condition is already true, the loop body is skipped.

With `LOOP UNTIL`, the body runs once before the condition is checked.

Examples:

```basic
BASIC3.5
10 I=5
20 DO UNTIL I=5
30 PRINT "WILL NOT PRINT"
40 LOOP
RUN
```

```basic
BASIC3.5
10 I=5
20 DO
30 PRINT "PRINTS ONCE"
40 LOOP UNTIL I=5
RUN
```

### WHILE

Syntax:

```basic
DO WHILE condition
LOOP WHILE condition
```

`WHILE` repeats a loop while its condition remains true.

With `DO WHILE`, the condition is checked before the loop body runs. With `LOOP WHILE`, the body runs once before the condition is checked.

Examples:

```basic
BASIC3.5
10 I=1
20 DO WHILE I<=3
30 PRINT I
40 I=I+1
50 LOOP
RUN
```

```basic
BASIC3.5
10 I=1
20 DO
30 PRINT I
40 I=I+1
50 LOOP WHILE I<=3
RUN
```

## IEEE 754 Numeric Extensions

### IEEE Mode Overview

BASIC V3's IEEE mode adds IEEE 754-style special values, sticky exception flags, selectable rounding modes, classification functions, and helper operations.

Enable IEEE mode:

```basic
FPMODE1
```

Return to legacy mode:

```basic
FPMODE0
```

Query the current IEEE mode:

```basic
PRINT FPMODE()
```

`FPMODE()` returns `1` when IEEE mode is enabled and `0` when it is disabled. The resident query accepts no expression argument.

Flag bits:

| Bit | Mask | Meaning |
| --- | --- | --- |
| 0 | 1 | invalid operation |
| 1 | 2 | divide by zero |
| 2 | 4 | overflow |
| 3 | 8 | underflow |
| 4 | 16 | inexact |

Rounding modes:

| Mode | Meaning |
| --- | --- |
| 0 | round ties to even |
| 1 | round toward zero |
| 2 | round toward positive infinity |
| 3 | round toward negative infinity |
| 4 | round ties away from zero |

Truth-valued IEEE predicates return BASIC true (`-1`) or false (`0`).

### IEEE Constants and Printed Values

IEEE mode recognizes and prints non-finite values:

```basic
 INF
-INF
 NAN
 SNAN
```

Examples:

```basic
FPMODE1
PRINT VAL("INF")
PRINT VAL("-INF")
PRINT VAL("NAN")
PRINT STR$(VAL("INF"))
```

Special arithmetic examples:

```basic
FPMODE1
PRINT 1/0
PRINT 0/0
PRINT SQR(-1)
PRINT LOG(0)
PRINT FPFLAGS()
```

Typical IEEE results:

- `1/0` returns `INF` and raises divide-by-zero.
- `0/0` returns `NAN` and raises invalid.
- `SQR(-1)` returns `NAN` and raises invalid.
- `LOG(0)` returns `-INF` and raises divide-by-zero.

### FPMODE

Syntax:

```basic
FPMODE0
FPMODE1
FPMODE()
```

`FPMODE1` enables IEEE semantics. `FPMODE0` restores legacy semantics. `FPMODE()` returns the current mode, `1` for enabled or `0` for disabled. The BASIC 3.5 dialect and IEEE mode are independent; `FPMODE1` can be used while BASIC remains in default BASIC 2 mode.

Examples:

```basic
FPMODE1
PRINT 1/0
FPMODE0
```

```basic
FPMODE1
PRINT FPMODE()
FPMODE0
PRINT FPMODE()
```

Notes:

- The `FPMODE` gateway and query forms are active at startup.
- Other IEEE functions require IEEE mode to be enabled with `FPMODE1`.

### FPFLAGS

Syntax:

```basic
FPFLAGS()
```

Returns the current sticky IEEE exception flag mask.

Example:

```basic
FPMODE1
PRINT FPCLR()
PRINT 1/0
PRINT FPFLAGS()
```

Expected flag result includes bit 1, mask `2`, for divide-by-zero.

### FPCLR

Syntax:

```basic
FPCLR
FPCLR()
FPCLR(mask)
```

Clears IEEE sticky flags and returns the previous flag mask. With no argument, clears all flags. With `mask`, clears only the selected bits.

Examples:

```basic
FPMODE1
PRINT 0/0
PRINT FPFLAGS()
PRINT FPCLR()
PRINT FPFLAGS()
```

```basic
REM CLEAR ONLY INVALID AND DIVIDE-BY-ZERO
PRINT FPCLR(3)
```

### FPSET

Syntax:

```basic
FPSET mask
FPSET(mask)
```

Raises selected sticky flags and returns the new flag mask.

Example:

```basic
FPMODE1
PRINT FPCLR()
PRINT FPSET(5)
PRINT FPFLAGS()
```

Mask `5` sets invalid (`1`) and overflow (`4`).

### FPTEST

Syntax:

```basic
FPTEST mask
FPTEST(mask)
```

Returns `FPFLAGS() AND mask`.

Example:

```basic
FPMODE1
PRINT FPCLR()
PRINT 1/0
IF FPTEST(2) THEN PRINT "DIVIDE BY ZERO"
```

### FPTTEST

Syntax:

```basic
FPTTEST mask
FPTTEST(mask)
```

`FPTTEST` is a compatibility spelling accepted by the tokenizer. It maps to the
same token and runtime behavior as `FPTEST(mask)`.

### ISNAN

Syntax:

```basic
ISNAN(x)
```

Returns true if `x` is a quiet or signaling NaN.

Examples:

```basic
FPMODE1
PRINT ISNAN(VAL("NAN"))
PRINT ISNAN(123)
```

Expected output:

```text
-1
 0
```

### ISSNAN

Syntax:

```basic
ISSNAN(x)
```

Returns true if `x` is a signaling NaN.

Example:

```basic
FPMODE1
PRINT ISSNAN(VAL("SNAN"))
```

Signaling NaNs may be quieted by operations that consume them, raising the invalid flag.

### ISINF

Syntax:

```basic
ISINF(x)
```

Returns true if `x` is positive or negative infinity.

Examples:

```basic
FPMODE1
PRINT ISINF(1/0)
PRINT ISINF(100)
```

### ISFIN

Syntax:

```basic
ISFIN(x)
```

Returns true if `x` is finite and nonzero.

Examples:

```basic
FPMODE1
PRINT ISFIN(25)
PRINT ISFIN(0)
PRINT ISFIN(1/0)
```

### ISNORM

Syntax:

```basic
ISNORM(x)
```

Returns true if `x` is a finite normal number.

Example:

```basic
FPMODE1
PRINT ISNORM(25)
PRINT ISNORM(VAL("NAN"))
```

### ISZERO

Syntax:

```basic
ISZERO(x)
```

Returns true if `x` is positive zero or negative zero.

Example:

```basic
FPMODE1
PRINT ISZERO(0)
PRINT ISZERO(-0)
PRINT ISZERO(1)
```

### SGNBIT

Syntax:

```basic
SGNBIT(x)
```

Returns true if the sign bit of `x` is set. This detects negative zero as well as negative finite values and negative infinity.

Examples:

```basic
FPMODE1
PRINT SGNBIT(-7)
PRINT SGNBIT(-0)
PRINT SGNBIT(7)
```

### ISUNORD

Syntax:

```basic
ISUNORD(x,y)
```

Returns true if either operand is NaN. This is useful because IEEE comparisons involving NaN are unordered.

Example:

```basic
FPMODE1
PRINT ISUNORD(1,2)
PRINT ISUNORD(1,VAL("NAN"))
```

### COPYSGN

Syntax:

```basic
COPYSGN(x,y)
```

Returns `x` with the sign bit copied from `y`.

Examples:

```basic
FPMODE1
PRINT COPYSGN(5,-1)
PRINT COPYSGN(-5,1)
```

Expected output:

```text
-5
 5
```

### TOTALORDER

Syntax:

```basic
TOTALORDER(x,y)
```

Compares `x` and `y` using IEEE totalOrder rules. Returns:

| Result | Meaning |
| --- | --- |
| -1 | `x` orders before `y` |
| 0 | `x` and `y` order equal |
| 1 | `x` orders after `y` |

Example:

```basic
FPMODE1
PRINT TOTALORDER(1,2)
PRINT TOTALORDER(2,1)
PRINT TOTALORDER(2,2)
PRINT TOTALORDER(1,VAL("NAN"))
```

### BIN32$

Syntax:

```basic
BIN32$(x)
```

Returns a printable big-endian IEEE binary32 hex string for `x`, rounded in the current FP mode. The string starts with `$` and contains eight hex digits.

Examples:

```basic
FPMODE1
A$=BIN32$(1)
PRINT A$          ' $3F800000
```

Notes:

- The result is printable hex text, not raw binary bytes.
- Conversions use the current rounding mode and may raise inexact, overflow, or underflow.

### VAL32

Syntax:

```basic
VAL32(b$)
```

Converts an eight-digit big-endian IEEE binary32 hex string into a BASIC V3 floating-point value. A leading `$` is optional, so both `"3F800000"` and `"$3F800000"` represent `1.0`.

Example:

```basic
FPMODE1
A$=BIN32$(1)
PRINT VAL32(A$)
PRINT VAL("3F800000")
```

The hex bytes `$3F,$80,$00,$00` represent binary32 `1.0`.

### FMA

Syntax:

```basic
FMA(x,y,z)
```

Returns the fused multiply-add result of `x*y+z`, rounded once at the end.

Example:

```basic
FPMODE1
PRINT FMA(2,3,4)
```

Expected output:

```text
 10
```

FMA is useful when intermediate rounding would otherwise change the result.

### REMAIN

Syntax:

```basic
REMAIN(x,y)
```

Returns the IEEE remainder of `x` divided by `y`.

Examples:

```basic
FPMODE1
PRINT REMAIN(7,3)
PRINT REMAIN(VAL("INF"),VAL("INF"))
PRINT FPFLAGS()
```

Invalid cases such as infinity remainder infinity return `NAN` and raise the invalid flag.

### MIN

Syntax:

```basic
MIN(x,y)
```

Returns the IEEE-aware minimum of `x` and `y`.

Examples:

```basic
FPMODE1
PRINT MIN(25,-7)
PRINT MIN(-0,0)
```

`MIN(-0,0)` preserves negative zero.

### MAX

Syntax:

```basic
MAX(x,y)
```

Returns the IEEE-aware maximum of `x` and `y`.

Examples:

```basic
FPMODE1
PRINT MAX(25,-7)
PRINT MAX(-0,0)
```

`MAX(-0,0)` returns positive zero.

### SCALB

Syntax:

```basic
SCALB(x,n)
```

Returns `x` scaled by `2^n` by adjusting the binary exponent.

Examples:

```basic
FPMODE1
PRINT SCALB(1.5,2)
PRINT SCALB(8,-1)
```

Expected output:

```text
 6
 4
```

### LOGB

Syntax:

```basic
LOGB(x)
```

Returns the unbiased binary exponent of `x`.

Examples:

```basic
FPMODE1
PRINT LOGB(25)
PRINT LOGB(1)
PRINT LOGB(0)
```

For `25`, the unbiased exponent is `4` because `25` is between `2^4` and `2^5`.

### MANT

Syntax:

```basic
MANT(x)
```

Returns the normalized positive significand of a finite nonzero number.

Example:

```basic
FPMODE1
PRINT MANT(25)
```

For `25`, this returns the significand with the exponent normalized to the implementation's mantissa range.

### RINT

Syntax:

```basic
RINT(x)
```

Rounds `x` to an integral value using the current rounding mode.

Examples:

```basic
FPMODE1
PRINT RINT(2.5)
PRINT RINT(-2.5)
```

Change the rounding mode with `FPMODE` before calling `RINT`.

### NEXTUP

Syntax:

```basic
NEXTUP(x)
```

Returns the next representable value greater than `x`.

Examples:

```basic
FPMODE1
PRINT NEXTUP(1)
PRINT NEXTUP(0)
```

For infinity and NaN inputs, the result follows IEEE special-value rules.

### NEXTDOWN

Syntax:

```basic
NEXTDOWN(x)
```

Returns the next representable value less than `x`.

Examples:

```basic
FPMODE1
PRINT NEXTDOWN(1)
PRINT NEXTDOWN(0)
```

For infinity and NaN inputs, the result follows IEEE special-value rules.

## Appendix A: Measured Numeric Accuracy

The current final runtime accuracy regression is `python tests\final_math_accuracy.py`. It samples each listed function at 301 points and checks the packed BASIC V3 result against a high-precision reference rounded to the target format. The acceptance limit is 2.0 ULP.

Measured on May 4, 2026:

| Function | Samples | Average ULP Error | Maximum ULP Error | Worst Input | Actual Packed | Expected Packed |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `EXP` | 301 | 0.299118 | 0.810190 | -20.4 | `$63 $3D $E3 $E0 $11` | `$63 $3D $E3 $E0 $10` |
| `SIN` | 301 | 0.341453 | 0.875437 | -2.3876104167282426 | `$80 $AF $3E $7A $A9` | `$80 $AF $3E $7A $A8` |
| `COS` | 301 | 0.338801 | 1.463104 | -1.8221237390820801 | `$7E $FE $A8 $8F $CD` | `$7E $FE $A8 $8F $CE` |
| `TAN` | 301 | 0.547050 | 1.800273 | -0.9885043403034345 | `$81 $C2 $65 $6B $49` | `$81 $C2 $65 $6B $47` |
| `ATN` | 301 | 0.294030 | 1.117374 | -0.5333333333333332 | `$7F $FA $DB $AF $C9` | `$7F $FA $DB $AF $CA` |

Arithmetic accuracy requirement:

| Operation | Required Accuracy |
| --- | --- |
| `+` / add | Correctly rounded to the BASIC V3 5-byte destination format under the active rounding mode. In round-to-nearest-even mode, the result must be within 0.5 ULP of the exact real result. |
| `-` / subtract | Same as add: correctly rounded to the destination format, within 0.5 ULP in round-to-nearest-even mode. |
| `*` / multiply | Correctly rounded to the destination format, within 0.5 ULP in round-to-nearest-even mode. |
| `/` / divide | Correctly rounded to the destination format, within 0.5 ULP in round-to-nearest-even mode. |
| `SQR` | Correctly rounded square root to the destination format, within 0.5 ULP in round-to-nearest-even mode. |

The transcendental functions in the table above use the project target of no more than 2 ULP over the tested range. The core IEEE arithmetic operations are held to the stricter correctly-rounded requirement because IEEE 754 requires exact operations rounded once to the selected destination format.

## Appendix B: New BASIC Tokens

BASIC V3 preserves the Commodore BASIC 2.0 token range and adds extension tokens for the new features.

### BASIC 3 Tokens

These tokens are always available from the resident BASIC 3 gateway layer.

| Token Bytes | Keyword | Availability | Notes |
| --- | --- | --- | --- |
| `$CE` | `COMPILE` | Direct mode | Compiles the current stored BASIC program. |
| `$D4` | `BASIC` | Direct mode / query parsing | Used by `BASIC2`, `BASIC3.5`, and `BASIC()`. |
| `$FE,$30` | `FPMODE` | Always available | IEEE mode gateway and query token. |

### BASIC 3.5 / 7 Structured Tokens

These tokens are implemented by the BASIC 3.5 / 7 extension mode and are available after `BASIC3.5`.

| Token Byte | Keyword | Availability | Notes |
| --- | --- | --- | --- |
| `$D5` | `ELSE` | BASIC 3.5 / 7 mode | Adds false branch handling to `IF`. |
| `$EB` | `DO` | BASIC 3.5 / 7 mode | Starts a structured loop. |
| `$EC` | `LOOP` | BASIC 3.5 / 7 mode | Ends a `DO` loop. |
| `$ED` | `EXIT` | BASIC 3.5 / 7 mode | Leaves the innermost `DO` loop. |
| `$FC` | `UNTIL` | BASIC 3.5 / 7 mode | Conditional loop modifier. |
| `$FD` | `WHILE` | BASIC 3.5 / 7 mode | Conditional loop modifier. |
| `$CC` | `RGR` | BASIC 3.5 / 7 graphics mode | Sets or queries the current graphics color. |
| `$CD` | `RCLR` | BASIC 3.5 / 7 graphics mode | Clears the graphics area. |
| `$DE` | `GRAPHIC` | BASIC 3.5 / 7 graphics mode | Selects graphics mode (0=text, 1=high-resolution, 3=multicolor). |
| `$DF` | `PAINT` | BASIC 3.5 / 7 graphics mode | Fills regions with the current color. |
| `$E0` | `CHAR` | BASIC 3.5 / 7 graphics mode | Prints text in graphics coordinates (40-column mode only). |
| `$E1` | `BOX` | BASIC 3.5 / 7 graphics mode | Draws rectangular shapes. |
| `$E2` | `CIRCLE` | BASIC 3.5 / 7 graphics mode | Draws circular shapes. |
| `$E3` | `SSHAPE` | BASIC 3.5 / 7 graphics mode | Saves rectangular bitmap regions. |
| `$E4` | `GSHAPE` | BASIC 3.5 / 7 graphics mode | Restores saved bitmap regions. |
| `$E5` | `DRAW` | BASIC 3.5 / 7 graphics mode | Draws line segments with coordinate interpolation. |
| `$E6` | `LOCATE` | BASIC 3.5 / 7 graphics mode | Sets the graphics/text cursor position. |
| `$E7` | `COLOR` | BASIC 3.5 / 7 graphics mode | Sets current drawing color. |
| `$E8` | `SCNCLR` | BASIC 3.5 / 7 graphics mode | Clears screen with current background color. |

In BASIC 2.0 mode, these keywords report `?SYNTAX ERROR`.

### BASIC 3.5 / 7 Graphics Overview

The BASIC 3.5 / 7 graphics commands provide C64-compatible graphics manipulation capabilities using the VIC-II video hardware:

**GRAPHIC Modes:**
- `GRAPHIC 0`: Returns to 40-column text mode
- `GRAPHIC 1`: Enables high-resolution bitmap graphics (320×200 pixels, 2 colors)
- `GRAPHIC 3`: Enables multicolor bitmap graphics (320×200 pixels, 4 colors)
- `GRAPHIC CLR`: Clears the current graphics area without reproducing the BASIC 3.5 memory-copy bug
- Modes 2, 4, and 5 are unsupported and report `?ILLEGAL QUANTITY ERROR`

**Color Management:**
- `COLOR`: Sets current drawing color (text and pen colors depend on mode)
- `SCNCLR`: Clears screen with current background color
- `RGR`: Queries or sets the current graphics color
- `RCLR`: Clears graphics area and resets color state

**Drawing Primitives:**
- `DRAW`: Draws lines between coordinate points with optional coordinate interpolation
- `BOX`: Draws rectangular shapes with optional fill via `PAINT`
- `CIRCLE`: Draws circular and elliptical shapes
- `PAINT`: Flood-fills regions with the current color
- `CHAR`: Prints text at graphics coordinates (40-column mode only)

**Graphics State:**
- `LOCATE`: Sets graphics/text cursor position for subsequent graphics commands
- `SCALE`: Toggles scaled graphics coordinate interpretation
- `SSHAPE`/`GSHAPE`: Save/restore rectangular bitmap regions
- `RDOT`: Reports color at graphics pixel coordinates
- `JOY`: Reads joystick input with BASIC-friendly conversion
- `DEC()`: Converts numeric value to decimal string
- `HEX$()`: Converts numeric value to hexadecimal string

All graphics commands preserve program state: program exit restores stock text mode and stock colors even on ERROR, STOP keyword, STOP key, or fall-through.

### DOS Wedge SEQ Streaming

The `!` wedge provides sequential file streaming to screen output:

- `!filename` and `"filename"` read SEQ files byte-by-byte, streaming PETSCII to screen
- Output is subject to CTRL slow-scroll throttling and STOP abortion
- Appearance state is preserved before streaming and restored on EOF or STOP
- The same throttle applies to LIST, PRINT, and `!` streaming for consistent behavior

### IEEE Tokens

IEEE function tokens use `$FE` as the extension prefix. The second byte starts at `$30` to avoid the single-byte BASIC 3.5 / 4.0 / 7.0 token ranges and the lower BASIC 7.0 `$FE` extension range.

| Token Bytes | Keyword | Notes |
| --- | --- | --- |
| `$FE,$30` | `FPMODE` | IEEE mode and rounding control. |
| `$FE,$31` | `FPFLAGS` | Read sticky exception flags. |
| `$FE,$32` | `FPCLR` | Clear sticky exception flags. |
| `$FE,$33` | `FPSET` | Raise sticky exception flags. |
| `$FE,$34` | `ISNAN` | NaN classifier. |
| `$FE,$35` | `ISSNAN` | Signaling NaN classifier. |
| `$FE,$36` | `ISINF` | Infinity classifier. |
| `$FE,$37` | `ISFIN` | Finite nonzero classifier. |
| `$FE,$38` | `ISNORM` | Normal finite classifier. |
| `$FE,$39` | `ISZERO` | Signed-zero classifier. |
| `$FE,$3A` | `SGNBIT` | Sign-bit test. |
| `$FE,$3B` | `ISUNORD` | Unordered comparison test. |
| `$FE,$3C` | `COPYSGN` | Copy sign bit from second operand. |
| `$FE,$3D` | `TOTALORDER` | IEEE totalOrder comparison. |
| `$FE,$3E` | `FPTEST`, `FPTTEST` | Mask sticky exception flags. `FPTTEST` is an accepted alias. |
| `$FE,$3F` | `BIN32$` | Convert BASIC numeric value to printable binary32 hex text. |
| `$FE,$40` | `VAL32` | Convert binary32 hex text to BASIC numeric value. |
| `$FE,$41` | `FMA` | Fused multiply-add. |
| `$FE,$42` | `REMAIN` | IEEE remainder. |
| `$FE,$43` | `MIN` | IEEE-aware minimum. |
| `$FE,$44` | `MAX` | IEEE-aware maximum. |
| `$FE,$45` | `SCALB` | Scale by a power of two. |
| `$FE,$46` | `LOGB` | Unbiased binary exponent. |
| `$FE,$47` | `MANT` | Normalized significand. |
| `$FE,$48` | `RINT` | Round to integral value. |
| `$FE,$49` | `NEXTUP` | Next representable value upward. |
| `$FE,$4A` | `NEXTDOWN` | Next representable value downward. |

## Appendix C: IEEE 754 Notes

IEEE 754 defines floating-point formats, arithmetic operations, rounding attributes, exception flags, special values, and interchange encodings. BASIC V3 does not replace its internal number format with IEEE binary32. Instead, IEEE mode applies IEEE-style semantics to the existing 5-byte packed BASIC number format and provides explicit conversion to and from portable binary32.

### Implemented Required Operations

The IEEE mode implementation covers these required operation families for the BASIC V3 destination format:

| IEEE Operation Area | BASIC V3 Surface |
| --- | --- |
| Addition | `+`, internal `basic_math_add` |
| Subtraction | `-`, internal `basic_math_subtract` |
| Multiplication | `*`, internal `basic_math_multiply` |
| Division | `/`, internal `basic_math_divide` |
| Square root | `SQR(x)` |
| Fused multiply-add | `FMA(x,y,z)` |
| Remainder | `REMAIN(x,y)` |
| Round to integral | `RINT(x)` |
| Comparisons / unordered handling | Relational operators plus `ISUNORD` and `TOTALORDER` |
| min/max style operations | `MIN(x,y)`, `MAX(x,y)` |
| Classification | `ISNAN`, `ISSNAN`, `ISINF`, `ISFIN`, `ISNORM`, `ISZERO`, `SGNBIT` |
| Exception flags | `FPFLAGS`, `FPCLR`, `FPSET`, `FPTEST` / `FPTTEST` |
| Rounding control | `FPMODE` control bits |
| Format conversion | `BIN32$` and `VAL32` |

Some elementary functions, such as `LOG`, `EXP`, `SIN`, `COS`, `TAN`, and `ATN`, also have IEEE special-value behavior where applicable, but they are not the core required arithmetic operations listed above.

### BASIC V3 5-Byte Numeric Encoding

Finite values use the existing Commodore-style packed layout:

```text
byte 0  exponent, bias 128
byte 1  sign bit in bit 7, high significand bits in bits 0-6
byte 2  significand
byte 3  significand
byte 4  significand
```

Examples:

| Value | Packed Bytes |
| ---: | --- |
| `0` | `$00 $00 $00 $00 $00` |
| `1` | `$81 $00 $00 $00 $00` |
| `2` | `$82 $00 $00 $00 $00` |
| `3` | `$82 $40 $00 $00 $00` |
| `4` | `$83 $00 $00 $00 $00` |
| `10` | `$84 $20 $00 $00 $00` |
| `-1` | `$81 $80 $00 $00 $00` |

IEEE mode reserves exponent `$FF` for non-finite values and preserves exponent `$00` for signed zero:

| Value | Packed Bytes | Meaning |
| --- | --- | --- |
| `+0` | `$00 $00 $00 $00 $00` | Positive zero. |
| `-0` | `$00 $80 $00 $00 $00` | Negative zero, sign bit set. |
| `+INF` | `$FF $00 $00 $00 $00` | Positive infinity. |
| `-INF` | `$FF $80 $00 $00 $00` | Negative infinity. |
| `qNaN` | `$FF $40 pp pp pp` | Quiet NaN, quiet bit set, payload nonzero. |
| `sNaN` | `$FF $00 pp pp pp` | Signaling NaN, quiet bit clear, payload nonzero. |

Signaling NaNs are quieted when consumed by most operations and raise the invalid flag.

### Binary32 Conversion

Portable IEEE binary32 values are four bytes:

```text
bit 31      sign
bits 30-23  exponent, bias 127
bits 22-0   fraction
```

BASIC V3 uses big-endian byte order for binary32 hex strings: most significant byte first. The functions are:

```basic
A$=BIN32$(X)
X=VAL32(A$)
```

`BIN32$(x)` converts a BASIC V3 number to a printable `$XXXXXXXX` binary32 hex string using the current rounding mode. `VAL32(b$)` converts an eight-digit binary32 hex string, with or without the leading `$`, back into a BASIC V3 number. `VAL()` accepts the same binary32 hex string form.

Conversion examples:

| Value | BASIC V3 Packed Bytes | Binary32 Bytes | Notes |
| --- | --- | --- | --- |
| `+0` | `$00 $00 $00 $00 $00` | `$00 $00 $00 $00` | Positive zero. |
| `-0` | `$00 $80 $00 $00 $00` | `$80 $00 $00 $00` | Negative zero. |
| `1` | `$81 $00 $00 $00 $00` | `$3F $80 $00 $00` | Exact. |
| `2` | `$82 $00 $00 $00 $00` | `$40 $00 $00 $00` | Exact. |
| `10` | `$84 $20 $00 $00 $00` | `$41 $20 $00 $00` | Exact. |
| `-1` | `$81 $80 $00 $00 $00` | `$BF $80 $00 $00` | Exact. |
| `+INF` | `$FF $00 $00 $00 $00` | `$7F $80 $00 $00` | Positive infinity. |
| `-INF` | `$FF $80 $00 $00 $00` | `$FF $80 $00 $00` | Negative infinity. |
| `qNaN` | `$FF $40 pp pp pp` | `$7F $C0 pp pp` | Payload is preserved as far as the destination allows. |
| `sNaN` | `$FF $00 pp pp pp` | `$7F $80 pp pp` | May be quieted by operations that consume it. |

When converting finite values, exact binary values such as `1`, `2`, and `10` round-trip cleanly. Values that cannot be represented exactly in binary32 are rounded according to the active `FPMODE` rounding bits and may raise the inexact flag. Overflow produces infinity or the directed-rounding maximum finite result according to the rounding mode; underflow produces signed zero in the first implementation and raises underflow plus inexact when rounded.

## Appendix D: Adaptive Numeric Types

BASIC V3 can store numeric values in one of four internal forms:

| Type | Tag | Range / Meaning |
| --- | ---: | --- |
| `TYPE_FLOAT` | `$00` | Existing 5-byte Commodore-style packed float. |
| `TYPE_INT1` | `$01` | Signed 8-bit integer, `-128` through `127`. |
| `TYPE_INT2` | `$02` | Signed 16-bit integer, `-32768` through `32767`. |
| `TYPE_INT3` | `$03` | Unsigned 16-bit integer, `0` through `65535`. Useful for addresses, character counts, and other naturally unsigned BASIC values. |

This is an internal optimization. BASIC-visible behavior should remain compatible with ordinary numeric BASIC code. When an integer path cannot safely preserve behavior, the runtime promotes to a wider type:

```text
INT1 -> INT2 -> INT3 -> FLOAT
```

`INT3` is used only where an unsigned 16-bit value preserves BASIC behavior.
Negative values remain signed, and arithmetic that cannot stay in the safe
integer domain promotes to float.

### Where Types Are Used

- Scalar variables carry a type byte with their value payload.
- FAC and ARG carry `math_fac_type` and `math_arg_type` tags.
- Expression save/restore helpers preserve both the numeric payload and the type tag.
- PRINT can route integer-typed values through integer-aware formatting while preserving BASIC output shape.
- Compiled literal and expression paths can choose compact integer tags before falling back to float.
- Address-facing statements and functions can naturally use `INT3` when the value is in the C64 address range.

Literal classification examples:

| Literal | Internal Type |
| --- | --- |
| `0` | `INT1` |
| `2` | `INT1` |
| `2.0` | `INT1`, if exactly integer-valued after parsing |
| `2.1` | `FLOAT` |
| `200` | `INT2` |
| `32767` | `INT2` |
| `32768` | `INT3` |
| `65535` | `INT3` |
| `65536` | `FLOAT` |
| `1E5` | `FLOAT` |

### Explicit INT1 / INT2 / INT3 Implementations

The following paths have explicit integer handling:

| Area | INT1 / INT2 / INT3 Status |
| --- | --- |
| Variable load/store | Numeric variable entries include a type byte and 5-byte payload. |
| Integer-to-float conversion | Adaptive conversion helpers convert integer payloads when a float path is needed. |
| Addition | Native integer add paths promote when the result no longer fits the current integer tier. |
| Subtraction | Native integer subtract paths use the same promotion model, with unsigned cases promoted when needed to preserve signed BASIC behavior. |
| Multiplication | Native integer multiply paths handle compact products; wide or overflowing results promote as needed. |
| Unary minus | Integer unary negation is handled in the expression parser, with promotion for edge cases that cannot fit. |
| Comparisons | Integer comparisons are implemented for same-tier and mixed-tier operands; boolean results are `TYPE_INT1`. |
| PRINT | Integer-typed values are routed separately so integer values can avoid float formatting while matching BASIC output. |
| `INT()` | Integer inputs are preserved as integer values. |
| `PI` and `TI` | Explicitly marked as `TYPE_FLOAT`, not integer. |
| Address conversion helpers | Several address-oriented parser helpers accept unsigned 16-bit values through `TYPE_INT3`. |

The following paths intentionally promote to float or are still staged:

| Area | Status |
| --- | --- |
| Division | Promotes to float unless the integer division fast path can prove an exact integer result. |
| `SIN`, `COS`, `TAN`, `ATN`, `LOG`, `EXP` | Integer inputs are converted to float before calling the numeric routine; results are `TYPE_FLOAT`. |
| `SGN()` and `ABS()` | Planned to be fully integer-aware; they should return compact integer results where safe. |
| FOR/NEXT integer loop execution | Frame type storage exists, but dedicated INT1/INT2/INT3 NEXT paths and loop-frame promotion are still staged. |
| Address keywords | `WAIT`, `PEEK()`, `POKE`, and `SYS` should gain explicit `INT3` fast paths because their address operands are unsigned 16-bit values. |
| Natural small-integer functions | `ASC()`, `CHR$()`, `SPC()`, `TAB()`, and any future `LOCATE` implementation should prefer compact integer argument fast paths where behavior remains compatible. |

### Measured Adaptive Benchmarks

Current same-build benchmark summary from `ADAPTIVE_TYPE.md`. These rows should
be regenerated by a future documentation build step after the full test suite is
green.

| Case | Baseline Cycles | Standard Compiled Loop Cycles | Delta | Output |
| --- | ---: | ---: | ---: | --- |
| INT1 add loop | 2,035,470 | 1,380,063 | +32.2% | ` 257` |
| INT2 add loop | 4,285,524 | 1,671,932 | +61.0% | ` 51400` |
| FLOAT add loop | 7,732,210 | 1,708,836 | +77.9% | ` 321.25` |
| INT1 multiply loop | 24,846 | 15,135 | +39.1% | ` 64` |
| INT2 multiply loop | 9,769 | 24,525 | -151.0% | ` 1600` |
| FLOAT multiply loop | 146,936 | 107,308 | +27.0% | ` 26.578125` |

The broad compiled benchmark shows a larger program-level improvement:

```text
baseline cycles: 909,066
standard compiled cycles: 235,857
speedup:         3.85x
```

The INT2 multiply case is currently a known tradeoff: its overflow-safe signed path is heavier than the float path for that benchmark.

## Appendix E: Zero-Page Usage Design

BASIC V3 treats zero page as a managed resource instead of a fixed stock-ROM layout. User-visible BASIC compatibility is required, but private stock zero-page addresses are not a compatibility contract.

Every zero-page allocation is assigned:

- a symbol name,
- an address range,
- a size,
- a category,
- a lifetime.

Examples of categories include program memory pointers, expression lifetime, statement-local scratch, parser-local scratch, math working registers, math extended scratch, STOP/CONT-resumable state, FOR/NEXT state, direct-mode/editor state, and loader install scratch.

### Lifetime-Based Sharing

The design goal is to share zero-page locations only when lifetimes do not conflict. A pointer used only during loader install can overlap with runtime state because it is dead before BASIC starts. A statement-local scratch byte may share with another temporary only if no routine can need both at the same time.

Some state never shares:

- Persistent session state never shares with temporary state.
- STOP/CONT-resumable state does not share with per-statement scratch.
- FAC does not share with formatter scratch while a PRINT result is live.
- Expression result storage does not share with assignment destination state until assignment completes.
- String temporary descriptors do not share with garbage-collector traversal state.
- Multi-byte regions are checked as ranges unless byte-level reuse is explicitly documented.
- `$A0-$A2` remains reserved for the KERNAL-compatible `basic_jiffy` clock.

### Graph Coloring

The zero-page analyzer models allocations as live ranges. When two symbols can be live at the same time, they interfere and cannot occupy overlapping bytes. This creates an interference graph:

- nodes are zero-page symbols or ranges,
- edges mean the lifetimes conflict,
- colors are concrete zero-page byte ranges.

Graph coloring then assigns addresses so non-conflicting lifetimes can share storage while conflicting lifetimes are kept apart. The current allocation report says:

```text
Status: ok
Interference Graph: No overlapping live ranges were found.
```

### Current Allocation Shape

Important current zero-page regions are shown below as a snapshot. The planned
documentation build should derive this table from the latest allocation report
instead of keeping it hand-maintained.

| Range | Symbols | Purpose |
| --- | --- | --- |
| `$04-$13` | `program_ptr`, `list_output_ptr`, `run_output_ptr`, `line_input_ptr`, statement scratch | Program storage and statement dispatch state. |
| `$14-$1A` | `expr_input_ptr`, `expr_output_ptr`, `expr_status`, `expr_type`, `expr_cursor` | Expression parser state. |
| `$1B-$33` | `math_fac`, `math_arg`, `math_status`, math pointers/scratch, `math_fac_type`, `math_arg_type` | Numeric working registers and adaptive type tags. |
| `$70-$7F` | direct-mode and parser helper pointers | READY/direct runtime support. |
| `$80-$8B` | compile/runtime scratch and generated-code helpers | Compiler/runtime temporary state. |
| `$8C-$91` | FOR/NEXT pointer and temporaries | Loop state and loop statement scratch. |
| `$92-$93` | `math_coeff_ptr` | Numeric polynomial/FMA coefficient pointer. |
| `$A0-$A2` | `basic_jiffy` | Permanent KERNAL-compatible TI clock. |
| `$FB-$FE` | loader copy pointers | Loader install only. |

Run the analyzer with:

```powershell
python .\zp\analyze.py --manifest .\build\loader_manifest.json --conflicts .\zp\conflicts.json --listing .\build\basic.lst --json-out .\build\zp_allocation_report.json --md-out .\zp\allocation.md
```

The analyzer fails if a range is unclassified, violates a hard rule, crosses an invalid boundary, or overlaps a live conflicting allocation.

## Appendix F: Numeric Benchmarks

Generated for build `14-dirty` on 2026-05-07 UTC.

This table compares selected live benchmarks across stock Commodore BASIC V2 and BASIC V3 modes. Stock benchmarks run a small stored program with 30 loop iterations. Stock BASIC V2 is measured through VICE MCP using the cycle stopwatch. BASIC V3 benchmarks call each numeric runtime entrypoint 30 times in the local 6502 emulator through numeric runtime entrypoints, using median cycles over 3 rounds.

`-` means the operation or mode was not implemented or could not be measured by the harness.

| Operation | Stock BASIC V2 | BASIC V3 INT1 | BASIC V3 INT2 | BASIC V3 FLOAT | BASIC V3 IEEE FLOAT |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ADD` | 172,297 | 6,720 | 7,200 | 24,570 | 35,760 |
| `SUB` | 27,371 | 6,450 | 6,930 | 29,790 | 52,860 |
| `MUL` | 22,786 | 23,520 | 24,060 | 116,790 | 128,310 |
| `DIV` | 26,722 | 26,460 | 27,300 | 295,200 | 308,340 |
| `^` | 184,159 | 5,400 | 187,320 | 3,271,710 | 3,384,660 |
| `SQR` | 184,105 | 3,870 | 373,290 | 349,740 | 354,150 |
| `LOG` | 290,813 | 349,470 | 1,877,220 | 1,647,690 | 1,723,620 |
| `EXP` | 25,689 | 1,686,420 | 1,875,930 | 1,835,760 | 1,930,740 |
| `SIN` | 30,618 | 1,180,800 | 1,162,200 | 1,149,540 | 1,208,760 |
| `COS` | 29,213 | 1,357,710 | 1,332,180 | 1,320,600 | 1,392,930 |
| `TAN` | 30,523 | 2,398,890 | 2,326,680 | 1,417,770 | 1,464,360 |
| `ATN` | 184,639 | 13,830 | 1,851,630 | 1,880,640 | 1,966,950 |

Benchmark source:

```powershell
python .\tests\benchmark_manual_numeric.py --measure-stock-vice --rounds 3 --json-out build\manual_numeric_benchmark.json
```

JSON output:

```text
build\manual_numeric_benchmark.json
```

The benchmark is intentionally broad rather than microcoded per kernel: it includes BASIC loop overhead, expression dispatch, variable access, and the operation under test. It therefore reflects user-visible program execution more than isolated subroutine throughput.
