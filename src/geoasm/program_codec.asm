; src/geoasm/program_codec.asm
; Stock V2, Plus/4 BASIC 3.5, and optional C2P1 program codec helpers.
; SAVE format selection follows DESIGN.md §5: C2-only > Plus/4 3.5 > V2,
; scanning tokens outside REM/string/DATA contexts.

.include "common/zp.inc"
.include "common/constants.asm"
.include "program_formats.inc"

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

; A resident codec helper may temporarily map a program-data page at $DE00.
; Its caller can be executing from that same window, so it must restore the
; page captured by __program_stream_probe before it returns.  Preserve the
; complete public result (A and flags); X/Y are documented scratch registers.
.macro program_stream_return_to_code
    php
    pha
    ldx program_stream_code_block
    lda program_stream_code_page
    jsr georam_select
    pla
    plp
    rts
.endmacro

.import arena_handle_valid
.import arena_select_page
.import georam_select

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
; Selection to restore before a resident helper returns to an XIP caller.
program_stream_code_block: .res 1
program_stream_code_page: .res 1
program_codec_copy_count: .res 1
program_stream_validation_start: .res 2
program_codec_output_descriptor: .res 8
program_codec_page_buffer: .res 256
program_codec_load_lo: .res 1
program_codec_load_hi: .res 1
program_codec_link_base_hi: .res 1
program_codec_save_flags: .res 1
program_codec_scan_mode: .res 1

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

; Token bytes used by SAVE format classification (outside REM/string/DATA).
TOKEN_DATA = $83
TOKEN_REM = $8F
TOKEN_C2_COMPILE = $CE
TOKEN_C2_QUIT = $D3
TOKEN_C2_BASIC = $D4
TOKEN_C2_PREFIX = $FE
TOKEN_STOCK_MAX = $CB

; program_codec_save_flags bits while scanning.
SAVE_FLAG_BASIC35 = $01
SAVE_FLAG_C2 = $02

; Scan modes for program_select_save_format.
SCAN_MODE_NORMAL = 0
SCAN_MODE_STRING = 1
SCAN_MODE_REM = 2
SCAN_MODE_DATA = 3
SCAN_MODE_DATA_STRING = 4

; Load and validate the arena-backed whole-program descriptor from X/Y.
; The former one-byte bounded record ABI is rejected.
.proc __program_stream_probe
    stx program_stream_descriptor
    sty program_stream_descriptor+1
    ; This helper runs in resident RAM, but it is also entered from XIP pages.
    ; Capture that executable mapping before any arena validation remaps $DE00.
    lda zp_gr_block
    sta program_stream_code_block
    lda zp_gr_page
    sta program_stream_code_page
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
    ; No data-page mapping may survive the return to an XIP caller.  The byte
    ; helpers select their data page explicitly and invalidate this cache.
    ldx program_stream_code_block
    lda program_stream_code_page
    jsr georam_select
    lda #$00
    sta program_stream_page_valid
    ldx program_stream_descriptor
    ldy program_stream_descriptor+1
    lda #$01
    clc
    rts
@invalid:
    jmp @error
@error:
    ldx program_stream_code_block
    lda program_stream_code_page
    jsr georam_select
    lda #$00
    sta program_stream_page_valid
    ldx program_stream_descriptor
    ldy program_stream_descriptor+1
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Set linked-line load base for BASIC V2 ($0801 / link base $07FF).
.proc __program_stream_set_v2_base
    lda #STOCK_BASICV2_LOAD_LO
    sta program_codec_load_lo
    lda #STOCK_BASICV2_LOAD_HI
    sta program_codec_load_hi
    lda #$07
    sta program_codec_link_base_hi
    rts
.endproc

; Set linked-line load base for Plus/4 BASIC 3.5 ($1001 / link base $0FFF).
.proc __program_stream_set_plus4_base
    lda #STOCK_BASICV35_LOAD_LO
    sta program_codec_load_lo
    lda #STOCK_BASICV35_LOAD_HI
    sta program_codec_load_hi
    lda #$0F
    sta program_codec_link_base_hi
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
    ; External next address minus load address is the normalized next offset.
    sec
    lda program_stream_link
    sbc program_codec_load_lo
    sta program_stream_link
    lda program_stream_link+1
    sbc program_codec_load_hi
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
    lda program_stream_validation_start
    sta program_stream_index
    lda program_stream_validation_start+1
    sta program_stream_index+1
    lda #$00
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
; the $0801 load address has been prepended.  This is placed with the V2
; encoder entry: the resident orchestration keeps page 8 selected while it
; calls this helper, so the linked-line rewrite itself executes from geoRAM.
.segment "GEORAM_PAGE_8"

; program_encode_stock
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Prepends $0801 and canonically rebuilds every linked-line pointer.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
.export program_encode_stock
program_encode_stock:
    jsr __program_stream_probe
    bcs @error
    jsr __program_stream_set_v2_base
    jmp __program_stream_encode_stock
@error:
    rts

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
    ; External offset maps to absolute address (load - 2) + offset.
    clc
    lda program_stream_scan
    adc #$FF
    sta program_stream_record_length
    lda program_stream_scan+1
    adc program_codec_link_base_hi
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

.assert * - program_encode_stock <= $FA, error, "program codec page 8 exceeds geoRAM page"

.segment "CODE"

; Shared setup for the BASIC 3.5 encoder.  It runs from resident RAM while
; page 10 remains the caller's executable mapping, then transfers only the
; page-sensitive canonical link rewrite back to that XIP page.
.proc __program_stream_encode_basic35_prepare
    lda #$00
    sta program_stream_validation_start
    sta program_stream_validation_start+1
    jsr __program_stream_validate_normalized
    bcs @error
    jsr __program_stream_clone_for_encode
    bcs @error
    jsr __program_stream_load_start
    lda #$02
    jsr __program_stream_shift_right
    bcs @error
    lda #$00
    sta program_stream_index
    sta program_stream_index+1
    lda program_codec_load_lo
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    inc program_stream_index
    lda program_codec_load_hi
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    ldx #$00
    lda #$0A
    jsr georam_select
    jmp __program_stream_canonicalize_basic35
@error:
    lda #ERR_SYNTAX
    sec
    rts
.endproc

; Page 10 owns the Plus/4 encoder.  Its link rewrite is deliberately local:
; a normal-RAM caller must never jump into the V2 page-8 body.
.segment "GEORAM_PAGE_10"

; program_encode_basic35
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Prepends $1001 and canonically rebuilds Plus/4 linked-line pointers.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
.export program_encode_basic35
program_encode_basic35:
    jsr __program_stream_probe
    bcs @error
    jsr __program_stream_set_plus4_base
    jsr __program_stream_encode_basic35_prepare
    rts
@error:
    rts

.proc __program_stream_canonicalize_basic35
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
    jmp __program_stream_store_length
@record:
    clc
    lda program_stream_index
    adc program_stream_record_length
    sta program_stream_scan
    lda program_stream_index+1
    adc program_stream_record_length+1
    sta program_stream_scan+1
    jcs @error
    clc
    lda program_stream_scan
    adc #$FF
    sta program_stream_record_length
    lda program_stream_scan+1
    adc program_codec_link_base_hi
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

.assert * - program_encode_basic35 <= $FA, error, "program codec page 10 exceeds geoRAM page"

.segment "CODE"

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
    program_stream_return_to_code
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
    program_stream_return_to_code
@error:
    lda #ERR_OUT_OF_DATA
    sec
    program_stream_return_to_code
.endproc

__program_stream_encode_stock:
    lda #$00
    sta program_stream_validation_start
    sta program_stream_validation_start+1
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
    lda program_codec_load_lo
    sta program_stream_value
    jsr __program_stream_write
    bcs @error
    inc program_stream_index
    lda program_codec_load_hi
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

; The C2P1 decoder is a cold codec path.  Keep its complete validation and
; publication decision tree together in its assigned XIP page; callers enter
; it through the geoRAM dispatcher, never through a resident mirror.
.segment "GEORAM_PAGE_11"

; program_decode_extended
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Decode validates and removes the C2P1 envelope.  Clobbers A, X, Y; uses the
; expression-pointer workspace.  C set reports a malformed stream.
.export program_decode_extended
program_decode_extended:
    jsr __program_stream_probe
    bcs @error
    jsr __program_stream_decode_extended
    rts
@error:
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
    jsr __program_stream_validate_extended_tail
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
    ; A zero-length body is the valid empty-program representation. Any
    ; non-empty body must be the normalized logical stream before the header
    ; is removed, so malformed input cannot be published in place.
    lda program_stream_scan
    ora program_stream_scan+1
    beq @body_valid
    lda #$10
    sta program_stream_validation_start
    lda #$00
    sta program_stream_validation_start+1
    jsr __program_stream_validate_normalized
    bcs @error
@body_valid:
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

; Return to resident helpers after the XIP-local decode body.  The following
; encoder owns a separate page because it mutates and scans independently.
.segment "GEORAM_PAGE_12"

; program_encode_extended
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Encode prepends a canonical C2P1 envelope.  Clobbers A, X, Y; uses the
; expression-pointer workspace.  C set reports invalid input or capacity.
.export program_encode_extended
program_encode_extended:
    jsr __program_stream_probe
    bcs @error
    jsr __program_stream_encode_extended
    rts
@error:
    rts

__program_stream_encode_extended:
    lda program_stream_length
    ora program_stream_length+1
    beq @body_valid
    lda #$00
    sta program_stream_validation_start
    sta program_stream_validation_start+1
    jsr __program_stream_validate_normalized
    jcs @error
@body_valid:
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

.segment "CODE"

; The fixed reserved-byte and checksum tail is shared data validation.  The
; XIP page performs the envelope's identity, version, and exact body-length
; checks before this helper runs; keeping this loop resident lets the complete
; public decoder fit its single executable page.
.proc __program_stream_validate_extended_tail
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
.endproc

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
    lda zp_gr_block
    sta program_stream_code_block
    lda zp_gr_page
    sta program_stream_code_page
    lda program_stream_index+1
    clc
    adc program_stream_start_page
    bcs @error
    sta program_stream_target_page
    lda program_stream_target_page
    ldx program_stream_arena
    ldy program_stream_generation
    jsr arena_select_page
    bcs @error
    ldy program_stream_index
    lda $DE00,y
    sta program_stream_value
    ldx program_stream_code_block
    lda program_stream_code_page
    jsr georam_select
    lda #$00
    sta program_stream_page_valid
    lda program_stream_value
    clc
    rts
@error:
    ldx program_stream_code_block
    lda program_stream_code_page
    jsr georam_select
    lda #$00
    sta program_stream_page_valid
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Write program_stream_value at program_stream_index.
.proc __program_stream_write
    lda zp_gr_block
    sta program_stream_code_block
    lda zp_gr_page
    sta program_stream_code_page
    lda program_stream_index+1
    clc
    adc program_stream_start_page
    bcs @error
    ldx program_stream_arena
    ldy program_stream_generation
    jsr arena_select_page
    bcs @error
    ldy program_stream_index
    lda program_stream_value
    sta $DE00,y
    ldx program_stream_code_block
    lda program_stream_code_page
    jsr georam_select
    lda #$00
    sta program_stream_page_valid
    clc
    rts
@error:
    ldx program_stream_code_block
    lda program_stream_code_page
    jsr georam_select
    lda #$00
    sta program_stream_page_valid
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
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

; program_decode_stock
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Removes the BASIC V2 $0801 load address only after validating the program.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
; program_encode_stock
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Prepends $0801 and canonically rebuilds every linked-line pointer.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
; program_select_save_format
; Inputs: X/Y = arena-backed normalized logical program descriptor.
; Outputs: A = SAVE_FORMAT_V2 / SAVE_FORMAT_BASICV35 / SAVE_FORMAT_C2P1, C=error.
; Scans tokens outside REM, string, and DATA contexts. Priority: C2 > 3.5 > V2.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
; program_classify_file is a cold read-only codec operation.  Its entry and
; complete decision tree execute from the generated geoRAM page 6 (routine
; ID 335).  It may call the shared descriptor/page-selection helpers in RAM,
; but never has a resident mirror of its own.
.segment "GEORAM_PAGE_6"

; program_classify_file
; Inputs: X/Y = arena-backed whole-program descriptor.
; Outputs: A=0 V2, A=1 C2P1, A=2 Plus/4; C=1 on invalid descriptor/format.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
.export program_classify_file
program_classify_file:
    jsr __program_stream_probe
    bcs @error
    jmp __program_stream_classify
@error:
    rts

; Classify on-disk image: A=0 V2 ($0801), A=1 C2P1, A=2 Plus/4 ($1001).
; Note: file-class ids differ from SAVE_FORMAT_* (select uses C2 > 3.5 > V2).
__program_stream_classify:
    jsr __program_stream_load_start
    lda program_stream_length+1
    bne @select
    lda program_stream_length
    cmp #$04
    bcc @error
@select:
    ; Do not select a data page directly here: this routine itself executes
    ; at $DE00.  The stream helpers restore this routine's XIP mapping before
    ; returning, including their error path.
    lda #$00
    ldx #$00
    jsr __program_stream_read_ax
    bcs @error
    cmp #'C'
    beq @extended
    ; Both V2 and Plus/4 PRG headers begin with $01.
    cmp #$01
    bne @error
    lda #$01
    ldx #$00
    jsr __program_stream_read_ax
    bcs @error
    cmp #STOCK_BASICV2_LOAD_HI
    beq @v2
    cmp #STOCK_BASICV35_LOAD_HI
    beq @plus4
    jmp @error
@v2:
    lda #$00
    clc
    rts
@plus4:
    lda #$02
    clc
    rts
@extended:
    lda #$01
    ldx #$00
    jsr __program_stream_read_ax
    bcs @error
    cmp #'2'
    bne @error
    lda #$02
    ldx #$00
    jsr __program_stream_read_ax
    bcs @error
    cmp #'P'
    bne @error
    lda #$03
    ldx #$00
    jsr __program_stream_read_ax
    bcs @error
    cmp #'1'
    bne @error
    lda #$01
    clc
    rts
@error:
    lda #ERR_SYNTAX
    sec
    rts

; Keep this entry path page-local.  A routine in the mapped $DE00 page must
; not silently spill into the following physical page.
.assert * - program_classify_file <= $FA, error, "program_classify_file exceeds geoRAM page 6"

.segment "CODE"

; Read byte at A/X offset (low/high) into A.
.proc __program_stream_read_ax
    sta program_stream_index
    stx program_stream_index+1
    jmp __program_stream_read
.endproc

; The header probe is resident so the shared Plus/4 decoder can use it too.
; It deliberately leaves the caller's geoRAM code page selected before entering
; the page-7 linked-line validator below.
.segment "CODE"
.proc __program_stream_validate_stock_prepare
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
    cmp program_codec_load_lo
    jne @error
    jmp __program_stream_validate_stock
@error:
    lda #ERR_SYNTAX
    sec
    rts
.endproc

; Page 9 owns the BASIC 3.5 decoder.  This resident preamble is entered from
; that XIP page and deliberately jumps back to its page-local traversal while
; page 9 remains selected.  It must not jump into the V2 page-7 validator.
.proc __program_stream_validate_basic35_prepare
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
    cmp program_codec_load_lo
    jne @error
    jmp __program_stream_validate_basic35
@error:
    lda #ERR_SYNTAX
    sec
    rts
.endproc

; Compare the just-consumed linked-line offset with the stock absolute link.
; This arithmetic is shared resident glue; the page-7 routine owns the stream
; traversal and all page-sensitive byte reads.
.proc __program_stream_validate_stock_link
    ; Expected pointer is load + (next stream offset - 2) = (load-2) + offset.
    clc
    lda program_stream_index
    adc #$FF
    sta program_stream_scan
    lda program_stream_index+1
    adc program_codec_link_base_hi
    sta program_stream_scan+1
    lda program_stream_scan
    cmp program_stream_link
    bne @error
    lda program_stream_scan+1
    cmp program_stream_link+1
    bne @error
    clc
    rts
@error:
    sec
    rts
.endproc

; Page 7 owns the public V2 decode entry and its linked-line validation pass.
; Both execute while the dispatcher keeps this mapping selected.  The
; remaining stream transforms are deliberately resident shared helpers, which
; never remap the code page and therefore safely return into this page.
.segment "GEORAM_PAGE_7"

; program_decode_stock
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Removes the BASIC V2 $0801 load address only after validating the program.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
.export program_decode_stock
program_decode_stock:
    jsr __program_stream_probe
    bcs @error
    jsr __program_stream_set_v2_base
    jmp __program_stream_decode_stock
@error:
    rts

; Validate the linked-line stream for the active load base without changing it.
.proc __program_stream_validate_stock
    lda #$01
    ldx #$00
    jsr __program_stream_read_ax
    jcs @error
    cmp program_codec_load_hi
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
    jsr __program_stream_validate_stock_link
    jcs @error
    jmp @line
@error:
    lda #ERR_SYNTAX
    sec
    rts
.endproc

.assert * - program_decode_stock <= $FA, error, "program codec page 7 exceeds geoRAM page"

; program_decode_basic35 is independent of the V2 page-7 entry.  A resident
; wrapper cannot tail-jump into an XIP page, so the complete public Plus/4
; entry and its page-sensitive linked-line traversal live in its assigned
; page 9 and are entered only through the geoRAM dispatcher.
.segment "GEORAM_PAGE_9"

; program_decode_basic35
; Inputs/outputs: X/Y = arena-backed whole-program descriptor.
; Validates Plus/4 $1001 linked-line PRG and normalizes to logical records.
; Clobbers: A, X, Y. Zero page: expression pointer workspace.
.export program_decode_basic35
program_decode_basic35:
    jsr __program_stream_probe
    bcs @error
    jsr __program_stream_set_plus4_base
    jsr __program_stream_validate_basic35_prepare
    bcs @error
    jmp __program_stream_decode_stock_validated
@error:
    rts

; Page-local linked-line validator for the active Plus/4 load base.
.proc __program_stream_validate_basic35
    lda #$01
    ldx #$00
    jsr __program_stream_read_ax
    jcs @error
    cmp program_codec_load_hi
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
    jsr __program_stream_validate_stock_link
    jcs @error
    jmp @line
@error:
    lda #ERR_SYNTAX
    sec
    rts
.endproc

.assert * - program_decode_basic35 <= $FA, error, "program codec page 9 exceeds geoRAM page"

.segment "CODE"

; Classify a token byte in A for SAVE format selection.
; Sets SAVE_FLAG_C2 / SAVE_FLAG_BASIC35 in program_codec_save_flags.
.segment "GEORAM_PAGE_13"

; program_select_save_format
; Inputs: X/Y = arena-backed normalized logical program descriptor.
; Outputs: A = SAVE_FORMAT_V2 / SAVE_FORMAT_BASICV35 / SAVE_FORMAT_C2P1,
; C=error.  Clobbers A, X, Y; uses expression-pointer workspace.
.export program_select_save_format
program_select_save_format:
    jsr __program_stream_probe
    bcs @done_error
    jsr __program_stream_select_save_format
    rts
@done_error:
    lda #ERR_SYNTAX
    sec
    rts

.proc __program_codec_classify_token
    cmp #TOKEN_C2_COMPILE
    beq @c2
    cmp #TOKEN_C2_QUIT
    beq @c2
    cmp #TOKEN_C2_BASIC
    beq @c2
    cmp #TOKEN_C2_PREFIX
    beq @c2
    cmp #TOKEN_STOCK_MAX
    bcc @stock
    beq @stock
    ; Token above stock V2 range and not C2-only → BASIC 3.5 / Plus/4.
    lda program_codec_save_flags
    ora #SAVE_FLAG_BASIC35
    sta program_codec_save_flags
    rts
@c2:
    lda program_codec_save_flags
    ora #SAVE_FLAG_C2
    sta program_codec_save_flags
@stock:
    rts
.endproc

; Scan normalized logical program for SAVE format class.  This whole state
; machine belongs to the assigned XIP page, including the public dispatcher
; entry and token classifier, so no resident format-selection mirror remains.

__program_stream_select_save_format:
    jsr __program_stream_load_start
    lda #$00
    sta program_codec_save_flags
    sta program_stream_index
    sta program_stream_index+1
@line:
    jsr __program_stream_index_before_length
    jcs @done_error
    jsr __program_stream_read
    jcs @done_error
    sta program_stream_record_length
    jsr __program_stream_inc_index
    jsr __program_stream_index_before_length
    jcs @done_error
    jsr __program_stream_read
    jcs @done_error
    sta program_stream_record_length+1
    jsr __program_stream_inc_index
    ora program_stream_record_length
    bne @record
    ; Terminal zero-length record must consume the stream exactly.
    lda program_stream_index
    cmp program_stream_length
    jne @done_error
    lda program_stream_index+1
    cmp program_stream_length+1
    jne @done_error
    jmp @finish
@record:
    ; Skip line number.
    jsr __program_stream_index_before_length
    jcs @done_error
    jsr __program_stream_inc_index
    jsr __program_stream_index_before_length
    jcs @done_error
    jsr __program_stream_inc_index
    ; Remaining body bytes after line number = record_length - 2.
    sec
    lda program_stream_record_length
    sbc #$02
    sta program_stream_scan
    lda program_stream_record_length+1
    sbc #$00
    sta program_stream_scan+1
    jcc @done_error
    lda #SCAN_MODE_NORMAL
    sta program_codec_scan_mode
@body:
    jsr __program_stream_scan_body
    jcs @done_error
    lda program_codec_save_flags
    and #SAVE_FLAG_C2
    bne @finish
    jmp @line
@finish:
    lda program_codec_save_flags
    and #SAVE_FLAG_C2
    beq @check_35
    lda #SAVE_FORMAT_C2P1
    clc
    rts
@check_35:
    lda program_codec_save_flags
    and #SAVE_FLAG_BASIC35
    beq @v2
    lda #SAVE_FORMAT_BASICV35
    clc
    rts
@v2:
    lda #SAVE_FORMAT_V2
    clc
    rts
@done_error:
    lda #ERR_SYNTAX
    sec
    rts

.assert * - program_select_save_format <= $FA, error, "program_select_save_format exceeds geoRAM page 13"

.segment "CODE"

; Scan one normalized line body after the XIP selector has established the
; record bounds and lexical mode.  This shared normal-RAM helper contains no
; public codec operation or format decision; page 13 retains descriptor
; validation, record framing, format priority, and final result selection.
.proc __program_stream_scan_body
@body:
    lda program_stream_scan
    ora program_stream_scan+1
    bne :+
    jmp @done
:
    jsr __program_stream_index_before_length
    bcc :+
    jmp @error
:
    jsr __program_stream_read
    bcc :+
    jmp @error
:
    sta program_stream_value
    jsr __program_stream_inc_index
    lda program_stream_scan
    bne @dec_lo
    dec program_stream_scan+1
@dec_lo:
    dec program_stream_scan
    lda program_codec_scan_mode
    cmp #SCAN_MODE_REM
    beq @body
    cmp #SCAN_MODE_STRING
    beq @in_string
    cmp #SCAN_MODE_DATA_STRING
    beq @in_data_string
    cmp #SCAN_MODE_DATA
    beq @in_data
    lda program_stream_value
    cmp #'"'
    beq @start_string
    cmp #TOKEN_REM
    beq @start_rem
    cmp #TOKEN_DATA
    beq @start_data
    cmp #$80
    bcc @body
    jsr __program_codec_classify_token
    lda program_codec_save_flags
    and #SAVE_FLAG_C2
    beq @body
    clc
    rts
@start_string:
    lda #SCAN_MODE_STRING
    sta program_codec_scan_mode
    jmp @body
@start_rem:
    lda #SCAN_MODE_REM
    sta program_codec_scan_mode
    jmp @body
@start_data:
    lda #SCAN_MODE_DATA
    sta program_codec_scan_mode
    jmp @body
@in_string:
    lda program_stream_value
    cmp #'"'
    beq :+
    jmp @body
:
    lda #SCAN_MODE_NORMAL
    sta program_codec_scan_mode
    jmp @body
@in_data_string:
    lda program_stream_value
    cmp #'"'
    beq :+
    jmp @body
:
    lda #SCAN_MODE_DATA
    sta program_codec_scan_mode
    jmp @body
@in_data:
    lda program_stream_value
    cmp #'"'
    beq @data_string
    cmp #':'
    beq :+
    jmp @body
:
    lda #SCAN_MODE_NORMAL
    sta program_codec_scan_mode
    jmp @body
@data_string:
    lda #SCAN_MODE_DATA_STRING
    sta program_codec_scan_mode
    jmp @body
@done:
    clc
    rts
@error:
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
    jsr __program_stream_validate_stock_prepare
    bcs @error
    jmp __program_stream_decode_stock_validated
@error:
    lda #ERR_SYNTAX
    sec
    rts

; Decode transform after an XIP page has already validated the active
; V2/3.5 linked-line stream.  This resident tail never changes $DE00.
__program_stream_decode_stock_validated:
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
