; Generated from a trusted skeleton profile. Do not rename entries.

; detect_check_minimum: Capacity threshold check
; Inputs: none
; Outputs: C=1 if below minimum
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Compares detected capacity against build-declared minimum
.export detect_check_minimum
.proc detect_check_minimum
    .error "skeleton requires implementation"
.endproc

; detect_expansion: Dual-device non-destructive expansion probe and profile publication
; Inputs: geoRAM and REU hardware state
; Outputs: C=0 with selected expansion profile, C=1 when neither device is valid
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Probes both devices with real non-destructive probes, prefers geoRAM, publishes store/assist policy
.export detect_expansion
.proc detect_expansion
    .error "skeleton requires implementation"
.endproc

; detect_georam: Sole installation detector
; Inputs: build-declared minimum/profile schema
; Outputs: X/Y=profile record, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Full non-destructive probe before arenas are trusted
.export detect_georam
.proc detect_georam
    .error "skeleton requires implementation"
.endproc

; detect_probe_aliasing: Aliasing/capacity detection
; Inputs: none
; Outputs: capacity
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Probes address-bit aliasing to bound total capacity
.export detect_probe_aliasing
.proc detect_probe_aliasing
    .error "skeleton requires implementation"
.endproc

; detect_probe_pattern1: First probe pattern
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes and verifies pattern order 1 on candidate pages
.export detect_probe_pattern1
.proc detect_probe_pattern1
    .error "skeleton requires implementation"
.endproc

; detect_probe_pattern2: Second probe pattern (debug)
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes and verifies pattern order 2 (debug: catches floating bus)
.export detect_probe_pattern2
.proc detect_probe_pattern2
    .error "skeleton requires implementation"
.endproc

; detect_publish_profile: Install profile
; Inputs: X/Y=validated detection result
; Outputs: X/Y=immutable profile
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Records 16 KiB block count, alias result, integrity fingerprint
.export detect_publish_profile
.proc detect_publish_profile
    .error "skeleton requires implementation"
.endproc

; detect_restore_state: State restoration (success or failure)
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Restores all saved bytes, selection, and processor status
.export detect_restore_state
.proc detect_restore_state
    .error "skeleton requires implementation"
.endproc

; detect_save_state: State preservation before probe
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Saves current geoRAM selection, probe bytes, processor status
.export detect_save_state
.proc detect_save_state
    .error "skeleton requires implementation"
.endproc

; detect_validate_profile: Session integrity
; Inputs: X/Y=installed profile
; Outputs: C=1 mismatch/corruption
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Bounded continuity check; mismatch calls fatal path, never resizes
.export detect_validate_profile
.proc detect_validate_profile
    .error "skeleton requires implementation"
.endproc
