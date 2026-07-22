; Generated from a trusted skeleton profile. Do not rename entries.

; ir_emit_array_ref: Array reference emitter
; Inputs: X/Y=arr descriptor, subscript
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes array element reference
.export ir_emit_array_ref
.proc ir_emit_array_ref
    .error "skeleton requires implementation"
.endproc

; ir_emit_branch: Branch emitter
; Inputs: A=type, X/Y=target
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes GOTO/GOSUB/IF-THEN branch
.export ir_emit_branch
.proc ir_emit_branch
    .error "skeleton requires implementation"
.endproc

; ir_emit_expr: Expression tree emitter
; Inputs: A=op, operands referenced
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Writes expression tree node
.export ir_emit_expr
.proc ir_emit_expr
    .error "skeleton requires implementation"
.endproc

; ir_emit_literal_float: Float literal emitter
; Inputs: FAC1=value
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Writes float literal node
.export ir_emit_literal_float
.proc ir_emit_literal_float
    .error "skeleton requires implementation"
.endproc

; ir_emit_literal_int: Integer literal emitter
; Inputs: X/Y=16-bit value
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes integer literal node
.export ir_emit_literal_int
.proc ir_emit_literal_int
    .error "skeleton requires implementation"
.endproc

; ir_emit_literal_str: String literal emitter
; Inputs: X/Y=string data, A=len
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes string literal node
.export ir_emit_literal_str
.proc ir_emit_literal_str
    .error "skeleton requires implementation"
.endproc

; ir_emit_loop: Loop descriptor emitter
; Inputs: A=kind, loop params
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_forlev
; Side effects: Writes loop descriptor (FOR, DO, etc.)
.export ir_emit_loop
.proc ir_emit_loop
    .error "skeleton requires implementation"
.endproc

; ir_emit_stmt: Statement boundary emitter
; Inputs: A=stmt type, X/Y=args
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Writes one statement record to IR buffer
.export ir_emit_stmt
.proc ir_emit_stmt
    .error "skeleton requires implementation"
.endproc

; ir_emit_string_ref: String reference emitter
; Inputs: X/Y=string descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes string reference node
.export ir_emit_string_ref
.proc ir_emit_string_ref
    .error "skeleton requires implementation"
.endproc

; ir_emit_var_ref: Variable reference emitter
; Inputs: X/Y=var descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes variable reference node
.export ir_emit_var_ref
.proc ir_emit_var_ref
    .error "skeleton requires implementation"
.endproc

; ir_finish_line: End-of-line IR finalization
; Inputs: none
; Outputs: C=error
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Validates IR completeness for line, returns to caller
.export ir_finish_line
.proc ir_finish_line
    .error "skeleton requires implementation"
.endproc

; ir_get_buf_ptr: Query for tests/replay
; Inputs: none
; Outputs: X/Y=current write ptr
; Clobbers: X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Returns current IR buffer position
.export ir_get_buf_ptr
.proc ir_get_buf_ptr
    .error "skeleton requires implementation"
.endproc

; ir_init: Initialize IR builder for new compilation
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Clears IR buffer, resets write pointer
.export ir_init
.proc ir_init
    .error "skeleton requires implementation"
.endproc
