; Generated from a trusted skeleton profile. Do not rename entries.

; reu_xip_active: REU XIP live-slot flag (BSS data symbol)
; Inputs: none
; Outputs: byte: nonzero while $CE00 miss slot is live
; Clobbers: none
; Flags: return_kind:data, stack_delta:0, preserves:A X Y, irq_safe:true, irq_masked_ok:true
; Zero page: none
; Side effects: Default 0; REU XIP module sets/clears; system_poke gates $CE00 on this
.export reu_xip_active
.proc reu_xip_active
    .error "skeleton requires implementation"
.endproc

; system_peek: PEEK
; Inputs: X/Y=16-bit address
; Outputs: A=byte
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Reads real C64 CPU address space under documented banking policy
.export system_peek
.proc system_peek
    .error "skeleton requires implementation"
.endproc

; system_poke: POKE
; Inputs: X/Y=16-bit address, A=already-coerced argument byte
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes real C64 address unless narrow control-plane protection denies it (ZP, high guard, $CE00 while reu_xip_active)
.export system_poke
.proc system_poke
    .error "skeleton requires implementation"
.endproc

; system_sys: SYS
; Inputs: X/Y=16-bit machine-code address
; Outputs: returned registers per stock-visible policy, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Calls user machine code with invalidation barrier
.export system_sys
.proc system_sys
    .error "skeleton requires implementation"
.endproc

; system_ti_load: TI
; Inputs: none
; Outputs: FAC1=current 24-bit jiffy value as an exact float
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Reads IRQ-owned clock atomically
.export system_ti_load
.proc system_ti_load
    .error "skeleton requires implementation"
.endproc

; system_ti_store: TI assignment
; Inputs: A/X/Y=new jiffy low/middle/high bytes
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Validates and sets clock through approved path
.export system_ti_store
.proc system_ti_store
    .error "skeleton requires implementation"
.endproc

; system_ti_string_load: TI$
; Inputs: X/Y=destination SD descriptor
; Outputs: C=error; destination receives HHMMSS
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Formats current clock with stock behavior
.export system_ti_string_load
.proc system_ti_string_load
    .error "skeleton requires implementation"
.endproc

; system_ti_string_store: TI$ assignment
; Inputs: X/Y=validated source SD containing HHMMSS
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Parses/sets clock with stock behavior
.export system_ti_string_store
.proc system_ti_string_store
    .error "skeleton requires implementation"
.endproc

; system_usr: USR
; Inputs: FAC1=argument, generated USR vector
; Outputs: FAC1=result, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Calls user routine with declared compatibility ABI
.export system_usr
.proc system_usr
    .error "skeleton requires implementation"
.endproc

; system_wait: WAIT
; Inputs: X/Y=six-byte SW/address/mask/xor record
; Outputs: C=error/STOP
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Polls real address and bank-safe STOP at bounded cadence
.export system_wait
.proc system_wait
    .error "skeleton requires implementation"
.endproc
