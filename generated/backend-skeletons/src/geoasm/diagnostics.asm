; Generated from a trusted skeleton profile. Do not rename entries.

; diag_error_from_kernal: KERNAL error translation
; Inputs: KERNAL error in C/A
; Outputs: A=basic error code
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Converts KERNAL carry/error to BASIC error code
.export diag_error_from_kernal
.proc diag_error_from_kernal
    .error "skeleton requires implementation"
.endproc

; diag_format_error: Formats "?SYNTAX ERROR IN 10" type message
; Inputs: A=error code, X/Y=source line ptr
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Formats error string with line number and context
.export diag_format_error
.proc diag_format_error
    .error "skeleton requires implementation"
.endproc

; diag_format_source_context: Error context display
; Inputs: X/Y=source line ptr, A=cursor offset
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Extracts and formats source context around error point
.export diag_format_source_context
.proc diag_format_source_context
    .error "skeleton requires implementation"
.endproc

; diag_format_warning: Warning formatter (for future use)
; Inputs: A=warning code, X/Y=source line ptr
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Formats non-fatal warning
.export diag_format_warning
.proc diag_format_warning
    .error "skeleton requires implementation"
.endproc

; diag_print_error: Error output to screen
; Inputs: formatted error in buffer
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Outputs formatted error to current channel
.export diag_print_error
.proc diag_print_error
    .error "skeleton requires implementation"
.endproc
