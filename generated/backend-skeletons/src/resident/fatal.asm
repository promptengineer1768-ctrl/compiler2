; Generated from a trusted skeleton profile. Do not rename entries.

; fatal_georam: Fatal integrity exit
; Inputs: A=reason, X/Y=diagnostic record
; Outputs: does not return to service
; Clobbers: declared unwind set
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Stops allocation/execution, restores selection/mapping/P, closes channels, reports reinstall requirement
.export fatal_georam
.proc fatal_georam
    .error "skeleton requires implementation"
.endproc

; fatal_restore_machine: Shared bounded cleanup
; Inputs: saved gate/bridge context
; Outputs: canonical editor-safe state
; Clobbers: A X Y, flags
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Restores page selection, `$01`, channels, graphics, IRQ state
.export fatal_restore_machine
.proc fatal_restore_machine
    .error "skeleton requires implementation"
.endproc
