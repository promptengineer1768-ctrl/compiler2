; Generated from a trusted skeleton profile. Do not rename entries.

; math_bin32str: BIN32$: value → "XXXXXXXX" hex
; Inputs: FAC1=value
; Outputs: string in buffer
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Converts to IEEE 754 binary32 hex string
.export math_bin32str
.proc math_bin32str
    .error "skeleton requires implementation"
.endproc

; math_copysign: Copy sign
; Inputs: FAC1=value1, ARG=value2
; Outputs: FAC1=abs(value1) with sign(value2)
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: none
.export math_copysign
.proc math_copysign
    .error "skeleton requires implementation"
.endproc

; math_exp: EXP
; Inputs: FAC1=value
; Outputs: FAC1=exp(value)
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: Updates IEEE flags when enabled
.export math_exp
.proc math_exp
    .error "skeleton requires implementation"
.endproc

; math_fma: Fused multiply-add
; Inputs: X/Y=typed `(a,b,c)` operand record
; Outputs: FAC1=(a×b)+c
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg, write:zp_iesstp
; Side effects: none
.export math_fma
.proc math_fma
    .error "skeleton requires implementation"
.endproc

; math_isfin: Is finite
; Inputs: FAC1=value
; Outputs: A=0/1
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_isfin
.proc math_isfin
    .error "skeleton requires implementation"
.endproc

; math_isinf: Is infinite
; Inputs: FAC1=value
; Outputs: A=0/1
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_isinf
.proc math_isinf
    .error "skeleton requires implementation"
.endproc

; math_isnan: Is NaN
; Inputs: FAC1=value
; Outputs: A=0/1
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_isnan
.proc math_isnan
    .error "skeleton requires implementation"
.endproc

; math_isnorm: Is normalized
; Inputs: FAC1=value
; Outputs: A=0/1
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_isnorm
.proc math_isnorm
    .error "skeleton requires implementation"
.endproc

; math_issnan: Is signaling NaN
; Inputs: FAC1=value
; Outputs: A=0/1
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_issnan
.proc math_issnan
    .error "skeleton requires implementation"
.endproc

; math_isunord: Is unordered (either NaN)
; Inputs: FAC1=a, ARG=b
; Outputs: A=0/1
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: none
.export math_isunord
.proc math_isunord
    .error "skeleton requires implementation"
.endproc

; math_iszero: Is zero
; Inputs: FAC1=value
; Outputs: A=0/1
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_iszero
.proc math_iszero
    .error "skeleton requires implementation"
.endproc

; math_log: LOG (natural)
; Inputs: FAC1=value
; Outputs: FAC1=log(value)
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: Updates IEEE flags when enabled
.export math_log
.proc math_log
    .error "skeleton requires implementation"
.endproc

; math_logb: Unbiased base-2 exponent
; Inputs: FAC1=value
; Outputs: FAC1=unbiased exponent
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_logb
.proc math_logb
    .error "skeleton requires implementation"
.endproc

; math_mant: Extract mantissa
; Inputs: FAC1=value
; Outputs: FAC1=mantissa
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_mant
.proc math_mant
    .error "skeleton requires implementation"
.endproc

; math_max: IEEE maximum
; Inputs: FAC1=a, ARG=b
; Outputs: FAC1=max(a,b)
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: none
.export math_max
.proc math_max
    .error "skeleton requires implementation"
.endproc

; math_min: IEEE minimum
; Inputs: FAC1=a, ARG=b
; Outputs: FAC1=min(a,b)
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: none
.export math_min
.proc math_min
    .error "skeleton requires implementation"
.endproc

; math_nextdown: NextDown
; Inputs: FAC1=value
; Outputs: FAC1=next smaller representable
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_nextdown
.proc math_nextdown
    .error "skeleton requires implementation"
.endproc

; math_nextup: NextUp
; Inputs: FAC1=value
; Outputs: FAC1=next larger representable
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_nextup
.proc math_nextup
    .error "skeleton requires implementation"
.endproc

; math_pow: Exponentiation
; Inputs: FAC1=base, ARG=exponent
; Outputs: FAC1=result
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: Updates IEEE flags when enabled
.export math_pow
.proc math_pow
    .error "skeleton requires implementation"
.endproc

; math_remain: IEEE remainder
; Inputs: FAC1=a, ARG=b
; Outputs: FAC1=remainder(a/b)
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: none
.export math_remain
.proc math_remain
    .error "skeleton requires implementation"
.endproc

; math_rint: Round to integer per rounding mode
; Inputs: FAC1=value
; Outputs: FAC1=rounded integer
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_rint
.proc math_rint
    .error "skeleton requires implementation"
.endproc

; math_rnd: RND
; Inputs: FAC1=argument
; Outputs: FAC1=random value
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: Updates deterministic RND state per profile
.export math_rnd
.proc math_rnd
    .error "skeleton requires implementation"
.endproc

; math_scalb: Scale by power of 2
; Inputs: FAC1=value, X=exponent
; Outputs: FAC1=value×2^exp
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_scalb
.proc math_scalb
    .error "skeleton requires implementation"
.endproc

; math_sgnbit: Sign bit extraction
; Inputs: FAC1=value
; Outputs: A=sign bit (0/1)
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_sgnbit
.proc math_sgnbit
    .error "skeleton requires implementation"
.endproc

; math_sqr: SQR
; Inputs: FAC1=value
; Outputs: FAC1=sqrt(value)
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: Updates IEEE flags when enabled
.export math_sqr
.proc math_sqr
    .error "skeleton requires implementation"
.endproc

; math_totalorder: Total ordering comparison
; Inputs: FAC1=a, ARG=b
; Outputs: A=comparison result
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: none
.export math_totalorder
.proc math_totalorder
    .error "skeleton requires implementation"
.endproc

; math_val32: VAL32$: hex string → value
; Inputs: string in buffer
; Outputs: FAC1=numeric value
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Parses 8-digit hex string → numeric
.export math_val32
.proc math_val32
    .error "skeleton requires implementation"
.endproc
