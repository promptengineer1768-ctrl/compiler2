; Generated from a trusted skeleton profile. Do not rename entries.

; opt_build_effect_summaries: Generation-cached read/write/escape/invalidation summaries
; Inputs: X/Y=typed IR generation
; Outputs: X/Y=summary table, C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_expr_ptr1, write:zp_tmp1, write:zp_tmp2
; Side effects: One bottom-up pass; parent loops merge child masks
.export opt_build_effect_summaries
.proc opt_build_effect_summaries
    .error "skeleton requires implementation"
.endproc

; opt_check_aliasing: Shared alias predicate; no body rescan
; Inputs: X/Y=variable/summary record
; Outputs: C=1 if aliased write found
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Reads cached alias/escape/bank-change facts
.export opt_check_aliasing
.proc opt_check_aliasing
    .error "skeleton requires implementation"
.endproc

; opt_check_invalidation: Shared invalidation predicate; no body rescan
; Inputs: X/Y=loop effect-summary record
; Outputs: A=dirty mask
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmp1
; Side effects: Reads cached POKE/SYS/CLR/DIM/callback/string barriers
.export opt_check_invalidation
.proc opt_check_invalidation
    .error "skeleton requires implementation"
.endproc

; opt_check_stop_poll: STOP polling eligibility for long loops
; Inputs: loop descriptor in X/Y
; Outputs: C=1 if long loop needing poll
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Determines if loop body is long enough to require STOP polling
.export opt_check_stop_poll
.proc opt_check_stop_poll
    .error "skeleton requires implementation"
.endproc

; opt_eligible_for_do_fast: DO/LOOP fast-path eligibility predicate
; Inputs: loop descriptor in X/Y
; Outputs: C=1 if eligible
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_expr_ptr1, write:zp_tmp1
; Side effects: Checks DO/LOOP fast-path eligibility (bare, WHILE, UNTIL)
.export opt_eligible_for_do_fast
.proc opt_eligible_for_do_fast
    .error "skeleton requires implementation"
.endproc

; opt_eligible_for_for_fast: FOR/NEXT fast-path eligibility predicate
; Inputs: loop descriptor in X/Y
; Outputs: C=1 if eligible
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_expr_ptr1, write:zp_tmp1
; Side effects: Checks all FOR/NEXT fast-path eligibility conditions per §11
.export opt_eligible_for_for_fast
.proc opt_eligible_for_for_fast
    .error "skeleton requires implementation"
.endproc

; opt_propagate_dirty: Dirty mask propagation through nesting
; Inputs: dirty mask in A
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Propagates dirty masks through nested loop descriptors
.export opt_propagate_dirty
.proc opt_propagate_dirty
    .error "skeleton requires implementation"
.endproc

; opt_run_passes: Top-level optimization driver
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Runs all optimization passes over current IR
.export opt_run_passes
.proc opt_run_passes
    .error "skeleton requires implementation"
.endproc

; opt_select_branch_polarity: Polarity selection for WHILE/UNTIL conditions
; Inputs: condition type in A
; Outputs: A=branch opcode
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Selects branch polarity (UNTIL is NOT inverted by scattered NOT)
.export opt_select_branch_polarity
.proc opt_select_branch_polarity
    .error "skeleton requires implementation"
.endproc
