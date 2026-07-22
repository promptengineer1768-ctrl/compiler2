# Documentation Map

Compiler 2 is a new native 6502 BASIC compiler and interactive environment for
the Commodore 64 with dual expansion support (geoRAM and REU). Design and
requirements in this tree are the source of truth.

## Authority order

1. **Requirements** — externally visible behavior and acceptance criteria  
   - `../REQUIREMENTS.md` — product, language, memory, expansion summary, tests  
   - `../REU_REQUIREMENTS.md` — dual-device detection, REU DMA/overlays, dual packaging  
2. **Design** — architecture that satisfies those requirements  
   - `../DESIGN.md` — top-level design index
   - `../REU_DESIGN.md` — dual-device / REU detailed design  
3. **Focused design docs** (this directory) — subsystem contracts named by
   `DESIGN.md`
4. **Implementation maps** — `../SKELETON.md`, `../TASKS.md`, `../REU_TASKS.md`,
   with canonical state and evidence in `TASKS_MANIFEST.md` / `../manifests/tasks.json`,
   `../TESTS.md` (not authorities when they conflict with 1–3)  
5. **Generated build references** — `build/API.md`, `build/MAP.md` (current
   build only; never normative inputs)

When documents disagree, a higher tier wins. When a focused doc and
`DESIGN.md` disagree on architecture, update the focused doc or reconcile
through requirements first.

## Normative design documents (`docs/`)

| Document | Role |
|---|---|
| `COMPILER_ARCHITECTURE.md` | Layer map, program store, runtime ABI sketch |
| `GEORAM_BANKING.md` | geoRAM hardware contract and call ABI |
| `GEORAM_LOADER_DESIGN.md` | geoRAM install stream (CGS1) |
| `ZERO_PAGE.md` | Zero-page manifest and interference graph |
| `KERNAL_ABI.md` | KERNAL bridge contract |
| `BASIC_COMPATIBILITY_LIMITS.md` | Stock edge-limit contracts |
| `SYSTEM_PRIMITIVES.md` | PEEK/POKE/SYS/USR/WAIT/TI |
| `LOOP_OPTIMIZATION.md` | Loop descriptors and fast paths |
| `CONTROL_FLOW.md` | FOR/DO frames, STOP/CONT |
| `INCREMENTAL_COMPILATION.md` | Per-line compile/publish |
| `COMPILE_EXPORT.md` | Stock-C64 export format and budget |
| `RUNTIME_IO.md` | Channel/file runtime request records |
| `DOS_WEDGE.md` | `$` `@` `/` `!` direct-mode commands |
| `EDITOR.md` | Resident / expansion-native editor split |
| `IEEE754.md` | IEEE 754 numeric profile summary |
| `MEMORY_BUDGETS.md` | Normal-RAM and expansion accounting |
| `GRAPHICS_MEMORY.md` | Bitmap / screen-matrix layout |
| `BUILD.md` | Toolchain, build order, artifacts |
| `GENERATED_REFERENCE.md` | `API.md` / `MAP.md` schemas |
| `VICE_TOOLS.md` | D64/PETCAT recipes |
| `TESTING.md` | Test hierarchy and fixture mechanics |
| `CANONICAL_TESTS.md` | Fixture regeneration policy |
| `TRACEABILITY.md` | EARS trace-record format |

## Language references

User-facing and keyword references. They must stay consistent with
requirements; they do not reduce the BASIC V2 surface if an entry is missing.

- `KEYWORDS.md`
- `MANUAL.md`
- `CANONICAL_TESTS.md` (fixture policy; also under testing)

Planned entries are not implemented solely because they appear in a reference.

## Generated build references

Every build produces non-normative, current-build references:

- `build/API.md` — production callables and calling conventions  
- `build/MAP.md` — CPU, zero-page, segment, geoRAM/REU, arena, graphics,
  vector, standalone, dynamic, and free summaries  

Schemas: `GENERATED_REFERENCE.md`. Safe to delete with `build/`; never edit by
hand or use as inputs to the next build.

## External references

Stock BASIC V2 and KERNAL behavior:

`C:\Users\me\Documents\Coding Projects\c64rom`

An earlier external compiler tree may be consulted during implementation for
algorithms or measurements only; it is not part of Compiler 2 documentation
and is not a design or compatibility authority.
