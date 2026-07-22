; Generated from a trusted skeleton profile. Do not rename entries.

; program_classify_file: Classify on-disk image before decode
; Inputs: X/Y=input byte-stream handle
; Outputs: A=0 V2 / 1 C2P1 / 2 Plus4, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Reads only bounded header bytes
.export program_classify_file
.proc program_classify_file
    .error "skeleton requires implementation"
.endproc

; program_decode_basic35: Plus/4 BASIC 3.5 import
; Inputs: X/Y=input handle
; Outputs: X/Y=scratch program handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Validates `$1001` links, ordering, terminators for Plus/4 PRG
.export program_decode_basic35
.proc program_decode_basic35
    .error "skeleton requires implementation"
.endproc

; program_decode_extended: Versioned extension import
; Inputs: X/Y=input handle
; Outputs: X/Y=scratch program handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Validates magic, format/ABI version, token namespace, bounds
.export program_decode_extended
.proc program_decode_extended
    .error "skeleton requires implementation"
.endproc

; program_decode_stock: BASIC V2 import
; Inputs: X/Y=input handle
; Outputs: X/Y=scratch program handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Validates `$0801`, links, ordering, terminators, stock tokens/contexts
.export program_decode_stock
.proc program_decode_stock
    .error "skeleton requires implementation"
.endproc

; program_encode_basic35: Byte-compatible Plus/4 BASIC 3.5 SAVE
; Inputs: X/Y=logical program handle
; Outputs: X/Y=byte-stream handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Prepends `$1001` and recomputes absolute next-line pointers
.export program_encode_basic35
.proc program_encode_basic35
    .error "skeleton requires implementation"
.endproc

; program_encode_extended: Extension SAVE
; Inputs: X/Y=logical program handle
; Outputs: X/Y=byte-stream handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes unambiguous versioned envelope
.export program_encode_extended
.proc program_encode_extended
    .error "skeleton requires implementation"
.endproc

; program_encode_stock: Byte-compatible BASIC V2 SAVE
; Inputs: X/Y=logical program handle
; Outputs: X/Y=byte-stream handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Canonically recomputes every next-line pointer
.export program_encode_stock
.proc program_encode_stock
    .error "skeleton requires implementation"
.endproc

; program_select_save_format: Token-class SAVE format selection
; Inputs: X/Y=normalized logical program handle
; Outputs: A=SAVE_FORMAT_V2/BASICV35/C2P1, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Scans tokens outside REM/string/DATA; priority C2 > 3.5 > V2
.export program_select_save_format
.proc program_select_save_format
    .error "skeleton requires implementation"
.endproc
