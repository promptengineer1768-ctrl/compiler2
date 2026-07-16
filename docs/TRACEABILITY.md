# Requirements Traceability

Compiler 2 uses EARS-style requirement statements to connect normative
requirements, design elements, implementation components, and tests.

`../REQUIREMENTS.md` remains the authority for required behavior. This document
defines the trace format and generated matrix rules.

## EARS Forms

Trace records should use one of these EARS forms:

- **Ubiquitous:** The system shall `<required behavior>`.
- **Event-driven:** When `<trigger>`, the system shall `<required behavior>`.
- **State-driven:** While `<state>`, the system shall `<required behavior>`.
- **Optional-feature:** Where `<feature>` is enabled, the system shall
  `<required behavior>`.
- **Unwanted behavior:** If `<fault or invalid condition>`, the system shall
  `<required response>`.

Each EARS statement must be testable, externally meaningful, and tied to a
stable requirement ID from `REQUIREMENTS.md`.

## Trace Record

Each trace record contains:

- requirement ID, such as `R6.2` or a stable matrix suffix like
  `R2.1-PHASE1-LOOP-JIFFY`;
- EARS statement;
- requirement source section;
- design element or document section;
- implementation component or planned component;
- test nodes by layer: unit, integration, functional, E2E, system contract, and
  hardware/VICE where applicable;
- reference fixture provenance when stock semantics are involved;
- status: planned, implemented, unsupported, not-applicable, or passing;
- last passing build or fixture fingerprint when available.

Generated trace data may be stored as JSON, CSV, Markdown, or all three, but
`requirements_matrix.json` is the machine-readable build artifact.

`build/API.md` and `build/MAP.md` are also generated current-build views.
Their generation and consistency requirements map to named system contract
tests, but the documents themselves are not requirement or trace-record
inputs; generated output must not become a circular authority.

`manifests/traceability.json` must contain exactly one section-level record for
every numbered requirement heading in `REQUIREMENTS.md` after the status
section and every `RREU-*` heading in `REU_REQUIREMENTS.md`. More granular
records may be introduced only by adding stable normative requirement IDs; ad
hoc trace-only IDs are rejected. Planned product behavior remains `planned`
even when its design and intended test nodes are already recorded.

## Example

```text
ID: R6.2-STOCK-C64-BUDGET
EARS: When COMPILE exports a source-free program, the system shall reject the
      export unless the loaded PRG image fits within $0801-$CFFF on a stock C64
      without geoRAM.
Design: docs/COMPILE_EXPORT.md#stock-memory-budget
Tests: system contract PRG range check; E2E stock-C64 load/run smoke
Status: planned
```

```text
ID: R6.2-STANDALONE-COMMANDS
EARS: When a source-free compiled export is in direct mode, the system shall
      support RUN, LOAD, SAVE, VERIFY, CLR, and every documented DOS wedge
      command using the stock KERNAL current-device state.
Design: docs/COMPILE_EXPORT.md#standalone-direct-mode;
        docs/DOS_WEDGE.md
Tests: unit command-dispatch cases; integration current-device cases;
       E2E exported-PRG command and DOS-wedge cases on stock C64 VICE
Status: planned
```

## Build Rules

The build must fail when:

- an implemented requirement lacks a trace record;
- a trace record points to a missing requirement, design section, or test node;
- an implemented keyword lacks a critical language E2E case;
- a stock-compatible critical language case lacks reference provenance;
- the generated requirements matrix is stale relative to source trace inputs.

Validation also rejects duplicate or unknown requirement IDs, missing source,
design, implementation, or fixture-provenance paths, invalid EARS statements,
unresolved test nodes, and stale forward or inverse generated mappings.

Static source-pattern tests do not by themselves complete a requirement. At
least one test node must prove the behavior at the appropriate fidelity layer.
