# IEEE 754 Profile

IEEE mode follows IEEE 754:2019 semantics except that Compiler 2 uses the stock
BASIC V2-compatible internal floating layout and legacy-compatible formatting.

`FPMODE1` enables IEEE mode. `FPMODE0` restores legacy mode. `FPMODE()` returns
the active mode and is independent of the BASIC dialect selected by `BASIC2` or
`BASIC3.5`.

## Accuracy

Core arithmetic operations `+`, `-`, `*`, `/`, and `SQR` must be exactly
rounded to the Compiler 2 destination format according to the active rounding
mode.

Trigonometric, logarithmic, exponential, power, and other transcendental
functions must be within 2 ULP over their documented domain. Slow routines may
be geoRAM-native.

## Legacy Math Reuse

The legacy project at `C:\Users\me\Documents\Coding Projects\compiler` is the
preferred starting point for trig, transcendental, and IEEE extension
implementation. Reuse its algorithms and ca65 source code where practical,
because those calculations were already exercised through Python proxy models
and validated for the documented accuracy targets.

Compiler 2 is not required to preserve the legacy memory map, fixed addresses,
or zero-page layout. Treat the legacy placement as guidance only: port useful
math kernels to the Compiler 2 routine contracts, generated zero-page
allocation, geoRAM placement, and manifest-driven ABI.

## Required Surface

The inherited manual defines the required IEEE surface:

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
