; src/resident/georam_gate.asm
; Resident expansion gate and geoRAM selection helpers.  The CPU-window copy
; routines below are the common byte-accurate path used by the current profile;
; device selection and profile validation are published by the detector.

.include "common/zp.inc"
.include "georam_pages.inc"

.export georam_group_0_blocks
.export georam_group_0_pages
.export georam_group_0_offsets
.export georam_group_1_blocks
.export georam_group_1_pages
.export georam_group_1_offsets
.exportzp GEORAM_DIRECTORY_GROUP_COUNT
.exportzp GEORAM_ROUTINE_COUNT
.exportzp GEORAM_DIRECTORY_XOR8
.exportzp GEORAM_DIRECTORY_CRC32_0
.exportzp GEORAM_DIRECTORY_CRC32_1
.exportzp GEORAM_DIRECTORY_CRC32_2
.exportzp GEORAM_DIRECTORY_CRC32_3
; Re-export generated routine IDs so resident callers never hardcode stale values.
.export GEORAM_ROUTINE_ID_EDITOR_SUBMIT_LINE
.export GEORAM_ROUTINE_ID_PIPELINE_COMPILE_LINE
.export GEORAM_ROUTINE_ID_DIRECT_EXECUTE_TEMPORARY

.import ctx_push
.import ctx_pop
.import ctx_init
; Full RAM_HIGH install image (hibasic.bin): EDITOR_PINNED through COMPRESSOR.
.import __EDITOR_PINNED_LOAD__, __COMPRESSOR_LOAD__, __COMPRESSOR_SIZE__

.segment "RESIDENT"

DESC_OFFSET    = 0
DESC_PAGE      = 1
DESC_LENGTH    = 2
DESC_PTR_LO    = 3
DESC_PTR_HI    = 4
DESC_VALUE_LO  = 5
DESC_VALUE_HI  = 6
GEORAM_WINDOW  = $DE00
GEORAM_PAGE    = $DFFE
GEORAM_BLOCK   = $DFFF

.segment "BSS"
georam_mirror_block: .res 1
georam_mirror_page:  .res 1
georam_ptr:          .res 2
georam_src_ptr:      .res 2
georam_dst_ptr:      .res 2
georam_count:        .res 1
georam_index:        .res 1
georam_src_index:    .res 1
georam_dst_index:    .res 1
georam_src_page:     .res 1
georam_dst_page:     .res 1
georam_saved_block:  .res 1
georam_saved_page:   .res 1
georam_copy_byte:    .res 1
georam_sum_lo:       .res 1
georam_sum_hi:       .res 1
georam_result_a:     .res 1
georam_result_x:     .res 1
georam_result_y:     .res 1
georam_result_p:     .res 1
hibasic_swap_active: .res 1
hibasic_swap_remain: .res 2
hibasic_swap_page:   .res 1
hibasic_swap_port:   .res 1

.segment "RESIDENT"

.export georam_call_group_n
.export georam_tail_group_n
.export georam_ctx_push
.export georam_ctx_pop
.export georam_select
.export georam_read_byte
.export georam_read_word
.export georam_write_byte
.export georam_write_word
.export georam_copy_from_ram
.export georam_copy_to_ram
.export georam_copy_pages
.export georam_checksum
.export georam_verify_mirror
.export hibasic_graphics_reserve
.export hibasic_graphics_restore

; The final 32 pages of the minimum 512 KiB device are a dedicated backing
; store. They are outside the 64 KiB release image installed in blocks 0-3.
; Covers the full hibasic.bin install ($E000..compressor end), which the
; VIC-II bitmap at $E000+ displaces for graphics-capable RUN (GRAPHICS_MEMORY).
HIBASIC_SWAP_BLOCK = 31
HIBASIC_SWAP_PAGE  = 32
CPU_PORT           = $01
hibasic_swap_ptr   = zp_tmptr
; Exclusive end of the RAM_HIGH install image.
HIBASIC_IMAGE_END  = __COMPRESSOR_LOAD__ + __COMPRESSOR_SIZE__
HIBASIC_IMAGE_SIZE = HIBASIC_IMAGE_END - __EDITOR_PINNED_LOAD__

; hibasic_graphics_reserve - Save occupied high-image bytes before bitmap use.
; Input: none. Output: C clear. Side effects: selects geoRAM and marks the
; graphics reservation active. Clobbers A, X, Y and flags. Zero page: geoRAM
; selection mirror only.
hibasic_graphics_reserve:
    lda hibasic_swap_active
    bne @reserve_done
    lda #<__EDITOR_PINNED_LOAD__
    sta hibasic_swap_ptr
    lda #>__EDITOR_PINNED_LOAD__
    sta hibasic_swap_ptr+1
    lda #<HIBASIC_IMAGE_SIZE
    sta hibasic_swap_remain
    lda #>HIBASIC_IMAGE_SIZE
    sta hibasic_swap_remain+1
    lda #HIBASIC_SWAP_PAGE
    sta hibasic_swap_page
    lda CPU_PORT
    sta hibasic_swap_port
    and #$fd                    ; expose RAM at $e000, retain I/O
    sta CPU_PORT
@reserve_page:
    ldx #HIBASIC_SWAP_BLOCK
    lda hibasic_swap_page
    jsr georam_select
    ldy #0
@reserve_byte:
    lda (hibasic_swap_ptr),y
    sta GEORAM_WINDOW,y
    lda hibasic_swap_remain
    bne :+
    dec hibasic_swap_remain+1
:
    dec hibasic_swap_remain
    lda hibasic_swap_remain
    ora hibasic_swap_remain+1
    beq @reserve_finish
    iny
    bne @reserve_byte
    inc hibasic_swap_ptr+1
    inc hibasic_swap_page
    bne @reserve_page
@reserve_finish:
    lda hibasic_swap_port
    sta CPU_PORT
    lda #1
    sta hibasic_swap_active
@reserve_done:
    clc
    rts

; hibasic_graphics_restore - Lazily restore displaced high-image bytes.
; Input: none. Output: C clear. Side effects: releases graphics reservation.
; Clobbers A, X, Y and flags. Zero page: geoRAM selection mirror only.
hibasic_graphics_restore:
    lda hibasic_swap_active
    beq @restore_done
    lda #<__EDITOR_PINNED_LOAD__
    sta hibasic_swap_ptr
    lda #>__EDITOR_PINNED_LOAD__
    sta hibasic_swap_ptr+1
    lda #<HIBASIC_IMAGE_SIZE
    sta hibasic_swap_remain
    lda #>HIBASIC_IMAGE_SIZE
    sta hibasic_swap_remain+1
    lda #HIBASIC_SWAP_PAGE
    sta hibasic_swap_page
    lda CPU_PORT
    sta hibasic_swap_port
    and #$fd
    sta CPU_PORT
@restore_page:
    ldx #HIBASIC_SWAP_BLOCK
    lda hibasic_swap_page
    jsr georam_select
    ldy #0
@restore_byte:
    lda GEORAM_WINDOW,y
    sta (hibasic_swap_ptr),y
    lda hibasic_swap_remain
    bne :+
    dec hibasic_swap_remain+1
:
    dec hibasic_swap_remain
    lda hibasic_swap_remain
    ora hibasic_swap_remain+1
    beq @restore_finish
    iny
    bne @restore_byte
    inc hibasic_swap_ptr+1
    inc hibasic_swap_page
    bne @restore_page
@restore_finish:
    lda hibasic_swap_port
    sta CPU_PORT
    lda #0
    sta hibasic_swap_active
@restore_done:
    clc
    rts

georam_ctx_push:
    jsr ctx_push
    rts

georam_ctx_pop:
    jsr ctx_pop
    bcs @fail
    lda zp_gr_block
    sta georam_mirror_block
    lda zp_gr_page
    sta georam_mirror_page
    sta GEORAM_PAGE
    lda zp_gr_block
    sta GEORAM_BLOCK
    clc
    rts
@fail:
    sec
    rts

georam_select:
    stx zp_gr_block
    sta zp_gr_page
    stx georam_mirror_block
    sta georam_mirror_page
    stx GEORAM_BLOCK
    sta GEORAM_PAGE
    rts

georam_verify_mirror:
    lda zp_gr_block
    cmp georam_mirror_block
    bne @fail
    lda zp_gr_page
    cmp georam_mirror_page
    bne @fail
    clc
    rts
@fail:
    sec
    rts

georam_call_group_n:
    stx zp_gr_call_id
    jsr ctx_push
    bcs @fail
    ldx zp_gr_call_id
    lda georam_group_1_blocks,x
    cmp #$FF
    beq @missing
    sta zp_gr_block
    sta georam_mirror_block
    sta GEORAM_BLOCK
    lda georam_group_1_pages,x
    cmp #$FF
    beq @missing
    sta zp_gr_page
    sta georam_mirror_page
    sta GEORAM_PAGE
    lda georam_group_1_offsets,x
    cmp #$FF
    beq @missing
    sta @target_jsr+1
    lda #>GEORAM_WINDOW
    sta @target_jsr+2
@target_jsr:
    jsr GEORAM_WINDOW
    php
    sta georam_result_a
    stx georam_result_x
    sty georam_result_y
    pla
    sta georam_result_p
    jsr georam_ctx_pop
    bcs @fail
    lda georam_result_a
    pha
    lda georam_result_p
    pha
    ldx georam_result_x
    ldy georam_result_y
    plp
    pla
    rts
@missing:
    jsr georam_ctx_pop
    bcs @fail
    lda #$00
    tax
    tay
    sec
    rts
@fail:
    sec
    rts

georam_call_group_0:
    stx zp_gr_call_id
    jsr ctx_push
    bcs @fail
    ldx zp_gr_call_id
    lda georam_group_0_blocks,x
    cmp #$FF
    beq @missing
    sta zp_gr_block
    sta georam_mirror_block
    sta GEORAM_BLOCK
    lda georam_group_0_pages,x
    cmp #$FF
    beq @missing
    sta zp_gr_page
    sta georam_mirror_page
    sta GEORAM_PAGE
    lda georam_group_0_offsets,x
    cmp #$FF
    beq @missing
    sta @target_jsr+1
    lda #>GEORAM_WINDOW
    sta @target_jsr+2
@target_jsr:
    jsr GEORAM_WINDOW
    php
    sta georam_result_a
    stx georam_result_x
    sty georam_result_y
    pla
    sta georam_result_p
    jsr georam_ctx_pop
    bcs @fail
    lda georam_result_a
    pha
    lda georam_result_p
    pha
    ldx georam_result_x
    ldy georam_result_y
    plp
    pla
    rts
@missing:
    jsr georam_ctx_pop
    bcs @fail
    lda #$00
    tax
    tay
    sec
    rts
@fail:
    sec
    rts

georam_call_group_1:
    jmp georam_call_group_n

georam_tail_group_n:
    lda zp_gr_ctx_sp
    beq @fail
    stx zp_gr_call_id
    ldx zp_gr_call_id
    lda georam_group_1_blocks,x
    cmp #$FF
    beq @missing
    sta zp_gr_block
    sta georam_mirror_block
    sta GEORAM_BLOCK
    lda georam_group_1_pages,x
    cmp #$FF
    beq @missing
    sta zp_gr_page
    sta georam_mirror_page
    sta GEORAM_PAGE
    lda georam_group_1_offsets,x
    cmp #$FF
    beq @missing
    sta @target_jmp+1
    lda #>GEORAM_WINDOW
    sta @target_jmp+2
    dec zp_gr_ctx_sp
@target_jmp:
    jmp GEORAM_WINDOW
@missing:
    lda #$00
    tax
    tay
    sec
    rts
@fail:
    sec
    rts

georam_load_descriptor:
    stx zp_src
    sty zp_src+1
    rts

georam_validate_descriptor_page:
    ldy #DESC_PAGE
    lda (zp_src),y
    cmp zp_gr_page
    rts

georam_read_byte:
    jsr georam_load_descriptor
    jsr georam_validate_descriptor_page
    bne @fail
    ldy #DESC_OFFSET
    lda (zp_src),y
    sta georam_index
    ldy georam_index
    lda GEORAM_WINDOW,y
    clc
    rts
@fail:
    lda #$00
    sec
    rts

georam_read_word:
    jsr georam_load_descriptor
    jsr georam_validate_descriptor_page
    bne @fail
    ldy #DESC_OFFSET
    lda (zp_src),y
    cmp #$FF
    beq @fail
    sta georam_index
    ldy georam_index
    lda GEORAM_WINDOW,y
    sta georam_sum_lo
    iny
    lda GEORAM_WINDOW,y
    tax
    lda georam_sum_lo
    ldy #$00
    clc
    rts
@fail:
    lda #$00
    ldx #$00
    ldy #$00
    sec
    rts

georam_write_byte:
    jsr georam_load_descriptor
    jsr georam_validate_descriptor_page
    bne @fail
    ldy #DESC_OFFSET
    lda (zp_src),y
    sta georam_index
    ldy #DESC_VALUE_LO
    lda (zp_src),y
    ldy georam_index
    sta GEORAM_WINDOW,y
    clc
    rts
@fail:
    sec
    rts

georam_write_word:
    jsr georam_load_descriptor
    jsr georam_validate_descriptor_page
    bne @fail
    ldy #DESC_OFFSET
    lda (zp_src),y
    cmp #$FF
    beq @fail
    sta georam_index
    ldy #DESC_VALUE_LO
    lda (zp_src),y
    ldy georam_index
    sta GEORAM_WINDOW,y
    iny
    ldy #DESC_VALUE_HI
    lda (zp_src),y
    ldy georam_index
    iny
    sta GEORAM_WINDOW,y
    clc
    rts
@fail:
    sec
    rts

georam_copy_from_ram:
    jsr georam_load_descriptor
    jsr georam_validate_descriptor_page
    bne @fail
    ldy #DESC_OFFSET
    lda (zp_src),y
    sta georam_index
    ldy #DESC_LENGTH
    lda (zp_src),y
    sta georam_count
    beq @done
    lda georam_index
    clc
    adc georam_count
    bcc @src
    bcs @fail
@src:
    ldy #DESC_PTR_LO
    lda (zp_src),y
    sta zp_dest
    iny
    lda (zp_src),y
    sta zp_dest+1
    ldy #$00
@copy:
    lda (zp_dest),y
    ldx georam_index
    sta GEORAM_WINDOW,x
    inc georam_index
    iny
    cpy georam_count
    bcc @copy
@done:
    clc
    rts
@fail:
    sec
    rts

georam_copy_to_ram:
    jsr georam_load_descriptor
    jsr georam_validate_descriptor_page
    bne @fail
    ldy #DESC_OFFSET
    lda (zp_src),y
    sta georam_index
    ldy #DESC_LENGTH
    lda (zp_src),y
    sta georam_count
    beq @done
    lda georam_index
    clc
    adc georam_count
    bcc @dst
    bcs @fail
@dst:
    ldy #DESC_PTR_LO
    lda (zp_src),y
    sta zp_dest
    iny
    lda (zp_src),y
    sta zp_dest+1
    ldy #$00
@copy:
    ldx georam_index
    lda GEORAM_WINDOW,x
    sta (zp_dest),y
    inc georam_index
    iny
    cpy georam_count
    bcc @copy
@done:
    clc
    rts
@fail:
    sec
    rts

georam_copy_pages:
    jsr georam_load_descriptor
    lda zp_gr_block
    sta georam_saved_block
    lda zp_gr_page
    sta georam_saved_page
    ldy #DESC_OFFSET
    lda (zp_src),y
    sta georam_src_index
    ldy #DESC_PAGE
    lda (zp_src),y
    sta georam_src_page
    ldy #DESC_LENGTH
    lda (zp_src),y
    sta georam_count
    beq @done
    lda georam_src_index
    clc
    adc georam_count
    bcs @fail
    ldy #DESC_PTR_LO
    lda (zp_src),y
    sta zp_dest
    iny
    lda (zp_src),y
    sta zp_dest+1
    ldy #DESC_OFFSET
    lda (zp_dest),y
    sta georam_dst_index
    ldy #DESC_PAGE
    lda (zp_dest),y
    sta georam_dst_page
    lda georam_dst_index
    clc
    adc georam_count
    bcs @fail
    ldy #$00
@copy:
    ldx #$00
    lda georam_src_page
    jsr georam_select
    ldx georam_src_index
    lda GEORAM_WINDOW,x
    sta georam_copy_byte
    ldx #$00
    lda georam_dst_page
    jsr georam_select
    ldx georam_dst_index
    lda georam_copy_byte
    sta GEORAM_WINDOW,x
    inc georam_src_index
    inc georam_dst_index
    iny
    cpy georam_count
    bcc @copy
@done:
    ldx georam_saved_block
    lda georam_saved_page
    jsr georam_select
    clc
    rts
@fail:
    ldx georam_saved_block
    lda georam_saved_page
    jsr georam_select
    sec
    rts

georam_checksum:
    jsr georam_load_descriptor
    jsr georam_validate_descriptor_page
    bne @fail
    ldy #DESC_OFFSET
    lda (zp_src),y
    sta georam_index
    ldy #DESC_LENGTH
    lda (zp_src),y
    sta georam_count
    lda #$00
    sta georam_sum_lo
    sta georam_sum_hi
    ldy #$00
@loop:
    ldx georam_index
    lda GEORAM_WINDOW,x
    clc
    adc georam_sum_lo
    sta georam_sum_lo
    bcc :+
    inc georam_sum_hi
:
    inc georam_index
    iny
    cpy georam_count
    bcc @loop
    lda georam_sum_lo
    ldx georam_sum_hi
    clc
    rts
@fail:
    lda #$00
    ldx #$00
    sec
    rts
