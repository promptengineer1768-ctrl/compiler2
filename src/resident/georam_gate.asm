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
.export GEORAM_ROUTINE_ID_EDITOR_DELETE_LINE
.export GEORAM_ROUTINE_ID_EDITOR_READY_TRANSITION
.export GEORAM_ROUTINE_ID_EDITOR_DETOKENIZE_LINE
.export GEORAM_ROUTINE_ID_PROGRAM_LINES_PRINT_SELECTED_LINE_NUMBER
.export GEORAM_ROUTINE_ID_PIPELINE_COMPILE_LINE
.export GEORAM_ROUTINE_ID_PIPELINE_COMPILE_PROGRAM
.export GEORAM_ROUTINE_ID_DIRECT_EXECUTE_COMMAND
.export GEORAM_ROUTINE_ID_DIRECT_EXECUTE_TEMPORARY
.export GEORAM_ROUTINE_ID_WEDGE_PARSE
.export GEORAM_ROUTINE_ID_PROGRAM_ENCODE_STOCK
.export GEORAM_ROUTINE_ID_PROGRAM_ENCODE_BASIC35
.export GEORAM_ROUTINE_ID_PROGRAM_ENCODE_EXTENDED
.export GEORAM_ROUTINE_ID_PROGRAM_SELECT_SAVE_FORMAT
.export GEORAM_ROUTINE_ID_PROGRAM_TX_BEGIN
.export GEORAM_ROUTINE_ID_PROGRAM_TX_PUT_LINE
.export GEORAM_ROUTINE_ID_PROGRAM_TX_DELETE_LINE
.export GEORAM_ROUTINE_ID_PROGRAM_TX_COMMIT
.export GEORAM_ROUTINE_ID_PROGRAM_TX_ABORT
.export GEORAM_ROUTINE_ID_PROGRAM_REPLACE_FROM_LOAD
.export GEORAM_ROUTINE_ID_EXPORT_PARSE_COMMAND
.export GEORAM_ROUTINE_ID_EXPORT_COLLECT_DEPENDENCIES
.export GEORAM_ROUTINE_ID_EXPORT_LINK_IMAGE
.export GEORAM_ROUTINE_ID_EXPORT_CHECK_BUDGETS
.export GEORAM_ROUTINE_ID_EXPORT_WRITE_PRG
.export GEORAM_ROUTINE_ID_EXPORT_APPLY_SOFT_BUDGETS
.export GEORAM_ROUTINE_ID_EXPORT_SELECT_LAYOUT
.export GEORAM_ROUTINE_ID_COMPILER_INIT
.export GEORAM_ROUTINE_ID_INIT_ARENAS
.export GEORAM_ROUTINE_ID_INIT_EDITOR
.export GEORAM_ROUTINE_ID_INIT_ENTER_MAIN_LOOP
.export GEORAM_ROUTINE_ID_TOKEN_INIT
.export GEORAM_ROUTINE_ID_GRAPHICS_EXIT

.import ctx_push
.import ctx_pop
.import ctx_init
.import ctx_set_code_mapping
.import ctx_get_code_mapping
; Full RAM_HIGH install image (hibasic.bin): EDITOR_PINNED through WEDGE.
.import __EDITOR_PINNED_LOAD__, __WEDGE_LOAD__, __WEDGE_SIZE__

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
CPU_PORT       = $01
CTX_MAX_DEPTH  = 8

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
georam_arg_x:        .res 1
georam_arg_y:        .res 1
; Caller CPU-port mappings for nested group-1 XIP gates.  The entry selected
; at $DE00 is I/O, so XIP must run with the I/O-visible mapping; callers such
; as EDITOR execute from RAM under a different mapping and must get it back.
georam_xip_port_stack: .res CTX_MAX_DEPTH
georam_xip_restore_port: .res 1
georam_window_saved_port: .res 1
hibasic_swap_active: .res 1
hibasic_swap_remain: .res 2
hibasic_swap_page:   .res 1
hibasic_swap_port:   .res 1

.segment "RESIDENT"

.export georam_call_group_n
.export georam_call_group_n_xy
.export georam_call_group_0
.export georam_call_group_0_xy
.export georam_tail_group_n
.export georam_ctx_push
.export georam_ctx_pop
.export georam_restore_xip_code
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
hibasic_swap_ptr   = zp_tmptr
; Exclusive end of the RAM_HIGH install image.
HIBASIC_IMAGE_END  = __WEDGE_LOAD__ + __WEDGE_SIZE__
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
    lda zp_gr_page
    sta georam_mirror_page
    sta GEORAM_PAGE
    lda zp_gr_block
    sta georam_mirror_block
    sta GEORAM_BLOCK
    clc
    rts
@fail:
    sec
    rts

; georam_restore_xip_code - Re-select the active gate's instruction page.
; Input: none. Output: C=0.  With no active XIP gate this is a no-op.
; Clobbers: A, X, Y, flags.  Data-page helpers call this before returning to
; code that may be executing at $DE00.
georam_restore_xip_code:
    jsr ctx_get_code_mapping
    bcs @done
    jsr georam_select
@done:
    clc
    rts

; Save the caller port for this active context and expose I/O/geoRAM.  The
; context has already been pushed, so slot SP-1 belongs to this invocation.
georam_xip_open_io:
    ldx zp_gr_ctx_sp
    dex
    lda CPU_PORT
    sta georam_xip_port_stack,x
    ora #$07                    ; LORAM/HIRAM/CHAREN: I/O at $D000-$DFFF
    sta CPU_PORT
    rts

; Capture the saved caller port before popping the active context.  The pop
; itself still needs I/O visible to restore the geoRAM page selection.
georam_xip_prepare_close:
    ldx zp_gr_ctx_sp
    dex
    lda georam_xip_port_stack,x
    sta georam_xip_restore_port
    rts

georam_xip_finish_close:
    lda georam_xip_restore_port
    sta CPU_PORT
    rts

; Open the physical geoRAM window for a resident transfer.  The selected
; mirror is re-applied while I/O is visible, which lets high-RAM editor code
; prepare an arena selection without ever executing with its own bank hidden.
georam_window_open:
    lda CPU_PORT
    sta georam_window_saved_port
    ora #$07
    sta CPU_PORT
    ldx zp_gr_block
    stx GEORAM_BLOCK
    lda zp_gr_page
    sta GEORAM_PAGE
    rts

georam_window_close:
    lda georam_window_saved_port
    sta CPU_PORT
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
    jsr georam_xip_open_io
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
    ldx zp_gr_block
    lda zp_gr_page
    jsr ctx_set_code_mapping
    ldx zp_gr_call_id
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
    jsr georam_xip_prepare_close
    jsr georam_ctx_pop
    bcs @pop_fail
    jsr georam_xip_finish_close
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
    jsr georam_xip_prepare_close
    jsr georam_ctx_pop
    bcs @pop_fail
    jsr georam_xip_finish_close
    lda #$00
    tax
    tay
    sec
    rts
@fail:
    sec
    rts
@pop_fail:
    jsr georam_xip_finish_close
    sec
    rts

; georam_call_group_n_xy - Invoke a group-1 XIP routine while preserving
; caller-supplied X/Y as that routine's ABI arguments.  A is the group-local
; directory index; on return A/X/Y/flags are exactly those returned by XIP.
; The normal gate takes X as its selector, so this variant is required for
; descriptor-based XIP services such as the program codec.
georam_call_group_n_xy:
    sta zp_gr_call_id
    stx georam_arg_x
    sty georam_arg_y
    jsr ctx_push
    bcs @fail
    jsr georam_xip_open_io
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
    ldx zp_gr_block
    lda zp_gr_page
    jsr ctx_set_code_mapping
    ldx zp_gr_call_id
    lda georam_group_1_offsets,x
    cmp #$FF
    beq @missing
    sta @target_jsr+1
    lda #>GEORAM_WINDOW
    sta @target_jsr+2
    ldx georam_arg_x
    ldy georam_arg_y
@target_jsr:
    jsr GEORAM_WINDOW
    php
    sta georam_result_a
    stx georam_result_x
    sty georam_result_y
    pla
    sta georam_result_p
    jsr georam_xip_prepare_close
    jsr georam_ctx_pop
    bcs @pop_fail
    jsr georam_xip_finish_close
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
    jsr georam_xip_prepare_close
    jsr georam_ctx_pop
    bcs @pop_fail
    jsr georam_xip_finish_close
    lda #$00
    tax
    tay
    sec
    rts
@fail:
    sec
    rts
@pop_fail:
    jsr georam_xip_finish_close
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

; georam_call_group_0_xy - Group-0 XIP entry that preserves caller X/Y as the
; target routine's ABI arguments.  A is the group-0 directory index (global
; routine ID for IDs 0-255).  Mirrors georam_call_group_n_xy for early-group
; cold services such as token_init.
georam_call_group_0_xy:
    sta zp_gr_call_id
    stx georam_arg_x
    sty georam_arg_y
    jsr ctx_push
    bcs @fail
    jsr georam_xip_open_io
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
    ldx zp_gr_block
    lda zp_gr_page
    jsr ctx_set_code_mapping
    ldx zp_gr_call_id
    lda georam_group_0_offsets,x
    cmp #$FF
    beq @missing
    sta @target_jsr+1
    lda #>GEORAM_WINDOW
    sta @target_jsr+2
    ldx georam_arg_x
    ldy georam_arg_y
@target_jsr:
    jsr GEORAM_WINDOW
    php
    sta georam_result_a
    stx georam_result_x
    sty georam_result_y
    pla
    sta georam_result_p
    jsr georam_xip_prepare_close
    jsr georam_ctx_pop
    bcs @pop_fail
    jsr georam_xip_finish_close
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
    jsr georam_xip_prepare_close
    jsr georam_ctx_pop
    bcs @pop_fail
    jsr georam_xip_finish_close
    lda #$00
    tax
    tay
    sec
    rts
@fail:
    sec
    rts
@pop_fail:
    jsr georam_xip_finish_close
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
    jsr georam_window_open
    ldy #DESC_OFFSET
    lda (zp_src),y
    sta georam_index
    ldy #DESC_VALUE_LO
    lda (zp_src),y
    ldy georam_index
    sta GEORAM_WINDOW,y
    jsr georam_window_close
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
    jsr georam_window_open
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
    jsr georam_window_close
    clc
    rts
@fail:
    ; Only paths after georam_window_open reach @done; all validation and
    ; bounds failures occur before the window is opened.
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
