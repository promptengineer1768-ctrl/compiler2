; Generated from a trusted skeleton profile. Do not rename entries.

; var_coerce: Type coercion with error on loss
; Inputs: FAC1=value, target variable kind in A
; Outputs: result in FAC1 or X/Y, C=0; C=1 on unsupported or lossy conversion
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_fac1, write:zp_fac1
; Side effects: Coerces value to target variable kind and reclassifies FAC before integer narrowing
.export var_coerce
.proc var_coerce
    .error "skeleton requires implementation"
.endproc

; var_load_float: Float variable load
; Inputs: X/Y=VD float descriptor
; Outputs: FAC1=float value, C=0; C=1/A=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, read:zp_dest, read:zp_fac1, write:zp_src, write:zp_dest, write:zp_fac1
; Side effects: Loads 5-byte float through a validated VD descriptor
.export var_load_float
.proc var_load_float
    .error "skeleton requires implementation"
.endproc

; var_load_int: Integer variable load
; Inputs: X/Y=VD integer descriptor
; Outputs: X/Y=16-bit value, C=0; C=1/A=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, read:zp_dest, write:zp_src, write:zp_dest
; Side effects: Loads 16-bit integer through a validated VD descriptor
.export var_load_int
.proc var_load_int
    .error "skeleton requires implementation"
.endproc

; var_load_string: String variable load
; Inputs: X/Y=VD string descriptor
; Outputs: X/Y=ptr, A=len, C=0; C=1/A=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, read:zp_dest, write:zp_src, write:zp_dest
; Side effects: Loads string descriptor through a validated VD descriptor
.export var_load_string
.proc var_load_string
    .error "skeleton requires implementation"
.endproc

; var_promote_to_float: Type promotion: int → float
; Inputs: X/Y=integer value
; Outputs: FAC1=float equivalent, C=0
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_fac1, write:zp_fac1
; Side effects: Promotes integer to float
.export var_promote_to_float
.proc var_promote_to_float
    .error "skeleton requires implementation"
.endproc

; var_resolve: Variable resolution: descriptor → address
; Inputs: X/Y=VD variable descriptor
; Outputs: X/Y=cell address, C=0; C=1/A=error on malformed or stale descriptor
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, read:zp_dest, write:zp_src, write:zp_dest
; Side effects: Validates VD shape and resolves direct or arena-backed descriptor to live memory cell
.export var_resolve
.proc var_resolve
    .error "skeleton requires implementation"
.endproc

; var_set_type: Variable type annotation
; Inputs: X/Y=VD descriptor, A=variable kind
; Outputs: C=0 on success; C=1/A=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, write:zp_src
; Side effects: Updates kind tag in a validated VD descriptor
.export var_set_type
.proc var_set_type
    .error "skeleton requires implementation"
.endproc

; var_store_float: Float variable store
; Inputs: X/Y=VF store request, FAC1=value
; Outputs: C=0 on success; C=1/A=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, read:zp_dest, read:zp_fac1, write:zp_src, write:zp_dest
; Side effects: Stores 5-byte float through a validated VF request and VD descriptor
.export var_store_float
.proc var_store_float
    .error "skeleton requires implementation"
.endproc

; var_store_int: Integer variable store
; Inputs: X/Y=VI store request
; Outputs: C=0 on success; C=1/A=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, read:zp_dest, write:zp_src, write:zp_dest
; Side effects: Stores 16-bit integer through a validated VI request and VD descriptor
.export var_store_int
.proc var_store_int
    .error "skeleton requires implementation"
.endproc

; var_store_string: String variable store
; Inputs: X/Y=VS store request
; Outputs: C=0 on success; C=1/A=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_src, read:zp_dest, write:zp_src, write:zp_dest
; Side effects: Stores string descriptor through a validated VS request and VD descriptor
.export var_store_string
.proc var_store_string
    .error "skeleton requires implementation"
.endproc
