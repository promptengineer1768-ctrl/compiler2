; src/resident/fatal.asm
; Minimal fatal-path cleanup.

.include "common/zp.inc"

.import ctx_init
.import georam_select

.segment "BSS"
fatal_reason:   .res 1
fatal_diag_lo:  .res 1
fatal_diag_hi:  .res 1

.segment "RESIDENT"

.export fatal_georam
.export fatal_restore_machine
.export fatal_reason
.export fatal_diag_lo
.export fatal_diag_hi

fatal_restore_machine:
    jsr ctx_init
    lda #$35
    sta $01
    lda #$00
    ldx #$00
    jsr georam_select
    lda #$00
    sta zp_crsr_vis
    clc
    rts

fatal_georam:
    sta fatal_reason
    stx fatal_diag_lo
    sty fatal_diag_hi
    jsr fatal_restore_machine
    sec
    rts
