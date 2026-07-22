; Generated from a trusted skeleton profile. Do not rename entries.

; wedge_parse: Prefix parser
; Inputs: X/Y=raw prefix command
; Outputs: A=kind ($=0,@=1,/=2,!=3,$FF=normal), C=error
; Clobbers: A Y
; Flags: return_kind:rts, stack_delta:0, preserves:X, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_tmptr, write:zp_tmptr
; Side effects: Enforces direct-only grammar for $ @ / ! forms
.export wedge_parse
.proc wedge_parse
    .error "skeleton requires implementation"
.endproc

; wedge_run_development: Parse then dispatch one development wedge line
; Inputs: X/Y=raw prefix command text
; Outputs: C=error; A=$FF means normal BASIC input
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_tmptr, write:zp_tmptr
; Side effects: May invoke KERNAL-backed wedge core handlers
.export wedge_run_development
.proc wedge_run_development
    .error "skeleton requires implementation"
.endproc
