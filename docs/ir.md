# Compiler IR Design

Compiler 2 lowers canonical tokenized BASIC source through versioned,
inspectable compiler artifacts before emitting native 6502 code. This document
describes the required IR shape; it does not claim any Compiler 2 source files
already exist.

## Authority

`../REQUIREMENTS.md` defines the required compiler pipeline and acceptance
criteria. `../DESIGN2.md` and `COMPILER_ARCHITECTURE.md` define the high-level
architecture. If this note conflicts with either document, the higher-level
document wins.

## Required Boundaries

The IR pipeline must preserve the boundaries required by `REQUIREMENTS.md`:

1. canonical tokenized source;
2. lexical and statement records;
3. symbols and variable descriptors;
4. control-flow and loop descriptors;
5. typed intermediate representation;
6. optimized intermediate representation;
7. emitted code, relocations, and runtime dependencies;
8. installed compiled image.

Each boundary has a format version, generation, source fingerprint, and host
test serialization. Failed compilation reports the failing phase, source line,
and BASIC-compatible error class.

## IR Contents

The typed IR must be able to represent:

- statement boundaries and source-line mapping;
- expression trees with BASIC V2-compatible coercion and error behavior;
- scalar, array, and string descriptor references;
- string payload storage class where required by runtime/export behavior;
- branch, subroutine, `DATA`, and loop metadata;
- `FOR`/`NEXT` and BASIC 3.5 structured-loop descriptors through the same loop
  model;
- runtime helper dependencies and ABI version requirements;
- relocation sites, exported debug/test labels, and direct-shell inspection
  metadata for source-free COMPILE exports.

Unsupported behavior must fail visibly during a documented phase. It must not
be simulated by host tooling or routed through an interpreter fallback.

## Emission

Production emission is native 6502 assembled with `ca65` and linked with
`ld65`. Host tools may generate manifests, validate artifacts, replay phase
serializations, and package outputs, but they are not a second production
compiler backend.
