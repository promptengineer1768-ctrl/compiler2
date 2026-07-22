; Generated from a trusted skeleton profile. Do not rename entries.

; ctx_check_overflow: Overflow guard
; Inputs: none
; Outputs: C=1 if full
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Checks if next push would overflow
.export ctx_check_overflow
.proc ctx_check_overflow
    .error "skeleton requires implementation"
.endproc

; ctx_depth: Depth query
; Inputs: none
; Outputs: A=current depth
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Returns current nesting depth (for debug)
.export ctx_depth
.proc ctx_depth
    .error "skeleton requires implementation"
.endproc

; ctx_init: Context stack initialization
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Resets context stack pointer to empty
.export ctx_init
.proc ctx_init
    .error "skeleton requires implementation"
.endproc

; ctx_pop: Context restore
; Inputs: X/Y=destination record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Pops complete caller context; detects underflow
.export ctx_pop
.proc ctx_pop
    .error "skeleton requires implementation"
.endproc

; ctx_push: Context save for nesting
; Inputs: X/Y=context-record pointer
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Pushes selected block/page, P, declared registers/results; checks first
.export ctx_push
.proc ctx_push
    .error "skeleton requires implementation"
.endproc
