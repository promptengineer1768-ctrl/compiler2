# Loop Optimization Design

## Rule

Every loop has a correct generic implementation. Fast paths are selected only
when compiler-built descriptors prove that the shorter implementation has the
same observable behavior.

Loop lowering is also a performance-critical part of the design. The Phase 1
bootstrap benchmark:

```basic
10 B=TI
20 FORX=1TO1000
30 NEXT
40 A=TI
50 PRINTA-B
```

must complete in less than 60 C64 jiffies when compiled. The direct
`FOR`/`NEXT` path therefore has to avoid stock-interpreter-style repeated
statement scanning, repeated keyword lookup, and unnecessary floating runtime
dispatch when descriptor facts prove the loop can use a narrower path.

## Stable Variable Descriptors

A scalar variable descriptor is a 12-byte `VD` record. It contains a typed
kind (`int`, `float`, or `string`), a non-zero descriptor generation, a storage
policy, and either a direct RAM cell pointer or an arena id/generation/page/
offset handle. Reserved bytes must be zero. The runtime rejects malformed
records, stale arena generations, unsupported storage policies, and kind
mismatches before reading or writing a payload.

Compiled code may cache a direct cell only while the descriptor generation and
banking facts remain valid. Arena-backed cells must be reselected through the
arena API before access. String variables store a string descriptor
`payload_ptr:u16,length:u8`; storing a string updates that descriptor rather
than copying the payload bytes.

## Loop Descriptors

Each statement participating in a loop has a descriptor containing:

- kind: `FOR`, `NEXT`, bare `DO`, pretest `DO`, posttest `LOOP`, or exit;
- matching partner statement;
- body and exit targets;
- source/condition offset;
- variable descriptor;
- width and banking policy;
- literal start, limit, and step when proven;
- condition operator and operands;
- fallback flags;
- read, write, escape, and invalidation masks.

Unknown fields use explicit invalid sentinels. Zero is never overloaded to mean
both a valid value and "not known."

Descriptors are rebuilt for each source generation and cleared by `NEW`, `CLR`,
dialect changes, incompatible `CONT`, and failed compilation.

## FOR/NEXT Fast Path

A direct integer path is eligible only when:

- start, limit, and step have proven signed INT2 values;
- step is nonzero;
- every value through `end + step` can be represented by the loop variable's
  assigned numeric type without changing the generic loop result;
- the variable descriptor resolves to a stable accessible cell;
- body analysis finds no aliasing write, `POKE`, `SYS`, callback, DIM/CLR, or
  bank change that can invalidate the cell;
- overflow and promotion behavior match the generic path;
- `NEXT` names the same variable or follows stock unnamed-`NEXT` rules;
- nested-loop and error-unwind metadata is valid.

The emitted path initializes the real variable cell once, compares according to
step sign, updates the cell directly, and branches to a resolved target. It
does not invent a separate loop-counter type: stores and visible reads respect
the descriptor's assigned variable type. `INT1` loop variables are
sign-extended for mixed comparisons, `INT2` variables use signed 16-bit
ordering, `INT3` variables use unsigned 16-bit ordering, and `FLOAT` variables
use the packed numeric runtime. If any operation would require behavior outside
those proven facts, the fast path is ineligible.

Any failed condition selects the generic frame-based runtime helper.

## DO/LOOP Fast Paths

Safe bare `DO`/`LOOP` emits a direct native backedge.

Simple truthiness or scalar comparisons may emit a native pretest/posttest:

- `DO WHILE A`
- `DO UNTIL A`
- `DO WHILE A<10`
- `LOOP WHILE A<B`
- corresponding `UNTIL` inversions

The condition descriptor records polarity explicitly. `UNTIL` is not
implemented by scattered branch inversions.

Complex expressions, function calls, mutable aliases, or invalidated operands
use generic expression evaluation.

`EXIT DO` and `EXIT FOR` use resolved descriptor targets only when nesting is
proven. Otherwise they use the generic control stack or report the stock error.

## Invalidation Barriers

The optimizer treats these as barriers unless a narrower effect is proven:

- `POKE` into runtime, descriptor, banking, or arena control storage;
- `SYS` and `USR`;
- KERNAL or user callbacks;
- `CLR`, `NEW`, `RUN`, and program replacement;
- dynamic array allocation or redimensioning;
- unknown string compaction side effects;
- error paths that can expose intermediate variable state.

Dirty masks identify exactly which descriptor facts a loop body changes. The
code generator asks one eligibility predicate; it does not reproduce partial
checks in several emitters.

## Analysis Complexity

Loop invalidation and read/write/escape summaries are computed once in a
bottom-up pass over the typed IR and cached by source/IR generation. A parent
loop merges child summaries; it does not rescan each nested body independently.
Eligibility predicates consume those summaries, and emitters never rerun body
analysis. This keeps analysis approximately linear in IR size plus descriptor
edges and avoids the quadratic behavior of rescanning a large nested body for
every loop and every emitter.

Build/debug timing reports separate summary construction, eligibility checks,
and emission so a lost cache or accidental body rescan is visible.

The current compact typed-IR boundary uses four-byte records. For optimizer
analysis, loop records carry the proven lowering facts, dirty mask, and
alias/escape mask in their three payload bytes; bit 7 of the fact byte marks a
long loop requiring bounded STOP polling. Non-loop records contribute their
dirty and alias payload bytes to the enclosing summary. The optimizer scans
the record stream once, publishes at most four four-byte summaries
(`facts`, `dirty`, `alias`, `metadata`) only after the scan succeeds, and reuses
them only for an exact 16-bit IR-generation match. Capacity failure leaves the
previous generation's published table intact.

## STOP, Timer, and Side Effects

Timer advancement is IRQ-owned. Fast loops do not synthesize jiffy ticks.

Long loops must reach a bounded statement/iteration boundary that polls the
bank-safe STOP bridge. The polling cadence may be amortized, but STOP behavior
and final visible variable state must match the generic path.

## Testing

Each optimized form is differential-tested against:

- the generic path in the local emulator;
- stock BASIC V2 where the syntax is stock;
- VICE for IRQ, STOP, timer, and banking behavior.

Tests cover positive/negative steps, zero step, empty loops, integer width
edges, promotion, nested loops, unnamed and named `NEXT`, modified loop
variables, arrays, `POKE`, `SYS`, errors, STOP/CONT, and every `WHILE`/`UNTIL`
polarity.

Static tests prove descriptor completeness and that every fast-path branch has
an explicit fallback. Benchmark tests run only after semantic tests pass.
Performance tests report CPU cycles for stock-reference and compiled runs. C64
BASIC V2 comparisons use stock C64 BASIC V2; BASIC 3.5 comparisons use stock
Plus/4 BASIC 3.5 and compare cycles rather than elapsed wall time.
