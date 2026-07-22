; Generated from a trusted skeleton profile. Do not rename entries.

; parse_array_ref: Array element reference parser
; Inputs: X/Y=var descriptor
; Outputs: element address
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_expr_ptr1
; Side effects: Parses array subscript(s), resolves element
.export parse_array_ref
.proc parse_array_ref
    .error "skeleton requires implementation"
.endproc

; parse_comparison: Comparison operator parser
; Inputs: left value loaded
; Outputs: result in A (boolean), C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_fac1, write:zp_fac2
; Side effects: Parses =, <>, <, >, <=, >=
.export parse_comparison
.proc parse_comparison
    .error "skeleton requires implementation"
.endproc

; parse_expression: Primary expression parser
; Inputs: none
; Outputs: type in `zp_expr_type`, value in FAC1 or accumulator
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_expr_ptr1, write:zp_expr_ptr2, write:zp_fac1, write:zp_prec
; Side effects: Full expression parser (Pratt: handles precedence, functions, operators)
.export parse_expression
.proc parse_expression
    .error "skeleton requires implementation"
.endproc

; parse_factor: Factor-level parser
; Inputs: none
; Outputs: value in FAC1
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_fac1
; Side effects: Parses unary -, NOT, ^
.export parse_factor
.proc parse_factor
    .error "skeleton requires implementation"
.endproc

; parse_for: FOR statement parser
; Inputs: none
; Outputs: loop descriptor set up
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_forlev
; Side effects: Parses FOR var=start TO end [STEP inc], pushes loop frame
.export parse_for
.proc parse_for
    .error "skeleton requires implementation"
.endproc

; parse_function_call: Built-in function parser
; Inputs: A=func ID
; Outputs: value in FAC1 or string
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_fac1, write:zp_opptr
; Side effects: Parses function argument list, calls function
.export parse_function_call
.proc parse_function_call
    .error "skeleton requires implementation"
.endproc

; parse_gosub: GOSUB statement parser
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_sublev
; Side effects: Parses GOSUB line, validates target
.export parse_gosub
.proc parse_gosub
    .error "skeleton requires implementation"
.endproc

; parse_line: Top-level line parser
; Inputs: X/Y=token stream
; Outputs: C=error, error code in A
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_lptr, write:zp_forlev, write:zp_sublev
; Side effects: Parses one complete program or direct line
.export parse_line
.proc parse_line
    .error "skeleton requires implementation"
.endproc

; parse_primary: Primary (atom) parser
; Inputs: none
; Outputs: value in FAC1 or string ptr
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_fac1
; Side effects: Parses primary: number, string, variable, function call, (expr)
.export parse_primary
.proc parse_primary
    .error "skeleton requires implementation"
.endproc

; parse_statement: Statement parser dispatcher
; Inputs: none
; Outputs: A=stmt ID, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_stmt_op, write:zp_stmt_arg
; Side effects: Parses one statement, dispatches to statement handler
.export parse_statement
.proc parse_statement
    .error "skeleton requires implementation"
.endproc

; parse_term: Term-level parser
; Inputs: none
; Outputs: value in FAC1
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_fac1, write:zp_arg
; Side effects: Parses *, /
.export parse_term
.proc parse_term
    .error "skeleton requires implementation"
.endproc
