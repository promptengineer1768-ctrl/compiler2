# COMPILE Export

`COMPILE` creates a source-free compiled PRG for stock C64 loading and
execution without geoRAM.

## Syntax

```text
COMPILE ["filename" [,device]]
```

If `filename` is omitted, the export filename is `COMPILED`. If `device` is
omitted, the export uses the current disk device. The current disk device is
the stock KERNAL file-device byte `fa` at `$BA`, shared with `SETLFS`, `LOAD`,
and `SAVE`. Compiler 2 supports disk devices 8 through 11; tests normally use
device 8, but a system loaded from device 9 must default subsequent bare
`COMPILE` output to device 9. DOS wedge device-selection commands such as `@10`
update the same current disk device.

The exported program contains:

- a stock BASIC V2 loader line;
- native compiled code;
- the required runtime helpers;
- relocation and version metadata already resolved for the export;
- variable descriptors needed for runtime and direct inspection;
- a source-free standalone direct-mode environment.

The export must not require the Compiler 2 editor, compiler workspace, source
arena, installed Compiler 2 environment, or geoRAM. Any runtime state needed by
the exported program, including string payloads, must be representable in normal
C64 RAM.

## Stock Memory Budget

The exported PRG must load entirely within `$0801-$CFFF` on a stock C64. With
the standard loader line `2026 SYS2061`, the standalone machine-code/runtime
payload starts at `$080D`; therefore the longest possible contiguous compiled
payload ends at `$CFFF`.

The compiler reports and enforces:

```text
standalone_code_budget = standalone_loader_bytes + compiled_program_bytes
```

`compiled_program_bytes` includes user code, required runtime helpers,
relocation or runtime metadata, variable descriptors, the standalone
direct-mode environment, and any other byte loaded as part of the standalone
program image.
Tokenized source is not part of `compiled_program_bytes` and does not count
against the standalone code budget.
The development environment may cache the compiled image in geoRAM, but that
cache is accepted only if the same bytes would fit the standalone stock-C64
export budget.

Variable, array, string, stack, and standalone command-environment working storage
are budgeted outside the code image and must fit the normal RAM remaining after
the exported PRG is loaded. Programs whose code image fits only by relying on
geoRAM are not valid `COMPILE` outputs.

## No Source

The compiled PRG has no tokenized source. `LIST` in standalone direct mode
shell may reveal only the exact stock-compatible loader stub:

```basic
2026 SYS2061
```

Source reconstruction or decompilation is not a feature.

## Standalone Direct Mode

After a compiled program returns to `READY.` with valid state, the exported
runtime provides a source-free direct-mode environment. It is not a general
BASIC immediate environment and does not include a program editor.

For state inspection and continuation, it accepts:

```basic
?A
PRINT A
?A(N)
PRINT A$(N)
CONT
```

The expression after `?` or `PRINT` is one term: a scalar variable, string
variable, or one array element.

The environment also supports `RUN`, `LOAD`, `SAVE`, `VERIFY`, `CLR`, and every
DOS wedge command defined in `DOS_WEDGE.md`. File and wedge operations use the
stock KERNAL current-device state, `fa` at `$BA`; wedge device selection updates
that state for subsequent commands.

Compound expressions, assignment, program editing, and arbitrary BASIC
statements outside this required command set are rejected. `LIST` has the
loader-only behavior defined above.

`CONT` resumes compiled code from a valid STOP keyword or STOP-key interruption
state. Since there is no source, `CONT` depends only on the compiled continuation
frame, runtime state, and variable arenas.
