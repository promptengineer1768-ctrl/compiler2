; Generated from a trusted skeleton profile. Do not rename entries.

; err_break: STOP-key break
; Inputs: continuation point/runtime frame
; Outputs: (never returns to caller)
; Clobbers: declared unwind set
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_cont_handle, write:zp_cont_generation, write:zp_stop_flag
; Side effects: Raises `?BREAK IN line`, publishes CONT descriptor
.export err_break
.proc err_break
    .error "skeleton requires implementation"
.endproc

; err_from_kernal: KERNAL error translation
; Inputs: KERNAL error in carry
; Outputs: A=basic error code
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Translates KERNAL carry/status to BASIC error code
.export err_from_kernal
.proc err_from_kernal
    .error "skeleton requires implementation"
.endproc

; err_outofmemory: Out of memory error shortcut
; Inputs: none
; Outputs: (never returns)
; Clobbers: none
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Shortcut: raises ?OUT OF MEMORY ERROR
.export err_outofmemory
.proc err_outofmemory
    .error "skeleton requires implementation"
.endproc

; err_overflow: Overflow error shortcut
; Inputs: none
; Outputs: (never returns)
; Clobbers: none
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Shortcut: raises ?OVERFLOW ERROR
.export err_overflow
.proc err_overflow
    .error "skeleton requires implementation"
.endproc

; err_raise: BASIC error raise
; Inputs: A=error code, X/Y=error-context record
; Outputs: does not return to caller
; Clobbers: declared unwind set
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_errnum, write:zp_errline, write:zp_errptr
; Side effects: Closes/restores channels, calls unified graphics exit, formats stock message, enters profile READY shell
.export err_raise
.proc err_raise
    .error "skeleton requires implementation"
.endproc

; err_raise_direct: Direct-mode error raise
; Inputs: A=error code
; Outputs: A=error code, C=1 after development READY transition
; Clobbers: A X Y flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_errnum
; Side effects: Formats error for direct mode: "?CODE ERROR"
.export err_raise_direct
.proc err_raise_direct
    .error "skeleton requires implementation"
.endproc

; err_save_cont: Save generation-checked CONT state
; Inputs: continuation point/runtime frame
; Outputs: X/Y=continuation handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_cont_handle, write:zp_cont_generation, write:zp_stop_flag
; Side effects: Copies all required resumable state before stack unwind
.export err_save_cont
.proc err_save_cont
    .error "skeleton requires implementation"
.endproc

; err_syntax: Syntax error shortcut
; Inputs: none
; Outputs: (never returns)
; Clobbers: none
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Shortcut: raises ?SYNTAX ERROR
.export err_syntax
.proc err_syntax
    .error "skeleton requires implementation"
.endproc

; err_type: Type mismatch error shortcut
; Inputs: none
; Outputs: (never returns)
; Clobbers: none
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Shortcut: raises ?TYPE MISMATCH ERROR
.export err_type
.proc err_type
    .error "skeleton requires implementation"
.endproc

; err_undefdfunction: Undefined function error
; Inputs: X/Y=fn name
; Outputs: (never returns)
; Clobbers: none
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Shortcut: raises ?UNDEF'D FUNCTION ERROR
.export err_undefdfunction
.proc err_undefdfunction
    .error "skeleton requires implementation"
.endproc
