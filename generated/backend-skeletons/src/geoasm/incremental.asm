; Generated from a trusted skeleton profile. Do not rename entries.

; incremental_abort: Rollback
; Inputs: X/Y=transaction
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Frees scratch, preserves last valid generation
.export incremental_abort
.proc incremental_abort
    .error "skeleton requires implementation"
.endproc

; incremental_can_run: RUN guard
; Inputs: X/Y=current generation
; Outputs: C=0 executable, C=1 blocked
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Checks no dirty records, verified layout/checksum
.export incremental_can_run
.proc incremental_can_run
    .error "skeleton requires implementation"
.endproc

; incremental_fingerprint: Cache key
; Inputs: X/Y=source and dependency record
; Outputs: X/Y=fingerprint handle
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, write:zp_src
; Side effects: Includes all generations named by `DESIGN.md` §6.2
.export incremental_fingerprint
.proc incremental_fingerprint
    .error "skeleton requires implementation"
.endproc

; incremental_mark_dependents: Structural invalidation
; Inputs: X/Y=edit descriptor
; Outputs: X/Y=dirty-set handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, write:zp_src
; Side effects: Tracks branch, DATA, loop, subroutine, variable, layout effects
.export incremental_mark_dependents
.proc incremental_mark_dependents
    .error "skeleton requires implementation"
.endproc

; incremental_publish: Publication rule
; Inputs: X/Y=validated source/code transaction
; Outputs: X/Y=new generation record, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Atomically swaps both roots and image checksum
.export incremental_publish
.proc incremental_publish
    .error "skeleton requires implementation"
.endproc

; incremental_resolve_dirty: No interpreter fallback
; Inputs: X/Y=transaction/dirty set
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Recompiles or relinks every required record
.export incremental_resolve_dirty
.proc incremental_resolve_dirty
    .error "skeleton requires implementation"
.endproc
