; Generated from a trusted skeleton profile. Do not rename entries.

; math_abs: ABS function
; Inputs: FAC1=value
; Outputs: FAC1=abs(value)
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_abs
.proc math_abs
    .error "skeleton requires implementation"
.endproc

; math_add: Float addition (+)
; Inputs: FAC1=left, ARG=right
; Outputs: FAC1=result; math_status=MATH_OK/error; C=0 success, C=1 error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: none
.export math_add
.proc math_add
    .error "skeleton requires implementation"
.endproc

; math_add_int: Integer addition
; Inputs: X/Y=pointer to 4-byte record: signed lhs low/high, signed rhs low/high
; Outputs: Record bytes 0..1=signed sum; C=0 success, C=1 signed overflow
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: none
.export math_add_int
.proc math_add_int
    .error "skeleton requires implementation"
.endproc

; math_cmp: Float comparison (=, <>, )
; Inputs: FAC1=a, ARG=b
; Outputs: A=$FF if FAC1<ARG, $00 if equal, $01 if FAC1>ARG; N/Z reflect A
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: none
.export math_cmp
.proc math_cmp
    .error "skeleton requires implementation"
.endproc

; math_div: Float division (/)
; Inputs: FAC1=left, ARG=right
; Outputs: FAC1=result; math_status=MATH_OK/error; C=0 success, C=1 error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: Returns MATH_ERR_DIV_ZERO with C=1 for a zero divisor; may update IEEE flags when enabled
.export math_div
.proc math_div
    .error "skeleton requires implementation"
.endproc

; math_div_int: Integer division with remainder
; Inputs: X/Y=pointer to 4-byte record: signed dividend low/high, signed divisor low/high
; Outputs: Record bytes 0..1=signed quotient truncated toward zero; C=0 success, C=1 division by zero or -32768/-1 overflow
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Division-by-zero and overflow follow numeric profile
.export math_div_int
.proc math_div_int
    .error "skeleton requires implementation"
.endproc

; math_float_to_int: Float to 16-bit integer conversion
; Inputs: FAC1=float
; Outputs: X=low byte and Y=high byte of signed 16-bit integer; C=0 success, C=1 unrepresentable
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Truncates toward zero
.export math_float_to_int
.proc math_float_to_int
    .error "skeleton requires implementation"
.endproc

; math_fpe: Floating-point examine (set N/Z for branching)
; Inputs: FAC1=value
; Outputs: A=$FF for negative, $00 for zero, $01 for positive; N/Z reflect A
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Sets flags: N=negative, Z=zero
.export math_fpe
.proc math_fpe
    .error "skeleton requires implementation"
.endproc

; math_int: Stock BASIC `INT`: greatest integer not greater than the operand
; Inputs: FAC1=value
; Outputs: FAC1=floor(value)
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_int
.proc math_int
    .error "skeleton requires implementation"
.endproc

; math_int_to_float: 16-bit integer to float conversion
; Inputs: X=low byte and Y=high byte of signed 16-bit integer
; Outputs: FAC1=5-byte float; C=0
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_int_to_float
.proc math_int_to_float
    .error "skeleton requires implementation"
.endproc

; math_mul: Float multiplication (*)
; Inputs: FAC1=left, ARG=right
; Outputs: FAC1=result; math_status=MATH_OK/error; C=0 success, C=1 error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: none
.export math_mul
.proc math_mul
    .error "skeleton requires implementation"
.endproc

; math_mul_int: Integer multiplication
; Inputs: X/Y=pointer to 4-byte record: signed lhs low/high, signed rhs low/high
; Outputs: Record bytes 0..1=signed product; C=0 success, C=1 signed overflow
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: none
.export math_mul_int
.proc math_mul_int
    .error "skeleton requires implementation"
.endproc

; math_negate: Float negation (unary -)
; Inputs: FAC1=value
; Outputs: FAC1=-value
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_negate
.proc math_negate
    .error "skeleton requires implementation"
.endproc

; math_sgn: SGN function (-1, 0, +1)
; Inputs: FAC1=value
; Outputs: FAC1=sgn(value)
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: none
.export math_sgn
.proc math_sgn
    .error "skeleton requires implementation"
.endproc

; math_sub: Float subtraction (-)
; Inputs: FAC1=left, ARG=right
; Outputs: FAC1=result; math_status=MATH_OK/error; C=0 success, C=1 error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1, write:zp_arg
; Side effects: none
.export math_sub
.proc math_sub
    .error "skeleton requires implementation"
.endproc

; math_sub_int: Integer subtraction
; Inputs: X/Y=pointer to 4-byte record: signed lhs low/high, signed rhs low/high
; Outputs: Record bytes 0..1=signed difference; C=0 success, C=1 signed overflow
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: none
.export math_sub_int
.proc math_sub_int
    .error "skeleton requires implementation"
.endproc

; math_to_arg_byte: Narrow a numeric expression to the shared unsigned argument-byte domain
; Inputs: A=numeric type, FAC=value
; Outputs: A=unsigned byte and C=0, or A=ERR_ILLEGAL_QUANTITY and C=1
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_fac1, write:zp_fac1
; Side effects: Rejects negative, fractional, and greater-than-255 values
.export math_to_arg_byte
.proc math_to_arg_byte
    .error "skeleton requires implementation"
.endproc

; math_u24_to_float: Exact unsigned 24-bit integer to packed-float conversion
; Inputs: A=low, X=middle, Y=high byte
; Outputs: FAC1=exact positive float, C=0
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Sets math_fac_type to FLOAT
.export math_u24_to_float
.proc math_u24_to_float
    .error "skeleton requires implementation"
.endproc
