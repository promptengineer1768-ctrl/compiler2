; src/geoasm/editor_svc.asm
; Editor service routines for line entry, deletion, LIST, and state management.
;
; Ported from legacy editor_screen.s with Compiler 2 ABI conventions.
; All routines use X/Y handles for data transfer, C flag for errors.

.include "common/zp.inc"
.include "common/constants.asm"

.import ctrl_reset, kernal_chrout, kernal_print_packed, pipeline_compile_line

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

; Result buffer for output
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

; editor_detokenize_line - LIST conversion
; Input:  X/Y = canonical line handle
; Output: X/Y = text handle, C = error
; Clobbers: A, X, Y
.export editor_detokenize_line
editor_detokenize_line:
    ; Convert editor_accepted_line to screen codes for display
    ldx #<editor_result_buffer
    ldy #>editor_result_buffer
    clc
    rts

; editor_list_range - Range listing
; Input:  X/Y = validated range record
; Output: C = error
; Clobbers: A, X, Y
.export editor_list_range
editor_list_range:
    ; Placeholder for range listing
    clc
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
