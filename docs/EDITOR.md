# Editor Requirements

The editor is a stock-compatible BASIC program editor with expansion-native
services (geoRAM execute-in-place or REU-loaded overlays, per the dual-device
profile in `DESIGN2.md` §8).

The resident front end owns only timing-sensitive work:

- IRQ keyboard scan and jiffy-clock service;
- cursor state needed for visible editing;
- bounded current-line capture;
- handoff to the expansion-native editor service.

The expansion-native service owns tokenization, detokenization, `LIST`, range
formatting, line insertion/deletion, diagnostics, and program-directory
maintenance.

Line submission should feel interactive. The target for ordinary numbered-line
entry is about 0.5 seconds or less, measured from Return to the next editor-ready
state. Long services must stay bounded and measurable (and, under REU, chunked
so pending IRQ service can run). Keyword scanning uses the generated
first-character-indexed trie defined by `INCREMENTAL_COMPILATION.md`; it does
not linearly scan the complete keyword table for each candidate. The build
reports trie bounds and measured tokenizer/line-entry cost in
`keyword_lookup_report.json`.

## Stock Behaviors to Preserve

Implementation and tests must cover:

- logical-line length and wrapping;
- quote mode;
- insert and delete;
- cursor movement;
- keyboard repeat;
- STOP polling;
- screen scrolling;
- color/output behavior visible to BASIC programs;
- canonical tokenization of `REM`, `DATA`, quotes, abbreviations, and extended
  tokens.

IRQ code must never enter an expansion-native editor routine and must never
program the REU controller. Long editor services must
permit timer and keyboard progress through bounded entry points.
