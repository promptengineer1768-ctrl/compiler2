; src/resident/resident_main.asm
; Resident input loop, boundary assertions, and degraded minimal editor.
;
; Normal mode submits lines through expansion-native editor services.
; Degraded mode (store loss after NMI re-detect) shows an expansion error and
; accepts only QUIT; any other command re-shows the error (DESIGN2 §8.5).

.include "common/zp.inc"
.include "common/constants.asm"

.import screen_line_input
.import kernal_getin
.import georam_call_group_n
.import georam_verify_mirror
.import vectors_prior_irq
.import vectors_prior_nmi
.import vectors_installed
.import nmi_invalidate_cont

; Low-byte group-1 index for editor_submit_line. Must match
; build/georam_pages.inc GEORAM_ROUTINE_ID_EDITOR_SUBMIT_LINE (tables live in
; georam_gate.asm; do not re-include that file here — it would duplicate CODE).
GEORAM_ROUTINE_ID_EDITOR_SUBMIT_LINE = 322

; Stock BASIC map pointers (BASIC_ZP / c64rom declare.s).
BASIC_TEMPPT = $16
BASIC_TEMPST = $19
BASIC_TXTTAB = $2B
BASIC_VARTAB = $2D
BASIC_ARYTAB = $2F
BASIC_STREND = $31
BASIC_FRETOP = $33
BASIC_MEMSIZ = $37
; Stock warm-start READY path after explicit CLR (KERNAL/BASIC glue).
STOCK_READY  = $E386
; Canonical stock map with BASIC + KERNAL + I/O visible.
CPU_PORT_STOCK = $37
CINV  = $0314
NMINV = $0318

.segment "BSS"
resident_input_byte:      .res 1
resident_last_key:        .res 1
resident_last_submit_len: .res 1
resident_submit_count:    .res 1
resident_saved_p:         .res 1
.export resident_degraded
resident_degraded:        .res 1
.export resident_quit_done
resident_quit_done:       .res 1

.segment "RESIDENT"

.export resident_main
.export resident_poll_input
.export resident_submit_line
.export resident_assert_boundary
.export resident_input_byte
.export resident_enter_degraded
.export resident_show_expansion_error
.export quit_to_stock
.export quit_explicit_clr
.export vectors_restore

resident_main:
    lda resident_degraded
    bne resident_minimal_editor
@loop:
    jsr resident_poll_input
    beq @loop
    sta resident_last_key
    jsr resident_submit_line
    jmp resident_main

; resident_enter_degraded - Enter minimal no-store editor (error + QUIT only).
; Input: none. Output: never returns.
; Side effects: sets resident_degraded, prints expansion error, loops.
resident_enter_degraded:
    lda #1
    sta resident_degraded
    ; Fall through into the minimal editor.

resident_minimal_editor:
    jsr resident_show_expansion_error
@loop:
    jsr resident_poll_input
    beq @loop
    sta resident_last_key
    jsr resident_submit_degraded
    ; Non-QUIT paths re-display the error; QUIT never returns.
    jmp resident_minimal_editor

; resident_show_expansion_error - Print the expansion-memory failure banner.
; Input: none. Output: C=0. Clobbers: A, X, Y.
resident_show_expansion_error:
    ldx #0
@copy:
    lda expansion_error_msg, x
    beq @done
    sta $0400, x
    inx
    cpx #40
    bcc @copy
@done:
    clc
    rts

; resident_submit_degraded - Accept only QUIT in the minimal editor.
; Captures the logical screen line and matches ASCII "QUIT" (case-insensitive).
; Any other non-empty command re-shows the expansion error (caller loops).
; Input: none. Output: C=0 always when returning; QUIT does not return.
; Clobbers: A, X, Y.
resident_submit_degraded:
    jsr screen_line_input
    lda zp_line_len
    beq @empty
    cmp #4
    bne @reject
    ldy #0
@check:
    lda (zp_linebuf), y
    and #$7F
    ; Fold ASCII letters to uppercase for case-insensitive QUIT match.
    cmp #'a'
    bcc @cmp
    cmp #'z'+1
    bcs @cmp
    and #$DF
@cmp:
    cmp quit_ascii, y
    bne @reject
    iny
    cpy #4
    bne @check
    jmp quit_to_stock
@reject:
    sec
    rts
@empty:
    clc
    rts

quit_ascii:
    .byte "QUIT"

expansion_error_msg:
    .byte "?EXPANSION MEMORY REQUIRED"
    .byte 0

resident_poll_input:
    lda resident_input_byte
    bne @consume
    jsr kernal_getin
    rts
@consume:
    pha
    lda #$00
    sta resident_input_byte
    pla
    rts

resident_submit_line:
    lda resident_degraded
    bne @degraded
    jsr resident_assert_boundary
    bcs @fail
    jsr screen_line_input
    ldx #<GEORAM_ROUTINE_ID_EDITOR_SUBMIT_LINE
    jsr georam_call_group_n
    bcs @fail
    lda zp_line_len
    sta resident_last_submit_len
    inc resident_submit_count
    clc
    rts
@degraded:
    jmp resident_submit_degraded
@fail:
    sec
    rts

resident_assert_boundary:
    php
    pla
    sta resident_saved_p
    lda $01
    cmp #$35
    bne @fail
    lda resident_saved_p
    and #$08
    bne @fail
    jsr georam_verify_mirror
    bcs @fail
    lda zp_gr_ctx_sp
    cmp #$08
    bcs @fail
    clc
    rts
@fail:
    sec
    rts

; vectors_restore - Restore prior IRQ/NMI vectors saved by compiler_vectors.
; Resident so QUIT/degraded leave works without expansion-native code.
; Input:  none
; Output: C clear when priors were installed and restored; C set if never installed
; Clobbers: A
; Side effects: writes $0314-$0315 and $0318-$0319
vectors_restore:
    lda vectors_installed
    beq @not_installed
    lda vectors_prior_irq
    sta CINV
    lda vectors_prior_irq+1
    sta CINV+1
    lda vectors_prior_nmi
    sta NMINV
    lda vectors_prior_nmi+1
    sta NMINV+1
    lda #0
    sta vectors_installed
    clc
    rts
@not_installed:
    sec
    rts

; quit_to_stock - Soft-reset leave path for QUIT (gateway, direct-only).
; Locked sequence (REQUIREMENTS R4 / DESIGN2 §8.5):
;   1. restore banking/map pointers and prior IRQ/NMI vectors
;   2. clean Compiler 2-owned continuation/control state
;   3. CLR explicitly (keep tokenized program)
;   4. enter stock READY with BASIC+KERNAL map
; Expansion device contents are left untouched. Does not return.
; Input: none. Output: never returns.
; Clobbers: A, X, Y, stack, mapping, BASIC variable map.
quit_to_stock:
    sei
    cld
    ldx #$FF
    txs
    ; Canonical project map while we touch project BSS and stock ZP.
    lda #CPU_PORT_CANONICAL
    sta $01
    jsr vectors_restore
    ; Resident-safe CONT invalidation (no geoRAM CODE dependency).
    jsr nmi_invalidate_cont
    jsr quit_explicit_clr
    lda #1
    sta resident_quit_done
    lda #0
    sta resident_degraded
    ; Stock BASIC + KERNAL + I/O, then READY.
    lda #CPU_PORT_STOCK
    sta $01
    cli
    jmp STOCK_READY

; quit_explicit_clr - Stock CLR semantics without cold init.
; Resets arytab/strend to vartab, fretop to memsiz, and the string stack
; pointer, leaving txttab/program text intact (clearc + temppt).
; Input: none. Output: C=0. Clobbers: A, Y.
quit_explicit_clr:
    lda BASIC_MEMSIZ
    ldy BASIC_MEMSIZ+1
    sta BASIC_FRETOP
    sty BASIC_FRETOP+1
    lda BASIC_VARTAB
    ldy BASIC_VARTAB+1
    sta BASIC_ARYTAB
    sty BASIC_ARYTAB+1
    sta BASIC_STREND
    sty BASIC_STREND+1
    lda #BASIC_TEMPST
    sta BASIC_TEMPPT
    clc
    rts
