; src/runtime/ieee_state.asm
; Numeric-mode state management for IEEE 754 floating-point operations.
; This module owns IEEE status/rounding behavior missing from pure math
; operations.

.include "common/zp.inc"
.include "common/constants.asm"

; IEEE Mode constants
IEEE_MODE_LEGACY = 0
IEEE_MODE_IEEE   = 1

; IEEE Flag bits
FP_FLAG_INVALID    = $80
FP_FLAG_DIV_ZERO   = $40
FP_FLAG_OVERFLOW   = $20
FP_FLAG_UNDERFLOW  = $10
FP_FLAG_INEXACT    = $08

; IEEE Rounding modes
FP_ROUND_NEAREST  = 0
FP_ROUND_DOWN     = 1
FP_ROUND_UP       = 2
FP_ROUND_TRUNCATE = 3

; IEEE Constant IDs
FP_CONST_INF  = 0
FP_CONST_NAN  = 1
FP_CONST_SNAN = 2

; State variables. These are persistent runtime state, not scratch; keep them
; out of zero page so they cannot collide with generated ZP allocations.
.segment "BSS"

; Current IEEE mode
FP_MODE:
    .res 1

; Current IEEE flags (sticky)
FP_FLAGS:
    .res 1

; Current rounding mode
FP_ROUNDING:
    .res 1

.segment "CODE"

; =============================================================================
; Mode Management
; =============================================================================

; fp_get_mode - Get current IEEE mode
; Input:  none
; Output: A = current mode (0=legacy, 1=IEEE)
; Clobbers: A
.export fp_get_mode
fp_get_mode:
    lda FP_MODE
    rts

; fp_set_mode - Set IEEE mode
; Input:  A = new mode
; Output: C = error (0=ok)
; Clobbers: A, X, Y
.export fp_set_mode
fp_set_mode:
    ; Validate mode
    cmp #IEEE_MODE_LEGACY
    beq @valid
    cmp #IEEE_MODE_IEEE
    beq @valid
    ; Invalid mode
    sec
    rts
    
@valid:
    sta FP_MODE
    clc
    rts

; =============================================================================
; Flag Management
; =============================================================================

; fp_get_flags - Get current IEEE flags
; Input:  A = flag mask (which flags to read)
; Output: A = current flags (masked)
; Clobbers: A
.export fp_get_flags
fp_get_flags:
    and FP_FLAGS
    rts

; fp_clear_flags - Clear IEEE flags
; Input:  A = flag mask (which flags to clear)
; Output: none
; Clobbers: A
.export fp_clear_flags
fp_clear_flags:
    ; Clear specified flags
    eor #$FF           ; Invert mask
    and FP_FLAGS
    sta FP_FLAGS
    rts

; fp_test_flags - Test IEEE flags
; Input:  X/Y = test descriptor (pointer to flag mask)
; Output: A = boolean result (0/1)
; Clobbers: A, X, Y
.export fp_test_flags
fp_test_flags:
    ; Load test mask from descriptor
    stx zp_tmp1
    sty zp_tmp1+1
    ldy #0
    lda (zp_tmp1), y
    and FP_FLAGS
    beq @false
    lda #1
    rts
@false:
    lda #0
    rts

; =============================================================================
; Rounding Management
; =============================================================================

; fp_set_rounding - Set rounding mode
; Input:  A = rounding ID
; Output: C = error (0=ok)
; Clobbers: A, flags
.export fp_set_rounding
fp_set_rounding:
    ; Validate rounding mode
    cmp #FP_ROUND_NEAREST
    beq @valid
    cmp #FP_ROUND_DOWN
    beq @valid
    cmp #FP_ROUND_UP
    beq @valid
    cmp #FP_ROUND_TRUNCATE
    beq @valid
    ; Invalid rounding mode
    sec
    rts
    
@valid:
    sta FP_ROUNDING
    clc
    rts

; =============================================================================
; IEEE Constants
; =============================================================================

; fp_load_constant - Load IEEE special constant
; Input:  A = constant ID (INF, NAN, SNAN)
; Output: FAC1 = constant value
; Clobbers: A, X, Y
.export fp_load_constant
fp_load_constant:
    ; Check constant ID
    cmp #FP_CONST_INF
    beq @load_inf
    cmp #FP_CONST_NAN
    beq @load_nan
    cmp #FP_CONST_SNAN
    beq @load_snan
    ; Invalid ID, return zero
    jsr @clear_fac
    rts
    
@load_inf:
    ; Load +Infinity: exponent=$FF, mantissa=$800000, sign=0
    lda #$FF
    sta zp_fac1
    lda #$80
    sta zp_fac1+1
    lda #$00
    sta zp_fac1+2
    sta zp_fac1+3
    sta zp_fac1+4
    rts
    
@load_nan:
    ; Load quiet NaN: exponent=$FF, mantissa=$C00000, sign=0
    lda #$FF
    sta zp_fac1
    lda #$C0
    sta zp_fac1+1
    lda #$00
    sta zp_fac1+2
    sta zp_fac1+3
    sta zp_fac1+4
    rts
    
@load_snan:
    ; Load signaling NaN: exponent=$FF, mantissa=$800001, sign=0
    lda #$FF
    sta zp_fac1
    lda #$80
    sta zp_fac1+1
    lda #$00
    sta zp_fac1+2
    sta zp_fac1+3
    lda #$01
    sta zp_fac1+4
    rts
    
@clear_fac:
    ; Clear FAC1 (set to zero)
    lda #$00
    sta zp_fac1
    sta zp_fac1+1
    sta zp_fac1+2
    sta zp_fac1+3
    sta zp_fac1+4
    rts
