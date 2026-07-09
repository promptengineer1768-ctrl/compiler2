; src/arena/context_stack.asm
; Fixed-depth geoRAM context stack helpers.

.include "common/zp.inc"

.segment "RESIDENT"

CTX_MAX_DEPTH = 8

.segment "BSS"
ctx_stack_block: .res CTX_MAX_DEPTH
ctx_stack_page:  .res CTX_MAX_DEPTH

.segment "RESIDENT"

.export ctx_init
.export ctx_push
.export ctx_pop
.export ctx_depth
.export ctx_check_overflow

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
