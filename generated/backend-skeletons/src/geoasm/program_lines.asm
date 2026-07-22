; Generated from a trusted skeleton profile. Do not rename entries.

; program_lines_print_selected_line_number: Cold LIST decimal formatter for the selected canonical program line
; Inputs: program_store_selected_line_number:u16 published by program_store_copy_line_body_at
; Outputs: C=0 after emitting the decimal line number
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_tmp1, write:zp_tmp1
; Side effects: Writes the selected line number to the editor output stream
.export program_lines_print_selected_line_number
.proc program_lines_print_selected_line_number
    .error "skeleton requires implementation"
.endproc
