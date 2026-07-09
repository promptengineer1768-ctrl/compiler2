; src/runtime/control.asm
; Typed control-stack runtime for compiled BASIC control flow.
;
; FOR descriptor (12 bytes): 'F', type (0=FLOAT, 1=INT1, 2=INT2, 3=INT3), variable pointer,
; start, limit, step, and compiled backedge, all little endian.
; DO descriptor (4 bytes): 'D', flags (bit 0=condition, bit 1=UNTIL), backedge.
; Continuation descriptor (39 bytes): 'C', generation, resume PC, saved stack
; byte count, then the 34-byte tagged control stack.
;
; Public entries use X/Y for descriptor pointers unless documented otherwise.
; C=1 reports malformed input, stack failure, a completed FOR, or loop exit.
; Clobbers: A, X, Y. Zero page: zp_src, zp_dst, zp_tmp1, zp_tmp2,
; zp_cont_handle, zp_cont_generation, zp_stop_flag.

.include "common/zp.inc"
.include "common/constants.asm"

.import editor_ready_transition, graphics_exit, hibasic_graphics_restore, inspect_shell
.import math_add, math_cmp, math_int_to_float

CTRL_STACK_BYTES = 34
CTRL_FRAME_BYTES = 3
CTRL_TAG_FOR = $46
CTRL_TAG_DO = $44
CTRL_TAG_GOSUB = $47
TYPE_FLOAT = $00
TYPE_INT1 = $01
TYPE_INT2 = $02
TYPE_INT3 = $03
zp_dst = zp_tmp3

.segment "BSS"
ctrl_stack:
    .res CTRL_STACK_BYTES
ctrl_sp:
    .res 1
ctrl_last_target:
    .res 2
ctrl_descriptor:
    .res 2

.segment "CODE"

; Push tag A and pointer X/Y as one bounded frame.
_push_frame:
    sta zp_tmp1
    stx zp_src
    sty zp_src+1
    ldx ctrl_sp
    cpx #(CTRL_STACK_BYTES-CTRL_FRAME_BYTES+1)
    bcs @full
    lda zp_tmp1
    sta ctrl_stack, x
    inx
    lda zp_src
    sta ctrl_stack, x
    inx
    lda zp_src+1
    sta ctrl_stack, x
    inx
    stx ctrl_sp
    clc
    rts
@full:
    sec
    rts

; Pop top frame. A=tag, X/Y=pointer.
_pop_frame:
    ldx ctrl_sp
    cpx #CTRL_FRAME_BYTES
    bcc @empty
    dex
    lda ctrl_stack, x
    tay
    dex
    lda ctrl_stack, x
    sta zp_tmp1
    dex
    stx ctrl_sp
    lda ctrl_stack, x
    ldx zp_tmp1
    clc
    rts
@empty:
    sec
    rts

; Peek and validate the top tag supplied in A. X/Y=pointer on success.
_peek_tag:
    sta zp_tmp1
    ldx ctrl_sp
    cpx #CTRL_FRAME_BYTES
    bcc @bad
    dex
    lda ctrl_stack, x
    tay
    dex
    lda ctrl_stack, x
    sta zp_tmp2
    dex
    lda ctrl_stack, x
    cmp zp_tmp1
    bne @bad
    ldx zp_tmp2
    clc
    rts
@bad:
    sec
    rts

; ctrl_for_init - Validate a signed-integer FOR descriptor, initialize its
; variable from start, and push the typed frame.
.export ctrl_for_init
ctrl_for_init:
    stx zp_dst
    sty zp_dst+1
    stx ctrl_descriptor
    sty ctrl_descriptor+1
    ldy #0
    lda (zp_dst), y
    cmp #CTRL_TAG_FOR
    bne @bad
    iny
    lda (zp_dst), y
    cmp #(TYPE_INT3+1)
    bcs @bad
    sta ctrl_last_target
    iny
    lda (zp_dst), y
    sta zp_src
    iny
    lda (zp_dst), y
    sta zp_src+1
    iny
    lda (zp_dst), y
    pha
    lda ctrl_last_target
    beq @init_float
    pla
    ldy #0
    sta (zp_src), y
    ; INT1 owns one byte; wider integer cells own the high byte too.
    ldy #1
    lda (zp_dst), y
    cmp #TYPE_INT1
    beq @push
    ldy #5
    lda (zp_dst), y
    ldy #1
    sta (zp_src), y
@push:
    ldx zp_dst
    ldy zp_dst+1
    lda #CTRL_TAG_FOR
    jmp _push_frame
@init_float:
    pla
    tax
    ldy #5
    lda (zp_dst), y
    tay
    jsr math_int_to_float
    lda ctrl_descriptor
    sta zp_dst
    lda ctrl_descriptor+1
    sta zp_dst+1
    ldy #2
    lda (zp_dst), y
    sta zp_src
    iny
    lda (zp_dst), y
    sta zp_src+1
    ldy #0
@copy_float_start:
    lda zp_fac1, y
    sta (zp_src), y
    iny
    cpy #5
    bne @copy_float_start
    ldx zp_dst
    ldy zp_dst+1
    lda #CTRL_TAG_FOR
    jmp _push_frame
@bad:
    sec
    rts

; ctrl_for_next - Add signed step and compare inclusively with signed limit.
.export ctrl_for_next
ctrl_for_next:
    lda #CTRL_TAG_FOR
    jsr _peek_tag
    bcc @frame_ok
    jmp @error
@frame_ok:
    stx zp_src
    sty zp_src+1
    lda zp_src
    sta zp_dst
    lda zp_src+1
    sta zp_dst+1
    ldy #1
    lda (zp_dst), y
    bne @integer_next
    jmp @float_next
@integer_next:
    ldy #2
    lda (zp_src), y
    sta zp_tmp1
    iny
    lda (zp_src), y
    sta zp_tmp2
    ; Save descriptor address while zp_src is used for the variable.
    lda zp_src
    sta zp_dst
    lda zp_src+1
    sta zp_dst+1
    lda zp_tmp1
    sta zp_src
    lda zp_tmp2
    sta zp_src+1
    ldy #0
    lda (zp_src), y
    sta zp_tmp1
    ldy #1
    lda (zp_dst), y
    cmp #TYPE_INT1
    bne @wide_current
    lda zp_tmp1
    bpl @positive_int1
    lda #$ff
    bne @current_high
@positive_int1:
    lda #0
    beq @current_high
@wide_current:
    ldy #1
    lda (zp_src), y
@current_high:
    sta zp_tmp2
    ldy #8
    lda (zp_dst), y
    clc
    adc zp_tmp1
    sta zp_tmp1
    iny
    lda (zp_dst), y
    adc zp_tmp2
    sta zp_tmp2
    ; Publish the incremented variable.
    ldy #0
    lda zp_tmp1
    sta (zp_src), y
    ldy #1
    lda (zp_dst), y
    cmp #TYPE_INT1
    beq @check_int1_range
    ldy #1
    lda zp_tmp2
    sta (zp_src), y
    jmp @compare
@check_int1_range:
    lda zp_tmp1
    bpl @int1_positive
    lda zp_tmp2
    cmp #$ff
    bne @promote_int2
    lda zp_tmp1
    cmp #$80
    bcc @promote_int2
    bcs @compare
@int1_positive:
    lda zp_tmp2
    bne @promote_int2
    lda zp_tmp1
    bmi @promote_int2
    bpl @compare
@promote_int2:
    ; Generic frames may start compact and widen when static range proof was
    ; unavailable. The cell reserves the full numeric payload.
    ldy #1
    lda #TYPE_INT2
    sta (zp_dst), y
    lda zp_tmp2
    sta (zp_src), y
@compare:
    ldy #1
    lda (zp_dst), y
    cmp #TYPE_INT3
    beq @compare_unsigned
    ; Signed compare uses sign-bit bias. Negative step exits below limit;
    ; non-negative step exits above limit.
    ldy #9
    lda (zp_dst), y
    bmi @negative
    ldy #7
    lda zp_tmp2
    eor #$80
    sta zp_tmp2
    lda (zp_dst), y
    eor #$80
    cmp zp_tmp2
    bcc @done
    bne @continue
    dey
    lda (zp_dst), y
    cmp zp_tmp1
    bcc @done
    bcs @continue
@negative:
    ldy #7
    lda zp_tmp2
    eor #$80
    sta zp_tmp2
    lda (zp_dst), y
    eor #$80
    cmp zp_tmp2
    bcc @continue
    bne @done
    dey
    lda zp_tmp1
    cmp (zp_dst), y
    bcc @done
    bcs @continue
@compare_unsigned:
    ldy #9
    lda (zp_dst), y
    bmi @unsigned_negative
    ldy #7
    lda zp_tmp2
    cmp (zp_dst), y
    bcc @continue
    bne @done
    dey
    lda zp_tmp1
    cmp (zp_dst), y
    bcc @continue
    beq @continue
    bne @done
@unsigned_negative:
    ldy #7
    lda zp_tmp2
    cmp (zp_dst), y
    bcc @done
    bne @continue
    dey
    lda zp_tmp1
    cmp (zp_dst), y
    bcc @done
@continue:
    clc
    rts
@done:
    jsr _pop_frame
@error:
    sec
    rts

@float_next:
    lda zp_dst
    sta ctrl_descriptor
    lda zp_dst+1
    sta ctrl_descriptor+1
    ; Convert the signed step to packed float in ARG.
    ldy #8
    lda (zp_dst), y
    tax
    iny
    lda (zp_dst), y
    tay
    jsr math_int_to_float
    lda ctrl_descriptor
    sta zp_dst
    lda ctrl_descriptor+1
    sta zp_dst+1
    ldy #0
@step_to_arg:
    lda zp_fac1, y
    sta zp_arg, y
    iny
    cpy #5
    bne @step_to_arg
    lda ctrl_descriptor
    sta zp_src
    lda ctrl_descriptor+1
    sta zp_src+1
    ; Resolve the variable cell and add ARG to its current packed value.
    ldy #2
    lda (zp_src), y
    sta ctrl_last_target
    iny
    lda (zp_src), y
    sta ctrl_last_target+1
    lda ctrl_last_target
    sta zp_src
    lda ctrl_last_target+1
    sta zp_src+1
    ldy #0
@cell_to_fac:
    lda (zp_src), y
    sta zp_fac1, y
    iny
    cpy #5
    bne @cell_to_fac
    jsr math_add
    bcs @error
    lda ctrl_descriptor
    sta zp_dst
    lda ctrl_descriptor+1
    sta zp_dst+1
    ldy #2
    lda (zp_dst), y
    sta zp_src
    iny
    lda (zp_dst), y
    sta zp_src+1
    ldy #0
@fac_to_cell:
    lda zp_fac1, y
    sta (zp_src), y
    iny
    cpy #5
    bne @fac_to_cell
    ; Compare current FAC with the signed limit converted into ARG.
    ldy #6
    lda (zp_dst), y
    tax
    iny
    lda (zp_dst), y
    tay
    jsr math_int_to_float
    lda ctrl_descriptor
    sta zp_dst
    lda ctrl_descriptor+1
    sta zp_dst+1
    ldy #2
    lda (zp_dst), y
    sta zp_src
    iny
    lda (zp_dst), y
    sta zp_src+1
    ldy #0
@limit_to_arg:
    lda zp_fac1, y
    sta zp_arg, y
    iny
    cpy #5
    bne @limit_to_arg
    ldy #0
@reload_fac:
    lda (zp_src), y
    sta zp_fac1, y
    iny
    cpy #5
    bne @reload_fac
    jsr math_cmp
    sta zp_tmp1
    lda ctrl_descriptor
    sta zp_dst
    lda ctrl_descriptor+1
    sta zp_dst+1
    ldy #9
    lda (zp_dst), y
    bmi @float_negative
    lda zp_tmp1
    bmi @float_continue
    beq @float_continue
    bne @float_done
@float_negative:
    lda zp_tmp1
    bpl @float_continue
@float_done:
    jsr _pop_frame
    sec
    rts
@float_continue:
    clc
    rts

; ctrl_do_init - Validate and push a DO descriptor.
.export ctrl_do_init
ctrl_do_init:
    stx zp_dst
    sty zp_dst+1
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #CTRL_TAG_DO
    bne @bad
    ldx zp_dst
    ldy zp_dst+1
    lda #CTRL_TAG_DO
    jmp _push_frame
@bad:
    sec
    rts

; ctrl_loop_test - A is the evaluated Boolean. Bare loops continue;
; WHILE exits on false; UNTIL exits on true.
.export ctrl_loop_test
ctrl_loop_test:
    sta ctrl_last_target
    lda #CTRL_TAG_DO
    jsr _peek_tag
    bcs @exit
    stx zp_src
    sty zp_src+1
    ldy #1
    lda (zp_src), y
    and #1
    beq @continue
    lda (zp_src), y
    and #2
    bne @until
    lda ctrl_last_target
    beq @exit_pop
@continue:
    clc
    rts
@until:
    lda ctrl_last_target
    beq @continue
@exit_pop:
    jsr _pop_frame
@exit:
    sec
    rts

; ctrl_exit_loop - Pop the top FOR or DO frame.
.export ctrl_exit_loop
ctrl_exit_loop:
    ldx ctrl_sp
    cpx #CTRL_FRAME_BYTES
    bcc @bad
    txa
    sec
    sbc #CTRL_FRAME_BYTES
    tax
    lda ctrl_stack, x
    cmp #CTRL_TAG_FOR
    beq @pop
    cmp #CTRL_TAG_DO
    bne @bad
@pop:
    jmp _pop_frame
@bad:
    sec
    rts

; ctrl_gosub - Push a compiled return address.
.export ctrl_gosub
ctrl_gosub:
    lda #CTRL_TAG_GOSUB
    jsr _push_frame
    bcs @done
    inc zp_sublev
@done:
    rts

; ctrl_return - Pop and validate one GOSUB return address.
.export ctrl_return
ctrl_return:
    lda #CTRL_TAG_GOSUB
    jsr _peek_tag
    bcs @done
    jsr _pop_frame
    dec zp_sublev
@done:
    rts

; ctrl_on_goto - Select a one-based entry from a zero-terminated u16 table.
.export ctrl_on_goto
ctrl_on_goto:
    cmp #0
    beq @error
    sta zp_tmp1
    stx zp_src
    sty zp_src+1
    lda zp_tmp1
    sec
    sbc #1
    asl a
    bcs @error
    tay
    lda (zp_src), y
    tax
    iny
    lda (zp_src), y
    tay
    cpx #0
    bne @ok
    cpy #0
    beq @error
@ok:
    stx ctrl_last_target
    sty ctrl_last_target+1
    clc
    rts
@error:
    sec
    rts

.export ctrl_on_gosub
ctrl_on_gosub:
    jsr ctrl_on_goto
    bcs @done
    jsr ctrl_gosub
@done:
    rts

; ctrl_stop - Validate and publish a continuation, snapshotting all frames.
.export ctrl_stop
ctrl_stop:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #$43
    bne @bad
    iny
    lda (zp_src), y
    sta zp_cont_generation
    iny
    iny
    iny
    lda ctrl_sp
    sta (zp_src), y
    tax
    beq @saved
@copy:
    dex
    lda ctrl_stack, x
    iny
    sta (zp_src), y
    cpx #0
    bne @copy
@saved:
    lda zp_src
    sta zp_cont_handle
    lda zp_src+1
    sta zp_cont_handle+1
    lda #1
    sta zp_stop_flag
    clc
    rts
@bad:
    sec
    rts

; ctrl_end - Terminate compiled execution through the active READY environment.
; Input:  A=0 development editor, A<>0 standalone inspection shell
; Output: does not return for standalone; development returns only when its
;         editor transition returns to the host dispatcher
; Side:   invalidates continuation/frames and restores text graphics state
; Clobbers: A, X, Y and flags
.export ctrl_end
ctrl_end:
    pha
    jsr ctrl_reset
    jsr graphics_exit
    jsr hibasic_graphics_restore
    pla
    bne @standalone
    jmp editor_ready_transition
@standalone:
    jmp inspect_shell

; ctrl_reset - Clear control and continuation state without a shell transition.
; Input: none. Output: C=0. Clobbers: A and flags.
; Side: invalidates the published continuation and all tagged frames.
.export ctrl_reset
ctrl_reset:
    lda #0
    sta zp_stop_flag
    sta zp_cont_handle
    sta zp_cont_handle+1
    sta ctrl_sp
    clc
    rts

; ctrl_cont - Validate the published descriptor and restore all frames.
.export ctrl_cont
ctrl_cont:
    cpx zp_cont_handle
    bne @bad
    cpy zp_cont_handle+1
    bne @bad
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #$43
    bne @bad
    iny
    lda (zp_src), y
    cmp zp_cont_generation
    bne @bad
    ldy #4
    lda (zp_src), y
    cmp #(CTRL_STACK_BYTES+1)
    bcs @bad
    sta ctrl_sp
    tax
    beq @restored
@copy:
    dex
    iny
    lda (zp_src), y
    sta ctrl_stack, x
    cpx #0
    bne @copy
@restored:
    lda #0
    sta zp_stop_flag
    ldy #2
    lda (zp_src), y
    tax
    iny
    lda (zp_src), y
    tay
    clc
    rts
@bad:
    sec
    rts

.export ctrl_check_stop
ctrl_check_stop:
    lda zp_stop_flag
    and #1
    rts

; Test-only generic frame helpers retain the pointer API but use a DO tag.
.export ctrl_push_loop_frame
ctrl_push_loop_frame:
    lda #CTRL_TAG_DO
    jmp _push_frame

.export ctrl_pop_loop_frame
ctrl_pop_loop_frame:
    jmp _pop_frame
