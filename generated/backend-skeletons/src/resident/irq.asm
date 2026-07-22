; Generated from a trusted skeleton profile. Do not rename entries.

; irq_cursor_blink: Bounded resident reverse-video cursor service; no geoRAM dependency
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:true, irq_masked_ok:true
; Zero page: read:zp_crsr_x, read:zp_crsr_y, read:zp_crsr_vis
; Side effects: Reverse-videos the screen cell at zp_crsr_x/y when zp_crsr_vis is set
.proc irq_cursor_blink
    .error "skeleton requires implementation"
.endproc

; irq_entry: Pinned entry: save A/X/Y/mapping, UDTIM, cursor, SCNKEY, CIA ack, restore, RTI
; Inputs: hardware IRQ frame (CPU has pushed PC/P; A/X/Y are live)
; Outputs: interrupted A/X/Y/P/PC and mapping restored
; Clobbers: internal IRQ save set
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:true, irq_masked_ok:true
; Zero page: none
; Side effects: Advances jiffy clock, updates keyboard state, blinks cursor
.export irq_entry
.proc irq_entry
    .error "skeleton requires implementation"
.endproc

; irq_restore_mapping: Called before RTI
; Inputs: saved interrupted $01/P
; Outputs: exact interrupted mapping/P restored
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:true, irq_masked_ok:true
; Zero page: none
; Side effects: Does not touch geoRAM selection
.proc irq_restore_mapping
    .error "skeleton requires implementation"
.endproc

; irq_scan_keyboard: Called only from irq_entry
; Inputs: IRQ-private call
; Outputs: none
; Clobbers: A X Y, declared flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:true, irq_masked_ok:true
; Zero page: none
; Side effects: Calls KERNAL SCNKEY directly after cursor service
.proc irq_scan_keyboard
    .error "skeleton requires implementation"
.endproc

; irq_update_jiffy: Called only from irq_entry
; Inputs: IRQ-private call
; Outputs: none
; Clobbers: A X Y, declared flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:true, irq_masked_ok:true
; Zero page: none
; Side effects: Calls KERNAL UDTIM directly while IRQ entry owns $01=$36
.proc irq_update_jiffy
    .error "skeleton requires implementation"
.endproc
