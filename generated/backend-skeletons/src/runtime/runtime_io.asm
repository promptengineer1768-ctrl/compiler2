; Generated from a trusted skeleton profile. Do not rename entries.

; rio_chrin: Compiled channel read
; Inputs: X/Y=RI record containing one unsigned logical-file byte
; Outputs: A=byte
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: KERNAL-bridged character input
.export rio_chrin
.proc rio_chrin
    .error "skeleton requires implementation"
.endproc

; rio_chrout: Compiled channel write
; Inputs: X/Y=RW record containing unsigned logical-file and value bytes
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: KERNAL-bridged character output
.export rio_chrout
.proc rio_chrout
    .error "skeleton requires implementation"
.endproc

; rio_close: Compiled CLOSE implementation
; Inputs: X/Y=RC record containing one unsigned logical-file byte
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: KERNAL-bridged file close
.export rio_close
.proc rio_close
    .error "skeleton requires implementation"
.endproc

; rio_clrchn: Compiled CLRCHN
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: KERNAL-bridged channel restore
.export rio_clrchn
.proc rio_clrchn
    .error "skeleton requires implementation"
.endproc

; rio_load: LOAD implementation
; Inputs: X/Y=RL record with unsigned length/device/secondary bytes and address
; Outputs: X/Y=load result, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: KERNAL-bridged direct program load
.export rio_load
.proc rio_load
    .error "skeleton requires implementation"
.endproc

; rio_open: OPEN implementation
; Inputs: X/Y=RO record with unsigned logical/device/secondary/length bytes
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: KERNAL-bridged file open
.export rio_open
.proc rio_open
    .error "skeleton requires implementation"
.endproc

; rio_save: Language SAVE: token-class encode, materialize, KERNAL SAVE
; Inputs: X/Y=RS record with filename/device and exclusive workspace range
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Encodes published program by tokens (C2>3.5>V2), writes workspace, KERNAL SAVE
.export rio_save
.proc rio_save
    .error "skeleton requires implementation"
.endproc

; rio_verify: Language VERIFY: pure byte equality vs SAVE emission
; Inputs: X/Y=RL record with filename/device and candidate image address
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Compares memory against same token-class emission SAVE would write
.export rio_verify
.proc rio_verify
    .error "skeleton requires implementation"
.endproc
