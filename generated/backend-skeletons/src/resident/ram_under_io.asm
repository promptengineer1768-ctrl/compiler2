; Generated from a trusted skeleton profile. Do not rename entries.

; ram_under_io_copy_in: Bounded chunk copy for screen matrix
; Inputs: X/Y=dest, A=len, src pointer set
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Copies bytes from normal RAM into $D000-$DFFF region through gate
.export ram_under_io_copy_in
.proc ram_under_io_copy_in
    .error "skeleton requires implementation"
.endproc

; ram_under_io_copy_out: Read-back for screen matrix
; Inputs: X/Y=src, A=len, dest pointer set
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Copies bytes from $D000-$DFFF region out to normal RAM through gate
.export ram_under_io_copy_out
.proc ram_under_io_copy_out
    .error "skeleton requires implementation"
.endproc

; ram_under_io_enter: Opens gate: $01 → all-RAM; IRQ disabled
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Selects all-RAM mapping; masks IRQ
.export ram_under_io_enter
.proc ram_under_io_enter
    .error "skeleton requires implementation"
.endproc

; ram_under_io_exit: Closes gate: restore canonical mapping
; Inputs: none
; Outputs: $01 restored to $35
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Restores $35 mapping; restores incoming IRQ state
.export ram_under_io_exit
.proc ram_under_io_exit
    .error "skeleton requires implementation"
.endproc
