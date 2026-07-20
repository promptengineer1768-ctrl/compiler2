; src/arena/context_stack.asm
; Fixed-depth geoRAM context stack helpers.

.include "common/zp.inc"

.segment "RESIDENT"

CTX_MAX_DEPTH = 8

.segment "BSS"
ctx_stack_block: .res CTX_MAX_DEPTH
ctx_stack_page:  .res CTX_MAX_DEPTH
; The XIP code page selected by the gate for each active context.  Data
; helpers use this to restore the instruction mapping before returning to a
; caller that is executing at $DE00.
ctx_code_block:  .res CTX_MAX_DEPTH
ctx_code_page:   .res CTX_MAX_DEPTH

.segment "RESIDENT"

.export ctx_init
.export ctx_push
.export ctx_pop
.export ctx_depth
.export ctx_check_overflow
.export ctx_set_code_mapping
.export ctx_get_code_mapping

ctx_init:
    lda #$00
    sta zp_gr_ctx_sp
    rts

ctx_check_overflow:
    lda zp_gr_ctx_sp
    cmp #CTX_MAX_DEPTH
    bcc @ok
    sec
    rts
@ok:
    clc
    rts

ctx_push:
    jsr ctx_check_overflow
    bcs @fail
    ldx zp_gr_ctx_sp
    lda zp_gr_block
    sta ctx_stack_block,x
    lda zp_gr_page
    sta ctx_stack_page,x
    inx
    stx zp_gr_ctx_sp
    clc
    rts
@fail:
    sec
    rts

ctx_pop:
    lda zp_gr_ctx_sp
    beq @fail
    tax
    dex
    stx zp_gr_ctx_sp
    lda ctx_stack_block,x
    sta zp_gr_block
    lda ctx_stack_page,x
    sta zp_gr_page
    clc
    rts
@fail:
    sec
    rts

ctx_depth:
    lda zp_gr_ctx_sp
    rts

; ctx_set_code_mapping - Record the current XIP page for the active context.
; Inputs: X=block, A=page. Outputs: C=0, or C=1 when no context is active.
; Clobbers: A, X, flags. Side effects: updates only context metadata.
ctx_set_code_mapping:
    ldy zp_gr_ctx_sp
    beq @fail
    dey
    sta ctx_code_page,y
    txa
    sta ctx_code_block,y
    clc
    rts
@fail:
    sec
    rts

; ctx_get_code_mapping - Return the current XIP code mapping.
; Inputs: none. Outputs: X=block, A=page, C=0; C=1 if no XIP context.
; Clobbers: A, X, Y, flags. Side effects: none.
ctx_get_code_mapping:
    ldy zp_gr_ctx_sp
    beq @fail
    dey
    lda ctx_code_page,y
    ldx ctx_code_block,y
    clc
    rts
@fail:
    sec
    rts
