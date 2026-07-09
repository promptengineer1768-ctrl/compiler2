# IEEE 754 Profile

IEEE mode follows IEEE 754:2019 semantics except that Compiler 2 uses the stock
BASIC V2-compatible internal floating layout and stock-compatible formatting.

`FPMODE1` enables IEEE mode. `FPMODE0` restores stock (non-IEEE) numeric mode.
`FPMODE()` returns the active mode and is independent of the BASIC dialect
selected by `BASIC2` or `BASIC3.5`.

## Accuracy

Core arithmetic operations `+`, `-`, `*`, `/`, and `SQR` must be exactly
rounded to the Compiler 2 destination format according to the active rounding
mode.

Trigonometric, logarithmic, exponential, power, and other transcendental
functions must be within 2 ULP over their documented domain. Slow routines may
be expansion-native (geoRAM XIP or REU overlay).

## Implementation sources

Implementations may adopt proven external algorithms for trig, transcendental,
and IEEE extensions when they meet the accuracy bounds and generated ABI.
Placement always uses Compiler 2 manifests, generated zero-page allocation,
dual expansion policy, and routine contracts — never external fixed addresses.

## Required Surface

`docs/MANUAL.md` and `REQUIREMENTS.md` define the required IEEE surface:

- mode and flags: `FPMODE`, `FPFLAGS`, `FPCLR`, `FPSET`, `FPTEST`, `FPTTEST`;
- classification: `ISNAN`, `ISSNAN`, `ISINF`, `ISFIN`, `ISNORM`, `ISZERO`,
  `SGNBIT`, `ISUNORD`;
- operations: `COPYSGN`, `TOTALORDER`, `FMA`, `REMAIN`, `MIN`, `MAX`, `SCALB`,
  `LOGB`, `MANT`, `RINT`, `NEXTUP`, `NEXTDOWN`;
- interchange helpers: `BIN32$`, `VAL32`;
- constants and printed values: `INF`, `-INF`, `NAN`, `SNAN`.

Flag bits are invalid operation, divide by zero, overflow, underflow, and
inexact. Rounding modes include ties-to-even, toward zero, toward positive
infinity, toward negative infinity, and ties-away.
