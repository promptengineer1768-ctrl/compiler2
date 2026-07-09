; src/geoasm/ir_builder.asm
; Compact intermediate-representation record builder.

.include "common/zp.inc"
.include "common/constants.asm"

IR_END           = $00
IR_STMT          = $01
IR_EXPR          = $02
IR_VAR_REF       = $03
IR_ARRAY_REF     = $04
IR_STRING_REF    = $05
IR_BRANCH        = $06
IR_LOOP          = $07
IR_LITERAL_INT   = $08
IR_LITERAL_FLOAT = $09
IR_LITERAL_STR   = $0A

IR_BUFFER_SIZE = 128
IR_RECORD_SIZE = 4

.segment "BSS"
.export ir_buffer
ir_buffer:
    .res IR_BUFFER_SIZE
.export ir_buffer_len
ir_buffer_len:
    .res 1
ir_arg_a:
    .res 1
ir_arg_x:
    .res 1
ir_arg_y:
    .res 1

.segment "GEOASM"

; ir_init
; Purpose: Reset the current line IR buffer.
; Inputs: none.
; Outputs: ir_buffer_len = 0.
; Side effects: Discards all current line records.
; Clobbers: A.
; Flags: C clear.
; Zero page: none.
.export ir_init
ir_init:
    lda #0
    sta ir_buffer_len
    clc
    rts

; ir_finish_line
; Purpose: Append the end-of-line record.
; Inputs: none.
; Outputs: One IR_END record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_finish_line
ir_finish_line:
    lda #0
    sta ir_arg_a
    sta ir_arg_x
    sta ir_arg_y
    lda #IR_END
    jmp _ir_emit_record

; ir_get_buf_ptr - Return the current typed-IR write position.
; Inputs: none. Outputs: X/Y = ir_buffer + ir_buffer_len.
; Side effects: none. Clobbers: A, X, Y. Flags: C clear. Zero page: none.
.export ir_get_buf_ptr
ir_get_buf_ptr:
    lda #<ir_buffer
    clc
    adc ir_buffer_len
    tax
    lda #>ir_buffer
    adc #0
    tay
    clc
    rts

; ir_emit_stmt
; Purpose: Append a statement record.
; Inputs: A/X/Y are the statement payload.
; Outputs: One IR_STMT record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_emit_stmt
ir_emit_stmt:
    jsr _ir_save_args
    lda #IR_STMT
    jmp _ir_emit_record

; ir_emit_expr
; Purpose: Append an expression record.
; Inputs: A/X/Y are the expression payload.
; Outputs: One IR_EXPR record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_emit_expr
ir_emit_expr:
    jsr _ir_save_args
    lda #IR_EXPR
    jmp _ir_emit_record

; ir_emit_var_ref
; Purpose: Append a variable-reference record.
; Inputs: A/X/Y are the reference payload.
; Outputs: One IR_VAR_REF record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_emit_var_ref
ir_emit_var_ref:
    jsr _ir_save_args
    lda #IR_VAR_REF
    jmp _ir_emit_record

; ir_emit_array_ref
; Purpose: Append an array-reference record.
; Inputs: A/X/Y are the reference payload.
; Outputs: One IR_ARRAY_REF record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_emit_array_ref
ir_emit_array_ref:
    jsr _ir_save_args
    lda #IR_ARRAY_REF
    jmp _ir_emit_record

; ir_emit_string_ref
; Purpose: Append a string-reference record.
; Inputs: A/X/Y are the reference payload.
; Outputs: One IR_STRING_REF record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_emit_string_ref
ir_emit_string_ref:
    jsr _ir_save_args
    lda #IR_STRING_REF
    jmp _ir_emit_record

; ir_emit_branch
; Purpose: Append a branch record.
; Inputs: A/X/Y are the branch payload.
; Outputs: One IR_BRANCH record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_emit_branch
ir_emit_branch:
    jsr _ir_save_args
    lda #IR_BRANCH
    jmp _ir_emit_record

; ir_emit_loop
; Purpose: Append a loop record.
; Inputs: A/X/Y are the loop payload.
; Outputs: One IR_LOOP record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_emit_loop
ir_emit_loop:
    jsr _ir_save_args
    lda #IR_LOOP
    jmp _ir_emit_record

; ir_emit_literal_int
; Purpose: Append an integer-literal record.
; Inputs: A/X/Y are the literal payload.
; Outputs: One IR_LITERAL_INT record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_emit_literal_int
ir_emit_literal_int:
    jsr _ir_save_args
    lda #IR_LITERAL_INT
    jmp _ir_emit_record

; ir_emit_literal_float
; Purpose: Append a floating-literal record.
; Inputs: A/X/Y are the literal payload.
; Outputs: One IR_LITERAL_FLOAT record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_emit_literal_float
ir_emit_literal_float:
    jsr _ir_save_args
    lda #IR_LITERAL_FLOAT
    jmp _ir_emit_record

; ir_emit_literal_str
; Purpose: Append a string-literal record.
; Inputs: A/X/Y are the literal payload.
; Outputs: One IR_LITERAL_STR record appended.
; Side effects: Advances ir_buffer_len by four.
; Clobbers: A, X.
; Flags: C clear on success, set when the buffer is full.
; Zero page: none.
.export ir_emit_literal_str
ir_emit_literal_str:
    jsr _ir_save_args
    lda #IR_LITERAL_STR
    jmp _ir_emit_record

_ir_save_args:
    sta ir_arg_a
    stx ir_arg_x
    sty ir_arg_y
    rts

_ir_emit_record:
    pha
    ldx ir_buffer_len
    cpx #IR_BUFFER_SIZE-IR_RECORD_SIZE+1
    bcs @full
    pla
    sta ir_buffer, x
    lda ir_arg_a
    sta ir_buffer+1, x
    lda ir_arg_x
    sta ir_buffer+2, x
    lda ir_arg_y
    sta ir_buffer+3, x
    txa
    clc
    adc #IR_RECORD_SIZE
    sta ir_buffer_len
    clc
    rts
@full:
    pla
    sec
    rts
