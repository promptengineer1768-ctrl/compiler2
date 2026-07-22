; Generated from a trusted skeleton profile. Do not rename entries.

; expansion_check_skip_reload: Fingerprint skip-reload decision for re-entry
; Inputs: A=candidate image fingerprint
; Outputs: C=0 skip reload, C=1 must reload
; Clobbers: A X
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: none
.export expansion_check_skip_reload
.proc expansion_check_skip_reload
    .error "skeleton requires implementation"
.endproc

; expansion_clear: Clear expansion profile before probe or on failure
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Zeros store, assist, capacities, fingerprints, session_ready
.export expansion_clear
.proc expansion_clear
    .error "skeleton requires implementation"
.endproc

; expansion_mark_ready: Mark install complete for skip-reload
; Inputs: A=image fingerprint
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Sets expansion_image_fingerprint and expansion_session_ready
.export expansion_mark_ready
.proc expansion_mark_ready
    .error "skeleton requires implementation"
.endproc

; expansion_publish: Publish dual-device expansion profile for the session
; Inputs: expansion_* BSS fields set by selector
; Outputs: fingerprint and generation updated
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Recomputes expansion_fingerprint and bumps generation
.export expansion_publish
.proc expansion_publish
    .error "skeleton requires implementation"
.endproc
