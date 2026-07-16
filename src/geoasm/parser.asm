; src/geoasm/parser.asm
; Token-driven BASIC syntax parser with deterministic postfix IR emission.
;
; Public entries take X/Y = zero-terminated source text.  They return C clear
; after consuming the complete requested production, or C set after discarding
; the IR stream.  Expressions emit operands followed by IR_EXPR operators.
; Zero-page read/write: zp_tmp1 (through tokenizer)
; Clobbers: A, X, Y

.include "common/zp.inc"
.include "common/constants.asm"

.macro jcs target
    bcc :+
    jmp target
:
.endmacro

.macro jne target
    beq :+
    jmp target
:
.endmacro

.import token_init, token_next
.import token_source_ptr, token_start, token_last_len, token_keyword_id
.import ir_init, ir_finish_line, ir_emit_stmt, ir_emit_expr
.import ir_emit_var_ref, ir_emit_array_ref
.import ir_emit_literal_float, ir_emit_literal_str
.import ir_emit_branch, ir_emit_loop

TOKEN_EOF        = $00
TOKEN_IDENTIFIER = $01
TOKEN_NUMBER     = $02
TOKEN_STRING     = $03
TOKEN_SYMBOL     = $06
TOKEN_ERROR      = $FF

BASIC_TOKEN_FOR   = 129
BASIC_TOKEN_GOSUB = 141
BASIC_TOKEN_PRINT = 153

NODE_LINE       = $01
NODE_STATEMENT  = $02
NODE_EXPRESSION = $03
NODE_PRIMARY    = $04
NODE_FUNCTION   = $05
NODE_ARRAY_REF  = $06

STMT_NONE  = $00
STMT_PRINT = $01
STMT_FOR   = $02
STMT_GOSUB = $03

FLAG_HAS_COMPARISON  = $01
FLAG_TERM_PRECEDENCE = $02

OP_UNARY_PLUS  = $80
OP_UNARY_MINUS = $81
OP_POWER       = $82
OP_LE          = $83
OP_GE          = $84
OP_NE          = $85
OP_CALL        = $86

.segment "BSS"
.export parse_source_ptr
parse_source_ptr: .res 2
.export parse_last_node
parse_last_node: .res 1
.export parse_last_stmt
parse_last_stmt: .res 1
.export parse_flags
parse_flags: .res 1
parse_token: .res 1
parse_saved_start: .res 1
parse_saved_len: .res 1
parse_arg_count: .res 1
parse_operator: .res 1
parse_compare_operator: .res 1
parse_add_operator: .res 1
parse_term_operator: .res 1
parse_unary_operator: .res 1
parse_target: .res 2
parse_target_double: .res 2
parse_compare_char: .res 1
parse_word_char1: .res 1
parse_word_char2: .res 1
parse_char_offset: .res 1

.segment "GEOASM"

; Parse [line-number] statement and terminate its IR.
.export parse_line
parse_line:
    jsr _parse_begin
    jcs _parse_error
    lda parse_token
    cmp #TOKEN_NUMBER
    bne @statement
    jsr _parse_number_is_integer
    jcs _parse_error
    jsr _parse_advance
    jcs _parse_error
@statement:
    jsr _parse_statement_current
    jcs _parse_error
    lda parse_token
    jne _parse_error
    jsr ir_finish_line
    jcs _parse_error
    lda #NODE_LINE
    sta parse_last_node
    clc
    rts

; Parse one complete supported statement.
.export parse_statement
parse_statement:
    jsr _parse_begin
    jcs _parse_error
    jsr _parse_statement_current
    jcs _parse_error
    lda parse_token
    jne _parse_error
    lda #NODE_STATEMENT
    sta parse_last_node
    clc
    rts

; Parse one complete comparison expression.
.export parse_expression
parse_expression:
    jsr _parse_begin
    jcs _parse_error
    jsr _parse_comparison_current
    jcs _parse_error
    lda parse_token
    jne _parse_error
    lda #NODE_EXPRESSION
    sta parse_last_node
    clc
    rts

; Parse exactly one primary.
.export parse_primary
parse_primary:
    jsr _parse_begin
    jcs _parse_error
    jsr _parse_primary_current
    jcs _parse_error
    lda parse_token
    jne _parse_error
    lda #NODE_PRIMARY
    sta parse_last_node
    clc
    rts

; Parse a complete expression containing exactly one comparison.
.export parse_comparison
parse_comparison:
    jsr parse_expression
    bcs @done
    lda parse_flags
    and #FLAG_HAS_COMPARISON
    bne @done
    jmp _parse_error
@done:
    rts

; Parse exactly one multiplicative term.
.export parse_term
parse_term:
    jsr _parse_begin
    jcs _parse_error
    jsr _parse_term_current
    jcs _parse_error
    lda parse_token
    jne _parse_error
    lda #NODE_EXPRESSION
    sta parse_last_node
    clc
    rts

; Parse exactly one unary/power factor.
.export parse_factor
parse_factor:
    jsr _parse_begin
    jcs _parse_error
    jsr _parse_factor_current
    jcs _parse_error
    lda parse_token
    jne _parse_error
    lda #NODE_PRIMARY
    sta parse_last_node
    clc
    rts

; Parse a named function call and emit its postfix call record.
.export parse_function_call
parse_function_call:
    jsr _parse_begin
    jcs _parse_error
    jsr _parse_named_call_current
    jcs _parse_error
    lda parse_token
    jne _parse_error
    lda #NODE_FUNCTION
    sta parse_last_node
    clc
    rts

; Parse a named array reference and emit its postfix array record.
.export parse_array_ref
parse_array_ref:
    jsr _parse_begin
    jcs _parse_error
    jsr _parse_array_current
    jcs _parse_error
    lda parse_token
    jne _parse_error
    lda #NODE_ARRAY_REF
    sta parse_last_node
    clc
    rts

; Parse FOR variable=start TO limit [STEP increment].
.export parse_for
parse_for:
    jsr _parse_begin
    jcs _parse_error
    lda token_keyword_id
    cmp #BASIC_TOKEN_FOR
    jne _parse_error
    jsr _parse_for_after_keyword
    jcs _parse_error
    lda #STMT_FOR
    sta parse_last_stmt
    lda parse_token
    jne _parse_error
    lda #NODE_STATEMENT
    sta parse_last_node
    clc
    rts

; Parse GOSUB followed by an integer target in the BASIC line-number range.
.export parse_gosub
parse_gosub:
    jsr _parse_begin
    jcs _parse_error
    lda token_keyword_id
    cmp #BASIC_TOKEN_GOSUB
    jne _parse_error
    jsr _parse_gosub_after_keyword
    jcs _parse_error
    lda parse_token
    jne _parse_error
    lda #NODE_STATEMENT
    sta parse_last_node
    clc
    rts

_parse_error:
    lda #STMT_NONE
    sta parse_last_stmt
    jsr ir_init
    lda #ERR_SYNTAX
    sec
    rts

_parse_begin:
    stx parse_source_ptr
    sty parse_source_ptr+1
    lda #0
    sta parse_flags
    sta parse_last_stmt
    jsr ir_init
    ldx parse_source_ptr
    ldy parse_source_ptr+1
    jsr token_init
    jmp _parse_advance

_parse_advance:
    jsr token_next
    sta parse_token
    rts

_parse_statement_current:
    lda parse_token
    cmp #TOKEN_IDENTIFIER
    bne @bad
    lda token_keyword_id
    cmp #BASIC_TOKEN_PRINT
    beq @print
    cmp #BASIC_TOKEN_FOR
    beq @for
    cmp #BASIC_TOKEN_GOSUB
    beq @gosub
@bad:
    sec
    rts
@print:
    jsr _parse_advance
    jcs @bad
    lda parse_token
    beq @bad
    jsr _parse_comparison_current
    bcs @bad
    lda #STMT_PRINT
    sta parse_last_stmt
    lda #STMT_PRINT
    ldx #0
    ldy #0
    jmp ir_emit_stmt
@for:
    jsr _parse_for_after_keyword
    bcs @for_done
    lda #STMT_FOR
    sta parse_last_stmt
@for_done:
    rts
@gosub:
    jsr _parse_gosub_after_keyword
    rts

_parse_for_after_keyword:
    jsr _parse_advance
    bcs @bad
    lda parse_token
    cmp #TOKEN_IDENTIFIER
    bne @bad
    jsr _parse_identifier_valid
    bcs @bad
    jsr _parse_save_span
    jsr _parse_advance
    bcs @bad
    lda #'='
    jsr _parse_require_symbol
    bcs @bad
    jsr _parse_advance
    bcs @bad
    jsr _parse_comparison_current
    bcs @bad
    lda #'T'
    ldx #'O'
    jsr _parse_word2
    bcs @bad
    jsr _parse_advance
    bcs @bad
    jsr _parse_comparison_current
    bcs @bad
    lda #'S'
    ldx #'T'
    ldy #'E'
    jsr _parse_word_step
    bcs @no_step
    jsr _parse_advance
    bcs @bad
    jsr _parse_comparison_current
    bcs @bad
@no_step:
    lda #STMT_FOR
    ldx parse_saved_start
    ldy parse_saved_len
    jsr ir_emit_loop
    bcs @bad
    lda #STMT_FOR
    ldx #0
    ldy #0
    jmp ir_emit_stmt
@bad:
    sec
    rts

_parse_gosub_after_keyword:
    jsr _parse_advance
    bcs @bad
    lda parse_token
    cmp #TOKEN_NUMBER
    bne @bad
    jsr _parse_line_number_valid
    bcs @bad
    lda token_start
    jsr _parse_line_number_value
    bcs @bad
    jsr _parse_advance
    bcs @bad
    ldx parse_target
    ldy parse_target+1
    lda #STMT_GOSUB
    jsr ir_emit_branch
    bcs @bad
    lda #STMT_GOSUB
    sta parse_last_stmt
    lda #STMT_GOSUB
    ldx #0
    ldy #0
    jmp ir_emit_stmt
@bad:
    sec
    rts

; comparison := additive [comparison-op additive]
_parse_comparison_current:
    jsr _parse_additive_current
    jcs @bad
    lda #'='
    jsr _parse_symbol_is
    bcc @eq
    lda #'<'
    jsr _parse_symbol_is
    bcc @lt
    lda #'>'
    jsr _parse_symbol_is
    bcc @gt
    clc
    rts
@eq:
    lda #'='
    sta parse_compare_operator
    jmp @consume
@lt:
    lda #'<'
    sta parse_compare_operator
    jsr _parse_advance
    bcs @bad
    lda #'='
    jsr _parse_symbol_is
    bcc @set_le
    lda #'>'
    jsr _parse_symbol_is
    bcc @set_ne
    jmp @rhs
@set_le:
    lda #OP_LE
    sta parse_compare_operator
    jmp @consume_second
@set_ne:
    lda #OP_NE
    sta parse_compare_operator
    jmp @consume_second
@gt:
    lda #'>'
    sta parse_compare_operator
    jsr _parse_advance
    bcs @bad
    lda #'='
    jsr _parse_symbol_is
    bcs @rhs
    lda #OP_GE
    sta parse_compare_operator
@consume_second:
    jsr _parse_advance
    bcs @bad
    jmp @rhs
@consume:
    jsr _parse_advance
    bcs @bad
@rhs:
    jsr _parse_additive_current
    bcs @bad
    lda parse_flags
    ora #FLAG_HAS_COMPARISON
    sta parse_flags
    lda parse_compare_operator
    ldx #4
    ldy #0
    jsr ir_emit_expr
    rts
@bad:
    sec
    rts

; additive := term {(+|-) term}
_parse_additive_current:
    jsr _parse_term_current
    bcs @bad
@loop:
    lda #'+'
    jsr _parse_symbol_is
    bcc @operator
    lda #'-'
    jsr _parse_symbol_is
    bcs @done
@operator:
    jsr _parse_current_char
    sta parse_add_operator
    jsr _parse_advance
    bcs @bad
    jsr _parse_term_current
    bcs @bad
    lda parse_add_operator
    ldx #2
    ldy #0
    jsr ir_emit_expr
    bcs @bad
    jmp @loop
@done:
    clc
@bad:
    rts

; term := factor {(*|/) factor}
_parse_term_current:
    jsr _parse_factor_current
    bcs @bad
@loop:
    lda #'*'
    jsr _parse_symbol_is
    bcc @operator
    lda #'/'
    jsr _parse_symbol_is
    bcs @done
@operator:
    jsr _parse_current_char
    sta parse_term_operator
    jsr _parse_advance
    bcs @bad
    jsr _parse_factor_current
    bcs @bad
    lda parse_flags
    ora #FLAG_TERM_PRECEDENCE
    sta parse_flags
    lda parse_term_operator
    ldx #3
    ldy #0
    jsr ir_emit_expr
    bcs @bad
    jmp @loop
@done:
    clc
@bad:
    rts

; factor := [('+'|'-')] primary ['^' factor]
_parse_factor_current:
    lda #0
    sta parse_unary_operator
    lda #'+'
    jsr _parse_symbol_is
    bcc @unary_plus
    lda #'-'
    jsr _parse_symbol_is
    bcc @unary_minus
    jmp @primary
@unary_plus:
    lda #OP_UNARY_PLUS
    bne @save_unary
@unary_minus:
    lda #OP_UNARY_MINUS
@save_unary:
    sta parse_unary_operator
    jsr _parse_advance
    bcs @bad
@primary:
    jsr _parse_primary_current
    bcs @bad
    lda parse_unary_operator
    beq @power
    ldx #5
    ldy #0
    jsr ir_emit_expr
    bcs @bad
@power:
    lda #'^'
    jsr _parse_symbol_is
    bcs @done
    jsr _parse_advance
    bcs @bad
    jsr _parse_factor_current
    bcs @bad
    lda #OP_POWER
    ldx #5
    ldy #0
    jsr ir_emit_expr
@done:
    clc
    rts
@bad:
    sec
    rts

_parse_primary_current:
    lda parse_token
    cmp #TOKEN_NUMBER
    beq @number
    cmp #TOKEN_STRING
    beq @string
    cmp #TOKEN_IDENTIFIER
    beq @identifier
    lda #'('
    jsr _parse_symbol_is
    bcc @group
    sec
    rts
@number:
    jsr _parse_number_valid
    bcs @bad
    jsr _parse_save_span
    jsr _parse_advance
    bcs @bad
    lda parse_saved_start
    ldx parse_saved_len
    ldy #0
    jsr ir_emit_literal_float
    rts
@string:
    jsr _parse_save_span
    jsr _parse_advance
    bcs @bad
    lda parse_saved_start
    ldx parse_saved_len
    ldy #0
    jsr ir_emit_literal_str
    rts
@identifier:
    lda token_keyword_id
    bne @bad
    jsr _parse_identifier_valid
    bcs @bad
    jsr _parse_save_span
    jsr _parse_advance
    bcs @bad
    lda #'('
    jsr _parse_symbol_is
    bcc _parse_array_saved
    lda parse_saved_start
    ldx parse_saved_len
    ldy #0
    jsr ir_emit_var_ref
    rts
@group:
    jsr _parse_advance
    bcs @bad
    jsr _parse_comparison_current
    bcs @bad
    lda #')'
    jsr _parse_require_symbol
    bcs @bad
    jmp _parse_advance
@bad:
    sec
    rts

_parse_named_call_current:
    lda parse_token
    cmp #TOKEN_IDENTIFIER
    bne @bad
    jsr _parse_identifier_valid
    bcs @bad
    jsr _parse_save_span
    jsr _parse_advance
    bcs @bad
    lda #'('
    jsr _parse_require_symbol
    bcs @bad
    jsr _parse_argument_list
    bcs @bad
    lda #OP_CALL
    ldx parse_saved_start
    ldy parse_arg_count
    jmp ir_emit_expr
@bad:
    sec
    rts

_parse_array_current:
    lda parse_token
    cmp #TOKEN_IDENTIFIER
    bne _parse_array_bad
    lda token_keyword_id
    bne _parse_array_bad
    jsr _parse_identifier_valid
    bcs _parse_array_bad
    jsr _parse_save_span
    jsr _parse_advance
    bcs _parse_array_bad
    lda #'('
    jsr _parse_require_symbol
    bcs _parse_array_bad
_parse_array_saved:
    jsr _parse_argument_list
    bcs _parse_array_bad
    lda parse_saved_start
    ldx parse_saved_len
    ldy parse_arg_count
    jmp ir_emit_array_ref
_parse_array_bad:
    sec
    rts

_parse_argument_list:
    lda #0
    sta parse_arg_count
    jsr _parse_advance
    bcs @bad
@argument:
    lda #')'
    jsr _parse_symbol_is
    bcc @bad
    jsr _parse_comparison_current
    bcs @bad
    inc parse_arg_count
    lda #','
    jsr _parse_symbol_is
    bcs @close
    jsr _parse_advance
    bcs @bad
    jmp @argument
@close:
    lda #')'
    jsr _parse_require_symbol
    bcs @bad
    jmp _parse_advance
@bad:
    sec
    rts

_parse_save_span:
    lda token_start
    sta parse_saved_start
    lda token_last_len
    sta parse_saved_len
    rts

_parse_symbol_is:
    pha
    lda parse_token
    cmp #TOKEN_SYMBOL
    bne @no_pop
    jsr _parse_current_char
    tax
    pla
    stx parse_compare_char
    cmp parse_compare_char
    bne @no
    clc
    rts
@no_pop:
    pla
@no:
    sec
    rts

_parse_require_symbol:
    jmp _parse_symbol_is

_parse_current_char:
    lda token_source_ptr
    sta zp_tmp1
    lda token_source_ptr+1
    sta zp_tmp1+1
    ldy token_start
    lda (zp_tmp1),y
    and #$7f
    rts

; A/X = exact two-character word.
_parse_word2:
    sta parse_operator
    stx parse_word_char1
    lda parse_token
    cmp #TOKEN_IDENTIFIER
    bne @bad
    lda token_last_len
    cmp #2
    bne @bad
    jsr _parse_span_char0
    cmp parse_operator
    bne @bad
    jsr _parse_span_char1
    cmp parse_word_char1
    bne @bad
    clc
    rts
@bad:
    sec
    rts

; A/X/Y = S/T/E marker; also require fourth character P.
_parse_word_step:
    sta parse_operator
    stx parse_word_char1
    sty parse_word_char2
    lda parse_token
    cmp #TOKEN_IDENTIFIER
    bne @bad
    lda token_last_len
    cmp #4
    bne @bad
    jsr _parse_span_char0
    cmp parse_operator
    bne @bad
    jsr _parse_span_char1
    cmp parse_word_char1
    bne @bad
    ldy #2
    jsr _parse_span_char
    cmp parse_word_char2
    bne @bad
    ldy #3
    jsr _parse_span_char
    cmp #'P'
    bne @bad
    clc
    rts
@bad:
    sec
    rts

_parse_span_char0:
    ldy #0
    beq _parse_span_char
_parse_span_char1:
    ldy #1
_parse_span_char:
    sty parse_char_offset
    lda token_source_ptr
    sta zp_tmp1
    lda token_source_ptr+1
    sta zp_tmp1+1
    tya
    clc
    adc token_start
    tay
    lda (zp_tmp1),y
    and #$7f
    cmp #'a'
    bcc @done
    cmp #'z'+1
    bcs @done
    and #$df
@done:
    ldy parse_char_offset
    rts

_parse_number_is_integer:
    ldy #0
@loop:
    cpy token_last_len
    beq @ok
    jsr _parse_span_char
    cmp #'0'
    bcc @bad
    cmp #'9'+1
    bcs @bad
    iny
    bne @loop
@ok:
    clc
    rts
@bad:
    sec
    rts

; Validate a BASIC identifier: alphabetic first byte and an optional terminal
; type suffix.  This rejects numeric prefixes and mixed suffix spellings that
; the tokenizer deliberately leaves for the parser to diagnose.
_parse_identifier_valid:
    lda token_last_len
    beq @bad
    ldy #0
    jsr _parse_span_char
    cmp #'A'
    bcc @bad
    cmp #'Z'+1
    bcs @bad
    iny
@rest:
    cpy token_last_len
    beq @ok
    jsr _parse_span_char
    cmp #'A'
    bcc @digit
    cmp #'Z'+1
    bcc @next
@digit:
    cmp #'0'
    bcc @special
    cmp #'9'+1
    bcc @next
@special:
    cmp #'.'
    beq @next
    cmp #'$'
    beq @suffix
    cmp #'%'
    beq @suffix
    cmp #'#'
    bne @bad
@suffix:
    iny
    cpy token_last_len
    beq @ok
    bne @bad
@next:
    iny
    bne @rest
@ok:
    clc
    rts
@bad:
    sec
    rts

; Convert the current validated decimal token to a 16-bit branch target.
_parse_line_number_value:
    lda #0
    sta parse_target
    sta parse_target+1
    ldy #0
@digit:
    cpy token_last_len
    beq @done
    jsr _parse_span_char
    sec
    sbc #'0'
    pha
    lda parse_target
    asl
    sta parse_target_double
    lda parse_target+1
    rol
    sta parse_target_double+1
    asl parse_target
    rol parse_target+1
    asl parse_target
    rol parse_target+1
    asl parse_target
    rol parse_target+1
    lda parse_target
    clc
    adc parse_target_double
    sta parse_target
    lda parse_target+1
    adc parse_target_double+1
    sta parse_target+1
    pla
    clc
    adc parse_target
    sta parse_target
    bcc :+
    inc parse_target+1
:
    iny
    bne @digit
@done:
    clc
    rts

; Reject incomplete exponents and a bare decimal point.
_parse_number_valid:
    lda token_last_len
    beq @bad
    ldy #0
    lda #0
    sta parse_operator
@loop:
    cpy token_last_len
    beq @ok
    jsr _parse_span_char
    cmp #'E'
    bne @next
    tya
    clc
    adc #1
    cmp token_last_len
    bcs @bad
    iny
    jsr _parse_span_char
    cmp #'+'
    beq @after_sign
    cmp #'-'
    bne @require_digit
@after_sign:
    tya
    clc
    adc #1
    cmp token_last_len
    bcs @bad
    iny
@require_digit:
    jsr _parse_span_char
    cmp #'0'
    bcc @bad
    cmp #'9'+1
    bcs @bad
@next:
    iny
    bne @loop
@ok:
    clc
    rts
@bad:
    sec
    rts

; Decimal integer, at most 63999.
_parse_line_number_valid:
    jsr _parse_number_is_integer
    bcs @bad
    lda token_last_len
    cmp #6
    bcs @bad
    cmp #5
    bne @ok
    ldy #0
@compare:
    jsr _parse_span_char
    cmp _parse_max_line,y
    bcc @ok
    bne @bad
    iny
    cpy #5
    bne @compare
@ok:
    clc
    rts
@bad:
    sec
    rts

_parse_max_line:
    .byte "63999"
