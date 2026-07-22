; Generated from a trusted skeleton profile. Do not rename entries.

; program_replace_from_load: Transactional LOAD
; Inputs: X/Y=fully decoded scratch program
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Publishes only after format and dependency validation
.export program_replace_from_load
.proc program_replace_from_load
    .error "skeleton requires implementation"
.endproc

; program_tx_abort: Roll back
; Inputs: X/Y=transaction
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Frees scratch; published root unchanged
.export program_tx_abort
.proc program_tx_abort
    .error "skeleton requires implementation"
.endproc

; program_tx_begin: Begin isolated edit
; Inputs: current source generation
; Outputs: X/Y=transaction handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Allocates scratch directory/records
.export program_tx_begin
.proc program_tx_begin
    .error "skeleton requires implementation"
.endproc

; program_tx_commit: Publish source generation
; Inputs: X/Y=validated transaction
; Outputs: X/Y=new generation record, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Atomically swaps directory root
.export program_tx_commit
.proc program_tx_commit
    .error "skeleton requires implementation"
.endproc

; program_tx_delete_line: Stage deletion
; Inputs: X/Y=transaction + line number
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Removes only scratch record
.export program_tx_delete_line
.proc program_tx_delete_line
    .error "skeleton requires implementation"
.endproc

; program_tx_put_line: Stage line
; Inputs: X/Y=transaction + line record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Replaces/inserts only scratch record
.export program_tx_put_line
.proc program_tx_put_line
    .error "skeleton requires implementation"
.endproc
