; Generated from a trusted skeleton profile. Do not rename entries.

; overlay_enter: Overlay page swap-in
; Inputs: A=overlay ID
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Swaps in overlay page, adjusts dispatch table
.export overlay_enter
.proc overlay_enter
    .error "skeleton requires implementation"
.endproc

; overlay_exit: Overlay page swap-out
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Restores previous overlay page
.export overlay_exit
.proc overlay_exit
    .error "skeleton requires implementation"
.endproc

; overlay_resolve: ID → physical address resolution
; Inputs: A=routine ID
; Outputs: X=page, Y=offset
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Resolves routine ID to geoRAM page and entry offset
.export overlay_resolve
.proc overlay_resolve
    .error "skeleton requires implementation"
.endproc

; overlay_validate: Directory integrity check
; Inputs: none
; Outputs: C=1 if directory corrupt
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Validates overlay directory checksums and ABI versions
.export overlay_validate
.proc overlay_validate
    .error "skeleton requires implementation"
.endproc
