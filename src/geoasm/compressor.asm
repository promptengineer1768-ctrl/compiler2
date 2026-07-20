; src/geoasm/compressor.asm
; In-memory CGS1/RLE stream decompression for the installed loader.
;
; CGS1 disk-to-geoRAM streaming remains in georam_stream_reader.asm. This
; module handles the compact CGS1-framed RLE body consumed by
; loader_decompression.  Packing belongs to the host compressor artifact
; pipeline; shipping packers in the installed image was dead code.

.include "common/zp.inc"
.include "common/constants.asm"

; Working pointers (generated ZP)
zp_ptr1 = zp_tmptr
zp_ptr2 = zp_expr_ptr2

; Stream aliases into the 15-byte georam_stream block
zp_cgs_src = zp_georam_stream
zp_cgs_dst = zp_georam_stream + 2
zp_cgs_len = zp_georam_stream + 4
zp_cgs_out = zp_georam_stream + 6

; In-memory CGS1/RLE header (compact subset of the install stream contract):
;   0..3  'C''G''S''1'
;   4     algorithm id (1 = RLE)
;   5     reserved (0)
;   6..7  unpacked size (u16 LE), 1..255 for this RAM helper
;   8..   RLE body: repeated (count, value) pairs, count in 1..255
CGS_ALGO_RLE = 1

; Reuse the loader stage buffer as pack/unpack scratch. Safe because
; compressor_stream runs outside the active geoRAM staging window (install
; uses the buffer only while loading).
.import georam_stage_buffer
.import ram_under_io_enter, ram_under_io_exit
.export compressor_out_buffer
compressor_out_buffer = georam_stage_buffer

.segment "BSS"
.export compressor_out_length
compressor_out_length:
    .res 1

.segment "HIBASIC"

; compressor_stream is the only resident-facing compressor entry.  The body
; lives in RAM under I/O and is reached only while the RAM-under-I/O gate has
; masked interrupts and banked the I/O devices out.
.export compressor_stream
compressor_stream:
    jsr ram_under_io_enter
    jsr io_compressor_stream
    php
    pha
    jsr ram_under_io_exit
    pla
    plp
    rts

.segment "IO_COLD"

; =============================================================================
; compressor_stream - Decompress an in-memory CGS1/RLE stream
; Input:  X/Y = packed stream pointer
;         On entry zp_cgs_dst (zp_georam_stream+2) may hold dest; if both
;         bytes are zero, dest defaults to compressor_out_buffer.
; Output: C=0 success, A = unpacked length; C=1 and A=error on bad input
; Side effects: writes destination bytes and compressor_out_length
; Clobbers: A, X, Y
; =============================================================================
.export io_compressor_stream
io_compressor_stream:
    stx zp_cgs_src
    sty zp_cgs_src+1
    ; Default destination when unset
    lda zp_cgs_dst
    ora zp_cgs_dst+1
    bne @have_dst
    lda #<compressor_out_buffer
    sta zp_cgs_dst
    lda #>compressor_out_buffer
    sta zp_cgs_dst+1
@have_dst:
    ; Validate CGS1 magic
    ldy #0
    lda (zp_cgs_src),y
    cmp #'C'
    bne @bad_header
    iny
    lda (zp_cgs_src),y
    cmp #'G'
    bne @bad_header
    iny
    lda (zp_cgs_src),y
    cmp #'S'
    bne @bad_header
    iny
    lda (zp_cgs_src),y
    cmp #'1'
    bne @bad_header
    iny
    ; algorithm
    lda (zp_cgs_src),y
    cmp #CGS_ALGO_RLE
    bne @bad_header
    iny
    ; reserved
    iny
    ; unpacked size lo
    lda (zp_cgs_src),y
    sta zp_cgs_len
    iny
    lda (zp_cgs_src),y
    sta zp_cgs_len+1
    iny
    ; reject zero or >255 for this RAM helper
    lda zp_cgs_len+1
    bne @bad_header
    lda zp_cgs_len
    beq @bad_header
    ; body starts at offset 8; Y is already 8
    sty zp_tmp1                 ; packed index
    lda #0
    sta zp_tmp2                 ; unpacked count
@rle_loop:
    lda zp_tmp2
    cmp zp_cgs_len
    bcs @done
    ; need count,value
    ldy zp_tmp1
    lda (zp_cgs_src),y
    beq @bad_stream             ; count 0 illegal
    sta zp_tmp3                 ; count
    iny
    lda (zp_cgs_src),y
    sta zp_tmp4                 ; value
    iny
    sty zp_tmp1
@emit:
    lda zp_tmp2
    cmp zp_cgs_len
    bcs @bad_stream             ; would overrun declared size
    tay
    lda zp_tmp4
    sta (zp_cgs_dst),y
    inc zp_tmp2
    dec zp_tmp3
    bne @emit
    jmp @rle_loop
@done:
    sta compressor_out_length
    clc
    rts
@bad_header:
    lda #ERR_SYNTAX
    sec
    rts
@bad_stream:
    lda #ERR_FILE_DATA
    sec
    rts
