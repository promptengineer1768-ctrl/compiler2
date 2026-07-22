; Generated from a trusted skeleton profile. Do not rename entries.

; georam_install_pages: Installs geoRAM payload
; Inputs: none
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Copies loaded image into geoRAM pages, byte-by-byte through window
.export georam_install_pages
.proc georam_install_pages
    .error "skeleton requires implementation"
.endproc

; georam_load_georam_file: Reads the geoRAM page image from D64
; Inputs: none
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Loads GEORAM file from disk into geoRAM pages via kernal_load
.export georam_load_georam_file
.proc georam_load_georam_file
    .error "skeleton requires implementation"
.endproc

; loader_check_sentinel: Sanity check after install
; Inputs: none
; Outputs: C=0 valid, C=1 missing
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Verifies $FFF9 guard byte
.export loader_check_sentinel
.proc loader_check_sentinel
    .error "skeleton requires implementation"
.endproc

; loader_detect_georam: Dual-device installation detector wrapper
; Inputs: none
; Outputs: C=0 selected store published (X/Y=geo pages when geo), C=1 neither valid
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Non-destructive dual probe; prefers geoRAM store; publishes expansion profile
.export loader_detect_georam
.proc loader_detect_georam
    .error "skeleton requires implementation"
.endproc

; loader_entry: Main loader entry at $080D
; Inputs: BASIC cold-start state
; Outputs: jumps to compiler_init on success; C=1 + ERR_LOAD on failure
; Clobbers: A X Y
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Dual-device probe, prefer geoRAM store, load GEORAM image, REU patch if REU store, fingerprint skip-reload, publish expansion profile
.export loader_entry
.proc loader_entry
    .error "skeleton requires implementation"
.endproc

; loader_install_ram_payload: Resident + runtime code installation
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Copies/decompresses RAM payload to runtime locations
.export loader_install_ram_payload
.proc loader_install_ram_payload
    .error "skeleton requires implementation"
.endproc

; loader_restore_banking: Post-install banking restore
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:true
; Zero page: none
; Side effects: Restores $01=$35 canonical runtime mapping
.export loader_restore_banking
.proc loader_restore_banking
    .error "skeleton requires implementation"
.endproc
