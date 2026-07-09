; src/geoasm/semantic.asm
; Token-stream semantic policy for Compiler 2.

.include "common/constants.asm"
.include "common/zp.inc"

DIALECT_BASICV2  = $00
DIALECT_BASICV35 = $01
NUMERIC_FLOAT    = $00
NUMERIC_INT_FAST = $01

DIALECT_MASK_BASIC2  = $01
DIALECT_MASK_BASIC35 = $02
KEYWORD_MODE_PROGRAM = $01
KEYWORD_MODE_DIRECT  = $02

TOKEN_FOR       = 129
TOKEN_NEXT      = 130
TOKEN_DO        = 200
TOKEN_LOOP      = 201
TOKEN_EOF       = $00
TOKEN_NUMBER    = $02

.import keyword_token
.import keyword_dialect
.import keyword_modes
.import keyword_count_value
.import token_init, token_next, token_keyword_id, token_dialect

.segment "BSS"
.export semantic_dialect
semantic_dialect: .res 1
.export semantic_numeric_mode
semantic_numeric_mode: .res 1
.export semantic_policy_generation
semantic_policy_generation: .res 2
.export semantic_source_ptr
semantic_source_ptr: .res 2
semantic_for_depth: .res 1
semantic_do_depth: .res 1
semantic_program_line: .res 1

.segment "GEOASM"

; semantic_validate_dialect - Validate one keyword token against active dialect.
; Inputs: A=token ID. Outputs: A preserved; C=1 when token is unknown or disabled.
; Side effects: none. Clobbers: X, flags. Zero page: none.
.export semantic_validate_dialect
semantic_validate_dialect:
    ldx #0
@find:
    cpx keyword_count_value
    beq @unknown
    cmp keyword_token,x
    beq @found
    inx
    bne @find
@unknown:
    sec
    rts
@found:
    pha
    lda semantic_dialect
    beq @basic2
    lda #DIALECT_MASK_BASIC2 | DIALECT_MASK_BASIC35
    bne @check
@basic2:
    lda #DIALECT_MASK_BASIC2
@check:
    and keyword_dialect,x
    beq @invalid
    pla
    clc
    rts
@invalid:
    pla
    sec
    rts

; semantic_classify_direct - Apply stored-program policy to a statement token.
; Inputs: A=statement token. Outputs: A preserved; C=1 for direct-only command.
; Side effects: none. Clobbers: flags. Zero page: none.
.export semantic_classify_direct
semantic_classify_direct:
    ldx #0
@find:
    cpx keyword_count_value
    beq @allowed
    cmp keyword_token,x
    beq @found
    inx
    bne @find
@found:
    pha
    lda keyword_modes,x
    and #KEYWORD_MODE_PROGRAM
    bne @pop_allowed
    lda keyword_modes,x
    and #KEYWORD_MODE_DIRECT
    beq @pop_allowed
    pla
@direct:
    sec
    rts
@pop_allowed:
    pla
@allowed:
    clc
    rts

; semantic_validate_line - Validate a source line through the tokenizer stream.
; Inputs: X/Y=zero-terminated canonical line. Outputs: C=error, A=error index.
; Validates dialect and direct/program policy without publishing state.
; Side effects: tokenizer cursor and temporary BSS only. Clobbers: A, X, Y.
; Zero page: none.
.export semantic_validate_line
semantic_validate_line:
    stx semantic_source_ptr
    sty semantic_source_ptr+1
    lda #0
    sta semantic_for_depth
    sta semantic_do_depth
    sta semantic_program_line
    jsr token_init
    lda semantic_dialect
    sta token_dialect
    jsr token_next
    bcs @syntax_error
    cmp #TOKEN_NUMBER
    bne @inspect
    lda #1
    sta semantic_program_line
    jsr token_next
    bcs @syntax_error
    jmp @inspect
@next:
    jsr token_next
    bcs @syntax_error
@inspect:
    cmp #TOKEN_EOF
    beq @finish
    lda token_keyword_id
    beq @next
    pha
    jsr semantic_validate_dialect
    bcs @dialect_error
    pla
    ldx semantic_program_line
    beq @control
    pha
    jsr semantic_classify_direct
    bcs @direct_error
    pla
@control:
    cmp #TOKEN_FOR
    beq @for
    cmp #TOKEN_NEXT
    beq @next_stmt
    cmp #TOKEN_DO
    beq @do
    cmp #TOKEN_LOOP
    beq @loop
    jmp @next
@for:
    inc semantic_for_depth
    bne @next
    lda #ERR_FORMULA_TOO_COMPLEX
    sec
    rts
@next_stmt:
    lda semantic_for_depth
    beq @next_without_for
    dec semantic_for_depth
    jmp @next
@do:
    inc semantic_do_depth
    bne @next
    lda #ERR_FORMULA_TOO_COMPLEX
    sec
    rts
@loop:
    lda semantic_do_depth
    beq @syntax_error
    dec semantic_do_depth
    jmp @next
@finish:
    lda #ERR_OK
    clc
    rts
@dialect_error:
    pla
    jmp @syntax_error
@direct_error:
    pla
    lda #ERR_ILLEGAL_DIRECT
    sec
    rts
@syntax_error:
    lda #ERR_SYNTAX
    sec
    rts
@next_without_for:
    lda #ERR_NEXT_WITHOUT_FOR
    sec
    rts

; semantic_check_for_dialect - Return active dialect.
; Inputs: none. Outputs: A=current dialect, C=0. Clobbers: A, flags.
.export semantic_check_for_dialect
semantic_check_for_dialect:
    lda semantic_dialect
    clc
    rts

; semantic_set_dialect - Select BASIC dialect and invalidate policy generation.
; Inputs: A=dialect. Outputs: C=1 if unsupported. A preserved.
.export semantic_set_dialect
semantic_set_dialect:
    cmp #DIALECT_BASICV35+1
    bcs @invalid
    cmp semantic_dialect
    beq @ok
    sta semantic_dialect
    jsr _semantic_advance_generation
@ok:
    clc
    rts
@invalid:
    sec
    rts

; semantic_get_numeric_mode - Return active numeric mode.
; Inputs: none. Outputs: A=current numeric mode, C=0.
.export semantic_get_numeric_mode
semantic_get_numeric_mode:
    lda semantic_numeric_mode
    clc
    rts

; semantic_set_numeric_mode - Select numeric policy and invalidate generation.
; Inputs: A=mode. Outputs: C=1 if unsupported. A preserved.
.export semantic_set_numeric_mode
semantic_set_numeric_mode:
    cmp #NUMERIC_INT_FAST+1
    bcs @invalid
    cmp semantic_numeric_mode
    beq @ok
    sta semantic_numeric_mode
    jsr _semantic_advance_generation
@ok:
    clc
    rts
@invalid:
    sec
    rts

_semantic_advance_generation:
    inc semantic_policy_generation
    bne @done
    inc semantic_policy_generation+1
@done:
    rts
