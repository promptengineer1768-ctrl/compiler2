; src/runtime/math_core.asm
; Compiler 2 resident arithmetic helpers.
;
; Core finite arithmetic is adapted from the proven basic v3 numeric backend.
; The legacy fixed scratch window is remapped to Compiler 2-owned BSS storage;
; FAC/ARG use the generated Compiler 2 zero-page ABI symbols.
;
; Public entries: math_add, math_sub, math_mul, math_div, math_negate,
; math_cmp, math_int, math_sgn, math_abs, math_fpe, math_int_to_float,
; math_float_to_int, math_u24_to_float, math_to_arg_byte, math_add_int, math_sub_int,
; math_mul_int, math_div_int
; Input:  FAC1 and ARG use C64 5-byte packed float format for math_add/sub/mul/div.
; Output: FAC1 receives the fully rounded C64 5-byte packed result.
; Side effects: sets carry on arithmetic domain/divide errors, clears carry on success.
; Clobbers: A, X, Y, math scratch BSS.
; Flags: C clear on success, C set on error; N/Z follow last loaded value.
; Zero-page use: zp_fac1, zp_arg.

.include "common/zp.inc"
.include "common/constants.asm"

CONFIG_IEEE_SUPPORT = 0
TYPE_FLOAT = $00
TYPE_INT1  = $01
TYPE_INT2  = $02
TYPE_INT3  = $03
BASIC_INITIAL_FRE_FLOAT_0 = $84
BASIC_INITIAL_FRE_FLOAT_1 = $7A
BASIC_INITIAL_FRE_FLOAT_2 = $00
BASIC_INITIAL_FRE_FLOAT_3 = $00
BASIC_INITIAL_FRE_FLOAT_4 = $00

math_fac = zp_fac1
math_arg = zp_arg
math_input_ptr = zp_tmptr
math_output_ptr = zp_tmptr
math_coeff_ptr = zp_tmptr

.segment "BSS"
math_status:       .res 1
math_class:        .res 1
math_work:         .res 5
math_rnd_seed:     .res 2
.export math_fac_type, math_arg_type
math_fac_type:     .res 1
math_arg_type:     .res 1
temp1:             .res 5
temp2:             .res 5
temp3:             .res 5
temp4:             .res 5
temp5:             .res 5
temp6:             .res 5
poly_degree:       .res 1
sqr_rad:           .res 8
mul_mcand:         .res 8
poly_x:            .res 8
poly_ptr_save:     .res 2
fin_negative:      .res 1
fin_exp_tmp:       .res 2
fin_digit_value:   .res 1
trig_quadrant:     .res 1
trig_input_sign:   .res 1
log_exp_k:         .res 1
log_num_save:      .res 5
log_m_save:        .res 5
log_y_save:        .res 5
log_result_save:   .res 5
log_coeff_save:    .res 2
exp_input_save:    .res 5
atn_sign:          .res 1
atn_input_save:    .res 5
atn_num_save:      .res 5
reduce_value_save: .res 5
math_ieee_mode:    .res 1
math_ieee_flags:   .res 1
math_ieee_control: .res 1
math_tmp0:         .res 2
math_tmp1:         .res 2
math_tmp2:         .res 2
math_sign0:        .res 1
math_sign1:        .res 1
math_result_sign:  .res 1

ext_sign = math_work
ext_exp = math_work+4
ext_mant = temp1
ext_extra = temp4

.segment "RUNTIME"

.export math_add, math_sub, math_mul, math_div, math_negate, basic_sqr
.export basic_rnd, basic_sin, basic_cos, basic_tan, basic_atn
.export basic_log, basic_exp, basic_math_power
.export math_cmp, math_int, math_sgn, math_abs, math_fpe
.export math_int_to_float, math_float_to_int, math_u24_to_float, math_to_arg_byte
.export math_add_int, math_sub_int, math_mul_int, math_div_int

math_add:
    lda #TYPE_FLOAT
    sta math_fac_type
    sta math_arg_type
    jmp basic_math_add

math_sub:
    lda #TYPE_FLOAT
    sta math_fac_type
    sta math_arg_type
    jmp basic_math_subtract

math_mul:
    lda #TYPE_FLOAT
    sta math_fac_type
    sta math_arg_type
    jmp basic_math_multiply

math_div:
    lda #TYPE_FLOAT
    sta math_fac_type
    sta math_arg_type
    jmp basic_math_divide

math_negate:
    lda zp_fac1
    beq @done
    lda zp_fac1+1
    eor #$80
    sta zp_fac1+1
@done:
    clc
    rts

math_cmp:
    jsr basic_math_sign_compare_classify
    lda math_class
    rts

math_int:
    lda #TYPE_FLOAT
    sta math_fac_type
    lda math_fac
    beq @success
    cmp #$81
    bcs @has_integer_bit
    lda math_fac+1
    bmi @negative_between_zero_and_one
    jsr math_load_zero
    jmp @success
@negative_between_zero_and_one:
    jsr math_load_neg_one
    jmp @success
@has_integer_bit:
    cmp #$A0
    bcs @success
    ; A C64 float has 32 significand bits.  The exponent gives the number
    ; of bits left of the binary point, so $A0-exp low bits are fractional.
    sta temp1
    lda #$A0
    sec
    sbc temp1
    tax
    lda math_int_byte_index,x
    tay
    lda math_int_keep_mask,x
    sta temp1
    eor #$ff
    sta math_work
    lda #0
    sta temp1+1
    lda math_fac,y
    and math_work
    ora temp1+1
    sta temp1+1
    lda math_fac,y
    and temp1
    sta math_fac,y
    iny
@clear_lower_bytes:
    cpy #5
    beq @fraction_removed
    lda math_fac,y
    ora temp1+1
    sta temp1+1
    lda #0
    sta math_fac,y
    iny
    bne @clear_lower_bytes
@fraction_removed:
    lda temp1+1
    beq @success
    lda math_fac+1
    bpl @success
    ; INT floors, rather than truncating: a negative value with discarded
    ; fraction is the truncated value minus one.
    jsr math_copy_fac_to_arg
    jsr math_load_neg_one
    jsr basic_math_add
    rts
@success:
    clc
    rts

; Indexed by the count of low fractional significand bits (0..31).
math_int_byte_index:
    .byte 4,4,4,4,4,4,4,4,3,3,3,3,3,3,3,3
    .byte 2,2,2,2,2,2,2,2,1,1,1,1,1,1,1,1
math_int_keep_mask:
    .byte $ff,$fe,$fc,$f8,$f0,$e0,$c0,$80
    .byte $ff,$fe,$fc,$f8,$f0,$e0,$c0,$80
    .byte $ff,$fe,$fc,$f8,$f0,$e0,$c0,$80
    .byte $ff,$fe,$fc,$f8,$f0,$e0,$c0,$80

math_sgn:
    jsr math_cmp_zero_fac
    beq @zero
    bmi @neg
    jsr math_load_one
    clc
    rts
@neg:
    jsr math_load_neg_one
    clc
    rts
@zero:
    jsr math_load_zero
    clc
    rts

math_abs:
    lda zp_fac1+1
    and #$7f
    sta zp_fac1+1
    clc
    rts

math_fpe:
math_cmp_zero_fac:
    lda zp_fac1
    beq @zero
    lda zp_fac1+1
    bmi @neg
    lda #$01
    rts
@neg:
    lda #$ff
    rts
@zero:
    lda #$00
    rts

math_int_to_float:
    stx temp1
    sty temp1+1
    jmp math_temp1_int_to_fac

math_float_to_int:
    lda math_fac_type
    bne @extract
    lda math_fac+1
    and #$80
    sta math_result_sign
    jsr math_classify_fac_adaptive
    bcs @error
@extract:
    jsr math_fac_uint16
    bcs @error
    ; FLOAT narrowing is signed.  Adaptive classification also supports the
    ; unsigned INT3 value 32768, so reject a result whose two's-complement
    ; sign does not match the original packed-float sign.
    lda math_fac_type
    cmp #TYPE_INT3
    bne @return
    lda temp1+1
    eor math_result_sign
    and #$80
    bne @error
@return:
    ldx temp1
    ldy temp1+1
    clc
    rts
@error:
    sec
    rts

; math_u24_to_float - Convert one unsigned 24-bit integer to packed FAC1.
; Input: A=least significant, X=middle, Y=most significant byte.
; Output: FAC1 exact, math_fac_type=TYPE_FLOAT, C clear. Clobbers A/X/Y.
math_u24_to_float:
    sta temp1
    stx temp1+1
    sty temp1+2
    ora temp1+1
    ora temp1+2
    bne @normalize
    jsr math_load_zero
    lda #TYPE_FLOAT
    sta math_fac_type
    clc
    rts
@normalize:
    lda #$98
    sta temp1+3
@shift:
    lda temp1+2
    bmi @packed
    asl temp1
    rol temp1+1
    rol temp1+2
    dec temp1+3
    bne @shift
@packed:
    lda temp1+3
    sta math_fac
    lda temp1+2
    and #$7F
    sta math_fac+1
    lda temp1+1
    sta math_fac+2
    lda temp1
    sta math_fac+3
    lda #0
    sta math_fac+4
    lda #TYPE_FLOAT
    sta math_fac_type
    clc
    rts

; math_to_arg_byte - Convert a numeric value to the shared unsigned command
; argument-byte domain used by byte-valued language operands. This is not
; signed INT1: 128..255 are valid. Negative, fractional, greater-than-255, and
; unknown-type inputs return ERR_ILLEGAL_QUANTITY with carry set.
; Input: A=TYPE_FLOAT/TYPE_INT1/TYPE_INT2/TYPE_INT3, value in FAC1.
; Output: A=unsigned byte and C=0, or A=ERR_ILLEGAL_QUANTITY and C=1.
; Clobbers: A, X, Y. Zero page: reads FAC1; FLOAT conversion may rewrite FAC1.
math_to_arg_byte:
    sta math_class
    cmp #TYPE_FLOAT
    beq @float
    cmp #TYPE_INT1
    beq @int1
    cmp #TYPE_INT2
    beq @word
    cmp #TYPE_INT3
    bne @error
@word:
    lda math_fac+1
    bne @error
    lda math_fac
    clc
    rts
@int1:
    lda math_fac
    bmi @error
    clc
    rts
@float:
    lda #TYPE_FLOAT
    sta math_fac_type
    jsr math_float_to_int
    bcs @error
    cpy #0
    bne @error
    txa
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

math_add_int:
    jsr _load_int_record
    clc
    lda math_tmp0
    adc math_tmp1
    sta math_tmp2
    lda math_tmp0+1
    adc math_tmp1+1
    sta math_tmp2+1
    bvc :+
    jmp _int_error
:
    jmp _store_int_record

math_sub_int:
    jsr _load_int_record
    sec
    lda math_tmp0
    sbc math_tmp1
    sta math_tmp2
    lda math_tmp0+1
    sbc math_tmp1+1
    sta math_tmp2+1
    bvc :+
    jmp _int_error
:
    jmp _store_int_record

math_mul_int:
    jsr _load_int_record
    lda math_tmp0+1
    eor math_tmp1+1
    and #$80
    sta math_result_sign
    jsr _abs_tmp0
    jsr _abs_tmp1
    lda #0
    sta temp1
    sta temp1+1
    sta temp1+2
    sta temp1+3
    sta temp2
    sta temp2+1
    sta temp2+2
    sta temp2+3
    lda math_tmp0
    sta temp1
    lda math_tmp0+1
    sta temp1+1
    ldx #16
@loop:
    lsr math_tmp1+1
    ror math_tmp1
    bcc @skip
    clc
    lda temp2
    adc temp1
    sta temp2
    lda temp2+1
    adc temp1+1
    sta temp2+1
    lda temp2+2
    adc temp1+2
    sta temp2+2
    lda temp2+3
    adc temp1+3
    sta temp2+3
@skip:
    asl temp1
    rol temp1+1
    rol temp1+2
    rol temp1+3
    dex
    bne @loop
    lda temp2+2
    ora temp2+3
    beq :+
    jmp _int_error
:
    lda math_result_sign
    bne @negative
    lda temp2+1
    bpl :+
    jmp _int_error
:
    jmp @copy
@negative:
    lda temp2+1
    cmp #$80
    bcc @negate
    beq :+
    jmp _int_error
:
    lda temp2
    beq :+
    jmp _int_error
:
@negate:
    sec
    lda #0
    sbc temp2
    sta temp2
    lda #0
    sbc temp2+1
    sta temp2+1
@copy:
    lda temp2
    sta math_tmp2
    lda temp2+1
    sta math_tmp2+1
    jmp _store_int_record

math_div_int:
    jsr _load_int_record
    lda math_tmp1
    ora math_tmp1+1
    bne @nonzero
    sec
    rts
@nonzero:
    ; -32768 / -1 is the sole signed 16-bit division overflow.
    lda math_tmp0
    bne :+
    lda math_tmp0+1
    cmp #$80
    bne :+
    lda math_tmp1
    cmp #$ff
    bne :+
    lda math_tmp1+1
    cmp #$ff
    bne :+
    jmp _int_error
:
    lda math_tmp0+1
    eor math_tmp1+1
    and #$80
    sta math_result_sign
    lda math_tmp0+1
    bpl @divisor_sign
    sec
    lda #0
    sbc math_tmp0
    sta math_tmp0
    lda #0
    sbc math_tmp0+1
    sta math_tmp0+1
@divisor_sign:
    lda math_tmp1+1
    bpl @divide
    sec
    lda #0
    sbc math_tmp1
    sta math_tmp1
    lda #0
    sbc math_tmp1+1
    sta math_tmp1+1
@divide:
    lda #0
    sta math_tmp2
    sta math_tmp2+1
    sta temp1
    sta temp1+1
    ldx #16
@loop:
    asl math_tmp0
    rol math_tmp0+1
    rol temp1
    rol temp1+1
    asl math_tmp2
    rol math_tmp2+1
    lda temp1+1
    cmp math_tmp1+1
    bcc @next
    bne @sub
    lda temp1
    cmp math_tmp1
    bcc @next
@sub:
    sec
    lda temp1
    sbc math_tmp1
    sta temp1
    lda temp1+1
    sbc math_tmp1+1
    sta temp1+1
    inc math_tmp2
@next:
    dex
    bne @loop
    lda math_result_sign
    beq _store_int_record
    sec
    lda #0
    sbc math_tmp2
    sta math_tmp2
    lda #0
    sbc math_tmp2+1
    sta math_tmp2+1
    jmp _store_int_record

_abs_tmp0:
    lda math_tmp0+1
    bpl @done
    sec
    lda #0
    sbc math_tmp0
    sta math_tmp0
    lda #0
    sbc math_tmp0+1
    sta math_tmp0+1
@done:
    rts

_abs_tmp1:
    lda math_tmp1+1
    bpl @done
    sec
    lda #0
    sbc math_tmp1
    sta math_tmp1
    lda #0
    sbc math_tmp1+1
    sta math_tmp1+1
@done:
    rts

_int_error:
    sec
    rts

_load_int_record:
    stx zp_tmp1
    sty zp_tmp1+1
    ldy #0
    lda (zp_tmp1),y
    sta math_tmp0
    iny
    lda (zp_tmp1),y
    sta math_tmp0+1
    iny
    lda (zp_tmp1),y
    sta math_tmp1
    iny
    lda (zp_tmp1),y
    sta math_tmp1+1
    rts

_store_int_record:
    ldy #0
    lda math_tmp2
    sta (zp_tmp1),y
    iny
    lda math_tmp2+1
    sta (zp_tmp1),y
    clc
    rts

math_load_tenth_arg:
    ldx #0
@loop:
    lda math_const_tenth,x
    sta math_arg,x
    inx
    cpx #5
    bne @loop
    lda #TYPE_FLOAT
    sta math_arg_type
    clc
    rts

math_const_tenth:
    .byte $7D,$4C,$CC,$CC,$CD

; ---- Adapted from basic v3/basic/numeric/math_core.s ----
; Numeric backend - Phase 1: Core Arithmetic + Phase 2: SQR
; C64 5-byte float format:
;   byte 0: exponent (bias 128, $80=0, $81=1)
;   bytes 1-4: mantissa (bit 7 of byte 1 = sign, bits 6-0 = mantissa high)

.if CONFIG_IEEE_SUPPORT
.endif
.if CONFIG_IEEE_SUPPORT
.endif
.if CONFIG_IEEE_SUPPORT
.endif


; ZP-LIVE: math_fac LIVE-IN=math entrypoint primary operand
; ZP-LIVE: math_fac LIVE-OUT=math result remains in FAC on success
; ZP-LIVE: math_fac CLOBBERS=all math entrypoints that return a numeric result
; ZP-LIVE: math_fac PRESERVES=math_arg unless operation documents otherwise
; ZP-LIVE: math_arg LIVE-IN=math entrypoint secondary operand
; ZP-LIVE: math_arg LIVE-OUT=caller-owned secondary operand unless clobbered by documented helper
; ZP-LIVE: math_arg CLOBBERS=helpers that copy FAC/ARG or normalize binary operands
; ZP-LIVE: math_arg PRESERVES=math_fac input until result write
; ZP-LIVE: math_fac_type LIVE-IN=type tag is valid whenever math_fac is valid
; ZP-LIVE: math_fac_type LIVE-OUT=FAC result type tag on success
; ZP-LIVE: math_fac_type CLOBBERS=math result writers and integer fast paths
; ZP-LIVE: math_fac_type PRESERVES=math_arg_type unless operation documents otherwise
; ZP-LIVE: math_arg_type LIVE-IN=type tag is valid whenever math_arg is valid
; ZP-LIVE: math_arg_type LIVE-OUT=secondary operand type remains caller-owned unless helper clobbers ARG
; ZP-LIVE: math_arg_type CLOBBERS=helpers that copy FAC/ARG or normalize binary operands
; ZP-LIVE: math_arg_type PRESERVES=math_fac_type input until result write
; ZP-LIVE: math_status LIVE-IN=math entry initializes status when needed
; ZP-LIVE: math_status LIVE-OUT=0 success or math error status
; ZP-LIVE: math_status CLOBBERS=math_success,math_fail_current,math_fail_a
; ZP-LIVE: math_status PRESERVES=
; ZP-LIVE: math_input_ptr LIVE-IN=FIN and parser-facing numeric helpers
; ZP-LIVE: math_input_ptr LIVE-OUT=input pointer advanced by numeric parsing helpers
; ZP-LIVE: math_input_ptr CLOBBERS=basic_fin,FIN helpers,expression bridge helpers
; ZP-LIVE: math_input_ptr PRESERVES=math_output_ptr unless formatting/parsing helper documents otherwise
; ZP-LIVE: math_output_ptr LIVE-IN=FOUT and caller-provided output buffer
; ZP-LIVE: math_output_ptr LIVE-OUT=output pointer advanced by numeric formatting helpers
; ZP-LIVE: math_output_ptr CLOBBERS=basic_fout,FOUT helpers,statement copy helpers
; ZP-LIVE: math_output_ptr PRESERVES=math_input_ptr unless formatting/parsing helper documents otherwise
; ZP-LIVE: math_class LIVE-IN=classification helpers initialize result
; ZP-LIVE: math_class LIVE-OUT=0 equal/zero,1 positive or FAC greater,$ff negative or FAC less
; ZP-LIVE: math_class CLOBBERS=basic_math_classify_fac,basic_math_sign_compare_classify
; ZP-LIVE: math_class PRESERVES=
; ZP-LIVE: math_work LIVE-IN=math routines own scratch only while call is live
; ZP-LIVE: math_work LIVE-OUT=discarded before return unless used as documented extended result state
; ZP-LIVE: math_work CLOBBERS=normalization,comparison,transcendental helpers
; ZP-LIVE: math_work PRESERVES=
; ZP-LIVE: math_rnd_seed LIVE-IN=basic_rnd
; ZP-LIVE: math_rnd_seed LIVE-OUT=updated random seed remains live across calls
; ZP-LIVE: math_rnd_seed CLOBBERS=basic_rnd
; ZP-LIVE: math_rnd_seed PRESERVES=
; ZP-LIVE: math_coeff_ptr LIVE-IN=basic_math_poly_eval,basic_math_fma_from_coeff_ptr
; ZP-LIVE: math_coeff_ptr LIVE-OUT=coefficient input remains caller-owned
; ZP-LIVE: math_coeff_ptr CLOBBERS=polynomial/FMA helpers advance coefficient pointer
; ZP-LIVE: math_coeff_ptr PRESERVES=math_input_ptr


; Error codes
MATH_OK = $00
MATH_ERR_SYNTAX = $01
MATH_ERR_UNSUPPORTED = $02
MATH_ERR_DIV_ZERO = $03
MATH_ERR_DOMAIN = $04

IEEE_MODE_ENABLE = $01
IEEE_FLAG_INVALID = $01
IEEE_FLAG_DIV_ZERO = $02
IEEE_FLAG_OVERFLOW = $04
IEEE_FLAG_UNDERFLOW = $08
IEEE_FLAG_INEXACT = $10
IEEE_CLASS_NAN = $01
IEEE_CLASS_SNAN = $02
IEEE_CLASS_INF = $04
IEEE_CLASS_ZERO = $08
IEEE_CLASS_SIGN = $10
IEEE_CLASS_FINITE = $20

.macro BCS_FAR target
    bcc :+
    jmp target
:
.endmacro

.macro BEQ_FAR target
    bne :+
    jmp target
:
.endmacro

.segment "RUNTIME"

; ============================================================
; COMPATIBILITY MATRIX
; ============================================================
basic_math_compat_matrix:
    .byte "0",0,$00,$00,$00,$00,$00
    .byte "1",0,$81,$00,$00,$00,$00
    .byte "2",0,$82,$00,$00,$00,$00
    .byte "3",0,$82,$40,$00,$00,$00
    .byte "4",0,$83,$00,$00,$00,$00
    .byte "6",0,$83,$40,$00,$00,$00
    .byte "7",0,$83,$60,$00,$00,$00
    .byte "8",0,$84,$00,$00,$00,$00
    .byte "9",0,$84,$10,$00,$00,$00
    .byte "10",0,$84,$20,$00,$00,$00
    .byte "15",0,$84,$70,$00,$00,$00
    .byte "-1",0,$81,$80,$00,$00,$00
    .byte 0

; ============================================================
; PACKED LOAD/STORE
; ============================================================
basic_fac_from_packed:
    lda #TYPE_FLOAT
    sta math_fac_type
    ldy #0
fac_from_packed_loop:
    lda (math_input_ptr),y
    sta math_fac,y
    iny
    cpy #5
    bne fac_from_packed_loop
    jmp math_success

basic_fac_to_packed:
    ldy #0
fac_to_packed_loop:
    lda math_fac,y
    sta (math_output_ptr),y
    iny
    cpy #5
    bne fac_to_packed_loop
    jmp math_success

; ============================================================
; NORMALIZE AND ROUND
; ============================================================
basic_math_normalize_round:
    lda #TYPE_FLOAT
    sta math_fac_type
    lda math_fac+1
    and #$7f
    ora math_fac+2
    ora math_fac+3
    ora math_fac+4
    bne normalize_not_zero
    sta math_fac
    jmp math_success
normalize_not_zero:
    lda math_fac+1
    and #$40
    bne normalize_check_overflow
normalize_shift_left:
    lda math_fac
    beq normalize_underflow
    dec math_fac
    lda math_fac+1
    pha
    and #$80
    sta math_work
    pla
    asl
    ora math_work
    sta math_fac+1
    lda math_fac+2
    rol
    sta math_fac+2
    lda math_fac+3
    rol
    sta math_fac+3
    lda math_fac+4
    rol
    sta math_fac+4
    lda math_fac+1
    and #$40
    beq normalize_shift_left
    jmp math_success
normalize_check_overflow:
    jmp math_success
normalize_underflow:
    lda #0
    sta math_fac
    sta math_fac+1
    sta math_fac+2
    sta math_fac+3
    sta math_fac+4
    jmp math_success

; ============================================================
; SIGN, COMPARE, CLASSIFY
; ============================================================
.if CONFIG_IEEE_SUPPORT
basic_math_classify_fac:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    sta math_class
    jmp math_success

.if CONFIG_IEEE_SUPPORT
basic_math_classify_arg:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_arg_to_a
.endif
    sta math_class
    jmp math_success
.endif

.if CONFIG_IEEE_SUPPORT
basic_math_is_nan_fac:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    and #IEEE_CLASS_NAN
    jmp ieee_return_bool_a
.endif

.if CONFIG_IEEE_SUPPORT
basic_math_is_snan_fac:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    and #IEEE_CLASS_SNAN
    jmp ieee_return_bool_a
.endif

.if CONFIG_IEEE_SUPPORT
basic_math_is_inf_fac:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    and #IEEE_CLASS_INF
    jmp ieee_return_bool_a
.endif

.if CONFIG_IEEE_SUPPORT
basic_math_is_fin_fac:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    and #IEEE_CLASS_FINITE
    jmp ieee_return_bool_a
.endif

.if CONFIG_IEEE_SUPPORT
basic_math_is_norm_fac:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    and #IEEE_CLASS_FINITE
    beq @false
    lda math_fac
    beq @false
    lda #1
    jmp ieee_return_bool_a
.endif
@false:
    lda #0
    jmp ieee_return_bool_a

.if CONFIG_IEEE_SUPPORT
basic_math_is_zero_fac:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    and #IEEE_CLASS_ZERO
    jmp ieee_return_bool_a
.endif

.if CONFIG_IEEE_SUPPORT
basic_math_sgn_bit_fac:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    and #IEEE_CLASS_SIGN
    jmp ieee_return_bool_a
.endif

.if CONFIG_IEEE_SUPPORT
basic_math_is_unord:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    and #IEEE_CLASS_NAN
    bne @true
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_arg_to_a
.endif
    and #IEEE_CLASS_NAN
    bne @true
    lda #0
    jmp ieee_return_bool_a
.endif
@true:
    lda #1
    jmp ieee_return_bool_a

.endif

basic_math_quiet_nan_fac:
    lda math_fac
    cmp #$ff
    bne @done
    lda math_fac+1
    and #$7f
    ora math_fac+2
    ora math_fac+3
    ora math_fac+4
    beq @done
    lda math_fac+1
    ora #$40
    sta math_fac+1
    lda #IEEE_FLAG_INVALID
.if CONFIG_IEEE_SUPPORT
    jsr ieee_raise_flags_a
.endif
@done:
    jmp math_success

.if CONFIG_IEEE_SUPPORT
basic_math_copy_sign_arg_to_fac:
    lda math_arg+1
    and #$80
    sta temp1
    lda math_fac+1
    and #$7f
    ora temp1
    sta math_fac+1
    jmp math_success
.endif

.if CONFIG_IEEE_SUPPORT
basic_math_total_order:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    and #IEEE_CLASS_NAN
    bne @nan_path
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_arg_to_a
.endif
    and #IEEE_CLASS_NAN
    bne @fac_before_nan
    jmp basic_math_sign_compare_classify
.endif
@nan_path:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_arg_to_a
.endif
    and #IEEE_CLASS_NAN
    beq @nan_after_finite
    lda math_fac+1
    cmp math_arg+1
    bne @byte_diff
    lda math_fac+2
    cmp math_arg+2
    bne @byte_diff
    lda math_fac+3
    cmp math_arg+3
    bne @byte_diff
    lda math_fac+4
    cmp math_arg+4
    bne @byte_diff
    lda #0
    sta math_class
    jmp math_success
@byte_diff:
    bcc @less
    lda #1
    sta math_class
    jmp math_success
@less:
    lda #$ff
    sta math_class
    jmp math_success
@nan_after_finite:
    lda #1
    sta math_class
    jmp math_success
@fac_before_nan:
    lda #$ff
    sta math_class
    jmp math_success

.if CONFIG_IEEE_SUPPORT
basic_math_min:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    sta temp1
    and #IEEE_CLASS_NAN
    bne @nan_fac
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_arg_to_a
.endif
    sta temp2
    and #IEEE_CLASS_NAN
    bne @nan_arg
    lda temp1
    and #IEEE_CLASS_ZERO
    beq @compare
    lda temp2
    and #IEEE_CLASS_ZERO
    beq @compare
    lda math_fac+1
    ora math_arg+1
    and #$80
    sta temp3
    lda math_fac+1
    and #$7f
    ora temp3
    sta math_fac+1
    jmp math_success
@compare:
    jsr basic_math_sign_compare_classify
    lda math_class
    bmi @keep_fac
    beq @keep_fac
    jmp math_copy_arg_to_fac_success
@keep_fac:
    jmp math_success
@nan_fac:
    jsr basic_math_quiet_nan_fac
    jmp math_success
@nan_arg:
    jsr math_copy_arg_to_fac
    lda math_arg_type
    sta math_fac_type
    jsr basic_math_quiet_nan_fac
    jmp math_success

basic_math_max:
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    sta temp1
    and #IEEE_CLASS_NAN
    bne @nan_fac
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_arg_to_a
.endif
    sta temp2
    and #IEEE_CLASS_NAN
    bne @nan_arg
    lda temp1
    and #IEEE_CLASS_ZERO
    beq @compare
    lda temp2
    and #IEEE_CLASS_ZERO
    beq @compare
    lda math_fac+1
    and math_arg+1
    and #$80
    sta temp3
    lda math_fac+1
    and #$7f
    ora temp3
    sta math_fac+1
    jmp math_success
@compare:
    jsr basic_math_sign_compare_classify
    lda math_class
    bmi @use_arg
    jmp math_success
@use_arg:
    jmp math_copy_arg_to_fac_success
@nan_fac:
    jsr basic_math_quiet_nan_fac
    jmp math_success
@nan_arg:
    jsr math_copy_arg_to_fac
    lda math_arg_type
    sta math_fac_type
    jsr basic_math_quiet_nan_fac
    jmp math_success

.endif

basic_math_sign_compare_classify:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode

    and #IEEE_MODE_ENABLE
    beq @legacy
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_fac_to_a
.endif
    and #IEEE_CLASS_NAN
    bne compare_unordered_ieee
.if CONFIG_IEEE_SUPPORT
    jsr ieee_classify_arg_to_a
.endif
    and #IEEE_CLASS_NAN
    bne compare_unordered_ieee
.endif
@legacy:
    jsr math_try_integer_compare
    bcs :+
    jmp compare_integer_done
:
    jsr math_adaptive_fac_arg_to_float
    lda math_arg
    bne :+
    jmp classify_only
:
    lda #0
    sta math_compare_reverse
    lda math_fac
    beq compare_fac_zero_arg_nonzero
    lda math_arg
    bne :+
    jmp classify_only
:
    lda math_fac+1
    eor math_arg+1
    bmi compare_sign_diff
    lda math_fac+1
    bpl @same_sign_positive
    lda #1
    sta math_compare_reverse
@same_sign_positive:
    lda math_fac
    cmp math_arg
    bne compare_exp_diff
    ldx #4
compare_mantissa_loop:
    lda math_fac,x
    cmp math_arg,x
    bne compare_mantissa_diff
    dex
    cpx #0
    bne compare_mantissa_loop
    lda #0
    sta math_class
    jmp math_success
compare_exp_diff:
    bcc compare_fac_less
    lda math_compare_reverse
    bne compare_fac_less_no_reverse
    lda #1
    sta math_class
    jmp math_success
compare_fac_less:
    lda math_compare_reverse
    bne compare_fac_greater_reversed
compare_fac_less_no_reverse:
    lda #$ff
    sta math_class
    jmp math_success
compare_unordered_ieee:
    lda #IEEE_FLAG_INVALID
.if CONFIG_IEEE_SUPPORT
    jsr ieee_raise_flags_a
.endif
    lda #$80
    sta math_class
    jmp math_success
compare_fac_greater_reversed:
    lda #1
    sta math_class
    jmp math_success
compare_mantissa_diff:
    bcc compare_fac_less_m
    lda math_compare_reverse
    bne compare_fac_less_no_reverse
    lda #1
    sta math_class
    jmp math_success
compare_fac_less_m:
    lda math_compare_reverse
    bne compare_fac_greater_reversed
    lda #$ff
    sta math_class
    jmp math_success
compare_fac_zero_arg_nonzero:
    lda math_arg+1
    bmi compare_fac_greater_reversed
    jmp compare_fac_less
compare_sign_diff:
    lda math_fac+1
    bmi compare_fac_less
    lda #1
    sta math_class
    jmp math_success
classify_only:
    lda math_fac
    beq classify_zero
    lda math_fac+1
    bmi classify_neg
    lda #1
    sta math_class
    jmp math_success
classify_zero:
    lda #0
    sta math_class
    jmp math_success
classify_neg:
    lda #$ff
    sta math_class
    jmp math_success
compare_integer_done:
    rts

math_compare_reverse:
    .byte 0

; ============================================================
; INTEGER CONVERSION
; ============================================================
basic_int_to_fac:
    lda #TYPE_FLOAT
    sta math_fac_type
    ldy #0
    lda (math_input_ptr),y
    beq int_to_fac_zero
    cmp #16
    bcs int_to_fac_generic
    jsr math_load_code
    BCS_FAR math_unsupported
    jmp math_success
int_to_fac_generic:
    sta ext_mant+3
    lda #0
    sta ext_mant
    sta ext_mant+1
    sta ext_mant+2
    sta ext_extra
    sta ext_extra+1
    sta ext_extra+2
    sta ext_extra+3
    sta ext_sign
    sta fin_negative
    lda #$A0
    sta ext_exp
    jsr math_finalize_extended_to_fac
    rts
int_to_fac_zero:
    jsr math_load_zero
    jmp math_success

; ============================================================
; ADAPTIVE INTEGER HELPERS
; ============================================================
; Carry clear means the integer operation completed in FAC.
; Carry set means temp1/temp2 still hold the original signed 16-bit operands
; and the caller should fall back through the float implementation.
math_try_integer_add:
    jsr math_load_integer_operands_to_temp12
    bcs @fallback
    clc
    lda temp1
    adc temp2
    sta temp3
    lda temp1+1
    adc temp2+1
    sta temp3+1
    lda temp1+1
    eor temp2+1
    bmi @no_overflow
    lda temp1+1
    eor temp3+1
    bmi @fallback
@no_overflow:
    jsr math_pack_temp3_integer_to_fac
    jmp math_success
@fallback:
    sec
    rts

math_try_integer_subtract:
    jsr math_load_integer_operands_to_temp12
    bcs @fallback
    sec
    lda temp1
    sbc temp2
    sta temp3
    lda temp1+1
    sbc temp2+1
    sta temp3+1
    lda temp1+1
    eor temp2+1
    bpl @no_overflow
    lda temp1+1
    eor temp3+1
    bmi @fallback
@no_overflow:
    jsr math_pack_temp3_integer_to_fac
    jmp math_success
@fallback:
    sec
    rts

math_try_integer_multiply:
    jsr math_load_integer_operands_to_temp12
    bcs @fallback
    lda #0
    sta temp3
    sta temp3+1
    sta temp4
    jsr math_abs_temp1
    bcs @fallback
    jsr math_abs_temp2
    bcs @fallback
    ldx #16
@loop:
    lsr temp2+1
    ror temp2
    bcc @no_add
    clc
    lda temp3
    adc temp1
    sta temp3
    lda temp3+1
    adc temp1+1
    sta temp3+1
    bcs @fallback
@no_add:
    asl temp1
    rol temp1+1
    bcc @shift_ok
    lda temp2
    ora temp2+1
    bne @fallback
@shift_ok:
    dex
    bne @loop
    lda temp4
    beq @positive
    lda temp3
    eor #$ff
    clc
    adc #1
    sta temp3
    lda temp3+1
    eor #$ff
    adc #0
    sta temp3+1
    bmi @pack
    jmp @fallback
@positive:
    lda temp3+1
    bmi @fallback
@pack:
    jsr math_pack_temp3_integer_to_fac
    jmp math_success
@fallback:
    sec
    rts

math_try_integer_divide_exact:
    jsr math_load_integer_operands_to_temp12
    bcs @fallback
    lda #0
    sta temp4
    jsr math_abs_temp1
    bcs @fallback
    jsr math_abs_temp2
    bcs @fallback
    lda temp2
    beq @fallback
    lda temp2+1
    bne @fallback
    lda temp2
    cmp #129
    bcs @fallback
    lda #0
    sta temp3
    sta temp3+1
    sta temp5
    ldx #16
@loop:
    asl temp1
    rol temp1+1
    rol temp5
    asl temp3
    rol temp3+1
    lda temp5
    cmp temp2
    bcc @next
    sbc temp2
    sta temp5
    inc temp3
@next:
    dex
    bne @loop
    lda temp5
    bne @fallback
    lda temp4
    beq @positive
    lda temp3
    eor #$ff
    clc
    adc #1
    sta temp3
    lda temp3+1
    eor #$ff
    adc #0
    sta temp3+1
    jmp @pack
@positive:
    lda temp3+1
    bmi @fallback
@pack:
    jsr math_pack_temp3_integer_to_fac
    jmp math_success
@fallback:
    sec
    rts

math_try_integer_compare:
    jsr math_load_integer_operands_to_temp12
    bcs @fallback
    ; INT3 is unsigned.  A negative signed operand always sorts below an
    ; unsigned operand; otherwise compare both normalized words unsigned.
    lda math_fac_type
    cmp #TYPE_INT3
    beq @fac_unsigned
    lda math_arg_type
    cmp #TYPE_INT3
    beq @arg_unsigned
    jmp @signed_compare
@fac_unsigned:
    lda math_arg_type
    cmp #TYPE_INT3
    beq @unsigned_compare
    lda temp2+1
    bmi @greater
    bpl @unsigned_compare
@arg_unsigned:
    lda temp1+1
    bmi @less
@unsigned_compare:
    lda temp1+1
    cmp temp2+1
    bne @unsigned_diff
    lda temp1
    cmp temp2
    bne @unsigned_diff
    beq @equal
@signed_compare:
    lda temp1+1
    eor temp2+1
    bmi @sign_diff
    lda temp1+1
    cmp temp2+1
    bne @unsigned_diff
    lda temp1
    cmp temp2
    bne @unsigned_diff
@equal:
    lda #0
    sta math_class
    jmp math_success
@unsigned_diff:
    bcc @less
    lda #1
    sta math_class
    jmp math_success
@sign_diff:
    lda temp1+1
    bmi @less
@greater:
    lda #1
    sta math_class
    jmp math_success
@less:
    lda #$ff
    sta math_class
    jmp math_success
@fallback:
    sec
    rts

math_operands_are_integer:
    lda math_fac_type
    cmp #TYPE_INT1
    beq @check_arg
    cmp #TYPE_INT2
    beq @check_arg
    cmp #TYPE_INT3
    bne @no
@check_arg:
    lda math_arg_type
    cmp #TYPE_INT1
    beq @yes
    cmp #TYPE_INT2
    beq @yes
    cmp #TYPE_INT3
    beq @yes
@no:
    sec
    rts
@yes:
    clc
    rts

math_load_integer_operands_to_temp12:
    lda math_fac_type
    cmp #TYPE_INT1
    beq @fac_int1
    cmp #TYPE_INT2
    beq @fac_wide
    cmp #TYPE_INT3
    bne @fallback
@fac_wide:
    lda math_fac
    sta temp1
    lda math_fac+1
    sta temp1+1
    jmp @arg
@fac_int1:
    lda math_fac
    sta temp1
    bpl :+
    lda #$ff
    jmp :++
:
    lda #0
:
    sta temp1+1
@arg:
    lda math_arg_type
    cmp #TYPE_INT1
    beq @arg_int1
    cmp #TYPE_INT2
    beq @arg_wide
    cmp #TYPE_INT3
    bne @fallback
@arg_wide:
    lda math_arg
    sta temp2
    lda math_arg+1
    sta temp2+1
    clc
    rts
@arg_int1:
    lda math_arg
    sta temp2
    bpl :+
    lda #$ff
    jmp :++
:
    lda #0
:
    sta temp2+1
    clc
    rts
@fallback:
    sec
    rts

math_pack_temp3_integer_to_fac:
    lda temp3+1
    beq @maybe_pos_int1
    cmp #$ff
    beq @maybe_neg_int1
    ; Check if bit 15 is set (32768-65535)
    bit temp3+1
    bpl @int2
@int3:
    lda #TYPE_INT3
    sta math_fac_type
    lda temp3
    sta math_fac
    lda temp3+1
    sta math_fac+1
    jmp math_clear_fac_tail
@int2:
    lda #TYPE_INT2
    sta math_fac_type
    lda temp3
    sta math_fac
    lda temp3+1
    sta math_fac+1
    jmp math_clear_fac_tail
@maybe_pos_int1:
    lda temp3
    bpl @int1
    jmp @int2
@maybe_neg_int1:
    lda temp3
    bmi @int1
    jmp @int2
@int1:
    lda #TYPE_INT1
    sta math_fac_type
    lda temp3
    sta math_fac
    lda #0
    sta math_fac+1
    jmp math_clear_fac_tail
math_abs_temp1:
    lda temp1+1
    bpl @done
    lda temp4
    eor #$80
    sta temp4
    lda temp1
    eor #$ff
    clc
    adc #1
    sta temp1
    lda temp1+1
    eor #$ff
    adc #0
    sta temp1+1
    lda temp1+1
    bmi @overflow
@done:
    clc
    rts
@overflow:
    sec
    rts

math_abs_temp2:
    lda temp2+1
    bpl @done
    lda temp4
    eor #$80
    sta temp4
    lda temp2
    eor #$ff
    clc
    adc #1
    sta temp2
    lda temp2+1
    eor #$ff
    adc #0
    sta temp2+1
    lda temp2+1
    bmi @overflow
@done:
    clc
    rts
@overflow:
    sec
    rts

math_restore_temp12_int_to_fac_arg:
    jsr math_temp1_int_to_fac_fast
    ldx #0
@save_left:
    lda math_fac,x
    sta temp3,x
    inx
    cpx #5
    bne @save_left
    lda temp2
    sta temp1
    lda temp2+1
    sta temp1+1
    jsr math_temp1_int_to_fac_fast
    jsr math_copy_fac_to_arg
    ldx #0
@restore_left:
    lda temp3,x
    sta math_fac,x
    inx
    cpx #5
    bne @restore_left
    lda #TYPE_FLOAT
    sta math_fac_type
    sta math_arg_type
    rts

math_temp1_int_to_fac:
    lda temp1+1
    and #$80
    sta ext_sign
    lda temp1
    sta ext_mant+3
    lda temp1+1
    sta ext_mant+2
    lda #0
    sta ext_mant
    sta ext_mant+1
    sta ext_extra
    sta ext_extra+1
    sta ext_extra+2
    sta ext_extra+3
    lda ext_sign
    beq math_temp1_int_to_fac_positive
    lda ext_mant+3
    eor #$ff
    clc
    adc #1
    sta ext_mant+3
    lda ext_mant+2
    eor #$ff
    adc #0
    sta ext_mant+2
math_temp1_int_to_fac_positive:
    lda ext_mant+2
    ora ext_mant+3
    beq math_temp1_int_to_fac_zero
    lda #$A0
    sta ext_exp
    jsr math_finalize_extended_to_fac
    lda #TYPE_FLOAT
    sta math_fac_type
    rts

math_temp1_uint_to_fac:
    lda temp1
    sta ext_mant+3
    lda temp1+1
    sta ext_mant+2
    lda #0
    sta ext_sign
    sta ext_mant
    sta ext_mant+1
    sta ext_extra
    sta ext_extra+1
    sta ext_extra+2
    sta ext_extra+3
    jmp math_temp1_int_to_fac_positive

math_temp1_int_to_fac_fast:
    lda temp1+1
    beq @maybe_small_positive
    cmp #$ff
    bne @generic
    lda temp1
    cmp #$ff
    bne @generic
    jsr math_load_neg_one
    lda #TYPE_FLOAT
    sta math_fac_type
    rts
@maybe_small_positive:
    lda temp1
    cmp #16
    bcs @generic
    jsr math_load_code
    lda #TYPE_FLOAT
    sta math_fac_type
    rts
@generic:
    jmp math_temp1_int_to_fac
math_temp1_int_to_fac_zero:
    jsr math_load_zero
    lda #TYPE_FLOAT
    sta math_fac_type
    rts



; ---- Adapted from basic v3/basic/numeric/math_add_sub.s ----
; ============================================================
; ARITHMETIC: ADDITION
; ============================================================
basic_math_add:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @legacy
    jsr ieee_add_sub_special
    bcc @legacy
    rts
.endif
@legacy:
    jsr math_operands_are_integer
    bcs add_float_path
    jsr math_try_integer_add
    bcs :+
    jmp add_integer_done
:
    jsr math_restore_temp12_int_to_fac_arg
add_float_path:
    jsr math_adaptive_fac_arg_to_float
    lda #TYPE_FLOAT
    sta math_fac_type
    lda math_fac
    BEQ_FAR add_result_is_arg
    lda math_arg
    BEQ_FAR add_result_is_fac
    jsr math_copy_fac_arg_to_temp12
    jsr math_compare_temp_magnitudes
    bcs add_fac_larger
    jsr math_swap_temp1_temp2
add_fac_larger:
    lda temp1
    sec
    sbc temp2
    tay
    lda temp1+1
    and #$80
    sta ext_sign
    jsr math_load_temp1_to_sqr_rad64
    jsr math_load_temp2_to_mul_mcand64
    tya
    beq add_aligned
    cpy #64
    bcc add_shift_smaller
    jsr fma_zero_addend_with_sticky
    jmp add_aligned
add_shift_smaller:
    jsr fma_shift_addend_right_y_jam
add_aligned:
    lda temp1+1
    eor temp2+1
    and #$80
    beq add_same_sign
    jsr fma_compare_ext_addend
    beq add_cancel_to_zero
    bcc add_subtract_larger_from_smaller
    jsr fma_subtract_addend_from_ext
    jmp add_commit
add_subtract_larger_from_smaller:
    jsr fma_subtract_ext_from_addend
    lda temp2+1
    and #$80
    sta ext_sign
    jmp add_commit_from_addend
add_same_sign:
    jsr fma_add_addend_to_ext
    bcc add_commit
    jsr fma_shift_ext_right_one_with_carry_jam
    inc temp1
    beq add_overflow
add_commit:
    lda temp1
    sta ext_exp
    jsr math_copy_sqr_rad_to_ext
    jsr math_finalize_extended_to_fac
    BCS_FAR math_unsupported
    jmp math_success
add_commit_from_addend:
    lda temp1
    sta ext_exp
    jsr math_copy_mul_mcand_to_ext
    jsr math_finalize_extended_to_fac
    BCS_FAR math_unsupported
    jmp math_success
add_cancel_to_zero:
    jsr math_load_zero
    jmp math_success
add_overflow:
    jmp math_unsupported
add_result_is_arg:
    jsr math_copy_arg_to_fac
    jmp math_success
add_result_is_fac:
    jmp math_success
add_integer_done:
    rts

math_swap_temp1_temp2:
    ldx #0
swap_loop:
    lda temp1,x
    pha
    lda temp2,x
    sta temp1,x
    pla
    sta temp2,x
    inx
    cpx #5
    bne swap_loop
    rts

shift_right_y_bits:
    cpy #0
    beq shift_done
shift_loop:
    lda temp2+1
    and #$80
    sta math_work
    lda temp2+1
    lsr
    ora math_work
    sta temp2+1
    lda temp2+2
    ror
    sta temp2+2
    lda temp2+3
    ror
    sta temp2+3
    lda temp2+4
    ror
    sta temp2+4
    dey
    bne shift_loop
shift_done:
    rts

add_mantissas_same_sign:
    lda temp1+4
    clc
    adc temp2+4
    sta temp1+4
    lda temp1+3
    adc temp2+3
    sta temp1+3
    lda temp1+2
    adc temp2+2
    sta temp1+2
    lda temp1+1
    adc temp2+1
    sta temp1+1
    bcc add_no_overflow
    lda temp1+1
    pha
    and #$80
    sta math_work
    pla
    lsr
    ora math_work
    sta temp1+1
    lda temp1+2
    ror
    sta temp1+2
    lda temp1+3
    ror
    sta temp1+3
    lda temp1+4
    ror
    sta temp1+4
    inc temp1
add_no_overflow:
    rts

; ============================================================
; ARITHMETIC: SUBTRACTION
; ============================================================
basic_math_subtract:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @legacy
    lda math_arg+1
    eor #$80
    sta math_arg+1
    jsr ieee_add_sub_special
    php
    lda math_arg+1
    eor #$80
    sta math_arg+1
    plp
    bcc @legacy
    rts
.endif
@legacy:
    jsr math_operands_are_integer
    bcs subtract_float_path
    jsr math_try_integer_subtract
    bcc subtract_integer_done
    jsr math_restore_temp12_int_to_fac_arg
subtract_float_path:
    jsr math_adaptive_fac_arg_to_float
    lda math_arg
    beq subtract_result_is_fac
    lda math_arg+1
    eor #$80
    sta math_arg+1
    jmp basic_math_add
subtract_result_is_fac:
    jmp math_success
subtract_integer_done:
    rts



; ---- Adapted from basic v3/basic/numeric/math_mul_div.s ----
; ============================================================
; ARITHMETIC: MULTIPLICATION
; ============================================================
basic_math_multiply:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @legacy
    jsr ieee_multiply_special
    bcc @legacy
    rts
.endif
@legacy:
    jsr math_operands_are_integer
    bcs multiply_float_path
    jsr math_try_integer_multiply
    bcc multiply_integer_done
    jsr math_restore_temp12_int_to_fac_arg
multiply_float_path:
    jsr math_adaptive_fac_arg_to_float
    lda #TYPE_FLOAT
    sta math_fac_type
    jmp basic_math_multiply_impl
multiply_integer_done:
    rts
mul_zero_result:
    jsr math_load_zero
    jmp math_success

basic_math_square:
    jsr math_adaptive_fac_to_float
    lda #TYPE_FLOAT
    sta math_fac_type
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @legacy
    jsr ieee_square_special
    bcc @legacy
    rts
.endif
@legacy:
    jsr math_square_to_ext
    BCS_FAR math_fail_a
    jsr math_finalize_extended_to_fac
    BCS_FAR math_unsupported
    jmp math_success

basic_math_power:
    lda math_arg_type
    cmp #TYPE_INT1
    BEQ_FAR power_integer
    cmp #TYPE_INT2
    BEQ_FAR power_integer
    jsr power_try_half_integer_arg
    bcc power_half_integer
    jsr power_try_float_integer_arg
    bcs :+
    jmp power_integer
:
    jsr power_try_pow2_base
    bcs :+
    jmp power_pow2
:
    jmp power_general

power_half:
    jmp basic_sqr
power_half_integer:
    jsr power_save_fac_base
    jsr power_integer
    BCS_FAR math_fail_current
    jsr math_adaptive_fac_to_float
    jsr power_save_fac_result
    jsr power_restore_base_fac
    jsr basic_sqr
    BCS_FAR math_fail_current
    lda power_exp_save+1
    and #$80
    beq :+
    lda power_half_int_part
    bne :+
    jmp power_recip_base
:
    jsr power_save_fac_sqrt
    jsr power_restore_result_fac
    jsr math_copy_fac_to_arg
    jsr power_restore_sqrt_fac
    jsr basic_math_multiply
    BCS_FAR math_fail_current
    lda power_exp_save+1
    and #$80
    beq :+
    jmp power_recip_base
:
    jmp math_success
power_pow2:
    jsr power_pow2_exp_arg
    BCS_FAR math_fail_current
    jmp basic_exp

power_general:
    jsr power_save_arg_exp
    jsr basic_log
    BCS_FAR math_fail_current
    jsr power_restore_exp_arg
    jsr basic_math_multiply
    BCS_FAR math_fail_current
    jmp basic_exp

power_integer:
    jsr power_load_integer_exponent
    BCS_FAR math_unsupported
    lda power_exp_lo
    ora power_exp_hi
    bne :+
    lda #1
    sta math_fac
    jmp math_set_fac_a_int1_success
:
    jsr power_try_int1_two_pow_small
    bcs :+
    rts
:
    lda power_exp_hi
    bne power_integer_general
    lda power_exp_lo
    cmp #1
    bne power_check_square_exp
    lda power_exp_negative
    bne power_integer_recip_base
    jmp power_return_base
power_integer_recip_base:
    jmp power_recip_base
power_check_square_exp:
    cmp #2
    bne power_integer_general
    lda power_exp_negative
    bne power_integer_general
    jmp power_square_base
power_integer_general:
    jsr math_adaptive_fac_to_float
    jsr power_save_fac_base
    jsr math_load_one
    lda #TYPE_FLOAT
    sta math_fac_type
    jsr power_save_fac_result
power_integer_loop:
    lda power_exp_lo
    and #1
    beq power_skip_multiply
    jsr power_restore_result_fac
    jsr power_load_base_arg
    jsr basic_math_multiply
    BCS_FAR math_fail_current
    jsr power_save_fac_result
power_skip_multiply:
    jsr power_shift_exp_right
    lda power_exp_lo
    ora power_exp_hi
    beq power_integer_done
    jsr power_restore_base_fac
    jsr basic_math_square
    BCS_FAR math_fail_current
    jsr power_save_fac_base
    jmp power_integer_loop
power_integer_done:
    jsr power_restore_result_fac
    lda power_exp_negative
    beq :+
    jmp power_recip_base
:
    jmp math_success

.segment "RUNTIME"

power_try_int1_two_pow_small:
    lda power_exp_negative
    bne @no
    lda power_exp_hi
    bne @no
    lda power_exp_lo
    cmp #16
    bcs @no
    lda math_fac_type
    cmp #TYPE_INT1
    bne @no
    lda math_fac
    cmp #2
    bne @no
    ldx power_exp_lo
    lda power_pow2_int1_table,x
    sta math_fac
    lda power_pow2_int1_table_hi,x
    sta math_fac+1
    sta math_fac+2
    sta math_fac+3
    sta math_fac+4
    cpx #7
    bcc @int1
    lda #TYPE_INT2
    sta math_fac_type
    clc
    rts
@int1:
    lda #TYPE_INT1
    sta math_fac_type
    clc
    rts
@no:
    sec
    rts

power_pow2_int1_table:
    .byte 1,2,4,8,16,32,64,128
    .byte 0,0,0,0,0,0,0,0
power_pow2_int1_table_hi:
    .byte 0,0,0,0,0,0,0,0
    .byte 1,2,4,8,16,32,64,128

.segment "RUNTIME"

power_return_base:
    jsr power_pack_fac_code_to_int
    jmp math_success
power_square_base:
    jsr basic_math_square
    BCS_FAR math_fail_current
    jsr power_pack_fac_code_to_int
    jmp math_success
power_recip_base:
    jsr math_copy_fac_to_arg
    jsr math_load_one
    lda #TYPE_FLOAT
    sta math_fac_type
    jsr basic_math_divide
    BCS_FAR math_fail_current
    jmp math_success

; ============================================================
; ARITHMETIC: DIVISION
; ============================================================
basic_math_divide:
    jsr math_try_integer_divide_exact
    bcs @float_path
    rts
@float_path:
    jsr math_adaptive_fac_arg_to_float
    lda #TYPE_FLOAT
    sta math_fac_type
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @legacy
    jsr ieee_divide_special
    bcc @legacy
    rts
.endif
@legacy:
    lda math_arg
    BEQ_FAR div_zero_error
    lda math_fac
    BEQ_FAR div_zero_result
    jsr math_copy_fac_arg_to_temp12
    lda temp1+1
    eor temp2+1
    and #$80
    sta ext_sign
    lda temp1
    sec
    sbc temp2
    sta ext_exp
    lda #0
    sbc #0
    sta temp3
    lda ext_exp
    clc
    adc #$81
    sta ext_exp
    lda temp3
    adc #0
    beq div_exp_ready
    cmp #$ff
    beq div_underflow
    jmp math_unsupported
div_underflow:
    jsr math_load_zero
    jmp math_success
div_exp_ready:
    jsr math_prepare_div_operands
    jsr math_divide_to_ext
    BCS_FAR math_unsupported
    jsr math_finalize_extended_to_fac
    BCS_FAR math_unsupported
    jmp math_success
div_zero_error:
    lda #MATH_ERR_DIV_ZERO
    jmp math_fail_a
div_zero_result:
    jsr math_load_zero
    jmp math_success



; ---- Adapted from basic v3/basic/numeric/math_transcendental.s ----
; ============================================================
; TRANSCENDENTALS (Phase 2: SQR, Phase 3: LOG/EXP, Phase 4: SIN/COS/TAN)
; ============================================================
basic_sqr:
    lda math_fac_type
    cmp #TYPE_INT1
    bne @convert
    jsr math_sqr_int1_ladder
    bcs @convert
    rts
@convert:
    jsr math_adaptive_fac_to_float
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @legacy
    jsr ieee_sqr_special
    bcc @legacy
    rts
.endif
@legacy:
    lda math_fac+1
    bmi sqr_domain_error
    lda math_fac
    beq sqr_zero_result
    jmp basic_sqr_impl
sqr_zero_result:
    jsr math_load_zero
    jmp math_success
sqr_domain_error:
    lda #MATH_ERR_DOMAIN
    jmp math_fail_a

.segment "RUNTIME"

math_sqr_int1_ladder:
    lda math_fac
    bmi @float
    ldx #0
@loop:
    cmp sqr_int1_square_table,x
    beq @found
    inx
    cpx #12
    bne @loop
@float:
    sec
    rts
@found:
    txa
    sta math_fac
    jmp math_set_fac_a_int1_success

sqr_int1_square_table:
    .byte 0,1,4,9,16,25,36,49,64,81,100,121

.segment "RUNTIME"

basic_rnd:
    inc math_rnd_seed
    bne rnd_loaded
    inc math_rnd_seed+1
rnd_loaded:
    jsr math_load_one
    jmp math_success

basic_sin:
    jsr math_adaptive_fac_to_float
    lda math_fac
    BEQ_FAR sin_zero
    jsr trig_reduce_to_kernel
    BCS_FAR math_fail_current
    lda math_fac
    beq sin_axis
    lda trig_quadrant
    and #3
    beq sin_kernel
    cmp #1
    beq sin_use_cos
    cmp #2
    beq sin_use_neg_sin
    jmp sin_use_neg_cos
sin_kernel:
    lda #<coeff_sin_remez7_u
    sta math_coeff_ptr
    lda #>coeff_sin_remez7_u
    sta math_coeff_ptr+1
    jsr basic_math_poly_eval_odd
    BCS_FAR math_fail_current
    jmp math_success
sin_use_cos:
    jsr trig_eval_cos_kernel
    BCS_FAR math_fail_current
    jmp math_success
sin_use_neg_sin:
    jsr trig_eval_sin_kernel
    BCS_FAR math_fail_current
    jsr trig_negate_fac
    jmp math_success
sin_use_neg_cos:
    jsr trig_eval_cos_kernel
    BCS_FAR math_fail_current
    jsr trig_negate_fac
    jmp math_success
sin_zero:
    jsr math_load_zero
    jmp math_success
sin_axis:
    lda trig_quadrant
    and #3
    beq sin_zero
    cmp #2
    beq sin_axis_pi
    cmp #1
    beq sin_axis_one
    jsr math_load_neg_one
    jmp math_success
sin_axis_one:
    jsr math_load_one
    jmp math_success
sin_axis_pi:
    jsr trig_load_pi_resid_fac
    lda trig_input_sign
    beq :+
    jsr trig_negate_fac
:
    jmp math_success

basic_log:
    jsr math_adaptive_fac_to_float
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @legacy
    jsr ieee_log_special
    bcc @legacy
    rts
.endif
@legacy:
    lda math_fac
    BEQ_FAR log_domain_error
    lda math_fac+1
    bpl :+
    jmp log_domain_error
:
    jsr log_normalize_mantissa
    BCS_FAR log_domain_error
    jsr log_compute_y
    BCS_FAR log_domain_error
    jmp log_general_path
log_general_path:
    jsr log_compute_z
    BCS_FAR log_domain_error
    jsr log_evaluate_atanh
    BCS_FAR log_domain_error
    jmp log_reconstruct
log_domain_error:
    lda #MATH_ERR_DOMAIN
    jmp math_fail_a

log_normalize_mantissa:
    jsr math_copy_fac_to_temp1
    lda temp1
    sec
    sbc #$81
    sta log_exp_k
    lda #$81
    sta math_fac
    lda #<const_sqrt_two
    sta log_coeff_save
    lda #>const_sqrt_two
    sta log_coeff_save+1
    jsr log_abs_fac_le_saved_const
    bcc @save_m
    dec math_fac
    inc log_exp_k
@save_m:
    ldx #0
@copy_m:
    lda math_fac,x
    sta log_m_save,x
    inx
    cpx #5
    bne @copy_m
    lda #TYPE_FLOAT
    sta math_fac_type
    clc
    rts

log_compute_y:
    jsr atn_load_one_arg
    jsr basic_math_subtract
    bcs @fail
    ldx #0
@save_y:
    lda math_fac,x
    sta log_y_save,x
    inx
    cpx #5
    bne @save_y
    lda #TYPE_FLOAT
    sta math_fac_type
    clc
    rts
@fail:
    sec
    rts

log_fast_path_check:
    ldx #0
@restore_y:
    lda log_y_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @restore_y
    lda #TYPE_FLOAT
    sta math_fac_type
    lda #<const_log1p_fast_limit
    sta log_coeff_save
    lda #>const_log1p_fast_limit
    sta log_coeff_save+1
    jmp log_abs_fac_le_saved_const

log_evaluate_fast_path:
    lda #<coeff_log_taylor6_u
    sta log_coeff_save
    lda #>coeff_log_taylor6_u
    sta log_coeff_save+1
    jmp basic_math_poly_eval_coeff

log_compute_z:
    ldx #0
@restore_m:
    lda log_m_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @restore_m
    lda #TYPE_FLOAT
    sta math_fac_type
    jsr atn_load_one_arg
    jsr basic_math_add
    bcs @fail
    jsr math_copy_fac_to_arg
    ldx #0
@restore_y:
    lda log_y_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @restore_y
    lda #TYPE_FLOAT
    sta math_fac_type
    jsr basic_math_divide
    bcs @fail
    lda #TYPE_FLOAT
    sta math_fac_type
    clc
    rts
@fail:
    sec
    rts

log_evaluate_atanh:
    ldx #0
@save_z:
    lda math_fac,x
    sta log_num_save,x
    inx
    cpx #5
    bne @save_z
    jsr math_copy_fac_to_arg
    jsr basic_math_multiply
    bcs @fail
    ldx #0
@save_u:
    lda math_fac,x
    sta log_result_save,x
    inx
    cpx #5
    bne @save_u
    lda #<log_atanh_c5
    sta log_coeff_save
    lda #>log_atanh_c5
    sta log_coeff_save+1
    jsr log_load_saved_coeff_to_fac
    lda #<log_atanh_c4
    ldy #>log_atanh_c4
    jsr log_horner_step
    bcs @fail
    lda #<log_atanh_c3
    ldy #>log_atanh_c3
    jsr log_horner_step
    bcs @fail
    lda #<log_atanh_c2
    ldy #>log_atanh_c2
    jsr log_horner_step
    bcs @fail
    lda #<log_atanh_c1
    ldy #>log_atanh_c1
    jsr log_horner_step
    bcs @fail
    lda #<log_atanh_c0
    ldy #>log_atanh_c0
    jsr log_horner_step
    bcs @fail
    ldx #0
@restore_z_arg:
    lda log_num_save,x
    sta math_arg,x
    inx
    cpx #5
    bne @restore_z_arg
    lda #TYPE_FLOAT
    sta math_arg_type
    jmp basic_math_multiply
@fail:
    sec
    rts

log_horner_step:
    sta log_coeff_save
    sty log_coeff_save+1
    ldx #0
@restore_u_arg:
    lda log_result_save,x
    sta math_arg,x
    inx
    cpx #5
    bne @restore_u_arg
    lda #TYPE_FLOAT
    sta math_arg_type
    jsr basic_math_multiply
    bcs @fail
    lda log_coeff_save
    sta log_coeff_save
    lda log_coeff_save+1
    sta log_coeff_save+1
    jsr log_load_saved_coeff_to_arg
    jmp basic_math_add
@fail:
    sec
    rts

log_load_saved_coeff_to_fac:
    lda log_coeff_save
    sta @read+1
    lda log_coeff_save+1
    sta @read+2
    ldy #0
@loop:
@read:
    lda $FFFF,y
    sta math_fac,y
    iny
    cpy #5
    bne @loop
    lda #TYPE_FLOAT
    sta math_fac_type
    clc
    rts

log_load_saved_coeff_to_arg:
    lda log_coeff_save
    sta @read+1
    lda log_coeff_save+1
    sta @read+2
    ldy #0
@loop:
@read:
    lda $FFFF,y
    sta math_arg,y
    iny
    cpy #5
    bne @loop
    lda #TYPE_FLOAT
    sta math_arg_type
    clc
    rts

log_reconstruct:
    ldx #0
@save_result:
    lda math_fac,x
    sta log_result_save,x
    inx
    cpx #5
    bne @save_result
    lda log_exp_k
    beq @success
    jsr reduce_signed_byte_to_fac
    bcs @fail
    jsr math_load_const_ln2_arg
    jsr basic_math_multiply
    bcs @fail
    jsr math_copy_fac_to_arg
    ldx #0
@restore_result:
    lda log_result_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @restore_result
    lda #TYPE_FLOAT
    sta math_fac_type
    jsr basic_math_add
    bcs @fail
@success:
    jmp math_success
@fail:
    lda #MATH_ERR_DOMAIN
    jmp math_fail_a

log_save_fac:
    ldx #0
log_save_fac_loop:
    lda math_fac,x
    sta temp3,x
    inx
    cpx #5
    bne log_save_fac_loop
    rts

log_restore_fac:
    ldx #0
log_restore_fac_loop:
    lda temp3,x
    sta math_fac,x
    inx
    cpx #5
    bne log_restore_fac_loop
    rts

log_save_num:
    ldx #0
log_save_num_loop:
    lda math_fac,x
    sta log_num_save,x
    inx
    cpx #5
    bne log_save_num_loop
    rts

log_restore_num:
    ldx #0
log_restore_num_loop:
    lda log_num_save,x
    sta math_fac,x
    inx
    cpx #5
    bne log_restore_num_loop
    rts

math_abs_fac_le_const_ptr:
    ldy #0
@loop:
    lda math_fac,y
    cpy #1
    bne @fac_ready
    and #$7f
@fac_ready:
    sta temp6
    lda (math_coeff_ptr),y
    cpy #1
    bne @const_ready
    and #$7f
@const_ready:
    sta temp6+1
    lda temp6
    cmp temp6+1
    bcc @less_equal
    bne @greater
    iny
    cpy #5
    bne @loop
@less_equal:
    clc
    rts
@greater:
    sec
    rts

log_abs_fac_le_saved_const:
    lda log_coeff_save
    sta @read_const+1
    lda log_coeff_save+1
    sta @read_const+2
    ldy #0
@loop:
    lda math_fac,y
    cpy #1
    bne @fac_ready
    and #$7f
@fac_ready:
    sta temp6
@read_const:
    lda $FFFF,y
    cpy #1
    bne @const_ready
    and #$7f
@const_ready:
    sta temp6+1
    lda temp6
    cmp temp6+1
    bcc @less_equal
    bne @greater
    iny
    cpy #5
    bne @loop
@less_equal:
    clc
    rts
@greater:
    sec
    rts

basic_exp:
    jsr math_adaptive_fac_to_float
    lda math_fac
    BEQ_FAR exp_zero_input
    jsr exp_reduce_to_kernel
    BCS_FAR math_fail_current
    lda #<coeff_exp_taylor4
    sta math_coeff_ptr
    lda #>coeff_exp_taylor4
    sta math_coeff_ptr+1
    jsr basic_math_poly_eval_coeff
    BCS_FAR math_fail_current
    jsr exp_apply_scale
    BCS_FAR math_fail_current
    jmp math_success
exp_zero_input:
    jsr math_load_one
    jmp math_success
exp_reduce_to_kernel:
    jsr exp_save_input
    lda #0
    sta log_exp_k
exp_reduce_loop:
    jsr exp_abs_le_half_ln2
    bcc exp_reduce_done
    lda math_fac+1
    bmi exp_reduce_negative
    jsr exp_load_reduce_ln2_arg
    jsr basic_math_subtract
    BCS_FAR exp_reduce_fail
    inc log_exp_k
    jmp exp_reduce_loop
exp_reduce_negative:
    jsr exp_load_reduce_ln2_arg
    jsr basic_math_add
    BCS_FAR exp_reduce_fail
    dec log_exp_k
    jmp exp_reduce_loop
exp_reduce_done:
    jsr exp_recompute_reduction
    bcs exp_reduce_fail
    clc
    rts
exp_reduce_fail:
    sec
    rts

exp_apply_scale:
    lda math_fac
    beq exp_apply_done
    clc
    adc log_exp_k
    beq exp_apply_underflow
    sta math_fac
exp_apply_done:
    clc
    rts
exp_apply_underflow:
    jsr math_load_zero
    clc
    rts

exp_abs_le_half_ln2:
    ldx #0
exp_abs_le_half_ln2_loop:
    lda math_fac,x
    cpx #1
    bne :+
    and #$7f
:
    cmp const_half_ln2_reduce_hi,x
    bne exp_compare_done
    inx
    cpx #5
    bne exp_abs_le_half_ln2_loop
    clc
    rts

exp_compare_done:
    rts

math_load_const_ln2_arg:
    lda #TYPE_FLOAT
    sta math_arg_type
    ldx #0
math_load_const_ln2_arg_loop:
    lda const_ln2,x
    sta math_arg,x
    inx
    cpx #5
    bne math_load_const_ln2_arg_loop
    rts

exp_load_reduce_ln2_arg:
    lda #TYPE_FLOAT
    sta math_arg_type
    ldx #0
@loop:
    lda const_ln2_reduce_hi,x
    sta math_arg,x
    inx
    cpx #5
    bne @loop
    rts

exp_save_input:
    ldx #0
@loop:
    lda math_fac,x
    sta exp_input_save,x
    inx
    cpx #5
    bne @loop
    rts

exp_restore_input:
    ldx #0
@loop:
    lda exp_input_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @loop
    rts

math_signed_byte_to_fac:
    bpl math_signed_byte_positive
    eor #$ff
    clc
    adc #1
    jsr math_load_code
    bcs math_signed_byte_fail
    lda math_fac+1
    ora #$80
    sta math_fac+1
    clc
    rts
math_signed_byte_positive:
    jsr math_load_code
    bcs math_signed_byte_fail
    clc
    rts
math_signed_byte_fail:
    sec
    rts

basic_cos:
    jsr math_adaptive_fac_to_float
    lda math_fac
    beq cos_zero
    jsr trig_reduce_to_kernel
    BCS_FAR math_fail_current
    lda math_fac
    beq cos_axis
    lda trig_quadrant
    and #3
    beq cos_kernel
    cmp #1
    beq cos_use_neg_sin
    cmp #2
    beq cos_use_neg_cos
    jmp cos_use_sin
cos_kernel:
    lda #<coeff_cos_remez6_u
    sta math_coeff_ptr
    lda #>coeff_cos_remez6_u
    sta math_coeff_ptr+1
    jsr basic_math_poly_eval_even
    BCS_FAR math_fail_current
    jmp math_success
cos_use_neg_sin:
    jsr trig_eval_sin_kernel
    BCS_FAR math_fail_current
    jsr trig_negate_fac
    jmp math_success
cos_use_neg_cos:
    jsr trig_eval_cos_kernel
    BCS_FAR math_fail_current
    jsr trig_negate_fac
    jmp math_success
cos_use_sin:
    jsr trig_eval_sin_kernel
    BCS_FAR math_fail_current
    jmp math_success
cos_zero:
    jsr math_load_one
    jmp math_success
cos_axis:
    lda trig_quadrant
    and #3
    beq cos_zero
    cmp #2
    beq cos_axis_neg_one
    jsr trig_load_half_resid_fac
    jmp math_success
cos_axis_neg_one:
    jsr math_load_neg_one
    jmp math_success

trig_eval_sin_kernel:
    lda #<coeff_sin_remez7_u
    sta math_coeff_ptr
    lda #>coeff_sin_remez7_u
    sta math_coeff_ptr+1
    jmp basic_math_poly_eval_odd

trig_eval_cos_kernel:
    lda #<coeff_cos_remez6_u
    sta math_coeff_ptr
    lda #>coeff_cos_remez6_u
    sta math_coeff_ptr+1
    jmp basic_math_poly_eval_even

trig_negate_fac:
    lda math_fac
    beq trig_negate_done
    lda math_fac+1
    eor #$80
    sta math_fac+1
trig_negate_done:
    rts

trig_reduce_to_kernel:
    lda #0
    sta trig_quadrant
    lda math_fac+1
    and #$80
    sta trig_input_sign
trig_reduce_loop:
    jsr trig_abs_le_quarter_pi
    bcc trig_reduce_done
    lda math_fac+1
    bmi trig_reduce_negative
    jsr trig_load_half_pi_arg
    jsr basic_math_subtract
    BCS_FAR trig_reduce_fail
    inc trig_quadrant
    jmp trig_reduce_loop
trig_reduce_negative:
    jsr trig_load_half_pi_arg
    jsr basic_math_add
    BCS_FAR trig_reduce_fail
    dec trig_quadrant
    jmp trig_reduce_loop
trig_reduce_done:
    lda math_fac
    beq trig_reduce_exact_axis
    jsr trig_apply_reduction_correction
    bcs trig_reduce_fail
trig_reduce_exact_axis:
    clc
    rts
trig_reduce_fail:
    sec
    rts

trig_abs_le_quarter_pi:
    ldx #0
trig_abs_le_quarter_pi_loop:
    lda math_fac,x
    cpx #1
    bne :+
    and #$7f
:
    cmp const_quarter_pi,x
    bne trig_compare_done
    inx
    cpx #5
    bne trig_abs_le_quarter_pi_loop
    clc
    rts

trig_compare_done:
    rts

trig_load_half_pi_arg:
    lda #TYPE_FLOAT
    sta math_arg_type
    ldx #0
trig_load_half_pi_arg_loop:
    lda const_half_pi,x
    sta math_arg,x
    inx
    cpx #5
    bne trig_load_half_pi_arg_loop
    rts

trig_load_half_resid_fac:
    ldx #0
trig_load_half_resid_fac_loop:
    lda const_trig_resid_half,x
    sta math_fac,x
    inx
    cpx #5
    bne trig_load_half_resid_fac_loop
    rts

trig_load_pi_resid_fac:
    ldx #0
trig_load_pi_resid_fac_loop:
    lda const_trig_resid_pi,x
    sta math_fac,x
    inx
    cpx #5
    bne trig_load_pi_resid_fac_loop
    rts

trig_match_half_pi_abs:
    ldx #0
trig_match_half_pi_abs_loop:
    lda math_fac,x
    cpx #1
    bne :+
    and #$7f
:
    cmp const_half_pi,x
    bne trig_match_half_pi_abs_no
    inx
    cpx #5
    bne trig_match_half_pi_abs_loop
    clc
    rts
trig_match_half_pi_abs_no:
    sec
    rts

.segment "RUNTIME"

math_get_binary_codes:
    jsr math_copy_fac_to_temp1
    jsr math_fac_code
    bcs math_codes_fail
    sta math_class
    jsr math_copy_arg_to_fac
    jsr math_fac_code
    bcs math_codes_restore_fail
    sta math_work
    jsr math_copy_temp1_to_fac
    clc
    rts
math_codes_restore_fail:
    jsr math_copy_temp1_to_fac
math_codes_fail:
    sec
    rts

math_load_code_success:
    jsr math_load_code
    bcs math_codes_fail
    jmp math_success

math_add_code_impl:
    jsr math_get_binary_codes
    BCS_FAR math_code_unhandled
    lda math_class
    cmp #$80
    BCS_FAR math_code_unhandled
    clc
    adc math_work
    cmp #16
    BCS_FAR math_code_unhandled
    jsr math_load_code_success
    clc
    rts

math_subtract_code_impl:
    jsr math_get_binary_codes
    BCS_FAR math_code_unhandled
    lda math_class
    cmp #$80
    BCS_FAR math_code_unhandled
    sec
    sbc math_work
    bpl :+
    jmp math_code_unhandled
:
    jsr math_load_code_success
    clc
    rts

math_multiply_code_impl:
    jsr math_get_binary_codes
    BCS_FAR math_code_unhandled
    lda math_class
    cmp #$80
    BCS_FAR math_code_unhandled
    ldx math_work
    beq math_multiply_zero
    sta math_work+1
    lda #0
math_multiply_code_loop:
    clc
    adc math_work+1
    dex
    bne math_multiply_code_loop
    cmp #16
    bcs math_code_unhandled
    jsr math_load_code_success
    clc
    rts
math_multiply_zero:
    jsr math_load_zero
    jsr math_success
    clc
    rts

math_divide_code_impl:
    jsr math_get_binary_codes
    bcs math_code_unhandled
    lda math_work
    beq math_divide_code_zero
    lda math_class
    cmp #$80
    bcs math_code_unhandled
    ldx #0
math_divide_code_loop:
    cmp math_work
    bcc math_divide_code_done
    sec
    sbc math_work
    inx
    jmp math_divide_code_loop
math_divide_code_done:
    sta fin_digit_value
    txa
    jsr math_load_code_success
    lda fin_digit_value
    beq math_divide_code_success
    jsr math_copy_fac_to_temp1
    lda fin_digit_value
    asl
    sta fin_exp_tmp
    asl
    asl
    clc
    adc fin_exp_tmp
    ldx #0
math_divide_code_frac_loop:
    cmp math_work
    bcc math_divide_code_frac_done
    sec
    sbc math_work
    inx
    jmp math_divide_code_frac_loop
math_divide_code_frac_done:
    txa
    jsr math_load_code
    bcs math_code_unhandled
    jsr math_load_tenth_arg
    jsr basic_math_multiply
    bcs math_code_unhandled
    jsr math_copy_fac_to_arg
    jsr math_copy_temp1_to_fac
    jsr basic_math_add
    bcs math_code_unhandled
math_divide_code_success:
    clc
    rts
math_divide_code_zero:
    sec
    rts
math_code_unhandled:
    sec
    rts

math_sqr_code_impl:
    jsr math_fac_code
    bcs math_code_unhandled
    cmp #0
    beq math_sqr_zero
    cmp #1
    beq math_sqr_one
    cmp #4
    beq math_sqr_two
    cmp #9
    beq math_sqr_three
    sec
    rts
math_sqr_zero:
    jsr math_load_zero
    jsr math_success
    clc
    rts
math_sqr_one:
    jsr math_load_one
    jsr math_success
    clc
    rts
math_sqr_two:
    jsr math_load_two
    jsr math_success
    clc
    rts
math_sqr_three:
    jsr math_load_three
    jsr math_success
    clc
    rts

; General C64 5-byte SQR.
; Builds a 64-bit radicand from the normalized mantissa:
;   if exponent power is even, radicand = mantissa << 31
;   if exponent power is odd,  radicand = mantissa << 32
; Then runs a 32-step restoring integer square root and repacks the rounded
; 32-bit root as the result mantissa.
basic_sqr_impl:
    lda math_fac
    clc
    adc #$81
    ror
    sta math_work+4
    lda math_fac
    eor #$81
    and #1
    sta temp6
    jsr sqr_build_radicand
    jsr sqr_clear_root_rem
    ldx #32
sqr_loop:
    stx math_work+3
    lda #0
    sta math_work
    lda sqr_rad
    and #$80
    beq :+
    lda #2
    sta math_work
:
    lda sqr_rad
    and #$40
    beq :+
    lda math_work
    ora #1
    sta math_work
:
    asl sqr_rad+7
    rol sqr_rad+6
    rol sqr_rad+5
    rol sqr_rad+4
    rol sqr_rad+3
    rol sqr_rad+2
    rol sqr_rad+1
    rol sqr_rad
    asl sqr_rad+7
    rol sqr_rad+6
    rol sqr_rad+5
    rol sqr_rad+4
    rol sqr_rad+3
    rol sqr_rad+2
    rol sqr_rad+1
    rol sqr_rad
    asl temp2+4
    rol temp2+3
    rol temp2+2
    rol temp2+1
    rol temp2
    asl temp2+4
    rol temp2+3
    rol temp2+2
    rol temp2+1
    rol temp2
    lda temp2+4
    ora math_work
    sta temp2+4
    asl temp1+4
    rol temp1+3
    rol temp1+2
    rol temp1+1
    lda #0
    sta temp3
    sta temp3+1
    sta temp3+2
    sta temp3+3
    sta temp3+4
    lda temp1+4
    asl
    sta temp3+4
    lda temp1+3
    rol
    sta temp3+3
    lda temp1+2
    rol
    sta temp3+2
    lda temp1+1
    rol
    sta temp3+1
    lda #0
    rol
    sta temp3
    lda temp3+4
    ora #1
    sta temp3+4
    ldy #0
@compare:
    lda temp2,y
    cmp temp3,y
    bne @compare_done
    iny
    cpy #5
    bne @compare
    sec
@compare_done:
    bcc sqr_loop_next
    lda temp2+4
    sec
    sbc temp3+4
    sta temp2+4
    lda temp2+3
    sbc temp3+3
    sta temp2+3
    lda temp2+2
    sbc temp3+2
    sta temp2+2
    lda temp2+1
    sbc temp3+1
    sta temp2+1
    lda temp2
    sbc temp3
    sta temp2
    lda temp1+4
    ora #1
    sta temp1+4
sqr_loop_next:
    ldx math_work+3
    dex
    beq sqr_done
    jmp sqr_loop
sqr_done:
    lda #0
    sta ext_sign
    lda math_work+4
    sta ext_exp
    lda temp1+1
    sta ext_mant
    lda temp1+2
    sta ext_mant+1
    lda temp1+3
    sta ext_mant+2
    lda temp1+4
    sta ext_mant+3
    jsr sqr_prepare_finalize
    jsr math_finalize_extended_to_fac
    BCS_FAR math_unsupported
    jmp math_success

sqr_build_radicand:
    lda math_fac+1
    and #$7f
    ora #$80
    sta sqr_rad
    lda math_fac+2
    sta sqr_rad+1
    lda math_fac+3
    sta sqr_rad+2
    lda math_fac+4
    sta sqr_rad+3
    lda #0
    sta sqr_rad+4
    sta sqr_rad+5
    sta sqr_rad+6
    sta sqr_rad+7
    lda temp6
    bne sqr_build_done
    ldx #1
sqr_build_shift_right:
    lsr sqr_rad
    ror sqr_rad+1
    ror sqr_rad+2
    ror sqr_rad+3
    ror sqr_rad+4
    dex
    bne sqr_build_shift_right
sqr_build_done:
    rts

sqr_clear_root_rem:
    lda #0
    ldx #0
sqr_clear_loop:
    sta temp1+1,x
    sta temp2,x
    inx
    cpx #5
    bne sqr_clear_loop
    rts

sqr_prepare_finalize:
    lda #0
    sta ext_extra
    sta ext_extra+1
    sta ext_extra+2
    sta ext_extra+3
    lda temp2
    bne sqr_round_gt_half
    lda temp2+1
    cmp ext_mant
    bne sqr_round_compare_done
    lda temp2+2
    cmp ext_mant+1
    bne sqr_round_compare_done
    lda temp2+3
    cmp ext_mant+2
    bne sqr_round_compare_done
    lda temp2+4
    cmp ext_mant+3
    bne sqr_round_compare_done
    sta ext_extra
    rts
sqr_round_compare_done:
    bcc sqr_round_lt_half
sqr_round_gt_half:
    lda #$80
    sta ext_extra
    lda #1
    sta ext_extra+3
sqr_round_lt_half:
    rts

.segment "RUNTIME"

basic_tan:
    jsr math_adaptive_fac_to_float
    lda math_fac
    beq tan_initial_zero
    jsr trig_reduce_to_kernel
    BCS_FAR math_fail_current
    lda math_fac
    beq tan_axis
    lda trig_quadrant
    and #1
    bne tan_recip
tan_kernel:
    lda #<coeff_tan_remez5_u
    sta math_coeff_ptr
    lda #>coeff_tan_remez5_u
    sta math_coeff_ptr+1
    jsr basic_math_poly_eval_odd
    BCS_FAR math_fail_current
    jmp math_success
tan_recip:
    lda math_fac
    beq tan_domain_error
    jsr tan_kernel_value
    BCS_FAR math_fail_current
    lda math_fac
    beq tan_domain_error
    jsr math_copy_fac_to_arg
    jsr math_load_neg_one
    jsr basic_math_divide
    BCS_FAR math_fail_current
    jmp math_success
tan_kernel_value:
    lda #<coeff_tan_remez5_u
    sta math_coeff_ptr
    lda #>coeff_tan_remez5_u
    sta math_coeff_ptr+1
    jmp basic_math_poly_eval_odd
tan_zero:
    lda trig_quadrant
    and #3
    cmp #2
    beq tan_axis_pi
    jsr math_load_zero
    jmp math_success
tan_initial_zero:
    jsr math_load_zero
    jmp math_success
tan_axis:
    lda trig_quadrant
    and #1
    bne tan_domain_error
    jmp tan_zero
tan_axis_pi:
    jsr trig_load_pi_resid_fac
    lda trig_input_sign
    bne :+
    jsr trig_negate_fac
:
    jmp math_success
tan_domain_error:
    lda #MATH_ERR_DOMAIN
    jmp math_fail_a

basic_atn:
    jsr math_adaptive_fac_to_float
    lda math_fac
    beq atn_zero
    lda math_fac+1
    and #$80
    sta atn_sign
    lda math_fac+1
    and #$7f
    sta math_fac+1
    jsr atn_match_one
    bcc atn_exact_one
    ; The odd minimax kernel is accurate across |x| < 1.  Keeping that whole
    ; interval on the direct path also avoids the lossy (x-1)/(x+1)
    ; transformation, whose nested arithmetic reused the polynomial scratch
    ; state and corrupted ordinary inputs such as 1/sqrt(3).
    jsr atn_abs_lt_one
    bcc atn_direct
    jmp atn_recip
atn_zero:
    jsr math_load_zero
    jmp math_success
atn_direct:
    jsr atn_kernel
    BCS_FAR math_fail_current
    jsr atn_apply_sign
    jmp math_success
atn_exact_one:
    jsr atn_load_quarter_pi_fac
    jsr atn_apply_sign
    jmp math_success
atn_mid:
    jsr atn_abs_lt_one
    bcc atn_mid_common
atn_mid_common:
    jsr atn_save_input
    jsr atn_load_one_arg
    jsr basic_math_subtract
    BCS_FAR math_fail_current
    jsr atn_save_num
    jsr atn_restore_input
    jsr atn_load_one_arg
    jsr basic_math_add
    BCS_FAR math_fail_current
    jsr math_copy_fac_to_arg
    jsr atn_restore_num
    jsr basic_math_divide
    BCS_FAR math_fail_current
    jsr atn_kernel
    BCS_FAR math_fail_current
    jsr math_copy_fac_to_arg
    jsr atn_load_quarter_pi_fac
    jsr basic_math_add
    BCS_FAR math_fail_current
    jsr atn_apply_sign
    jmp math_success
atn_mid_below_one:
    jsr math_copy_fac_to_temp1
    jsr math_copy_temp1_to_fac
    jsr math_copy_fac_to_arg
    jsr math_load_one
    jsr basic_math_subtract
    BCS_FAR math_fail_current
    jsr math_copy_fac_to_temp2
    jsr math_copy_temp1_to_fac
    jsr atn_load_one_arg
    jsr basic_math_add
    BCS_FAR math_fail_current
    jsr math_copy_fac_to_arg
    jsr math_copy_temp2_to_fac
    jsr basic_math_divide
    BCS_FAR math_fail_current
    jsr atn_kernel
    BCS_FAR math_fail_current
    jsr math_copy_fac_to_arg
    jsr atn_load_quarter_pi_fac
    jsr basic_math_subtract
    BCS_FAR math_fail_current
    jsr atn_apply_sign
    jmp math_success
atn_recip:
    jsr math_copy_fac_to_arg
    jsr math_load_one
    jsr basic_math_divide
    BCS_FAR math_fail_current
    jsr atn_kernel
    BCS_FAR math_fail_current
    jsr math_copy_fac_to_arg
    jsr atn_load_half_pi_fac
    jsr basic_math_subtract
    BCS_FAR math_fail_current
    jsr atn_apply_sign
    jmp math_success

atn_kernel:
    lda #<coeff_atn_remez7_u
    sta math_coeff_ptr
    lda #>coeff_atn_remez7_u
    sta math_coeff_ptr+1
    jmp basic_math_poly_eval_odd

atn_apply_sign:
    lda math_fac
    beq atn_apply_sign_done
    lda math_fac+1
    and #$7f
    ora atn_sign
    sta math_fac+1
atn_apply_sign_done:
    rts

atn_match_one:
    ldx #0
atn_match_one_loop:
    lda math_fac,x
    cmp const_one,x
    bne atn_match_one_no
    inx
    cpx #5
    bne atn_match_one_loop
    clc
    rts
atn_match_one_no:
    sec
    rts

atn_abs_lt_one:
    ldx #0
atn_abs_lt_one_loop:
    lda math_fac,x
    cmp const_one,x
    bne atn_compare_done
    inx
    cpx #5
    bne atn_abs_lt_one_loop
    sec
    rts

atn_abs_le_low:
    ldx #0
atn_abs_le_low_loop:
    lda math_fac,x
    cmp const_atn_low,x
    bne atn_compare_done
    inx
    cpx #5
    bne atn_abs_le_low_loop
    clc
    rts

atn_abs_le_high:
    ldx #0
atn_abs_le_high_loop:
    lda math_fac,x
    cmp const_atn_high,x
    bne atn_compare_done
    inx
    cpx #5
    bne atn_abs_le_high_loop
    clc
    rts
atn_compare_done:
    rts

atn_load_one_arg:
    lda #TYPE_FLOAT
    sta math_arg_type
    ldx #0
atn_load_one_arg_loop:
    lda const_one,x
    sta math_arg,x
    inx
    cpx #5
    bne atn_load_one_arg_loop
    rts

atn_load_quarter_pi_fac:
    ldx #0
atn_load_quarter_pi_fac_loop:
    lda const_quarter_pi,x
    sta math_fac,x
    inx
    cpx #5
    bne atn_load_quarter_pi_fac_loop
    rts

atn_load_half_pi_fac:
    ldx #0
atn_load_half_pi_fac_loop:
    lda const_half_pi,x
    sta math_fac,x
    inx
    cpx #5
    bne atn_load_half_pi_fac_loop
    rts

atn_save_input:
    ldx #0
@loop:
    lda math_fac,x
    sta atn_input_save,x
    inx
    cpx #5
    bne @loop
    rts

atn_restore_input:
    ldx #0
@loop:
    lda atn_input_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @loop
    rts

atn_save_num:
    ldx #0
@loop:
    lda math_fac,x
    sta atn_num_save,x
    inx
    cpx #5
    bne @loop
    rts

atn_restore_num:
    ldx #0
@loop:
    lda atn_num_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @loop
    rts

exp_apply_reduction_correction:
    lda log_exp_k
    bne :+
    clc
    rts
:
    jsr reduce_save_value
    lda log_exp_k
    jsr reduce_signed_byte_to_fac
    bcs reduce_correction_fail
    jsr load_ln2_reduce_err_arg
    jsr basic_math_multiply
    bcs reduce_correction_fail
    jsr math_copy_fac_to_arg
    jsr reduce_restore_value
    jsr basic_math_add
    bcs reduce_correction_fail
    clc
    rts

exp_recompute_reduction:
    lda log_exp_k
    bne :+
    jsr exp_restore_input
    clc
    rts
:
    jsr reduce_signed_byte_to_fac
    bcs reduce_correction_fail
    jsr exp_load_reduce_ln2_arg
    jsr basic_math_multiply
    bcs reduce_correction_fail
    jsr math_copy_fac_to_arg
    jsr exp_restore_input
    jsr basic_math_subtract
    bcs reduce_correction_fail
    jmp exp_apply_reduction_correction

trig_apply_reduction_correction:
    lda trig_quadrant
    ldy #<const_half_pi_reduce_err
    ldx #>const_half_pi_reduce_err

apply_signed_reduction_correction:
    sta temp6
    bne :+
    clc
    rts
:
    sty math_coeff_ptr
    stx math_coeff_ptr+1
    jsr reduce_save_value
    lda temp6
    jsr math_signed_byte_to_fac
    bcs reduce_correction_fail
    ldy #0
@load_arg:
    lda (math_coeff_ptr),y
    sta math_arg,y
    iny
    cpy #5
    bne @load_arg
    jsr basic_math_multiply
    bcs reduce_correction_fail
    jsr math_copy_fac_to_arg
    jsr reduce_restore_value
    jsr basic_math_add
    bcs reduce_correction_fail
    clc
    rts
reduce_correction_fail:
    sec
    rts

load_ln2_reduce_err_arg:
    lda #TYPE_FLOAT
    sta math_arg_type
    ldy #0
@loop:
    lda const_ln2_reduce_err,y
    sta math_arg,y
    iny
    cpy #5
    bne @loop
    rts

reduce_signed_byte_to_fac:
    sta temp6
    bpl reduce_unsigned_byte_to_fac
    eor #$ff
    clc
    adc #1
    sta temp6
    jsr reduce_unsigned_byte_to_fac
    bcs :+
    lda math_fac+1
    ora #$80
    sta math_fac+1
:
    rts

reduce_unsigned_byte_to_fac:
    lda #<temp6
    sta math_input_ptr
    lda #>temp6
    sta math_input_ptr+1
    jsr basic_int_to_fac
    clc
    rts

reduce_save_value:
    ldx #0
@loop:
    lda math_fac,x
    sta reduce_value_save,x
    inx
    cpx #5
    bne @loop
    rts

reduce_restore_value:
    ldx #0
@loop:
    lda reduce_value_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @loop
    rts

.segment "RUNTIME"

basic_math_fma:
    ldy #0
fma_copy_addend:
    lda (math_input_ptr),y
    sta temp5,y
    iny
    cpy #5
    bne fma_copy_addend
    jmp fma_with_saved_addend

basic_math_fma_from_coeff_ptr:
    ldy #0
fma_copy_coeff_addend:
    lda (math_coeff_ptr),y
    sta temp5,y
    iny
    cpy #5
    bne fma_copy_coeff_addend
fma_with_saved_addend:
    lda math_fac
    beq fma_addend_only
    lda math_arg
    beq fma_addend_only
    jsr math_multiply_to_ext
    BCS_FAR math_fail_a
    lda temp5
    beq fma_finalize_result
    jsr fma_accumulate_saved_addend
    BCS_FAR math_unsupported
fma_finalize_result:
    jsr math_finalize_extended_to_fac
    BCS_FAR math_unsupported
    jmp math_success
fma_addend_only:
    ldx #0
fma_copy_addend_to_fac:
    lda temp5,x
    sta math_fac,x
    inx
    cpx #5
    bne fma_copy_addend_to_fac
    jmp math_success

basic_math_multiply_impl:
    jsr math_multiply_to_ext
    BCS_FAR math_fail_a
    jsr math_finalize_extended_to_fac
    BCS_FAR math_unsupported
    jmp math_success

math_multiply_to_ext:
    lda math_fac
    beq mul_impl_zero_ext
    lda math_arg
    beq mul_impl_zero_ext
    lda math_fac+1
    eor math_arg+1
    and #$80
    sta ext_sign
    lda math_fac
    clc
    adc math_arg
    bcs mul_impl_exp_carry
    sec
    sbc #$81
    sta math_work+1
    bcc mul_impl_zero_ext
    jmp mul_impl_exp_done
mul_impl_exp_carry:
    cmp #$81
    bcs mul_impl_overflow_ext
    sec
    sbc #$81
    sta math_work+1
mul_impl_exp_done:
    jsr mul_load_operands
mul_operands_loaded:
    jsr mul_clear_product
    ldx #32
mul_impl_loop:
    stx math_work+2
    jsr mul_shift_multiplier_right
    bcc mul_impl_no_add
    jsr mul_add_multiplicand
mul_impl_no_add:
    jsr mul_shift_multiplicand_left
    ldx math_work+2
    dex
    bne mul_impl_loop
    lda sqr_rad
    bmi mul_impl_high_product
    jsr mul_extract_shift31
    lda math_work+1
    sta ext_exp
    clc
    rts
mul_impl_high_product:
    inc math_work+1
    beq mul_impl_overflow_ext
    jsr mul_extract_shift32
    lda math_work+1
    sta ext_exp
    clc
    rts
mul_impl_zero_ext:
    lda #0
    sta ext_sign
    sta ext_exp
    sta ext_mant
    sta ext_mant+1
    sta ext_mant+2
    sta ext_mant+3
    sta ext_extra
    sta ext_extra+1
    sta ext_extra+2
    sta ext_extra+3
    clc
    rts
mul_impl_overflow_ext:
    lda #MATH_ERR_UNSUPPORTED
    sec
    rts

.segment "RUNTIME"

math_square_to_ext:
    lda math_fac
    BEQ_FAR mul_impl_zero_ext
    lda #0
    sta ext_sign
    lda math_fac
    clc
    adc math_fac
    bcs square_exp_carry
    sec
    sbc #$81
    sta math_work+1
    bcs :+
    jmp mul_impl_zero_ext
:
    jmp square_exp_done
square_exp_carry:
    cmp #$81
    bcc :+
    jmp mul_impl_overflow_ext
:
    sec
    sbc #$81
    sta math_work+1
square_exp_done:
    jsr square_load_operand
    jmp mul_operands_loaded

square_load_operand:
    lda math_fac+1
    and #$7f
    ora #$80
    sta temp1
    sta temp2+1
    lda math_fac+2
    sta temp1+1
    sta temp2+2
    lda math_fac+3
    sta temp1+2
    sta temp2+3
    lda math_fac+4
    sta temp1+3
    sta temp2+4
    lda #0
    sta mul_mcand+4
    sta mul_mcand+5
    sta mul_mcand+6
    sta mul_mcand+7
    lda temp1+3
    sta mul_mcand
    lda temp1+2
    sta mul_mcand+1
    lda temp1+1
    sta mul_mcand+2
    lda temp1
    sta mul_mcand+3
    rts

power_load_integer_exponent:
    lda #0
    sta power_exp_negative
    sta power_half_negative
    lda math_arg_type
    cmp #TYPE_INT1
    beq power_load_int1_exp
    cmp #TYPE_INT2
    beq power_load_int2_exp
    sec
    rts
power_load_int1_exp:
    lda math_arg
    sta power_exp_lo
    sta power_half_int_part
    bpl :+
    lda #$ff
    jmp :++
:
    lda #0
:
    sta power_exp_hi
    jmp power_abs_exponent
power_load_int2_exp:
    lda math_arg
    sta power_exp_lo
    sta power_half_int_part
    lda math_arg+1
    sta power_exp_hi
power_abs_exponent:
    lda power_exp_hi
    bpl power_exp_positive
    lda #1
    sta power_exp_negative
    sta power_half_negative
    lda power_exp_lo
    eor #$ff
    clc
    adc #1
    sta power_exp_lo
    lda power_exp_hi
    eor #$ff
    adc #0
    sta power_exp_hi
power_exp_positive:
    clc
    rts

power_shift_exp_right:
    lsr power_exp_hi
    ror power_exp_lo
    rts

power_save_arg_exp:
    ldx #0
power_save_arg_exp_loop:
    lda math_arg,x
    sta power_exp_save,x
    inx
    cpx #5
    bne power_save_arg_exp_loop
    rts

power_restore_exp_arg:
    ldx #0
power_restore_exp_arg_loop:
    lda power_exp_save,x
    sta math_arg,x
    inx
    cpx #5
    bne power_restore_exp_arg_loop
    lda #TYPE_FLOAT
    sta math_arg_type
    rts

power_save_fac_base:
    ldx #0
power_save_fac_base_loop:
    lda math_fac,x
    sta power_base_save,x
    inx
    cpx #5
    bne power_save_fac_base_loop
    rts

power_restore_base_fac:
    ldx #0
power_restore_base_fac_loop:
    lda power_base_save,x
    sta math_fac,x
    inx
    cpx #5
    bne power_restore_base_fac_loop
    lda #TYPE_FLOAT
    sta math_fac_type
    rts

power_load_base_arg:
    ldx #0
power_load_base_arg_loop:
    lda power_base_save,x
    sta math_arg,x
    inx
    cpx #5
    bne power_load_base_arg_loop
    lda #TYPE_FLOAT
    sta math_arg_type
    rts

power_save_fac_result:
    ldx #0
power_save_fac_result_loop:
    lda math_fac,x
    sta power_result_save,x
    inx
    cpx #5
    bne power_save_fac_result_loop
    rts

power_restore_result_fac:
    ldx #0
power_restore_result_fac_loop:
    lda power_result_save,x
    sta math_fac,x
    inx
    cpx #5
    bne power_restore_result_fac_loop
    lda #TYPE_FLOAT
    sta math_fac_type
    rts

power_save_fac_sqrt:
    ldx #0
@loop:
    lda math_fac,x
    sta power_sqrt_save,x
    inx
    cpx #5
    bne @loop
    rts

power_restore_sqrt_fac:
    ldx #0
@loop:
    lda power_sqrt_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @loop
    lda #TYPE_FLOAT
    sta math_fac_type
    rts

power_load_sqrt_arg:
    ldx #0
@loop:
    lda power_sqrt_save,x
    sta math_arg,x
    inx
    cpx #5
    bne @loop
    lda #TYPE_FLOAT
    sta math_arg_type
    rts

power_try_float_integer_arg:
    lda math_arg_type
    cmp #TYPE_FLOAT
    bne @fail
    jsr power_save_fac_base
    ldx #0
@arg_to_fac_loop:
    lda math_arg,x
    sta math_fac,x
    inx
    cpx #5
    bne @arg_to_fac_loop
    jsr math_fac_code
    bcs @restore_fail
    pha
    jsr power_restore_base_fac
    pla
    sta math_arg
    lda #0
    sta math_arg+1
    sta math_arg+2
    sta math_arg+3
    sta math_arg+4
    lda #TYPE_INT1
    sta math_arg_type
    clc
    rts
@restore_fail:
    jsr power_restore_base_fac
@fail:
    sec
    rts

power_try_half_integer_arg:
    lda math_arg_type
    cmp #TYPE_FLOAT
    beq :+
    sec
    rts
:
    jsr math_adaptive_fac_to_float
    jsr power_save_fac_base
    jsr power_save_arg_exp
    lda math_arg+2
    ora math_arg+3
    ora math_arg+4
    beq :+
    jmp @arg_to_fac_loop_start
:
    lda math_arg+1
    bmi @packed_negative_half
    lda #0
    sta power_half_negative
    lda math_arg
    cmp #$80
    bne :+
    lda math_arg+1
    beq @packed_half_0
    jmp @arg_to_fac_loop_start
:
    cmp #$81
    bne :+
    lda math_arg+1
    cmp #$40
    beq @packed_half_1
    jmp @arg_to_fac_loop_start
:
    cmp #$82
    bne :+
    lda math_arg+1
    cmp #$20
    beq @packed_half_2
    cmp #$60
    beq @packed_half_3
    jmp @arg_to_fac_loop_start
:
    cmp #$83
    bne @arg_to_fac_loop_start
    lda math_arg+1
    cmp #$10
    beq @packed_half_4
    cmp #$30
    beq @packed_half_5
    cmp #$50
    beq @packed_half_6
    cmp #$70
    beq @packed_half_7
    jmp @arg_to_fac_loop_start
@packed_negative_half:
    lda math_arg
    cmp #$80
    bne @arg_to_fac_loop_start
    lda math_arg+1
    cmp #$80
    bne @arg_to_fac_loop_start
    lda #1
    sta power_half_negative
@packed_half_0:
    lda #0
    jmp @packed_half_success
@packed_half_1:
    lda #1
    jmp @packed_half_success
@packed_half_2:
    lda #2
    jmp @packed_half_success
@packed_half_3:
    lda #3
    jmp @packed_half_success
@packed_half_4:
    lda #4
    jmp @packed_half_success
@packed_half_5:
    lda #5
    jmp @packed_half_success
@packed_half_6:
    lda #6
    jmp @packed_half_success
@packed_half_7:
    lda #7
@packed_half_success:
    sta math_arg
    lda #0
    sta math_arg+1
    sta math_arg+2
    sta math_arg+3
    sta math_arg+4
    lda #TYPE_INT1
    sta math_arg_type
    jsr power_restore_base_fac
    clc
    rts
@arg_to_fac_loop_start:
    jsr math_load_two
    lda #TYPE_FLOAT
    sta math_fac_type
    jsr math_copy_fac_to_arg
    ldx #0
@restore_exp_to_fac_loop:
    lda power_exp_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @restore_exp_to_fac_loop
    lda #TYPE_FLOAT
    sta math_fac_type
    jsr basic_math_multiply
    bcs @restore_fail
    jsr math_fac_code
    bcs @restore_fail
    sta power_exp_lo
    sta power_half_int_part
    and #1
    beq @restore_fail
    lda #0
    sta power_exp_negative
    sta power_half_negative
    lda power_exp_lo
    cmp #$ff
    bne @positive
    lda #1
    sta power_exp_negative
    sta power_half_negative
    lda #0
    sta power_exp_lo
    sta power_half_int_part
    sta math_arg
    jmp @success
@positive:
    lsr
    sta power_exp_lo
    sta power_half_int_part
    sta math_arg
@success:
    lda #0
    sta math_arg+1
    sta math_arg+2
    sta math_arg+3
    sta math_arg+4
    lda #TYPE_INT1
    sta math_arg_type
    jsr power_restore_base_fac
    clc
    rts
@restore_fail:
    jsr power_restore_base_fac
    jsr power_restore_exp_arg
@fail:
    sec
    rts

power_try_half_exponent:
    lda math_arg_type
    cmp #TYPE_FLOAT
    bne @fail
    lda math_arg
    cmp #$80
    bne @fail
    lda math_arg+1
    ora math_arg+2
    ora math_arg+3
    ora math_arg+4
    bne @fail
    clc
    rts
@fail:
    sec
    rts

power_try_pow2_base:
    jsr power_save_arg_exp
    jsr math_adaptive_fac_to_float
    lda math_fac
    beq @fail
    lda math_fac+1
    bmi @fail
    ora math_fac+2
    ora math_fac+3
    ora math_fac+4
    bne @fail
    sec
    lda math_fac
    sbc #$81
    sta power_exp_lo
    clc
    rts
@fail:
    jsr power_restore_exp_arg
    sec
    rts

power_pow2_exp_arg:
    lda power_exp_lo
    jsr math_signed_byte_to_fac
    bcs @fail
    jsr power_restore_exp_arg
    jsr basic_math_multiply
    bcs @fail
    jsr power_save_fac_result
    jsr exp_load_reduce_ln2_arg
    jsr basic_math_multiply
    bcs @fail
    jsr power_save_fac_sqrt
    jsr power_restore_result_fac
    jsr load_ln2_reduce_err_arg
    jsr basic_math_multiply
    bcs @fail
    jsr math_copy_fac_to_arg
    ldx #0
@restore_hi_loop:
    lda power_sqrt_save,x
    sta math_fac,x
    inx
    cpx #5
    bne @restore_hi_loop
    lda #TYPE_FLOAT
    sta math_fac_type
    jsr basic_math_subtract
    bcs @fail
    clc
    rts
@fail:
    sec
    rts

power_pack_fac_code_to_int:
    jsr math_fac_code
    bcc :+
    rts
:
    sta math_fac
    lda #0
    sta math_fac+1
    sta math_fac+2
    sta math_fac+3
    sta math_fac+4
    lda #TYPE_INT1
    sta math_fac_type
    rts

power_exp_save:
    .res 5
power_base_save:
    .res 5
power_result_save:
    .res 5
power_sqrt_save:
    .res 5
power_exp_lo:
    .byte 0
power_exp_hi:
    .byte 0
power_exp_negative:
    .byte 0
power_half_negative:
    .byte 0
power_half_int_part:
    .byte 0

.segment "RUNTIME"

mul_load_operands:
    lda math_fac+1
    and #$7f
    ora #$80
    sta temp1
    lda math_fac+2
    sta temp1+1
    lda math_fac+3
    sta temp1+2
    lda math_fac+4
    sta temp1+3
    lda math_arg+1
    and #$7f
    ora #$80
    sta temp2+1
    lda math_arg+2
    sta temp2+2
    lda math_arg+3
    sta temp2+3
    lda math_arg+4
    sta temp2+4
    lda #0
    sta mul_mcand+4
    sta mul_mcand+5
    sta mul_mcand+6
    sta mul_mcand+7
    lda temp1+3
    sta mul_mcand
    lda temp1+2
    sta mul_mcand+1
    lda temp1+1
    sta mul_mcand+2
    lda temp1
    sta mul_mcand+3
    rts

mul_clear_product:
    lda #0
    ldx #0
mul_clear_product_loop:
    sta sqr_rad,x
    inx
    cpx #8
    bne mul_clear_product_loop
    rts

mul_shift_multiplier_right:
    lsr temp2+1
    ror temp2+2
    ror temp2+3
    ror temp2+4
    rts

mul_add_multiplicand:
    lda sqr_rad+7
    clc
    adc mul_mcand
    sta sqr_rad+7
    lda sqr_rad+6
    adc mul_mcand+1
    sta sqr_rad+6
    lda sqr_rad+5
    adc mul_mcand+2
    sta sqr_rad+5
    lda sqr_rad+4
    adc mul_mcand+3
    sta sqr_rad+4
    lda sqr_rad+3
    adc mul_mcand+4
    sta sqr_rad+3
    lda sqr_rad+2
    adc mul_mcand+5
    sta sqr_rad+2
    lda sqr_rad+1
    adc mul_mcand+6
    sta sqr_rad+1
    lda sqr_rad
    adc mul_mcand+7
    sta sqr_rad
    rts

mul_shift_multiplicand_left:
    asl mul_mcand
    rol mul_mcand+1
    rol mul_mcand+2
    rol mul_mcand+3
    rol mul_mcand+4
    rol mul_mcand+5
    rol mul_mcand+6
    rol mul_mcand+7
    rts

mul_extract_shift32:
    lda sqr_rad
    sta temp1
    lda sqr_rad+1
    sta temp1+1
    lda sqr_rad+2
    sta temp1+2
    lda sqr_rad+3
    sta temp1+3
    lda sqr_rad+4
    sta temp4
    lda sqr_rad+5
    sta temp4+1
    lda sqr_rad+6
    sta temp4+2
    lda sqr_rad+7
    sta temp4+3
    rts

mul_extract_shift31:
    lda sqr_rad
    asl sqr_rad+7
    rol sqr_rad+6
    rol sqr_rad+5
    rol sqr_rad+4
    rol sqr_rad+3
    rol sqr_rad+2
    rol sqr_rad+1
    rol sqr_rad
    jsr mul_extract_shift32
    rts

.segment "RUNTIME"

math_finalize_extended_to_fac:
    lda ext_mant
    ora ext_mant+1
    ora ext_mant+2
    ora ext_mant+3
    BEQ_FAR finalize_zero
finalize_normalize:
    lda ext_mant
    bmi finalize_round_check
    lda ext_exp
    BEQ_FAR finalize_zero
    dec ext_exp
    lda ext_extra+3
    and #1
    sta math_work+3
    asl ext_extra+3
    rol ext_extra+2
    rol ext_extra+1
    rol ext_extra
    rol ext_mant+3
    rol ext_mant+2
    rol ext_mant+1
    rol ext_mant
    lda math_work+3
    beq :+
    lda ext_extra+3
    ora #1
    sta ext_extra+3
:
    jmp finalize_normalize
finalize_round_check:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @nearest_even
    lda ext_extra
    ora ext_extra+1
    ora ext_extra+2
    ora ext_extra+3
    beq @nearest_even
    lda #IEEE_FLAG_INEXACT
    jsr ieee_raise_flags_a
    lda math_ieee_control
    and #$07
    cmp #1
    beq finalize_pack
    cmp #2
    beq @round_pos
    cmp #3
    beq @round_neg
    cmp #4
    beq @ties_away
    jmp @nearest_even
@round_pos:
    lda ext_sign
    bne finalize_pack
    jmp finalize_round_up
@round_neg:
    lda ext_sign
    beq finalize_pack
    jmp finalize_round_up
@ties_away:
    lda ext_extra
    cmp #$80
    bcc finalize_pack
    jmp finalize_round_up
.else
    jmp @nearest_even
.endif
@nearest_even:
    lda ext_extra
    cmp #$80
    bcc finalize_pack
    bne finalize_round_up
    lda ext_extra+1
    ora ext_extra+2
    ora ext_extra+3
    bne finalize_round_up
    lda ext_mant+3
    and #1
    beq finalize_pack
finalize_round_up:
    inc ext_mant+3
    bne finalize_pack
    inc ext_mant+2
    bne finalize_pack
    inc ext_mant+1
    bne finalize_pack
    inc ext_mant
    bne finalize_pack
    inc ext_exp
    beq finalize_overflow
    lda #$80
    sta ext_mant
    lda #0
    sta ext_mant+1
    sta ext_mant+2
    sta ext_mant+3
finalize_pack:
    lda ext_exp
    sta math_fac
    lda ext_mant
    and #$7f
    ora ext_sign
    sta math_fac+1
    lda ext_mant+1
    sta math_fac+2
    lda ext_mant+2
    sta math_fac+3
    lda ext_mant+3
    sta math_fac+4
    clc
    rts
finalize_zero:
    jsr math_load_zero
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @zero_done
    lda ext_sign
    sta math_fac+1
@zero_done:
.endif
    clc
    rts
finalize_overflow:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @legacy
    lda #(IEEE_FLAG_OVERFLOW | IEEE_FLAG_INEXACT)
    jsr ieee_raise_flags_a
    jsr ieee_load_inf_fac_sign
    clc
    rts
.endif
@legacy:
    sec
    rts

.segment "RUNTIME"

fma_accumulate_saved_addend:
    jsr math_copy_ext_to_sqr_rad
    jsr fma_load_saved_addend
    lda temp5
    cmp ext_exp
    beq fma_exponents_aligned
    bcc fma_shift_addend
    sec
    sbc ext_exp
    tay
    jsr fma_shift_ext_right_y_jam
    lda temp5
    sta ext_exp
    jmp fma_exponents_aligned
fma_shift_addend:
    lda ext_exp
    sec
    sbc temp5
    tay
    jsr fma_shift_addend_right_y_jam
fma_exponents_aligned:
    lda ext_sign
    eor math_class
    and #$80
    beq fma_same_sign
    jsr fma_compare_ext_addend
    beq fma_cancel_to_zero
    bcc fma_addend_larger
    jsr fma_subtract_addend_from_ext
    jmp fma_store_accumulator
fma_addend_larger:
    jsr fma_subtract_ext_from_addend
    lda math_class
    sta ext_sign
    jmp fma_store_accumulator
fma_same_sign:
    jsr fma_add_addend_to_ext
    bcc fma_store_accumulator
    jsr fma_shift_ext_right_one_with_carry_jam
    inc ext_exp
    beq fma_accumulate_overflow
fma_store_accumulator:
    jsr math_copy_sqr_rad_to_ext
    clc
    rts
fma_cancel_to_zero:
    lda #0
    sta ext_sign
    sta ext_exp
    sta ext_mant
    sta ext_mant+1
    sta ext_mant+2
    sta ext_mant+3
    sta ext_extra
    sta ext_extra+1
    sta ext_extra+2
    sta ext_extra+3
    clc
    rts
fma_accumulate_overflow:
    sec
    rts

fma_load_saved_addend:
    lda temp5+1
    and #$80
    sta math_class
    lda temp5+1
    and #$7f
    ora #$80
    sta mul_mcand
    lda temp5+2
    sta mul_mcand+1
    lda temp5+3
    sta mul_mcand+2
    lda temp5+4
    sta mul_mcand+3
    lda #0
    sta mul_mcand+4
    sta mul_mcand+5
    sta mul_mcand+6
    sta mul_mcand+7
    rts

fma_shift_ext_right_y_jam:
    cpy #0
    beq fma_shift_ext_done
    cpy #64
    bcc fma_shift_ext_loop
    jsr fma_zero_ext_with_sticky
    rts
fma_shift_ext_loop:
    jsr fma_shift_ext_right_one_jam
    dey
    bne fma_shift_ext_loop
fma_shift_ext_done:
    rts

fma_shift_addend_right_y_jam:
    cpy #0
    beq fma_shift_addend_done
    cpy #64
    bcc fma_shift_addend_loop
    jsr fma_zero_addend_with_sticky
    rts
fma_shift_addend_loop:
    jsr fma_shift_addend_right_one_jam
    dey
    bne fma_shift_addend_loop
fma_shift_addend_done:
    rts

fma_shift_ext_right_one_jam:
    lda sqr_rad+7
    and #1
    sta math_work+2
    clc
    ror sqr_rad
    ror sqr_rad+1
    ror sqr_rad+2
    ror sqr_rad+3
    ror sqr_rad+4
    ror sqr_rad+5
    ror sqr_rad+6
    ror sqr_rad+7
    lda math_work+2
    beq :+
    lda sqr_rad+7
    ora #1
    sta sqr_rad+7
:
    rts

fma_shift_addend_right_one_jam:
    lda mul_mcand+7
    and #1
    sta math_work+2
    clc
    ror mul_mcand
    ror mul_mcand+1
    ror mul_mcand+2
    ror mul_mcand+3
    ror mul_mcand+4
    ror mul_mcand+5
    ror mul_mcand+6
    ror mul_mcand+7
    lda math_work+2
    beq :+
    lda mul_mcand+7
    ora #1
    sta mul_mcand+7
:
    rts

fma_zero_ext_with_sticky:
    lda sqr_rad
    ora sqr_rad+1
    ora sqr_rad+2
    ora sqr_rad+3
    ora sqr_rad+4
    ora sqr_rad+5
    ora sqr_rad+6
    ora sqr_rad+7
    pha
    lda #0
    sta sqr_rad
    sta sqr_rad+1
    sta sqr_rad+2
    sta sqr_rad+3
    sta sqr_rad+4
    sta sqr_rad+5
    sta sqr_rad+6
    sta sqr_rad+7
    pla
    beq :+
    lda #1
    sta sqr_rad+7
:
    rts

fma_zero_addend_with_sticky:
    lda mul_mcand
    ora mul_mcand+1
    ora mul_mcand+2
    ora mul_mcand+3
    ora mul_mcand+4
    ora mul_mcand+5
    ora mul_mcand+6
    ora mul_mcand+7
    pha
    lda #0
    sta mul_mcand
    sta mul_mcand+1
    sta mul_mcand+2
    sta mul_mcand+3
    sta mul_mcand+4
    sta mul_mcand+5
    sta mul_mcand+6
    sta mul_mcand+7
    pla
    beq :+
    lda #1
    sta mul_mcand+7
:
    rts

fma_compare_ext_addend:
    ldy #0
fma_compare_ext_addend_loop:
    lda sqr_rad,y
    cmp mul_mcand,y
    bne fma_compare_ext_addend_done
    iny
    cpy #8
    bne fma_compare_ext_addend_loop
    lda #0
    rts
fma_compare_ext_addend_done:
    rts

fma_add_addend_to_ext:
    clc
    lda sqr_rad+7
    adc mul_mcand+7
    sta sqr_rad+7
    lda sqr_rad+6
    adc mul_mcand+6
    sta sqr_rad+6
    lda sqr_rad+5
    adc mul_mcand+5
    sta sqr_rad+5
    lda sqr_rad+4
    adc mul_mcand+4
    sta sqr_rad+4
    lda sqr_rad+3
    adc mul_mcand+3
    sta sqr_rad+3
    lda sqr_rad+2
    adc mul_mcand+2
    sta sqr_rad+2
    lda sqr_rad+1
    adc mul_mcand+1
    sta sqr_rad+1
    lda sqr_rad
    adc mul_mcand
    sta sqr_rad
    rts

fma_subtract_addend_from_ext:
    lda sqr_rad+7
    sec
    sbc mul_mcand+7
    sta sqr_rad+7
    lda sqr_rad+6
    sbc mul_mcand+6
    sta sqr_rad+6
    lda sqr_rad+5
    sbc mul_mcand+5
    sta sqr_rad+5
    lda sqr_rad+4
    sbc mul_mcand+4
    sta sqr_rad+4
    lda sqr_rad+3
    sbc mul_mcand+3
    sta sqr_rad+3
    lda sqr_rad+2
    sbc mul_mcand+2
    sta sqr_rad+2
    lda sqr_rad+1
    sbc mul_mcand+1
    sta sqr_rad+1
    lda sqr_rad
    sbc mul_mcand
    sta sqr_rad
    rts

fma_subtract_ext_from_addend:
    lda mul_mcand+7
    sec
    sbc sqr_rad+7
    sta sqr_rad+7
    lda mul_mcand+6
    sbc sqr_rad+6
    sta sqr_rad+6
    lda mul_mcand+5
    sbc sqr_rad+5
    sta sqr_rad+5
    lda mul_mcand+4
    sbc sqr_rad+4
    sta sqr_rad+4
    lda mul_mcand+3
    sbc sqr_rad+3
    sta sqr_rad+3
    lda mul_mcand+2
    sbc sqr_rad+2
    sta sqr_rad+2
    lda mul_mcand+1
    sbc sqr_rad+1
    sta sqr_rad+1
    lda mul_mcand
    sbc sqr_rad
    sta sqr_rad
    rts

fma_shift_ext_right_one_with_carry_jam:
    lda sqr_rad+7
    and #1
    sta math_work+2
    sec
    ror sqr_rad
    ror sqr_rad+1
    ror sqr_rad+2
    ror sqr_rad+3
    ror sqr_rad+4
    ror sqr_rad+5
    ror sqr_rad+6
    ror sqr_rad+7
    lda math_work+2
    beq :+
    lda sqr_rad+7
    ora #1
    sta sqr_rad+7
:
    rts

math_copy_ext_to_sqr_rad:
    lda ext_mant
    sta sqr_rad
    lda ext_mant+1
    sta sqr_rad+1
    lda ext_mant+2
    sta sqr_rad+2
    lda ext_mant+3
    sta sqr_rad+3
    lda ext_extra
    sta sqr_rad+4
    lda ext_extra+1
    sta sqr_rad+5
    lda ext_extra+2
    sta sqr_rad+6
    lda ext_extra+3
    sta sqr_rad+7
    rts

math_copy_sqr_rad_to_ext:
    lda sqr_rad
    sta ext_mant
    lda sqr_rad+1
    sta ext_mant+1
    lda sqr_rad+2
    sta ext_mant+2
    lda sqr_rad+3
    sta ext_mant+3
    lda sqr_rad+4
    sta ext_extra
    lda sqr_rad+5
    sta ext_extra+1
    lda sqr_rad+6
    sta ext_extra+2
    lda sqr_rad+7
    sta ext_extra+3
    rts

math_copy_mul_mcand_to_ext:
    lda mul_mcand
    sta ext_mant
    lda mul_mcand+1
    sta ext_mant+1
    lda mul_mcand+2
    sta ext_mant+2
    lda mul_mcand+3
    sta ext_mant+3
    lda mul_mcand+4
    sta ext_extra
    lda mul_mcand+5
    sta ext_extra+1
    lda mul_mcand+6
    sta ext_extra+2
    lda mul_mcand+7
    sta ext_extra+3
    rts

basic_math_poly_eval:
    lda math_input_ptr
    sta math_coeff_ptr
    lda math_input_ptr+1
    sta math_coeff_ptr+1
    jmp basic_math_poly_eval_coeff

basic_math_poly_eval_coeff:
    ; temp4 aliases ext_extra and is destroyed by every multiply/FMA.  Keep
    ; the Horner variable in its dedicated persistent slot instead.
    ldx #0
@save_x:
    lda math_fac,x
    sta poly_x,x
    inx
    cpx #5
    bne @save_x
    ldy #0
    lda (math_coeff_ptr),y
    sta poly_degree
    clc
    lda math_coeff_ptr
    adc #1
    sta math_output_ptr
    lda math_coeff_ptr+1
    adc #0
    sta math_output_ptr+1
    sta poly_ptr_save+1
    lda math_output_ptr
    sta poly_ptr_save
    jsr poly_load_coeff_to_fac
    lda math_output_ptr
    sta poly_ptr_save
    lda math_output_ptr+1
    sta poly_ptr_save+1
    lda poly_degree
    beq poly_done
poly_loop:
    ldx #0
@load_x:
    lda poly_x,x
    sta math_arg,x
    inx
    cpx #5
    bne @load_x
    lda #TYPE_FLOAT
    sta math_fac_type
    sta math_arg_type
    jsr basic_math_multiply
    BCS_FAR math_fail_current
    lda poly_ptr_save
    sta math_coeff_ptr
    lda poly_ptr_save+1
    sta math_coeff_ptr+1
    ldy #0
@load_coeff:
    lda (math_coeff_ptr),y
    sta math_arg,y
    iny
    cpy #5
    bne @load_coeff
    lda #TYPE_FLOAT
    sta math_fac_type
    sta math_arg_type
    jsr basic_math_add
    BCS_FAR math_fail_current
    clc
    lda poly_ptr_save
    adc #5
    sta poly_ptr_save
    lda poly_ptr_save+1
    adc #0
    sta poly_ptr_save+1
    dec poly_degree
    bne poly_loop
poly_done:
    jmp math_success

.segment "RUNTIME"

basic_math_poly_eval_even:
    jsr basic_math_square
    BCS_FAR math_fail_current
    jmp basic_math_poly_eval_coeff

basic_math_poly_eval_odd:
    ldx #4
poly_odd_save_x:
    lda math_fac,x
    pha
    dex
    bpl poly_odd_save_x
    ; math_coeff_ptr shares the generated temporary pointer with arithmetic
    ; input/output helpers.  Squaring the argument is therefore allowed to
    ; consume it; preserve the coefficient-table address explicitly.
    lda math_coeff_ptr
    pha
    lda math_coeff_ptr+1
    pha
    jsr basic_math_square
    bcs poly_odd_restore_pointer_fail
    pla
    sta math_coeff_ptr+1
    pla
    sta math_coeff_ptr
    jsr basic_math_poly_eval_coeff
    BCS_FAR poly_odd_fail_saved
    jsr math_copy_fac_to_arg
    ldx #0
poly_odd_restore_x:
    pla
    sta math_fac,x
    inx
    cpx #5
    bne poly_odd_restore_x
    jmp basic_math_multiply
poly_odd_restore_pointer_fail:
    pla
    sta math_coeff_ptr+1
    pla
    sta math_coeff_ptr
poly_odd_fail_saved:
    ldx #0
poly_odd_discard_x:
    pla
    inx
    cpx #5
    bne poly_odd_discard_x
    sec
    rts

.segment "RUNTIME"

poly_load_coeff_to_fac:
    ldy #0
poly_load_coeff_loop:
    lda (math_output_ptr),y
    sta math_fac,y
    iny
    cpy #5
    bne poly_load_coeff_loop
    jmp poly_advance_coeff_ptr

poly_advance_coeff_ptr:
    clc
    lda math_output_ptr
    adc #5
    sta math_output_ptr
    lda math_output_ptr+1
    adc #0
    sta math_output_ptr+1
    rts

math_fac_code:
    lda math_fac+2
    ora math_fac+3
    ora math_fac+4
    bne fac_code_fail
    lda math_fac
    bne fac_code_nonzero
    lda math_fac+1
    bne fac_code_fail
    lda #0
    clc
    rts
fac_code_nonzero:
    cmp #$81
    beq fac_code_exp81
    cmp #$82
    beq fac_code_exp82
    cmp #$83
    beq fac_code_exp83
    cmp #$84
    beq fac_code_exp84
fac_code_fail:
    sec
    rts
fac_code_exp81:
    lda math_fac+1
    beq fac_code_one
    cmp #$80
    beq fac_code_neg_one
    jmp fac_code_fail
fac_code_one:
    lda #1
    clc
    rts
fac_code_neg_one:
    lda #$ff
    clc
    rts
fac_code_exp82:
    lda math_fac+1
    beq fac_code_two
    cmp #$40
    beq fac_code_three
    jmp fac_code_fail
fac_code_two:
    lda #2
    clc
    rts
fac_code_three:
    lda #3
    clc
    rts
fac_code_exp83:
    lda math_fac+1
    beq fac_code_four
    cmp #$20
    beq fac_code_five
    cmp #$40
    beq fac_code_six
    cmp #$60
    beq fac_code_seven
    jmp fac_code_fail
fac_code_four:
    lda #4
    clc
    rts
fac_code_five:
    lda #5
    clc
    rts
fac_code_six:
    lda #6
    clc
    rts
fac_code_seven:
    lda #7
    clc
    rts
fac_code_exp84:
    lda math_fac+1
    beq fac_code_eight
    cmp #$10
    beq fac_code_nine
    cmp #$20
    beq fac_code_ten
    cmp #$30
    beq fac_code_eleven
    cmp #$40
    beq fac_code_twelve
    cmp #$50
    beq fac_code_thirteen
    cmp #$60
    beq fac_code_fourteen
    cmp #$70
    beq fac_code_fifteen
    jmp fac_code_fail
fac_code_eight:
    lda #8
    clc
    rts
fac_code_nine:
    lda #9
    clc
    rts
fac_code_ten:
    lda #10
    clc
    rts
fac_code_eleven:
    lda #11
    clc
    rts
fac_code_twelve:
    lda #12
    clc
    rts
fac_code_thirteen:
    lda #13
    clc
    rts
fac_code_fourteen:
    lda #14
    clc
    rts
fac_code_fifteen:
    lda #15
    clc
    rts

math_load_code:
    cmp #$ff
    beq math_load_neg_one
    cmp #16
    bcs @fail
    tax
    lda math_load_code_offsets,x
    tax
    jmp math_load_const_at_x
@fail:
    sec
    rts

math_load_zero:
    ldx #0
    jmp math_load_const_at_x

math_load_one:
    ldx #5
    jmp math_load_const_at_x

math_load_two:
    ldx #10
    jmp math_load_const_at_x

math_load_three:
    ldx #15
    jmp math_load_const_at_x

math_load_four:
    ldx #20
    jmp math_load_const_at_x

math_load_five:
    ldx #25
    jmp math_load_const_at_x

math_load_six:
    ldx #30
    jmp math_load_const_at_x

math_load_seven:
    ldx #35
    jmp math_load_const_at_x

math_load_eight:
    ldx #40
    jmp math_load_const_at_x

math_load_nine:
    ldx #45
    jmp math_load_const_at_x

math_load_ten:
    ldx #50
    jmp math_load_const_at_x

math_load_eleven:
    ldx #55
    jmp math_load_const_at_x

math_load_twelve:
    ldx #60
    jmp math_load_const_at_x

math_load_thirteen:
    ldx #65
    jmp math_load_const_at_x

math_load_fourteen:
    ldx #70
    jmp math_load_const_at_x

math_load_fifteen:
    ldx #75
    jmp math_load_const_at_x

math_load_neg_one:
    ldx #80
math_load_const_at_x:
    ldy #0
@copy:
    lda math_load_const_table,x
    sta math_fac,y
    inx
    iny
    cpy #5
    bne @copy
    clc
    rts

math_load_code_offsets:
    .byte 0,5,10,15,20,25,30,35
    .byte 40,45,50,55,60,65,70,75

math_load_const_table:
    .byte $00,$00,$00,$00,$00
    .byte $81,$00,$00,$00,$00
    .byte $82,$00,$00,$00,$00
    .byte $82,$40,$00,$00,$00
    .byte $83,$00,$00,$00,$00
    .byte $83,$20,$00,$00,$00
    .byte $83,$40,$00,$00,$00
    .byte $83,$60,$00,$00,$00
    .byte $84,$00,$00,$00,$00
    .byte $84,$10,$00,$00,$00
    .byte $84,$20,$00,$00,$00
    .byte $84,$30,$00,$00,$00
    .byte $84,$40,$00,$00,$00
    .byte $84,$50,$00,$00,$00
    .byte $84,$60,$00,$00,$00
    .byte $84,$70,$00,$00,$00
    .byte $81,$80,$00,$00,$00

math_adaptive_fac_arg_to_float:
    jsr math_adaptive_fac_to_float
    jmp math_adaptive_arg_to_float

.segment "RUNTIME"
math_adaptive_fac_to_float:
    lda math_fac_type
    beq @done
    cmp #TYPE_INT1
    beq @fac_int1
    cmp #TYPE_INT2
    beq @fac_int2
    cmp #TYPE_INT3
    beq @fac_int3
@done:
    rts
@fac_int1:
    lda math_fac
    sta temp1
    bpl :+
    lda #$ff
    jmp :++
:
    lda #0
:
    sta temp1+1
    jsr math_temp1_int_to_fac_fast
    lda #TYPE_FLOAT
    sta math_fac_type
    rts
@fac_int2:
    lda math_fac
    sta temp1
    lda math_fac+1
    sta temp1+1
    jsr math_temp1_int_to_fac_fast
    lda #TYPE_FLOAT
    sta math_fac_type
    rts
@fac_int3:
    lda math_fac
    sta temp1
    lda math_fac+1
    sta temp1+1
    jsr math_temp1_uint_to_fac
    lda #TYPE_FLOAT
    sta math_fac_type
    rts

math_adaptive_arg_to_float:
    lda math_arg_type
    beq @done
    cmp #TYPE_INT1
    beq @arg_int1
    cmp #TYPE_INT2
    beq @arg_int2
    cmp #TYPE_INT3
    beq @arg_int3
@done:
    rts
@arg_int1:
    ldx #0
@arg_int1_save:
    lda math_fac,x
    sta temp3,x
    inx
    cpx #5
    bne @arg_int1_save
    lda math_arg
    sta temp2
    bpl :+
    lda #$ff
    jmp :++
:
    lda #0
:
    sta temp2+1
    lda temp2
    sta temp1
    lda temp2+1
    sta temp1+1
    jsr math_temp1_int_to_fac_fast
    jsr math_copy_fac_to_arg
    ldx #0
@arg_int1_restore:
    lda temp3,x
    sta math_fac,x
    inx
    cpx #5
    bne @arg_int1_restore
    lda #TYPE_FLOAT
    sta math_arg_type
    rts
@arg_int2:
    ldx #0
@arg_int2_save:
    lda math_fac,x
    sta temp3,x
    inx
    cpx #5
    bne @arg_int2_save
    lda math_arg
    sta temp2
    lda math_arg+1
    sta temp2+1
    lda temp2
    sta temp1
    lda temp2+1
    sta temp1+1
    jsr math_temp1_int_to_fac_fast
    jsr math_copy_fac_to_arg
    ldx #0
@arg_int2_restore:
    lda temp3,x
    sta math_fac,x
    inx
    cpx #5
    bne @arg_int2_restore
    lda #TYPE_FLOAT
    sta math_arg_type
    rts
@arg_int3:
    ldx #0
@arg_int3_save:
    lda math_fac,x
    sta temp3,x
    inx
    cpx #5
    bne @arg_int3_save
    lda math_arg
    sta temp1
    lda math_arg+1
    sta temp1+1
    jsr math_temp1_uint_to_fac
    jsr math_copy_fac_to_arg
    ldx #0
@arg_int3_restore:
    lda temp3,x
    sta math_fac,x
    inx
    cpx #5
    bne @arg_int3_restore
    lda #TYPE_FLOAT
    sta math_arg_type
    rts

.segment "RUNTIME"

math_copy_fac_to_arg:
    ldx #0
math_copy_fac_to_arg_loop:
    lda math_fac,x
    sta math_arg,x
    inx
    cpx #5
    bne math_copy_fac_to_arg_loop
    lda math_fac_type
    sta math_arg_type
    rts

math_copy_arg_to_fac:
    ldx #0
math_copy_arg_to_fac_loop:
    lda math_arg,x
    sta math_fac,x
    inx
    cpx #5
    bne math_copy_arg_to_fac_loop
    rts

math_copy_arg_to_fac_success:
    jsr math_copy_arg_to_fac
    lda math_arg_type
    sta math_fac_type
    jmp math_success

math_copy_fac_to_temp1:
    ldx #0
math_copy_fac_to_temp1_loop:
    lda math_fac,x
    sta temp1,x
    inx
    cpx #5
    bne math_copy_fac_to_temp1_loop
    rts

math_copy_arg_to_temp2:
    ldx #0
math_copy_arg_to_temp2_loop:
    lda math_arg,x
    sta temp2,x
    inx
    cpx #5
    bne math_copy_arg_to_temp2_loop
    rts

math_copy_fac_to_temp2:
    ldx #0
math_copy_fac_to_temp2_loop:
    lda math_fac,x
    sta temp2,x
    inx
    cpx #5
    bne math_copy_fac_to_temp2_loop
    rts

math_copy_fac_to_temp4:
    ldx #0
math_copy_fac_to_temp4_loop:
    lda math_fac,x
    sta poly_x,x
    inx
    cpx #5
    bne math_copy_fac_to_temp4_loop
    rts

math_copy_temp1_to_fac:
    ldx #0
math_copy_temp1_to_fac_loop:
    lda temp1,x
    sta math_fac,x
    inx
    cpx #5
    bne math_copy_temp1_to_fac_loop
    rts

math_copy_temp2_to_fac:
    ldx #0
math_copy_temp2_to_fac_loop:
    lda temp2,x
    sta math_fac,x
    inx
    cpx #5
    bne math_copy_temp2_to_fac_loop
    rts

math_copy_temp4_to_arg:
    ldx #0
math_copy_temp4_to_arg_loop:
    lda poly_x,x
    sta math_arg,x
    inx
    cpx #5
    bne math_copy_temp4_to_arg_loop
    rts

math_copy_fac_arg_to_temp12:
    jsr math_copy_fac_to_temp1
    jmp math_copy_arg_to_temp2

math_commit_temp1_to_fac_normalized:
    jsr math_copy_temp1_to_fac
    jmp basic_math_normalize_round

math_compare_temp_magnitudes:
    lda temp1
    cmp temp2
    bne math_compare_temp_exp_done
    lda temp1+1
    and #$7f
    sta math_work+1
    lda temp2+1
    and #$7f
    sta math_work+2
    lda math_work+1
    cmp math_work+2
    bne math_compare_temp_byte1_done
    lda temp1+2
    cmp temp2+2
    bne math_compare_temp_exp_done
    lda temp1+3
    cmp temp2+3
    bne math_compare_temp_exp_done
    lda temp1+4
    cmp temp2+4
math_compare_temp_exp_done:
    rts
math_compare_temp_byte1_done:
    lda math_work+1
    rts

math_load_temp1_to_sqr_rad64:
    lda temp1+1
    and #$7f
    ora #$80
    sta sqr_rad
    lda temp1+2
    sta sqr_rad+1
    lda temp1+3
    sta sqr_rad+2
    lda temp1+4
    sta sqr_rad+3
    lda #0
    sta sqr_rad+4
    sta sqr_rad+5
    sta sqr_rad+6
    sta sqr_rad+7
    rts

math_load_temp2_to_mul_mcand64:
    lda temp2+1
    and #$7f
    ora #$80
    sta mul_mcand
    lda temp2+2
    sta mul_mcand+1
    lda temp2+3
    sta mul_mcand+2
    lda temp2+4
    sta mul_mcand+3
    lda #0
    sta mul_mcand+4
    sta mul_mcand+5
    sta mul_mcand+6
    sta mul_mcand+7
    rts

math_prepare_div_operands:
    lda #0
    sta temp1
    sta temp2
    lda temp1+1
    and #$7f
    ora #$80
    sta temp1+1
    lda temp2+1
    and #$7f
    ora #$80
    sta temp2+1
    rts

math_divide_to_ext:
    jsr div_clear_quotient
    ldx #64
div_quot_loop:
    jsr div_shift_quotient_left
    jsr div_compare_remainder_divisor
    bcc div_quot_no_subtract
    jsr div_subtract_divisor
    inc sqr_rad+7
div_quot_no_subtract:
    dex
    beq div_quot_done
    jsr div_shift_remainder_left
    jmp div_quot_loop
div_quot_done:
    jsr math_copy_sqr_rad_to_ext
    lda temp1
    ora temp1+1
    ora temp1+2
    ora temp1+3
    ora temp1+4
    beq div_exact
    lda ext_extra+3
    ora #1
    sta ext_extra+3
div_exact:
    clc
    rts

div_clear_quotient:
    lda #0
    ldx #0
div_clear_quotient_loop:
    sta sqr_rad,x
    inx
    cpx #8
    bne div_clear_quotient_loop
    rts

div_shift_quotient_left:
    asl sqr_rad+7
    rol sqr_rad+6
    rol sqr_rad+5
    rol sqr_rad+4
    rol sqr_rad+3
    rol sqr_rad+2
    rol sqr_rad+1
    rol sqr_rad
    rts

div_compare_remainder_divisor:
    ldy #0
div_compare_remainder_loop:
    lda temp1,y
    cmp temp2,y
    bne div_compare_remainder_done
    iny
    cpy #5
    bne div_compare_remainder_loop
    sec
    rts
div_compare_remainder_done:
    rts

div_subtract_divisor:
    lda temp1+4
    sec
    sbc temp2+4
    sta temp1+4
    lda temp1+3
    sbc temp2+3
    sta temp1+3
    lda temp1+2
    sbc temp2+2
    sta temp1+2
    lda temp1+1
    sbc temp2+1
    sta temp1+1
    lda temp1
    sbc temp2
    sta temp1
    rts

.segment "RUNTIME"

.if CONFIG_IEEE_SUPPORT
ieee_raise_flags_a:
    ora math_ieee_flags
    sta math_ieee_flags
    rts

ieee_return_bool_a:
    beq @false
    lda #$ff
    sta math_fac
    jmp math_set_fac_a_int1_success
@false:
    lda #0
    sta math_fac
    sta math_fac+1
    sta math_fac+2
    sta math_fac+3
    sta math_fac+4
    lda #TYPE_INT1
    sta math_fac_type
    jmp math_success

ieee_pack_ax_to_fac:
    sta temp3
    stx temp3+1
    jsr math_pack_temp3_integer_to_fac
    clc
    rts

ieee_classify_fac_to_a:
    jsr math_adaptive_fac_to_float
    lda #0
    sta temp6
    lda math_fac+1
    and #$80
    beq :+
    lda temp6
    ora #IEEE_CLASS_SIGN
    sta temp6
:
    lda math_fac
    cmp #$ff
    beq @special
    lda math_fac
    bne @finite
    lda temp6
    ora #IEEE_CLASS_ZERO
    rts
@finite:
    lda temp6
    ora #IEEE_CLASS_FINITE
    rts
@special:
    lda math_fac+1
    and #$7f
    ora math_fac+2
    ora math_fac+3
    ora math_fac+4
    beq @inf
    lda temp6
    ora #IEEE_CLASS_NAN
    sta temp6
    lda math_fac+1
    and #$40
    bne :+
    lda temp6
    ora #IEEE_CLASS_SNAN
    sta temp6
:
    lda temp6
    rts
@inf:
    lda temp6
    ora #IEEE_CLASS_INF
    rts

ieee_classify_arg_to_a:
    lda math_fac_type
    pha
    ldx #0
@save:
    lda math_fac,x
    sta temp5,x
    lda math_arg,x
    sta math_fac,x
    inx
    cpx #5
    bne @save
    lda math_arg_type
    sta math_fac_type
    jsr ieee_classify_fac_to_a
    tay
    ldx #0
@restore:
    lda temp5,x
    sta math_fac,x
    inx
    cpx #5
    bne @restore
    pla
    sta math_fac_type
    tya
    rts

ieee_arg_to_signed_byte:
    lda math_arg_type
    cmp #TYPE_INT1
    beq @int1
    cmp #TYPE_INT2
    beq @int2
    sec
    rts
@int1:
    lda math_arg
    sta temp2
    clc
    rts
@int2:
    lda math_arg+1
    beq @int2_pos
    cmp #$ff
    bne @bad
    lda math_arg
    bpl @bad
    sta temp2
    clc
    rts
@int2_pos:
    lda math_arg
    bmi @bad
    sta temp2
    clc
    rts
@bad:
    sec
    rts

ieee_load_qnan_fac_invalid:
    lda #IEEE_FLAG_INVALID
    jsr ieee_raise_flags_a
ieee_load_qnan_fac:
    lda #TYPE_FLOAT
    sta math_fac_type
    lda #$ff
    sta math_fac
    lda #$40
    sta math_fac+1
    lda #0
    sta math_fac+2
    sta math_fac+3
    lda #1
    sta math_fac+4
    jmp math_success

ieee_load_inf_fac_sign:
    lda #TYPE_FLOAT
    sta math_fac_type
    lda #$ff
    sta math_fac
    lda ext_sign
    sta math_fac+1
    lda #0
    sta math_fac+2
    sta math_fac+3
    sta math_fac+4
    rts

ieee_load_zero_fac_sign:
    jsr math_load_zero
    lda ext_sign
    sta math_fac+1
    rts

ieee_quiet_fac_if_snan:
    lda math_fac
    cmp #$ff
    bne @done
    lda math_fac+1
    and #$7f
    ora math_fac+2
    ora math_fac+3
    ora math_fac+4
    beq @done
    lda math_fac+1
    and #$40
    bne @done
    lda math_fac+1
    ora #$40
    sta math_fac+1
    lda #IEEE_FLAG_INVALID
    jsr ieee_raise_flags_a
@done:
    rts

ieee_propagate_nan:
    jsr ieee_classify_fac_to_a
    and #IEEE_CLASS_NAN
    bne @fac_nan
    jsr math_copy_arg_to_fac
@fac_nan:
    jsr ieee_quiet_fac_if_snan
    jmp math_success

ieee_add_sub_special:
    jsr ieee_classify_fac_to_a
    sta temp6
    and #IEEE_CLASS_NAN
    bne @nan
    lda temp6
    pha
    jsr ieee_classify_arg_to_a
    sta temp6+1
    pla
    sta temp6
    lda temp6+1
    and #IEEE_CLASS_NAN
    bne @nan
    lda temp6
    and #IEEE_CLASS_INF
    beq @arg_inf
    lda temp6+1
    and #IEEE_CLASS_INF
    beq @handled_fac
    lda math_fac+1
    eor math_arg+1
    bmi @invalid
@handled_fac:
    jsr math_success
    sec
    rts
@arg_inf:
    lda temp6+1
    and #IEEE_CLASS_INF
    beq @not_handled
    jsr math_copy_arg_to_fac
    jsr math_success
    sec
    rts
@invalid:
    jsr ieee_load_qnan_fac_invalid
    sec
    rts
@nan:
    jsr ieee_propagate_nan
    sec
    rts
@not_handled:
    clc
    rts

ieee_multiply_special:
    lda math_fac+1
    eor math_arg+1
    and #$80
    sta ext_sign
    jsr ieee_classify_fac_to_a
    sta temp6
    and #IEEE_CLASS_NAN
    bne @nan
    lda temp6
    pha
    jsr ieee_classify_arg_to_a
    sta temp6+1
    pla
    sta temp6
    lda temp6+1
    and #IEEE_CLASS_NAN
    bne @nan
    lda temp6
    and #IEEE_CLASS_INF
    beq @fac_not_inf
    lda temp6+1
    and #IEEE_CLASS_ZERO
    bne @invalid
    jsr ieee_load_inf_fac_sign
    jsr math_success
    sec
    rts
@fac_not_inf:
    lda temp6+1
    and #IEEE_CLASS_INF
    beq @not_handled
    lda temp6
    and #IEEE_CLASS_ZERO
    bne @invalid
    jsr ieee_load_inf_fac_sign
    jsr math_success
    sec
    rts
@invalid:
    jsr ieee_load_qnan_fac_invalid
    sec
    rts
@nan:
    jsr ieee_propagate_nan
    sec
    rts
@not_handled:
    clc
    rts

ieee_divide_special:
    lda math_fac+1
    eor math_arg+1
    and #$80
    sta ext_sign
    jsr ieee_classify_fac_to_a
    sta temp6
    and #IEEE_CLASS_NAN
    bne @nan
    lda temp6
    pha
    jsr ieee_classify_arg_to_a
    sta temp6+1
    pla
    sta temp6
    lda temp6+1
    and #IEEE_CLASS_NAN
    bne @nan
    lda temp6
    and #IEEE_CLASS_INF
    beq @fac_not_inf
    lda temp6+1
    and #IEEE_CLASS_INF
    bne @invalid
    jsr ieee_load_inf_fac_sign
    jsr math_success
    sec
    rts
@fac_not_inf:
    lda temp6+1
    and #IEEE_CLASS_INF
    beq @arg_not_inf
    jsr ieee_load_zero_fac_sign
    jsr math_success
    sec
    rts
@arg_not_inf:
    lda temp6+1
    and #IEEE_CLASS_ZERO
    beq @not_handled
    lda temp6
    and #IEEE_CLASS_ZERO
    bne @invalid
    lda #IEEE_FLAG_DIV_ZERO
    jsr ieee_raise_flags_a
    jsr ieee_load_inf_fac_sign
    jsr math_success
    sec
    rts
@invalid:
    jsr ieee_load_qnan_fac_invalid
    sec
    rts
@nan:
    jsr ieee_propagate_nan
    sec
    rts
@not_handled:
    clc
    rts

ieee_square_special:
    jsr ieee_classify_fac_to_a
    sta temp6
    and #IEEE_CLASS_NAN
    bne @nan
    lda temp6
    and #IEEE_CLASS_INF
    beq @not_handled
    lda #0
    sta math_fac+1
    jsr math_success
    sec
    rts
@nan:
    jsr ieee_quiet_fac_if_snan
    jsr math_success
    sec
    rts
@not_handled:
    clc
    rts

ieee_sqr_special:
    jsr ieee_classify_fac_to_a
    sta temp6
    and #IEEE_CLASS_NAN
    bne @nan
    lda temp6
    and #IEEE_CLASS_INF
    bne @inf
    lda temp6
    and #IEEE_CLASS_ZERO
    bne @zero
    lda temp6
    and #IEEE_CLASS_SIGN
    bne @invalid
    clc
    rts
@inf:
    lda temp6
    and #IEEE_CLASS_SIGN
    bne @invalid
    jsr math_success
    sec
    rts
@zero:
    jsr math_success
    sec
    rts
@nan:
    jsr ieee_quiet_fac_if_snan
    jsr math_success
    sec
    rts
@invalid:
    jsr ieee_load_qnan_fac_invalid
    sec
    rts

ieee_log_special:
    jsr ieee_classify_fac_to_a
    sta temp6
    and #IEEE_CLASS_NAN
    bne @nan
    lda temp6
    and #IEEE_CLASS_ZERO
    bne @zero
    lda temp6
    and #IEEE_CLASS_INF
    bne @inf
    lda temp6
    and #IEEE_CLASS_SIGN
    bne @invalid
    clc
    rts
@zero:
    lda #IEEE_FLAG_DIV_ZERO
    jsr ieee_raise_flags_a
    lda #$80
    sta ext_sign
    jsr ieee_load_inf_fac_sign
    jsr math_success
    sec
    rts
@inf:
    lda temp6
    and #IEEE_CLASS_SIGN
    bne @invalid
    jsr math_success
    sec
    rts
@nan:
    jsr ieee_quiet_fac_if_snan
    jsr math_success
    sec
    rts
@invalid:
    jsr ieee_load_qnan_fac_invalid
    sec
    rts

basic_math_rem_ieee:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @unsupported
    jsr ieee_classify_fac_to_a
    sta temp6
    and #(IEEE_CLASS_NAN | IEEE_CLASS_INF)
    bne @invalid
.endif
    jsr ieee_classify_arg_to_a
    sta temp6+1
    and #IEEE_CLASS_NAN
    bne @invalid
    lda temp6+1
    and #IEEE_CLASS_ZERO
    bne @invalid
    lda temp6+1
    and #IEEE_CLASS_INF
    beq @unsupported
    jmp math_success
@invalid:
    jmp ieee_load_qnan_fac_invalid
@unsupported:
    jmp math_unsupported

basic_math_scalb:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @unsupported
    jsr ieee_classify_fac_to_a
    sta temp6
    and #IEEE_CLASS_NAN
    bne @nan
.endif
    lda temp6
    and #(IEEE_CLASS_INF | IEEE_CLASS_ZERO)
    bne @unchanged
    lda temp6
    and #IEEE_CLASS_FINITE
    beq @unsupported
    jsr ieee_arg_to_signed_byte
    bcs @unsupported
    lda math_fac
    sta temp1
    lda temp2
    bmi @scale_down
    lda temp1
    clc
    adc temp2
    bcs @overflow
    beq @underflow
    sta math_fac
    jmp math_success
@scale_down:
    lda temp2
    eor #$ff
    clc
    adc #1
    sta temp2
    lda temp1
    sec
    sbc temp2
    beq @underflow
    bcc @underflow
    sta math_fac
    jmp math_success
@overflow:
    lda #(IEEE_FLAG_OVERFLOW | IEEE_FLAG_INEXACT)
    jsr ieee_raise_flags_a
    lda math_fac+1
    and #$80
    sta ext_sign
    jsr ieee_load_inf_fac_sign
    jmp math_success
@underflow:
    lda #(IEEE_FLAG_UNDERFLOW | IEEE_FLAG_INEXACT)
    jsr ieee_raise_flags_a
    lda math_fac+1
    and #$80
    sta ext_sign
    jsr ieee_load_zero_fac_sign
    jmp math_success
@nan:
    jsr ieee_quiet_fac_if_snan
@unchanged:
    jmp math_success
@unsupported:
    jmp math_unsupported

basic_math_logb:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @unsupported
    jsr ieee_classify_fac_to_a
    sta temp6
    and #IEEE_CLASS_NAN
    bne @nan
.endif
    lda temp6
    and #IEEE_CLASS_INF
    bne @pos_inf
    lda temp6
    and #IEEE_CLASS_ZERO
    bne @neg_inf
    lda math_fac
    sec
    sbc #$81
    pha
    bpl :+
    ldx #$ff
    bne :++
:
    ldx #0
:
    pla
    jmp ieee_pack_ax_to_fac
@pos_inf:
    lda #$00
    sta ext_sign
    jsr ieee_load_inf_fac_sign
    jmp math_success
@neg_inf:
    lda #IEEE_FLAG_DIV_ZERO
    jsr ieee_raise_flags_a
    lda #$80
    sta ext_sign
    jsr ieee_load_inf_fac_sign
    jmp math_success
@nan:
    jsr ieee_quiet_fac_if_snan
    jmp math_success
@unsupported:
    jmp math_unsupported

basic_math_mant:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @unsupported
    jsr ieee_classify_fac_to_a
    sta temp6
    and #IEEE_CLASS_NAN
    bne @nan
.endif
    lda temp6
    and #(IEEE_CLASS_INF | IEEE_CLASS_ZERO)
    bne @unchanged
    lda temp6
    and #IEEE_CLASS_FINITE
    beq @unsupported
    lda #$81
    sta math_fac
    lda math_fac+1
    and #$7f
    sta math_fac+1
@unchanged:
    jmp math_success
@nan:
    jsr ieee_quiet_fac_if_snan
    jmp math_success
@unsupported:
    jmp math_unsupported

basic_math_rint:
.if CONFIG_IEEE_SUPPORT
    lda math_ieee_mode
    and #IEEE_MODE_ENABLE
    beq @legacy
    jsr ieee_classify_fac_to_a
    and #(IEEE_CLASS_NAN | IEEE_CLASS_INF | IEEE_CLASS_ZERO)
    beq @legacy
    jsr ieee_quiet_fac_if_snan
.endif
    jmp math_success
@legacy:
    jmp basic_math_round_nearest_even

.endif

div_shift_remainder_left:
    asl temp1+4
    rol temp1+3
    rol temp1+2
    rol temp1+1
    rol temp1
    rts

math_write_one_char:
    ldy #0
    sta (math_output_ptr),y
    iny
    lda #0
    sta (math_output_ptr),y
    rts

math_success:
    lda #MATH_OK
    sta math_status
    clc
    rts

math_unsupported:
    lda #MATH_ERR_UNSUPPORTED
    jmp math_fail_a

math_set_fac_a_int1_success:
    sta math_fac
    lda #TYPE_INT1
    sta math_fac_type
math_clear_fac_tail_success:
    lda #0
    sta math_fac+1
    sta math_fac+2
    sta math_fac+3
    sta math_fac+4
    clc
    rts

math_clear_fac_tail:
    lda #0
    sta math_fac+2
    sta math_fac+3
    sta math_fac+4
    clc
    rts

.segment "RUNTIME"

math_fail_current:
    sec
    rts


math_fail_a:
    sta math_status
    sec
    rts

math_load_pi:
    ldx #0
:   lda const_pi,x
    sta math_fac,x
    inx
    cpx #5
    bne :-
    rts


.segment "RUNTIME"

; ---------------------------------------------------------------------------
; math_classify_fac_adaptive
; Classifies a FLOAT FAC into the most compact adaptive integer type if possible.
; Returns CC if classified, CS if stays float.
; ---------------------------------------------------------------------------
math_classify_fac_adaptive:
    lda math_fac
    bne @nonzero
    lda math_fac+1
    ora math_fac+2
    ora math_fac+3
    ora math_fac+4
    beq :+
    sec
    rts
:
    lda #TYPE_INT1
    sta math_fac_type
    lda #0
    sta math_fac
    jmp math_clear_fac_tail

@nonzero:
    sec
    sbc #$81
    bcs :+
    rts
:
    cmp #16
    bcc :+
    rts
:
    sta temp4

    lda math_fac+1
    and #$80
    sta temp5
    lda math_fac+1
    and #$7f
    ora #$80
    sta temp1
    lda math_fac+2
    sta temp1+1
    lda math_fac+3
    sta temp2
    lda math_fac+4
    sta temp2+1

    lda #31
    sec
    sbc temp4
    sta temp4
    lda #0
    sta temp3
@shift_loop:
    lsr temp1
    ror temp1+1
    ror temp2
    ror temp2+1
    bcc :+
    lda #1
    sta temp3
:
    dec temp4
    bne @shift_loop

    lda temp3
    bne @float
    lda temp1
    ora temp1+1
    bne @float

    lda temp5
    beq @positive

    lda temp2
    cmp #$80
    bcc @ok_neg
    bne @float
    lda temp2+1
    bne @float
@ok_neg:
    lda temp2+1
    eor #$ff
    clc
    adc #1
    sta temp3
    lda temp2
    eor #$ff
    adc #0
    sta temp3+1
    jmp math_pack_temp3_integer_to_fac

@positive:
    lda temp2+1
    sta temp3
    lda temp2
    sta temp3+1
    jmp math_pack_temp3_integer_to_fac

@float:
    sec
    rts

math_fac_uint16:
    lda math_fac_type
    cmp #TYPE_INT1
    beq @fac_int1
    cmp #TYPE_INT2
    beq @fac_int2
    cmp #TYPE_INT3
    beq @fac_int3
    sec
    rts
@fac_int1:
    lda math_fac
    sta temp1
    bpl :+
    lda #$ff
    jmp :++
:
    lda #0
:
    sta temp1+1
    clc
    rts
@fac_int2:
@fac_int3:
    lda math_fac
    sta temp1
    lda math_fac+1
    sta temp1+1
    clc
    rts

math_arg_uint16:
    lda math_arg_type
    cmp #TYPE_INT1
    beq @arg_int1
    cmp #TYPE_INT2
    beq @arg_int2
    cmp #TYPE_INT3
    beq @arg_int3
    sec
    rts
@arg_int1:
    lda math_arg
    sta temp2
    lda #0
    sta temp2+1
    clc
    rts
@arg_int2:
@arg_int3:
    lda math_arg
    sta temp2
    lda math_arg+1
    sta temp2+1
    clc
    rts

.segment "RUNTIME"






; ---- Adapted from basic v3/basic/numeric/constants.s ----
; Numeric constants in the runtime 5-byte C64 float format:
; [exponent, mantissa_hi/sign, mantissa_mid_hi, mantissa_mid_lo, mantissa_lo].

.export const_half
.export const_one
.export const_two
.export const_pi
.export const_half_pi
.export const_quarter_pi
.export const_two_pi_inv
.export const_trig_resid_half
.export const_trig_resid_pi
.export const_ln2
.export const_ln2_reduce_hi
.export const_ln2_reduce_err
.export const_half_ln2
.export const_half_ln2_reduce_hi
.export const_inv_ln2
.export const_half_pi_reduce_err
.export const_atn_low
.export const_atn_high
; FRE baseline constant used by the profile-aware runtime query.
.export const_fre_bytes

.segment "RUNTIME"

const_half:       .byte $80,$00,$00,$00,$00
const_one:        .byte $81,$00,$00,$00,$00
const_two:        .byte $82,$00,$00,$00,$00
const_pi:         .byte $82,$49,$0f,$da,$a2
const_half_pi:    .byte $81,$49,$0f,$da,$a2
const_quarter_pi: .byte $80,$49,$0f,$da,$a2
const_two_pi_inv: .byte $7e,$22,$f9,$83,$6e
const_trig_resid_half: .byte $5f,$05,$a3,$08,$d3
const_trig_resid_pi:   .byte $60,$05,$a3,$08,$d3
const_ln2:        .byte $80,$31,$72,$17,$f8
const_ln2_reduce_hi: .byte $80,$31,$72,$17,$c0
const_ln2_reduce_err: .byte $66,$df,$47,$3d,$e0
const_half_ln2:   .byte $7f,$31,$72,$17,$f8
const_half_ln2_reduce_hi: .byte $7f,$31,$72,$17,$c0
const_inv_ln2:    .byte $81,$38,$aa,$3b,$29
const_half_pi_reduce_err: .byte $5f,$85,$a3,$00,$00
const_atn_low:    .byte $7f,$60,$00,$00,$00  ; 0.4375
const_atn_high:   .byte $82,$1c,$00,$00,$00  ; 2.4375
const_fre_bytes:
    .byte BASIC_INITIAL_FRE_FLOAT_0
    .byte BASIC_INITIAL_FRE_FLOAT_1
    .byte BASIC_INITIAL_FRE_FLOAT_2
    .byte BASIC_INITIAL_FRE_FLOAT_3
    .byte BASIC_INITIAL_FRE_FLOAT_4


; ---- Adapted from basic v3/basic/numeric/coeffs.s ----
; Starter polynomial coefficient tables, quantized to the runtime 5-byte
; C64 float format. Tables are stored high-degree coefficient first for
; basic_math_poly_eval's Horner evaluator: [degree], cN, ..., c0.

.export coeff_log_taylor3_u
.export coeff_log_taylor6_u
.export coeff_log_atanh5_u
.export coeff_exp_taylor4
.export coeff_sin_remez7_u
.export coeff_cos_remez6_u
.export coeff_tan_remez5_u
.export coeff_atn_remez7_u

.segment "RUNTIME"

coeff_log_taylor3_u:
    .byte 5
    .byte $7e,$79,$fd,$64,$be
    .byte $7e,$5b,$11,$1f,$76
    .byte $7f,$12,$89,$c0,$bd
    .byte $7f,$4c,$cb,$15,$8a
    .byte $80,$2a,$aa,$ac,$ca
    .byte $82,$00,$00,$00,$00

const_sqrt_two:
    .byte $81,$35,$04,$f3,$34

const_log1p_fast_limit:
    .byte $7c,$00,$00,$00,$00

; Degree-6 log1p(y) polynomial for |y| <= 1/32.
; Coefficients are c6..c0 for Horner evaluation in y.
coeff_log_taylor6_u:
    .byte 6
    .byte $7e,$aa,$aa,$aa,$ab
    .byte $7e,$4c,$cc,$cc,$cd
    .byte $7f,$80,$00,$00,$00
    .byte $7f,$2a,$aa,$aa,$ab
    .byte $80,$80,$00,$00,$00
    .byte $81,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00

; Degree-5 centered atanh polynomial:
; P(u)=2*(1 + u/3 + u^2/5 + ... + u^5/11), LOG(m)=z*P(z*z).
coeff_log_atanh5_u:
    .byte 5
log_atanh_c5:
    .byte $7e,$3a,$2e,$8b,$a3
log_atanh_c4:
    .byte $7e,$63,$8e,$38,$e4
log_atanh_c3:
    .byte $7f,$12,$49,$24,$92
log_atanh_c2:
    .byte $7f,$4c,$cc,$cc,$cd
log_atanh_c1:
    .byte $80,$2a,$aa,$aa,$ab
log_atanh_c0:
    .byte $82,$00,$00,$00,$00

coeff_exp_taylor4:
    .byte 7
    .byte $74,$50,$be,$f9,$76
    .byte $77,$36,$d3,$a9,$8c
    .byte $7a,$08,$88,$53,$11
    .byte $7c,$2a,$aa,$32,$50
    .byte $7e,$2a,$aa,$aa,$bf
    .byte $80,$00,$00,$00,$2e
    .byte $81,$00,$00,$00,$00
    .byte $81,$00,$00,$00,$00

; Dense parity-aware tables for kernels evaluated in u=x*x.
; Odd functions are reconstructed as x*P(u); even functions as P(u).

coeff_sin_remez7_u:
    .byte 4
    .byte $6e,$36,$5b,$a4,$b5
    .byte $74,$d0,$07,$73,$f3
    .byte $7a,$08,$88,$83,$a6
    .byte $7e,$aa,$aa,$aa,$a5
    .byte $81,$00,$00,$00,$00

coeff_cos_remez6_u:
    .byte 4
    .byte $71,$4c,$83,$49,$f9
    .byte $77,$b6,$03,$c2,$08
    .byte $7c,$2a,$aa,$9d,$40
    .byte $7f,$ff,$ff,$ff,$df
    .byte $81,$00,$00,$00,$00

coeff_tan_remez5_u:
    .byte 8
    .byte $78,$06,$ed,$0c,$6a
    .byte $76,$a8,$60,$91,$07
    .byte $79,$25,$40,$1b,$87
    .byte $7a,$08,$07,$69,$5c
    .byte $7b,$34,$2c,$e2,$95
    .byte $7c,$5c,$fd,$b8,$eb
    .byte $7e,$08,$88,$c7,$8e
    .byte $7f,$2a,$aa,$a9,$ee
    .byte $81,$00,$00,$00,$00

coeff_atn_remez7_u:
    .byte 6
    .byte $7c,$36,$cc,$db,$93
    .byte $7d,$aa,$ad,$64,$1c
    .byte $7d,$61,$a4,$60,$61
    .byte $7e,$92,$39,$3b,$54
    .byte $7e,$4c,$cc,$4d,$1a
    .byte $7f,$aa,$aa,$a9,$e9
    .byte $81,$00,$00,$00,$00


