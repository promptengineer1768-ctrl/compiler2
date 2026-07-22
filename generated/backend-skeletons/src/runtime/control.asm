; Generated from a trusted skeleton profile. Do not rename entries.

; ctrl_check_stop: STOP polling in long loops
; Inputs: none
; Outputs: Z=1 if STOP pressed
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_stkey
; Side effects: Polls STOP key via KERNAL bridge; bounded iteration check
.export ctrl_check_stop
.proc ctrl_check_stop
    .error "skeleton requires implementation"
.endproc

; ctrl_cont: CONT statement
; Inputs: valid continuation handle/generation
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_cont_handle, write:zp_cont_generation
; Side effects: Validates/restores compiled PC and runtime control/stack state
.export ctrl_cont
.proc ctrl_cont
    .error "skeleton requires implementation"
.endproc

; ctrl_do_init: DO statement initialization
; Inputs: loop descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Pushes DO frame onto control stack
.export ctrl_do_init
.proc ctrl_do_init
    .error "skeleton requires implementation"
.endproc

; ctrl_end: END statement
; Inputs: A=0 development editor, A<>0 standalone inspection shell
; Outputs: standalone does not return; development returns through editor dispatcher
; Clobbers: A X Y flags
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_stop_flag, write:zp_cont_handle
; Side effects: Calls unified graphics exit, then development editor or standalone READY shell
.export ctrl_end
.proc ctrl_end
    .error "skeleton requires implementation"
.endproc

; ctrl_exit_loop: EXIT DO/FOR
; Inputs: loop descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Pops control stack to matching DO, jumps past LOOP
.export ctrl_exit_loop
.proc ctrl_exit_loop
    .error "skeleton requires implementation"
.endproc

; ctrl_for_init: FOR statement initialization
; Inputs: var desc, start/limit/step in FAC1
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Pushes FOR frame onto control stack, initializes variable
.export ctrl_for_init
.proc ctrl_for_init
    .error "skeleton requires implementation"
.endproc

; ctrl_for_next: NEXT statement: update and test
; Inputs: var desc, loop descriptor
; Outputs: C=1 loop done, C=0 loop continues
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Increments variable, compares to limit, branches or pops
.export ctrl_for_next
.proc ctrl_for_next
    .error "skeleton requires implementation"
.endproc

; ctrl_gosub: GOSUB implementation
; Inputs: target line address
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_sublev
; Side effects: Pushes return address, jumps to target
.export ctrl_gosub
.proc ctrl_gosub
    .error "skeleton requires implementation"
.endproc

; ctrl_loop_test: LOOP condition test
; Inputs: loop descriptor, condition result
; Outputs: C=1 exit, C=0 continue
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Tests WHILE/UNTIL condition at loop bottom (posttest)
.export ctrl_loop_test
.proc ctrl_loop_test
    .error "skeleton requires implementation"
.endproc

; ctrl_on_gosub: ON ... GOSUB implementation
; Inputs: expr result in A, table ptr
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_sublev
; Side effects: Multi-way subroutine call
.export ctrl_on_gosub
.proc ctrl_on_gosub
    .error "skeleton requires implementation"
.endproc

; ctrl_on_goto: ON ... GOTO implementation
; Inputs: expr result in A, table ptr
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Multi-way branch: select line from table
.export ctrl_on_goto
.proc ctrl_on_goto
    .error "skeleton requires implementation"
.endproc

; ctrl_pop_loop_frame: Internal: pop loop frame
; Inputs: none
; Outputs: loop descriptor restored
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Pops loop frame from control stack
.export ctrl_pop_loop_frame
.proc ctrl_pop_loop_frame
    .error "skeleton requires implementation"
.endproc

; ctrl_push_loop_frame: Internal: push loop frame
; Inputs: loop descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Pushes loop frame (FOR/DO) onto control stack
.export ctrl_push_loop_frame
.proc ctrl_push_loop_frame
    .error "skeleton requires implementation"
.endproc

; ctrl_reset: Clear control and continuation state without changing shells
; Inputs: none
; Outputs: C=0
; Clobbers: A flags
; Flags: return_kind:rts, stack_delta:0, preserves:X Y, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_stop_flag, write:zp_cont_handle
; Side effects: Invalidates the published continuation and all tagged frames
.proc ctrl_reset
    .error "skeleton requires implementation"
.endproc

; ctrl_return: RETURN implementation
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_sublev
; Side effects: Pops return address, validates GOSUB nesting
.export ctrl_return
.proc ctrl_return
    .error "skeleton requires implementation"
.endproc

; ctrl_stop: STOP statement
; Inputs: generated continuation point and runtime frame handle
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_cont_handle, write:zp_cont_generation, write:zp_stop_flag
; Side effects: Publishes a generation-checked continuation descriptor, returns to shell
.export ctrl_stop
.proc ctrl_stop
    .error "skeleton requires implementation"
.endproc
