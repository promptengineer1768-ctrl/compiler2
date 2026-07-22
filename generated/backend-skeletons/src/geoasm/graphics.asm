; Generated from a trusted skeleton profile. Do not rename entries.

; graphics_enter: Enter bitmap mode
; Inputs: X/Y=validated graphics allocation plan (+0 mode: 0=hires, 1=multicolor)
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_tmptr, write:zp_tmptr
; Side effects: Transactionally reserves `$DC00-$FF3F`, selects VIC bank 3/`$D018=$78`
.export graphics_enter
.proc graphics_enter
    .error "skeleton requires implementation"
.endproc

; graphics_exit: Sole exit path
; Inputs: A=exit reason
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Restores stock text/colors, invalidates graphics data, then restores ceiling
.export graphics_exit
.proc graphics_exit
    .error "skeleton requires implementation"
.endproc

; graphics_matrix_copy: `$DC00-$DFE7` access
; Inputs: X/Y=bounded transfer record (src.w, dest.w, len.w)
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_tmptr, read:zp_src, read:zp_tmp4, write:zp_tmptr, write:zp_src, write:zp_tmp2, write:zp_tmp3, write:zp_tmp4
; Side effects: Uses chunked RAM-under-I/O gate with IRQ opportunities
.export graphics_matrix_copy
.proc graphics_matrix_copy
    .error "skeleton requires implementation"
.endproc

; graphics_validate_bounds: Untrusted boundary
; Inputs: X/Y=pixel/cell descriptor (kind, x_lo, x_hi, y)
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_tmptr, write:zp_tmptr
; Side effects: Checks bitmap/matrix/color limits
.export graphics_validate_bounds
.proc graphics_validate_bounds
    .error "skeleton requires implementation"
.endproc
