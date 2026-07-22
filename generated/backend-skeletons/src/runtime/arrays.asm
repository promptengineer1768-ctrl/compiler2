; Generated from a trusted skeleton profile. Do not rename entries.

; arr_check_bounds: Bounds-only check helper
; Inputs: subscript in X/Y, dimension limit
; Outputs: C=1 if out of bounds
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Bounds check without resolution
.export arr_check_bounds
.proc arr_check_bounds
    .error "skeleton requires implementation"
.endproc

; arr_dim: DIM handler
; Inputs: X/Y=14-byte AM dimension request
; Outputs: C=error, A=error code
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Allocates and clears array-arena pages, then publishes one AD descriptor
.export arr_dim
.proc arr_dim
    .error "skeleton requires implementation"
.endproc

; arr_free: Array deallocation
; Inputs: X/Y=16-byte AD descriptor
; Outputs: C=error, A=error code
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Releases owned array pages and invalidates the AD descriptor
.export arr_free
.proc arr_free
    .error "skeleton requires implementation"
.endproc

; arr_load_element: Array element load
; Inputs: X/Y=8-byte AE descriptor/subscripts request
; Outputs: integer in X/Y, float in FAC1, or string pointer X/Y and length A; C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Loads typed element from resolved address
.export arr_load_element
.proc arr_load_element
    .error "skeleton requires implementation"
.endproc

; arr_redim: Existing-array guard
; Inputs: X/Y=16-byte AD descriptor
; Outputs: C=error, A=ERR_REDIM_ARRAY for a live descriptor
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Rejects an already dimensioned array with stock `REDIM'D ARRAY` behavior
.export arr_redim
.proc arr_redim
    .error "skeleton requires implementation"
.endproc

; arr_resolve_element: Array element resolution
; Inputs: X/Y=8-byte AE descriptor/subscripts request
; Outputs: X/Y=selected $DE00 element address, C=error, A=error code
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Bounds-checks subscripts, computes element offset
.export arr_resolve_element
.proc arr_resolve_element
    .error "skeleton requires implementation"
.endproc

; arr_store_element: Array element store
; Inputs: X/Y=12-byte AS request; FAC1 supplies float values
; Outputs: C=error, A=error code
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Stores typed element to resolved address
.export arr_store_element
.proc arr_store_element
    .error "skeleton requires implementation"
.endproc
