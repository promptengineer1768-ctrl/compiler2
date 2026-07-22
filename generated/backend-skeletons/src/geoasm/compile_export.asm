; Generated from a trusted skeleton profile. Do not rename entries.

; export_apply_soft_budgets: Export warning threshold state
; Inputs: export range state
; Outputs: C=clear
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Publishes edge-triggered export warnings
.export export_apply_soft_budgets
.proc export_apply_soft_budgets
    .error "skeleton requires implementation"
.endproc

; export_check_budgets: Code/workspace budgets
; Inputs: X/Y=standalone image/workspace plan
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Proves `$0801-$CFFF` load range and disjoint workspace
.export export_check_budgets
.proc export_check_budgets
    .error "skeleton requires implementation"
.endproc

; export_collect_dependencies: Standalone closure
; Inputs: X/Y=compiled image
; Outputs: X/Y=runtime dependency set, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Rejects editor/compiler/source/geoRAM dependencies
.export export_collect_dependencies
.proc export_collect_dependencies
    .error "skeleton requires implementation"
.endproc

; export_link_image: Export link
; Inputs: X/Y=image/options
; Outputs: X/Y=standalone image, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Resolves runtime helpers, metadata, descriptors, shell
.export export_link_image
.proc export_link_image
    .error "skeleton requires implementation"
.endproc

; export_parse_command: Syntax/defaults
; Inputs: X/Y=COMPILE command record
; Outputs: X/Y=options, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Defaults filename `COMPILED`, device from persistent `fa`
.export export_parse_command
.proc export_parse_command
    .error "skeleton requires implementation"
.endproc

; export_select_layout: Export layout selection
; Inputs: export range state
; Outputs: C=clear
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:X Y, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Sets stock or developer export layout metadata
.export export_select_layout
.proc export_select_layout
    .error "skeleton requires implementation"
.endproc

; export_write_prg: COMPILE output
; Inputs: X/Y=validated image/options
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Saves through KERNAL sequence to devices 8-11
.export export_write_prg
.proc export_write_prg
    .error "skeleton requires implementation"
.endproc
