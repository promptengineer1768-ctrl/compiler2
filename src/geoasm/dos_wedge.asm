; src/geoasm/dos_wedge.asm
; DOS wedge prefix recognition before BASIC tokenization.

.include "common/zp.inc"

zp_ptr1 = zp_tmptr

.segment "WEDGE"

; wedge_parse - Parse a development wedge prefix.
; Inputs: X/Y = captured text pointer. Outputs: A = $:0, @:1, /:2, !:3,
; or $FF for normal BASIC input. Side effects: none. Clobbers: A, Y.
; Flags: C clear. Zero page: reads/writes zp_tmptr.
.export wedge_parse
wedge_parse:
    stx zp_ptr1
    sty zp_ptr1+1
    ldy #0
    lda (zp_ptr1), y
    ldy #0
@scan:
    cmp @prefixes, y
    beq @found
    iny
    cpy #4
    bne @scan
    lda #$FF
    clc
    rts
@found:
    tya
    clc
    rts
@prefixes:
    .byte '$', '@', '/', '!'
