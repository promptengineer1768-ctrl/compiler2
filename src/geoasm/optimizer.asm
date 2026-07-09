; src/geoasm/optimizer.asm
; Generation-cached, single-pass IR effect analysis and loop predicates.

.include "common/zp.inc"
.include "common/constants.asm"

.import ir_buffer, ir_buffer_len

IR_END  = $00
IR_LOOP = $07
IR_RECORD_SIZE = 4

FOR_REQUIRED_FLAGS = $1F
DO_SIMPLE_FLAG     = $20
DO_BARE_FLAG       = $40
KNOWN_FLAGS        = FOR_REQUIRED_FLAGS | DO_SIMPLE_FLAG | DO_BARE_FLAG

COND_WHILE = $00
COND_UNTIL = $01
OP_BNE = $D0
OP_BEQ = $F0

SUMMARY_FLAGS = 0
SUMMARY_DIRTY = 1
SUMMARY_ALIAS = 2
SUMMARY_META  = 3
SUMMARY_SIZE  = 4
SUMMARY_CAPACITY = 4
SUMMARY_VALID = $80
SUMMARY_STOP_POLL = $01
IR_LONG_LOOP_FLAG = $80

.segment "BSS"
.export opt_summary_table
opt_summary_table:
    .res SUMMARY_SIZE * SUMMARY_CAPACITY
.export opt_summary_count
opt_summary_count:
    .res 1
.export opt_summary_generation
opt_summary_generation:
    .res 2
opt_summary_valid:
    .res 1
opt_work_table:
    .res SUMMARY_SIZE * SUMMARY_CAPACITY
opt_work_count:
    .res 1
.export opt_dirty_mask
opt_dirty_mask:
    .res 1
.export opt_pass_count
opt_pass_count:
    .res 1
opt_alias_mask:
    .res 1
opt_requested_generation:
    .res 2

.segment "GEOASM"

; opt_run_passes
; Purpose: Build the cached effects for the current typed IR generation.
; Inputs: X/Y = typed IR generation.
; Outputs: X/Y = summary table, C clear; C set if summary capacity is exceeded.
; Side effects: Publishes summaries atomically and increments opt_pass_count.
; Clobbers: A, X, Y.
; Flags: C reports success.
; Zero page: none.
.export opt_run_passes
opt_run_passes:
    jsr opt_build_effect_summaries
    bcs @error
    inc opt_pass_count
@error:
    rts

; opt_build_effect_summaries
; Purpose: Scan typed IR once and cache loop effect summaries by generation.
; Inputs: X/Y = typed IR generation. IR payload bytes are facts/dirty/alias.
; Outputs: X/Y = opt_summary_table, C clear; C set on excess loop records.
; Side effects: Replaces the cache only after a complete successful scan.
; Clobbers: A, X, Y.
; Flags: C reports success.
; Zero page: none.
.export opt_build_effect_summaries
opt_build_effect_summaries:
    stx opt_requested_generation
    sty opt_requested_generation+1
    lda opt_summary_valid
    beq @rebuild
    cpx opt_summary_generation
    bne @rebuild
    cpy opt_summary_generation+1
    bne @rebuild
    jmp @return_table
@rebuild:
    lda #0
    sta opt_work_count
    sta opt_dirty_mask
    sta opt_alias_mask
    ldx #SUMMARY_SIZE * SUMMARY_CAPACITY - 1
@clear:
    sta opt_work_table, x
    dex
    bpl @clear
    ldx #0
@scan:
    cpx ir_buffer_len
    bcs @publish
    lda ir_buffer, x
    beq @publish
    cmp #IR_LOOP
    beq @loop
    lda ir_buffer+2, x
    jsr opt_propagate_dirty
    lda ir_buffer+3, x
    ora opt_alias_mask
    sta opt_alias_mask
    jmp @next
@loop:
    lda opt_work_count
    cmp #SUMMARY_CAPACITY
    bcs @overflow
    asl
    asl
    tay
    lda ir_buffer+1, x
    sta opt_work_table+SUMMARY_FLAGS, y
    lda ir_buffer+2, x
    ora opt_dirty_mask
    sta opt_work_table+SUMMARY_DIRTY, y
    lda ir_buffer+3, x
    ora opt_alias_mask
    sta opt_work_table+SUMMARY_ALIAS, y
    lda ir_buffer+1, x
    and #IR_LONG_LOOP_FLAG
    beq @not_long
    lda #SUMMARY_STOP_POLL
@not_long:
    sta opt_work_table+SUMMARY_META, y
    inc opt_work_count
@next:
    txa
    clc
    adc #IR_RECORD_SIZE
    tax
    jmp @scan
@publish:
    lda opt_work_count
    sta opt_summary_count
    ldx #SUMMARY_SIZE * SUMMARY_CAPACITY - 1
@copy:
    lda opt_work_table, x
    sta opt_summary_table, x
    dex
    bpl @copy
    lda opt_requested_generation
    sta opt_summary_generation
    lda opt_requested_generation+1
    sta opt_summary_generation+1
    lda #SUMMARY_VALID
    sta opt_summary_valid
@return_table:
    ldx #<opt_summary_table
    ldy #>opt_summary_table
    clc
    rts
@overflow:
    sec
    rts

; opt_eligible_for_for_fast
; Purpose: Decide all cached FOR/NEXT fast-path facts at one boundary.
; Inputs: X/Y = four-byte effect summary.
; Outputs: C set iff required facts are exact and no barrier/alias exists.
; Side effects: none. Clobbers: A, Y. Flags: C predicate. Zero page: zp_tmp1.
.export opt_eligible_for_for_fast
opt_eligible_for_for_fast:
    jsr _opt_set_ptr
    ldy #SUMMARY_FLAGS
    lda (zp_tmp1), y
    and #KNOWN_FLAGS
    cmp #FOR_REQUIRED_FLAGS
    bne @no
    jmp _opt_no_effect_barriers
@no:
    clc
    rts

; opt_eligible_for_do_fast
; Purpose: Decide cached bare/simple DO eligibility.
; Inputs: X/Y = summary. Outputs: C predicate. Side effects: none.
; Clobbers: A, Y. Flags: C predicate. Zero page: zp_tmp1.
.export opt_eligible_for_do_fast
opt_eligible_for_do_fast:
    jsr _opt_set_ptr
    ldy #SUMMARY_FLAGS
    lda (zp_tmp1), y
    and #DO_SIMPLE_FLAG | DO_BARE_FLAG
    beq @no
    cmp #DO_SIMPLE_FLAG | DO_BARE_FLAG
    beq @no                       ; contradictory lowering kinds
    jmp _opt_no_effect_barriers
@no:
    clc
    rts

_opt_no_effect_barriers:
    iny
    lda (zp_tmp1), y
    bne @blocked
    iny
    lda (zp_tmp1), y
    bne @blocked
    sec
    rts
@blocked:
    clc
    rts

; opt_check_invalidation
; Purpose: Return cached body invalidation bits without rescanning IR.
; Inputs: X/Y = summary. Outputs: A = mask. Side effects: none.
; Clobbers: A, Y. Flags: N/Z from mask, C clear. Zero page: zp_tmp1.
.export opt_check_invalidation
opt_check_invalidation:
    jsr _opt_set_ptr
    ldy #SUMMARY_DIRTY
    lda (zp_tmp1), y
    clc
    rts

; opt_check_aliasing
; Purpose: Test cached alias/escape/bank-change effects.
; Inputs: X/Y = summary. Outputs: C set when blocked. Side effects: none.
; Clobbers: A, Y. Flags: C predicate. Zero page: zp_tmp1.
.export opt_check_aliasing
opt_check_aliasing:
    jsr _opt_set_ptr
    ldy #SUMMARY_ALIAS
    lda (zp_tmp1), y
    beq @no
    sec
    rts
@no:
    clc
    rts

; opt_propagate_dirty
; Purpose: Union child/body dirty facts into the current parent summary.
; Inputs: A = dirty bits. Outputs: A and opt_dirty_mask = union.
; Side effects: updates analysis accumulator. Clobbers: A. Flags: C clear.
; Zero page: none.
.export opt_propagate_dirty
opt_propagate_dirty:
    ora opt_dirty_mask
    sta opt_dirty_mask
    clc
    rts

; opt_select_branch_polarity
; Purpose: Select explicit WHILE/UNTIL truth branch; reject unknown polarity.
; Inputs: A = condition kind. Outputs: A = opcode on success.
; Side effects: none. Clobbers: A. Flags: C clear valid, set invalid.
; Zero page: none.
.export opt_select_branch_polarity
opt_select_branch_polarity:
    cmp #COND_WHILE
    beq @while
    cmp #COND_UNTIL
    bne @invalid
    lda #OP_BEQ
    clc
    rts
@while:
    lda #OP_BNE
    clc
    rts
@invalid:
    sec
    rts

; opt_check_stop_poll
; Purpose: Return the descriptor's proven long-loop STOP-poll requirement.
; Inputs: X/Y = summary. Outputs: C set when bounded polling is required.
; Side effects: none. Clobbers: A, Y. Flags: C predicate. Zero page: zp_tmp1.
.export opt_check_stop_poll
opt_check_stop_poll:
    jsr _opt_set_ptr
    ldy #SUMMARY_META
    lda (zp_tmp1), y
    and #SUMMARY_STOP_POLL
    beq @no
    sec
    rts
@no:
    clc
    rts

_opt_set_ptr:
    stx zp_tmp1
    sty zp_tmp1+1
    rts
