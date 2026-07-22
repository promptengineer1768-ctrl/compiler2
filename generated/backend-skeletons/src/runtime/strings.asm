; Generated from a trusted skeleton profile. Do not rename entries.

; str_alloc: String allocation
; Inputs: X/Y=SA request (magic, destination SD pointer, length)
; Outputs: C=success/error; destination receives validated 12-byte SD descriptor
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Allocates one owned page in the string arena for nonempty payloads and initializes the caller-owned SD descriptor
.export str_alloc
.proc str_alloc
    .error "skeleton requires implementation"
.endproc

; str_asc: ASC function
; Inputs: X/Y=validated 12-byte SD descriptor
; Outputs: A=first PETSCII byte, C=success/error
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Errors on an empty string per stock behavior
.export str_asc
.proc str_asc
    .error "skeleton requires implementation"
.endproc

; str_assign: String assignment with copy semantics
; Inputs: X/Y=SX request (magic, destination SD pointer, source SD pointer)
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Atomically replaces the destination with an independent arena-backed copy of the validated source
.export str_assign
.proc str_assign
    .error "skeleton requires implementation"
.endproc

; str_chr: CHR$ function
; Inputs: X/Y=SH request (magic, destination SD pointer, PETSCII byte)
; Outputs: C=success/error; destination receives one-byte SD descriptor
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Creates one-character string using C64 PETSCII byte semantics
.export str_chr
.proc str_chr
    .error "skeleton requires implementation"
.endproc

; str_cmp: String comparison
; Inputs: X/Y=SP request (magic, left SD pointer, right SD pointer)
; Outputs: A=$FF/0/$01 for less/equal/greater, C=success/error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: PETSCII bytewise comparison per stock semantics
.export str_cmp
.proc str_cmp
    .error "skeleton requires implementation"
.endproc

; str_concat: String concatenation (+)
; Inputs: X/Y=SC request (magic, destination SD pointer, left SD pointer, right SD pointer)
; Outputs: C=success/error; destination receives result SD descriptor
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Atomically allocates and writes an alias-safe concatenation; rejects results longer than 255 bytes
.export str_concat
.proc str_concat
    .error "skeleton requires implementation"
.endproc

; str_copy: Descriptor string copy
; Inputs: X/Y=SX request (magic, destination SD pointer, source SD pointer)
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Atomically replaces the destination with an independent arena-backed copy of the validated source
.export str_copy
.proc str_copy
    .error "skeleton requires implementation"
.endproc

; str_export_bytes: Export one validated SD to a bounded normal-memory buffer
; Inputs: X/Y=SE request (magic, source SD, destination pointer, capacity)
; Outputs: A=length and C=0, or C=1 on validation/capacity error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_src, write:zp_dest
; Side effects: Copies only after descriptor and capacity validation
.export str_export_bytes
.proc str_export_bytes
    .error "skeleton requires implementation"
.endproc

; str_free: String deallocation
; Inputs: X/Y=caller-owned 12-byte SD descriptor
; Outputs: C=success/error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Returns the owned string-arena page and invalidates the SD descriptor; rejects stale and double frees
.export str_free
.proc str_free
    .error "skeleton requires implementation"
.endproc

; str_from_bytes: Import a bounded normal-memory byte string into one SD
; Inputs: X/Y=SB request (magic, destination SD, source pointer, length)
; Outputs: C=success/error; destination receives an arena-backed SD
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_src, write:zp_dest
; Side effects: Atomically imports bytes and replaces the destination ownership
.export str_from_bytes
.proc str_from_bytes
    .error "skeleton requires implementation"
.endproc

; str_left: LEFT$ function
; Inputs: X/Y=SL request (magic, destination SD pointer, source SD pointer, count)
; Outputs: C=success/error; destination receives result SD descriptor
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Atomically allocates and writes alias-safe LEFT$ bytes
.export str_left
.proc str_left
    .error "skeleton requires implementation"
.endproc

; str_len: LEN function
; Inputs: X/Y=validated 12-byte SD descriptor
; Outputs: A=length, C=success/error
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Returns string length
.export str_len
.proc str_len
    .error "skeleton requires implementation"
.endproc

; str_mid: MID$ function
; Inputs: X/Y=SM request (magic, destination SD pointer, source SD pointer, one-based start, count)
; Outputs: C=success/error; destination receives result SD descriptor
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Atomically allocates and writes alias-safe MID$ bytes
.export str_mid
.proc str_mid
    .error "skeleton requires implementation"
.endproc

; str_right: RIGHT$ function
; Inputs: X/Y=SR request (magic, destination SD pointer, source SD pointer, count)
; Outputs: C=success/error; destination receives result SD descriptor
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Atomically allocates and writes alias-safe RIGHT$ bytes
.export str_right
.proc str_right
    .error "skeleton requires implementation"
.endproc

; str_str: STR$ function
; Inputs: X/Y=ST request (magic, destination SD pointer); FAC1=numeric value
; Outputs: C=success/error; destination receives formatted SD descriptor
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Formats float to numeric string
.export str_str
.proc str_str
    .error "skeleton requires implementation"
.endproc

; str_val: VAL function
; Inputs: X/Y=validated 12-byte SD descriptor
; Outputs: FAC1=numeric value, C=success/error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_fac1
; Side effects: Parses numeric string to float
.export str_val
.proc str_val
    .error "skeleton requires implementation"
.endproc
