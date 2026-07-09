; src/loader/georam_stream_reader.asm
; ca65 port of the compressor project's CGS1 geoRAM stream reader.

.include "common/zp.inc"

SETNAM = $FFBD
SETLFS = $FFBA
OPEN   = $FFC0
CLOSE  = $FFC3
CHKIN  = $FFC6
CLRCHN = $FFCC
CHRIN  = $FFCF

gsrc_remain_lo = gsrc_state + 0
gsrc_remain_hi = gsrc_state + 1
gsrc_dest_lo   = gsrc_state + 2
gsrc_dest_hi   = gsrc_state + 3
gsrc_match_lo  = gsrc_state + 4
gsrc_match_hi  = gsrc_state + 5
gsrc_temp      = gsrc_state + 6
gsrc_token     = gsrc_state + 7
gsrc_offset_hi = gsrc_state + 8
gsrc_block     = gsrc_state + 9
gsrc_page      = gsrc_state + 10
gsrc_page_hi   = gsrc_state + 11
gsrc_chunks_lo = gsrc_state + 12
gsrc_chunks_hi = gsrc_state + 13
gsrc_byte      = gsrc_state + 14

.segment "CODE"
gsrc_state:
    .res 15
.export georam_stream_device
georam_stream_device:
    .byte 8
gsrc_directory_index:
    .byte 0
gsrc_chunk_blocks:
    .res 8
gsrc_chunk_pages:
    .res 8
gsrc_chunk_page_high:
    .res 8

; georam_stream_load - Stream a fake-header PRG CGS1 sidecar into geoRAM.
; Inputs: A=filename length, X/Y=filename pointer; device in exported state.
; Outputs: C clear on success, set on KERNAL/signature failure.
; Side effects: KERNAL channel 1 and geoRAM window/register writes.
; Clobbers: A, X, Y. Flags: C=error.
; Zero page: reads/writes all 15 bytes of generated zp_georam_stream.
.export georam_stream_load
georam_stream_load:
    jsr SETNAM
    lda #2
    ldx georam_stream_device
    ldy #2
    jsr SETLFS
    jsr OPEN
    bcc :+
    jmp @open_failed
:
    ldx #2
    jsr CHKIN
    bcc :+
    jmp @close_failed
:

    jsr _gsrc_skip_u16
    jsr _gsrc_read_byte
    cmp #'C'
    beq :+
    jmp @close_failed
:
    jsr _gsrc_read_byte
    cmp #'G'
    beq :+
    jmp @close_failed
:
    jsr _gsrc_read_byte
    cmp #'S'
    beq :+
    jmp @close_failed
:
    jsr _gsrc_read_byte
    cmp #'1'
    beq :+
    jmp @close_failed
:

    jsr _gsrc_skip_u16
    jsr _gsrc_read_byte
    sta gsrc_chunks_lo
    jsr _gsrc_read_byte
    sta gsrc_chunks_hi
    jsr _gsrc_skip_u32
    jsr _gsrc_skip_u16
    jsr _gsrc_read_byte
    jsr _gsrc_read_byte
    jsr _gsrc_skip_u32
    jsr _gsrc_skip_u32
    jsr _gsrc_skip_u32

    lda gsrc_chunks_hi
    bne @close_failed
    lda gsrc_chunks_lo
    cmp #9
    bcs @close_failed
    lda #0
    sta gsrc_directory_index

; CGS1 stores the complete chunk directory before all packed payloads.
@directory_loop:
    ldx gsrc_directory_index
    cpx gsrc_chunks_lo
    beq @payload_start
    jsr _gsrc_read_byte
    ldx gsrc_directory_index
    sta gsrc_chunk_blocks,x
    jsr _gsrc_read_byte
    ldx gsrc_directory_index
    sta gsrc_chunk_pages,x
    jsr _gsrc_read_byte
    ldx gsrc_directory_index
    sta gsrc_chunk_page_high,x
    jsr _gsrc_skip_u32
    jsr _gsrc_skip_u32
    jsr _gsrc_skip_u32
    jsr _gsrc_skip_u32
    jsr _gsrc_skip_u32
    inc gsrc_directory_index
    jmp @directory_loop

@payload_start:
    lda #0
    sta gsrc_directory_index
@payload_loop:
    ldx gsrc_directory_index
    cpx gsrc_chunks_lo
    beq @done
    lda gsrc_chunk_blocks,x
    sta gsrc_block
    lda gsrc_chunk_pages,x
    sta gsrc_page
    lda gsrc_chunk_page_high,x
    sta gsrc_page_hi
    jsr _gsrc_decompress_chunk
    inc gsrc_directory_index
    jmp @payload_loop

@done:
    jsr CLRCHN
    lda #2
    jsr CLOSE
    clc
    rts
@close_failed:
    jsr CLRCHN
    lda #2
    jsr CLOSE
@open_failed:
    sec
    rts

_gsrc_read_byte:
    jsr CHRIN
    rts

_gsrc_skip_u16:
    jsr _gsrc_read_byte
    jmp _gsrc_read_byte

_gsrc_skip_u32:
    jsr _gsrc_read_byte
    jsr _gsrc_read_byte
    jsr _gsrc_read_byte
    jmp _gsrc_read_byte

_gsrc_decompress_chunk:
    jsr _gsrc_read_byte
    sta gsrc_remain_lo
    jsr _gsrc_read_byte
    sta gsrc_remain_hi
    jsr _gsrc_read_byte
    jsr _gsrc_read_byte
    lda #0
    sta gsrc_dest_lo
    sta gsrc_dest_hi
@main_loop:
    lda gsrc_remain_lo
    ora gsrc_remain_hi
    bne :+
    jmp @chunk_done
:
    jsr _gsrc_read_byte
    sta gsrc_token
    bmi @match
    and #$7F
    tax
    inx
@literal_loop:
    jsr _gsrc_read_byte
    jsr _gsrc_write_byte
    jsr _gsrc_consume_byte
    dex
    bne @literal_loop
    jmp @main_loop
@match:
    lda gsrc_token
    asl
    bmi @long_match
    lda gsrc_token
    and #$3F
    sta gsrc_temp
    sec
    lda gsrc_dest_lo
    sbc gsrc_temp
    sta gsrc_match_lo
    lda gsrc_dest_hi
    sbc #0
    sta gsrc_match_hi
    lda gsrc_match_lo
    bne :+
    dec gsrc_match_hi
:
    dec gsrc_match_lo
    ldx #2
    jmp @copy_match
@long_match:
    lda gsrc_token
    and #$0F
    clc
    adc #3
    sta gsrc_temp
    cmp #18
    bne @read_offset
@extend_len:
    jsr _gsrc_read_byte
    tay
    clc
    adc gsrc_temp
    sta gsrc_temp
    cpy #255
    beq @extend_len
@read_offset:
    lda gsrc_token
    lsr
    lsr
    lsr
    lsr
    and #$03
    sta gsrc_offset_hi
    jsr _gsrc_read_byte
    sta gsrc_match_lo
    sec
    lda gsrc_dest_lo
    sbc gsrc_match_lo
    sta gsrc_match_lo
    lda gsrc_dest_hi
    sbc gsrc_offset_hi
    sta gsrc_match_hi
    lda gsrc_match_lo
    bne :+
    dec gsrc_match_hi
:
    dec gsrc_match_lo
    ldx gsrc_temp
@copy_match:
    jsr _gsrc_read_georam_match_byte
    jsr _gsrc_write_byte
    jsr _gsrc_advance_match
    jsr _gsrc_consume_byte
    dex
    bne @copy_match
    jmp @main_loop
@chunk_done:
    rts

_gsrc_set_window_dest:
    lda gsrc_dest_hi
    jmp _gsrc_set_window

_gsrc_set_window_match:
    lda gsrc_match_hi

_gsrc_set_window:
    sta gsrc_temp
    lda gsrc_page_hi
    sta gsrc_offset_hi
    lda gsrc_temp
    clc
    adc gsrc_page
@page_loop:
    cmp #$40
    bcc @page_ready
    sec
    sbc #$40
    inc gsrc_offset_hi
    jmp @page_loop
@page_ready:
    sta $DFFE
    lda gsrc_block
    clc
    adc gsrc_offset_hi
    sta $DFFF
    rts

_gsrc_write_byte:
    sta gsrc_byte
    jsr _gsrc_set_window_dest
    ldy gsrc_dest_lo
    lda gsrc_byte
    sta $DE00, y
    inc gsrc_dest_lo
    bne :+
    inc gsrc_dest_hi
:
    rts

_gsrc_read_georam_match_byte:
    jsr _gsrc_set_window_match
    ldy gsrc_match_lo
    lda $DE00, y
    rts

_gsrc_advance_match:
    inc gsrc_match_lo
    bne :+
    inc gsrc_match_hi
:
    rts

_gsrc_consume_byte:
    lda gsrc_remain_lo
    bne :+
    dec gsrc_remain_hi
:
    dec gsrc_remain_lo
    rts
