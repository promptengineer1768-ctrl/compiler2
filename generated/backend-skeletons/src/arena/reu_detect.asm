; Generated from a trusted skeleton profile. Do not rename entries.

; detect_reu: Non-destructive REU probe (>=512 KiB)
; Inputs: none
; Outputs: C=0 present and sized, C=1 absent/undersized; fingerprint published
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_tmp1, read:zp_tmp2, read:zp_tmp3, read:zp_tmp4, write:zp_tmp1, write:zp_tmp2, write:zp_tmp3, write:zp_tmp4
; Side effects: Saves/restores REC registers and REU probe bytes; publishes capacity and fingerprint
.export detect_reu
.proc detect_reu
    .error "skeleton requires implementation"
.endproc

; detect_reu_check_minimum: REU capacity threshold check (>=8 banks / 512 KiB)
; Inputs: detect_reu_capacity_banks filled
; Outputs: C=0 ok, C=1 undersized
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: none
.export detect_reu_check_minimum
.proc detect_reu_check_minimum
    .error "skeleton requires implementation"
.endproc

; detect_reu_restore_state: Restore REC registers and CPU port after REU probe
; Inputs: none
; Outputs: preserves carry as probe result
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Restores REC $DF01-$DF0A and $01
.export detect_reu_restore_state
.proc detect_reu_restore_state
    .error "skeleton requires implementation"
.endproc

; detect_reu_save_state: Save REC registers and CPU port before REU probe
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Snapshots REC $DF01-$DF0A and $01
.export detect_reu_save_state
.proc detect_reu_save_state
    .error "skeleton requires implementation"
.endproc
