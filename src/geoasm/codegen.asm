; src/geoasm/codegen.asm
; Typed-IR to executable 6502 lowering.

.include "common/zp.inc"

CODEGEN_BUFFER_SIZE = 192
CODEGEN_RELOC_CAPACITY = 16

IR_END           = $00
IR_STMT          = $01
IR_VAR_REF       = $03
IR_LITERAL_INT   = $08
IR_LITERAL_FLOAT = $09
IR_LITERAL_STR   = $0A
IR_RECORD_SIZE   = 4

STMT_PRINT = $01

; Pending value kinds for PRINT lowering.
PEND_NONE   = 0
PEND_STR    = 1
PEND_INT    = 2
PEND_VAR    = 3

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

.import ir_buffer, ir_buffer_len
.import io_print_cstr, io_print_newline, io_print_value
.import pipeline_source_lo, pipeline_source_hi
.import math_int_to_float

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
; Immediate-mode single-letter integer cells A-Z (stock-like default 0).
.export imm_var_int
imm_var_int:
    .res 26 * 2
.export codegen_reloc_count, codegen_reloc_table
codegen_reloc_count:
    .res 1
codegen_reloc_table:
    .res CODEGEN_RELOC_CAPACITY * 3

.segment "GEOASM"

; codegen_init - Reset native emitter state.
.export codegen_init
codegen_init:
    lda #0
    sta codegen_buffer_len
    sta codegen_reloc_count
    sta codegen_pend_kind
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
    cmp #IR_STMT
    beq @stmt
    jmp @skip
@stmt:
    lda ir_buffer+1,x
    cmp #STMT_PRINT
    bne @other_stmt
    jmp @print
@other_stmt:
    sta codegen_ir_arg_a
    ldy ir_buffer+3,x
    lda ir_buffer+2,x
    tax
    lda codegen_ir_arg_a
    jsr codegen_emit_stmt
    bcs @error
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
    jmp @skip
@var_ref:
    lda ir_buffer+1,x
    sta codegen_lit_start
    lda ir_buffer+2,x
    sta codegen_lit_len
    lda #PEND_VAR
    sta codegen_pend_kind
    jmp @skip
@print:
    jsr _codegen_emit_print
    bcs @error
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
    bcs @error
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
    jmp _codegen_emit_newline_call
@string:
    jmp _codegen_emit_print_string
@int:
    jmp _codegen_emit_print_int
@var:
    jmp _codegen_emit_print_var

_codegen_emit_print_string:
    ; Layout (critical): executable prologue, then RTS, then the string payload.
    ; The string must NOT sit immediately after the last JSR — fall-through would
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
    clc
    rts
@fail:
    sec
    rts

; PRINT <var>: single-letter A-Z reads imm_var_int[letter] at compile time
; (cells are zero-filled; later assignment lowering updates them before print).
_codegen_emit_print_var:
    lda pipeline_source_lo
    clc
    adc codegen_lit_start
    sta zp_src
    lda pipeline_source_hi
    adc #0
    sta zp_src+1
    lda codegen_lit_len
    cmp #1
    bne @zero
    ldy #0
    lda (zp_src), y
    jsr _codegen_fold_letter
    beq @zero
    sec
    sbc #'A'
    asl
    tax
    lda imm_var_int, x
    sta codegen_pend_a
    lda imm_var_int+1, x
    sta codegen_pend_x
    jmp _codegen_emit_print_int
@zero:
    lda #0
    sta codegen_pend_a
    sta codegen_pend_x
    jmp _codegen_emit_print_int

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

_codegen_emit_newline_call:
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
