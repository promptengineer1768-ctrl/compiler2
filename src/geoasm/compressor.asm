; src/geoasm/compressor.asm
; SKELETON (design audit 2026-07-09) — does not meet DESIGN2 / GEORAM_LOADER.
;
; Previous bodies reported success without writing compressed output or
; decompressing CGS1 payloads. Re-implement against docs/GEORAM_LOADER_DESIGN.md
; and the dual-device install stream contract before treating as complete.

.include "common/zp.inc"
.include "common/constants.asm"

.segment "COMPRESSOR"

; compressor_rle - RLE compression (SKELETON)
; Input:  X/Y = source, A = length
; Output: C set, A = ERR_UNDEFINED_FUNCTION
.export compressor_rle
compressor_rle:
    lda #ERR_UNDEFINED_FUNCTION
    sec
    rts

; compressor_lz77 - LZ77 compression (SKELETON)
; Input:  X/Y = source, A = length
; Output: C set, A = ERR_UNDEFINED_FUNCTION
.export compressor_lz77
compressor_lz77:
    lda #ERR_UNDEFINED_FUNCTION
    sec
    rts

; compressor_stream - Streaming CGS1 decompression (SKELETON)
; Input:  X/Y = packed data pointer
; Output: C set, A = ERR_UNDEFINED_FUNCTION
.export compressor_stream
compressor_stream:
    lda #ERR_UNDEFINED_FUNCTION
    sec
    rts
