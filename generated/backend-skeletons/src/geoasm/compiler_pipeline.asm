; Generated from a trusted skeleton profile. Do not rename entries.

; pipeline_compile_line: Per-line compile
; Inputs: X/Y=canonical source record
; Outputs: X/Y=scratch compiled record, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Runs boundaries 1-7 without publication
.export pipeline_compile_line
.proc pipeline_compile_line
    .error "skeleton requires implementation"
.endproc

; pipeline_compile_program: Whole-program compile/relink
; Inputs: X/Y=source-generation handle
; Outputs: X/Y=scratch image, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Resolves all dirty records/layout/dependencies
.export pipeline_compile_program
.proc pipeline_compile_program
    .error "skeleton requires implementation"
.endproc

; pipeline_report_failure: Phase-localized failure
; Inputs: phase/line/error record
; Outputs: does not return to caller
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Leaves all published outputs unchanged
.export pipeline_report_failure
.proc pipeline_report_failure
    .error "skeleton requires implementation"
.endproc

; pipeline_serialize_boundary: Boundaries 1-8
; Inputs: A=boundary ID, X/Y=record handle
; Outputs: X/Y=versioned byte record, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Debug/host replay artifact
.export pipeline_serialize_boundary
.proc pipeline_serialize_boundary
    .error "skeleton requires implementation"
.endproc

; pipeline_validate_boundary: Deterministic replay guard
; Inputs: A=boundary ID, X/Y=record handle
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Checks schema/version/checksum
.export pipeline_validate_boundary
.proc pipeline_validate_boundary
    .error "skeleton requires implementation"
.endproc
