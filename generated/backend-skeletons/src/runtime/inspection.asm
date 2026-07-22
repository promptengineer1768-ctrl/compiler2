; Generated from a trusted skeleton profile. Do not rename entries.

; inspect_clr: CLR
; Inputs: optional whitespace only
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Clears variables, arrays, strings, frames, continuation
.export inspect_clr
.proc inspect_clr
    .error "skeleton requires implementation"
.endproc

; inspect_cont: CONT in inspection shell
; Inputs: valid continuation handle/generation
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Restores compiled continuation descriptor and runtime state
.export inspect_cont
.proc inspect_cont
    .error "skeleton requires implementation"
.endproc

; inspect_list_loader: Source-free LIST behavior
; Inputs: optional whitespace only
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Prints exactly `2026 SYS2061`
.export inspect_list_loader
.proc inspect_list_loader
    .error "skeleton requires implementation"
.endproc

; inspect_load: LOAD
; Inputs: generated LOAD grammar
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Uses standalone KERNAL file path/current `fa`
.export inspect_load
.proc inspect_load
    .error "skeleton requires implementation"
.endproc

; inspect_parse_command: Grammar gate for inspection shell
; Inputs: input buffer
; Outputs: C=1 invalid
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Validates input against restricted grammar
.export inspect_parse_command
.proc inspect_parse_command
    .error "skeleton requires implementation"
.endproc

; inspect_print_string_var: ?A$(N) / PRINT A$(N) handler
; Inputs: variable name token
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Resolves and prints string variable or array element
.export inspect_print_string_var
.proc inspect_print_string_var
    .error "skeleton requires implementation"
.endproc

; inspect_print_var: ?A / PRINT A handler
; Inputs: variable name token
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Resolves and prints scalar or array element
.export inspect_print_var
.proc inspect_print_var
    .error "skeleton requires implementation"
.endproc

; inspect_run: RUN
; Inputs: optional whitespace only
; Outputs: does not return on success
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Reinitializes and enters current compiled image
.export inspect_run
.proc inspect_run
    .error "skeleton requires implementation"
.endproc

; inspect_save: SAVE
; Inputs: generated SAVE grammar
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Uses standalone KERNAL file path/current `fa`
.export inspect_save
.proc inspect_save
    .error "skeleton requires implementation"
.endproc

; inspect_shell: Inspection shell main loop
; Inputs: (never returns normally)
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Main REPL loop: reads input, dispatches restricted grammar
.export inspect_shell
.proc inspect_shell
    .error "skeleton requires implementation"
.endproc

; inspect_verify: VERIFY
; Inputs: generated VERIFY grammar
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Uses standalone KERNAL file path/current `fa`
.export inspect_verify
.proc inspect_verify
    .error "skeleton requires implementation"
.endproc

; inspect_wedge: `$`, `/`, `@`, `!`
; Inputs: validated prefix command
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Calls standalone wedge service; shares `fa`
.export inspect_wedge
.proc inspect_wedge
    .error "skeleton requires implementation"
.endproc
