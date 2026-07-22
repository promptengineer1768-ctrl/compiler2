; Generated from a trusted skeleton profile. Do not rename entries.

; codegen_emit_data: DATA emitter
; Inputs: DATA values
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Emits DATA record into data section
.export codegen_emit_data
.proc codegen_emit_data
    .error "skeleton requires implementation"
.endproc

; codegen_emit_dim: DIM emitter
; Inputs: DIM var(sizes)
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Emits array dimension allocation call
.export codegen_emit_dim
.proc codegen_emit_dim
    .error "skeleton requires implementation"
.endproc

; codegen_emit_do_fast: DO/LOOP optimized emitter
; Inputs: eligible loop descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp4
; Side effects: Emits native backedge for bare DO/LOOP or native pretest/posttest
.export codegen_emit_do_fast
.proc codegen_emit_do_fast
    .error "skeleton requires implementation"
.endproc

; codegen_emit_do_generic: DO/LOOP generic emitter
; Inputs: loop descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp4
; Side effects: Emits frame-based generic DO/LOOP with full condition evaluation
.export codegen_emit_do_generic
.proc codegen_emit_do_generic
    .error "skeleton requires implementation"
.endproc

; codegen_emit_exit: EXIT DO/FOR emitter
; Inputs: exit descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Emits EXIT DO/FOR: resolves descriptor target or generic control stack
.export codegen_emit_exit
.proc codegen_emit_exit
    .error "skeleton requires implementation"
.endproc

; codegen_emit_for_fast: FOR/NEXT optimized emitter
; Inputs: eligible loop descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp4
; Side effects: Emits direct integer FOR/NEXT fast path: init var, compare, branch, update
.export codegen_emit_for_fast
.proc codegen_emit_for_fast
    .error "skeleton requires implementation"
.endproc

; codegen_emit_for_generic: FOR/NEXT generic emitter
; Inputs: loop descriptor
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp4
; Side effects: Emits frame-based generic FOR/NEXT with full error handling
.export codegen_emit_for_generic
.proc codegen_emit_for_generic
    .error "skeleton requires implementation"
.endproc

; codegen_emit_gosub: GOSUB emitter
; Inputs: target line
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Emits GOSUB with push return address, validate line exists
.export codegen_emit_gosub
.proc codegen_emit_gosub
    .error "skeleton requires implementation"
.endproc

; codegen_emit_if: IF/THEN/ELSE emitter
; Inputs: IR if-statement
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Emits IF cond THEN stmt [ELSE stmt]
.export codegen_emit_if
.proc codegen_emit_if
    .error "skeleton requires implementation"
.endproc

; codegen_emit_input: INPUT statement emitter
; Inputs: INPUT prompt, var list
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Emits INPUT with prompt, channel select, type coercion
.export codegen_emit_input
.proc codegen_emit_input
    .error "skeleton requires implementation"
.endproc

; codegen_emit_let: LET/assignment emitter
; Inputs: assignment target, expr
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Emits assignment with type promotion if needed
.export codegen_emit_let
.proc codegen_emit_let
    .error "skeleton requires implementation"
.endproc

; codegen_emit_on: ON GOTO/GOSUB emitter
; Inputs: ON expr GOTO/GOSUB
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Emits multi-way branch
.export codegen_emit_on
.proc codegen_emit_on
    .error "skeleton requires implementation"
.endproc

; codegen_emit_print: PRINT statement emitter
; Inputs: PRINT expression list
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp2
; Side effects: Emits PRINT with formatting, semicolons, commas, TAB, SPC
.export codegen_emit_print
.proc codegen_emit_print
    .error "skeleton requires implementation"
.endproc

; codegen_emit_read: READ emitter
; Inputs: READ var list
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Emits READ with type coercion from DATA stream
.export codegen_emit_read
.proc codegen_emit_read
    .error "skeleton requires implementation"
.endproc

; codegen_emit_return: RETURN emitter
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Emits RETURN: pop return address, validate nesting
.export codegen_emit_return
.proc codegen_emit_return
    .error "skeleton requires implementation"
.endproc

; codegen_emit_stmt: Statement code emitter
; Inputs: IR statement record
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1, write:zp_tmp4
; Side effects: Emits native code for one statement
.export codegen_emit_stmt
.proc codegen_emit_stmt
    .error "skeleton requires implementation"
.endproc

; screen_clear: CLR/HOME
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Clears screen, homes cursor
.export screen_clear
.proc screen_clear
    .error "skeleton requires implementation"
.endproc

; screen_cursor_down: Authoritative ABI contract for screen_cursor_down
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Advances cursor row, scrolls if needed
.export screen_cursor_down
.proc screen_cursor_down
    .error "skeleton requires implementation"
.endproc

; screen_cursor_left: Authoritative ABI contract for screen_cursor_left
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Retreats cursor column, wraps to prev line
.export screen_cursor_left
.proc screen_cursor_left
    .error "skeleton requires implementation"
.endproc

; screen_cursor_off: Authoritative ABI contract for screen_cursor_off
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Clears cursor visible flag
.export screen_cursor_off
.proc screen_cursor_off
    .error "skeleton requires implementation"
.endproc

; screen_cursor_on: Authoritative ABI contract for screen_cursor_on
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Sets cursor visible flag
.export screen_cursor_on
.proc screen_cursor_on
    .error "skeleton requires implementation"
.endproc

; screen_cursor_right: Authoritative ABI contract for screen_cursor_right
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Advances cursor column, wraps to next line
.export screen_cursor_right
.proc screen_cursor_right
    .error "skeleton requires implementation"
.endproc

; screen_cursor_up: Authoritative ABI contract for screen_cursor_up
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Retreats cursor row
.export screen_cursor_up
.proc screen_cursor_up
    .error "skeleton requires implementation"
.endproc

; screen_getchar: For LIST display
; Inputs: none
; Outputs: A=char or $00
; Clobbers: A X
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Reads character at cursor position
.export screen_getchar
.proc screen_getchar
    .error "skeleton requires implementation"
.endproc

; screen_init: Cold-start screen setup
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Initializes screen editor state, clears screen
.export screen_init
.proc screen_init
    .error "skeleton requires implementation"
.endproc

; screen_line_input: Bounded line capture for editor; respects quote mode
; Inputs: zp_linebuf=buffer ptr
; Outputs: zp_line_len=length
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Captures one logical line from screen into buffer
.export screen_line_input
.proc screen_line_input
    .error "skeleton requires implementation"
.endproc

; screen_putchar: Resident output primitive
; Inputs: A=char
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Writes character at cursor, advances cursor
.export screen_putchar
.proc screen_putchar
    .error "skeleton requires implementation"
.endproc

; screen_scroll_up: When cursor below bottom
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Scrolls screen memory up one line
.export screen_scroll_up
.proc screen_scroll_up
    .error "skeleton requires implementation"
.endproc
