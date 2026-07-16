; Stock-compatible COMPILE export baseline image.
;
; Emitted as build/COMPILED.PRG (PRG header $01 $08 + this payload).  This is
; the source-free standalone shell contract from docs/COMPILE_EXPORT.md:
; stock BASIC V2 loader line, native entry at SYS 2061, and the restricted
; direct-mode vocabulary.  It is not a development/installer image.
;
; Layout profile: stock_compatible ($CE00 free).  No geoRAM dependency.

.segment "CODE"

; --- Stock BASIC V2 loader: 2026 SYS2061 ---
; Occupies $0801-$080C so the native entry is at the documented $080D (2061).
basic_line:
    .word basic_end
    .word 2026
    .byte $9E               ; SYS token
    .byte "2061"
    .byte 0
basic_end:
    .word 0

; --- Native entry ($080D): return to READY via a single CR ---
; A full program export replaces this with compiled user code + runtime.
native_entry:
    lda #$0D
    jsr $FFD2               ; CHROUT
    rts

; --- Standalone shell contract strings (source-free direct mode) ---
; LIST may reveal only the loader stub text; other keywords name the accepted
; restricted command set (COMPILE_EXPORT.md §Standalone Direct Mode).
shell_list_line:
    .byte "2026 SYS2061", $8D
shell_ready:
    .byte "READY.", $8D
shell_syntax:
    .byte "?SYNTAX ERROR", $8D
shell_commands:
    .byte "PRINT", 0
    .byte "CONT", 0
    .byte "LIST", 0
    .byte "RUN", 0
    .byte "LOAD", 0
    .byte "SAVE", 0
    .byte "VERIFY", 0
    .byte "CLR", 0
shell_wedge:
    .byte "$", 0
    .byte "/", 0
    .byte "@", 0
    .byte "!", 0
