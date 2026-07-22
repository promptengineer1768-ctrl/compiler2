; Generated from a trusted skeleton profile. Do not rename entries.

; direct_classify: Direct/program policy
; Inputs: X/Y=validated statement record
; Outputs: A=command class, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, write:zp_src
; Side effects: Uses generated table only
.export direct_classify
.proc direct_classify
    .error "skeleton requires implementation"
.endproc

; direct_execute_command: Direct-only commands
; Inputs: X/Y=direct-command record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, write:zp_src
; Side effects: Dispatches NEW/RUN/CONT/CLR/LIST/COMPILE/file/mode commands
.export direct_execute_command
.proc direct_execute_command
    .error "skeleton requires implementation"
.endproc

; direct_execute_temporary: Single immediate compiler path
; Inputs: X/Y=tokenized direct line
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, write:zp_src
; Side effects: Compiles, executes, and discards one-line temporary generation
.export direct_execute_temporary
.proc direct_execute_temporary
    .error "skeleton requires implementation"
.endproc

; direct_probe_prefix: `$`, `/`, `@`, `!` front door
; Inputs: X/Y=captured text
; Outputs: A=wedge/normal, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, write:zp_src
; Side effects: Does not tokenize wedge input
.export direct_probe_prefix
.proc direct_probe_prefix
    .error "skeleton requires implementation"
.endproc
