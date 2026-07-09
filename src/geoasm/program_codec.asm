; src/geoasm/program_codec.asm
; Minimal stock and extended program codec helpers.

.include "common/zp.inc"
.include "common/constants.asm"

.macro jcs target
    bcc *+5
    jmp target
.endmacro
.macro jcc target
    bcs *+5
    jmp target
.endmacro
.macro jne target
    beq *+5
    jmp target
.endmacro

.import arena_handle_valid
.import arena_select_page

.segment "BSS"
__program_codec_checksum: .res 1
__program_codec_line_lo: .res 1
__program_codec_line_hi: .res 1
program_stream_descriptor: .res 2
program_stream_length: .res 2
program_stream_index: .res 2
program_stream_scan: .res 2
program_stream_arena: .res 1
program_stream_generation: .res 1
program_stream_start_page: .res 1
program_stream_value: .res 1
program_stream_delta: .res 1
program_stream_prev_line: .res 2
program_stream_have_line: .res 1
program_stream_link: .res 2
program_stream_record_length: .res 2
program_stream_selected_page: .res 1
program_stream_page_valid: .res 1
program_stream_target_page: .res 1
program_codec_copy_count: .res 1
program_codec_output_descriptor: .res 8
program_codec_page_buffer: .res 256

.segment "CODE"

PROGRAM_STREAM_MAGIC_0 = 'P'
PROGRAM_STREAM_MAGIC_1 = 'S'
PROGRAM_STREAM_DESC_LENGTH_LO = 2
PROGRAM_STREAM_DESC_LENGTH_HI = 3
PROGRAM_STREAM_DESC_ARENA = 4
PROGRAM_STREAM_DESC_GENERATION = 5
PROGRAM_STREAM_DESC_START_PAGE = 6
PROGRAM_CODEC_OUTPUT_ARENA = 8
PROGRAM_CODEC_OUTPUT_GENERATION = 1

; Load and validate the arena-backed whole-program descriptor from X/Y.
; The former one-byte bounded record ABI is rejected.
.proc __program_stream_probe
    stx program_stream_descriptor
    sty program_stream_descriptor+1
    lda #$00
    sta program_stream_page_valid
    stx zp_expr_ptr1
    sty zp_expr_ptr1+1
    ldy #$00
    lda (zp_expr_ptr1),y
    cmp #PROGRAM_STREAM_MAGIC_0
    jne @invalid
    iny
    lda (zp_expr_ptr1),y
    cmp #PROGRAM_STREAM_MAGIC_1
    jne @invalid
    ldy #PROGRAM_STREAM_DESC_LENGTH_LO
    lda (zp_expr_ptr1),y
    sta program_stream_length
    iny
    lda (zp_expr_ptr1),y
    sta program_stream_length+1
    iny
    lda (zp_expr_ptr1),y
    sta program_stream_arena
    tax
    iny
    lda (zp_expr_ptr1),y
    sta program_stream_generation
    tay
    jsr arena_handle_valid
    jcs @error
    lda program_stream_descriptor
    sta zp_expr_ptr1
    lda program_stream_descriptor+1
    sta zp_expr_ptr1+1
    ldy #PROGRAM_STREAM_DESC_START_PAGE
    lda (zp_expr_ptr1),y
    sta program_stream_start_page
    iny
    lda (zp_expr_ptr1),y
    bne @error
    ; Prove the complete claimed extent fits in the arena before any codec
    ; operation reads or mutates payload bytes.
    lda program_stream_length
    bne @last_page
    lda program_stream_length+1
    beq @empty
    sec
    sbc #$01
    jmp @add_start
@last_page:
    lda program_stream_length+1
@add_start:
    clc
    adc program_stream_start_page
    jcs @error
    jmp @select_page
@empty:
    lda program_stream_start_page
@select_page:
    sta program_stream_target_page
    ldx program_stream_arena
    ldy program_stream_generation
    jsr arena_select_page
    bcs @error
    lda program_stream_target_page
    sta program_stream_selected_page
    lda #$01
    sta program_stream_page_valid
    ldx program_stream_descriptor
    ldy program_stream_descriptor+1
    lda #$01
    clc
    rts
@invalid:
    jmp @error
@error:
    ldx program_stream_descriptor
    ldy program_stream_descriptor+1
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Replace validated external stock link fields with canonical internal record
; lengths. The normalized stream retains a final zero-length terminator.
.proc __program_stream_normalize_stock
    lda #$00
    sta program_stream_index
    sta program_stream_index+1
@line:
    lda program_stream_index
    sta program_stream_scan
    lda program_stream_index+1
    sta program_stream_scan+1
    jsr __program_stream_read
    jcs @error
    sta program_stream_link
    jsr __program_stream_inc_index
    jsr __program_stream_read
    jcs @error
    sta program_stream_link+1
    jsr __program_stream_inc_index
    ora program_stream_link
    bne @record
    lda program_stream_index
    cmp program_stream_length
    bne @error
    lda program_stream_index+1
    cmp program_stream_length+1
    bne @error
    clc
    rts
@record:
    ; External next address minus $0801 is the normalized next-record offset.
    sec
    lda program_stream_link
    sbc #$01
    sta program_stream_link
    lda program_stream_link+1
    sbc #$08
    sta program_stream_link+1
    bcc @error
    ; Stored record length excludes its own two-byte length field.
    sec
    lda program_stream_link
    sbc program_stream_scan
    sta program_stream_record_length
    lda program_stream_link+1
    sbc program_stream_scan+1
    sta program_stream_record_length+1
    sec
    lda program_stream_record_length
    sbc #$02
    sta program_stream_record_length
    lda program_stream_record_length+1
    sbc #$00
    sta program_stream_record_length+1
    bcc @error
    lda program_stream_scan
    sta program_stream_index
    lda program_stream_scan+1
    sta program_stream_index+1
    lda program_stream_record_length
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    jsr __program_stream_inc_index
    lda program_stream_record_length+1
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    lda program_stream_link
    sta program_stream_index
    lda program_stream_link+1
    sta program_stream_index+1
    jmp @line
@error:
    lda #ERR_SYNTAX
    sec
    rts
.endproc

; Validate normalized logical line records before stock export.
.proc __program_stream_validate_normalized
    jsr __program_stream_load_start
    lda #$00
    sta program_stream_index
    sta program_stream_index+1
    sta program_stream_prev_line
    sta program_stream_prev_line+1
    sta program_stream_have_line
@line:
    jsr __program_stream_index_before_length
    jcs @error
    jsr __program_stream_read
    jcs @error
    sta program_stream_record_length
    jsr __program_stream_inc_index
    jsr __program_stream_index_before_length
    jcs @error
    jsr __program_stream_read
    jcs @error
    sta program_stream_record_length+1
    jsr __program_stream_inc_index
    ora program_stream_record_length
    bne @record
    lda program_stream_index
    cmp program_stream_length
    jne @error
    lda program_stream_index+1
    cmp program_stream_length+1
    jne @error
    clc
    rts
@record:
    lda program_stream_record_length+1
    bne @length_ok
    lda program_stream_record_length
    cmp #$03
    jcc @error
@length_ok:
    clc
    lda program_stream_index
    adc program_stream_record_length
    sta program_stream_scan
    lda program_stream_index+1
    adc program_stream_record_length+1
    sta program_stream_scan+1
    jcs @error
    lda program_stream_scan+1
    cmp program_stream_length+1
    bcc @line_number
    jne @error
    lda program_stream_scan
    cmp program_stream_length
    bcc @line_number
    beq @line_number
    jmp @error
@line_number:
    jsr __program_stream_read
    jcs @error
    sta __program_codec_line_lo
    jsr __program_stream_inc_index
    jsr __program_stream_read
    jcs @error
    sta __program_codec_line_hi
    jsr __program_stream_inc_index
    lda program_stream_have_line
    beq @ordered
    lda __program_codec_line_hi
    cmp program_stream_prev_line+1
    bcc @error
    bne @ordered
    lda __program_codec_line_lo
    cmp program_stream_prev_line
    bcc @error
    beq @error
@ordered:
    lda __program_codec_line_lo
    sta program_stream_prev_line
    lda __program_codec_line_hi
    sta program_stream_prev_line+1
    lda #$01
    sta program_stream_have_line
@body:
    jsr __program_stream_read
    jcs @error
    sta program_stream_value
    jsr __program_stream_inc_index
    lda program_stream_index+1
    cmp program_stream_scan+1
    bne @not_end
    lda program_stream_index
    cmp program_stream_scan
    beq @body_end
@not_end:
    lda program_stream_value
    beq @error
    jmp @body
@body_end:
    lda program_stream_value
    bne @error
    jmp @line
@error:
    lda #ERR_SYNTAX
    sec
    rts
.endproc

; Replace normalized record lengths with canonical absolute BASIC links after
; the $0801 load address has been prepended.
.proc __program_stream_canonicalize_stock
    lda #$02
    sta program_stream_index
    lda #$00
    sta program_stream_index+1
@line:
    lda program_stream_index
    sta program_stream_link
    lda program_stream_index+1
    sta program_stream_link+1
    jsr __program_stream_read
    jcs @error
    sta program_stream_record_length
    jsr __program_stream_inc_index
    jsr __program_stream_read
    jcs @error
    sta program_stream_record_length+1
    jsr __program_stream_inc_index
    ora program_stream_record_length
    bne @record
    lda program_stream_index
    cmp program_stream_length
    jne @error
    lda program_stream_index+1
    cmp program_stream_length+1
    jne @error
    clc
    rts
@record:
    clc
    lda program_stream_index
    adc program_stream_record_length
    sta program_stream_scan
    lda program_stream_index+1
    adc program_stream_record_length+1
    sta program_stream_scan+1
    jcs @error
    ; External offset maps to absolute address $07ff + offset.
    clc
    lda program_stream_scan
    adc #$FF
    sta program_stream_record_length
    lda program_stream_scan+1
    adc #$07
    sta program_stream_record_length+1
    lda program_stream_link
    sta program_stream_index
    lda program_stream_link+1
    sta program_stream_index+1
    lda program_stream_record_length
    sta program_stream_value
    jsr __program_stream_write
    jcs @error
    jsr __program_stream_inc_index
    lda program_stream_record_length+1
    sta program_stream_value
    jsr __program_stream_write
    jcs @error
    lda program_stream_scan
    sta program_stream_index
    lda program_stream_scan+1
    sta program_stream_index+1
    jmp @line
@error:
    lda #ERR_SYNTAX
    sec
    rts
.endproc

; Clone a logical program into the dedicated codec output arena. An input
; already owned by that arena is reused; every other input remains unchanged.
.proc __program_stream_clone_for_encode
    lda program_stream_arena
    cmp #PROGRAM_CODEC_OUTPUT_ARENA
    bne @clone
    lda program_stream_generation
    cmp #PROGRAM_CODEC_OUTPUT_GENERATION
    bne @clone
    clc
    rts
@clone:
    ; Preflight the complete destination extent.
    lda program_stream_length
    bne @last_page
    lda program_stream_length+1
    beq @preflight
    sec
    sbc #$01
    jmp @preflight
@last_page:
    lda program_stream_length+1
@preflight:
    ldx #PROGRAM_CODEC_OUTPUT_ARENA
    ldy #PROGRAM_CODEC_OUTPUT_GENERATION
    jsr arena_select_page
    jcs @error
    lda #$00
    sta program_stream_scan
    sta program_stream_scan+1
@page:
    lda program_stream_scan
    cmp program_stream_length+1
    bcc @full
    bne @done
    lda program_stream_length
    beq @done
    sta program_codec_copy_count
    jmp @read_page
@full:
    lda #$00
    sta program_codec_copy_count
@read_page:
    clc
    lda program_stream_start_page
    adc program_stream_scan
    jcs @error
    ldx program_stream_arena
    ldy program_stream_generation
    jsr arena_select_page
    jcs @error
    ldx #$00
@read:
    lda $DE00,x
    sta program_codec_page_buffer,x
    inx
    lda program_codec_copy_count
    beq @read_full
    cpx program_codec_copy_count
    bcc @read
    jmp @write_page
@read_full:
    cpx #$00
    bne @read
@write_page:
    lda program_stream_scan
    ldx #PROGRAM_CODEC_OUTPUT_ARENA
    ldy #PROGRAM_CODEC_OUTPUT_GENERATION
    jsr arena_select_page
    jcs @error
    ldx #$00
@write:
    lda program_codec_page_buffer,x
    sta $DE00,x
    inx
    lda program_codec_copy_count
    beq @write_full
    cpx program_codec_copy_count
    bcc @write
    jmp @next
@write_full:
    cpx #$00
    bne @write
@next:
    inc program_stream_scan
    jmp @page
@done:
    lda #'P'
    sta program_codec_output_descriptor
    lda #'S'
    sta program_codec_output_descriptor+1
    lda program_stream_length
    sta program_codec_output_descriptor+2
    lda program_stream_length+1
    sta program_codec_output_descriptor+3
    lda #PROGRAM_CODEC_OUTPUT_ARENA
    sta program_codec_output_descriptor+4
    lda #PROGRAM_CODEC_OUTPUT_GENERATION
    sta program_codec_output_descriptor+5
    lda #$00
    sta program_codec_output_descriptor+6
    sta program_codec_output_descriptor+7
    lda #<program_codec_output_descriptor
    sta program_stream_descriptor
    lda #>program_codec_output_descriptor
    sta program_stream_descriptor+1
    lda #PROGRAM_CODEC_OUTPUT_ARENA
    sta program_stream_arena
    lda #PROGRAM_CODEC_OUTPUT_GENERATION
    sta program_stream_generation
    lda #$00
    sta program_stream_start_page
    sta program_stream_page_valid
    clc
    rts
@error:
    lda #ERR_OUT_OF_DATA
    sec
    rts
.endproc

__program_stream_encode_stock:
    jsr __program_stream_validate_normalized
    bcs @error
    jsr __program_stream_clone_for_encode
    jcs @error
    jsr __program_stream_load_start
    lda #$02
    jsr __program_stream_shift_right
    bcs @error
    lda #$00
    sta program_stream_index
    sta program_stream_index+1
    lda #$01
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    inc program_stream_index
    lda #$08
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    jsr __program_stream_canonicalize_stock
    bcs @error
    jmp __program_stream_store_length
@error:
    lda #ERR_SYNTAX
    sec
    rts

.proc __program_stream_validate_extended
    jsr __program_stream_load_start
    lda program_stream_length+1
    bne @length_ok
    lda program_stream_length
    cmp #$10
    jcc @error
@length_ok:
    ldx #$00
@magic:
    txa
    pha
    lda @magic_bytes,x
    sta program_stream_value
    pla
    tax
    txa
    pha
    lda #$00
    tax
    pla
    jsr __program_stream_read_ax
    jcs @error
    ldx program_stream_index
    cmp @magic_bytes,x
    jne @error
    inx
    cpx #$04
    bcc @magic
    lda #$04
    ldx #$00
    jsr __program_stream_read_ax
    jcs @error
    cmp #$01
    jne @error
    lda #$05
    ldx #$00
    jsr __program_stream_read_ax
    jcs @error
    cmp #$01
    jne @error
    lda #$06
    ldx #$00
    jsr __program_stream_read_ax
    jcs @error
    sta program_stream_scan
    lda #$07
    ldx #$00
    jsr __program_stream_read_ax
    jcs @error
    sta program_stream_scan+1
    clc
    lda program_stream_scan
    adc #$10
    sta program_stream_link
    lda program_stream_scan+1
    adc #$00
    sta program_stream_link+1
    lda program_stream_link
    cmp program_stream_length
    bne @error
    lda program_stream_link+1
    cmp program_stream_length+1
    bne @error
    lda #$09
    ldx #$00
    jsr __program_stream_read_ax
    bcs @error
    bne @error
    ldx #$0A
@reserved:
    txa
    pha
    lda #$00
    tax
    pla
    jsr __program_stream_read_ax
    bcs @error
    bne @error
    ldx program_stream_index
    inx
    cpx #$10
    bcc @reserved
    lda #$00
    sta __program_codec_checksum
    lda #$10
    sta program_stream_index
    lda #$00
    sta program_stream_index+1
@checksum:
    jsr __program_stream_index_before_length
    bcs @checksum_done
    jsr __program_stream_read
    bcs @error
    clc
    adc __program_codec_checksum
    sta __program_codec_checksum
    jsr __program_stream_inc_index
    jmp @checksum
@checksum_done:
    lda #$08
    ldx #$00
    jsr __program_stream_read_ax
    bcs @error
    cmp __program_codec_checksum
    bne @error
    clc
    rts
@error:
    lda #ERR_SYNTAX
    sec
    rts
@magic_bytes:
    .byte 'C', '2', 'P', '1'
.endproc

__program_stream_decode_extended:
    jsr __program_stream_validate_extended
    bcs @error
    lda #$10
    jsr __program_stream_shift_left
    bcs @error
    sec
    lda program_stream_length
    sbc #$10
    sta program_stream_length
    lda program_stream_length+1
    sbc #$00
    sta program_stream_length+1
    jmp __program_stream_store_length
@error:
    lda #ERR_SYNTAX
    sec
    rts

__program_stream_encode_extended:
    jsr __program_stream_clone_for_encode
    jcs @error
    jsr __program_stream_load_start
    lda #$10
    jsr __program_stream_shift_right
    jcs @error
    ; Header fields 0..15.
    lda #$00
    sta program_stream_index
    sta program_stream_index+1
@header:
    ldx program_stream_index
    lda @header_bytes,x
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    jsr __program_stream_inc_index
    lda program_stream_index
    cmp #$10
    bcc @header
    ; Body length excludes the newly prepended header.
    sec
    lda program_stream_length
    sbc #$10
    sta program_stream_scan
    lda program_stream_length+1
    sbc #$00
    sta program_stream_scan+1
    lda #$06
    sta program_stream_index
    lda #$00
    sta program_stream_index+1
    lda program_stream_scan
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    inc program_stream_index
    lda program_stream_scan+1
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    lda #$00
    sta __program_codec_checksum
    lda #$10
    sta program_stream_index
    lda #$00
    sta program_stream_index+1
@checksum:
    jsr __program_stream_index_before_length
    bcs @checksum_done
    jsr __program_stream_read
    bcs @error
    clc
    adc __program_codec_checksum
    sta __program_codec_checksum
    jsr __program_stream_inc_index
    jmp @checksum
@checksum_done:
    lda #$08
    sta program_stream_index
    lda #$00
    sta program_stream_index+1
    lda __program_codec_checksum
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    jmp __program_stream_store_length
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
@header_bytes:
    .byte 'C', '2', 'P', '1', $01, $01, $00, $00
    .byte $00, $00, $00, $00, $00, $00, $00, $00

.proc __program_stream_load_start
    lda program_stream_descriptor
    sta zp_expr_ptr1
    lda program_stream_descriptor+1
    sta zp_expr_ptr1+1
    ldy #PROGRAM_STREAM_DESC_START_PAGE
    lda (zp_expr_ptr1),y
    sta program_stream_start_page
    rts
.endproc

; Select the page containing program_stream_index and return its byte in A.
.proc __program_stream_read
    lda program_stream_index+1
    clc
    adc program_stream_start_page
    bcs @error
    sta program_stream_target_page
    lda program_stream_page_valid
    beq @select
    lda program_stream_target_page
    cmp program_stream_selected_page
    beq @read
@select:
    lda program_stream_target_page
    ldx program_stream_arena
    ldy program_stream_generation
    jsr arena_select_page
    bcs @error
    lda program_stream_target_page
    sta program_stream_selected_page
    lda #$01
    sta program_stream_page_valid
@read:
    ldy program_stream_index
    lda $DE00,y
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Write program_stream_value at program_stream_index.
.proc __program_stream_write
    lda program_stream_index+1
    clc
    adc program_stream_start_page
    bcs @error
    pha
    lda program_stream_page_valid
    beq @select_saved
    pla
    cmp program_stream_selected_page
    beq @write
    pha
@select_saved:
    pla
    pha
    ldx program_stream_arena
    ldy program_stream_generation
    jsr arena_select_page
    bcs @error_stack
    pla
    sta program_stream_selected_page
    lda #$01
    sta program_stream_page_valid
    jmp @write
@write:
    ldy program_stream_index
    lda program_stream_value
    sta $DE00,y
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
@error_stack:
    pla
    jmp @error
.endproc

.proc __program_stream_inc_index
    inc program_stream_index
    bne :+
    inc program_stream_index+1
:
    rts
.endproc

.proc __program_stream_index_before_length
    lda program_stream_index+1
    cmp program_stream_length+1
    bne :+
    lda program_stream_index
    cmp program_stream_length
:
    rts
.endproc

.proc __program_stream_store_length
    lda program_stream_descriptor
    sta zp_expr_ptr1
    lda program_stream_descriptor+1
    sta zp_expr_ptr1+1
    ldy #PROGRAM_STREAM_DESC_LENGTH_LO
    lda program_stream_length
    sta (zp_expr_ptr1),y
    iny
    lda program_stream_length+1
    sta (zp_expr_ptr1),y
    ldx program_stream_descriptor
    ldy program_stream_descriptor+1
    clc
    rts
.endproc

; program_classify_file
; Inputs: X/Y = arena-backed whole-program descriptor.
; Outputs: A=0 stock or A=1 extended, C=1 on invalid descriptor/format.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
.export program_classify_file
program_classify_file:
    jsr __program_stream_probe
    bcs @error
    jmp __program_stream_classify
@error:
    rts

; program_decode_stock
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Removes the stock load address only after validating the complete program.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
.export program_decode_stock
program_decode_stock:
    jsr __program_stream_probe
    bcs @error
    jmp __program_stream_decode_stock
@error:
    rts

; program_encode_stock
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Prepends $0801 and canonically rebuilds every linked-line pointer.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
.export program_encode_stock
program_encode_stock:
    jsr __program_stream_probe
    bcs @error
    jmp __program_stream_encode_stock
@error:
    rts

; program_decode_extended
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Validates and removes the complete C2P1 envelope transactionally.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
.export program_decode_extended
program_decode_extended:
    jsr __program_stream_probe
    bcs @error
    jmp __program_stream_decode_extended
@error:
    rts

; program_encode_extended
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Prepends a versioned C2P1 envelope with 16-bit length and checksum fields.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
.export program_encode_extended
program_encode_extended:
    jsr __program_stream_probe
    bcs @error
    jmp __program_stream_encode_extended
@error:
    rts

__program_stream_classify:
    jsr __program_stream_load_start
    lda program_stream_length+1
    bne @select
    lda program_stream_length
    cmp #$04
    bcc @error
@select:
    lda program_stream_start_page
    ldx program_stream_arena
    ldy program_stream_generation
    jsr arena_select_page
    bcs @error
    lda $DE00
    cmp #'C'
    beq @extended
    cmp #$01
    bne @error
    lda $DE01
    cmp #$08
    bne @error
    lda #$00
    clc
    rts
@extended:
    lda $DE01
    cmp #'2'
    bne @error
    lda $DE02
    cmp #'P'
    bne @error
    lda $DE03
    cmp #'1'
    bne @error
    lda #$01
    clc
    rts
@error:
    lda #ERR_SYNTAX
    sec
    rts

; Read byte at A/X offset (low/high) into A.
.proc __program_stream_read_ax
    sta program_stream_index
    stx program_stream_index+1
    jmp __program_stream_read
.endproc

; Validate the stock linked-line stream without changing it.
.proc __program_stream_validate_stock
    jsr __program_stream_load_start
    lda program_stream_length+1
    bne @length_ok
    lda program_stream_length
    cmp #$04
    jcc @error
@length_ok:
    lda #$00
    ldx #$00
    jsr __program_stream_read_ax
    jcs @error
    cmp #$01
    jne @error
    lda #$01
    ldx #$00
    jsr __program_stream_read_ax
    jcs @error
    cmp #$08
    jne @error
    lda #$00
    sta program_stream_prev_line
    sta program_stream_prev_line+1
    sta program_stream_have_line
    lda #$02
    sta program_stream_index
    lda #$00
    sta program_stream_index+1
@line:
    jsr __program_stream_index_before_length
    jcs @error
    jsr __program_stream_read
    jcs @error
    sta program_stream_link
    jsr __program_stream_inc_index
    jsr __program_stream_index_before_length
    jcs @error
    jsr __program_stream_read
    jcs @error
    sta program_stream_link+1
    jsr __program_stream_inc_index
    ora program_stream_link
    bne @record
    lda program_stream_index
    cmp program_stream_length
    jne @error
    lda program_stream_index+1
    cmp program_stream_length+1
    jne @error
    clc
    rts
@record:
    ; Line number occupies the next two bytes.
    jsr __program_stream_index_before_length
    bcs @error
    jsr __program_stream_read
    bcs @error
    sta __program_codec_line_lo
    jsr __program_stream_inc_index
    jsr __program_stream_index_before_length
    bcs @error
    jsr __program_stream_read
    bcs @error
    sta __program_codec_line_hi
    jsr __program_stream_inc_index
    lda program_stream_have_line
    beq @ordered
    lda __program_codec_line_hi
    cmp program_stream_prev_line+1
    bcc @error
    bne @ordered
    lda __program_codec_line_lo
    cmp program_stream_prev_line
    bcc @error
    beq @error
@ordered:
    lda __program_codec_line_lo
    sta program_stream_prev_line
    lda __program_codec_line_hi
    sta program_stream_prev_line+1
    lda #$01
    sta program_stream_have_line
@body:
    jsr __program_stream_index_before_length
    bcs @error
    jsr __program_stream_read
    bcs @error
    jsr __program_stream_inc_index
    cmp #$00
    bne @body
    ; Expected pointer is $0801 + (next stream offset - 2) = $07ff + offset.
    clc
    lda program_stream_index
    adc #$FF
    sta program_stream_scan
    lda program_stream_index+1
    adc #$07
    sta program_stream_scan+1
    lda program_stream_scan
    cmp program_stream_link
    bne @error
    lda program_stream_scan+1
    cmp program_stream_link+1
    bne @error
    jmp @line
@error:
    lda #ERR_SYNTAX
    sec
    rts
.endproc

; Move [source,length) to destination zero, where source is A (0, 2, or 16).
.proc __program_stream_shift_left
    sta program_stream_scan
    lda #$00
    sta program_stream_scan+1
    sta program_stream_index
    sta program_stream_index+1
@copy:
    lda program_stream_scan+1
    cmp program_stream_length+1
    bne :+
    lda program_stream_scan
    cmp program_stream_length
:
    bcs @done
    lda program_stream_index
    pha
    lda program_stream_index+1
    pha
    lda program_stream_scan
    sta program_stream_index
    lda program_stream_scan+1
    sta program_stream_index+1
    jsr __program_stream_read
    bcs @error_stack
    sta program_stream_value
    pla
    sta program_stream_index+1
    pla
    sta program_stream_index
    jsr __program_stream_write
    bcs @error
    inc program_stream_scan
    bne :+
    inc program_stream_scan+1
:
    jsr __program_stream_inc_index
    jmp @copy
@error_stack:
    pla
    pla
@error:
    sec
    rts
@done:
    clc
    rts
.endproc

__program_stream_decode_stock:
    jsr __program_stream_validate_stock
    bcs @error
    lda #$02
    jsr __program_stream_shift_left
    bcs @error
    sec
    lda program_stream_length
    sbc #$02
    sta program_stream_length
    lda program_stream_length+1
    sbc #$00
    sta program_stream_length+1
    jsr __program_stream_normalize_stock
    bcs @error
    jmp __program_stream_store_length
@error:
    lda #ERR_SYNTAX
    sec
    rts


; Shift a stream right by A bytes, copying backwards to support overlap.
.proc __program_stream_shift_right
    sta program_stream_delta
    clc
    adc program_stream_length
    sta program_stream_link
    lda program_stream_length+1
    adc #$00
    sta program_stream_link+1
    bcs @error
    lda program_stream_length
    sta program_stream_scan
    lda program_stream_length+1
    sta program_stream_scan+1
@copy:
    lda program_stream_scan
    ora program_stream_scan+1
    beq @done
    sec
    lda program_stream_scan
    sbc #$01
    sta program_stream_scan
    lda program_stream_scan+1
    sbc #$00
    sta program_stream_scan+1
    lda program_stream_scan
    sta program_stream_index
    lda program_stream_scan+1
    sta program_stream_index+1
    jsr __program_stream_read
    bcs @error
    sta program_stream_value
    clc
    lda program_stream_index
    adc program_stream_delta
    sta program_stream_index
    bcc :+
    inc program_stream_index+1
:
    jsr __program_stream_write
    bcs @error
    jmp @copy
@done:
    lda program_stream_link
    sta program_stream_length
    lda program_stream_link+1
    sta program_stream_length+1
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc
