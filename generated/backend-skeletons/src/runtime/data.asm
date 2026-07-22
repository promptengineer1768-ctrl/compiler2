; Generated from a trusted skeleton profile. Do not rename entries.

; data_read: READ
; Inputs: X/Y=typed destination descriptor
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Advances generation-checked DATA cursor and coerces stock-compatible value
.export data_read
.proc data_read
    .error "skeleton requires implementation"
.endproc

; data_reset: Runtime initialization
; Inputs: current source generation
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Initializes stream state for RUN/CLR policy
.export data_reset
.proc data_reset
    .error "skeleton requires implementation"
.endproc

; data_restore: RESTORE
; Inputs: optional line-target descriptor
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Resolves first applicable DATA record and resets cursor
.export data_restore
.proc data_restore
    .error "skeleton requires implementation"
.endproc
