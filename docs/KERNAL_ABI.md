# KERNAL ABI and Zero-Page Effects

## Source of Truth

The reference ROM source is:

`C:\Users\me\Documents\Coding Projects\c64rom`

It contains source that builds byte-identical Commodore BASIC
`901226-01` and KERNAL `901227-03`, along with labels and generated API/ZP
reports. Use the source and `debug/c64rom.labels` when a generated report and
the routine body disagree.

Compiler 2 targets the public KERNAL jump table. It does not call private ROM
addresses unless a separately versioned compatibility module requires one.

## Banking Contract

The nominal runtime map is `$01 = $35` under the standard DDR. BASIC and KERNAL
ROMs are banked out, I/O is visible, and RAM is visible at `$E000-$FFFF`.

Consequently, a normal `JSR` to a KERNAL jump-table address would execute RAM,
not ROM. KERNAL calls are legal only through a bridge that selects `$01 = $36`
for the call. This exposes KERNAL ROM and I/O while leaving BASIC ROM banked
out.

Ordinary runtime code does not save or change CPU banking. The transition is
owned entirely by the KERNAL bridge, which restores `$35` before returning.

While KERNAL ROM is visible, hardware vectors come from ROM rather than the RAM
vectors at `$FFFA-$FFFF`. Any bridge that permits IRQ must ensure the KERNAL RAM
indirect vectors, including `$0314`, reach the pinned bank-safe handlers.
Interrupt masking for an entire blocking file call is not acceptable.

## Bridge Rules

Every KERNAL bridge must:

1. assert the canonical `$35` entry mapping in debug builds;
2. save the interrupt state and any declared result registers;
3. select the `$36` KERNAL+I/O mapping;
4. marshal the documented register inputs;
5. call the public jump-table address;
6. capture returned registers, carry, and zero as required;
7. restore the canonical `$35` mapping and incoming interrupt state;
8. return only the documented result.

Bridges serialize use of shared KERNAL workspace. A foreground bridge cannot be
entered from IRQ. The IRQ uses only its explicitly approved KERNAL routines.

## Planned Call Surface

The table lists the important public calls, their intended use, and the
source-visible zero-page set that must seed the allocator. Device-dependent
file paths can touch additional KERNAL workspace and therefore use a broader
generated call domain.

| Call | Address | Main register ABI | Known ZP effects |
|---|---:|---|---|
| `READST` | `$FFB7` | returns status in A | `$90` `status`, `$BA` `fa` |
| `SETLFS` | `$FFBA` | A=logical, X=device, Y=secondary | `$B8` `la`, `$B9` `sa`, `$BA` `fa` |
| `SETNAM` | `$FFBD` | A=length, X/Y=name pointer | `$B7` `fnlen`, `$BB-$BC` `fnadr` |
| `OPEN` | `$FFC0` | uses prior `SETLFS`/`SETNAM` | file/channel domain; includes `$B8` and device workspace |
| `CLOSE` | `$FFC3` | A=logical file | `$98` `ldtnd` plus device workspace |
| `CHKIN` | `$FFC6` | X=logical file | channel/status domain including `$90`, `$99` |
| `CHKOUT` | `$FFC9` | X=logical file | channel/status domain including `$90`, `$9A` |
| `CLRCHN` | `$FFCC` | no inputs | `$94`, `$9A`, `$A3`, `$D7` on serial/default-channel paths |
| `CHRIN` | `$FFCF` | returns byte in A | `$99`, `$C9-$CA`, `$D0`, `$D3`, `$D6`; device paths add more |
| `CHROUT` | `$FFD2` | A=byte | `$9A`, `$C7`, `$C9`, `$D0`, `$D3-$D4`, `$D6-$D8` |
| `LOAD` | `$FFD5` | A=load/verify, X/Y=alternate address | `$90`, `$93`, `$BA`, `$C3-$C4` plus device workspace |
| `SAVE` | `$FFD8` | A=ZP pointer to start, X/Y=end | `$AE-$AF`, `$BA`, `$C1-$C2` plus device workspace |
| `SETTIM` | `$FFDB` | A=LSB, X=middle, Y=MSB | `$A0-$A2` |
| `RDTIM` | `$FFDE` | returns A=LSB, X=middle, Y=MSB | `$A0-$A2` |
| `STOP` | `$FFE1` | Z/result reports STOP | `$91`, `$C6`; STOP path also calls `CLRCHN` |
| `GETIN` | `$FFE4` | returns byte in A, zero if none | `$99`, `$C6` for keyboard; selected devices add more |
| `UDTIM` | `$FFEA` | no stable register result | `$91`, `$A0-$A2`; reads CIA keyboard matrix |
| `SCNKEY` | `$FF9F` | no stable register result | `$C5-$C6`, `$CB`, `$F5-$F6`; updates keyboard RAM state |

The exact screen-editor paths also use non-ZP state such as the keyboard queue,
repeat controls, shift state, color, and line tables. These addresses belong in
the same generated call contract even though they are not zero page.

`fa` at `$BA` is the stock KERNAL file-device byte written by `SETLFS` and used
by `LOAD`/`SAVE` paths. Compiler 2 also treats `$BA` as the current disk device
state for direct file commands, DOS wedge device selection, and `COMPILE`
default-device selection. Supported disk-device values are 8 through 11.

## IRQ Call Order

The pinned timer/keyboard IRQ follows the stock ordering:

1. select KERNAL+I/O mapping;
2. call `UDTIM`;
3. perform the bounded project cursor service;
4. call `SCNKEY`;
5. acknowledge CIA interrupt state;
6. restore mapping and registers;
7. `RTI`.

The foreground editor drains input with `GETIN`; it does not call `SCNKEY` or
manually advance the jiffy clock.

## File Calls

The canonical program file sequence is:

```text
SETNAM -> SETLFS -> LOAD
SETNAM -> SETLFS -> SAVE
```

When a direct command omits its device operand, the wrapper uses the current
disk device in `fa` (`$BA`). A command that explicitly specifies a device or a
DOS wedge device-selection form such as `@10` updates `fa` before subsequent
defaulted file commands.

Channel I/O uses:

```text
SETNAM -> SETLFS -> OPEN -> CHKIN/CHKOUT
CHRIN/CHROUT and READST
CLRCHN -> CLOSE
```

Every error exit restores the default channel as needed and restores the
project CPU mapping. Carry and KERNAL error code are converted to one documented
BASIC error in a resident wrapper.

`SAVE` receives A as the address of a zero-page pointer to the first byte, not
the first byte address itself. That pointer is an explicit KERNAL-call lifetime
in the zero-page manifest.

## ROM Availability

Production assumes a compatible KERNAL ROM is available while bridges run.
Local emulator tests may install minimal jump-table stubs, but those tests prove
only bridge marshalling and return behavior. Real file, keyboard, timer, and
screen effects require VICE.

## Verification

For each bridge:

- a static test checks address and declared ABI;
- a local-emulator test checks bank, stack, register, flag, and ZP preservation;
- a source audit checks the declared clobber set against `c64rom`;
- a VICE test covers the real routine and relevant hardware/device state.

Every successful build renders the validated bridge contracts into
`build/API.md`, including registers/flags, complete ZP read/write sets,
stack/return behavior, blocking/IRQ policy, banking, and side effects. The
generated reference is a view of the structured contract, not an independent
source of truth.
