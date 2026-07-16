; src/geoasm/editor_svc.asm
; Editor service routines for line entry, deletion, LIST, and state management.
;
; Ported from legacy editor_screen.s with Compiler 2 ABI conventions.
; All routines use X/Y handles for data transfer, C flag for errors.

.include "common/zp.inc"
.include "common/constants.asm"

.import ctrl_reset, kernal_chrout, kernal_print_packed, pipeline_compile_line
.import keyword_name_lo, keyword_name_hi, keyword_length, keyword_token
.import keyword_count_value

; KERNAL routines
CHROUT      = $FFD2
GETIN       = $FFE4
CLRCHN      = $FFCC
SCNKEY      = $FF9F

; Screen constants
SCREEN_COLS = 40
SCREEN_ROWS = 25
SCREEN_BASE = $0400
COLOR_BASE  = $D800

; LIST text buffer capacity (line number + space + body + NUL).
EDITOR_LIST_MAX = 80

; =============================================================================
; Zero Page Scratch (from zp_symbols.inc via zp.inc)
; =============================================================================

; Working pointers (allocated by ZP graph-colorer)
zp_ptr1         = zp_src
zp_ptr2         = zp_expr_ptr2

.segment "BSS"
.export editor_mailbox_buffer
editor_mailbox_buffer:
    .res 81
.export editor_mailbox_length
editor_mailbox_length:
    .res 1
.export editor_mailbox_pending
editor_mailbox_pending:
    .res 1
.export editor_mailbox_submit_count
editor_mailbox_submit_count:
    .res 1
.export editor_mailbox_error
editor_mailbox_error:
    .res 1

.segment "EDITOR_PINNED"

; Editor state
editor_cursor_row:      .byte 0
editor_cursor_col:      .byte 0
editor_quote_mode:      .byte 0
editor_reverse_mode:    .byte 0
editor_insert_count:    .byte 0
editor_accepted_length: .byte 0

; Logical line links (mirrors ROM LDTB1)
editor_line_links:      .res 25, 0

; Accepted line buffer
editor_accepted_line:   .res 81, 0

; Result buffer for output (detokenized LIST text handle target)
.export editor_result_buffer
editor_result_buffer:   .res 81, 0

; Row address lookup table (25 entries)
editor_row_lo:
    .byte <(SCREEN_BASE + 40 * 0)
    .byte <(SCREEN_BASE + 40 * 1)
    .byte <(SCREEN_BASE + 40 * 2)
    .byte <(SCREEN_BASE + 40 * 3)
    .byte <(SCREEN_BASE + 40 * 4)
    .byte <(SCREEN_BASE + 40 * 5)
    .byte <(SCREEN_BASE + 40 * 6)
    .byte <(SCREEN_BASE + 40 * 7)
    .byte <(SCREEN_BASE + 40 * 8)
    .byte <(SCREEN_BASE + 40 * 9)
    .byte <(SCREEN_BASE + 40 * 10)
    .byte <(SCREEN_BASE + 40 * 11)
    .byte <(SCREEN_BASE + 40 * 12)
    .byte <(SCREEN_BASE + 40 * 13)
    .byte <(SCREEN_BASE + 40 * 14)
    .byte <(SCREEN_BASE + 40 * 15)
    .byte <(SCREEN_BASE + 40 * 16)
    .byte <(SCREEN_BASE + 40 * 17)
    .byte <(SCREEN_BASE + 40 * 18)
    .byte <(SCREEN_BASE + 40 * 19)
    .byte <(SCREEN_BASE + 40 * 20)
    .byte <(SCREEN_BASE + 40 * 21)
    .byte <(SCREEN_BASE + 40 * 22)
    .byte <(SCREEN_BASE + 40 * 23)
    .byte <(SCREEN_BASE + 40 * 24)

editor_row_hi:
    .byte >(SCREEN_BASE + 40 * 0)
    .byte >(SCREEN_BASE + 40 * 1)
    .byte >(SCREEN_BASE + 40 * 2)
    .byte >(SCREEN_BASE + 40 * 3)
    .byte >(SCREEN_BASE + 40 * 4)
    .byte >(SCREEN_BASE + 40 * 5)
    .byte >(SCREEN_BASE + 40 * 6)
    .byte >(SCREEN_BASE + 40 * 7)
    .byte >(SCREEN_BASE + 40 * 8)
    .byte >(SCREEN_BASE + 40 * 9)
    .byte >(SCREEN_BASE + 40 * 10)
    .byte >(SCREEN_BASE + 40 * 11)
    .byte >(SCREEN_BASE + 40 * 12)
    .byte >(SCREEN_BASE + 40 * 13)
    .byte >(SCREEN_BASE + 40 * 14)
    .byte >(SCREEN_BASE + 40 * 15)
    .byte >(SCREEN_BASE + 40 * 16)
    .byte >(SCREEN_BASE + 40 * 17)
    .byte >(SCREEN_BASE + 40 * 18)
    .byte >(SCREEN_BASE + 40 * 19)
    .byte >(SCREEN_BASE + 40 * 20)
    .byte >(SCREEN_BASE + 40 * 21)
    .byte >(SCREEN_BASE + 40 * 22)
    .byte >(SCREEN_BASE + 40 * 23)
    .byte >(SCREEN_BASE + 40 * 24)

; Screen-to-PETSCII conversion state
editor_conversion_quote:  .byte 0
editor_conversion_data:   .byte 0
editor_cell_index:        .byte 0

; LIST / detokenize workspace
editor_list_out:          .res 1
editor_list_line:         .res 2
editor_list_start:        .res 2
editor_list_end:          .res 2
editor_list_src:          .res 2
editor_list_quote:        .res 1
editor_list_div:          .res 2
editor_list_digit:        .res 1

.segment "EDITOR"

; =============================================================================
; Screen Address Calculation
; =============================================================================

; Calculate screen pointer from row/col
; Input:  A = row, X = col
; Output: zp_ptr1 = screen address, Y = column offset
.export editor_point_to_index
editor_point_to_index:
    tay
    lda editor_row_lo,y
    sta zp_ptr1
    lda editor_row_hi,y
    sta zp_ptr1+1
    ldy #$00
    rts

; =============================================================================
; Screen-to-PETSCII Conversion
; =============================================================================

; Convert screen code to PETSCII (ROM-semantic)
; Input:  A = screen code
; Output: A = PETSCII character
.export editor_screen_to_petscii
editor_screen_to_petscii:
    sta editor_conversion_data
    and #$3f
    asl editor_conversion_data
    bit editor_conversion_data
    bpl :+
    ora #$80
:
    bcc @check_v
    ldx editor_conversion_quote
    bne @converted
@check_v:
    bvs @converted
    ora #$40
@converted:
    rts

; =============================================================================
; Measure Logical Line
; =============================================================================

; Find the length of the current logical line
; Input:  editor_cursor_row = current row
; Output: A = trimmed length (0..80)
.export editor_measure_logical_line
editor_measure_logical_line:
    ldx editor_cursor_row
    lda editor_line_links,x
    and #$7f
    sta editor_cell_index
    ldy #0
    ldx editor_cell_index
    cpx #SCREEN_COLS
    bcc @ok
    ldx #SCREEN_COLS-1
@ok:
    stx zp_tmp1
    ldx editor_cursor_row
    lda editor_row_lo,x
    sta zp_ptr1
    lda editor_row_hi,x
    sta zp_ptr1+1
    ldy zp_tmp1
    dey
@scan:
    cpy #$ff
    beq @empty
    lda (zp_ptr1),y
    cmp #$20
    bne @found
    dey
    jmp @scan
@found:
    iny
    tya
    rts
@empty:
    lda #0
    rts

; =============================================================================
; Extract Line to Buffer
; =============================================================================

; Extract current logical line from screen to editor_accepted_line
; Input:  editor_cursor_row = current row
; Output: editor_accepted_length = length, buffer filled
.export editor_extract_line
editor_extract_line:
    jsr editor_measure_logical_line
    sta editor_accepted_length
    lda #0
    sta editor_conversion_quote
    sta editor_cell_index
@copy:
    lda editor_cell_index
    cmp editor_accepted_length
    bcs @terminate
    ldx editor_cursor_row
    lda editor_row_lo,x
    sta zp_ptr1
    lda editor_row_hi,x
    sta zp_ptr1+1
    ldy editor_cell_index
    lda (zp_ptr1),y
    jsr editor_screen_to_petscii
    cmp #$a0
    bne :+
    lda #' '
:
    ldx editor_cell_index
    sta editor_accepted_line,x
    inc editor_cell_index
    jmp @copy
@terminate:
    ldx editor_accepted_length
    lda #0
    sta editor_accepted_line,x
    rts

; =============================================================================
; Line Entry
; =============================================================================

; editor_submit_line - Transactional line submission
; Input:  X/Y = captured-line handle (unused, reads from screen)
; Output: C = error, A = error code
; Clobbers: A, X, Y
.export editor_submit_line
editor_submit_line:
    jsr ctrl_reset
    jsr editor_extract_line
    lda editor_accepted_length
    beq @ready
    ldx #<editor_accepted_line
    ldy #>editor_accepted_line
    jsr pipeline_compile_line
    bcs @error
@ready:
    clc
    lda #ERR_OK
    rts
@error:
    rts

; =============================================================================
; Line Deletion
; =============================================================================

; editor_delete_line - Deletion with repair
; Input:  X/Y = line number record
; Output: C = error
; Clobbers: A, X, Y
.export editor_delete_line
editor_delete_line:
    ; Shift lines down and clear bottom
    stx zp_ptr1
    sty zp_ptr1+1
    ldy #0
    lda (zp_ptr1),y
    sta zp_tmp1
    iny
    lda (zp_ptr1),y
    sta zp_tmp1+1
    ; Clear the line in screen memory
    ldy editor_cursor_row
    lda editor_row_lo,y
    sta zp_ptr2
    lda editor_row_hi,y
    sta zp_ptr2+1
    ldy #SCREEN_COLS-1
    lda #' '
@clear:
    sta (zp_ptr2),y
    dey
    bpl @clear
    ; Fix line links
    ldx editor_cursor_row
    lda #$80
    sta editor_line_links,x
    clc
    rts

; =============================================================================
; LIST Conversion
; =============================================================================
;
; Canonical line handle (X/Y) points at a normal-RAM tokenized line:
;   line_number:u16, token_body..., $00
; Detokenized PETSCII text is written to editor_result_buffer (NUL-terminated)
; and returned as X/Y = text handle.
;
; Range record (X/Y) for editor_list_range:
;   start:u16, end:u16, source:u16
; source points at a stock-linked program image (next:u16, line:u16, body, 0)
; or is $0000 to list a single line previously staged at editor_list_src via
; the line handle itself (source may also point at one tokenized line when
; next-link is zero after the body terminator is treated as end-of-program).

; editor_detokenize_line - LIST conversion
; Input:  X/Y = canonical line handle (line:u16 + tokens + 0)
; Output: X/Y = text handle (editor_result_buffer), C = error
; Clobbers: A, X, Y
.export editor_detokenize_line
editor_detokenize_line:
    stx zp_ptr1
    sty zp_ptr1+1
    ldy #0
    lda (zp_ptr1),y
    sta editor_list_line
    iny
    lda (zp_ptr1),y
    sta editor_list_line+1
    ; Body starts at offset 2.
    clc
    lda zp_ptr1
    adc #2
    sta zp_ptr2
    lda zp_ptr1+1
    adc #0
    sta zp_ptr2+1
    jsr editor_format_line_number
    ; Space after line number when body is nonempty or always stock-style space.
    lda #' '
    jsr editor_list_emit
    bcs @error
    lda #0
    sta editor_list_quote
    ldy #0
@body:
    lda (zp_ptr2),y
    beq @done
    sty editor_cell_index
    cmp #$22
    bne @not_quote
    lda editor_list_quote
    eor #1
    sta editor_list_quote
    lda #$22
    jsr editor_list_emit
    bcs @error
    jmp @next
@not_quote:
    ldx editor_list_quote
    bne @literal
    cmp #$80
    bcc @literal
    jsr editor_emit_keyword
    bcs @error
    jmp @next
@literal:
    jsr editor_list_emit
    bcs @error
@next:
    ldy editor_cell_index
    iny
    bne @body
@done:
    ldx editor_list_out
    lda #0
    sta editor_result_buffer,x
    ldx #<editor_result_buffer
    ldy #>editor_result_buffer
    clc
    rts
@error:
    lda #ERR_STRING_TOO_LONG
    sec
    rts

; editor_list_range - Stream detokenized lines in [start, end] through CHROUT.
; Input:  X/Y = range record start:u16, end:u16, source:u16
; Output: C = error
; Clobbers: A, X, Y
.export editor_list_range
editor_list_range:
    stx zp_ptr1
    sty zp_ptr1+1
    ldy #0
    lda (zp_ptr1),y
    sta editor_list_start
    iny
    lda (zp_ptr1),y
    sta editor_list_start+1
    iny
    lda (zp_ptr1),y
    sta editor_list_end
    iny
    lda (zp_ptr1),y
    sta editor_list_end+1
    iny
    lda (zp_ptr1),y
    sta editor_list_src
    iny
    lda (zp_ptr1),y
    sta editor_list_src+1

    lda editor_list_src
    ora editor_list_src+1
    beq @empty_ok

    lda editor_list_src
    sta zp_ptr1
    lda editor_list_src+1
    sta zp_ptr1+1
@line_loop:
    ; Stock linked: next:u16 at zp_ptr1. Zero next ends the program.
    ldy #0
    lda (zp_ptr1),y
    sta zp_tmp1
    iny
    lda (zp_ptr1),y
    sta zp_tmp1+1
    ora zp_tmp1
    beq @empty_ok

    ; Line number at +2.
    iny
    lda (zp_ptr1),y
    sta editor_list_line
    iny
    lda (zp_ptr1),y
    sta editor_list_line+1

    ; Range filter: line < start → skip; line > end → done.
    lda editor_list_line+1
    cmp editor_list_start+1
    bcc @skip
    bne @ge_start
    lda editor_list_line
    cmp editor_list_start
    bcc @skip
@ge_start:
    lda editor_list_end+1
    cmp editor_list_line+1
    bcc @empty_ok
    bne @in_range
    lda editor_list_end
    cmp editor_list_line
    bcc @empty_ok
@in_range:
    ; Detokenize from line_number field (offset +2 of linked record).
    clc
    lda zp_ptr1
    adc #2
    tax
    lda zp_ptr1+1
    adc #0
    tay
    jsr editor_detokenize_line
    bcs @error
    jsr editor_list_print_result
    bcs @error
@skip:
    ; Advance to next linked line (absolute next pointer).
    lda zp_tmp1
    sta zp_ptr1
    lda zp_tmp1+1
    sta zp_ptr1+1
    jmp @line_loop
@empty_ok:
    clc
    rts
@error:
    rts

; =============================================================================
; READY State Transition
; =============================================================================

; editor_ready_transition - READY state
; Input:  X/Y = publication result handle
; Output: none
; Clobbers: A, X, Y
.export editor_ready_transition
editor_ready_transition:
    lda #<ready_msg
    ldx #>ready_msg
    jsr editor_print_string_ax
    lda #'R'
    rts

; Print null-terminated string at A/X
.export editor_print_string_ax
editor_print_string_ax:
    pha
    txa
    tay
    pla
    tax
    jmp kernal_print_packed

ready_msg:
    .byte "READY.", $8D

; =============================================================================
; LIST helpers (after public exports so size ceilings stay page-local)
; =============================================================================

; Format editor_list_line as decimal into editor_result_buffer.
editor_format_line_number:
    lda #0
    sta editor_list_out
    lda editor_list_line
    sta editor_list_div
    lda editor_list_line+1
    sta editor_list_div+1
    ; Emit up to 5 digits, suppressing leading zeros.
    lda #0
    sta editor_list_digit
    lda #<10000
    ldx #>10000
    jsr editor_list_div_digit
    lda #<1000
    ldx #>1000
    jsr editor_list_div_digit
    lda #<100
    ldx #>100
    jsr editor_list_div_digit
    lda #<10
    ldx #>10
    jsr editor_list_div_digit
    lda editor_list_div
    ora #'0'
    jmp editor_list_emit

; Divide editor_list_div by AX (16-bit), emit one digit if nonzero seen.
editor_list_div_digit:
    sta zp_tmp2
    stx zp_tmp2+1
    lda #0
    sta editor_conversion_data
@sub:
    lda editor_list_div
    cmp zp_tmp2
    lda editor_list_div+1
    sbc zp_tmp2+1
    bcc @emit
    lda editor_list_div
    sec
    sbc zp_tmp2
    sta editor_list_div
    lda editor_list_div+1
    sbc zp_tmp2+1
    sta editor_list_div+1
    inc editor_conversion_data
    jmp @sub
@emit:
    lda editor_conversion_data
    bne @force
    lda editor_list_digit
    beq @skip
@force:
    lda #1
    sta editor_list_digit
    lda editor_conversion_data
    ora #'0'
    jmp editor_list_emit
@skip:
    clc
    rts

; Emit A into editor_result_buffer. C set if buffer full.
editor_list_emit:
    ldx editor_list_out
    cpx #EDITOR_LIST_MAX
    bcs @full
    sta editor_result_buffer,x
    inx
    stx editor_list_out
    clc
    rts
@full:
    sec
    rts

; Look up token A ($80+) in keyword_token and emit its name.
; Preserves editor_cell_index (body scan offset in detokenize).
editor_emit_keyword:
    sta editor_conversion_data
    ldx #0
@find:
    cpx keyword_count_value
    beq @raw
    lda keyword_token,x
    cmp editor_conversion_data
    beq @found
    inx
    bne @find
@raw:
    ; Unknown token: emit the raw token byte.
    lda editor_conversion_data
    jmp editor_list_emit
@found:
    lda keyword_name_lo,x
    sta zp_tmptr
    lda keyword_name_hi,x
    sta zp_tmptr+1
    lda keyword_length,x
    sta editor_list_digit
    ldy #0
@copy:
    cpy editor_list_digit
    beq @done
    lda (zp_tmptr),y
    sty editor_conversion_quote
    jsr editor_list_emit
    bcs @err
    ldy editor_conversion_quote
    iny
    bne @copy
@done:
    clc
    rts
@err:
    sec
    rts

; Print editor_result_buffer via kernal_chrout and a CR.
editor_list_print_result:
    ldx #0
@loop:
    lda editor_result_buffer,x
    beq @cr
    stx editor_cell_index
    jsr kernal_chrout
    ldx editor_cell_index
    inx
    bne @loop
@cr:
    lda #$0D
    jsr kernal_chrout
    clc
    rts
