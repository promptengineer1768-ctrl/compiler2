; Generated from a trusted skeleton profile. Do not rename entries.

; compiler_init: System entry after successful install
; Inputs: jump from loader
; Outputs: enters editor main loop
; Clobbers: A X Y
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: XIP post-bootstrap init: latches phase, loads high/cold images, initializes arenas/editor, installs vectors, enters main loop
.export compiler_init
.proc compiler_init
    .error "skeleton requires implementation"
.endproc

; init_arenas: Arena initialization
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Constructs arena directory, stamps generations
.proc init_arenas
    .error "skeleton requires implementation"
.endproc

; init_clear_bss: Clears all uninitialized workspace
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Zeroes COMPILER_BSS segment
.proc init_clear_bss
    .error "skeleton requires implementation"
.endproc

; init_editor: Editor cold-start
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Initializes editor state, clears screen
.proc init_editor
    .error "skeleton requires implementation"
.endproc

; init_enter_main_loop: Forever: capture line, dispatch
; Inputs: none
; Outputs: never returns
; Clobbers: []
; Flags: return_kind:non_returning, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Enters editor main loop
.proc init_enter_main_loop
    .error "skeleton requires implementation"
.endproc
