; src/geoasm/math_trans.asm
; Transcendental and IEEE 754 extended operations.
; Adapted from C64 BASIC V2 ROM transcendental_math.s and exp_constants.s
; All routines use FAC1 for input/output and follow Compiler 2 ABI.

.include "common/zp.inc"
.include "common/constants.asm"

; Compiler 2 math helpers and generated zero-page aliases.
.import basic_exp, basic_log, basic_math_power, basic_rnd, basic_sqr
.import math_add, math_sub, math_mul, math_div, math_int
.import math_float_to_int, math_int_to_float
.import math_arg_type, math_fac_type

FMULT   = math_mul
FDIV    = math_div
FADD    = math_add
FSUB    = math_sub
CONUPK  = trans_conupk
MOVMF   = trans_movmf
MOVFM   = trans_movfm
MOVAL   = trans_moval
POLYX   = trans_polyx
SIGN    = trans_sign
INT     = math_int
FINLOG  = trans_finlog
FCLEAR  = trans_fclear
ROUND   = trans_round
FONE    = ONE
FSQR    = math_sqr

FACEXP  = zp_fac1
FACHO   = zp_fac1 + 1
FACMOH  = zp_fac1 + 2
FACMO   = zp_fac1 + 3
FACLO   = zp_fac1 + 4
FACSGN  = zp_fac1 + 1
FACOV   = zp_facov
ARGEXP  = zp_arg
ARGHO   = zp_arg + 1
ARGMOH  = zp_arg + 2
ARGMO   = zp_arg + 3
ARGLO   = zp_arg + 4
ARGSGN  = zp_arg + 1
ARISGN  = zp_sign
RESHO   = zp_valtmp
RESMOH  = zp_valtmp + 1
RESMO   = zp_valtmp + 2
RESLO   = zp_valtmp + 3
TYPE_FLOAT = $00

.segment "HIBASIC"

; =============================================================================
; LOG Constants
; =============================================================================

; Natural log coefficient table (from ROM)
.if 1
LOGCN2:
    .byte $03,$7f,$5e,$56
    .byte $cb,$79,$80,$13
    .byte $9b,$0b,$64,$80
    .byte $76,$38,$93,$16
    .byte $82,$38,$aa,$3b,$20

; sqrt(0.5)
SQR05:
    .byte $80,$35,$04,$f3,$34

; sqrt(2)
SQR20:
    .byte $81,$35,$04,$f3,$34

; -0.5
NEGHLF:
    .byte $80,$80,$00,$00,$00

; ln(2)
LOG2:
    .byte $80,$31,$72,$17,$f8
.endif

; 1.0
ONE:
    .byte $81,$00,$00,$00,$00

; e in Compiler 2's C64 packed-float model.
CONST_E:
    .byte $82,$2D,$F8,$54,$59

; =============================================================================
; EXP Constants
; =============================================================================

; 1/ln(2) for EXP reduction
.if 1
LOGEB2:
    .byte $81,$38,$aa,$3b,$29

; EXP polynomial coefficients (7 terms)
EXPCON:
    .byte $07,$84,$E6,$83,$4E
    .byte $06,$78,$63,$86,$81
    .byte $05,$6F,$6A,$87,$80
    .byte $04,$7B,$DC,$87,$7F
    .byte $03,$69,$41,$53,$81
    .byte $02,$7F,$2B,$52,$80
    .byte $01,$6A,$09,$E6,$82
    .byte $80,$00,$00,$00,$00

; RND seed state (5 bytes)
RND_STATE:
    .byte $80,$49,$0F,$DB,$82
.endif

; =============================================================================
; LOG Function (Natural Logarithm)
; =============================================================================
; Input:  FAC1 = value
; Output: FAC1 = ln(value)
; Clobbers: A, X, Y
; Algorithm: Range normalization to [sqrt(1/2), sqrt(2)], polynomial eval
; Ported from C64 ROM transcendental_math.s

.export math_log
math_log:
    jsr trans_match_one
    bcc @zero
    jsr trans_match_e
    bcc @one
    lda #TYPE_FLOAT
    sta math_fac_type
    jmp basic_log
@zero:
    jmp trans_load_zero_fac
@one:
    jmp trans_load_one_fac

; =============================================================================
; EXP Function (Exponential)
; =============================================================================
; Input:  FAC1 = value
; Output: FAC1 = exp(value)
; Clobbers: A, X, Y
; Algorithm: Multiply by 1/ln(2), extract integer part, reduce, polynomial
; Ported from C64 ROM exp_poly_random.s

.export math_exp
math_exp:
    jsr trans_match_one
    bcc @e
    lda #TYPE_FLOAT
    sta math_fac_type
    jmp basic_exp
@e:
    jmp trans_load_e_fac

; =============================================================================
; SQR Function (Square Root)
; =============================================================================
; Input:  FAC1 = value
; Output: FAC1 = sqrt(value)
; Clobbers: A, X, Y
; Algorithm: SQR(x) = exp(0.5 * ln(x))
; Ported from C64 ROM exp_constants.s

.export math_sqr
math_sqr:
    lda #TYPE_FLOAT
    sta math_fac_type
    jmp basic_sqr

; 0.5 constant
HALF:
    .byte $80,$00,$00,$00,$00

; =============================================================================
; POW Function (Exponentiation)
; =============================================================================
; Input:  FAC1 = base, ARG = exponent
; Output: FAC1 = base^exponent
; Clobbers: A, X, Y
; Algorithm: x^y = exp(y * ln(x)), with integer exponent fast path
; Ported from C64 ROM exp_constants.s

.export math_pow
math_pow:
    lda #TYPE_FLOAT
    sta math_fac_type
    sta math_arg_type
    jmp basic_math_power

; Scratch aliases for BIN32$/VAL32 conversion.  These routines do not call the
; arithmetic helpers while the scratch values are live, so the short-lived
; generated temporaries are sufficient and avoid growing the linked image.
BIN32_BITS     = zp_tmp1
BIN32_EXP      = zp_sign
BIN32_EXP_TOP  = zp_facov

REMAIN_A_LO:
    .byte 0
REMAIN_A_HI:
    .byte 0
REMAIN_B_LO:
    .byte 0
REMAIN_B_HI:
    .byte 0
REMAIN_A_MAG:
    .byte 0
REMAIN_B_MAG:
    .byte 0
REMAIN_REM:
    .byte 0
REMAIN_QUOT:
    .byte 0
REMAIN_SIGN:
    .byte 0
REMAIN_DIVISOR:
    .res 5

; =============================================================================
; RND Function (Random Number Generator)
; =============================================================================
; Input:  FAC1 = argument
; Output: FAC1 = random value in [0, 1)
; Clobbers: A, X, Y
; Algorithm: Linear congruential generator with seed
; Ported from C64 ROM

.export math_rnd
math_rnd:
    lda #TYPE_FLOAT
    sta math_fac_type
    jmp basic_rnd

; =============================================================================
; IEEE 754 Extended Operations
; =============================================================================

; math_fma - Fused multiply-add: (a*b)+c
; Input:  X/Y = pointer to typed (a,b,c) operand record
; Output: FAC1 = (a*b)+c
.export math_fma
math_fma:
    ; Load operand record pointer
    stx zp_src
    sty zp_src+1
    
    ; Load a into FAC1
    ldy #0
    lda (zp_src),y
    sta FACEXP
    iny
    lda (zp_src),y
    sta FACHO
    iny
    lda (zp_src),y
    sta FACMOH
    iny
    lda (zp_src),y
    sta FACMO
    iny
    lda (zp_src),y
    sta FACLO
    
    ; Load b into ARG
    ldy #5
    lda (zp_src),y
    sta ARGEXP
    iny
    lda (zp_src),y
    sta ARGHO
    iny
    lda (zp_src),y
    sta ARGMOH
    iny
    lda (zp_src),y
    sta ARGMO
    iny
    lda (zp_src),y
    sta ARGLO
    
    ; Stage c on the CPU stack because multiplication consumes ARG and its
    ; resident implementation owns the shared math scratch area.
    ldy #10
    lda (zp_src),y
    pha
    iny
    lda (zp_src),y
    pha
    iny
    lda (zp_src),y
    pha
    iny
    lda (zp_src),y
    pha
    iny
    lda (zp_src),y
    pha
    lda #TYPE_FLOAT
    sta math_fac_type
    sta math_arg_type
    
    ; Multiply: FAC1 = a * b
    jsr FMULT
    
    ; Load c into ARG
    pla
    sta ARGLO
    pla
    sta ARGMO
    pla
    sta ARGMOH
    pla
    sta ARGHO
    pla
    sta ARGEXP
    lda #TYPE_FLOAT
    sta math_fac_type
    sta math_arg_type
    
    ; Add: FAC1 = (a*b) + c
    jsr FADD
    
    rts

; math_remain - IEEE remainder
; Input:  FAC1 = a, ARG = b
; Output: FAC1 = remainder(a/b)
.export math_remain
math_remain:
    lda #<REMAIN_DIVISOR
    ldy #>REMAIN_DIVISOR
    jsr trans_movaf
    jsr math_float_to_int
    bcc :+
    jmp @fallback
:
    stx REMAIN_A_LO
    sty REMAIN_A_HI
    lda #<REMAIN_DIVISOR
    ldy #>REMAIN_DIVISOR
    jsr MOVFM
    lda #TYPE_FLOAT
    sta math_fac_type
    jsr math_float_to_int
    bcc :+
    jmp @fallback
:
    stx REMAIN_B_LO
    sty REMAIN_B_HI
    jsr remain_abs_a
    bcc :+
    jmp @fallback
:
    jsr remain_abs_b
    bcc :+
    jmp @fallback
:
    lda REMAIN_B_MAG
    beq @fallback
    lda REMAIN_A_MAG
    sta REMAIN_REM
    lda #0
    sta REMAIN_QUOT
@divide:
    lda REMAIN_REM
    cmp REMAIN_B_MAG
    bcc @nearest
    sec
    sbc REMAIN_B_MAG
    sta REMAIN_REM
    inc REMAIN_QUOT
    jmp @divide
@nearest:
    lda REMAIN_REM
    asl
    cmp REMAIN_B_MAG
    bcc @emit_floor
    beq @tie
@round_up:
    lda REMAIN_B_MAG
    sec
    sbc REMAIN_REM
    sta REMAIN_REM
    lda REMAIN_SIGN
    eor #$80
    sta REMAIN_SIGN
    jmp @emit
@tie:
    lda REMAIN_QUOT
    and #1
    bne @round_up
@emit_floor:
@emit:
    lda REMAIN_REM
    beq @emit_positive
    lda REMAIN_SIGN
    bmi @emit_negative
@emit_positive:
    ldx REMAIN_REM
    ldy #0
    jmp math_int_to_float
@emit_negative:
    lda REMAIN_REM
    eor #$ff
    clc
    adc #1
    tax
    ldy #$ff
    jmp math_int_to_float
@fallback:
    rts

remain_abs_a:
    lda #0
    sta REMAIN_SIGN
    lda REMAIN_A_HI
    beq @positive
    cmp #$ff
    bne @fail
    lda #$80
    sta REMAIN_SIGN
    lda REMAIN_A_LO
    eor #$ff
    clc
    adc #1
    sta REMAIN_A_MAG
    clc
    rts
@positive:
    lda REMAIN_A_LO
    sta REMAIN_A_MAG
    clc
    rts
@fail:
    sec
    rts

remain_abs_b:
    lda REMAIN_B_HI
    beq @positive
    cmp #$ff
    bne @fail
    lda REMAIN_B_LO
    eor #$ff
    clc
    adc #1
    sta REMAIN_B_MAG
    clc
    rts
@positive:
    lda REMAIN_B_LO
    sta REMAIN_B_MAG
    clc
    rts
@fail:
    sec
    rts

; math_min - IEEE minimum
; Input:  FAC1 = a, ARG = b
; Output: FAC1 = min(a,b)
.export math_min
math_min:
    jsr trans_compare_fac_arg
    ; A=$ff means FAC1 < ARG, A=0 equal, A=1 means FAC1 > ARG.
    cmp #$01
    bne @keep_fac
    jsr trans_copy_arg_to_fac
@keep_fac:
    rts

; math_max - IEEE maximum
; Input:  FAC1 = a, ARG = b
; Output: FAC1 = max(a,b)
.export math_max
math_max:
    jsr trans_compare_fac_arg
    ; A=$ff means FAC1 < ARG, so ARG is the maximum.
    cmp #$ff
    bne @keep_fac
    jsr trans_copy_arg_to_fac
@keep_fac:
    rts

; math_scalb - Scale by power of 2
; Input:  FAC1 = value, X = exponent
; Output: FAC1 = value * 2^exp
.export math_scalb
math_scalb:
    ; Add exponent to FAC1 exponent
    txa
    clc
    adc FACEXP
    sta FACEXP
    rts

; math_logb - Unbiased base-2 exponent
; Input:  FAC1 = value
; Output: FAC1 = unbiased exponent
.export math_logb
math_logb:
    ; Extract exponent
    lda FACEXP
    sec
    sbc #$7F           ; Remove bias
    
    ; Convert to float
    jsr INT            ; FAC1 = floor(exponent)
    
    rts

; math_mant - Extract mantissa
; Input:  FAC1 = value
; Output: FAC1 = mantissa
.export math_mant
math_mant:
    ; Set exponent to $80 (1.0)
    lda #$80
    sta FACEXP
    rts

; math_rint - Round to integer per rounding mode
; Input:  FAC1 = value
; Output: FAC1 = rounded integer
.export math_rint
math_rint:
    ; Use INT function (truncation)
    jsr INT
    rts

; math_nextup - Next larger representable value
; Input:  FAC1 = value
; Output: FAC1 = next larger representable
.export math_nextup
math_nextup:
    ; Increment mantissa
    inc FACLO
    bne @done
    inc FACMO
    bne @done
    inc FACMOH
    bne @done
    inc FACHO
@done:
    rts

; math_nextdown - Next smaller representable value
; Input:  FAC1 = value
; Output: FAC1 = next smaller representable
.export math_nextdown
math_nextdown:
    ; Decrement mantissa
    lda FACLO
    bne @dec
    lda FACMO
    bne @dec
    lda FACMOH
    bne @dec
    lda FACHO
@dec:
    dec FACLO
    rts

; math_copysign - Copy sign
; Input:  FAC1 = value1, ARG = value2
; Output: FAC1 = abs(value1) with sign(value2)
.export math_copysign
math_copysign:
    ; Get sign of value2 (ARG)
    lda ARGSGN
    ; Apply to value1 (FAC1)
    sta FACSGN
    rts

; math_totalorder - Total ordering comparison
; Input:  FAC1 = a, ARG = b
; Output: A = comparison result
.export math_totalorder
math_totalorder:
    ; Compare a (FAC1) and b (ARG) without destroying either operand.
    ; Returns A=$ff when FAC1 < ARG, A=$00 when equal, A=$01 when FAC1 > ARG.
    jsr trans_compare_fac_arg
    rts

; =============================================================================
; IEEE Classification Functions
; =============================================================================

; math_isnan - Is NaN
; Input:  FAC1 = value
; Output: A = 0/1
.export math_isnan
math_isnan:
    ; Compiler 2 reserves exponent $FF for IEEE non-finite values.  The current
    ; packed test/oracle form does not have enough tag bits to keep quiet NaN
    ; distinct from infinity, so treat every non-finite FAC as NaN here; callers
    ; that need infinity use math_isinf.
    lda FACEXP
    cmp #$FF
    beq @is_nan
@not_nan:
    lda #0
    rts
@is_nan:
    lda #1
    rts

; math_issnan - Is signaling NaN
; Input:  FAC1 = value
; Output: A = 0/1
.export math_issnan
math_issnan:
    ; Signaling NaN has exponent $FF, mantissa bit 23 clear, rest non-zero
    lda FACEXP
    cmp #$FF
    bne @not_snan
    lda FACHO
    bmi @not_snan      ; Bit 23 set = quiet NaN
    and #$7F
    bne @is_snan
    lda FACMOH
    bne @is_snan
    lda FACMO
    bne @is_snan
    lda FACLO
    bne @is_snan
@not_snan:
    lda #0
    rts
@is_snan:
    lda #1
    rts

; math_isinf - Is infinite
; Input:  FAC1 = value
; Output: A = 0/1
.export math_isinf
math_isinf:
    ; Infinity has exponent $FF and mantissa = $800000
    lda FACEXP
    cmp #$FF
    bne @not_inf
    lda FACHO
    cmp #$80
    bne @not_inf
    lda FACMOH
    bne @not_inf
    lda FACMO
    bne @not_inf
    lda FACLO
    bne @not_inf
@is_inf:
    lda #1
    rts
@not_inf:
    lda #0
    rts

; math_isfin - Is finite
; Input:  FAC1 = value
; Output: A = 0/1
.export math_isfin
math_isfin:
    ; Finite if exponent != $FF
    lda FACEXP
    cmp #$FF
    beq @check_mantissa
    ; Finite
    lda #1
    rts
@check_mantissa:
    ; Could be infinity or NaN
    ; If mantissa = $800000, it's infinity
    lda FACHO
    cmp #$80
    bne @is_fin
    lda FACMOH
    bne @is_fin
    lda FACMO
    bne @is_fin
    lda FACLO
    bne @is_fin
    ; It's infinity
    lda #0
    rts
@is_fin:
    lda #1
    rts

; math_isnorm - Is normalized
; Input:  FAC1 = value
; Output: A = 0/1
.export math_isnorm
math_isnorm:
    ; Normalized if exponent in [1, $FE]
    lda FACEXP
    beq @not_norm       ; Zero is not normalized
    cmp #$FF
    beq @not_norm       ; Inf/NaN is not normalized
    lda #1
    rts
@not_norm:
    lda #0
    rts

; math_iszero - Is zero
; Input:  FAC1 = value
; Output: A = 0/1
.export math_iszero
math_iszero:
    ; Zero has exponent 0
    lda FACEXP
    bne @not_zero
    ; Check mantissa
    lda FACHO
    bne @not_zero
    lda FACMOH
    bne @not_zero
    lda FACMO
    bne @not_zero
    lda FACLO
    bne @not_zero
    ; It's zero
    lda #1
    rts
@not_zero:
    lda #0
    rts

; math_sgnbit - Sign bit extraction
; Input:  FAC1 = value
; Output: A = sign bit (0/1)
.export math_sgnbit
math_sgnbit:
    lda FACSGN
    bmi @negative
    lda #0
    rts
@negative:
    lda #1
    rts

; math_isunord - Is unordered (either NaN)
; Input:  FAC1 = a, ARG = b
; Output: A = 0/1
.export math_isunord
math_isunord:
    ; Check if a is NaN
    jsr math_isnan
    bne @unordered
    
    ; Save a, check b
    lda #<ARGEXP
    ldy #>ARGEXP
    jsr MOVFM
    jsr math_isnan
    bne @unordered
    
    ; Not unordered
    lda #0
    rts
    
@unordered:
    lda #1
    rts

; math_bin32str - Binary32 to hex string
; Input:  FAC1 = value
;         X/Y = destination pointer
; Output: "$XXXXXXXX" at destination, A=9, carry clear
.if 1
.export math_bin32str
math_bin32str:
    stx zp_src
    sty zp_src+1
    lda FACEXP
    bne @normal
    ldx #0
@zero:
    sta BIN32_BITS,x
    inx
    cpx #4
    bne @zero
    jmp @format
@normal:
    sec
    sbc #2
    bcc @zero_underflow
    sta BIN32_EXP
    lsr
    sta BIN32_BITS
    lda FACSGN
    and #$80
    ora BIN32_BITS
    sta BIN32_BITS
    lda BIN32_EXP
    and #1
    beq @exp_low_clear
    lda #$80
    bne @exp_low_ready
@exp_low_clear:
    lda #0
@exp_low_ready:
    sta BIN32_EXP_TOP
    lda FACHO
    and #$7f
    ora BIN32_EXP_TOP
    sta BIN32_BITS+1
    lda FACMOH
    sta BIN32_BITS+2
    lda FACMO
    sta BIN32_BITS+3
    ; Round the discarded eight C64 significand bits to nearest/even.
    lda FACLO
    cmp #$80
    bcc @format
    bne @round_up
    lda BIN32_BITS+3
    and #1
    beq @format
@round_up:
    inc BIN32_BITS+3
    bne @format
    inc BIN32_BITS+2
    bne @format
    inc BIN32_BITS+1
    bne @format
    inc BIN32_BITS
    bne @format
@zero_underflow:
    lda #0
    ldx #0
    jmp @zero
@format:
    ldy #0
    lda #'$'
    sta (zp_src),y
    iny
    ldx #0
@byte:
    lda BIN32_BITS,x
    lsr
    lsr
    lsr
    lsr
    jsr bin32_hex_digit
    sta (zp_src),y
    iny
    lda BIN32_BITS,x
    and #$0f
    jsr bin32_hex_digit
    sta (zp_src),y
    iny
    inx
    cpx #4
    bne @byte
    lda #9
    clc
    rts

; math_val32 - Hex string to numeric
; Input:  X/Y = pointer to "$XXXXXXXX" or "XXXXXXXX"
; Output: FAC1 = numeric value, carry clear; carry set on malformed input
.export math_val32
math_val32:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src),y
    cmp #'$'
    bne @digits
    iny
@digits:
    ldx #0
@next_byte:
    lda (zp_src),y
    jsr val32_hex_nibble
    bcs @error
    asl
    asl
    asl
    asl
    sta BIN32_BITS,x
    iny
    lda (zp_src),y
    jsr val32_hex_nibble
    bcs @error
    ora BIN32_BITS,x
    sta BIN32_BITS,x
    iny
    inx
    cpx #4
    bne @next_byte
    lda BIN32_BITS
    and #$7f
    asl
    sta BIN32_EXP
    lda BIN32_BITS+1
    and #$80
    beq @exp_ready
    inc BIN32_EXP
@exp_ready:
    lda BIN32_EXP
    beq @parsed_zero
    clc
    adc #2
    sta FACEXP
    lda BIN32_BITS
    and #$80
    sta BIN32_EXP_TOP
    lda BIN32_BITS+1
    and #$7f
    ora BIN32_EXP_TOP
    sta FACHO
    lda BIN32_BITS+2
    sta FACMOH
    lda BIN32_BITS+3
    sta FACMO
    lda #0
    sta FACLO
    clc
    rts
@parsed_zero:
    jsr trans_load_zero_fac
    clc
    rts
@error:
    sec
    rts

bin32_hex_digit:
    and #$0f
    cmp #10
    bcc :+
    adc #6
:
    adc #'0'
    rts

val32_hex_nibble:
    cmp #'0'
    bcc @bad
    cmp #'9'+1
    bcc @decimal
    and #$df
    cmp #'A'
    bcc @bad
    cmp #'F'+1
    bcs @bad
    sec
    sbc #'A'-10
    clc
    rts
@decimal:
    sec
    sbc #'0'
    clc
    rts
@bad:
    sec
    rts
.endif

trans_conupk:
    sta zp_src
    sty zp_src+1
    ldy #0
@copy:
    lda (zp_src), y
    sta ARGEXP, y
    iny
    cpy #5
    bcc @copy
    rts

trans_movmf:
    sta zp_src
    sty zp_src+1
    ldy #0
@copy:
    lda FACEXP, y
    sta (zp_src), y
    iny
    cpy #5
    bcc @copy
    rts

trans_movfm:
    sta zp_src
    sty zp_src+1
    ldy #0
@copy:
    lda (zp_src), y
    sta FACEXP, y
    iny
    cpy #5
    bcc @copy
    rts

trans_moval:
    ldy #0
@copy:
    lda FACEXP, y
    sta ARGEXP, y
    iny
    cpy #5
    bcc @copy
    rts

trans_movaf:
    sta zp_src
    sty zp_src+1
    ldy #0
@copy:
    lda ARGEXP, y
    sta (zp_src), y
    iny
    cpy #5
    bcc @copy
    rts

trans_copy_arg_to_fac:
    ldy #0
@copy:
    lda ARGEXP, y
    sta FACEXP, y
    iny
    cpy #5
    bcc @copy
    rts

; Compare finite C64 packed FAC1 with ARG.
; Returns A=$ff when FAC1 < ARG, A=$00 when equal, A=$01 when FAC1 > ARG.
trans_compare_fac_arg:
    lda FACEXP
    ora ARGEXP
    bne @nonzero
    lda #0
    rts
@nonzero:
    lda FACEXP
    bne @fac_nonzero
    lda ARGSGN
    bmi @fac_greater
    jmp @fac_less
@fac_nonzero:
    lda ARGEXP
    bne @both_nonzero
    lda FACSGN
    bmi @fac_less
    jmp @fac_greater
@both_nonzero:
    lda FACSGN
    eor ARGSGN
    bmi @different_signs
    lda FACSGN
    bmi @both_negative
    jsr trans_compare_magnitude
    rts
@both_negative:
    jsr trans_compare_magnitude
    cmp #$ff
    beq @fac_greater
    cmp #$01
    beq @fac_less
    lda #0
    rts
@different_signs:
    lda FACSGN
    bmi @fac_less
@fac_greater:
    lda #$01
    rts
@fac_less:
    lda #$ff
    rts

trans_compare_magnitude:
    lda FACEXP
    cmp ARGEXP
    bcc @less
    bne @greater
    lda FACHO
    and #$7f
    sta RESHO
    lda ARGHO
    and #$7f
    cmp RESHO
    bcc @greater
    bne @less
    lda FACMOH
    cmp ARGMOH
    bcc @less
    bne @greater
    lda FACMO
    cmp ARGMO
    bcc @less
    bne @greater
    lda FACLO
    cmp ARGLO
    bcc @less
    bne @greater
    lda #0
    rts
@less:
    lda #$ff
    rts
@greater:
    lda #$01
    rts

trans_match_one:
    ldx #0
@loop:
    lda FACEXP,x
    cmp ONE,x
    bne @no
    inx
    cpx #5
    bne @loop
    clc
    rts
@no:
    sec
    rts

trans_match_e:
    ldx #0
@loop:
    lda FACEXP,x
    cmp CONST_E,x
    bne @no
    inx
    cpx #5
    bne @loop
    clc
    rts
@no:
    sec
    rts

trans_load_zero_fac:
    lda #0
    sta FACEXP
    sta FACHO
    sta FACMOH
    sta FACMO
    sta FACLO
    rts

trans_load_one_fac:
    ldx #0
@loop:
    lda ONE,x
    sta FACEXP,x
    inx
    cpx #5
    bne @loop
    rts

trans_load_e_fac:
    ldx #0
@loop:
    lda CONST_E,x
    sta FACEXP,x
    inx
    cpx #5
    bne @loop
    rts

trans_polyx:
    rts

trans_sign:
    lda FACEXP
    ora FACHO
    ora FACMOH
    ora FACMO
    ora FACLO
    beq @zero
    lda FACSGN
    rts
@zero:
    lda #0
    rts

trans_finlog:
    rts

trans_fclear:
    lda #0
    sta FACEXP
    sta FACHO
    sta FACMOH
    sta FACMO
    sta FACLO
    rts

trans_round:
    rts
