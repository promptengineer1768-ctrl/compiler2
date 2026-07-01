# DOS Wedge

The DOS wedge is direct-mode only and follows the Action Replay-style surface
for the required prefixes `$`, `@`, `/`, and `!`.

Reference behavior is informed by Action Replay MK VI conventions, including
directory display with `$` or `@$`, load alias with `/`, device selection with
`@8` through `@11`, and command-channel use through `@`.

Reference: `https://rr.pokefinder.org/wiki/Action_Replay_MK6_Manual_Project64.txt`

## `$` Directory

`$` and `@$` display the current disk directory to the current text screen.
The directory must not load over the BASIC program. Output scrolls and affects
the current screen like ordinary text output.

## `/` Load Alias

`/name` and `/"name"` load a program from the current disk device using
absolute PRG load semantics equivalent to `LOAD "name",device,1`. The default
test device is 8 unless the program was loaded from another supported disk
device or changed by a wedge command such as `@9`.

## `@` Status and Commands

Bare `@` reads and prints the disk error channel. `@8`, `@9`, `@10`, and `@11`
select the current disk device by writing the same stock KERNAL file-device
state used by `LOAD`, `SAVE`, and `COMPILE`: `fa` at `$BA`. Other `@command`
forms send a disk command to the current disk device and then report status.
Supported forms should include initialization, validation, rename, scratch, and
new/format commands as implementation milestones allow.

Destructive commands such as scratch and format require confirmation.

## `!` Sequential Text Stream

`!name` and `!"name"` open a SEQ file and stream PETSCII bytes to the current
text screen through the normal output path. STOP aborts streaming and closes
the file.

There is no special screen-state restoration. If a wedge command clears the
screen, changes colors, scrolls, or moves the cursor, that is the resulting
editor screen state.
