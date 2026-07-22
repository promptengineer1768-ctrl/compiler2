; Generated from a trusted skeleton profile. Do not rename entries.

; kernal_chkin: CHKIN bridge
; Inputs: X=lf
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Sets input channel
.export kernal_chkin
.proc kernal_chkin
    .error "skeleton requires implementation"
.endproc

; kernal_chkout: CHKOUT bridge
; Inputs: X=lf
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Sets output channel
.export kernal_chkout
.proc kernal_chkout
    .error "skeleton requires implementation"
.endproc

; kernal_chrin: CHRIN bridge
; Inputs: none
; Outputs: A=byte
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Reads byte from input channel
.export kernal_chrin
.proc kernal_chrin
    .error "skeleton requires implementation"
.endproc

; kernal_chrout: CHROUT bridge
; Inputs: A=byte
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes byte to output channel
.export kernal_chrout
.proc kernal_chrout
    .error "skeleton requires implementation"
.endproc

; kernal_close: CLOSE bridge
; Inputs: A=lf
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Closes logical file
.export kernal_close
.proc kernal_close
    .error "skeleton requires implementation"
.endproc

; kernal_clrchn: CLRCHN bridge
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Restores default channels
.export kernal_clrchn
.proc kernal_clrchn
    .error "skeleton requires implementation"
.endproc

; kernal_getin: GETIN bridge
; Inputs: none
; Outputs: A=byte or $00
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Reads from keyboard buffer
.export kernal_getin
.proc kernal_getin
    .error "skeleton requires implementation"
.endproc

; kernal_load: LOAD bridge
; Inputs: A=mode, X/Y=addr
; Outputs: C=error, X/Y=ended addr
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Loads from device
.export kernal_load
.proc kernal_load
    .error "skeleton requires implementation"
.endproc

; kernal_open: OPEN bridge
; Inputs: prior SETLFS/SETNAM
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Opens file/channel
.export kernal_open
.proc kernal_open
    .error "skeleton requires implementation"
.endproc

; kernal_print_packed: Sole static-output-string emitter
; Inputs: X/Y=packed string with bit 7 set on final character
; Outputs: C=0
; Clobbers: A X Y flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_src
; Side effects: Masks and emits bytes through the final-character marker
.export kernal_print_packed
.proc kernal_print_packed
    .error "skeleton requires implementation"
.endproc

; kernal_rdtim: RDTIM bridge
; Inputs: none
; Outputs: A=lo, X=mid, Y=hi
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Reads jiffy clock
.export kernal_rdtim
.proc kernal_rdtim
    .error "skeleton requires implementation"
.endproc

; kernal_readst: READST bridge
; Inputs: none
; Outputs: A=status
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: write:zp_status
; Side effects: Reads KERNAL status
.export kernal_readst
.proc kernal_readst
    .error "skeleton requires implementation"
.endproc

; kernal_save: SAVE bridge
; Inputs: A=ZP-ptr, X/Y=end
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Saves to device
.export kernal_save
.proc kernal_save
    .error "skeleton requires implementation"
.endproc

; kernal_scnkey: SCNKEY bridge
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Scans keyboard matrix
.export kernal_scnkey
.proc kernal_scnkey
    .error "skeleton requires implementation"
.endproc

; kernal_setlfs: SETLFS bridge
; Inputs: A=lf, X=dev, Y=sa
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: write:zp_la, write:zp_sa, write:zp_fa
; Side effects: Sets logical/device/secondary parameters; does not open
.export kernal_setlfs
.proc kernal_setlfs
    .error "skeleton requires implementation"
.endproc

; kernal_setnam: SETNAM bridge
; Inputs: A=len, X/Y=name
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: write:zp_fnlen, write:zp_fnadr
; Side effects: Sets filename for next OPEN/LOAD/SAVE
.export kernal_setnam
.proc kernal_setnam
    .error "skeleton requires implementation"
.endproc

; kernal_settim: SETTIM bridge
; Inputs: A=lo, X=mid, Y=hi
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Sets jiffy clock
.export kernal_settim
.proc kernal_settim
    .error "skeleton requires implementation"
.endproc

; kernal_stop: STOP bridge
; Inputs: none
; Outputs: Z=1 if STOP pressed
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Checks STOP key
.export kernal_stop
.proc kernal_stop
    .error "skeleton requires implementation"
.endproc

; kernal_udtim: UDTIM bridge
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Advances jiffy clock one tick
.export kernal_udtim
.proc kernal_udtim
    .error "skeleton requires implementation"
.endproc
