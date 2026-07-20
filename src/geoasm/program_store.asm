; src/geoasm/program_store.asm
; Arena-backed transactional store for normalized tokenized programs.
;
; A normalized program is a sequence of:
;   record_length:u16, line_number:u16, token_body:record_length-2 bytes
; followed by a zero record_length. token_body includes its terminating zero.
;
; Public machine records are deliberately distinct:
;   PS (8 bytes): "PS", byte_length:u16, arena, generation, start_page, reserved
;   PT (8 bytes): "PT", active, tx_generation, base_generation:u16, reserved:u16
;   PP (8 bytes): "PP", PT pointer:u16, one-line PS pointer:u16, reserved:u16
;   PD (8 bytes): "PD", PT pointer:u16, line_number:u16, reserved:u16

.include "common/zp.inc"
.include "common/constants.asm"
.include "arena_layout.inc"

.import arena_handle_valid
.import arena_select_page
.import georam_restore_xip_code

.macro jcs target
    bcc *+5
    jmp target
.endmacro
.macro jcc target
    bcs *+5
    jmp target
.endmacro
.macro jeq target
    bne *+5
    jmp target
.endmacro
.macro jne target
    beq *+5
    jmp target
.endmacro

PS_LENGTH_LO = 2
PS_LENGTH_HI = 3
PS_ARENA = 4
PS_GENERATION = 5
PS_START_PAGE = 6
PS_RESERVED = 7

PT_ACTIVE = $A5
PT_STATE = 2
PT_TX_GENERATION = 3
PT_BASE_GENERATION_LO = 4
PT_BASE_GENERATION_HI = 5
PT_RESERVED_LO = 6
PT_RESERVED_HI = 7

PROGRAM_ARENA = ARENA_TYPE_TOKENIZED_PROGRAM
STAGING_ARENA = ARENA_TYPE_PROGRAM_STAGING
PROGRAM_ARENA_GENERATION = 1
PROGRAM_MAX_PAGES = ARENA_MIN_PAGES_TOKENIZED_PROGRAM
STAGING_MAX_PAGES = ARENA_MIN_PAGES_PROGRAM_STAGING

.segment "BSS"

; Stable publication and transaction roots. Only the publication PS is exposed;
; callers receive and validate typed descriptors, never backing buffers.
.export __program_store_published
__program_store_published: .res 8
program_store_staging:     .res 8
program_store_transaction: .res 8

program_store_ready:             .res 1
program_store_source_generation: .res 2
program_store_tx_counter:        .res 1

program_store_request_ptr: .res 2
program_store_line_ptr:    .res 2

; Source cursor/descriptor.
program_store_src_desc:       .res 2
program_store_src_length:     .res 2
program_store_src_arena:      .res 1
program_store_src_generation: .res 1
program_store_src_start_page: .res 1
program_store_src_index:      .res 2

; Destination cursor/descriptor.
program_store_dst_desc:       .res 2
program_store_dst_length:     .res 2
program_store_dst_arena:      .res 1
program_store_dst_generation: .res 1
program_store_dst_start_page: .res 1
program_store_dst_index:      .res 2

program_store_value:       .res 1
program_store_record_len:  .res 2
program_store_record_total:.res 2
program_store_record_end:  .res 2
program_store_previous_line:.res 2
program_store_current_line: .res 2
program_store_requested_line:.res 2
program_store_have_line:    .res 1
program_store_insert_at:    .res 2
program_store_tail_at:      .res 2
program_store_old_total:    .res 2
program_store_new_total:    .res 2
program_store_new_length:   .res 2
program_store_delta:        .res 2
program_store_found:        .res 1

; Public read-side adapter workspace.  This is metadata only: published
; program bytes remain in the tokenized-program arena.
program_store_copy_left:      .res 2
program_store_copy_target:    .res 1
program_store_copy_index:     .res 1
.export program_store_selected_line_number
program_store_selected_line_number: .res 2

.segment "GEOASM"

; program_store_line_count
; Purpose: return the number of records in the published normalized stream.
; Inputs: none. Outputs: A=count, C=0; C=1/A=error.
; Clobbers: A, X, Y. Side effects: none.
; Zero page: zp_expr_ptr1.
.export program_store_line_count
program_store_line_count:
    jsr program_store_ensure_ready
    jcs @error
    ldx #<__program_store_published
    ldy #>__program_store_published
    jsr program_store_probe_src
    jcs @error
    jsr program_store_validate_src
    jcs @error
    lda #$00
    sta program_store_src_index
    sta program_store_src_index+1
    sta program_store_copy_index
@record:
    jsr program_store_read_src
    jcs @error
    sta program_store_record_len
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_record_len+1
    jsr program_store_inc_src
    lda program_store_record_len
    ora program_store_record_len+1
    beq @done
    inc program_store_copy_index
    beq @error
    lda program_store_src_index
    clc
    adc program_store_record_len
    sta program_store_src_index
    lda program_store_src_index+1
    adc program_store_record_len+1
    sta program_store_src_index+1
    jmp @record
@done:
    lda program_store_copy_index
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; program_store_copy_line_body_at
; Purpose: copy one published line body (including its NUL) into caller RAM.
; Inputs: A=zero-based sorted line index, X/Y=destination pointer (at least
;         81 bytes for editor input). Outputs: C=0; C=1/A=error.
; Clobbers: A, X, Y. Side effects: selects arena pages only.
; Zero page: zp_expr_ptr1.
.export program_store_copy_line_body_at
program_store_copy_line_body_at:
    sta program_store_copy_target
    stx zp_dest
    sty zp_dest+1
    jsr program_store_ensure_ready
    jcs @error
    ldx #<__program_store_published
    ldy #>__program_store_published
    jsr program_store_probe_src
    jcs @error
    jsr program_store_validate_src
    jcs @error
    lda #$00
    sta program_store_src_index
    sta program_store_src_index+1
    sta program_store_copy_index
@record:
    jsr program_store_read_src
    jcs @error
    sta program_store_record_len
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_record_len+1
    jsr program_store_inc_src
    lda program_store_record_len
    ora program_store_record_len+1
    jeq @error
    lda program_store_copy_index
    cmp program_store_copy_target
    beq @copy
    lda program_store_src_index
    clc
    adc program_store_record_len
    sta program_store_src_index
    lda program_store_src_index+1
    adc program_store_record_len+1
    sta program_store_src_index+1
    inc program_store_copy_index
    bne @record
    jmp @error
@copy:
    ; Skip line number, then copy record_length-2 body bytes (incl. NUL).
    jsr program_store_read_src
    jcs @error
    sta program_store_selected_line_number
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_selected_line_number+1
    jsr program_store_inc_src
    lda program_store_record_len
    sec
    sbc #$02
    sta program_store_copy_left
    lda program_store_record_len+1
    sbc #$00
    sta program_store_copy_left+1
    ldy #$00
@byte:
    lda program_store_copy_left
    ora program_store_copy_left+1
    beq @done
    jsr program_store_read_src
    jcs @error
    sta (zp_dest),y
    jsr program_store_inc_src
    inc zp_dest
    bne :+
    inc zp_dest+1
:
    lda program_store_copy_left
    bne :+
    dec program_store_copy_left+1
:
    dec program_store_copy_left
    jmp @byte
@done:
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; Select the source byte's page and return the byte in A.
.proc program_store_read_src
    lda program_store_src_index+1
    clc
    adc program_store_src_start_page
    bcs @error
    ldx program_store_src_arena
    ldy program_store_src_generation
    jsr arena_select_page
    bcs @error
    ldy program_store_src_index
    lda $DE00,y
    pha
    jsr georam_restore_xip_code
    pla
    clc
    rts
@error:
    jsr georam_restore_xip_code
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Write program_store_value at the destination cursor.
.proc program_store_write_dst
    lda program_store_dst_index+1
    clc
    adc program_store_dst_start_page
    bcs @error
    ldx program_store_dst_arena
    ldy program_store_dst_generation
    jsr arena_select_page
    bcs @error
    ldy program_store_dst_index
    lda program_store_value
    sta $DE00,y
    jsr georam_restore_xip_code
    clc
    rts
@error:
    jsr georam_restore_xip_code
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

.proc program_store_inc_src
    inc program_store_src_index
    bne :+
    inc program_store_src_index+1
:
    rts
.endproc

.proc program_store_inc_dst
    inc program_store_dst_index
    bne :+
    inc program_store_dst_index+1
:
    rts
.endproc

; Load and validate a PS into the source cursor.
; Inputs: X/Y=PS pointer. Outputs: C=error. Clobbers: A/X/Y.
.proc program_store_probe_src
    stx program_store_src_desc
    sty program_store_src_desc+1
    stx zp_expr_ptr1
    sty zp_expr_ptr1+1
    ldy #$00
    lda (zp_expr_ptr1),y
    cmp #'P'
    jne @error
    iny
    lda (zp_expr_ptr1),y
    cmp #'S'
    jne @error
    ldy #PS_LENGTH_LO
    lda (zp_expr_ptr1),y
    sta program_store_src_length
    iny
    lda (zp_expr_ptr1),y
    sta program_store_src_length+1
    iny
    lda (zp_expr_ptr1),y
    sta program_store_src_arena
    tax
    iny
    lda (zp_expr_ptr1),y
    sta program_store_src_generation
    tay
    jsr arena_handle_valid
    jcs @error
    lda program_store_src_desc
    sta zp_expr_ptr1
    lda program_store_src_desc+1
    sta zp_expr_ptr1+1
    ldy #PS_START_PAGE
    lda (zp_expr_ptr1),y
    sta program_store_src_start_page
    iny
    lda (zp_expr_ptr1),y
    jne @error
    lda program_store_src_length
    bne @nonempty
    lda program_store_src_length+1
    beq @first_page
@nonempty:
    lda program_store_src_length
    bne :+
    lda program_store_src_length+1
    sec
    sbc #$01
    jmp @extent
:
    lda program_store_src_length+1
@extent:
    clc
    adc program_store_src_start_page
    jcs @error
    jmp @select
@first_page:
    lda program_store_src_start_page
@select:
    ldx program_store_src_arena
    ldy program_store_src_generation
    jsr arena_select_page
    jcs @error
    jsr georam_restore_xip_code
    clc
    rts
@error:
    jsr georam_restore_xip_code
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Load and validate a PS into the destination cursor.
; Inputs: X/Y=PS pointer. Outputs: C=error. Clobbers: A/X/Y.
.proc program_store_probe_dst
    stx program_store_dst_desc
    sty program_store_dst_desc+1
    stx zp_expr_ptr1
    sty zp_expr_ptr1+1
    ldy #$00
    lda (zp_expr_ptr1),y
    cmp #'P'
    jne @error
    iny
    lda (zp_expr_ptr1),y
    cmp #'S'
    jne @error
    ldy #PS_LENGTH_LO
    lda (zp_expr_ptr1),y
    sta program_store_dst_length
    iny
    lda (zp_expr_ptr1),y
    sta program_store_dst_length+1
    iny
    lda (zp_expr_ptr1),y
    sta program_store_dst_arena
    tax
    iny
    lda (zp_expr_ptr1),y
    sta program_store_dst_generation
    tay
    jsr arena_handle_valid
    jcs @error
    lda program_store_dst_desc
    sta zp_expr_ptr1
    lda program_store_dst_desc+1
    sta zp_expr_ptr1+1
    ldy #PS_START_PAGE
    lda (zp_expr_ptr1),y
    sta program_store_dst_start_page
    iny
    lda (zp_expr_ptr1),y
    jne @error
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Store destination length last, making it the PS publication field.
.proc program_store_publish_dst_length
    lda program_store_dst_desc
    sta zp_expr_ptr1
    lda program_store_dst_desc+1
    sta zp_expr_ptr1+1
    ldy #PS_LENGTH_HI
    lda program_store_dst_length+1
    sta (zp_expr_ptr1),y
    dey
    lda program_store_dst_length
    sta (zp_expr_ptr1),y
    clc
    rts
.endproc

; Validate the complete normalized source payload.
; Inputs: source descriptor already probed. Outputs: C=error.
.proc program_store_validate_src
    lda #$00
    sta program_store_src_index
    sta program_store_src_index+1
    sta program_store_have_line
    sta program_store_previous_line
    sta program_store_previous_line+1
@record:
    ; Two length bytes must remain.
    lda program_store_src_index
    clc
    adc #$02
    sta program_store_record_end
    lda program_store_src_index+1
    adc #$00
    sta program_store_record_end+1
    lda program_store_record_end+1
    cmp program_store_src_length+1
    bcc @read_length
    jne @error
    lda program_store_record_end
    cmp program_store_src_length
    bcc @read_length
    beq @read_length
    jmp @error
@read_length:
    jsr program_store_read_src
    jcs @error
    sta program_store_record_len
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_record_len+1
    jsr program_store_inc_src
    lda program_store_record_len
    ora program_store_record_len+1
    bne @nonterminal
    lda program_store_src_index
    cmp program_store_src_length
    jne @error
    lda program_store_src_index+1
    cmp program_store_src_length+1
    jne @error
    clc
    rts
@nonterminal:
    lda program_store_record_len+1
    bne @length_ok
    lda program_store_record_len
    cmp #$03
    jcc @error
@length_ok:
    lda program_store_src_index
    clc
    adc program_store_record_len
    sta program_store_record_end
    lda program_store_src_index+1
    adc program_store_record_len+1
    sta program_store_record_end+1
    jcs @error
    lda program_store_record_end+1
    cmp program_store_src_length+1
    bcc @line
    jne @error
    lda program_store_record_end
    cmp program_store_src_length
    bcc @line
    beq @line
    jmp @error
@line:
    jsr program_store_read_src
    jcs @error
    sta program_store_current_line
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_current_line+1
    lda program_store_current_line
    sta program_store_requested_line
    lda program_store_current_line+1
    sta program_store_requested_line+1
    jsr program_store_inc_src
    lda program_store_have_line
    beq @ordered
    lda program_store_current_line+1
    cmp program_store_previous_line+1
    bcc @error
    bne @ordered
    lda program_store_current_line
    cmp program_store_previous_line
    bcc @error
    beq @error
@ordered:
    lda program_store_current_line
    sta program_store_previous_line
    lda program_store_current_line+1
    sta program_store_previous_line+1
    lda #$01
    sta program_store_have_line
    ; The final byte of every record is the token-body terminator.
    lda program_store_record_end
    bne :+
    dec program_store_record_end+1
:
    dec program_store_record_end
    lda program_store_record_end
    sta program_store_src_index
    lda program_store_record_end+1
    sta program_store_src_index+1
    jsr program_store_read_src
    jcs @error
    bne @error
    inc program_store_src_index
    bne :+
    inc program_store_src_index+1
:
    jmp @record
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Validate that source is exactly one normalized record plus terminal marker.
.proc program_store_validate_line_src
    jsr program_store_validate_src
    jcs @error
    lda program_store_src_length
    cmp #$07
    bcc @error
    lda #$00
    sta program_store_src_index
    sta program_store_src_index+1
    jsr program_store_read_src
    jcs @error
    sta program_store_record_len
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_record_len+1
    lda program_store_record_len
    clc
    adc #$04
    cmp program_store_src_length
    bne @error
    lda program_store_record_len+1
    clc
    adc #$00
    cmp program_store_src_length+1
    bne @error
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Copy source to destination after both descriptors have been probed.
; Destination capacity is selected from its dedicated arena type.
.proc program_store_clone
    lda program_store_dst_arena
    cmp #PROGRAM_ARENA
    beq @program_capacity
    cmp #STAGING_ARENA
    bne @error
    lda #STAGING_MAX_PAGES
    jmp @capacity
@program_capacity:
    lda #PROGRAM_MAX_PAGES
@capacity:
    cmp program_store_src_length+1
    bcc @error
    bne @copy
    lda program_store_src_length
    bne @error
@copy:
    lda #$00
    sta program_store_src_index
    sta program_store_src_index+1
    sta program_store_dst_index
    sta program_store_dst_index+1
@byte:
    lda program_store_src_index+1
    cmp program_store_src_length+1
    bne @move
    lda program_store_src_index
    cmp program_store_src_length
    beq @done
@move:
    jsr program_store_read_src
    jcs @error
    sta program_store_value
    jsr program_store_write_dst
    jcs @error
    jsr program_store_inc_src
    jsr program_store_inc_dst
    jmp @byte
@done:
    lda program_store_src_length
    sta program_store_dst_length
    lda program_store_src_length+1
    sta program_store_dst_length+1
    jmp program_store_publish_dst_length
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Initialize stable descriptors after the arena directory exists.
.proc program_store_ensure_ready
    lda program_store_ready
    jne @validate
    ldx #PROGRAM_ARENA
    ldy #PROGRAM_ARENA_GENERATION
    jsr arena_handle_valid
    jcs @error
    ldx #STAGING_ARENA
    ldy #PROGRAM_ARENA_GENERATION
    jsr arena_handle_valid
    jcs @error
    lda #'P'
    sta __program_store_published
    sta program_store_staging
    lda #'S'
    sta __program_store_published+1
    sta program_store_staging+1
    lda #$02
    sta __program_store_published+PS_LENGTH_LO
    sta program_store_staging+PS_LENGTH_LO
    lda #$00
    sta __program_store_published+PS_LENGTH_HI
    sta program_store_staging+PS_LENGTH_HI
    sta __program_store_published+PS_START_PAGE
    sta program_store_staging+PS_START_PAGE
    sta __program_store_published+PS_RESERVED
    sta program_store_staging+PS_RESERVED
    sta program_store_source_generation
    sta program_store_source_generation+1
    sta program_store_tx_counter
    sta program_store_transaction+PT_STATE
    lda #PROGRAM_ARENA
    sta __program_store_published+PS_ARENA
    lda #STAGING_ARENA
    sta program_store_staging+PS_ARENA
    lda #PROGRAM_ARENA_GENERATION
    sta __program_store_published+PS_GENERATION
    sta program_store_staging+PS_GENERATION
    ; Materialize the empty-program terminal in each arena.
    ldx #<__program_store_published
    ldy #>__program_store_published
    jsr program_store_probe_dst
    jcs @error
    lda #$00
    sta program_store_dst_index
    sta program_store_dst_index+1
    sta program_store_value
    jsr program_store_write_dst
    jcs @error
    jsr program_store_inc_dst
    jsr program_store_write_dst
    jcs @error
    ldx #<program_store_staging
    ldy #>program_store_staging
    jsr program_store_probe_dst
    jcs @error
    lda #$00
    sta program_store_dst_index
    sta program_store_dst_index+1
    jsr program_store_write_dst
    jcs @error
    jsr program_store_inc_dst
    jsr program_store_write_dst
    jcs @error
    lda #$01
    sta program_store_ready
@validate:
    ldx #PROGRAM_ARENA
    ldy #PROGRAM_ARENA_GENERATION
    jsr arena_handle_valid
    jcs @error
    ldx #STAGING_ARENA
    ldy #PROGRAM_ARENA_GENERATION
    jsr arena_handle_valid
    jcs @error
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Validate X/Y as the one stable active PT and check optimistic generation.
.proc program_store_validate_pt
    cpx #<program_store_transaction
    bne @error
    cpy #>program_store_transaction
    bne @error
    lda program_store_transaction
    cmp #'P'
    bne @error
    lda program_store_transaction+1
    cmp #'T'
    bne @error
    lda program_store_transaction+PT_STATE
    cmp #PT_ACTIVE
    bne @error
    lda program_store_transaction+PT_RESERVED_LO
    ora program_store_transaction+PT_RESERVED_HI
    bne @error
    lda program_store_transaction+PT_BASE_GENERATION_LO
    cmp program_store_source_generation
    bne @error
    lda program_store_transaction+PT_BASE_GENERATION_HI
    cmp program_store_source_generation+1
    bne @error
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Load and validate a PP request. Leaves its line PS pointer in line_ptr.
.proc program_store_parse_pp
    stx program_store_request_ptr
    sty program_store_request_ptr+1
    stx zp_expr_ptr1
    sty zp_expr_ptr1+1
    ldy #$00
    lda (zp_expr_ptr1),y
    cmp #'P'
    jne @error
    iny
    lda (zp_expr_ptr1),y
    cmp #'P'
    jne @error
    ldy #$06
    lda (zp_expr_ptr1),y
    iny
    ora (zp_expr_ptr1),y
    jne @error
    ldy #$02
    lda (zp_expr_ptr1),y
    tax
    iny
    lda (zp_expr_ptr1),y
    tay
    jsr program_store_validate_pt
    jcs @error
    lda program_store_request_ptr
    sta zp_expr_ptr1
    lda program_store_request_ptr+1
    sta zp_expr_ptr1+1
    ldy #$04
    lda (zp_expr_ptr1),y
    sta program_store_line_ptr
    iny
    lda (zp_expr_ptr1),y
    sta program_store_line_ptr+1
    tax
    lda program_store_line_ptr
    tax
    ldy program_store_line_ptr+1
    jsr program_store_probe_src
    jcs @error
    lda program_store_src_arena
    cmp #STAGING_ARENA
    beq @error
    jmp program_store_validate_line_src
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Load and validate a PD request. Leaves requested line in current_line.
.proc program_store_parse_pd
    stx program_store_request_ptr
    sty program_store_request_ptr+1
    stx zp_expr_ptr1
    sty zp_expr_ptr1+1
    ldy #$00
    lda (zp_expr_ptr1),y
    cmp #'P'
    jne @error
    iny
    lda (zp_expr_ptr1),y
    cmp #'D'
    jne @error
    ldy #$06
    lda (zp_expr_ptr1),y
    iny
    ora (zp_expr_ptr1),y
    jne @error
    ldy #$02
    lda (zp_expr_ptr1),y
    tax
    iny
    lda (zp_expr_ptr1),y
    tay
    jsr program_store_validate_pt
    jcs @error
    lda program_store_request_ptr
    sta zp_expr_ptr1
    lda program_store_request_ptr+1
    sta zp_expr_ptr1+1
    ldy #$04
    lda (zp_expr_ptr1),y
    sta program_store_current_line
    iny
    lda (zp_expr_ptr1),y
    sta program_store_current_line+1
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Find requested_line in destination staging.
; Outputs insert_at, old_total, tail_at, found.
.proc program_store_find_dst_line
    lda #$00
    sta program_store_dst_index
    sta program_store_dst_index+1
    sta program_store_found
@record:
    lda program_store_dst_index
    sta program_store_insert_at
    lda program_store_dst_index+1
    sta program_store_insert_at+1
    ; Read length using destination as a temporary source.
    lda program_store_dst_arena
    sta program_store_src_arena
    lda program_store_dst_generation
    sta program_store_src_generation
    lda program_store_dst_start_page
    sta program_store_src_start_page
    lda program_store_dst_index
    sta program_store_src_index
    lda program_store_dst_index+1
    sta program_store_src_index+1
    jsr program_store_read_src
    jcs @error
    sta program_store_record_len
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_record_len+1
    lda program_store_record_len
    ora program_store_record_len+1
    jeq @not_found
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_previous_line
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_previous_line+1
    lda program_store_previous_line+1
    cmp program_store_requested_line+1
    bcc @next
    bne @not_found
    lda program_store_previous_line
    cmp program_store_requested_line
    bcc @next
    bne @not_found
    lda #$01
    sta program_store_found
    lda program_store_record_len
    clc
    adc #$02
    sta program_store_old_total
    lda program_store_record_len+1
    adc #$00
    sta program_store_old_total+1
    lda program_store_insert_at
    clc
    adc program_store_old_total
    sta program_store_tail_at
    lda program_store_insert_at+1
    adc program_store_old_total+1
    sta program_store_tail_at+1
    clc
    rts
@next:
    lda program_store_record_len
    clc
    adc #$02
    sta program_store_record_total
    lda program_store_record_len+1
    adc #$00
    sta program_store_record_total+1
    lda program_store_dst_index
    clc
    adc program_store_record_total
    sta program_store_dst_index
    lda program_store_dst_index+1
    adc program_store_record_total+1
    sta program_store_dst_index+1
    jmp @record
@not_found:
    lda #$00
    sta program_store_old_total
    sta program_store_old_total+1
    lda program_store_insert_at
    sta program_store_tail_at
    lda program_store_insert_at+1
    sta program_store_tail_at+1
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Copy one byte within destination from source-index to destination-index.
.proc program_store_move_within_dst
    lda program_store_dst_arena
    sta program_store_src_arena
    lda program_store_dst_generation
    sta program_store_src_generation
    lda program_store_dst_start_page
    sta program_store_src_start_page
    jsr program_store_read_src
    jcs @error
    sta program_store_value
    jmp program_store_write_dst
@error:
    rts
.endproc

; Shift destination tail right by delta. Indices are computed from old length.
.proc program_store_shift_right
    lda program_store_dst_length
    sta program_store_src_index
    lda program_store_dst_length+1
    sta program_store_src_index+1
@loop:
    lda program_store_src_index
    cmp program_store_tail_at
    bne @move
    lda program_store_src_index+1
    cmp program_store_tail_at+1
    beq @done
@move:
    lda program_store_src_index
    bne :+
    dec program_store_src_index+1
:
    dec program_store_src_index
    lda program_store_src_index
    clc
    adc program_store_delta
    sta program_store_dst_index
    lda program_store_src_index+1
    adc program_store_delta+1
    sta program_store_dst_index+1
    jsr program_store_move_within_dst
    jcs @error
    jmp @loop
@done:
    clc
@error:
    rts
.endproc

; Shift destination tail left to insert_at.
.proc program_store_shift_left
    lda program_store_tail_at
    sta program_store_src_index
    lda program_store_tail_at+1
    sta program_store_src_index+1
    lda program_store_insert_at
    sta program_store_dst_index
    lda program_store_insert_at+1
    sta program_store_dst_index+1
@loop:
    lda program_store_src_index+1
    cmp program_store_dst_length+1
    bne @move
    lda program_store_src_index
    cmp program_store_dst_length
    beq @done
@move:
    jsr program_store_move_within_dst
    jcs @error
    jsr program_store_inc_src
    jsr program_store_inc_dst
    jmp @loop
@done:
    clc
@error:
    rts
.endproc

; Complete a validated line insertion after program_store_find_dst_line has
; published the insertion point and replacement extent. Keeping this internal
; tail separate ensures the public overlay entry remains within one 256-byte
; geoRAM execution page without enlarging the production ABI.
.proc program_store_put_finish
    ; new_length = old_length - old_total + new_total.
    lda program_store_dst_length
    sec
    sbc program_store_old_total
    sta program_store_new_length
    lda program_store_dst_length+1
    sbc program_store_old_total+1
    sta program_store_new_length+1
    lda program_store_new_length
    clc
    adc program_store_new_total
    sta program_store_new_length
    lda program_store_new_length+1
    adc program_store_new_total+1
    sta program_store_new_length+1
    jcs @oom
    lda program_store_new_length+1
    cmp #STAGING_MAX_PAGES
    bcc @size_ok
    jne @oom
    lda program_store_new_length
    jne @oom
@size_ok:
    ; Shift the tail according to replacement-size delta.
    lda program_store_new_total+1
    cmp program_store_old_total+1
    bcc @shift_left
    bne @shift_right
    lda program_store_new_total
    cmp program_store_old_total
    bcc @shift_left
    beq @copy_line
@shift_right:
    lda program_store_new_total
    sec
    sbc program_store_old_total
    sta program_store_delta
    lda program_store_new_total+1
    sbc program_store_old_total+1
    sta program_store_delta+1
    jsr program_store_shift_right
    jcs @error
    jmp @copy_line
@shift_left:
    jsr program_store_shift_left
    jcs @error
@copy_line:
    ; Re-probe the line PS because find/shift use source cursor workspace.
    ldx program_store_line_ptr
    ldy program_store_line_ptr+1
    jsr program_store_probe_src
    jcs @error
    lda #$00
    sta program_store_src_index
    sta program_store_src_index+1
    lda program_store_insert_at
    sta program_store_dst_index
    lda program_store_insert_at+1
    sta program_store_dst_index+1
@copy_byte:
    lda program_store_src_index+1
    cmp program_store_new_total+1
    bne @copy
    lda program_store_src_index
    cmp program_store_new_total
    beq @publish
@copy:
    jsr program_store_read_src
    jcs @error
    sta program_store_value
    jsr program_store_write_dst
    jcs @error
    jsr program_store_inc_src
    jsr program_store_inc_dst
    jmp @copy_byte
@publish:
    lda program_store_new_length
    sta program_store_dst_length
    lda program_store_new_length+1
    sta program_store_dst_length+1
    jsr program_store_publish_dst_length
    clc
    rts
@oom:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; program_tx_begin
; Purpose: begin one isolated whole-program edit transaction.
; Inputs: none.
; Outputs: X/Y=stable PT descriptor, C=0; C=1/A=error on failure.
; Side effects: clones the complete published PS payload to arena 9.
; Clobbers: A, X, Y. Flags: C reports failure.
; Zero page: zp_expr_ptr1.
.segment "GEORAM_PAGE_14"
.export program_tx_begin
program_tx_begin:
    jsr program_store_ensure_ready
    jcs @error
    lda program_store_transaction+PT_STATE
    cmp #PT_ACTIVE
    beq @error
    ldx #<__program_store_published
    ldy #>__program_store_published
    jsr program_store_probe_src
    jcs @error
    jsr program_store_validate_src
    jcs @error
    lda program_store_requested_line
    sta program_store_current_line
    lda program_store_requested_line+1
    sta program_store_current_line+1
    ldx #<program_store_staging
    ldy #>program_store_staging
    jsr program_store_probe_dst
    jcs @error
    jsr program_store_clone
    jcs @error
    lda #'P'
    sta program_store_transaction
    lda #'T'
    sta program_store_transaction+1
    lda #PT_ACTIVE
    sta program_store_transaction+PT_STATE
    inc program_store_tx_counter
    bne :+
    inc program_store_tx_counter
:
    lda program_store_tx_counter
    sta program_store_transaction+PT_TX_GENERATION
    lda program_store_source_generation
    sta program_store_transaction+PT_BASE_GENERATION_LO
    lda program_store_source_generation+1
    sta program_store_transaction+PT_BASE_GENERATION_HI
    lda #$00
    sta program_store_transaction+PT_RESERVED_LO
    sta program_store_transaction+PT_RESERVED_HI
    ldx #<program_store_transaction
    ldy #>program_store_transaction
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; program_tx_put_line
; Purpose: sorted-insert or replace one normalized line in staging.
; Inputs: X/Y=PP request descriptor.
; Outputs: C=0, or C=1/A=error. No published state changes.
; Side effects: mutates only the dedicated staging arena.
; Clobbers: A, X, Y. Flags: C reports failure.
; Zero page: zp_expr_ptr1.
.segment "GEORAM_PAGE_15"
.export program_tx_put_line
program_tx_put_line:
    stx program_store_request_ptr
    sty program_store_request_ptr+1
    jsr program_store_ensure_ready
    jcs @error
    ldx program_store_request_ptr
    ldy program_store_request_ptr+1
    jsr program_store_parse_pp
    jcs @error
    ldx program_store_line_ptr
    ldy program_store_line_ptr+1
    jsr program_store_probe_src
    jcs @error
    ; Capture new record size and line number from the line PS.
    lda program_store_record_len
    clc
    adc #$02
    sta program_store_new_total
    lda program_store_record_len+1
    adc #$00
    sta program_store_new_total+1
    lda #$02
    sta program_store_src_index
    lda #$00
    sta program_store_src_index+1
    jsr program_store_read_src
    jcs @error
    sta program_store_current_line
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_current_line+1
    lda program_store_current_line
    sta program_store_requested_line
    lda program_store_current_line+1
    sta program_store_requested_line+1
    ; Probe and validate staging, then find insertion/replacement point.
    ldx #<program_store_staging
    ldy #>program_store_staging
    jsr program_store_probe_dst
    jcs @error
    ldx #<program_store_staging
    ldy #>program_store_staging
    jsr program_store_probe_src
    jcs @error
    jsr program_store_validate_src
    jcs @error
    ldx #<program_store_staging
    ldy #>program_store_staging
    jsr program_store_probe_dst
    jcs @error
    ldx program_store_line_ptr
    ldy program_store_line_ptr+1
    jsr program_store_probe_src
    jcs @error
    lda #$02
    sta program_store_src_index
    lda #$00
    sta program_store_src_index+1
    jsr program_store_read_src
    jcs @error
    sta program_store_requested_line
    jsr program_store_inc_src
    jsr program_store_read_src
    jcs @error
    sta program_store_requested_line+1
    jsr program_store_find_dst_line
    jcs @error
    jmp program_store_put_finish
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; program_tx_delete_line
; Purpose: remove one line from the active transaction if present.
; Inputs: X/Y=PD request descriptor.
; Outputs: C=0 (missing line is a successful no-op), C=1/A=error.
; Side effects: mutates only the dedicated staging arena.
; Clobbers: A, X, Y. Flags: C reports failure.
; Zero page: zp_expr_ptr1.
.segment "GEORAM_PAGE_16"
.export program_tx_delete_line
program_tx_delete_line:
    stx program_store_request_ptr
    sty program_store_request_ptr+1
    jsr program_store_ensure_ready
    jcs @error
    ldx program_store_request_ptr
    ldy program_store_request_ptr+1
    jsr program_store_parse_pd
    jcs @error
    lda program_store_current_line
    sta program_store_requested_line
    lda program_store_current_line+1
    sta program_store_requested_line+1
    ldx #<program_store_staging
    ldy #>program_store_staging
    jsr program_store_probe_src
    jcs @error
    jsr program_store_validate_src
    jcs @error
    ldx #<program_store_staging
    ldy #>program_store_staging
    jsr program_store_probe_dst
    jcs @error
    lda program_store_requested_line
    sta program_store_current_line
    lda program_store_requested_line+1
    sta program_store_current_line+1
    jsr program_store_find_dst_line
    jcs @error
    lda program_store_found
    beq @success
    jsr program_store_shift_left
    jcs @error
    lda program_store_dst_length
    sec
    sbc program_store_old_total
    sta program_store_dst_length
    lda program_store_dst_length+1
    sbc program_store_old_total+1
    sta program_store_dst_length+1
    jsr program_store_publish_dst_length
@success:
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; program_tx_commit
; Purpose: atomically publish the validated staging generation.
; Inputs: X/Y=active PT descriptor returned by program_tx_begin.
; Outputs: X/Y=published PS descriptor, C=0; C=1/A=error.
; Side effects: copies all payload bytes before publishing PS length and source
; generation, then invalidates the PT.
; Clobbers: A, X, Y. Flags: C reports failure.
; Zero page: zp_expr_ptr1.
.segment "GEORAM_PAGE_17"
.export program_tx_commit
program_tx_commit:
    stx program_store_request_ptr
    sty program_store_request_ptr+1
    jsr program_store_ensure_ready
    jcs @error
    ldx program_store_request_ptr
    ldy program_store_request_ptr+1
    jsr program_store_validate_pt
    jcs @error
    ldx #<program_store_staging
    ldy #>program_store_staging
    jsr program_store_probe_src
    jcs @error
    jsr program_store_validate_src
    jcs @error
    ldx #<__program_store_published
    ldy #>__program_store_published
    jsr program_store_probe_dst
    jcs @error
    jsr program_store_clone
    jcs @error
    inc program_store_source_generation
    bne :+
    inc program_store_source_generation+1
:
    lda #$00
    sta program_store_transaction+PT_STATE
    ldx #<__program_store_published
    ldy #>__program_store_published
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; program_tx_abort
; Purpose: invalidate an active transaction without changing publication.
; Inputs: X/Y=active PT descriptor returned by program_tx_begin.
; Outputs: C=0, or C=1/A=error.
; Side effects: invalidates PT; published descriptor/payload/generation unchanged.
; Clobbers: A, X, Y. Flags: C reports failure.
; Zero page: none.
.segment "GEORAM_PAGE_18"
.export program_tx_abort
program_tx_abort:
    stx program_store_request_ptr
    sty program_store_request_ptr+1
    jsr program_store_ensure_ready
    jcs @error
    ldx program_store_request_ptr
    ldy program_store_request_ptr+1
    jsr program_store_validate_pt
    jcs @error
    lda #$00
    sta program_store_transaction+PT_STATE
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

.segment "GEOASM"

; program_replace_from_load
; Purpose: transactionally replace publication from a decoded normalized PS.
; Inputs: X/Y=validated decoded PS descriptor.
; Outputs: X/Y=published PS descriptor, C=0; C=1/A=error.
; Side effects: rejects arena-9 aliasing; validates then clones input to staging,
; validates staging, clones staging to publication, and publishes length last.
; Clobbers: A, X, Y. Flags: C reports failure.
; Zero page: zp_expr_ptr1.
.export program_replace_from_load
program_replace_from_load:
    stx program_store_line_ptr
    sty program_store_line_ptr+1
    jsr program_store_ensure_ready
    jcs @error
    lda program_store_transaction+PT_STATE
    cmp #PT_ACTIVE
    beq @error
    ldx program_store_line_ptr
    ldy program_store_line_ptr+1
    jsr program_store_probe_src
    jcs @error
    lda program_store_src_arena
    cmp #STAGING_ARENA
    beq @error
    jsr program_store_validate_src
    jcs @error
    ldx #<program_store_staging
    ldy #>program_store_staging
    jsr program_store_probe_dst
    jcs @error
    jsr program_store_clone
    jcs @error
    ldx #<program_store_staging
    ldy #>program_store_staging
    jsr program_store_probe_src
    jcs @error
    jsr program_store_validate_src
    jcs @error
    ldx #<__program_store_published
    ldy #>__program_store_published
    jsr program_store_probe_dst
    jcs @error
    jsr program_store_clone
    jcs @error
    inc program_store_source_generation
    bne :+
    inc program_store_source_generation+1
:
    ldx #<__program_store_published
    ldy #>__program_store_published
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
