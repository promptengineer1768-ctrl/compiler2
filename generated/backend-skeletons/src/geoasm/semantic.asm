; Generated from a trusted skeleton profile. Do not rename entries.

; semantic_check_for_dialect: Dialect query for compiler passes
; Inputs: none
; Outputs: A=current dialect
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Returns BASIC2_DIALECT or BASIC35_DIALECT
.export semantic_check_for_dialect
.proc semantic_check_for_dialect
    .error "skeleton requires implementation"
.endproc

; semantic_classify_direct: Direct/program classification per §4 table
; Inputs: A=stmt ID
; Outputs: C=1 if direct-only in program line
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Rejects direct-only commands in stored-program context
.export semantic_classify_direct
.proc semantic_classify_direct
    .error "skeleton requires implementation"
.endproc

; semantic_get_numeric_mode: `FPMODE()` query
; Inputs: none
; Outputs: A=current numeric mode
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Reads legacy/IEEE mode independently of dialect
.export semantic_get_numeric_mode
.proc semantic_get_numeric_mode
    .error "skeleton requires implementation"
.endproc

; semantic_set_dialect: BASIC2 / BASIC3.5 direct command handler
; Inputs: A=dialect
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Sets active dialect mode
.export semantic_set_dialect
.proc semantic_set_dialect
    .error "skeleton requires implementation"
.endproc

; semantic_set_numeric_mode: `FPMODE0` / `FPMODE1`
; Inputs: A=mode
; Outputs: C=error if unsupported
; Clobbers: A, flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Changes numeric policy and invalidates mode-keyed compiled records
.export semantic_set_numeric_mode
.proc semantic_set_numeric_mode
    .error "skeleton requires implementation"
.endproc

; semantic_validate_dialect: Tokenizer already prevents disabled extended tokens from being stored
; Inputs: A=token
; Outputs: C=1 if invalid in current dialect
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Defense-in-depth for loaded/versioned token streams
.export semantic_validate_dialect
.proc semantic_validate_dialect
    .error "skeleton requires implementation"
.endproc

; semantic_validate_line: Transactional syntax validation (step 3 of line entry)
; Inputs: X/Y=token stream
; Outputs: C=error, A=error code
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_txtptr, write:zp_forlev, write:zp_sublev
; Side effects: Full syntax/dialect validation of one line
.export semantic_validate_line
.proc semantic_validate_line
    .error "skeleton requires implementation"
.endproc
