# Canonical Reference Fixtures

Compiler 2 uses versioned VICE observations as semantic reference fixtures.
This document summarizes the fixture policy; `../REQUIREMENTS.md` and
`TESTING.md` are authoritative if they conflict with this note.

## Scope

Critical language E2E cases require reference provenance:

- BASIC V2 cases use stock C64 BASIC V2 and KERNAL under VICE C64 emulation.
- BASIC 3.5 cases use stock Plus/4 BASIC V3.5 under VICE Plus/4 emulation.
- Compiler 2-only BASIC 3 and IEEE extension behavior uses the normative
  Compiler 2 specification, with inherited operands and errors compared against
  the applicable stock reference where possible.

Reference fixtures record the source text, execution mode, reference machine,
dialect, VICE version, ROM identity, raw observation, normalized result, and
regeneration fingerprint.

The checked-in stock corpus currently contains:

- 95 C64 BASIC V2 `screen-v1` captures: 41 immediate mode and 54 program mode;
- 40 Plus/4 BASIC V3.5 `screen-v1` captures: 8 immediate mode and 32 program
  mode.

Both corpora record VICE 3.10 and exact SHA-256 identities for every selected
ROM. Offline fixture contracts recompute each regeneration fingerprint and
replay normalization from `raw_screen` plus `source_text`; catalog placeholders
are forbidden in both stock buckets.

## Regeneration Policy

Stock BASIC V2 and implemented BASIC 3.5 fixtures are normally generated once
because the selected ROM semantics are immutable. They must not be regenerated
merely because Compiler 2 changes.

New fixture cases may be generated when new edge cases are added. Existing
fixtures may be regenerated only for a reviewed oracle, ROM-identity, generator,
normalization, or fixture-schema correction, and the reason must be recorded in
the change.

## Storage and Debug Artifacts

Temporary VICE captures, one-off reproducers, generated listings, and diagnostic
outputs belong under `debug/`. Release builds and tests must not depend on
files under `debug/`.

Fixture-generation tools and stored fixture locations are implementation
details of the test harness, but the generated requirements matrix must map
each critical language case back to its requirement ID and reference
provenance.

## Offline Verification

Normal development verification must validate the immutable checked-in
captures without launching VICE:

```powershell
python -m pytest tests/fixtures/reference -v
```

The `--generate-reference basicv2` and `--generate-reference basicv35` commands
are capture workflows, not routine verification commands. Use them only under
the reviewed regeneration policy above.
