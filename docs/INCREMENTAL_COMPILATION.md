# Incremental Compilation

Compiler 2 compiles as the user edits.

Ordinary numbered-line entry should complete in about 0.5 seconds or less in
the target development environment. This is a responsiveness target rather than
a hard correctness gate, but builds and tests should report line-entry latency
so slow tokenization, dependency repair, or code publication is visible before
the editor becomes frustrating to use.

Numbered program-line entry is transactional:

1. capture the editor line;
2. tokenize into scratch storage;
3. validate syntax and dialect rules;
4. compile the line into a scratch compiled record;
5. update dependency fingerprints;
6. publish source and compiled records together.

If any step fails, the previous stored line and published compiled cache remain
valid. A deleted line removes its source record and invalidates dependent
compiled records in one generation update.

Immediate mode uses the same machinery. A direct executable command is wrapped
as a temporary program, compiled fully, executed, and discarded. That gives the
project one compiler path for stored execution, direct execution, and per-line
compile-on-entry.

## Dependency Classes

Per-line compiled records track at least:

- source generation;
- dialect and IEEE mode;
- runtime ABI version;
- branch target table generation;
- `FOR`/`NEXT`, `DO`/`LOOP`, and `GOSUB`/`RETURN` metadata generation;
- `DATA` order generation;
- variable descriptor generation;
- code-layout generation.

A local edit may republish only the changed line when these fingerprints remain
valid. A structural edit may dirty other lines or force a whole-program relink.
It must not choose an interpreter fallback.

Tokenizer and parser work must be bounded enough for interactive entry.
Keyword recognition uses a generated first-character-indexed trie. Accepting
nodes contain token ID, dialect mask, abbreviation policy, and longest-match
metadata, so stock abbreviations and extension gating do not require a second
linear search. Lookup is bounded by candidate length plus the generated
transition bound and never rescans the full keyword table.

Every build emits `keyword_lookup_report.json` with trie size, maximum depth
and fan-out, worst observed transitions, and tokenizer/line-entry timings.
System tests compare every implemented command-manifest entry with trie
acceptance and fail if a fallback full-table scan is reachable.

The likely interactive bottleneck is not local keyword lookup but structural
dependency repair: an edit that changes branch targets, `DATA` order, loop or
subroutine structure, descriptors, or code layout can dirty many lines and
force a whole-program relink. Reverse dependency indexes and generation-stamped
dirty sets keep local edits proportional to affected records. Whole-program
repair remains an explicit measured worst case; it is never hidden behind an
interpreter fallback.

## Publication Rule

Compiled code is executable only after all dirty records are resolved, code
layout is verified, and the compiled-image checksum matches the current source
generation. Failed compilation reports the phase and line, then leaves the
last valid state intact.
