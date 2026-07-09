# Zero-Page Allocation Design

## Principle

Zero page is a scheduled resource, not a collection of convenient global
addresses. Every byte must have a declared owner, size, alignment, lifetime,
alias policy, and interaction with interrupts and ROM calls.

Zero-page allocation uses declared lifetimes and graph coloring. The build owns
the analyzer; its output is a required, validated artifact — not a comment or
hand-maintained address table.

## Authoritative ROM Reference

The stock BASIC V2 and KERNAL source is available at:

`C:\Users\me\Documents\Coding Projects\c64rom`

Useful inputs include:

- `kernal/declare.s`
- `basic/core/declare.s`
- `docs/KERNEL_ZP.md`
- `docs/BASIC_ZP.md`
- `docs/KERNEL_API.md`
- `debug/c64rom.labels`

These files provide labels, resolved addresses, and source-derived call paths.
The generated reports are useful seeds, but surprising results must be checked
against the assembly source. For example, stock `UDTIM` directly updates
`time` and `stkey`.

## Allocation Manifest

Zero-page declarations are generated from a structured manifest. Each entry
contains:

```text
name
size
alignment
owner module
lifetime domain
entry points that require it
calls made while live
IRQ/NMI visibility
KERNAL/BASIC ROM call domains
allowed aliases
preserve or clobber policy
```

Assembly imports generated symbols. It does not assign new literal zero-page
addresses in source.

## Lifetime Domains

Initial domains include:

- CPU port, always live;
- IRQ/NMI state, concurrently live with foreground code;
- geoRAM call gate and nested context;
- runtime ABI call;
- expression evaluation;
- numeric FAC/ARG and extended math;
- statement-local scratch;
- tokenizer/lexer;
- parser/compiler phase;
- editor foreground;
- loader/install only;
- error unwind;
- STOP/CONT resumable state;
- KERNAL bridge call.

Domains are not assumed mutually exclusive. A parser can call math; editor
submission can invoke the tokenizer; geoRAM code can call a resident runtime
helper; an IRQ can interrupt any IRQ-safe foreground domain.

## Interference Graph

Each allocation or contiguous range is a node. Two nodes receive an edge when:

- their lifetimes overlap;
- one is live across a call that clobbers the other;
- one is foreground-visible and the other is IRQ/NMI-visible;
- a nested call can require both;
- an error or callback can observe both;
- an explicit alias prohibition applies.

Colors are concrete aligned address ranges. Multi-byte nodes require contiguous
colors. The allocator may overlay noninterfering domains, such as install-only
scratch and post-install runtime scratch.

An alias is legal only when represented in the manifest. Accidental numeric
overlap is a build failure even if current tests happen not to exercise both
paths.

## KERNAL and IRQ Constraints

`$00-$01` are permanently reserved for the 6510 CPU port.

The always-concurrent IRQ set includes at least:

- `$91` `stkey`;
- `$A0-$A2` `time`;
- `$C5` `lstx`;
- `$C6` `ndx`;
- `$CB` `sfdx`;
- `$F5-$F6` `keytab`.

The exact set is generated from the chosen IRQ implementation and checked
against `c64rom`. Project IRQ-private pointers must also interfere with every
foreground lifetime.

Foreground KERNAL bridges add call-scoped interference sets. Examples:

- `SETNAM`: `$B7`, `$BB-$BC`;
- `SETLFS`: `$B8-$BA`;
- current disk device: `$BA` `fa`, shared with stock `SETLFS`, `LOAD`, and
  `SAVE`, and updated by Compiler 2 DOS wedge device selection and defaulted
  `COMPILE`;
- `SETTIM`/`RDTIM`: `$A0-$A2`;
- `GETIN`: `$99`, `$C6` for keyboard input;
- `STOP`: `$91`, `$C6`, plus the `CLRCHN` path when STOP is pressed;
- `SCNKEY`: `$C5-$C6`, `$CB`, `$F5-$F6`;
- `LOAD`, `SAVE`, and serial/channel calls: broad device-dependent KERNAL
  workspace as generated from the selected ROM path.

Code may reuse a KERNAL byte outside the relevant call/IRQ lifetime, but it may
not keep a value there across the call unless the source-derived contract proves
the byte preserved.

Because `$BA` is persistent user-visible file-command state in Compiler 2, it
must be modeled as live across direct commands that rely on the current disk
device. It cannot be used as unrelated scratch while that state is valid.

## Coloring Policy

The allocator should prefer:

1. fixed architectural and IRQ reservations;
2. stable runtime ABI ranges;
3. frequently used two-byte pointers;
4. larger math ranges;
5. phase-local overlays;
6. loader-only overlays.

The goal is minimum total occupied range without creating fragile aliases. A
slightly larger coloring is preferable when it removes a complex lifetime
exception or callback dependency.

Graph coloring with contiguous/aligned multi-byte ranges is a build-time
constraint problem and a purely greedy allocator can falsely report failure or
produce avoidable fragmentation. The generator therefore uses deterministic
DSATUR-style ordering with interval placement and bounded backtracking. It must
emit a useful unsatisfied-constraint explanation if no placement is found.
Build time is secondary to correctness here; this algorithm is never executed
on the C64.

## Generated Outputs

Every build emits:

- `build/zp_symbols.inc`;
- `build/zp_allocation.json`;
- `build/zp_allocation.md`;
- `build/zp_interference.dot`;
- a list of unused bytes and contingency ranges;
- the source reason for every interference edge;
- the maximum simultaneous live-byte count by domain.

The linker map is checked against the generated allocation. Documentation must
not contain a hand-maintained address table presented as current truth.
`build/MAP.md` includes a sorted table view of the exact allocation, fixed
stock reservations, legal aliases, gaps, and contingency bytes for the current
build; it is generated from `zp_allocation.json`, never maintained separately.

## Validation

Static tests verify no undeclared literal ZP operands, overlaps, or missing
contracts. Local-emulator tests poison non-live zero page on entry and verify
that public routines touch only declared bytes.

Nested-call tests combine parser, math, KERNAL bridge, geoRAM re-entry, and
error unwind. VICE tests verify the IRQ-owned bytes while long compiler and
math routines execute with interrupts enabled.

Any new zero-page use requires a manifest change and a regenerated graph. A
comment alone is not allocation.
