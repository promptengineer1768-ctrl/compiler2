; src/geoasm/codegen.asm
; Typed-IR to executable 6502 lowering.

.include "common/zp.inc"

.macro jcs target
    bcc :+
    jmp target
:
.endmacro

CODEGEN_BUFFER_SIZE = 112
CODEGEN_RELOC_CAPACITY = 8
CODEGEN_FOR_VAL_MAX = 3

IR_END           = $00
IR_STMT          = $01
IR_EXPR          = $02
IR_VAR_REF       = $03
IR_LOOP          = $07
IR_LITERAL_INT   = $08
IR_LITERAL_FLOAT = $09
IR_LITERAL_STR   = $0A
IR_RECORD_SIZE   = 4
; Soft cap so FOR unroll can use ir_buffer+N,X without overflow checks.
IR_BUFFER_SOFT_MAX = 128 - 16

STMT_PRINT = $01
STMT_FOR   = $02
STMT_LET   = $04
STMT_NEXT  = $05
STMT_END   = $06

; Pending value kinds for PRINT/LET lowering.
PEND_NONE   = 0
PEND_STR    = 1
PEND_INT    = 2
PEND_VAR    = 3
PEND_TI_DIV60 = 4

PRINT_FLAG_TRAILING_SEMICOLON = $01

; Expression operator ids (must match parser.asm).
OP_UNARY_PLUS  = $80
OP_UNARY_MINUS = $81

TYPE_INT1   = $01
TYPE_INT2   = $02
TYPE_FLOAT  = $00

OP_LDA_IMM = $A9
OP_LDX_IMM = $A2
OP_LDY_IMM = $A0
OP_STA_ZP  = $85
OP_STX_ZP  = $86
OP_STY_ZP  = $84
OP_JSR     = $20
OP_RTS     = $60
OP_STA_ABS = $8D

CODEGEN_EXPR_STACK_MAX = 3

.import ir_buffer, ir_buffer_len
.import io_print_cstr, io_print_newline, io_print_value
.import pipeline_source_lo, pipeline_source_hi
.import math_int_to_float
.import pl_current_index
.import ctrl_for_next
.import kernal_rdtim, kernal_settim
.import system_ti_div60

.segment "BSS"
.export codegen_buffer
codegen_buffer:
    .res CODEGEN_BUFFER_SIZE
.export codegen_buffer_len
codegen_buffer_len:
    .res 1
codegen_arg_a:
    .res 1
codegen_arg_x:
    .res 1
codegen_arg_y:
    .res 1
codegen_ir_offset:
    .res 1
codegen_ir_arg_a:
    .res 1
codegen_lit_start:
    .res 1
codegen_lit_len:
    .res 1
codegen_pend_kind:
    .res 1
codegen_pend_a:
    .res 1
codegen_pend_x:
    .res 1
codegen_str_addr:
    .res 2
codegen_parse_val:
    .res 2
codegen_for_n:
    .res 1
codegen_for_vals:
    .res CODEGEN_FOR_VAL_MAX * 2
codegen_tgt_start:
    .res 1
codegen_tgt_len:
    .res 1
; Postfix integer expression stack (lo/hi pairs).
codegen_expr_sp:
    .res 1
codegen_expr_stack:
    .res CODEGEN_EXPR_STACK_MAX * 2
codegen_print_flags:
    .res 1
; Scratch for compile-time 16-bit multiply/divide of literal operands.
codegen_muldiv_lo:
    .res 1
codegen_muldiv_hi:
    .res 1
codegen_muldiv_cnt:
    .res 1
; Immediate-mode single-letter integer cells A-Z (stock-like default 0).
.export imm_var_int
imm_var_int:
    .res 26 * 2
; Multi-line FOR/NEXT state shared with program_lines_run.
.export for_continue, for_active, for_var_idx, for_limit, for_step, for_body_pc
for_continue:
    .res 1
for_active:
    .res 1
for_var_idx:
    .res 1
for_limit:
    .res 2
for_step:
    .res 2
for_body_pc:
    .res 1
.export codegen_reloc_count, codegen_reloc_table
codegen_reloc_count:
    .res 1
codegen_reloc_table:
    .res CODEGEN_RELOC_CAPACITY * 3
; Set only by executable END lowering. program_lines_run clears this at the
; beginning of RUN and stops dispatching stored lines once END executes.
.export codegen_program_stop
codegen_program_stop:
    .res 1

.segment "GEOASM"

; codegen_init - Reset native emitter state.
.export codegen_init
codegen_init:
    lda #0
    sta codegen_buffer_len
    sta codegen_reloc_count
    sta codegen_pend_kind
    sta codegen_for_n
    sta codegen_expr_sp
    sta codegen_print_flags
    clc
    rts

.export codegen_finish_line
codegen_finish_line:
    lda #OP_RTS
    jmp _codegen_append_a

.macro CODEGEN_EMITTER name
.export name
name:
    jsr _codegen_save_args
    jmp _codegen_emit_payload
.endmacro

CODEGEN_EMITTER codegen_emit_stmt
CODEGEN_EMITTER codegen_emit_for_fast
CODEGEN_EMITTER codegen_emit_for_generic
CODEGEN_EMITTER codegen_emit_do_fast
CODEGEN_EMITTER codegen_emit_do_generic
CODEGEN_EMITTER codegen_emit_if
CODEGEN_EMITTER codegen_emit_gosub
CODEGEN_EMITTER codegen_emit_return
CODEGEN_EMITTER codegen_emit_on
CODEGEN_EMITTER codegen_emit_print
CODEGEN_EMITTER codegen_emit_input
CODEGEN_EMITTER codegen_emit_let
CODEGEN_EMITTER codegen_emit_dim
CODEGEN_EMITTER codegen_emit_data
CODEGEN_EMITTER codegen_emit_exit
CODEGEN_EMITTER codegen_emit_read

.export codegen_emit_reloc
codegen_emit_reloc:
    sta codegen_arg_a
    stx codegen_arg_x
    sty codegen_arg_y
    ldx codegen_reloc_count
    cpx #CODEGEN_RELOC_CAPACITY
    bcs @full
    txa
    asl
    clc
    adc codegen_reloc_count
    tay
    lda codegen_arg_a
    sta codegen_reloc_table,y
    lda codegen_arg_x
    sta codegen_reloc_table+1,y
    lda codegen_arg_y
    sta codegen_reloc_table+2,y
    inc codegen_reloc_count
    clc
    rts
@full:
    sec
    rts

; codegen_emit_ir - Lower IR into executable scratch code.
.export codegen_emit_ir
codegen_emit_ir:
    jsr codegen_init
    lda #0
    sta codegen_ir_offset
@next:
    ldx codegen_ir_offset
    cpx ir_buffer_len
    bcc @have
    jmp @malformed
@have:
    lda ir_buffer,x
    bne @not_end
    jmp @finish
@not_end:
    cmp #IR_LITERAL_STR
    bne @not_str
    jmp @lit_str
@not_str:
    cmp #IR_LITERAL_FLOAT
    beq @lit_num
    cmp #IR_LITERAL_INT
    beq @lit_num
    cmp #IR_VAR_REF
    bne @not_var
    jmp @var_ref
@not_var:
    cmp #IR_EXPR
    bne @not_expr
    jmp @expr
@not_expr:
    cmp #IR_LOOP
    bne @not_loop
    jmp @loop_rec
@not_loop:
    cmp #IR_STMT
    beq @stmt
    jmp @skip
@stmt:
    lda ir_buffer+1,x
    cmp #STMT_PRINT
    bne @not_print
    jmp @print
@not_print:
    cmp #STMT_LET
    bne @not_let
    jmp @let
@not_let:
    cmp #STMT_FOR
    bne @not_for
    jmp @for
@not_for:
    cmp #STMT_NEXT
    bne @not_next
    jmp @next_stmt
@not_next:
    cmp #STMT_END
    bne @other_stmt
    jmp @end_stmt
@other_stmt:
    sta codegen_ir_arg_a
    ldy ir_buffer+3,x
    lda ir_buffer+2,x
    tax
    lda codegen_ir_arg_a
    jsr codegen_emit_stmt
    jcs @error
    jmp @skip
@lit_str:
    lda ir_buffer+1,x
    sta codegen_lit_start
    lda ir_buffer+2,x
    sta codegen_lit_len
    lda #PEND_STR
    sta codegen_pend_kind
    jmp @skip
@lit_num:
    lda ir_buffer+1,x
    sta codegen_lit_start
    lda ir_buffer+2,x
    sta codegen_lit_len
    jsr _codegen_parse_int_span
    lda #PEND_INT
    sta codegen_pend_kind
    jsr _codegen_expr_push
    jcs @error
    jmp @skip
@var_ref:
    lda ir_buffer+1,x
    sta codegen_lit_start
    lda ir_buffer+2,x
    sta codegen_lit_len
    lda #PEND_VAR
    sta codegen_pend_kind
    ; Push current cell value for postfix ops; keep PEND_VAR so bare
    ; PRINT A emits a runtime load (required inside FOR loops).
    jsr _codegen_materialize_pend
    jsr _codegen_expr_push
    jcs @error
    lda #PEND_VAR
    sta codegen_pend_kind
    jmp @skip
@expr:
    ; IR_EXPR A = operator char or OP_* code; apply to postfix stack.
    lda ir_buffer+1,x
    jsr _codegen_expr_apply
    jcs @error
    jmp @skip
@loop_rec:
    ; IR_LOOP payload: A=kind, X=var_start, Y=var_len
    lda ir_buffer+2,x
    sta codegen_lit_start
    lda ir_buffer+3,x
    sta codegen_lit_len
    jsr _codegen_resolve_letter_idx
    jcs @error
    sta for_var_idx
    jmp @skip
@print:
    lda ir_buffer+3,x
    sta codegen_print_flags
    jsr _codegen_emit_print
    jcs @error
    jmp @skip
@let:
    lda ir_buffer+2,x
    sta codegen_tgt_start
    lda ir_buffer+3,x
    sta codegen_tgt_len
    jsr _codegen_emit_let
    jcs @error
    jmp @skip
@for:
    jsr _codegen_emit_for
    jcs @error
    jmp @skip
@next_stmt:
    jsr _codegen_emit_next
    jcs @error
    jmp @skip
@end_stmt:
    jsr _codegen_emit_end
    jcs @error
    ; Parser accepts END only at end-of-line. This RTS makes the generated
    ; stop observable before program_lines_run considers another source line.
    jmp @finish
@skip:
    lda codegen_ir_offset
    clc
    adc #IR_RECORD_SIZE
    sta codegen_ir_offset
    jmp @next
@malformed:
    sec
    rts
@finish:
    jsr codegen_finish_line
    jcs @error
    ldx #<codegen_buffer
    ldy #>codegen_buffer
    clc
@error:
    rts

.export codegen_get_code_ptr
codegen_get_code_ptr:
    ldx #<codegen_buffer
    ldy #>codegen_buffer
    clc
    rts

_codegen_save_args:
    sta codegen_arg_a
    stx codegen_arg_x
    sty codegen_arg_y
    rts

; Parse a non-negative decimal integer from pipeline source span.
; Result: codegen_pend_a=lo, codegen_pend_x=hi.
_codegen_parse_int_span:
    lda #0
    sta codegen_pend_a
    sta codegen_pend_x
    lda pipeline_source_lo
    clc
    adc codegen_lit_start
    sta zp_src
    lda pipeline_source_hi
    adc #0
    sta zp_src+1
    ldy #0
@loop:
    cpy codegen_lit_len
    bcs @done
    lda (zp_src), y
    cmp #'0'
    bcc @done
    cmp #'9'+1
    bcs @done
    ; val = val * 10 + digit
    and #$0F
    sta codegen_parse_val
    lda #0
    sta codegen_parse_val+1
    ; *10 = *8 + *2
    lda codegen_pend_a
    sta zp_tmp1
    lda codegen_pend_x
    sta zp_tmp1+1
    asl codegen_pend_a
    rol codegen_pend_x
    asl codegen_pend_a
    rol codegen_pend_x
    asl codegen_pend_a
    rol codegen_pend_x
    asl zp_tmp1
    rol zp_tmp1+1
    lda codegen_pend_a
    clc
    adc zp_tmp1
    sta codegen_pend_a
    lda codegen_pend_x
    adc zp_tmp1+1
    sta codegen_pend_x
    lda codegen_pend_a
    clc
    adc codegen_parse_val
    sta codegen_pend_a
    lda codegen_pend_x
    adc #0
    sta codegen_pend_x
    iny
    bne @loop
@done:
    rts

; Emit PRINT for the pending value (string / int / var / bare newline).
_codegen_emit_print:
    lda codegen_pend_kind
    cmp #PEND_STR
    beq @string
    cmp #PEND_INT
    beq @int
    cmp #PEND_VAR
    beq @var
    cmp #PEND_TI_DIV60
    beq @ti_div60
    jmp _codegen_emit_newline_call
@string:
    jmp _codegen_emit_print_string
@int:
    jmp _codegen_emit_print_int
@var:
    jmp _codegen_emit_print_var
@ti_div60:
    jmp _codegen_emit_print_ti_div60

_codegen_emit_print_string:
    ; Layout (critical): executable prologue, then RTS, then the string payload.
    ; The string must NOT sit immediately after the last JSR ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â fall-through would
    ; execute PETSCII as opcodes and hang the editor after a successful print.
    ; Prologue is 11 bytes: LDX# / LDY# / JSR cstr / JSR newline / RTS.
    ; String begins at buffer + current_len + 11. finish_line may append a
    ; second RTS after the string; it is unreachable and harmless.
    lda #<codegen_buffer
    clc
    adc codegen_buffer_len
    sta codegen_str_addr
    lda #>codegen_buffer
    adc #0
    sta codegen_str_addr+1
    clc
    lda codegen_str_addr
    adc #11
    sta codegen_str_addr
    lda codegen_str_addr+1
    adc #0
    sta codegen_str_addr+1
    lda #OP_LDX_IMM
    jsr _codegen_append_a
    bcs @fail
    lda codegen_str_addr
    jsr _codegen_append_a
    bcs @fail
    lda #OP_LDY_IMM
    jsr _codegen_append_a
    bcs @fail
    lda codegen_str_addr+1
    jsr _codegen_append_a
    bcs @fail
    lda #OP_JSR
    jsr _codegen_append_a
    bcs @fail
    lda #<io_print_cstr
    jsr _codegen_append_a
    bcs @fail
    lda #>io_print_cstr
    jsr _codegen_append_a
    bcs @fail
    jsr _codegen_emit_newline_call
    bcs @fail
    ; Return before the payload so the string is never executed.
    lda #OP_RTS
    jsr _codegen_append_a
    bcs @fail
    lda pipeline_source_lo
    clc
    adc codegen_lit_start
    sta zp_src
    lda pipeline_source_hi
    adc #0
    sta zp_src+1
    ldy #0
@copy:
    cpy codegen_lit_len
    beq @nul
    lda (zp_src), y
    jsr _codegen_append_a
    bcs @fail
    iny
    bne @copy
@nul:
    lda #0
    jsr _codegen_append_a
    bcs @fail
    lda #PEND_NONE
    sta codegen_pend_kind
    clc
    rts
@fail:
    sec
    rts

; PRINT <int>: load value into zp_fac1 as INT2 and call io_print_value.
_codegen_emit_print_int:
    ; LDA #lo / STA zp_fac1 / LDA #hi / STA zp_fac1+1 / LDA #TYPE_INT2 / JSR io_print_value
    lda #OP_LDA_IMM
    jsr _codegen_append_a
    bcs @fail
    lda codegen_pend_a
    jsr _codegen_append_a
    bcs @fail
    lda #OP_STA_ZP
    jsr _codegen_append_a
    bcs @fail
    lda #zp_fac1
    jsr _codegen_append_a
    bcs @fail
    lda #OP_LDA_IMM
    jsr _codegen_append_a
    bcs @fail
    lda codegen_pend_x
    jsr _codegen_append_a
    bcs @fail
    lda #OP_STA_ZP
    jsr _codegen_append_a
    bcs @fail
    lda #zp_fac1+1
    jsr _codegen_append_a
    bcs @fail
    lda #OP_LDA_IMM
    jsr _codegen_append_a
    bcs @fail
    lda #TYPE_INT2
    jsr _codegen_append_a
    bcs @fail
    lda #OP_JSR
    jsr _codegen_append_a
    bcs @fail
    lda #<io_print_value
    jsr _codegen_append_a
    bcs @fail
    lda #>io_print_value
    jsr _codegen_append_a
    bcs @fail
    jsr _codegen_emit_newline_call
    bcs @fail
    lda #PEND_NONE
    sta codegen_pend_kind
    lda #0
    sta codegen_expr_sp
    clc
    rts
@fail:
    sec
    rts

; PRINT <var>: dispatch to EDITOR helper (TI/ST + letter cells).
_codegen_emit_print_var:
    jmp _codegen_emit_print_var_hi

_codegen_fold_letter:
    cmp #'a'
    bcc @up
    cmp #'z'+1
    bcs @up
    and #$DF
@up:
    cmp #'A'
    bcc @bad
    cmp #'Z'+1
    bcs @bad
    rts
@bad:
    lda #0
    rts

; --- LET/FOR/NEXT helpers (RAM_HIGH EDITOR; requires hibasic install) ---
.segment "EDITOR"

; Resolve single-letter A-Z span in codegen_lit_start/len -> A=0..25, C=0.
_codegen_resolve_letter_idx:
    lda codegen_lit_len
    cmp #1
    bne @bad
    lda pipeline_source_lo
    clc
    adc codegen_lit_start
    sta zp_src
    lda pipeline_source_hi
    adc #0
    sta zp_src+1
    ldy #0
    lda (zp_src), y
    jsr _codegen_fold_letter
    beq @bad
    sec
    sbc #'A'
    clc
    rts
@bad:
    sec
    rts

; PRINT var: live TI (jiffy now), ST (STATUS), or letter cell.
_codegen_emit_print_var_hi:
    lda codegen_lit_len
    cmp #2
    bne @letter
    ; Two-char specials: TI / ST
    lda pipeline_source_lo
    clc
    adc codegen_lit_start
    sta zp_src
    lda pipeline_source_hi
    adc #0
    sta zp_src+1
    ldy #0
    lda (zp_src), y
    and #$DF
    cmp #'T'
    bne @st
    iny
    lda (zp_src), y
    and #$DF
    cmp #'I'
    bne @letter
    ; Read the clock when generated code executes, not while this line is
    ; compiled. This keeps TI live inside stored-program RUN loops.
    jmp _codegen_emit_print_ti_live
@st:
    cmp #'S'
    bne @letter
    iny
    lda (zp_src), y
    and #$DF
    cmp #'T'
    bne @letter
    lda $90
    sta codegen_pend_a
    lda #0
    sta codegen_pend_x
    lda #PEND_INT
    sta codegen_pend_kind
    jmp _codegen_emit_print_int
@letter:
    jsr _codegen_materialize_pend
    jmp _codegen_emit_print_int

; Same-line FOR I=s TO L:PRINT I:NEXT → emit PRINT for each iteration.
; IR after FOR must be VAR_REF, STMT PRINT, STMT NEXT (offsets +4,+8,+12).
_codegen_for_unroll_print:
    ldx codegen_ir_offset
    cpx #IR_BUFFER_SOFT_MAX
    bcs @no
    lda ir_buffer+4, x
    cmp #IR_VAR_REF
    bne @no
    lda ir_buffer+8, x
    cmp #IR_STMT
    bne @no
    lda ir_buffer+9, x
    cmp #STMT_PRINT
    bne @no
    lda ir_buffer+12, x
    cmp #IR_STMT
    bne @no
    lda ir_buffer+13, x
    cmp #STMT_NEXT
    bne @no
    lda codegen_for_vals+1
    ora codegen_for_vals+3
    bne @no
    lda codegen_for_vals+2
    cmp codegen_for_vals
    bcc @no
    sbc codegen_for_vals
    cmp #9
    bcs @no
    jmp @go
@no:
    rts
@go:
    lda codegen_for_vals
    sta codegen_parse_val
    lda #0
    sta for_active
@loop:
    lda codegen_parse_val
    sta codegen_pend_a
    lda #0
    sta codegen_pend_x
    lda #PEND_INT
    sta codegen_pend_kind
    jsr _codegen_emit_print_int
    bcs @no
    ldx for_var_idx
    txa
    asl
    tax
    lda codegen_parse_val
    sta imm_var_int, x
    lda #0
    sta imm_var_int+1, x
    lda codegen_parse_val
    cmp codegen_for_vals+2
    bcs @done
    inc codegen_parse_val
    jmp @loop
@done:
    lda codegen_ir_offset
    clc
    adc #12
    sta codegen_ir_offset
    rts

; Materialize pending INT/VAR into codegen_pend_a/x as INT2.
_codegen_materialize_pend:
    lda codegen_pend_kind
    cmp #PEND_INT
    beq @ok
    cmp #PEND_VAR
    beq @var
    lda #0
    sta codegen_pend_a
    sta codegen_pend_x
    clc
    rts
@var:
    jsr _codegen_resolve_letter_idx
    bcs @zero
    asl
    tax
    lda imm_var_int, x
    sta codegen_pend_a
    lda imm_var_int+1, x
    sta codegen_pend_x
    lda #PEND_INT
    sta codegen_pend_kind
@ok:
    clc
    rts
@zero:
    lda #0
    sta codegen_pend_a
    sta codegen_pend_x
    clc
    rts

; LET applies at compile time (line recompiled before each RUN exec).
; Prefer postfix stack top when expression operators produced a value.
_codegen_emit_let:
    ; TI$ is a KERNAL-owned special variable, never a user string cell. This
    ; first Noel slice accepts its canonical reset spelling TI$="000000".
    jsr _codegen_target_is_ti_dollar
    bcs @not_ti_dollar
    jsr _codegen_value_is_midnight
    bcs @fail
    jsr _codegen_emit_ti_dollar_reset
    jmp @cleared
@not_ti_dollar:
    lda codegen_expr_sp
    beq @use_pend
    jsr _codegen_expr_peek
    jmp @store
@use_pend:
    jsr _codegen_materialize_pend
@store:
    lda codegen_tgt_start
    sta codegen_lit_start
    lda codegen_tgt_len
    sta codegen_lit_len
    ; TI = n sets the jiffy clock (low 16 bits; high = 0).
    lda codegen_lit_len
    cmp #2
    bne @letter
    lda pipeline_source_lo
    clc
    adc codegen_tgt_start
    sta zp_src
    lda pipeline_source_hi
    adc #0
    sta zp_src+1
    ldy #0
    lda (zp_src), y
    and #$DF
    cmp #'T'
    bne @letter
    iny
    lda (zp_src), y
    and #$DF
    cmp #'I'
    bne @letter
    lda codegen_pend_a
    ldx codegen_pend_x
    ldy #0
    jsr kernal_settim
    jmp @cleared
@letter:
    jsr _codegen_resolve_letter_idx
    bcs @fail
    asl
    tax
    lda codegen_pend_a
    sta imm_var_int, x
    lda codegen_pend_x
    sta imm_var_int+1, x
@cleared:
    lda #PEND_NONE
    sta codegen_pend_kind
    lda #0
    sta codegen_for_n
    sta codegen_expr_sp
    clc
    rts
@fail:
    sec
    rts

; FOR: scan IR for up to 3 numeric literals (start, limit, [step]).
_codegen_emit_for:
    lda #0
    sta codegen_for_n
    ldx #0
@scan:
    cpx ir_buffer_len
    bcs @scanned
    lda ir_buffer, x
    beq @scanned
    cmp #IR_LOOP
    beq @scanned
    cmp #IR_LITERAL_FLOAT
    beq @num
    cmp #IR_LITERAL_INT
    beq @num
    jmp @next
@num:
    lda codegen_for_n
    cmp #CODEGEN_FOR_VAL_MAX
    bcs @next
    stx codegen_ir_arg_a
    lda ir_buffer+1, x
    sta codegen_lit_start
    lda ir_buffer+2, x
    sta codegen_lit_len
    jsr _codegen_parse_int_span
    lda codegen_for_n
    asl
    tax
    lda codegen_pend_a
    sta codegen_for_vals, x
    lda codegen_pend_x
    sta codegen_for_vals+1, x
    inc codegen_for_n
    ldx codegen_ir_arg_a
@next:
    txa
    clc
    adc #IR_RECORD_SIZE
    tax
    jmp @scan
@scanned:
    lda #0
    sta codegen_pend_a
    sta codegen_pend_x
    lda codegen_for_n
    beq @have_start
    lda codegen_for_vals
    sta codegen_pend_a
    lda codegen_for_vals+1
    sta codegen_pend_x
@have_start:
    lda for_var_idx
    asl
    tax
    lda codegen_pend_a
    sta imm_var_int, x
    lda codegen_pend_x
    sta imm_var_int+1, x
    lda #0
    sta for_limit
    sta for_limit+1
    lda codegen_for_n
    cmp #2
    bcc @have_limit
    lda codegen_for_vals+2
    sta for_limit
    lda codegen_for_vals+3
    sta for_limit+1
@have_limit:
    lda #1
    sta for_step
    lda #0
    sta for_step+1
    lda codegen_for_n
    cmp #3
    bcc @have_step
    lda codegen_for_vals+4
    sta for_step
    lda codegen_for_vals+5
    sta for_step+1
@have_step:
    lda #1
    sta for_active
    lda pl_current_index
    clc
    adc #1
    sta for_body_pc
    ; Same-line FOR I=s TO L:PRINT I:NEXT — unroll small positive ranges.
    jsr _codegen_for_unroll_print
    lda #0
    sta codegen_for_n
    sta codegen_pend_kind
    sta codegen_expr_sp
    clc
    rts

; NEXT: multi-line FOR via program_lines_run + for_continue.
_codegen_emit_next:
    lda #OP_JSR
    jsr _codegen_append_a
    bcs @fail
    lda #<ctrl_for_next
    jsr _codegen_append_a
    bcs @fail
    lda #>ctrl_for_next
    jsr _codegen_append_a
    bcs @fail
    lda #0
    sta codegen_for_n
    sta codegen_pend_kind
    sta codegen_expr_sp
    clc
    rts
@fail:
    sec
    rts

; Return C clear when the current LET target is exactly TI$ (case-insensitive).
_codegen_target_is_ti_dollar:
    lda codegen_tgt_len
    cmp #3
    bne @bad
    lda pipeline_source_lo
    clc
    adc codegen_tgt_start
    sta zp_src
    lda pipeline_source_hi
    adc #0
    sta zp_src+1
    ldy #0
    lda (zp_src),y
    and #$DF
    cmp #'T'
    bne @bad
    iny
    lda (zp_src),y
    and #$DF
    cmp #'I'
    bne @bad
    iny
    lda (zp_src),y
    cmp #'$'
    bne @bad
    clc
    rts
@bad:
    sec
    rts

; Return C clear only for the six-character literal "000000". Other TI$
; assignments remain rejected until full string-descriptor lowering lands.
_codegen_value_is_midnight:
    lda codegen_pend_kind
    cmp #PEND_STR
    bne @bad
    lda codegen_lit_len
    cmp #6
    bne @bad
    lda pipeline_source_lo
    clc
    adc codegen_lit_start
    sta zp_src
    lda pipeline_source_hi
    adc #0
    sta zp_src+1
    ldy #0
@digit:
    lda (zp_src),y
    cmp #'0'
    bne @bad
    iny
    cpy #6
    bne @digit
    clc
    rts
@bad:
    sec
    rts

; Append executable TI$="000000" reset bytes. The KERNAL bridge is the sole
; time boundary, so the clock is changed at RUN execution time.
_codegen_emit_ti_dollar_reset:
    lda #OP_LDA_IMM
    jsr _codegen_append_a
    bcs @fail
    lda #0
    jsr _codegen_append_a
    bcs @fail
    lda #OP_LDX_IMM
    jsr _codegen_append_a
    bcs @fail
    lda #0
    jsr _codegen_append_a
    bcs @fail
    lda #OP_LDY_IMM
    jsr _codegen_append_a
    bcs @fail
    lda #0
    jsr _codegen_append_a
    bcs @fail
    lda #OP_JSR
    jsr _codegen_append_a
    bcs @fail
    lda #<kernal_settim
    jsr _codegen_append_a
    bcs @fail
    lda #>kernal_settim
    jmp _codegen_append_a
@fail:
    sec
    rts

; Append PRINT TI using a runtime RDTIM bridge call. The low 16 jiffy bits are
; retained by the existing integer print fast path; the call itself is live.
_codegen_emit_print_ti_live:
    lda #OP_JSR
    jsr _codegen_append_a
    bcs @fail
    lda #<kernal_rdtim
    jsr _codegen_append_a
    bcs @fail
    lda #>kernal_rdtim
    jsr _codegen_append_a
    bcs @fail
    lda #OP_STA_ZP
    jsr _codegen_append_a
    bcs @fail
    lda #zp_fac1
    jsr _codegen_append_a
    bcs @fail
    lda #OP_STX_ZP
    jsr _codegen_append_a
    bcs @fail
    lda #zp_fac1+1
    jsr _codegen_append_a
    bcs @fail
    lda #OP_LDA_IMM
    jsr _codegen_append_a
    bcs @fail
    lda #TYPE_INT2
    jsr _codegen_append_a
    bcs @fail
    lda #OP_JSR
    jsr _codegen_append_a
    bcs @fail
    lda #<io_print_value
    jsr _codegen_append_a
    bcs @fail
    lda #>io_print_value
    jsr _codegen_append_a
    bcs @fail
    jmp _codegen_emit_newline_call
@fail:
    sec
    rts

; END: set the stored-program stop latch at runtime and return immediately.
; The generated code runs from codegen_buffer, so use an absolute store rather
; than relying on a normal-RAM zero-page alias.
_codegen_emit_end:
    lda #OP_LDA_IMM
    jsr _codegen_append_a
    bcs @fail
    lda #1
    jsr _codegen_append_a
    bcs @fail
    lda #OP_STA_ABS
    jsr _codegen_append_a
    bcs @fail
    lda #<codegen_program_stop
    jsr _codegen_append_a
    bcs @fail
    lda #>codegen_program_stop
    jsr _codegen_append_a
    bcs @fail
    lda #OP_RTS
    jmp _codegen_append_a
@fail:
    sec
    rts

; Compact postfix +/– stack (kept in EDITOR; tight RAM_HIGH budget).
_codegen_expr_push:
    lda codegen_expr_sp
    cmp #CODEGEN_EXPR_STACK_MAX
    bcs @full
    asl
    tax
    lda codegen_pend_a
    sta codegen_expr_stack, x
    lda codegen_pend_x
    sta codegen_expr_stack+1, x
    inc codegen_expr_sp
    clc
    rts
@full:
    sec
    rts

_codegen_expr_peek:
    lda codegen_expr_sp
    beq @empty
    sec
    sbc #1
    asl
    tax
    lda codegen_expr_stack, x
    sta codegen_pend_a
    lda codegen_expr_stack+1, x
    sta codegen_pend_x
    lda #PEND_INT
    sta codegen_pend_kind
    clc
    rts
@empty:
    sec
    rts

_codegen_expr_pop:
    jsr _codegen_expr_peek
    bcs @out
    dec codegen_expr_sp
@out:
    rts

_codegen_expr_apply:
    sta codegen_ir_arg_a
    cmp #'/'
    bne @not_divide
    jsr _codegen_is_ti_div60
    bcs @not_divide
    lda #PEND_TI_DIV60
    sta codegen_pend_kind
    lda #0
    sta codegen_expr_sp
    clc
    rts
@not_divide:
    ; _codegen_is_ti_div60 clobbers A; reload the operator char.
    lda codegen_ir_arg_a
    cmp #'+'
    beq @bin
    cmp #'-'
    beq @bin
    cmp #'*'
    beq @bin
    cmp #'/'
    beq @bin
    clc
    rts
@bin:
    jmp _codegen_apply_binop

; Recognize the postfix sequence TI / 60 for the jiffy-clock fast path, which
; lowers to a dedicated runtime helper rather than general integer division.
_codegen_is_ti_div60:
    ldx codegen_ir_offset
    cpx #8
    bcc @bad
    lda ir_buffer-8,x
    cmp #IR_VAR_REF
    bne @bad
    lda ir_buffer-6,x
    cmp #2
    bne @bad
    lda ir_buffer-4,x
    cmp #IR_LITERAL_FLOAT
    beq @literal
    cmp #IR_LITERAL_INT
    bne @bad
@literal:
    lda ir_buffer-2,x
    cmp #2
    bne @bad
    lda pipeline_source_lo
    clc
    adc ir_buffer-7,x
    sta zp_src
    lda pipeline_source_hi
    adc #0
    sta zp_src+1
    ldy #0
    lda (zp_src),y
    and #$DF
    cmp #'T'
    bne @bad
    iny
    lda (zp_src),y
    and #$DF
    cmp #'I'
    bne @bad
    lda pipeline_source_lo
    clc
    adc ir_buffer-3,x
    sta zp_src
    lda pipeline_source_hi
    adc #0
    sta zp_src+1
    ldy #0
    lda (zp_src),y
    cmp #'6'
    bne @bad
    iny
    lda (zp_src),y
    cmp #'0'
    bne @bad
    clc
    rts
@bad:
    sec
    rts

; Append a runtime TI/60 print. The shared helper provides a 24-bit quotient;
; the active integer PRINT ABI consumes its low 16 bits (sufficient for the
; Noel benchmark's measured range).
_codegen_emit_print_ti_div60:
    lda #OP_JSR
    jsr _codegen_append_a
    bcs @fail
    lda #<system_ti_div60
    jsr _codegen_append_a
    bcs @fail
    lda #>system_ti_div60
    jsr _codegen_append_a
    bcs @fail
    lda #OP_STA_ZP
    jsr _codegen_append_a
    bcs @fail
    lda #zp_fac1
    jsr _codegen_append_a
    bcs @fail
    lda #OP_STX_ZP
    jsr _codegen_append_a
    bcs @fail
    lda #zp_fac1+1
    jsr _codegen_append_a
    bcs @fail
    lda #OP_LDA_IMM
    jsr _codegen_append_a
    bcs @fail
    lda #TYPE_INT2
    jsr _codegen_append_a
    bcs @fail
    lda #OP_JSR
    jsr _codegen_append_a
    bcs @fail
    lda #<io_print_value
    jsr _codegen_append_a
    bcs @fail
    lda #>io_print_value
    jsr _codegen_append_a
    bcs @fail
    jmp _codegen_emit_newline_call
@fail:
    sec
    rts

.segment "GEOASM"

; Apply a binary arithmetic operator (in A: '+','-','*','/') to the top two
; postfix-stack entries.  Pops RHS into codegen_for_vals, LHS into codegen_pend,
; computes the 16-bit result into codegen_pend, and pushes it back.  Returns
; carry set on stack underflow or divide-by-zero.  Called from
; _codegen_expr_apply (EDITOR).
_codegen_apply_binop:
    sta codegen_ir_arg_a
    jsr _codegen_expr_pop
    bcs @fail
    lda codegen_pend_a
    sta codegen_for_vals
    lda codegen_pend_x
    sta codegen_for_vals+1
    jsr _codegen_expr_pop
    bcs @fail
    lda codegen_ir_arg_a
    cmp #'-'
    beq @sub
    cmp #'*'
    beq @mul
    cmp #'/'
    beq @div
    clc
    lda codegen_pend_a
    adc codegen_for_vals
    sta codegen_pend_a
    lda codegen_pend_x
    adc codegen_for_vals+1
    jmp @store_hi
@sub:
    sec
    lda codegen_pend_a
    sbc codegen_for_vals
    sta codegen_pend_a
    lda codegen_pend_x
    sbc codegen_for_vals+1
    jmp @store_hi
@mul:
    jsr _codegen_mul16
    jmp @store_result
@div:
    jsr _codegen_div16
    bcs @fail
    jmp @store_result
@store_hi:
    sta codegen_pend_x
@store_result:
    lda #PEND_INT
    sta codegen_pend_kind
    jmp _codegen_expr_push
@fail:
    sec
    rts

; 16-bit unsigned multiply: codegen_pend (left) * codegen_for_vals (right).
; Result (low 16 bits) -> codegen_pend_a/x.  Shift-and-add; the right operand
; is the multiplier, product accumulated in codegen_muldiv_lo/hi.  Called by
; _codegen_expr_apply (EDITOR) via a plain jsr; lives here to keep RAM_HIGH
; free.
_codegen_mul16:
    lda #0
    sta codegen_muldiv_lo
    sta codegen_muldiv_hi
    ldx #16
@loop:
    lsr codegen_for_vals+1
    ror codegen_for_vals
    bcc @noadd
    lda codegen_muldiv_lo
    clc
    adc codegen_pend_a
    sta codegen_muldiv_lo
    lda codegen_muldiv_hi
    adc codegen_pend_x
    sta codegen_muldiv_hi
@noadd:
    asl codegen_pend_a
    rol codegen_pend_x
    dex
    bne @loop
    lda codegen_muldiv_lo
    sta codegen_pend_a
    lda codegen_muldiv_hi
    sta codegen_pend_x
    rts

; 16-bit unsigned divide: codegen_pend (dividend) / codegen_for_vals (divisor).
; Quotient -> codegen_pend_a/x.  Returns carry set on divide-by-zero.
_codegen_div16:
    lda codegen_for_vals
    ora codegen_for_vals+1
    bne @ok
    sec
    rts
@ok:
    lda #0
    sta codegen_muldiv_lo
    sta codegen_muldiv_hi
    ldx #16
@loop:
    asl codegen_pend_a
    rol codegen_pend_x
    rol codegen_muldiv_lo
    rol codegen_muldiv_hi
    lda codegen_muldiv_lo
    sec
    sbc codegen_for_vals
    tay
    lda codegen_muldiv_hi
    sbc codegen_for_vals+1
    bcc @skip
    sty codegen_muldiv_lo
    sta codegen_muldiv_hi
    inc codegen_pend_a
@skip:
    dex
    bne @loop
    clc
    rts

_codegen_emit_newline_call:
    lda codegen_print_flags
    and #PRINT_FLAG_TRAILING_SEMICOLON
    bne @done
    lda #OP_JSR
    jsr _codegen_append_a
    bcs @fail
    lda #<io_print_newline
    jsr _codegen_append_a
    bcs @fail
    lda #>io_print_newline
    jsr _codegen_append_a
@fail:
    rts
@done:
    clc
    rts

_codegen_emit_payload:
    ldx codegen_buffer_len
    cpx #CODEGEN_BUFFER_SIZE-6+1
    bcs @full
    lda #OP_LDA_IMM
    sta codegen_buffer,x
    lda codegen_arg_a
    sta codegen_buffer+1,x
    lda #OP_LDX_IMM
    sta codegen_buffer+2,x
    lda codegen_arg_x
    sta codegen_buffer+3,x
    lda #OP_LDY_IMM
    sta codegen_buffer+4,x
    lda codegen_arg_y
    sta codegen_buffer+5,x
    txa
    clc
    adc #6
    sta codegen_buffer_len
    clc
    rts
@full:
    sec
    rts

_codegen_append_a:
    ldx codegen_buffer_len
    cpx #CODEGEN_BUFFER_SIZE
    bcs @full
    sta codegen_buffer,x
    inc codegen_buffer_len
    clc
    rts
@full:
    sec
    rts
