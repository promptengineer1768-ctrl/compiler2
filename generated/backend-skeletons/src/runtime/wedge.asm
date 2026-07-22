; Generated from a trusted skeleton profile. Do not rename entries.

; wedge_confirm_destructive: Destructive guard
; Inputs: X/Y=flag record (byte0 nonzero confirms)
; Outputs: C=0 confirmed, C=1 declined
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Requires explicit confirmation
.export wedge_confirm_destructive
.proc wedge_confirm_destructive
    .error "skeleton requires implementation"
.endproc

; wedge_directory: `$` / `@$`
; Inputs: X/Y=validated options/output binding
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Streams directory; never loads over current program/image
.export wedge_directory
.proc wedge_directory
    .error "skeleton requires implementation"
.endproc

; wedge_dispatch_development: Development wedge command dispatcher
; Inputs: A=command kind, X/Y=validated command record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Records kind and dispatches to the matching wedge core path
.export wedge_dispatch_development
.proc wedge_dispatch_development
    .error "skeleton requires implementation"
.endproc

; wedge_format_directory: Bounded directory-entry formatter
; Inputs: X/Y=NUL-terminated directory entry
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Replaces bounded wedge output buffer
.export wedge_format_directory
.proc wedge_format_directory
    .error "skeleton requires implementation"
.endproc

; wedge_load_absolute: `/`
; Inputs: X/Y=filename/current-device record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Equivalent to `LOAD name,fa,1`
.export wedge_load_absolute
.proc wedge_load_absolute
    .error "skeleton requires implementation"
.endproc

; wedge_status_or_command: `@`
; Inputs: X/Y=validated command record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Reads status, selects device 8-11, sends command, or lists @$
.export wedge_status_or_command
.proc wedge_status_or_command
    .error "skeleton requires implementation"
.endproc

; wedge_stream_seq: `!`
; Inputs: X/Y=filename/output record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Streams PETSCII; STOP closes channel
.export wedge_stream_seq
.proc wedge_stream_seq
    .error "skeleton requires implementation"
.endproc
