# BASIC V3 Keyword Reference

This document provides an alphabetical reference of the intended BASIC V3
keyword surface, including BASIC 2.0 compatibility, BASIC 3.5 extensions, and
IEEE 754 functions.

`../REQUIREMENTS.md` is the authority for required language compatibility. If
this reference omits or contradicts a required stock BASIC V2 keyword,
operator, syntax token, or semantic behavior, the requirement still applies and
this file must be corrected.

## Table of Contents

- [Operators](#operators)
- [Statements A-Z](#statements-a-z)
- [Functions A-Z](#functions-a-z)
- [BASIC 3 Extensions](#basic-3-extensions)
- [BASIC 3.5 / 7 Extensions](#basic-35--7-extensions)
- [IEEE 754 Functions](#ieee-754-functions)
- [Disk Wedge Commands](#disk-wedge-commands)

## Operators

### Arithmetic Operators

| Operator | Description | Example | Result |
|----------|-------------|---------|--------|
| `+` | Addition | `PRINT 2+3` | `5` |
| `-` | Subtraction/Negation | `PRINT 5-2` | `3` |
| `*` | Multiplication | `PRINT 3*4` | `12` |
| `/` | Division | `PRINT 10/2` | `5` |
| `^` | Exponentiation | `PRINT 2^3` | `8` |

### Comparison Operators

| Operator | Description | Example | Result (-1=true, 0=false) |
|----------|-------------|---------|---------------------------|
| `=` | Equal | `PRINT 2=2` | `-1` |
| `<>` | Not equal | `PRINT 2<>3` | `-1` |
| `<` | Less than | `PRINT 2<3` | `-1` |
| `>` | Greater than | `PRINT 3>2` | `-1` |
| `<=` | Less or equal | `PRINT 2<=2` | `-1` |
| `>=` | Greater or equal | `PRINT 3>=2` | `-1` |

### Logical Operators

| Operator | Description | Example | Result |
|----------|-------------|---------|--------|
| `AND` | Bitwise AND | `PRINT -1 AND -1` | `-1` |
| `OR` | Bitwise OR | `PRINT 0 OR -1` | `-1` |
| `NOT` | Bitwise NOT | `PRINT NOT 0` | `-1` |

## Statements A-Z

### ABS
**Syntax**: `ABS(numeric-expression)`
**Type**: Function
**Description**: Returns the absolute value of a number.
**Example**:
```basic
PRINT ABS(-5)    ' Output: 5
PRINT ABS(5)     ' Output: 5
```

### ACS
**Syntax**: `ACS(numeric-expression)`
**Type**: Function
**Description**: Returns the arccosine (inverse cosine) in radians.
**Example**:
```basic
PRINT ACS(1)     ' Output: 0
```

### AND
**Syntax**: `expression1 AND expression2`
**Type**: Operator
**Description**: Performs bitwise AND operation.
**Example**:
```basic
PRINT 7 AND 3    ' Output: 3 (binary: 0111 AND 0011 = 0011)
```

### ASC
**Syntax**: `ASC(string-expression)`
**Type**: Function
**Description**: Returns the ASCII code of the first character in a string.
**Example**:
```basic
PRINT ASC("A")   ' Output: 65
```

### ASN
**Syntax**: `ASN(numeric-expression)`
**Type**: Function
**Description**: Returns the arcsine (inverse sine) in radians.
**Example**:
```basic
PRINT ASN(0)     ' Output: 0
```

### ATN
**Syntax**: `ATN(numeric-expression)`
**Type**: Function
**Description**: Returns the arctangent (inverse tangent) in radians.
**Example**:
```basic
PRINT ATN(1)     ' Output: 0.785398163 (PI/4)
```

### BASIC2
**Syntax**: `BASIC2`
**Type**: Statement (always enabled)
**Description**: Switches to BASIC 2 compatibility mode. BASIC 2 is the default startup mode, and this gateway command remains available in BASIC 2 and BASIC 3.5 modes.
**Example**:
```basic
BASIC2           ' Return to BASIC 2 compatibility
```

### BASIC3.5
**Syntax**: `BASIC3.5`
**Type**: Statement (always enabled)
**Description**: Switches to BASIC 3.5 mode. This gateway command is available from the default BASIC 2 mode so enhanced BASIC can be enabled immediately after startup.
**Example**:
```basic
BASIC3.5         ' Enable BASIC 3.5 features
```

### BASIC()
**Syntax**: `BASIC()`
**Type**: Function (always enabled)
**Description**: Returns the current BASIC version as a number: `2` in BASIC 2 mode or `3.5` in BASIC 3.5 mode. This resident query intentionally accepts no expression argument so it can remain small and always available.
**Example**:
```basic
PRINT BASIC()    ' Output: 2 or 3.5
```

### BIN32$
**Syntax**: `BIN32$(numeric-expression)`
**Type**: Function (IEEE mode)
**Description**: Converts a number to a printable big-endian IEEE 754 binary32 hex string.
**Example**:
```basic
FPMODE1
PRINT BIN32$(1)    ' Output: $3F800000
```

### CHR$
**Syntax**: `CHR$(numeric-expression)`
**Type**: Function
**Description**: Returns a string containing the character with the specified ASCII code.
**Example**:
```basic
PRINT CHR$(65)   ' Output: A
```

### CLOSE
**Syntax**: `CLOSE [#file-number]`
**Type**: Statement
**Description**: Closes one open file by logical file number. A missing file number is accepted by the parser and follows the runtime close-all path where supported.
**Example**:
```basic
OPEN 1,8,15
CLOSE #1
```

### CLR
**Syntax**: `CLR`
**Type**: Statement (Immediate mode)
**Description**: Clears all variables and resets the stack. Does not affect program text.
**Example**:
```basic
CLR
```

### CMD
**Syntax**: `CMD logical-file-number [, expression-list]`
**Type**: Statement
**Description**: Redirects subsequent screen output to an open output channel using stock BASIC V2 semantics.
**Example**:
```basic
10 OPEN 1,8,15
20 CMD 1
30 PRINT "I"
```

### CONT
**Syntax**: `CONT`
**Type**: Statement (Immediate mode)
**Description**: Continues program execution after STOP or error.
**Example**:
```basic
CONT
```

### COS
**Syntax**: `COS(numeric-expression)`
**Type**: Function
**Description**: Returns the cosine of an angle in radians.
**Example**:
```basic
PRINT COS(0)     ' Output: 1
```

### DATA
**Syntax**: `DATA value1,value2,...`
**Type**: Statement
**Description**: Defines data values to be read by READ statements.
**Example**:
```basic
10 READ A,B
20 DATA 1,2,3
```

### DEF
**Syntax**: `DEF FNname(arg)=expression`
**Type**: Statement
**Description**: Defines a user function.
**Example**:
```basic
10 DEF FNSQR(X)=X*X
20 PRINT FNSQR(4)  ' Output: 16
```

### DIM
**Syntax**: `DIM variable(size[,size2...])`
**Type**: Statement
**Description**: Dimensions arrays with specified bounds.
**Example**:
```basic
10 DIM A(10)          ' Single dimension
20 DIM B(5,5)         ' Two dimensions
30 DIM C$(20)         ' String array
```

### DO
**Syntax**: `DO`, `DO WHILE condition`, `DO UNTIL condition`
**Type**: Statement (BASIC 3.5+)
**Description**: Begins a structured `DO`/`LOOP` block. `DO WHILE` and `DO UNTIL` are pre-test forms. `LOOP`, `LOOP WHILE`, and `LOOP UNTIL` end the block.
**Compiler note**: Safe bare `DO`/`LOOP` pairs may compile to a direct native backedge. Conditional forms keep BASIC-compatible generic condition evaluation unless a descriptor-gated native condition path is proven safe by the compiler.
**Example**:
```basic
10 I=0
20 DO
30   I=I+1
40 LOOP UNTIL I=10
```

### ELSE
**Syntax**: `IF condition THEN statement ELSE statement`
**Type**: Statement (BASIC 3.5+)
**Description**: Provides alternative branch for IF statement.
**Example**:
```basic
10 IF X=1 THEN PRINT "ONE" ELSE PRINT "NOT ONE"
```

### END
**Syntax**: `END`
**Type**: Statement
**Description**: Terminates program execution.
**Example**:
```basic
10 PRINT "DONE"
20 END
```

### EXIT
**Syntax**: `EXIT`
**Type**: Statement (BASIC 3.5+)
**Description**: Leaves the innermost active `DO` loop and resumes after the matching `LOOP`.
**Example**:
```basic
10 DO
20 I=I+1
30 IF I=5 THEN EXIT
40 LOOP
```

### EXP
**Syntax**: `EXP(numeric-expression)`
**Type**: Function
**Description**: Returns e (2.71828...) raised to the power of the expression.
**Example**:
```basic
PRINT EXP(1)     ' Output: 2.71828...
```

### FOR
**Syntax**: `FOR variable=start TO end [STEP increment]`
**Type**: Statement
**Description**: Begins a FOR...NEXT loop.
**Compiler note**: Proven literal integer loops can use descriptor-gated direct runtime-cell helpers. Floating, bank-ambiguous, modified, or otherwise unsafe loops use the generic FOR/NEXT runtime path.
**Example**:
```basic
10 FOR I=1 TO 10 STEP 2
20   PRINT I
30 NEXT I
```

### FN
**Syntax**: `FN name(argument)`
**Type**: Function syntax token
**Description**: Invokes a user-defined function created with `DEF FN`.
**Example**:
```basic
10 DEF FNA(X)=X+1
20 PRINT FNA(1)
```

### FRE
**Syntax**: `FRE(numeric-expression)`
**Type**: Function
**Description**: Returns the number of bytes of free memory.
**Example**:
```basic
PRINT FRE(0)
```

### GET
**Syntax**: `GET variable$`
**Type**: Statement
**Description**: Reads a single character from keyboard buffer.
**Example**:
```basic
10 GET A$
20 IF A$="" THEN 10
30 PRINT A$
```

### GOSUB
**Syntax**: `GOSUB line-number`
**Type**: Statement
**Description**: Jumps to a subroutine at the specified line number.
**Example**:
```basic
10 GOSUB 100
20 END
100 PRINT "SUBROUTINE"
110 RETURN
```

### GOTO
**Syntax**: `GOTO line-number`
**Type**: Statement
**Description**: Jumps to the specified line number.
**Example**:
```basic
10 GOTO 30
20 PRINT "SKIP"
30 PRINT "GOTO"
```

### IF
**Syntax**: `IF condition THEN statement [ELSE statement]`
**Type**: Statement
**Description**: Conditional execution.
**Example**:
```basic
10 IF X>0 THEN PRINT "POSITIVE"
```

### INPUT#
**Syntax**: `INPUT# logical-file-number, variable-list`
**Type**: Statement
**Description**: Reads values from an open input channel using stock BASIC V2 parsing and error behavior.
**Example**:
```basic
10 INPUT#1,A$
```

### INPUT
**Syntax**: `INPUT ["prompt";] variable`
**Type**: Statement
**Description**: Prompts for and reads user input.
**Example**:
```basic
10 INPUT "Enter value: "; X
```

### INT
**Syntax**: `INT(numeric-expression)`
**Type**: Function
**Description**: Returns the greatest integer less than or equal to the expression.
**Example**:
```basic
PRINT INT(3.9)
```

### LEFT$
**Syntax**: `LEFT$(string-expression, length)`
**Type**: Function
**Description**: Returns the leftmost characters of a string.
**Example**:
```basic
PRINT LEFT$("HELLO",2)  ' Output: HE
```

### LEN
**Syntax**: `LEN(string-expression)`
**Type**: Function
**Description**: Returns the length of a string.
**Example**:
```basic
PRINT LEN("HELLO")  ' Output: 5
```

### LET
**Syntax**: `[LET] variable=expression`
**Type**: Statement
**Description**: Assigns a value to a variable. LET is optional.
**Example**:
```basic
10 LET X=5    ' Same as: 10 X=5
```

### LIST
**Syntax**: `LIST`
**Type**: Statement (Immediate mode)
**Description**: Lists stored program lines. Early milestones may support only bare `LIST`; stock range forms remain required by `../REQUIREMENTS.md`.
**Example**:
```basic
LIST
```

### LOAD
**Syntax**: `LOAD "filename" [,device]`
**Type**: Statement (Immediate mode)
**Description**: Loads a program from disk.
**Example**:
```basic
LOAD "PROGRAM",8
```

### LOG
**Syntax**: `LOG(numeric-expression)`
**Type**: Function
**Description**: Returns the natural logarithm (base e).
**Example**:
```basic
PRINT LOG(10)
```

### MID$
**Syntax**: `MID$(string-expression, start [, length])`
**Type**: Function
**Description**: Extracts a substring.
**Example**:
```basic
PRINT MID$("HELLO",2,3)  ' Output: ELL
```

### NEW
**Syntax**: `NEW`
**Type**: Statement (Immediate mode)
**Description**: Clears program and variables, resets to fresh state.
**Example**:
```basic
NEW
```

### NEXT
**Syntax**: `NEXT [variable]`
**Type**: Statement
**Description**: Ends a FOR...NEXT loop.
**Example**:
```basic
10 FOR I=1 TO 10
20 PRINT I
30 NEXT I
```

### NOT
**Syntax**: `NOT expression`
**Type**: Operator
**Description**: Bitwise NOT (inversion).
**Example**:
```basic
PRINT NOT 0   ' Output: -1
```

### ON
**Syntax**: `ON expression GOTO line1,line2,...`
**Type**: Statement
**Description**: Multi-way branch based on expression value.
**Example**:
```basic
10 X=2
20 ON X GOTO 100,200,300
```

### OPEN
**Syntax**: `OPEN logical-file-number [, device [, secondary-address [, filename]]]`
**Type**: Statement
**Description**: Opens a logical file through the KERNAL with stock BASIC V2 channel semantics.
**Example**:
```basic
OPEN 1,8,15
```

### OR
**Syntax**: `expression1 OR expression2`
**Type**: Operator
**Description**: Bitwise OR operation.
**Example**:
```basic
PRINT 7 OR 3   ' Output: 7
```

### PEEK
**Syntax**: `PEEK(address)`
**Type**: Function
**Description**: Returns the byte at the specified memory address.
**Example**:
```basic
PRINT PEEK(53265)  ' VIC control register
```

### POKE
**Syntax**: `POKE address, value`
**Type**: Statement
**Description**: Writes a byte to the specified memory address.
**Example**:
```basic
POKE 53280,0    ' Set border color to black
```

### POS
**Syntax**: `POS(numeric-expression)`
**Type**: Function
**Description**: Returns the current cursor column position.
**Example**:
```basic
PRINT POS(0)
```

### PRINT
**Syntax**: `PRINT [expression list]`
**Type**: Statement
**Description**: Outputs text and values to screen.
**Example**:
```basic
10 PRINT "HELLO WORLD"
20 PRINT A,B,C
30 PRINT "X=";X
```

### PRINT#
**Syntax**: `PRINT# logical-file-number [, expression-list]`
**Type**: Statement
**Description**: Writes formatted output to an open output channel using stock BASIC V2 semantics.
**Example**:
```basic
10 PRINT#1,"HELLO"
```

### READ
**Syntax**: `READ variable1,variable2,...`
**Type**: Statement
**Description**: Reads values from DATA statements.
**Example**:
```basic
10 READ A,B,C
20 DATA 1,2,3
```

### REM
**Syntax**: `REM comment`
**Type**: Statement
**Description**: Remark (comment). Everything after REM is ignored.
**Example**:
```basic
10 REM This is a comment
```

### RESTORE
**Syntax**: `RESTORE [line-number]`
**Type**: Statement
**Description**: Resets DATA pointer to beginning or specified line.
**Example**:
```basic
10 RESTORE
20 RESTORE 100
```

### RETURN
**Syntax**: `RETURN`
**Type**: Statement
**Description**: Returns from a GOSUB subroutine.
**Example**:
```basic
100 GOSUB 200
110 END
200 PRINT "SUB"
210 RETURN
```

### RIGHT$
**Syntax**: `RIGHT$(string, length)`
**Type**: Function
**Description**: Returns the rightmost characters of a string.
**Example**:
```basic
PRINT RIGHT$("HELLO",2)  ' Output: LO
```

### RND
**Syntax**: `RND(numeric-expression)`
**Type**: Function
**Description**: Returns a random number between 0 and 1.
**Example**:
```basic
10 PRINT RND(1)
```

### RUN
**Syntax**: `RUN [line-number]`
**Type**: Statement (Immediate mode)
**Description**: Compiles and runs the stored tokenized program. Direct `RUN` with no argument enters the public compiled-program runner; `RUN line-number` starts at the requested line where supported by the compiled runner.
**Example**:
```basic
RUN
RUN 100
```

### SAVE
**Syntax**: `SAVE "filename" [,device]`
**Type**: Statement (Immediate mode)
**Description**: Saves the current program to disk.
**Example**:
```basic
SAVE "PROGRAM",8
```

### SGN
**Syntax**: `SGN(numeric-expression)`
**Type**: Function
**Description**: Returns the sign: -1 (negative), 0 (zero), or 1 (positive).
**Example**:
```basic
PRINT SGN(-5)   ' Output: -1
PRINT SGN(0)    ' Output: 0
PRINT SGN(5)    ' Output: 1
```

### SIN
**Syntax**: `SIN(numeric-expression)`
**Type**: Function
**Description**: Returns the sine of an angle in radians.
**Example**:
```basic
PRINT SIN(0)    ' Output: 0
```

### SPC
**Syntax**: `SPC(count)`
**Type**: Function
**Description**: Skips the specified number of spaces in PRINT.
**Example**:
```basic
PRINT "A";SPC(5);"B"   ' Output: A     B
```

### SQR
**Syntax**: `SQR(numeric-expression)`
**Type**: Function
**Description**: Returns the square root.
**Example**:
```basic
PRINT SQR(16)   ' Output: 4
```

### STATUS
**Syntax**: `STATUS` or `ST`
**Type**: Function
**Description**: Returns the status of the last I/O operation.
**Example**:
```basic
PRINT ST
```

### STEP
**Syntax**: `FOR I=start TO end STEP increment`
**Type**: Keyword (used with FOR)
**Description**: Specifies the increment value in a FOR loop.
**Example**:
```basic
10 FOR I=1 TO 10 STEP 2
```

### STOP
**Syntax**: `STOP`
**Type**: Statement
**Description**: Stops program execution (can be continued with CONT).
**Example**:
```basic
10 STOP
```

### STR$
**Syntax**: `STR$(numeric-expression)`
**Type**: Function
**Description**: Converts a number to a string.
**Example**:
```basic
A$=STR$(123)
```

### SYS
**Syntax**: `SYS address`
**Type**: Statement
**Description**: Jumps to a machine language routine at the specified address.
**Example**:
```basic
SYS 64738    ' C64 warm start
```

### TAB
**Syntax**: `TAB(position)`
**Type**: Function
**Description**: Moves cursor to specified column in PRINT.
**Example**:
```basic
PRINT "A";TAB(10);"B"
```

### TAN
**Syntax**: `TAN(numeric-expression)`
**Type**: Function
**Description**: Returns the tangent of an angle in radians.
**Example**:
```basic
PRINT TAN(0)   ' Output: 0
```

### THEN
**Syntax**: `IF condition THEN statement`
**Type**: Keyword (used with IF)
**Description**: Introduces the true branch of an IF statement.

### TI$
**Syntax**: `TI$`
**Type**: Function
**Description**: Returns the current time as a string (HHMMSS).
**Example**:
```basic
PRINT TI$
```

### TO
**Syntax**: `FOR I=start TO end`
**Type**: Keyword (used with FOR)
**Description**: Specifies the end value in a FOR loop.

### USR
**Syntax**: `USR(numeric-expression)`
**Type**: Function
**Description**: Calls a user-defined machine language routine.
**Example**:
```basic
X=USR(0)
```

### VAL
**Syntax**: `VAL(string-expression)`
**Type**: Function
**Description**: Converts a string to a number.
**Example**:
```basic
PRINT VAL("123")   ' Output: 123
```

### VERIFY
**Syntax**: `VERIFY "filename" [,device]`
**Type**: Statement (Immediate mode)
**Description**: Verifies a program on disk matches the one in memory.
**Example**:
```basic
VERIFY "PROGRAM",8
```

### WAIT
**Syntax**: `WAIT address, value [,mask]`
**Type**: Statement
**Description**: Waits until a memory location matches the specified condition.
**Example**:
```basic
WAIT 53273,255
```

## BASIC 3 Extensions

### BASIC2 / BASIC3.5
**Syntax**: `BASIC2` or `BASIC3.5`
**Type**: Statement (always enabled)
**Description**: Selects BASIC 2 compatibility mode or enables the BASIC 3.5 / 7 structured-token extension mode.

### BASIC()
**Syntax**: `BASIC()`
**Type**: Function (always enabled)
**Description**: Returns the active BASIC dialect. No expression argument is accepted.

### COMPILE
**Syntax**: `COMPILE ["filename" [,device]]`
**Type**: Statement (Immediate mode)
**Description**: Compiles the current stored BASIC program to an independent, stock-loadable, source-free native PRG. With no filename, the output name is `COMPILED`. With no device, output uses the current disk device, which follows stock KERNAL `fa` at `$BA` and may be changed by DOS wedge commands such as `@10`. The exported program includes its required runtime and a standalone direct-mode environment supporting simple `?`/`PRINT` variable or array-element inspection, valid `CONT`, `RUN`, `LOAD`, `SAVE`, `VERIFY`, `CLR`, and the DOS wedge commands. `LIST` in the standalone environment may show only `2026 SYS2061`.

### FPMODE0 / FPMODE1
**Syntax**: `FPMODE0` or `FPMODE1`
**Type**: Statement (always enabled)
**Description**: Disables or enables IEEE-style floating-point semantics.

### FPMODE()
**Syntax**: `FPMODE()`
**Type**: Function (always enabled)
**Description**: Returns the current IEEE mode. No expression argument is accepted.

## BASIC 3.5 / 7 Extensions

### DO...LOOP
**Syntax**: See DO statement above
**Type**: Statement (BASIC 3.5+)
**Description**: Structured looping construct.

### ELSE
**Syntax**: See IF statement above
**Type**: Statement (BASIC 3.5+)
**Description**: Alternative branch for IF.

### EXIT
**Syntax**: See EXIT statement above
**Type**: Statement (BASIC 3.5+)
**Description**: Exits the innermost active `DO` loop.

### LOOP
**Syntax**: See DO statement above
**Type**: Statement (BASIC 3.5+)
**Description**: Ends a DO...LOOP block. Safe bare `LOOP` backedges can be lowered directly by the compiler; conditional `LOOP WHILE` and `LOOP UNTIL` forms remain on the generic condition path unless descriptor-gated native lowering is proven safe.

### UNTIL
**Syntax**: See DO statement above
**Type**: Keyword (BASIC 3.5+)
**Description**: Condition for DO...LOOP termination.

### WHILE
**Syntax**: See DO statement above
**Type**: Keyword (BASIC 3.5+)
**Description**: Condition for DO...LOOP continuation.

## IEEE 754 Functions

IEEE 754 functions are available when `FPMODE1` is set. The `FPMODE1`,
`FPMODE0`, and `FPMODE()` gateway forms are always enabled, including in the
default BASIC 2 startup mode.

### FPMODE0
**Syntax**: `FPMODE0`
**Type**: Statement (always enabled)
**Description**: Disables IEEE 754 floating-point mode.
**Example**:
```basic
FPMODE0
```

### FPMODE1
**Syntax**: `FPMODE1`
**Type**: Statement (always enabled)
**Description**: Enables IEEE 754 floating-point mode.
**Example**:
```basic
FPMODE1
```

### FPMODE()
**Syntax**: `FPMODE()`
**Type**: Function (always enabled)
**Description**: Returns the current IEEE 754 mode, `1` when enabled or `0` when disabled. This resident query intentionally accepts no expression argument.
**Example**:
```basic
FPMODE1          ' Enable IEEE mode
PRINT FPMODE()   ' Output: 1
```

### FPFLAGS
**Syntax**: `FPFLAGS` or `FPFLAGS()`
**Type**: Function
**Description**: Returns current IEEE exception flags.

### FPCLR
**Syntax**: `FPCLR`, `FPCLR()`, or `FPCLR(flags)`
**Type**: Function / direct statement
**Description**: Clears IEEE exception flags. With no argument, clears all flags; with a mask, clears only the selected flags.

### FPSET
**Syntax**: `FPSET(flags)` or `FPSET flags`
**Type**: Function / direct statement
**Description**: Sets IEEE exception flags selected by the mask.

### FPTEST
**Syntax**: `FPTEST(flags)` or `FPTEST flags`
**Type**: Function / direct statement
**Description**: Tests IEEE exception flags.

### FPTTEST
**Syntax**: `FPTTEST(flags)` or `FPTTEST flags`
**Type**: Function alias
**Description**: Compatibility spelling accepted by the tokenizer. It is equivalent to `FPTEST(flags)` and uses the same `$FE,$3E` token.

### ISNAN
**Syntax**: `ISNAN(value)`
**Type**: Function
**Description**: Returns -1 if value is NaN, 0 otherwise.

### ISSNAN
**Syntax**: `ISSNAN(value)`
**Type**: Function
**Description**: Returns -1 if value is signaling NaN.

### ISINF
**Syntax**: `ISINF(value)`
**Type**: Function
**Description**: Returns -1 if value is infinite.

### ISFIN
**Syntax**: `ISFIN(value)`
**Type**: Function
**Description**: Returns -1 if value is finite.

### ISNORM
**Syntax**: `ISNORM(value)`
**Type**: Function
**Description**: Returns -1 if value is normalized.

### ISZERO
**Syntax**: `ISZERO(value)`
**Type**: Function
**Description**: Returns -1 if value is zero.

### SGNBIT
**Syntax**: `SGNBIT(value)`
**Type**: Function
**Description**: Returns sign bit.

### ISUNORD
**Syntax**: `ISUNORD(value)`
**Type**: Function
**Description**: Returns -1 if value is unordered.

### COPYSGN
**Syntax**: `COPYSGN(value1, value2)`
**Type**: Function
**Description**: Copies sign from value2 to value1.

### TOTALORDER
**Syntax**: `TOTALORDER(value1, value2)`
**Type**: Function
**Description**: Compares with total ordering.

### BIN32$
**Syntax**: `BIN32$(value)`
**Type**: Function
**Description**: Converts to a printable big-endian IEEE 754 single-precision hex string, rounded in the current FP mode. For example, `BIN32$(1)` returns `$3F800000`.

### VAL32
**Syntax**: `VAL32(string)`
**Type**: Function
**Description**: Converts an eight-digit big-endian IEEE 754 single-precision hex string, with or without a leading `$`, back to a BASIC numeric value.

### FMA
**Syntax**: `FMA(a, b, c)`
**Type**: Function
**Description**: Fused multiply-add: (a * b) + c.

### REMAIN
**Syntax**: `REMAIN(a, b)`
**Type**: Function
**Description**: IEEE remainder operation.

### MIN
**Syntax**: `MIN(a, b)`
**Type**: Function
**Description**: Returns minimum of two values.

### MAX
**Syntax**: `MAX(a, b)`
**Type**: Function
**Description**: Returns maximum of two values.

### SCALB
**Syntax**: `SCALB(value, exp)`
**Type**: Function
**Description**: Scales value by 2^exp.

### LOGB
**Syntax**: `LOGB(value)`
**Type**: Function
**Description**: Returns unbiased exponent.

### MANT
**Syntax**: `MANT(value)`
**Type**: Function
**Description**: Returns mantissa.

### RINT
**Syntax**: `RINT(value)`
**Type**: Function
**Description**: Rounds to integer.

### NEXTUP
**Syntax**: `NEXTUP(value)`
**Type**: Function
**Description**: Returns next larger representable value.

### NEXTDOWN
**Syntax**: `NEXTDOWN(value)`
**Type**: Function
**Description**: Returns next smaller representable value.

## Disk Wedge Commands

These are immediate-mode conveniences handled by the direct runtime. Output is
written to the current text screen with no special screen-state restoration.

### $ (Directory)
**Syntax**: `$`
**Type**: Immediate command
**Description**: Displays the current disk directory without loading it over the stored BASIC program. `@$` is equivalent.
**Example**:
```basic
$
```

### / (Load Alias)
**Syntax**: `/filename` or `/"filename"`
**Type**: Immediate command
**Description**: Loads the named program from the current disk device with absolute PRG load semantics equivalent to `LOAD "filename",device,1`.
**Example**:
```basic
/"PROGRAM"
```

### @ (Command)
**Syntax**: `@`, `@8`, `@9`, `@10`, `@11`, or `@command`
**Type**: Immediate command
**Description**: Reads the disk error channel, selects the current disk device, or sends a disk command and reports status. Destructive commands require confirmation.
**Example**:
```basic
@
```

### ! (SEQ Stream)
**Syntax**: `!filename` or `!"filename"`
**Type**: Immediate command
**Description**: Opens the named SEQ file and streams PETSCII text to the current screen. STOP aborts output and closes the file. Screen and color changes made by the stream remain visible.
**Example**:
```basic
!README
!"README,S"
```

## Operators Summary

| Category | Operators |
|----------|-----------|
| Arithmetic | `+`, `-`, `*`, `/`, `^` |
| Comparison | `=`, `<>`, `<`, `>`, `<=`, `>=` |
| Logical | `AND`, `OR`, `NOT` |
| String | `+` (concatenation) |

## See Also

- BASIC V3 User Manual: `docs/MANUAL.md`
- Requirements: `REQUIREMENTS.md`
