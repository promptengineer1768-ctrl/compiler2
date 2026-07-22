; Generated from a trusted skeleton profile. Do not rename entries.

; editor_delete_line: Delete numbered line
; Inputs: X/Y=line number record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Runs dependency repair and one-generation deletion publish
.export editor_delete_line
.proc editor_delete_line
    .error "skeleton requires implementation"
.endproc

; editor_detokenize_line: LIST conversion
; Inputs: X/Y=canonical line handle
; Outputs: X/Y=text handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Allocates scratch text only
.export editor_detokenize_line
.proc editor_detokenize_line
    .error "skeleton requires implementation"
.endproc

; editor_list_range: LIST and ranges
; Inputs: X/Y=validated range record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Streams canonical detokenization through output path
.export editor_list_range
.proc editor_list_range
    .error "skeleton requires implementation"
.endproc

; editor_ready_transition: Observable synchronization point
; Inputs: publication result handle
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Atomically changes mailbox/editor state to READY or error
.export editor_ready_transition
.proc editor_ready_transition
    .error "skeleton requires implementation"
.endproc

; editor_submit_line: Numbered/direct submission
; Inputs: X/Y=captured-line handle
; Outputs: C=error, A=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Parses optional line number; publishes source/code together or changes nothing
.export editor_submit_line
.proc editor_submit_line
    .error "skeleton requires implementation"
.endproc
