; src/geoasm/compressor.asm
; RLE compression and in-memory CGS1/RLE stream decompression.
;
; CGS1 disk-to-geoRAM streaming remains in georam_stream_reader.asm. This
; module handles RAM-side RLE packing and a compact CGS1-framed RLE body for
; loader_decompression and tests.

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
; compressor_rle / compressor_lz77 / compressor_stream run outside the
; active geoRAM staging window (install uses the buffer only while loading).
.import georam_stage_buffer
.export compressor_out_buffer
compressor_out_buffer = georam_stage_buffer

.segment "BSS"
.export compressor_out_length
compressor_out_length:
    .res 1

.segment "COMPRESSOR"

; =============================================================================
; compressor_rle - RLE-compress a source buffer into compressor_out_buffer
; Input:  X/Y = source (low/high), A = length (1..255)
; Output: C=0, A = packed length; C=1 and A=error on bad input
; Side effects: writes compressor_out_buffer / compressor_out_length
; Clobbers: A, X, Y
; =============================================================================
.export compressor_rle
compressor_rle:
    cmp #0
    beq @bad
    stx zp_ptr1
    sty zp_ptr1+1
    sta zp_tmp1                 ; remaining / total length
    lda #<compressor_out_buffer
    sta zp_ptr2
    lda #>compressor_out_buffer
    sta zp_ptr2+1
    lda #0
    sta compressor_out_length
    sta zp_tmp2                 ; source index
@run:
    lda zp_tmp2
    cmp zp_tmp1
    bcs @done
    ; load first byte of run
    ldy zp_tmp2
    lda (zp_ptr1),y
    sta zp_tmp3                 ; run value
    ldx #1                      ; run count
    iny
@count:
    cpy zp_tmp1
    bcs @emit
    lda (zp_ptr1),y
    cmp zp_tmp3
    bne @emit
    inx
    beq @emit_full              ; cap at 255 (X wrapped)
    iny
    jmp @count
@emit_full:
    ldx #255
    ; Y still at first unconsumed byte of a long run
@emit:
    sty zp_tmp2                 ; next source index
    ; emit count, value
    lda compressor_out_length
    cmp #254
    bcs @overflow
    tay
    txa
    sta (zp_ptr2),y
    iny
    lda zp_tmp3
    sta (zp_ptr2),y
    iny
    sty compressor_out_length
    jmp @run
@done:
    lda compressor_out_length
    beq @bad                    ; produced nothing
    clc
    rts
@overflow:
    lda #ERR_OVERFLOW
    sec
    rts
@bad:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; =============================================================================
; compressor_lz77 - simple all-literal LZSS-style pack into compressor_out_buffer
; Input:  X/Y = source, A = length (1..127 for single-token form)
; Output: C=0, A = packed length; C=1 on bad input
; Format: for each run of up to 128 literals: token = (n-1) with bit7 clear,
;         followed by n literal bytes (compatible with CGS1 chunk tokens).
; Clobbers: A, X, Y
; =============================================================================
.export compressor_lz77
compressor_lz77:
    cmp #0
    beq @bad
    cmp #129
    bcs @bad
    stx zp_ptr1
    sty zp_ptr1+1
    sta zp_tmp1
    lda #<compressor_out_buffer
    sta zp_ptr2
    lda #>compressor_out_buffer
    sta zp_ptr2+1
    ; token = length - 1 (high bit clear => literal)
    lda zp_tmp1
    sec
    sbc #1
    ldy #0
    sta (zp_ptr2),y
    iny
    ldx #0
@copy:
    txa
    pha
    tay
    lda (zp_ptr1),y
    sta zp_tmp2
    pla
    tax
    txa
    clc
    adc #1
    tay
    lda zp_tmp2
    sta (zp_ptr2),y
    inx
    cpx zp_tmp1
    bcc @copy
    lda zp_tmp1
    clc
    adc #1
    sta compressor_out_length
    clc
    rts
@bad:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; =============================================================================
; compressor_stream - Decompress an in-memory CGS1/RLE stream
; Input:  X/Y = packed stream pointer
;         On entry zp_cgs_dst (zp_georam_stream+2) may hold dest; if both
;         bytes are zero, dest defaults to compressor_out_buffer.
; Output: C=0 success, A = unpacked length; C=1 and A=error on bad input
; Side effects: writes destination bytes and compressor_out_length
; Clobbers: A, X, Y
; =============================================================================
.export compressor_stream
compressor_stream:
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
    sta compressor_out_length
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
    ; exact size required
    lda zp_tmp2
    cmp zp_cgs_len
    bne @bad_stream
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
