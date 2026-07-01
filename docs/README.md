# Documentation Map

## Normative

These documents define Compiler 2:

- `../REQUIREMENTS.md`
- `../DESIGN2.md`
- `COMPILER_ARCHITECTURE.md`
- `GEORAM_BANKING.md`
- `ZERO_PAGE.md`
- `KERNAL_ABI.md`
- `BASIC_COMPATIBILITY_LIMITS.md`
- `LOOP_OPTIMIZATION.md`
- `INCREMENTAL_COMPILATION.md`
- `COMPILE_EXPORT.md`
- `DOS_WEDGE.md`
- `IEEE754.md`
- `MEMORY_BUDGETS.md`
- `EDITOR.md`
- `TESTING.md`
- `BUILD.md`
- `GENERATED_REFERENCE.md`
- `VICE_TOOLS.md`
- `GRAPHICS_MEMORY.md`
- `GEORAM_LOADER_DESIGN.md`
- `TRACEABILITY.md`

`REQUIREMENTS.md` has priority when documents disagree.

## Language References

These references describe the intended language and user surface. They must be
reconciled with the requirements as implementation proceeds:

- `KEYWORDS.md`
- `MANUAL.md`
- `CANONICAL_TESTS.md`

`REQUIREMENTS.md` is the complete language-compatibility authority. If
`KEYWORDS.md`, `MANUAL.md`, or `CANONICAL_TESTS.md` omits or contradicts a
stock BASIC V2 requirement, the requirement still applies and the reference
document must be corrected.

An entry described as planned is not implemented merely because it appears in a
reference document.

## Generated Build References

Every build creates these non-normative, current-build references:

- `build/API.md` — production callable entries and complete calling
  conventions;
- `build/MAP.md` — CPU, zero-page, segment, geoRAM, arena, graphics, vector,
  standalone, dynamic, and free memory summaries.

Their schema and generation rules are in `GENERATED_REFERENCE.md`. They are
derived from validated build artifacts, are safe to delete with `build/`, and
must not be edited by hand or treated as inputs to the next build.

## Legacy Implementation References

These files came from or summarize the legacy compiler and contain useful
formats, terms, and lessons. They are not Compiler 2 architecture:

- `ir.md`
- `save_format.md`

Do not copy fixed addresses, old memory regions, fallback machinery, or
generated XIP assumptions from them without a new requirement and design
review.

Exception: trig, transcendental, and IEEE extension math should reuse the
legacy algorithms and source where practical. Their numerical calculations
were already proven with Python proxies and validated for accuracy. Even in
that case, the legacy memory map and fixed ZP/address choices are guidance
only; Compiler 2 generated manifests and ABI remain authoritative.

The former full-compiler specification was superseded and removed. The old XIP
and memory-map documents were intentionally not copied. The useful indexed
geoRAM call concept has been re-derived in `GEORAM_BANKING.md`.

## External References

Stock BASIC V2 and KERNAL behavior, symbols, and zero-page use come from:

`C:\Users\me\Documents\Coding Projects\c64rom`

The legacy implementation and its tests remain available at:

`C:\Users\me\Documents\Coding Projects\compiler`
