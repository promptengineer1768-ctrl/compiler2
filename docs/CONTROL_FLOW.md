# Control-Flow Runtime

Compiled control flow uses one tagged, bounded runtime stack. Every frame is a
tag byte followed by a 16-bit descriptor pointer. FOR, DO, and GOSUB frames
therefore cannot be confused during NEXT, LOOP, EXIT, or RETURN.

## FOR descriptor

The FOR descriptor stores the loop-control operands as signed 16-bit INT2
values: start, limit, and step. The step must be nonzero. This matches the
compiled-loop control contract even when the loop variable itself is assigned a
different numeric representation.

The descriptor also records the assigned loop-variable type. That type uses the
runtime tags `FLOAT=0`, `INT1=1`, `INT2=2`, and `INT3=3`, but it is the
variable payload type, not a widening of the FOR start/limit/step fields. A
fully implemented FOR loop initializes, increments, stores, and exposes the
real variable through that recorded type:

- `INT1` variables receive signed 8-bit values and are sign-extended before
  comparison with wider operands.
- `INT2` variables receive signed 16-bit values directly.
- `INT3` variables receive unsigned 16-bit values where the value domain is
  nonnegative, and unsigned comparisons must not interpret bit 15 as a sign.
- `FLOAT` variables use the normal five-byte packed arithmetic path.

The compiler may select an integer-specialized loop only when it can prove that
the start value and every reachable value through `end + step` fit the selected
variable type and that the signed INT2 FOR operands can express the control
range exactly. Otherwise it emits the generic path. Generic compact integer
frames may promote or widen the variable representation when required, but the
loop-control limit and step fields remain signed INT2 values.

Numeric comparison is a general runtime contract, not a loop-only rule. Mixed
signed integer comparisons sign-extend narrower signed operands before
ordering; unsigned INT3 comparisons use unsigned ordering; mixed signed and
unsigned operands promote to a representation that preserves BASIC-visible
ordering before returning the Boolean result.

## DO and continuation descriptors

A DO descriptor is `D`, flags, and a 16-bit backedge. Flag bit 0 means a
condition is present and bit 1 selects UNTIL instead of WHILE. Bare loops always
continue until EXIT.

A continuation descriptor is `C`, generation, resume PC, saved stack byte
count, and the tagged control-stack image. STOP publishes the descriptor and
CONT accepts only the same handle and generation before restoring the complete
stack. END invalidates continuation state and the complete tagged stack, calls
the unified graphics exit, then selects the development editor READY transition
or the standalone inspection READY loop from its runtime-profile input.
