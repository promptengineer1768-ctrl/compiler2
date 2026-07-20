; Stored-program editor adapter.
; Numbered source is canonicalized into the transactional geoRAM PS store.
; EDITOR_PINNED holds only small descriptors and execution metadata, never
; program bytes.  The existing accepted editor buffer is reused for RUN/LIST.

.include "common/zp.inc"
.include "common/constants.asm"
.include "arena_layout.inc"

PL_BODY_MAX = 80

.import arena_select_page
.import program_store_line_count, program_store_copy_line_body_at
.import program_store_selected_line_number
.import codegen_buffer
.import for_continue, for_body_pc
.import kernal_chrout, screen_put_petscii
.import editor_accepted_line
.import georam_call_group_n
.import georam_call_group_n_xy
.import georam_write_byte, georam_copy_from_ram
.import GEORAM_ROUTINE_ID_PROGRAM_LINES_PRINT_SELECTED_LINE_NUMBER
.import GEORAM_ROUTINE_ID_PROGRAM_TX_BEGIN
.import GEORAM_ROUTINE_ID_PROGRAM_TX_PUT_LINE
.import GEORAM_ROUTINE_ID_PROGRAM_TX_DELETE_LINE
.import GEORAM_ROUTINE_ID_PROGRAM_TX_COMMIT
.import GEORAM_ROUTINE_ID_PROGRAM_TX_ABORT
.import GEORAM_ROUTINE_ID_PROGRAM_REPLACE_FROM_LOAD
.import GEORAM_ROUTINE_ID_PIPELINE_COMPILE_LINE

.segment "EDITOR_PINNED"

.export program_lines_count
program_lines_count: .res 1
; Compatibility statistics only.  Program bytes are in geoRAM, not here.
.export program_lines_used
program_lines_used: .res 2
; Retained export name now denotes adapter descriptor workspace, not an arena.
.export program_lines_arena
program_lines_arena: .res 48

pl_line_num: .res 2
pl_body_len: .res 1
pl_tx: .res 2
pl_index: .res 1
pl_digit_div: .res 2
pl_digit_out: .res 1
.export pl_current_index
pl_current_index: .res 1

PL_PS = program_lines_arena
PL_PP = program_lines_arena + 8
PL_PD = program_lines_arena + 16
pl_body_ptr = program_lines_arena + 24
; GD descriptor used by resident window helpers.  High-RAM editor code never
; accesses $DE00 directly: it submits each header/trailer byte or body copy
; through a helper that owns the temporary I/O banking.
PL_GD = program_lines_arena + 32

.segment "EDITOR"

; program_lines_clear - Publish an empty normalized PS stream.
.export program_lines_clear
program_lines_clear:
    jsr _pl_ensure_store
    bcs @error
    jsr _pl_make_empty_ps
    lda #<GEORAM_ROUTINE_ID_PROGRAM_REPLACE_FROM_LOAD
    jsr georam_call_group_n_xy
    bcs @error
    lda #0
    sta program_lines_count
    sta program_lines_used
    sta program_lines_used+1
    clc
    rts
@error:
    sec
    rts

.export program_lines_get_count
program_lines_get_count:
    jsr _pl_refresh_count
    bcs @error
    lda program_lines_count
    clc
    rts
@error:
    sec
    rts

; program_lines_put_linebuf - parse a numbered editor line and transactionally
; put/delete it in the canonical expansion-backed program store.
.export program_lines_put_linebuf
program_lines_put_linebuf:
    lda zp_linebuf
    sta zp_src
    lda zp_linebuf+1
    sta zp_src+1
    ldy #0
@skip_space:
    cpy zp_line_len
    bcc :+
    jmp @bad
:
    lda (zp_src),y
    cmp #' '
    bne @digit
    iny
    bne @skip_space
@digit:
    cmp #'0'
    bcs :+
    jmp @bad
:
    cmp #'9'+1
    bcc :+
    jmp @bad
:
    lda #0
    sta pl_line_num
    sta pl_line_num+1
@number:
    cpy zp_line_len
    bcs @after_number
    lda (zp_src),y
    cmp #'0'
    bcc @after_number
    cmp #'9'+1
    bcs @after_number
    jsr _pl_mul10_add
    bcc :+
    jmp @bad
:
    iny
    bne @number
@after_number:
@skip_body_space:
    cpy zp_line_len
    bcs @delete
    lda (zp_src),y
    cmp #' '
    bne @body
    iny
    bne @skip_body_space
@body:
    cmp #0
    beq @delete
    sty zp_tmp1
    lda zp_line_len
    sec
    sbc zp_tmp1
    beq @delete
    cmp #PL_BODY_MAX+1
    bcc :+
    jmp @bad
:
    sta pl_body_len
    tya
    clc
    adc zp_src
    sta pl_body_ptr
    lda zp_src+1
    adc #0
    sta pl_body_ptr+1
    jsr _pl_ensure_store
    bcs @error
    lda pl_body_ptr
    sta zp_src
    lda pl_body_ptr+1
    sta zp_src+1
    jsr _pl_make_line_ps
    bcs @error
    ldx #<GEORAM_ROUTINE_ID_PROGRAM_TX_BEGIN
    jsr georam_call_group_n
    bcs @error
    stx pl_tx
    sty pl_tx+1
    jsr _pl_make_pp
    ldx #<PL_PP
    ldy #>PL_PP
    lda #<GEORAM_ROUTINE_ID_PROGRAM_TX_PUT_LINE
    jsr georam_call_group_n_xy
    bcs @abort
    ldx pl_tx
    ldy pl_tx+1
    lda #<GEORAM_ROUTINE_ID_PROGRAM_TX_COMMIT
    jsr georam_call_group_n_xy
    bcs @error
    jmp _pl_refresh_count
@delete:
    jsr _pl_ensure_store
    bcs @error
    ldx #<GEORAM_ROUTINE_ID_PROGRAM_TX_BEGIN
    jsr georam_call_group_n
    bcs @error
    stx pl_tx
    sty pl_tx+1
    jsr _pl_make_pd
    ldx #<PL_PD
    ldy #>PL_PD
    lda #<GEORAM_ROUTINE_ID_PROGRAM_TX_DELETE_LINE
    jsr georam_call_group_n_xy
    bcs @abort
    ldx pl_tx
    ldy pl_tx+1
    lda #<GEORAM_ROUTINE_ID_PROGRAM_TX_COMMIT
    jsr georam_call_group_n_xy
    bcs @error
    jmp _pl_refresh_count
@abort:
    ; A failed put/delete leaves the active transaction invalid only after an
    ; explicit abort.  Reuse the public abort entry through a local tail.
    ldx pl_tx
    ldy pl_tx+1
    lda #<GEORAM_ROUTINE_ID_PROGRAM_TX_ABORT
    jsr georam_call_group_n_xy
@error:
    sec
    rts
@bad:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; program_lines_list - list canonical source through the one-line editor
; buffer.  The buffer is scratch, not a second program representation.
.export program_lines_list
program_lines_list:
    jsr _pl_refresh_count
    bcs @error
    lda #0
    sta pl_index
@next:
    lda pl_index
    cmp program_lines_count
    bcs @done
    ldx #<editor_accepted_line
    ldy #>editor_accepted_line
    jsr program_store_copy_line_body_at
    bcs @error
    ; Decimal formatting is a cold LIST-only operation.  Its inputs are
    ; published in program_store_selected_line_number, so the XIP entry has no
    ; register argument to marshal through the geoRAM gate.
    ldx #<GEORAM_ROUTINE_ID_PROGRAM_LINES_PRINT_SELECTED_LINE_NUMBER
    jsr georam_call_group_n
    bcs @error
    lda #' '
    jsr screen_put_petscii
    ldy #0
@body:
    lda editor_accepted_line,y
    beq @cr
    jsr screen_put_petscii
    iny
    bne @body
@cr:
    lda #$0d
    jsr kernal_chrout
    inc pl_index
    jmp @next
@done:
    clc
    rts
@error:
    sec
    rts

; program_lines_run - fetch each canonical line body into the editor scratch
; buffer, then compile and execute it in memory.  No export/PRG path is used.
.export program_lines_run
program_lines_run:
    jsr _pl_refresh_count
    bcs @fail
    lda #0
    sta pl_current_index
@loop:
    lda pl_current_index
    cmp program_lines_count
    bcs @ok
    ldx #<editor_accepted_line
    ldy #>editor_accepted_line
    jsr program_store_copy_line_body_at
    bcs @fail
    ldx #<editor_accepted_line
    ldy #>editor_accepted_line
    lda #0
    sta for_continue
    lda #<GEORAM_ROUTINE_ID_PIPELINE_COMPILE_LINE
    jsr georam_call_group_n_xy
    bcs @fail
    jsr codegen_buffer
    lda for_continue
    beq @advance
    lda for_body_pc
    sta pl_current_index
    jmp @loop
@advance:
    inc pl_current_index
    jmp @loop
@ok:
    clc
    rts
@fail:
    sec
    rts

; ---------------------------------------------------------------------------
; Canonical PS adapter helpers

_pl_ensure_store:
    jsr program_store_line_count
    bcs @error
    sta program_lines_count
    clc
    rts
@error:
    sec
    rts

_pl_refresh_count:
    jsr program_store_line_count
    bcs @error
    sta program_lines_count
    ; Statistics are deliberately not a capacity decision; retain byte count
    ; only as a compatibility diagnostic.
    lda #0
    sta program_lines_used
    sta program_lines_used+1
    clc
    rts
@error:
    sec
    rts

; Write a one-line normalized PS into scratch page zero.
_pl_make_line_ps:
    lda #'P'
    sta PL_PS
    lda #'S'
    sta PL_PS+1
    lda pl_body_len
    clc
    adc #7
    sta PL_PS+2
    lda #0
    sta PL_PS+3
    lda #ARENA_TYPE_SCRATCH
    sta PL_PS+4
    lda #1
    sta PL_PS+5
    lda #0
    sta PL_PS+6
    sta PL_PS+7
    ldx #ARENA_TYPE_SCRATCH
    ldy #1
    lda #0
    jsr arena_select_page
    bcs @error
    lda zp_gr_page
    sta PL_GD+1
    lda pl_body_len
    clc
    adc #3
    ldx #0
    jsr _pl_scratch_byte
    lda #0
    ldx #1
    jsr _pl_scratch_byte
    lda pl_line_num
    ldx #2
    jsr _pl_scratch_byte
    lda pl_line_num+1
    ldx #3
    jsr _pl_scratch_byte
    ; Copy the token body from the editor RAM buffer through the resident
    ; banked window helper into scratch offset four.
    lda #4
    sta PL_GD
    lda pl_body_len
    sta PL_GD+2
    lda zp_src
    sta PL_GD+3
    lda zp_src+1
    sta PL_GD+4
    ldx #<PL_GD
    ldy #>PL_GD
    jsr georam_copy_from_ram
    bcs @error
    ldx pl_body_len
    inx
    inx
    inx
    inx
    lda #0
    jsr _pl_scratch_byte
    inx
    lda #0
    jsr _pl_scratch_byte
    inx
    lda #0
    jsr _pl_scratch_byte
    clc
    rts
@error:
    sec
    rts

; Write A to scratch page offset X through the resident banked window.
; Preserves no registers; C reports the helper result.
_pl_scratch_byte:
    sta PL_GD+5
    stx PL_GD
    ldx #<PL_GD
    ldy #>PL_GD
    jmp georam_write_byte

_pl_make_empty_ps:
    lda #'P'
    sta PL_PS
    lda #'S'
    sta PL_PS+1
    lda #2
    sta PL_PS+2
    lda #0
    sta PL_PS+3
    lda #ARENA_TYPE_SCRATCH
    sta PL_PS+4
    lda #1
    sta PL_PS+5
    lda #0
    sta PL_PS+6
    sta PL_PS+7
    ldx #ARENA_TYPE_SCRATCH
    ldy #1
    lda #0
    jsr arena_select_page
    bcs @error
    lda zp_gr_page
    sta PL_GD+1
    ldx #0
    lda #0
    jsr _pl_scratch_byte
    bcs @error
    ldx #1
    lda #0
    jsr _pl_scratch_byte
    bcs @error
    ldx #<PL_PS
    ldy #>PL_PS
    clc
    rts
@error:
    sec
    rts

_pl_make_pp:
    lda #'P'
    sta PL_PP
    sta PL_PP+1
    lda pl_tx
    sta PL_PP+2
    lda pl_tx+1
    sta PL_PP+3
    lda #<PL_PS
    sta PL_PP+4
    lda #>PL_PS
    sta PL_PP+5
    lda #0
    sta PL_PP+6
    sta PL_PP+7
    rts

_pl_make_pd:
    lda #'P'
    sta PL_PD
    lda #'D'
    sta PL_PD+1
    lda pl_tx
    sta PL_PD+2
    lda pl_tx+1
    sta PL_PD+3
    lda pl_line_num
    sta PL_PD+4
    lda pl_line_num+1
    sta PL_PD+5
    lda #0
    sta PL_PD+6
    sta PL_PD+7
    rts

_pl_mul10_add:
    and #$0f
    sta zp_tmp2
    lda pl_line_num
    sta zp_tmp1
    lda pl_line_num+1
    sta zp_tmp1+1
    asl pl_line_num
    rol pl_line_num+1
    bcs @bad
    asl pl_line_num
    rol pl_line_num+1
    bcs @bad
    asl pl_line_num
    rol pl_line_num+1
    bcs @bad
    asl zp_tmp1
    rol zp_tmp1+1
    bcs @bad
    lda pl_line_num
    clc
    adc zp_tmp1
    sta pl_line_num
    lda pl_line_num+1
    adc zp_tmp1+1
    sta pl_line_num+1
    bcs @bad
    lda pl_line_num
    clc
    adc zp_tmp2
    sta pl_line_num
    lda pl_line_num+1
    adc #0
    sta pl_line_num+1
    bcs @bad
    clc
    rts
@bad:
    sec
    rts

.segment "GEORAM_PAGE_42"

; program_lines_print_selected_line_number - print the selected canonical
; store line number.  The selected number is published by
; program_store_copy_line_body_at; this deliberately avoids a resident mirror
; and makes the cold formatter gate-callable without an argument ABI.
; Input: program_store_selected_line_number. Output: C=0.
.export program_lines_print_selected_line_number
program_lines_print_selected_line_number:
    lda program_store_selected_line_number
    sta pl_line_num
    lda program_store_selected_line_number+1
    sta pl_line_num+1
    lda #0
    sta pl_digit_out
    lda #<10000
    sta pl_digit_div
    lda #>10000
    sta pl_digit_div+1
    jsr _pl_print_div
    lda #<1000
    sta pl_digit_div
    lda #>1000
    sta pl_digit_div+1
    jsr _pl_print_div
    lda #<100
    sta pl_digit_div
    lda #>100
    sta pl_digit_div+1
    jsr _pl_print_div
    lda #10
    sta pl_digit_div
    lda #0
    sta pl_digit_div+1
    jsr _pl_print_div
    lda pl_line_num
    ora #'0'
    jmp screen_put_petscii

_pl_print_div:
    lda #0
    sta zp_tmp1
@loop:
    lda pl_line_num
    cmp pl_digit_div
    lda pl_line_num+1
    sbc pl_digit_div+1
    bcc @done
    lda pl_line_num
    sec
    sbc pl_digit_div
    sta pl_line_num
    lda pl_line_num+1
    sbc pl_digit_div+1
    sta pl_line_num+1
    inc zp_tmp1
    bne @loop
@done:
    lda zp_tmp1
    bne @emit
    lda pl_digit_out
    beq @skip
@emit:
    lda #1
    sta pl_digit_out
    lda zp_tmp1
    ora #'0'
    jmp screen_put_petscii
@skip:
    rts

.assert * - program_lines_print_selected_line_number <= $FA, error, "program_lines_print_selected_line_number exceeds geoRAM page 42"

.segment "EDITOR"
