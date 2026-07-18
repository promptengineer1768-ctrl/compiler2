; src/resident/screen.asm
; Minimal resident screen and cursor helpers.
;
; Cursor model (stock-compatible reverse-video blink):
;   zp_crsr_vis     = enabled (1) or disabled (0); not toggled by IRQ
;   cursor_drawn    = reverse currently painted into screen RAM
;   cursor_saved    = original cell under the reverse cursor
;   cursor_count    = jiffy countdown to next reverse toggle
; IRQ owns only the reverse toggle; foreground hides before edit/move.

.include "common/zp.inc"
.include "common/constants.asm"

.segment "RESIDENT"

SCREEN_COLS = 40
SCREEN_ROWS = 25
SCREEN_BASE = $0400
; Stock KERNAL editor cursor (docs/KERNEL_ZP.md / c64rom).
KERNAL_PNTR = $D3
KERNAL_TBLX = $D6
; Half-period in jiffies (~1/3 s at 60 Hz), matching the companion editor.
CURSOR_BLINK_PERIOD = 20

.segment "BSS"
screen_length:         .res 1
; Scratch for PETSCII/screen-code conversion (ROM-semantic, bit tests).
screen_conv_tmp:       .res 1
; Resident line capture buffer pointed to by zp_linebuf after screen_init.
.export resident_line_capture
resident_line_capture: .res 81
; IRQ/foreground shared cursor paint state (must live in normal RAM, not $E000).
.export cursor_drawn
cursor_drawn:          .res 1
.export cursor_saved
cursor_saved:          .res 1
.export cursor_count
cursor_count:          .res 1

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
.export screen_cursor_hide
.export screen_cursor_irq_service
.export screen_sync_from_kernal
.export screen_put_petscii
.export screen_petscii_to_screen
.export screen_to_petscii

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
    jsr screen_cursor_hide
    lda #$00
    sta zp_crsr_x
    sta zp_crsr_y
    sta zp_crsr_vis
    rts

screen_init:
    ; Point zp_linebuf at the resident capture buffer for line submission.
    lda #<resident_line_capture
    sta zp_linebuf
    lda #>resident_line_capture
    sta zp_linebuf+1
    lda #0
    sta zp_line_len
    sta cursor_drawn
    sta cursor_saved
    lda #CURSOR_BLINK_PERIOD
    sta cursor_count
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
    jsr screen_cursor_hide
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

; screen_putchar - Store A at the project cursor and advance one cell.
; Input: A = screen cell byte (PETSCII letter range is accepted by the harness).
; Clobbers: A, X, Y. Side effects: hides reverse cursor, advances zp_crsr_*.
screen_putchar:
    pha
    jsr screen_cursor_hide
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
    jsr screen_cursor_reset_count
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

; screen_petscii_to_screen - Stock PETSCII → screen-code mapping.
; GETIN yields PETSCII ($41 = "A"). Screen RAM needs codes ($01 = "A" glyph
; in the default uppercase/graphics charset). Storing PETSCII raw paints
; shifted/graphics glyphs instead of letters.
; Input: A = PETSCII. Output: A = screen code. Clobbers: A. Preserves: X, Y.
screen_petscii_to_screen:
    bmi @shifted
    cmp #$60
    bcc @unshifted
    and #$DF
    bne @done
@unshifted:
    and #$3F
@done:
    rts
@shifted:
    and #$7F
    cmp #$7F
    bne @shift_or
    lda #$5E
@shift_or:
    ora #$40
    rts

; screen_to_petscii - Stock screen-code → PETSCII mapping (ROM input path).
; Used when capturing a painted line so the tokenizer sees canonical PETSCII
; (letter keys as $41-$5A). Input: A = screen code. Output: A = PETSCII.
; Clobbers: A. Preserves: X, Y.
screen_to_petscii:
    sta screen_conv_tmp
    and #$3F
    asl screen_conv_tmp
    bit screen_conv_tmp
    bpl @hi_clear
    ora #$80
@hi_clear:
    bcc @check_v
    rts
@check_v:
    bvs @done
    ora #$40
@done:
    rts

; screen_put_petscii - Convert GETIN PETSCII to a screen cell and put it.
; Quote toggles zp_quotemode. Printable PETSCII is mapped then stored as a
; true screen code so the default charset shows letters, not graphics.
; Input: A = PETSCII. Clobbers: A, X, Y.
screen_put_petscii:
    cmp #$22
    bne @convert
    pha
    lda zp_quotemode
    eor #1
    sta zp_quotemode
    pla
@convert:
    cmp #$20
    bcc @done
    ; Shifted graphics ($A0+) are valid PETSCII; map them too.
    jsr screen_petscii_to_screen
    jsr screen_putchar
@done:
    rts

screen_cursor_on:
    lda #$01
    sta zp_crsr_vis
    ; Next IRQ paints reverse promptly so the cursor is visible immediately.
    lda #1
    sta cursor_count
    rts

screen_cursor_off:
    jsr screen_cursor_hide
    lda #$00
    sta zp_crsr_vis
    rts

; screen_cursor_hide - Restore the reverse cell if painted. IRQ-safe with SEI.
; Clobbers: A, Y. Preserves X.
screen_cursor_hide:
    php
    sei
    lda cursor_drawn
    beq @reset
    lda zp_crsr_y
    cmp #SCREEN_ROWS
    bcs @clear_drawn
    jsr screen_set_row_ptr
    ldy zp_crsr_x
    cpy #SCREEN_COLS
    bcs @clear_drawn
    lda cursor_saved
    sta (zp_src),y
@clear_drawn:
    lda #0
    sta cursor_drawn
@reset:
    lda #CURSOR_BLINK_PERIOD
    sta cursor_count
    plp
    rts

screen_cursor_reset_count:
    lda #CURSOR_BLINK_PERIOD
    sta cursor_count
    rts

; screen_cursor_irq_service - Bounded reverse-video blink for the project cursor.
; Called only from the pinned IRQ with $01 already selecting I/O+KERNAL-safe
; mapping for screen RAM ($0400 is always visible). Saves/restores zp_src so
; an interrupt mid-foreground screen op cannot corrupt its pointer.
; Clobbers: A, X, Y.
screen_cursor_irq_service:
    lda zp_crsr_vis
    beq @done
    dec cursor_count
    bne @done
    lda #CURSOR_BLINK_PERIOD
    sta cursor_count
    lda zp_crsr_y
    cmp #SCREEN_ROWS
    bcs @done
    pha
    lda zp_src
    pha
    lda zp_src+1
    pha
    lda zp_crsr_y
    jsr screen_set_row_ptr
    ldy zp_crsr_x
    cpy #SCREEN_COLS
    bcs @restore
    lda cursor_drawn
    beq @draw
    lda cursor_saved
    sta (zp_src),y
    lda #0
    sta cursor_drawn
    jmp @restore
@draw:
    lda (zp_src),y
    sta cursor_saved
    eor #$80
    sta (zp_src),y
    lda #1
    sta cursor_drawn
@restore:
    pla
    sta zp_src+1
    pla
    sta zp_src
    pla
@done:
    rts

; screen_sync_from_kernal - Copy stock CHROUT cursor into project cursor ZP.
; Call after kernal_print_packed / CHROUT so the blink cell matches the banner.
; Clobbers: A.
screen_sync_from_kernal:
    jsr screen_cursor_hide
    lda KERNAL_PNTR
    sta zp_crsr_x
    lda KERNAL_TBLX
    sta zp_crsr_y
    rts

screen_cursor_right:
    jsr screen_cursor_hide
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
    jsr screen_cursor_reset_count
    rts

screen_cursor_left:
    jsr screen_cursor_hide
    lda zp_crsr_x
    bne @left
    lda zp_crsr_y
    beq @done
    dec zp_crsr_y
    lda #SCREEN_COLS - 1
    sta zp_crsr_x
    jsr screen_cursor_reset_count
    rts
@left:
    dec zp_crsr_x
@done:
    jsr screen_cursor_reset_count
    rts

screen_cursor_down:
    jsr screen_cursor_hide
    inc zp_crsr_y
    lda zp_crsr_y
    cmp #SCREEN_ROWS
    bcc @done
    jsr screen_scroll_up
    lda #SCREEN_ROWS - 1
    sta zp_crsr_y
@done:
    jsr screen_cursor_reset_count
    rts

screen_cursor_up:
    jsr screen_cursor_hide
    lda zp_crsr_y
    beq @done
    dec zp_crsr_y
@done:
    jsr screen_cursor_reset_count
    rts

; screen_line_input - Capture the logical screen row at zp_crsr_y into zp_linebuf.
; Screen cells are ROM screen codes; the buffer receives PETSCII so the
; expansion tokenizer sees the same bytes GETIN would have produced.
; Trims trailing spaces unless zp_quotemode is set. Always NUL-terminates.
; Input: zp_linebuf pointer. Output: zp_line_len. Clobbers: A, X, Y.
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
    and #$7F
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
    beq @terminate
    ldy #$00
@copy_loop:
    lda (zp_src),y
    ; Drop reverse-video bit if the IRQ cursor is painted mid-capture.
    and #$7F
    ; Convert screen code → PETSCII for tokenize/submit.
    jsr screen_to_petscii
    sta (zp_linebuf),y
    iny
    cpy zp_line_len
    bcc @copy_loop
@terminate:
    ldy zp_line_len
    lda #0
    sta (zp_linebuf),y
    rts
