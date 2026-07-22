; Generated from a trusted skeleton profile. Do not rename entries.

; fp_load_constant: IEEE constants
; Inputs: A=INF/NAN/SNAN ID
; Outputs: FAC1=value
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Produces specified special value/printed form
.export fp_load_constant
.proc fp_load_constant
    .error "skeleton requires implementation"
.endproc

; fp_set_rounding: FPSET
; Inputs: A=rounding ID
; Outputs: C=error
; Clobbers: A, flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Sets one of five specified rounding modes
.export fp_set_rounding
.proc fp_set_rounding
    .error "skeleton requires implementation"
.endproc

; fp_test_flags: FPTEST/FPTTEST
; Inputs: X/Y=test descriptor
; Outputs: boolean result
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Tests current/sticky flags
.export fp_test_flags
.proc fp_test_flags
    .error "skeleton requires implementation"
.endproc
