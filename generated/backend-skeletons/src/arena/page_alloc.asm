; Generated from a trusted skeleton profile. Do not rename entries.

; page_alloc: Page allocation
; Inputs: X/Y=extent request (16-bit count/alignment/owner)
; Outputs: X/Y=extent handle, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Allocates pages from free bitmap
.export page_alloc
.proc page_alloc
    .error "skeleton requires implementation"
.endproc

; page_alloc_count: Free page count query
; Inputs: none
; Outputs: X/Y=16-bit pages free
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Supports at least 2,048 pages at the 512 KiB minimum
.export page_alloc_count
.proc page_alloc_count
    .error "skeleton requires implementation"
.endproc

; page_alloc_init: Page allocator cold-start
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Initializes free-page bitmap from detected geoRAM capacity
.export page_alloc_init
.proc page_alloc_init
    .error "skeleton requires implementation"
.endproc

; page_alloc_largest: Fragmentation query
; Inputs: none
; Outputs: X/Y=16-bit largest run
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Returns largest contiguous extent
.export page_alloc_largest
.proc page_alloc_largest
    .error "skeleton requires implementation"
.endproc

; page_check_in_range: Bounds check
; Inputs: X/Y=extent descriptor
; Outputs: C=1 if out of profile/owner bounds
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Uses logical page/block capacity from installed profile
.export page_check_in_range
.proc page_check_in_range
    .error "skeleton requires implementation"
.endproc

; page_free: Page deallocation
; Inputs: X/Y=validated extent handle
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Returns pages to free bitmap and checks ownership/generation
.export page_free
.proc page_free
    .error "skeleton requires implementation"
.endproc
