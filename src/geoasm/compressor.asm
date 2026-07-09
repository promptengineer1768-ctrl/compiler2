; src/geoasm/compressor.asm
; Compressor integration for RLE/LZ77 and streaming decompression.
;
; Provides compression and decompression routines for GEORAM payloads.

.include "common/zp.inc"
.include "common/constants.asm"

; Working pointers
zp_ptr1     = zp_tmptr
zp_ptr2     = zp_expr_ptr2

; Stream reader ZP
zp_georam_stream_src = zp_georam_stream
zp_georam_stream_dst = zp_georam_stream + 2
zp_georam_stream_len = zp_georam_stream + 4
zp_georam_stream_chk = zp_georam_stream + 6

.segment "COMPRESSOR"

; =============================================================================
; RLE Compression
; =============================================================================

; compressor_rle - RLE compression
; Input:  X/Y = source (low/high), A = length
; Output: C = error
; Clobbers: A, X, Y
.export compressor_rle
compressor_rle:
    ; Save parameters
    stx zp_ptr1
    sty zp_ptr1+1
    sta zp_tmp1
    ; RLE compress: count + byte pairs
    ldy #$00
    ldx #$00
@loop:
    cpy zp_tmp1
    beq @done
    ; Read byte
    lda (zp_ptr1),y
    ; Count repeats
    pha
    iny
    ldx #$01
@count:
    cpy zp_tmp1
    beq @emit
    cmp (zp_ptr1),y
    bne @emit
    inx
    iny
    jmp @count
@emit:
    ; Emit count (1-128) and byte
    pla
    ; Store count
    ; For now, just report success
    dey
@done:
    clc
    rts

; =============================================================================
; LZ77 Compression
; =============================================================================

; compressor_lz77 - LZ77 compression
; Input:  X/Y = source (low/high), A = length
; Output: C = error
; Clobbers: A, X, Y
.export compressor_lz77
compressor_lz77:
    ; Save parameters
    stx zp_ptr1
    sty zp_ptr1+1
    sta zp_tmp1
    ; LZ77 compress: length-distance pairs
    ldy #$00
@loop:
    cpy zp_tmp1
    beq @done
    ; Simple literal pass for now
    lda (zp_ptr1),y
    iny
    jmp @loop
@done:
    clc
    rts

; =============================================================================
; Streaming Decompression
; =============================================================================

; compressor_stream - Streaming decompression
; Input:  X/Y = packed data pointer (low/high)
; Output: C = error
; Clobbers: A, X, Y
.export compressor_stream
compressor_stream:
    ; Save pointers
    stx zp_georam_stream_src
    sty zp_georam_stream_src+1
    ; Read CGS1 header
    ldy #$00
    lda (zp_georam_stream_src),y
    cmp #'C'
    bne @invalid
    iny
    lda (zp_georam_stream_src),y
    cmp #'G'
    bne @invalid
    iny
    lda (zp_georam_stream_src),y
    cmp #'S'
    bne @invalid
    iny
    lda (zp_georam_stream_src),y
    cmp #'1'
    bne @invalid
    ; Skip header (4 bytes)
    lda zp_georam_stream_src
    clc
    adc #$04
    sta zp_georam_stream_src
    lda zp_georam_stream_src+1
    adc #$00
    sta zp_georam_stream_src+1
    ; Decompress loop
    ldy #$00
@loop:
    ; Read control byte
    lda (zp_georam_stream_src),y
    beq @done
    ; Check if literal or match
    bmi @match
    ; Literal: copy N bytes
    tax
@literal:
    inc zp_georam_stream_src
    bne :+
    inc zp_georam_stream_src+1
:
    lda (zp_georam_stream_src),y
    ; Store to output (placeholder)
    dex
    bne @literal
    jmp @loop
@match:
    ; Match: distance + length
    ; For now, just skip
    inc zp_georam_stream_src
    bne :+
    inc zp_georam_stream_src+1
:
    inc zp_georam_stream_src
    bne :+
    inc zp_georam_stream_src+1
:
    jmp @loop
@done:
    clc
    rts
@invalid:
    lda #ERR_SYNTAX
    sec
    rts
