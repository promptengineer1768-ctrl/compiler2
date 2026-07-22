; Generated from a trusted skeleton profile. Do not rename entries.

; resident_assert_boundary: Common debug assertion
; Inputs: public-boundary ID
; Outputs: C=error in debug
; Clobbers: A, flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Checks `$01=$35`, D clear, gate mirror, stack watermark
.export resident_assert_boundary
.proc resident_assert_boundary
    .error "skeleton requires implementation"
.endproc

; resident_main: READY/editor loop
; Inputs: initialized environment
; Outputs: does not return
; Clobbers: A X Y
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Captures editor input and dispatches complete lines
.export resident_main
.proc resident_main
    .error "skeleton requires implementation"
.endproc

; resident_poll_input: Nonblocking input drain
; Inputs: mailbox handle in X/Y
; Outputs: A=byte or zero
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Calls foreground `GETIN` bridge only
.export resident_poll_input
.proc resident_poll_input
    .error "skeleton requires implementation"
.endproc

; resident_submit_line: Transactional handoff
; Inputs: X/Y=line mailbox handle
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Calls direct-prefix dispatch or geoRAM editor service
.export resident_submit_line
.proc resident_submit_line
    .error "skeleton requires implementation"
.endproc
