; Generated from a trusted skeleton profile. Do not rename entries.

; georam_call_group_n: Generated returning entry for each 256-ID group
; Inputs: X=routine index; target inputs per generated ABI
; Outputs: target outputs per generated ABI
; Clobbers: dispatch X plus generated target clobbers
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_gr_block, write:zp_gr_page, write:zp_gr_ctx_sp, write:zp_gr_call_id
; Side effects: Resolves group tables, calls target, captures results, restores caller selection/P
.export georam_call_group_n
.proc georam_call_group_n
    .error "skeleton requires implementation"
.endproc

; georam_checksum: Integrity helper
; Inputs: X/Y=validated extent record
; Outputs: X/Y=checksum, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Restores caller selection
.export georam_checksum
.proc georam_checksum
    .error "skeleton requires implementation"
.endproc

; georam_copy_from_ram: Bulk ingress
; Inputs: X/Y=bounded copy descriptor
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Copies normal RAM to geoRAM and restores selection
.export georam_copy_from_ram
.proc georam_copy_from_ram
    .error "skeleton requires implementation"
.endproc

; georam_copy_pages: geoRAM-to-geoRAM copy
; Inputs: X/Y=source descriptor; source ptr fields point to destination descriptor
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Copies through resident scratch and restores caller selection
.export georam_copy_pages
.proc georam_copy_pages
    .error "skeleton requires implementation"
.endproc

; georam_copy_to_ram: Bulk egress
; Inputs: X/Y=bounded copy descriptor
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Copies geoRAM to normal RAM and restores selection
.export georam_copy_to_ram
.proc georam_copy_to_ram
    .error "skeleton requires implementation"
.endproc

; georam_ctx_pop: Internal: restore before returning to caller
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_gr_ctx_sp, write:zp_gr_block, write:zp_gr_page
; Side effects: Pops and restores caller block/page/registers from context stack
.export georam_ctx_pop
.proc georam_ctx_pop
    .error "skeleton requires implementation"
.endproc

; georam_ctx_push: Internal: save caller geoRAM state before nesting
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_gr_ctx_sp, write:zp_gr_block, write:zp_gr_page
; Side effects: Pushes current block/page/registers onto context stack
.export georam_ctx_push
.proc georam_ctx_push
    .error "skeleton requires implementation"
.endproc

; georam_read_byte: Handle-based byte read
; Inputs: X/Y=stable logical byte handle
; Outputs: A=byte, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Maps, validates, and restores caller selection
.export georam_read_byte
.proc georam_read_byte
    .error "skeleton requires implementation"
.endproc

; georam_read_word: Handle-based word read
; Inputs: X/Y=stable logical word handle
; Outputs: X/Y=word, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Rejects boundary/owner/generation errors; restores selection
.export georam_read_word
.proc georam_read_word
    .error "skeleton requires implementation"
.endproc

; georam_select: Internal/diagnostic only: selects geoRAM page
; Inputs: A=page, X=block
; Outputs: none
; Clobbers: A X, flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_gr_block, write:zp_gr_page
; Side effects: Writes $DFFE and $DFFF; updates software mirror
.proc georam_select
    .error "skeleton requires implementation"
.endproc

; georam_tail_group_n: Generated tail-transfer entry; not an alias of returning call
; Inputs: X=routine index; target inputs per generated ABI
; Outputs: does not return to current frame
; Clobbers: dispatch X plus generated target clobbers
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_gr_block, write:zp_gr_page, write:zp_gr_ctx_sp, write:zp_gr_call_id
; Side effects: Reuses/removes current context frame before transfer
.export georam_tail_group_n
.proc georam_tail_group_n
    .error "skeleton requires implementation"
.endproc

; georam_verify_mirror: Integrity check for selection ownership
; Inputs: none
; Outputs: C=1 if mismatch
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Debug-only: compares software mirror against $DFFE/$DFFF
.proc georam_verify_mirror
    .error "skeleton requires implementation"
.endproc

; georam_write_byte: Handle-based byte write
; Inputs: X/Y=typed handle/value record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Maps, validates, writes, restores caller selection
.export georam_write_byte
.proc georam_write_byte
    .error "skeleton requires implementation"
.endproc

; georam_write_word: Handle-based word write
; Inputs: X/Y=typed handle/value record
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Rejects cross-boundary/owner/generation errors
.export georam_write_word
.proc georam_write_word
    .error "skeleton requires implementation"
.endproc

; hibasic_graphics_reserve: Save occupied HIBASIC bytes before graphics claims high RAM
; Inputs: none
; Outputs: C=0
; Clobbers: A X Y flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_tmptr, write:zp_tmptr, write:zp_gr_block, write:zp_gr_page
; Side effects: Copies HIBASIC to dedicated geoRAM block 31 pages 32 onward
.proc hibasic_graphics_reserve
    .error "skeleton requires implementation"
.endproc

; hibasic_graphics_restore: Restore displaced HIBASIC bytes and release graphics reservation
; Inputs: none
; Outputs: C=0
; Clobbers: A X Y flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_tmptr, write:zp_tmptr, write:zp_gr_block, write:zp_gr_page
; Side effects: Copies dedicated geoRAM backing bytes to HIBASIC
.proc hibasic_graphics_restore
    .error "skeleton requires implementation"
.endproc
