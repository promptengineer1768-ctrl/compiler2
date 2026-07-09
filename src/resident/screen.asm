; src/resident/screen.asm
; Minimal resident screen and cursor helpers.

.include "common/zp.inc"
.include "common/constants.asm"

.segment "RESIDENT"

SCREEN_COLS = 40
SCREEN_ROWS = 25
SCREEN_BASE = $0400

.segment "BSS"
screen_length:   .res 1

.segment "RESIDENT"

.export screen_init
.export screen_clear
.export screen_scroll_up
.export screen_putchar
.export screen_getchar
.export screen_cursor_on
.export screen_cursor_off
.export screen_cursor_right
.export screen_cursor_left
.export screen_cursor_down
.export screen_cursor_up
.export screen_line_input

screen_row_lo:
    .byte <(SCREEN_BASE + 40 * 0)
    .byte <(SCREEN_BASE + 40 * 1)
    .byte <(SCREEN_BASE + 40 * 2)
    .byte <(SCREEN_BASE + 40 * 3)
    .byte <(SCREEN_BASE + 40 * 4)
    .byte <(SCREEN_BASE + 40 * 5)
    .byte <(SCREEN_BASE + 40 * 6)
    .byte <(SCREEN_BASE + 40 * 7)
    .byte <(SCREEN_BASE + 40 * 8)
    .byte <(SCREEN_BASE + 40 * 9)
    .byte <(SCREEN_BASE + 40 * 10)
    .byte <(SCREEN_BASE + 40 * 11)
    .byte <(SCREEN_BASE + 40 * 12)
    .byte <(SCREEN_BASE + 40 * 13)
    .byte <(SCREEN_BASE + 40 * 14)
    .byte <(SCREEN_BASE + 40 * 15)
    .byte <(SCREEN_BASE + 40 * 16)
    .byte <(SCREEN_BASE + 40 * 17)
    .byte <(SCREEN_BASE + 40 * 18)
    .byte <(SCREEN_BASE + 40 * 19)
    .byte <(SCREEN_BASE + 40 * 20)
    .byte <(SCREEN_BASE + 40 * 21)
    .byte <(SCREEN_BASE + 40 * 22)
    .byte <(SCREEN_BASE + 40 * 23)
    .byte <(SCREEN_BASE + 40 * 24)

screen_row_hi:
    .byte >(SCREEN_BASE + 40 * 0)
    .byte >(SCREEN_BASE + 40 * 1)
    .byte >(SCREEN_BASE + 40 * 2)
    .byte >(SCREEN_BASE + 40 * 3)
    .byte >(SCREEN_BASE + 40 * 4)
    .byte >(SCREEN_BASE + 40 * 5)
    .byte >(SCREEN_BASE + 40 * 6)
    .byte >(SCREEN_BASE + 40 * 7)
    .byte >(SCREEN_BASE + 40 * 8)
    .byte >(SCREEN_BASE + 40 * 9)
    .byte >(SCREEN_BASE + 40 * 10)
    .byte >(SCREEN_BASE + 40 * 11)
    .byte >(SCREEN_BASE + 40 * 12)
    .byte >(SCREEN_BASE + 40 * 13)
    .byte >(SCREEN_BASE + 40 * 14)
    .byte >(SCREEN_BASE + 40 * 15)
    .byte >(SCREEN_BASE + 40 * 16)
    .byte >(SCREEN_BASE + 40 * 17)
    .byte >(SCREEN_BASE + 40 * 18)
    .byte >(SCREEN_BASE + 40 * 19)
    .byte >(SCREEN_BASE + 40 * 20)
    .byte >(SCREEN_BASE + 40 * 21)
    .byte >(SCREEN_BASE + 40 * 22)
    .byte >(SCREEN_BASE + 40 * 23)
    .byte >(SCREEN_BASE + 40 * 24)

screen_set_row_ptr:
    tay
    lda screen_row_lo,y
    sta zp_src
    lda screen_row_hi,y
    sta zp_src+1
    rts

screen_set_row_src_ptr:
    tay
    lda screen_row_lo,y
    sta zp_src
    lda screen_row_hi,y
    sta zp_src+1
    rts

screen_set_row_dst_ptr:
    tay
    lda screen_row_lo,y
    sta zp_dest
    lda screen_row_hi,y
    sta zp_dest+1
    rts

screen_home:
    lda #$00
    sta zp_crsr_x
    sta zp_crsr_y
    sta zp_crsr_vis
    rts

screen_init:
    jsr screen_clear
    rts

screen_clear:
    jsr screen_home
    ldx #SCREEN_ROWS - 1
@row_loop:
    txa
    jsr screen_set_row_ptr
    ldy #SCREEN_COLS - 1
    lda #$20
@col_loop:
    sta (zp_src),y
    dey
    bpl @col_loop
    dex
    bpl @row_loop
    rts

screen_scroll_up:
    ldx #$00
@copy_row:
    txa
    clc
    adc #$01
    jsr screen_set_row_src_ptr
    txa
    jsr screen_set_row_dst_ptr
    ldy #$00
@copy_col:
    lda (zp_src),y
    sta (zp_dest),y
    iny
    cpy #SCREEN_COLS
    bcc @copy_col
    inx
    cpx #SCREEN_ROWS - 1
    bcc @copy_row
    lda #SCREEN_ROWS - 1
    jsr screen_set_row_ptr
    ldy #SCREEN_COLS - 1
    lda #$20
@clear_row:
    sta (zp_src),y
    dey
    bpl @clear_row
    rts

screen_putchar:
    pha
    lda zp_crsr_y
    jsr screen_set_row_ptr
    ldy zp_crsr_x
    pla
    sta (zp_src),y
    inc zp_crsr_x
    lda zp_crsr_x
    cmp #SCREEN_COLS
    bcc @done
    lda #$00
    sta zp_crsr_x
    inc zp_crsr_y
    lda zp_crsr_y
    cmp #SCREEN_ROWS
    bcc @done
    jsr screen_scroll_up
    lda #SCREEN_ROWS - 1
    sta zp_crsr_y
@done:
    rts

screen_getchar:
    lda zp_crsr_y
    cmp #SCREEN_ROWS
    bcs @zero
    jsr screen_set_row_ptr
    ldy zp_crsr_x
    cpy #SCREEN_COLS
    bcs @zero
    lda (zp_src),y
    rts
@zero:
    lda #$00
    rts

screen_cursor_on:
    lda #$01
    sta zp_crsr_vis
    rts

screen_cursor_off:
    lda #$00
    sta zp_crsr_vis
    rts

screen_cursor_right:
    inc zp_crsr_x
    lda zp_crsr_x
    cmp #SCREEN_COLS
    bcc @done
    lda #$00
    sta zp_crsr_x
    inc zp_crsr_y
    lda zp_crsr_y
    cmp #SCREEN_ROWS
    bcc @done
    jsr screen_scroll_up
    lda #SCREEN_ROWS - 1
    sta zp_crsr_y
@done:
    rts

screen_cursor_left:
    lda zp_crsr_x
    bne @left
    lda zp_crsr_y
    beq @done
    dec zp_crsr_y
    lda #SCREEN_COLS - 1
    sta zp_crsr_x
    rts
@left:
    dec zp_crsr_x
@done:
    rts

screen_cursor_down:
    inc zp_crsr_y
    lda zp_crsr_y
    cmp #SCREEN_ROWS
    bcc @done
    jsr screen_scroll_up
    lda #SCREEN_ROWS - 1
    sta zp_crsr_y
@done:
    rts

screen_cursor_up:
    lda zp_crsr_y
    beq @done
    dec zp_crsr_y
@done:
    rts

screen_line_input:
    lda zp_crsr_y
    jsr screen_set_row_ptr
    lda zp_quotemode
    beq @trim
    lda #SCREEN_COLS
    sta screen_length
    jmp @copy
@trim:
    ldy #SCREEN_COLS - 1
@trim_loop:
    lda (zp_src),y
    cmp #$20
    bne @trim_found
    dey
    bpl @trim_loop
    lda #$00
    bne @store_len
@trim_found:
    iny
    tya
@store_len:
    sta screen_length
@copy:
    lda screen_length
    sta zp_line_len
    beq @done
    ldy #$00
@copy_loop:
    lda (zp_src),y
    sta (zp_linebuf),y
    iny
    cpy zp_line_len
    bcc @copy_loop
@done:
    rts
