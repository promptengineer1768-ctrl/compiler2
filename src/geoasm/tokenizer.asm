; src/geoasm/tokenizer.asm
; Source line tokenizer for the geoasm frontend.
;
; Public entries: token_init, token_next, token_peek, token_identifier,
; token_number, token_string, token_skip_whitespace, token_rem, token_data
; Zero-page read/write: zp_tmp1, zp_tmp2
; Clobbers: A, X, Y

.include "common/zp.inc"
.include "common/constants.asm"
.include "keyword_lookup.inc"

TOKEN_EOF        = $00
TOKEN_IDENTIFIER = $01
TOKEN_NUMBER     = $02
TOKEN_STRING     = $03
TOKEN_REM        = $04
TOKEN_DATA       = $05
TOKEN_SYMBOL     = $06
TOKEN_ERROR      = $FF

KW_NONE    = $00
KW_DATA    = BASIC_TOKEN_DATA
KW_REM     = BASIC_TOKEN_REM

.segment "BSS"
.export token_source_ptr
token_source_ptr:
    .res 2
.export token_cursor
token_cursor:
    .res 1
.export token_start
token_start:
    .res 1
.export token_last_type
token_last_type:
    .res 1
.export token_last_len
token_last_len:
    .res 1
.export token_keyword_id
token_keyword_id:
    .res 1
.export token_dialect
token_dialect:
    .res 1
.export token_keyword_dialect
token_keyword_dialect:
    .res 1
keyword_candidate:
    .res 1
keyword_candidate_end:
    .res 1
token_match_offset:
    .res 1

.segment "GEOASM"

.export token_init
token_init:
    stx token_source_ptr
    sty token_source_ptr+1
    lda #0
    sta token_cursor
    sta token_start
    sta token_last_type
    sta token_last_len
    sta token_keyword_id
    sta token_dialect
    sta token_keyword_dialect
    clc
    rts

.export token_next
token_next:
    jsr token_skip_whitespace
    lda token_cursor
    sta token_start
    jsr _token_load_current
    bne @not_eof
    jmp _token_emit_eof
@not_eof:
    cmp #'"'
    bne @not_string
    jmp token_string
@not_string:
    jsr _token_is_digit
    bcc @not_number
    jmp token_number
@not_number:
    jsr _token_is_alpha
    bcs @identifier
    cmp #'.'
    bne @symbol
    inc token_cursor
    jsr _token_load_current
    dec token_cursor
    jsr _token_is_digit
    bcc @symbol
    jmp token_number
@identifier:
    jmp token_identifier
@symbol:
    inc token_cursor
    lda #1
    sta token_last_len
    lda #KW_NONE
    sta token_keyword_id
    sta token_keyword_dialect
    lda #TOKEN_SYMBOL
    sta token_last_type
    clc
    rts

.export token_peek
token_peek:
    lda token_cursor
    pha
    jsr token_next
    tax
    pla
    sta token_cursor
    txa
    rts

.export token_identifier
token_identifier:
    lda #KW_NONE
    sta token_keyword_id
    sta token_keyword_dialect
@loop:
    jsr _token_load_current
    beq @done
    jsr _token_is_ident_char
    bcc @done
    inc token_cursor
    jmp @loop
@done:
    jsr _token_store_len
    ; TAB( and SPC( are the two stock spellings whose opening parenthesis is
    ; part of the keyword token.  Keep it attached only for those prefixes;
    ; ordinary calls such as SIN( must expose '(' as a separate symbol.
    jsr _token_load_current
    cmp #'('
    bne @classify
    lda token_last_len
    cmp #3
    bne @classify
    jsr _token_load_start
    cmp #'T'
    beq @attach_paren
    cmp #'S'
    bne @classify
    ldy #1
    jsr _token_load_start_offset
    cmp #'P'
    bne @classify
@attach_paren:
    inc token_cursor
    inc token_last_len
@classify:
    jsr _token_classify_keyword
    bcs @error
    lda token_keyword_id
    cmp #KW_REM
    bne @not_rem_token
    jmp token_rem
@not_rem_token:
    cmp #KW_DATA
    bne @not_data_token
    jmp token_data
@not_data_token:
@emit_identifier:
    lda #TOKEN_IDENTIFIER
    sta token_last_type
    clc
    rts
@error:
    rts

.export token_number
token_number:
@integer:
    jsr _token_load_current
    jsr _token_is_digit
    bcc @fraction
    inc token_cursor
    jmp @integer
@fraction:
    jsr _token_load_current
    cmp #'.'
    bne @exponent
    inc token_cursor
@fraction_digits:
    jsr _token_load_current
    jsr _token_is_digit
    bcc @exponent
    inc token_cursor
    jmp @fraction_digits
@exponent:
    jsr _token_load_current
    jsr _token_char_upper
    cmp #'E'
    bne @done
    inc token_cursor
    jsr _token_load_current
    cmp #'+'
    beq @consume_exponent_sign
    cmp #'-'
    bne @exponent_digits
@consume_exponent_sign:
    inc token_cursor
@exponent_digits:
    jsr _token_load_current
    jsr _token_is_digit
    bcc @done
    inc token_cursor
    jmp @exponent_digits
@done:
    jsr _token_store_len
    lda #KW_NONE
    sta token_keyword_id
    sta token_keyword_dialect
    lda #TOKEN_NUMBER
    sta token_last_type
    clc
    rts

.export token_string
token_string:
    inc token_cursor
    lda token_cursor
    sta token_start
@loop:
    jsr _token_load_current
    beq @done
    cmp #'"'
    beq @quoted_done
    inc token_cursor
    jmp @loop
@quoted_done:
    jsr _token_store_len
    inc token_cursor
    jmp @emit
@done:
    jsr _token_store_len
    lda #KW_NONE
    sta token_keyword_id
    sta token_keyword_dialect
    lda #TOKEN_ERROR
    sta token_last_type
    sec
    rts
@emit:
    lda #KW_NONE
    sta token_keyword_id
    lda #TOKEN_STRING
    sta token_last_type
    clc
    rts

.export token_skip_whitespace
token_skip_whitespace:
@loop:
    jsr _token_load_current
    cmp #' '
    beq @skip
    cmp #$09
    beq @skip
    clc
    rts
@skip:
    inc token_cursor
    jmp @loop

.export token_rem
token_rem:
@loop:
    jsr _token_load_current
    beq @done
    inc token_cursor
    jmp @loop
@done:
    jsr _token_store_len
    lda #KW_REM
    sta token_keyword_id
    lda #DIALECT_BASIC2
    sta token_keyword_dialect
    lda #TOKEN_REM
    sta token_last_type
    clc
    rts

.export token_data
token_data:
@loop:
    jsr _token_load_current
    beq @done
    cmp #':'
    beq @done
    inc token_cursor
    jmp @loop
@done:
    jsr _token_store_len
    lda #KW_DATA
    sta token_keyword_id
    lda #DIALECT_BASIC2
    sta token_keyword_dialect
    lda #TOKEN_DATA
    sta token_last_type
    clc
    rts

_token_emit_eof:
    lda #0
    sta token_last_len
    sta token_keyword_id
    sta token_keyword_dialect
    lda #TOKEN_EOF
    sta token_last_type
    clc
    rts

_token_load_current:
    lda token_source_ptr
    sta zp_tmp1
    lda token_source_ptr+1
    sta zp_tmp1+1
    ldy token_cursor
    lda (zp_tmp1), y
    rts

_token_load_start:
    lda token_source_ptr
    sta zp_tmp1
    lda token_source_ptr+1
    sta zp_tmp1+1
    ldy token_start
    lda (zp_tmp1), y
    rts

_token_load_start_offset:
    lda token_source_ptr
    sta zp_tmp1
    lda token_source_ptr+1
    sta zp_tmp1+1
    tya
    clc
    adc token_start
    tay
    lda (zp_tmp1), y
    rts

_token_store_len:
    lda token_cursor
    sec
    sbc token_start
    sta token_last_len
    rts

_token_is_digit:
    cmp #'0'
    bcc @no
    cmp #'9'+1
    bcs @no
    sec
    rts
@no:
    clc
    rts

_token_is_alpha:
    cmp #'A'
    bcc @lower
    cmp #'Z'+1
    bcc @yes
@lower:
    cmp #'a'
    bcc @no
    cmp #'z'+1
    bcs @no
@yes:
    sec
    rts
@no:
    clc
    rts

_token_is_ident_char:
    and #$7F
    pha
    jsr _token_is_alpha
    bcs @yes
    pla
    and #$7F
    pha
    jsr _token_is_digit
    bcs @yes
    pla
    and #$7F
    cmp #'$'
    beq @yes_direct
    cmp #'%'
    beq @yes_direct
    cmp #'#'
    beq @yes_direct
    cmp #'.'
    beq @yes_direct
    ; Parentheses terminate ordinary identifiers; TAB( and SPC( are parsed as
    ; a keyword followed by a symbol, preserving the same grammar boundary.
    clc
    rts
@yes:
    pla
@yes_direct:
    sec
    rts

_token_char_upper:
    and #$7F
    cmp #'a'
    bcc @done
    cmp #'z'+1
    bcs @done
    sec
    sbc #$20
@done:
    rts

_token_classify_keyword:
    lda #KW_NONE
    sta token_keyword_id
    sta token_keyword_dialect
    jsr _token_load_start
    jsr _token_char_upper
    cmp #'A'
    bcc @done
    cmp #'Z'+1
    bcs @done
    sec
    sbc #'A'
    tax
    lda keyword_first_start,x
    sta keyword_candidate
    lda keyword_first_end,x
    sta keyword_candidate_end
@candidate_loop:
    lda keyword_candidate
    cmp keyword_candidate_end
    bcs @done
    tax
    jsr _token_match_candidate
    bcc @next_candidate
    ldx keyword_candidate
    lda keyword_token,x
    sta token_keyword_id
    lda keyword_dialect,x
    sta token_keyword_dialect
    ; keyword_dialect is a bit mask: bit0=BASIC2, bit1=BASIC35, both=gateway.
    ; Active mask is always BASIC2; BASIC35 mode also sets bit1.
    lda #DIALECT_BASIC2
    ldx token_dialect
    beq @have_mask
    ora #DIALECT_BASIC35
@have_mask:
    and token_keyword_dialect
    bne @matched
    lda #TOKEN_ERROR
    sta token_last_type
    sec
    rts
@matched:
    clc
    rts
@next_candidate:
    inc keyword_candidate
    jmp @candidate_loop
@done:
    clc
    rts

_token_match_candidate:
    lda keyword_name_lo,x
    sta zp_tmptr
    lda keyword_name_hi,x
    sta zp_tmptr+1
    lda token_last_len
    cmp keyword_length,x
    beq @full_match
    cmp keyword_abbrev_min,x
    bcc @no
    cmp keyword_length,x
    bcs @no
    jmp @abbrev_match
@full_match:
    ldy #0
@full_loop:
    cpy token_last_len
    beq @yes
    sty token_match_offset
    jsr _token_load_start_offset
    jsr _token_char_upper
    ldy token_match_offset
    cmp (zp_tmptr),y
    bne @no
    iny
    jmp @full_loop
@abbrev_match:
    ldy #0
@abbrev_loop:
    tya
    cmp token_last_len
    beq @no
    sty token_match_offset
    jsr _token_load_start_offset
    pha
    lda token_match_offset
    clc
    adc #1
    cmp token_last_len
    beq @abbrev_final
    pla
    jsr _token_char_upper
    ldy token_match_offset
    cmp (zp_tmptr),y
    bne @no
    ldy token_match_offset
    iny
    jmp @abbrev_loop
@abbrev_final:
    pla
    bmi @abbrev_high
    clc
    rts
@abbrev_high:
    and #$7F
    jsr _token_char_upper
    ldy token_match_offset
    cmp (zp_tmptr),y
    bne @no
@yes:
    sec
    rts
@no:
    clc
    rts
