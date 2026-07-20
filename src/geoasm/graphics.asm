; src/geoasm/graphics.asm
; Graphics lifecycle: enter/exit, matrix copy, bounds (docs/GRAPHICS_MEMORY.md).
; Layout: bank 3, $D018=$78, matrix $DC00-$DFE7, bitmap $E000-$FF3F.
; Public entries return with $01 = $35.

.include "common/zp.inc"
.include "common/constants.asm"

.import hibasic_graphics_reserve
.import ram_under_io_copy_in

VIC_BORDER     = $D020
VIC_BG0        = $D021
VIC_CTRL1      = $D011
VIC_CTRL2      = $D016
VIC_MEM        = $D018
VIC_SPR_EN     = $D015
CIA2_PRA       = $DD00
CIA2_DDRA      = $DD02
CPU_PORT       = $01

BITMAP_BASE    = $E000
MATRIX_BASE    = $DC00
MATRIX_END     = $DFE7
MAX_X          = 319
MAX_Y          = 199
CELL_MAX_X     = 39
CELL_MAX_Y     = 24
MEM_TOP_BMP    = $DBFF
MEM_TOP_TEXT   = $FFF9
D018_BITMAP    = $78
D018_TEXT      = $17
D011_BITMAP    = $3B
D011_TEXT      = $1B
D016_TEXT      = $C8
CHUNK          = 64

zp_ptr1 = zp_tmptr

.segment "GRAPHICS_STATE"

.export graphics_mode
.export graphics_active
.export graphics_dynamic_ceiling
graphics_mode:            .byte 0
graphics_active:          .byte 0
graphics_dynamic_ceiling: .word MEM_TOP_TEXT
graphics_copy_dest:       .word 0
graphics_copy_remain:     .word 0

; Character-row bases for hires bitmap addressing (25 rows * 320).
graphics_bitmap_row_lo:
    .repeat 25, i
        .byte <(BITMAP_BASE + 320 * i)
    .endrepeat
graphics_bitmap_row_hi:
    .repeat 25, i
        .byte >(BITMAP_BASE + 320 * i)
    .endrepeat

.segment "GRAPHICS"

; graphics_calc_bitmap_addr — X=x(0-255 path), Y=row(0-24) → zp_tmptr
.export graphics_calc_bitmap_addr
graphics_calc_bitmap_addr:
    lda graphics_bitmap_row_lo,y
    sta zp_ptr1
    lda graphics_bitmap_row_hi,y
    sta zp_ptr1+1
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

; graphics_enter — X/Y → plan (+0 mode: 0=hires, 1=multicolor); C=error
.export graphics_enter
graphics_enter:
    stx zp_ptr1
    sty zp_ptr1+1
    ldy #0
    lda (zp_ptr1),y
    cmp #2
    bcs @bad_mode
    sta graphics_mode
    jsr hibasic_graphics_reserve
    jsr graphics_set_canonical

    lda CIA2_DDRA
    ora #$03
    sta CIA2_DDRA
    lda CIA2_PRA
    and #$fc                 ; VIC bank 3
    sta CIA2_PRA

    lda #D018_BITMAP
    sta VIC_MEM
    lda #D011_BITMAP
    sta VIC_CTRL1

    lda #D016_TEXT
    ldx graphics_mode
    beq @hires_ctrl2
    ora #$10                 ; multicolor
    bne @set_ctrl2
@hires_ctrl2:
    and #$ef
@set_ctrl2:
    sta VIC_CTRL2
    lda #0
    sta VIC_SPR_EN
    lda #1
    sta graphics_active
    lda #<MEM_TOP_BMP
    sta graphics_dynamic_ceiling
    lda #>MEM_TOP_BMP
    sta graphics_dynamic_ceiling+1
    jsr graphics_set_canonical
    clc
    rts
@bad_mode:
    jsr graphics_set_canonical
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; graphics_matrix_copy — X/Y → record: src.w, dest.w, len.w; C=error
; Copies through ram_under_io_copy_in in CHUNK-byte slices (IRQ between).
.export graphics_matrix_copy
graphics_matrix_copy:
    stx zp_ptr1
    sty zp_ptr1+1
    ldy #0
    lda (zp_ptr1),y
    sta zp_src
    iny
    lda (zp_ptr1),y
    sta zp_src+1
    iny
    lda (zp_ptr1),y
    sta graphics_copy_dest
    iny
    lda (zp_ptr1),y
    sta graphics_copy_dest+1
    iny
    lda (zp_ptr1),y
    sta graphics_copy_remain
    iny
    lda (zp_ptr1),y
    sta graphics_copy_remain+1

    lda graphics_copy_remain
    ora graphics_copy_remain+1
    bne @have_len
    jmp @ok
@have_len:
    ; dest >= $DC00
    lda graphics_copy_dest+1
    cmp #>MATRIX_BASE
    bcc @bad
    bne @check_end
    lda graphics_copy_dest
    cmp #<MATRIX_BASE
    bcc @bad
@check_end:
    ; last = dest+len-1 <= $DFE7
    lda graphics_copy_dest
    clc
    adc graphics_copy_remain
    tax
    lda graphics_copy_dest+1
    adc graphics_copy_remain+1
    tay
    txa
    bne @dec1
    dey
@dec1:
    dex
    cpy #>MATRIX_END
    bcc @loop
    bne @bad
    cpx #<MATRIX_END
    bcc @loop
    beq @loop
@bad:
    jsr graphics_set_canonical
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

@loop:
    lda graphics_copy_remain
    ora graphics_copy_remain+1
    beq @ok
    lda graphics_copy_remain+1
    bne @full
    lda graphics_copy_remain
    cmp #CHUNK+1
    bcc @use
@full:
    lda #CHUNK
@use:
    sta zp_tmp4
    ldx graphics_copy_dest
    ldy graphics_copy_dest+1
    lda zp_tmp4
    jsr ram_under_io_copy_in

    lda zp_src
    clc
    adc zp_tmp4
    sta zp_src
    bcc @src_ok
    inc zp_src+1
@src_ok:
    lda graphics_copy_dest
    clc
    adc zp_tmp4
    sta graphics_copy_dest
    bcc @dst_ok
    inc graphics_copy_dest+1
@dst_ok:
    lda graphics_copy_remain
    sec
    sbc zp_tmp4
    sta graphics_copy_remain
    bcs @loop
    dec graphics_copy_remain+1
    jmp @loop

@ok:
    jsr graphics_set_canonical
    clc
    rts

; graphics_validate_bounds — X/Y → desc: kind, x_lo, x_hi, y; C=out-of-bounds
; kind 0=pixel (0..319,0..199); 1/2=matrix/color cell (0..39,0..24)
; Pure cold compiler validation executes from a dedicated XIP page.  Callers
; pass the routine ID through georam_call_group_n_xy so X/Y survive the gate.
.segment "GEORAM_PAGE_45"
.export graphics_validate_bounds
graphics_validate_bounds:
    stx zp_ptr1
    sty zp_ptr1+1
    ldy #0
    lda (zp_ptr1),y
    beq @pixel
    cmp #3
    bcs @bad
    ; cell: x_hi==0, x_lo<=39, y<=24
    ldy #2
    lda (zp_ptr1),y
    bne @bad
    dey
    lda (zp_ptr1),y
    cmp #CELL_MAX_X+1
    bcs @bad
    ldy #3
    lda (zp_ptr1),y
    cmp #CELL_MAX_Y+1
    bcs @bad
    bcc @ok
@pixel:
    ldy #3
    lda (zp_ptr1),y
    cmp #MAX_Y+1
    bcs @bad
    ldy #2
    lda (zp_ptr1),y
    cmp #>MAX_X
    bcc @ok
    bne @bad
    dey
    lda (zp_ptr1),y
    cmp #<MAX_X+1
    bcs @bad
@ok:
    jsr graphics_validate_set_canonical
    clc
    rts
@bad:
    jsr graphics_validate_set_canonical
    sec
    rts

; Page-local: an XIP entry cannot JSR to the low-RAM graphics helper.
graphics_validate_set_canonical:
    lda #CPU_PORT_CANONICAL
    sta CPU_PORT
    rts

.assert * - graphics_validate_bounds <= $FA, error, "graphics_validate_bounds exceeds geoRAM page 45"

; graphics_exit — A=exit reason (reserved/ignored by gate setup); restore
; text/colors/ceiling.  Cold path only: enter via georam_call_group_n with
; X = GEORAM_ROUTINE_ID_GRAPHICS_EXIT (group-1 local index is the low byte).
.segment "GEORAM_PAGE_52"
.export graphics_exit
graphics_exit:
    lda #D011_TEXT
    sta VIC_CTRL1
    lda #D016_TEXT
    sta VIC_CTRL2
    lda #D018_TEXT
    sta VIC_MEM
    lda CIA2_DDRA
    ora #$03
    sta CIA2_DDRA
    lda CIA2_PRA
    ora #$03                 ; VIC bank 0
    sta CIA2_PRA
    lda #0
    sta VIC_BORDER
    sta VIC_SPR_EN
    sta graphics_mode
    sta graphics_active
    lda #$0e
    sta VIC_BG0
    lda #<MEM_TOP_TEXT
    sta graphics_dynamic_ceiling
    lda #>MEM_TOP_TEXT
    sta graphics_dynamic_ceiling+1
    ; Fall through: page-local canonical $01 restore (no low-RAM jsr).
graphics_exit_set_canonical:
    lda #CPU_PORT_CANONICAL
    sta CPU_PORT
    clc
    rts

.assert * - graphics_exit <= $FA, error, "graphics_exit exceeds geoRAM page 52"

; Shared: force $01 = canonical Compiler 2 mapping.
.segment "GRAPHICS"
graphics_set_canonical:
    lda #CPU_PORT_CANONICAL
    sta CPU_PORT
    rts
