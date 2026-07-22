; Generated from a trusted skeleton profile. Do not rename entries.

; codegen_emit_reloc: Relocation entry emitter
; Inputs: address, fixup type
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Records a relocation entry for linker
.export codegen_emit_reloc
.proc codegen_emit_reloc
    .error "skeleton requires implementation"
.endproc

; codegen_finish_line: End-of-line code finalization
; Inputs: none
; Outputs: C=error
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Validates code size, updates code layout, commits relocations
.export codegen_finish_line
.proc codegen_finish_line
    .error "skeleton requires implementation"
.endproc

; codegen_get_code_ptr: Query for tests/replay
; Inputs: none
; Outputs: X/Y=current code ptr
; Clobbers: X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Returns current code emission position
.export codegen_get_code_ptr
.proc codegen_get_code_ptr
    .error "skeleton requires implementation"
.endproc

; codegen_init: Initialize code generator
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Resets code emitter state, clears relocation list
.export codegen_init
.proc codegen_init
    .error "skeleton requires implementation"
.endproc
