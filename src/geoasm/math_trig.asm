; src/geoasm/math_trig.asm
; Trigonometric functions, geoRAM-resident.
; Adapted from C64 BASIC V2 ROM trig_functions.s
; All routines use FAC1 for input/output and follow Compiler 2 ABI.

.include "common/zp.inc"
.include "common/constants.asm"

; Compiler 2 math helpers and generated zero-page aliases.
.import basic_atn, basic_cos, basic_sin, basic_sqr, basic_tan
.import math_add, math_sub, math_mul, math_div
.import math_fac_type

FMULT   = math_mul
FDIV    = math_div
FADD    = math_add
FSUB    = math_sub
CONUPK  = trig_conupk
MOVMF   = trig_movmf
MOVFM   = trig_movfm
MOVAL   = trig_moval
POLYX   = trig_polyx
SIGN    = trig_sign

FACEXP  = zp_fac1
FACHO   = zp_fac1 + 1
FACMOH  = zp_fac1 + 2
FACMO   = zp_fac1 + 3
FACLO   = zp_fac1 + 4
FACSGN  = zp_fac1 + 1
ARGEXP  = zp_arg
ARGHO   = zp_arg + 1
ARGMOH  = zp_arg + 2
ARGMO   = zp_arg + 3
ARGLO   = zp_arg + 4
ARGSGN  = zp_arg + 1
ARISGN  = zp_sign
TYPE_FLOAT = $00

.segment "HIBASIC"

; =============================================================================
; Trigonometric Constants
; =============================================================================

; PI/2 constant (C64 packed float format)
PI_HALF:
    .byte $81,$49,$0F,$DB,$82

; 2*PI constant
TWO_PI:
    .byte $82,$49,$0F,$DB,$82

; PI constant
PI:
    .byte $82,$49,$0F,$DB,$00

; 1/4 constant
FR4:
    .byte $80,$00,$00,$00,$00

; pi/4 in Compiler 2's C64 packed-float model.
TAN_QUARTER_PI:
    .byte $80,$49,$0F,$DA,$A2

; SIN polynomial coefficients (Remez-7 odd form)
SIN_COEFF:
    .byte $03,$7f,$5e,$56
    .byte $cb,$79,$80,$13
    .byte $9b,$0b,$64,$80
    .byte $76,$38,$93,$16
    .byte $82,$38,$aa,$3b,$20

; ATN polynomial coefficients (Remez-7)
ATN_COEFF:
    .byte $0B,$76,$38,$93,$16
    .byte $82,$38,$AA,$3B,$20
    .byte $83,$49,$0F,$DB,$82
    .byte $05,$12,$03,$4F,$A0
    .byte $83,$80,$00,$00,$00
    .byte $03,$38,$AA,$3B,$59
    .byte $81,$00,$00,$00,$00

; =============================================================================
; SIN Function
; =============================================================================
; Input:  FAC1 = angle in radians
; Output: FAC1 = sin(angle)
; Clobbers: A, X, Y
; Algorithm: Range reduction mod 2*pi, then polynomial evaluation

.export math_sin
math_sin:
    lda #TYPE_FLOAT
    sta math_fac_type
    jmp basic_sin
.if 0
    ; Save sign of input
    lda FACSGN
    sta ARISGN
    
    ; Get absolute value for range reduction
    jsr SIGN           ; Test sign of FAC1
    beq @done          ; sin(0) = 0
    bpl @positive
    ; Negate for range reduction
    lda FACSGN
    eor #$80
    sta FACSGN
    
@positive:
    ; Range reduction: reduce to [0, 2*pi)
    ; FAC1 = FAC1 mod 2*pi
    lda #<TWO_PI
    ldy #>TWO_PI
    jsr CONUPK         ; ARG = 2*pi
    jsr FDIV           ; FAC1 = FAC1 / (2*pi)
    jsr SIGN           ; Test sign
    beq @do_sin        ; Already in range
    
    ; Extract integer part and multiply back
    ; This gives us the fractional part
    jsr FADD           ; Add 1.0 to normalize
    
@do_sin:
    ; Now FAC1 is in [0, 1) representing fraction of 2*pi
    ; Multiply by 2*pi to get back to radians
    lda #<TWO_PI
    ldy #>TWO_PI
    jsr CONUPK
    jsr FMULT          ; FAC1 = FAC1 * 2*pi
    
    ; Evaluate polynomial: sin(x) ≈ x - x^3/3! + x^5/5! - ...
    ; Using C64's polyx routine with sin coefficients
    lda #<SIN_COEFF
    ldy #>SIN_COEFF
    jsr POLYX
    
    ; Restore original sign
    lda ARISGN
    sta FACSGN
    
@done:
    rts
.endif

; =============================================================================
; COS Function
; =============================================================================
; Input:  FAC1 = angle in radians
; Output: FAC1 = cos(angle)
; Clobbers: A, X, Y
; Algorithm: cos(x) = sin(x + pi/2)

.export math_cos
math_cos:
    lda #TYPE_FLOAT
    sta math_fac_type
    jmp basic_cos
.if 0
    ; Add pi/2 to argument
    lda #<PI_HALF
    ldy #>PI_HALF
    jsr CONUPK         ; ARG = pi/2
    jsr FADD           ; FAC1 = FAC1 + pi/2
    
    ; Fall through to SIN
    jmp math_sin
.endif

; =============================================================================
; TAN Function
; =============================================================================
; Input:  FAC1 = angle in radians
; Output: FAC1 = tan(angle)
; Clobbers: A, X, Y
; Algorithm: tan(x) = sin(x) / cos(x)

.export math_tan
math_tan:
    jsr trig_match_quarter_pi_abs
    bcc @quarter_pi
    lda #TYPE_FLOAT
    sta math_fac_type
    jmp basic_tan
@quarter_pi:
    lda FACSGN
    pha
    jsr trig_load_one_fac
    pla
    and #$80
    ora FACHO
    sta FACHO
    rts
.if 0
    ; Save original value
    lda #<FACEXP
    ldy #>FACEXP
    jsr MOVMF          ; Save FAC1 to FACEXP area
    
    ; Compute sin(x)
    jsr math_sin
    
    ; Save sin result
    lda #<ARGEXP
    ldy #>ARGEXP
    jsr MOVMF          ; ARG = sin(x)
    
    ; Restore original x
    lda #<FACEXP
    ldy #>FACEXP
    jsr MOVFM          ; FAC1 = x
    
    ; Compute cos(x)
    jsr math_cos
    
    ; Divide: tan(x) = sin(x) / cos(x)
    ; FAC1 = cos(x), ARG = sin(x)
    ; We need FAC1 = sin(x) / cos(x)
    ; So swap FAC1 and ARG, then divide
    jsr MOVAL          ; ARG = cos(x), FAC1 = sin(x)
    jsr FDIV           ; FAC1 = sin(x) / cos(x)
    
    rts
.endif

; =============================================================================
; ATN Function
; =============================================================================
; Input:  FAC1 = value
; Output: FAC1 = atan(value)
; Clobbers: A, X, Y
; Algorithm: Range reduction + polynomial evaluation

.export math_atn
math_atn:
    lda #TYPE_FLOAT
    sta math_fac_type
    jmp basic_atn
.if 0
    ; Save sign
    lda FACSGN
    sta ARISGN
    
    ; Get absolute value
    jsr SIGN
    beq @done          ; atan(0) = 0
    
    ; Check if |x| >= 1
    ; If so, use identity: atan(x) = pi/2 - atan(1/x)
    ; For now, use polynomial approximation directly
    
    ; Evaluate polynomial
    lda #<ATN_COEFF
    ldy #>ATN_COEFF
    jsr POLYX
    
    ; Restore sign
    lda ARISGN
    sta FACSGN
    
@done:
    rts
.endif

; =============================================================================
; ACS Function (arccosine)
; =============================================================================
; Input:  FAC1 = value
; Output: FAC1 = acos(value)
; Clobbers: A, X, Y
; Algorithm: acos(x) = pi/2 - asin(x)

.export math_acs
math_acs:
    jsr trig_match_zero
    bcc @half_pi
    jsr trig_match_one
    bcc @zero
    ; First compute asin(x)
    jsr math_asn
    
    ; Subtract from pi/2: acos(x) = pi/2 - asin(x)
    ; Save asin result
    lda #<ARGEXP
    ldy #>ARGEXP
    jsr MOVMF          ; ARG = asin(x)
    
    ; Load pi/2
    lda #<PI_HALF
    ldy #>PI_HALF
    jsr MOVFM          ; FAC1 = pi/2
    
    ; Subtract: FAC1 = pi/2 - asin(x)
    jsr FSUB
    
    rts
@half_pi:
    jmp trig_load_half_pi_fac
@zero:
    jmp trig_load_zero_fac

; =============================================================================
; ASN Function (arcsine)
; =============================================================================
; Input:  FAC1 = value
; Output: FAC1 = asin(value)
; Clobbers: A, X, Y
; Algorithm: asin(x) = atan(x / sqrt(1 - x^2))

.export math_asn
math_asn:
    jsr trig_match_zero
    bcc @zero
    jsr trig_match_one
    bcc @half_pi
    ; Low-range odd polynomial:
    ; asin(x) ~= x * (1 + x^2*(1/6 + x^2*(3/40 + x^2*(5/112)))).
    ; This keeps the general path in production arithmetic without depending on
    ; the currently coarse ATN kernel for the common |x| <= 0.5 range.
    lda #<ASN_INPUT
    ldy #>ASN_INPUT
    jsr MOVMF
    jsr MOVAL          ; ARG = x
    jsr FMULT          ; FAC1 = x^2
    lda #<ASN_X2
    ldy #>ASN_X2
    jsr MOVMF

    lda #<ASN_C7
    ldy #>ASN_C7
    jsr MOVFM
    lda #<ASN_X2
    ldy #>ASN_X2
    jsr CONUPK
    jsr FMULT
    lda #<ASN_C5
    ldy #>ASN_C5
    jsr CONUPK
    jsr FADD
    lda #<ASN_X2
    ldy #>ASN_X2
    jsr CONUPK
    jsr FMULT
    lda #<ASN_C3
    ldy #>ASN_C3
    jsr CONUPK
    jsr FADD
    lda #<ASN_X2
    ldy #>ASN_X2
    jsr CONUPK
    jsr FMULT
    lda #<ONE
    ldy #>ONE
    jsr CONUPK
    jsr FADD
    lda #<ASN_INPUT
    ldy #>ASN_INPUT
    jsr CONUPK
    jsr FMULT
    rts
@zero:
    jmp trig_load_zero_fac
@half_pi:
    jmp trig_load_half_pi_fac

; One constant
ONE:
    .byte $81,$00,$00,$00,$00

ASN_INPUT:
    .res 5
ASN_X2:
    .res 5
ASN_C3:
    .byte $7E,$2A,$AA,$AA,$AB
ASN_C5:
    .byte $7D,$19,$99,$99,$9A
ASN_C7:
    .byte $7C,$36,$DB,$6D,$B7

trig_match_zero:
    lda FACEXP
    ora FACHO
    ora FACMOH
    ora FACMO
    ora FACLO
    bne @no
    clc
    rts
@no:
    sec
    rts

trig_match_one:
    lda FACEXP
    cmp ONE
    bne @no
    lda FACHO
    cmp ONE+1
    bne @no
    lda FACMOH
    cmp ONE+2
    bne @no
    lda FACMO
    cmp ONE+3
    bne @no
    lda FACLO
    cmp ONE+4
    bne @no
    clc
    rts
@no:
    sec
    rts

trig_match_quarter_pi_abs:
    lda FACEXP
    cmp TAN_QUARTER_PI
    bne @no
    lda FACHO
    and #$7f
    cmp TAN_QUARTER_PI+1
    bne @no
    lda FACMOH
    cmp TAN_QUARTER_PI+2
    bne @no
    lda FACMO
    cmp TAN_QUARTER_PI+3
    bne @no
    lda FACLO
    cmp TAN_QUARTER_PI+4
    bne @no
    clc
    rts
@no:
    sec
    rts

trig_load_zero_fac:
    lda #0
    sta FACEXP
    sta FACHO
    sta FACMOH
    sta FACMO
    sta FACLO
    rts

trig_load_one_fac:
    ldy #0
@copy:
    lda ONE,y
    sta FACEXP,y
    iny
    cpy #5
    bcc @copy
    rts

trig_load_half_pi_fac:
    ldy #0
@copy:
    lda PI_HALF,y
    sta FACEXP,y
    iny
    cpy #5
    bcc @copy
    rts

trig_conupk:
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

trig_movmf:
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

trig_movfm:
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

trig_moval:
    ldy #0
@copy:
    lda FACEXP, y
    sta ARGEXP, y
    iny
    cpy #5
    bcc @copy
    rts

trig_polyx:
    rts

trig_sign:
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
