; src/resident/resident_main.asm
; Minimal resident input loop and boundary assertions.

.include "common/zp.inc"
.include "common/constants.asm"
.include "georam_pages.inc"

.import screen_line_input
.import kernal_getin
.import georam_call_group_n
.import georam_verify_mirror

.segment "BSS"
resident_input_byte:      .res 1
resident_last_key:        .res 1
resident_last_submit_len: .res 1
resident_submit_count:    .res 1
resident_saved_p:         .res 1

.segment "RESIDENT"

.export resident_main
.export resident_poll_input
.export resident_submit_line
.export resident_assert_boundary
.export resident_input_byte

resident_main:
@loop:
    jsr resident_poll_input
    beq @loop
    sta resident_last_key
    jsr resident_submit_line
    jmp @loop

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
