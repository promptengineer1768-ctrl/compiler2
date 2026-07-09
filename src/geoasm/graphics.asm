; src/geoasm/graphics.asm
; Graphics API for bitmap mode, screen matrix copy, and bounds validation.
;
; Ported from legacy graphics_helpers.s with Compiler 2 ABI conventions.
; Supports hi-res and multicolor bitmap modes via VIC-II registers.

.include "common/zp.inc"
.include "common/constants.asm"

.import hibasic_graphics_reserve

; VIC-II registers
VIC_BORDER_COLOR       = $D020
VIC_BACKGROUND_COLOR0  = $D021
VIC_BACKGROUND_COLOR1  = $D022
VIC_BACKGROUND_COLOR2  = $D023
VIC_BACKGROUND_COLOR3  = $D024
VIC_SCREEN_CONTROL     = $D011
VIC_SCREEN_MSB         = $D012
VIC_MEM_CONTROL        = $D018
VIC_SPRITE_ENABLE      = $D015
VIC_IRQ_STATUS         = $D019
VIC_IRQ_MASK           = $D01A

; Sprite pointers
VIC_SPRITE_PTR_BASE    = $07F8

; Graphics constants
GRAPHICS_BITMAP_BASE   = $E000
GRAPHICS_SCREEN_BASE   = $DC00
GRAPHICS_MAX_X         = 319
GRAPHICS_MAX_Y         = 199
GRAPHICS_BITMAP_BYTES  = 8000   ; 320*200/8
GRAPHICS_ROW_BYTES     = 40     ; 320/8

; Working pointers
zp_ptr1     = zp_tmptr
zp_ptr2     = zp_expr_ptr2

.segment "GRAPHICS_STATE"

; Graphics state
graphics_mode:          .byte 0
graphics_fg:            .byte 1
graphics_bg:            .byte 0
graphics_mc1:           .byte 0
graphics_mc2:           .byte 0
graphics_text_color:    .byte $0E  ; light blue
graphics_cursor_x:      .word 0
graphics_cursor_y:      .byte 0
graphics_scale:         .byte 1
graphics_last_rdot:     .byte 0
graphics_row_base:      .word 0
graphics_column_offset: .word 0

; Bitmap row address table
graphics_bitmap_row_lo:
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 0)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 1)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 2)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 3)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 4)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 5)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 6)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 7)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 8)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 9)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 10)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 11)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 12)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 13)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 14)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 15)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 16)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 17)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 18)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 19)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 20)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 21)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 22)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 23)
    .byte <(GRAPHICS_BITMAP_BASE + 320 * 24)

graphics_bitmap_row_hi:
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 0)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 1)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 2)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 3)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 4)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 5)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 6)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 7)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 8)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 9)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 10)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 11)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 12)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 13)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 14)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 15)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 16)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 17)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 18)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 19)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 20)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 21)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 22)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 23)
    .byte >(GRAPHICS_BITMAP_BASE + 320 * 24)

.segment "GRAPHICS"

; =============================================================================
; Bitmap Address Calculation
; =============================================================================

; Calculate bitmap address from X/Y coordinates
; Input:  X = X coord (0-255), Y = row (0-24)
; Output: zp_ptr1 = bitmap address
.export graphics_calc_bitmap_addr
graphics_calc_bitmap_addr:
    ; Row base
    lda graphics_bitmap_row_lo,y
    sta zp_ptr1
    lda graphics_bitmap_row_hi,y
    sta zp_ptr1+1
    ; Add X offset (X/8 = byte offset)
    txa
    lsr a
    lsr a
    lsr a
    clc
    adc zp_ptr1
    sta zp_ptr1
    lda #0
    adc zp_ptr1+1
    sta zp_ptr1+1
    rts

; =============================================================================
; Bitmap Mode Entry/Exit
; =============================================================================

; graphics_enter - Switch to bitmap mode
; Input:  A = mode (0 = hi-res, 1 = multicolor)
; Output: C = error
; Clobbers: A, X, Y
.export graphics_enter
graphics_enter:
    pha
    jsr hibasic_graphics_reserve
    pla
    cmp #0
    beq @hires
    cmp #1
    beq @multicolor
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
@hires:
    sta graphics_mode
    ; Enable bitmap mode, set screen memory
    lda #$3B        ; bitmap mode on, 25 rows
    sta VIC_SCREEN_CONTROL
    ; Memory config: bitmap at $E000, screen at $DC00
    lda #$18        ; bitmap at $E000 (bit 3), screen at $DC00 (bits 4-7)
    sta VIC_MEM_CONTROL
    ; Clear sprites
    lda #$00
    sta VIC_SPRITE_ENABLE
    clc
    rts
@multicolor:
    sta graphics_mode
    ; Enable bitmap mode, set screen memory
    lda #$3B        ; bitmap mode on, 25 rows
    sta VIC_SCREEN_CONTROL
    ; Memory config for multicolor
    lda #$58        ; bitmap at $E000, screen at $DC00, multicolor
    sta VIC_MEM_CONTROL
    ; Clear sprites
    lda #$00
    sta VIC_SPRITE_ENABLE
    clc
    rts

; graphics_exit - Restore text mode
; Input:  A = saved state (0 = restore to text)
; Output: none
; Clobbers: A, X, Y
.export graphics_exit
graphics_exit:
    ; Restore text mode
    lda #$1B        ; text mode, 25 rows, display on
    sta VIC_SCREEN_CONTROL
    ; Restore standard memory config
    lda #$17        ; screen at $0400
    sta VIC_MEM_CONTROL
    ; Restore colors
    lda #$00        ; black border/background
    sta VIC_BORDER_COLOR
    lda #$0E        ; light blue text
    sta VIC_BACKGROUND_COLOR0
    rts

; =============================================================================
; Screen Matrix Operations
; =============================================================================

; graphics_matrix_copy - Copy bitmap data with IRQ opportunities
; Input:  X/Y = source handle (pointer to source data)
; Output: C = error
; Clobbers: A, X, Y
.export graphics_matrix_copy
graphics_matrix_copy:
    ; Copy bitmap data from source to bitmap memory
    ; Source pointer in X/Y
    stx zp_ptr1
    sty zp_ptr1+1
    ; Destination
    lda #<GRAPHICS_BITMAP_BASE
    sta zp_ptr2
    lda #>GRAPHICS_BITMAP_BASE
    sta zp_ptr2+1
    ; Copy 8000 bytes with IRQ opportunities every 256 bytes
    ldx #0
    ldy #0
@outer:
    ; IRQ opportunity
    lda VIC_IRQ_STATUS
    ; Copy 256 bytes
@inner:
    lda (zp_ptr1),y
    sta (zp_ptr2),y
    iny
    bne @inner
    ; Advance to next page
    inc zp_ptr1+1
    inc zp_ptr2+1
    inx
    cpx #31         ; 31 * 256 = 7936 bytes
    bcc @outer
    ; Copy remaining 64 bytes
    ldy #63
@remaining:
    lda (zp_ptr1),y
    sta (zp_ptr2),y
    dey
    bpl @remaining
    clc
    rts

; =============================================================================
; Bounds Validation
; =============================================================================

; graphics_validate_bounds - Check pixel/cell limits
; Input:  X = X coordinate (low byte), Y = Y coordinate (0-24)
; Output: C = out of bounds (set = invalid)
; Clobbers: A
.export graphics_validate_bounds
graphics_validate_bounds:
    ; Check Y bounds (0-24)
    cpy #25
    bcs @invalid
    ; Check X bounds (0-319)
    cpx #<GRAPHICS_MAX_X+1
    bcc @valid
    bne @invalid
    ; X == 200, check high byte if provided
@valid:
    clc
    rts
@invalid:
    sec
    rts
