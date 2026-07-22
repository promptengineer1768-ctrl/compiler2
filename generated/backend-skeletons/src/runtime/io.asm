; Generated from a trusted skeleton profile. Do not rename entries.

; io_cmd: CMD statement
; Inputs: X/Y=IC record containing one unsigned logical-file byte
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: CMD: redirects output to channel
.export io_cmd
.proc io_cmd
    .error "skeleton requires implementation"
.endproc

; io_get: GET statement
; Inputs: var descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Reads single character from keyboard buffer into variable
.export io_get
.proc io_get
    .error "skeleton requires implementation"
.endproc

; io_input_string: INPUT statement string read
; Inputs: X/Y=typed destination/prompt/channel record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Prints prompt, reads string line
.export io_input_string
.proc io_input_string
    .error "skeleton requires implementation"
.endproc

; io_input_value: INPUT statement value read
; Inputs: X/Y=typed destination/prompt/channel record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Prints prompt "? ", reads value, coerces, stores
.export io_input_value
.proc io_input_value
    .error "skeleton requires implementation"
.endproc

; io_print_comma: PRINT comma zone advance
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Outputs spaces to next 10-column zone
.export io_print_comma
.proc io_print_comma
    .error "skeleton requires implementation"
.endproc

; io_print_newline: PRINT newline
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Outputs CR (carriage return)
.export io_print_newline
.proc io_print_newline
    .error "skeleton requires implementation"
.endproc

; io_print_semicolon: PRINT semicolon: no separator
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Suppresses newline/space (no output)
.export io_print_semicolon
.proc io_print_semicolon
    .error "skeleton requires implementation"
.endproc

; io_print_space: PRINT space (SPC)
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Outputs space character
.export io_print_space
.proc io_print_space
    .error "skeleton requires implementation"
.endproc

; io_print_tab: TAB function
; Inputs: A=column
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Outputs spaces to reach tab stop
.export io_print_tab
.proc io_print_tab
    .error "skeleton requires implementation"
.endproc

; io_print_value: PRINT value output
; Inputs: value in FAC1, type tag in A
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Formats and outputs value (numeric or string) to current channel
.export io_print_value
.proc io_print_value
    .error "skeleton requires implementation"
.endproc
