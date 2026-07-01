# Compiled Save Format

Compiled save/export format notes. `REQUIREMENTS.md` and
`COMPILE_EXPORT.md` are authoritative if they conflict with this legacy-derived
note.

## Intent

The `COMPILE ["filename" [,device]]` export path saves:

- a one-line BASIC loader: `2026 SYS2061`
- a pre-relocated compiled machine-code payload

Omitted filename defaults to `COMPILED`. Omitted device defaults to the current
disk device in stock KERNAL `fa` at `$BA`.

The saved artifact will not include tokenized source. It includes only runtime
metadata that is required while the source-free program executes or provides its
standalone direct-mode environment.

`LIST` in the standalone direct-mode environment may show only:

```basic
2026 SYS2061
```

It must not include tokenized source and must not attempt to decompile the
native program image.

## Address Budget

The PRG starts at `$0801`; the machine-code payload starts at `$080D`, matching
the `SYS2061` loader target. The full loaded PRG image must end no later than
`$CFFF` so it runs on a stock C64 without geoRAM.

The compiler reports and enforces:

```text
standalone_code_budget = standalone_loader_bytes + compiled_program_bytes
```

Tokenized source is excluded from `compiled_program_bytes`.

The installed development environment may cache the compiled image in geoRAM,
but the cached image must still fit this standalone budget before it can be
published or exported.
