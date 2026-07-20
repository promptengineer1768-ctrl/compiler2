; src/resident/resident_main.asm
; Resident input loop, boundary assertions, and degraded minimal editor.
;
; Normal mode submits lines through expansion-native editor services.
; Degraded mode (store loss after NMI re-detect) shows an expansion error and
; accepts only QUIT; any other command re-shows the error (DESIGN2 §8.5).

.include "common/zp.inc"
.include "common/constants.asm"
.include "keyword_constants.inc"

.import screen_line_input
.import screen_put_petscii
.import screen_putchar
.import screen_cursor_on
.import screen_cursor_off
.import screen_cursor_left
.import screen_cursor_right
.import screen_cursor_up
.import screen_cursor_down
.import screen_cursor_hide
.import screen_sync_from_kernal
.import resident_line_capture
.import kernal_getin
.import kernal_chrout
.import georam_verify_mirror
.import vectors_prior_irq
.import vectors_prior_nmi
.import vectors_installed
.import nmi_invalidate_cont
.import codegen_buffer
.import wedge_dispatch_development
.import token_next
.import token_keyword_id
.import token_last_type
.import program_lines_put_linebuf
.import georam_call_group_n_xy
.import georam_call_group_0_xy
.import GEORAM_ROUTINE_ID_PIPELINE_COMPILE_LINE
.import GEORAM_ROUTINE_ID_DIRECT_EXECUTE_COMMAND
.importzp GEORAM_ROUTINE_ID_TOKEN_INIT

; Tokenizer type for identifiers (matches tokenizer.asm).
TOKEN_TYPE_IDENTIFIER = $01

; Stock BASIC map pointers (BASIC_ZP / c64rom declare.s).
BASIC_TEMPPT = $16
BASIC_TEMPST = $19
BASIC_TXTTAB = $2B
BASIC_VARTAB = $2D
BASIC_ARYTAB = $2F
BASIC_STREND = $31
BASIC_FRETOP = $33
BASIC_MEMSIZ = $37
; Stock warm-start READY path after explicit CLR (KERNAL/BASIC glue).
STOCK_READY  = $E386
; Canonical stock map with BASIC + KERNAL + I/O visible.
CPU_PORT_STOCK = $37
CINV  = $0314
NMINV = $0318

.segment "BSS"
resident_input_byte:      .res 1
resident_last_key:        .res 1
resident_last_submit_len: .res 1
resident_submit_count:    .res 1
resident_saved_p:         .res 1
.export resident_degraded
resident_degraded:        .res 1
.export resident_quit_done
resident_quit_done:       .res 1
; 2-byte direct-command record: [token_id, 0] for bare NEW/LIST/RUN/CLR/...
resident_direct_record:   .res 2

.segment "RESIDENT"

.export resident_main
.export resident_poll_input
.export resident_submit_line
.export resident_assert_boundary
.export resident_input_byte
.export resident_enter_degraded
.export resident_show_expansion_error
.export resident_handle_key
.export quit_to_stock
.export quit_explicit_clr
.export vectors_restore

; resident_main - READY/editor loop.
; Foreground drains GETIN and dispatches keys. IRQ owns SCNKEY/UDTIM/cursor.
; Return submits the current screen line through the expansion editor service.
resident_main:
    lda resident_degraded
    bne resident_minimal_editor
@loop:
    jsr resident_poll_input
    beq @loop
    sta resident_last_key
    jsr resident_handle_key
    jmp resident_main

; resident_enter_degraded - Enter minimal no-store editor (error + QUIT only).
; Input: none. Output: never returns.
; Side effects: sets resident_degraded, prints expansion error, loops.
resident_enter_degraded:
    lda #1
    sta resident_degraded
    ; Fall through into the minimal editor.

resident_minimal_editor:
    jsr resident_show_expansion_error
    ; Type on the line below the error banner.
    lda #0
    sta zp_crsr_x
    lda #1
    sta zp_crsr_y
    jsr screen_cursor_on
@loop:
    jsr resident_poll_input
    beq @loop
    sta resident_last_key
    jsr resident_handle_key
    ; QUIT leaves degraded (never returns). Rejected submits re-show the
    ; banner inside resident_handle_key; keep draining keys here.
    jmp @loop

; resident_show_expansion_error - Print the expansion-memory failure banner.
; Input: none. Output: C=0. Clobbers: A, X, Y.
resident_show_expansion_error:
    ldx #0
@copy:
    lda expansion_error_msg, x
    beq @done
    sta $0400, x
    inx
    cpx #40
    bcc @copy
@done:
    clc
    rts

; resident_submit_degraded - Accept only QUIT in the minimal editor.
; Captures the logical screen line and matches ASCII "QUIT" (case-insensitive).
; Any other non-empty command re-shows the expansion error (caller loops).
; Input: none. Output: C=0 always when returning; QUIT does not return.
; Clobbers: A, X, Y.
resident_submit_degraded:
    jsr screen_line_input
    lda zp_line_len
    beq @empty
    cmp #4
    bne @reject
    ldy #0
@check:
    lda (zp_linebuf), y
    and #$7F
    ; Fold ASCII letters to uppercase for case-insensitive QUIT match.
    cmp #'a'
    bcc @cmp
    cmp #'z'+1
    bcs @cmp
    and #$DF
@cmp:
    cmp quit_ascii, y
    bne @reject
    iny
    cpy #4
    bne @check
    jmp quit_to_stock
@reject:
    sec
    rts
@empty:
    clc
    rts

quit_ascii:
    .byte "QUIT"

expansion_error_msg:
    .byte "?EXPANSION MEMORY REQUIRED"
    .byte 0

resident_poll_input:
    lda resident_input_byte
    bne @consume
    jsr kernal_getin
    rts
@consume:
    pha
    lda #$00
    sta resident_input_byte
    pla
    rts

; resident_handle_key - Dispatch one GETIN PETSCII byte.
; CR submits the current screen line; DEL erases left; cursor keys move;
; printable bytes are echoed into screen RAM at the project cursor.
; Input: A = key. Output: none. Clobbers: A, X, Y.
resident_handle_key:
    cmp #$0D
    beq @return
    cmp #$14
    beq @delete
    cmp #$1D
    beq @right
    cmp #$9D
    beq @left
    cmp #$11
    beq @down
    cmp #$91
    beq @up
    ; Ignore remaining controls; echo printable PETSCII.
    cmp #$20
    bcc @done
    jmp screen_put_petscii
@right:
    jmp screen_cursor_right
@left:
    jmp screen_cursor_left
@down:
    jmp screen_cursor_down
@up:
    jmp screen_cursor_up
@delete:
    ; Minimal DEL: move left and blank the cell under the cursor.
    lda zp_crsr_x
    bne @del_go
    lda zp_crsr_y
    beq @done
@del_go:
    jsr screen_cursor_left
    jsr screen_cursor_hide
    lda zp_crsr_y
    ; Write space without advancing: reuse putchar path carefully.
    pha
    lda zp_crsr_x
    pha
    lda #$20
    jsr screen_putchar
    pla
    sta zp_crsr_x
    pla
    sta zp_crsr_y
    jsr screen_cursor_on
@done:
    rts
@return:
    jsr screen_cursor_off
    lda resident_degraded
    bne @degraded_submit
    jsr resident_submit_line
    bcs @submit_failed
    ; Direct execution may have printed through CHROUT; adopt the KERNAL
    ; cursor so the next edit line follows the output.
    jsr screen_sync_from_kernal
    jsr screen_cursor_on
    rts
@submit_failed:
    ; Keep the typed line visible; move to the next physical row for retry.
    lda #0
    sta zp_crsr_x
    jsr screen_cursor_down
    jsr screen_cursor_on
    rts
@degraded_submit:
    jsr resident_submit_degraded
    bcs @reject_degraded
    jsr screen_sync_from_kernal
    jsr screen_cursor_on
    rts
@reject_degraded:
    ; Wrong command in degraded mode: re-show error and re-enable typing.
    jsr resident_show_expansion_error
    lda #0
    sta zp_crsr_x
    lda #1
    sta zp_crsr_y
    jsr screen_cursor_on
    rts

resident_submit_line:
    lda resident_degraded
    bne @degraded
    ; GETIN bridges briefly select $01=$36. Force the canonical map and clear
    ; decimal mode so submit is not rejected by a mid-bridge pause state.
    cld
    lda #CPU_PORT_CANONICAL
    sta $01
    ; Re-arm the capture pointer every submit. zp_linebuf may share a fragile
    ; ZP slot that KERNAL bridges can clobber across GETIN/CHROUT windows.
    lda #<resident_line_capture
    sta zp_linebuf
    lda #>resident_line_capture
    sta zp_linebuf+1
    jsr screen_line_input
    lda zp_line_len
    beq @empty
    ; DOS wedge prefixes are recognized ahead of tokenization.
    jsr resident_try_wedge
    bcc @done
    ; Numbered program lines: store PETSCII body in the interim line table.
    jsr resident_line_is_numbered
    bcs @program_line
    ; Direct-only commands (NEW/LIST/RUN/CLR/QUIT/...) via tokenizer front door.
    jsr resident_try_direct_command
    bcc @done
    ; Temporary statements (PRINT, assignments, etc.): always-mapped pipeline.
    ldx zp_linebuf
    ldy zp_linebuf+1
    lda #<GEORAM_ROUTINE_ID_PIPELINE_COMPILE_LINE
    jsr georam_call_group_n_xy
    bcs @fail
    jsr resident_kernal_cursor_below
    jsr codegen_buffer
    ; Restore editor map/IRQs after compiled code (may have used KERNAL bridges).
    cld
    lda #CPU_PORT_CANONICAL
    sta $01
    cli
    jmp @done
@program_line:
    jsr program_lines_put_linebuf
    bcs @fail
    jmp @done
@done:
    lda zp_line_len
    sta resident_last_submit_len
    inc resident_submit_count
    clc
    rts
@empty:
    clc
    rts
@degraded:
    jmp resident_submit_degraded
@fail:
    sec
    rts

; resident_try_direct_command - Tokenize and dispatch bare direct-only keywords.
; On match: builds [token_id, 0], runs direct_execute_command, returns C=0
; (handled — success or command error; do not also compile).
; On non-match (temporary statement / bare assignment): returns C=1 so the
; caller falls through to pipeline_compile_line.
; Input: zp_linebuf / zp_line_len. Output: C clear if handled.
; Clobbers: A, X, Y.
.export resident_try_direct_command
resident_try_direct_command:
    ldx zp_linebuf
    ldy zp_linebuf+1
    lda #<GEORAM_ROUTINE_ID_TOKEN_INIT
    jsr georam_call_group_0_xy
    jsr token_next
    ; Require an identifier with a keyword id in the direct-only set.
    lda token_last_type
    cmp #TOKEN_TYPE_IDENTIFIER
    bne @not_direct
    lda token_keyword_id
    beq @not_direct
    cmp #BASIC_TOKEN_RUN
    beq @dispatch
    cmp #BASIC_TOKEN_LIST
    beq @dispatch
    cmp #BASIC_TOKEN_CLR
    beq @dispatch
    cmp #BASIC_TOKEN_NEW
    beq @dispatch
    cmp #BASIC_TOKEN_QUIT
    beq @dispatch
    cmp #BASIC_TOKEN_LOAD
    beq @dispatch
    cmp #BASIC_TOKEN_SAVE
    beq @dispatch
    cmp #BASIC_TOKEN_VERIFY
    beq @dispatch
    cmp #BASIC_TOKEN_CONT
    beq @dispatch
    cmp #BASIC_TOKEN_COMPILE
    beq @dispatch
    cmp #BASIC_TOKEN_BASIC
    beq @dispatch
    cmp #BASIC_TOKEN_FPMODE
    beq @dispatch
@not_direct:
    sec
    rts
@dispatch:
    sta resident_direct_record
    lda #0
    sta resident_direct_record+1
    jsr resident_kernal_cursor_below
    ldx #<resident_direct_record
    ldy #>resident_direct_record
    lda #<GEORAM_ROUTINE_ID_DIRECT_EXECUTE_COMMAND
    jsr georam_call_group_n_xy
    ; Restore canonical map after command side effects (CLR/LIST/IO).
    ; QUIT never returns. Treat any command outcome as handled.
    cld
    lda #CPU_PORT_CANONICAL
    sta $01
    cli
    clc
    rts


; resident_try_wedge - If the line starts with $ @ / !, run the wedge core.
; Output: C clear when handled; C set when the line is not a wedge command.
.export resident_try_wedge
resident_try_wedge:
    ldy #0
@skip:
    cpy zp_line_len
    bcs @no
    lda (zp_linebuf), y
    cmp #' '
    bne @kind
    iny
    bne @skip
@kind:
    cmp #'$'
    bne @at
    lda #0
    jmp @run
@at:
    cmp #'@'
    bne @slash
    lda #1
    jmp @run
@slash:
    cmp #'/'
    bne @bang
    lda #2
    jmp @run
@bang:
    cmp #'!'
    bne @no
    lda #3
@run:
    ; A=kind; X/Y = full line pointer (wedge parsers skip the prefix).
    pha
    ; Directory/status stream through CHROUT; park the KERNAL cursor under the
    ; typed wedge line first so the listing does not overwrite the command.
    jsr resident_kernal_cursor_below
    pla
    ldx zp_linebuf
    ldy zp_linebuf+1
    jsr wedge_dispatch_development
    ; Restore canonical map after disk/KERNAL bridges.
    cld
    lda #CPU_PORT_CANONICAL
    sta $01
    cli
    ; Treat success and reported errors as "handled" so we do not also compile.
    clc
    rts
@no:
    sec
    rts

; Carry set when the PETSCII capture starts with a digit (optional spaces).
resident_line_is_numbered:
    ldy #0
@skip:
    cpy zp_line_len
    bcs @no
    lda (zp_linebuf), y
    cmp #' '
    bne @check
    iny
    bne @skip
@check:
    cmp #'0'
    bcc @no
    cmp #'9'+1
    bcs @no
    sec
    rts
@no:
    clc
    rts

; resident_direct_print - Execute PRINT "text" from zp_linebuf without geoRAM.
; Input:  zp_linebuf/zp_line_len filled by screen_line_input.
; Output: C clear when this form was recognized and printed; C set to decline.
; Clobbers: A, X, Y.
.export resident_direct_print
resident_direct_print:
    ldy #0
@skip_sp:
    cpy zp_line_len
    bcs @decline
    lda (zp_linebuf), y
    cmp #' '
    bne @match_print
    iny
    bne @skip_sp
@match_print:
    ; Require the five letters P R I N T (case-insensitive PETSCII).
    jsr resident_fold_letter
    cmp #'P'
    bne @decline
    iny
    jsr resident_fold_letter
    cmp #'R'
    bne @decline
    iny
    jsr resident_fold_letter
    cmp #'I'
    bne @decline
    iny
    jsr resident_fold_letter
    cmp #'N'
    bne @decline
    iny
    jsr resident_fold_letter
    cmp #'T'
    bne @decline
    iny
@skip_sp2:
    cpy zp_line_len
    bcs @decline
    lda (zp_linebuf), y
    cmp #' '
    bne @open_quote
    iny
    bne @skip_sp2
@open_quote:
    cmp #'"'
    bne @decline
    iny
    ; Editor writes screen RAM without updating KERNAL PNTR/TBLX. Point
    ; CHROUT at the row under the command so output does not overwrite it.
    jsr resident_kernal_cursor_below
@emit:
    cpy zp_line_len
    bcs @decline
    lda (zp_linebuf), y
    cmp #'"'
    beq @close
    jsr kernal_chrout
    iny
    bne @emit
@close:
    iny
@trail:
    cpy zp_line_len
    bcs @cr
    lda (zp_linebuf), y
    cmp #' '
    bne @decline
    iny
    bne @trail
@cr:
    lda #$0D
    jsr kernal_chrout
    clc
    rts
@decline:
    sec
    rts

; Place the stock KERNAL editor cursor on the line below zp_crsr_y.
; Set TBLX/PNT/PNTR for the command row, then CHROUT CR to advance one line
; using the ROM path (keeps all KERNAL line state consistent).
resident_kernal_cursor_below:
    lda zp_crsr_y
    sta $D6                 ; TBLX = command row
    ; PNT = $0400 + TBLX * 40
    tax
    lda #0
    sta $D1
    sta $D2
    cpx #0
    beq @base
@mul:
    lda $D1
    clc
    adc #40
    sta $D1
    bcc @nx
    inc $D2
@nx:
    dex
    bne @mul
@base:
    lda $D1
    clc
    adc #<$0400
    sta $D1
    lda $D2
    adc #>$0400
    sta $D2
    lda #0
    sta $D3                 ; PNTR
    lda #$0D
    jmp kernal_chrout

; resident_fold_letter - Load (zp_linebuf),Y as uppercase A-Z, else A=0.
resident_fold_letter:
    cpy zp_line_len
    bcs @bad
    lda (zp_linebuf), y
    cmp #'a'
    bcc @up
    cmp #'z'+1
    bcs @up
    and #$DF
@up:
    cmp #'A'
    bcc @bad
    cmp #'Z'+1
    bcs @bad
    rts
@bad:
    lda #0
    rts

resident_assert_boundary:
    php
    pla
    sta resident_saved_p
    lda $01
    cmp #$35
    bne @fail
    lda resident_saved_p
    and #$08
    bne @fail
    jsr georam_verify_mirror
    bcs @fail
    lda zp_gr_ctx_sp
    cmp #$08
    bcs @fail
    clc
    rts
@fail:
    sec
    rts

; vectors_restore - Restore prior IRQ/NMI vectors saved by compiler_vectors.
; Resident so QUIT/degraded leave works without expansion-native code.
; Input:  none
; Output: C clear when priors were installed and restored; C set if never installed
; Clobbers: A
; Side effects: writes $0314-$0315 and $0318-$0319
vectors_restore:
    lda vectors_installed
    beq @not_installed
    lda vectors_prior_irq
    sta CINV
    lda vectors_prior_irq+1
    sta CINV+1
    lda vectors_prior_nmi
    sta NMINV
    lda vectors_prior_nmi+1
    sta NMINV+1
    lda #0
    sta vectors_installed
    clc
    rts
@not_installed:
    sec
    rts

; quit_to_stock - Soft-reset leave path for QUIT (gateway, direct-only).
; Locked sequence (REQUIREMENTS R4 / DESIGN2 §8.5):
;   1. restore banking/map pointers and prior IRQ/NMI vectors
;   2. clean Compiler 2-owned continuation/control state
;   3. CLR explicitly (keep tokenized program)
;   4. enter stock READY with BASIC+KERNAL map
; Expansion device contents are left untouched. Does not return.
; Input: none. Output: never returns.
; Clobbers: A, X, Y, stack, mapping, BASIC variable map.
quit_to_stock:
    sei
    cld
    ldx #$FF
    txs
    ; Canonical project map while we touch project BSS and stock ZP.
    lda #CPU_PORT_CANONICAL
    sta $01
    jsr vectors_restore
    ; Resident-safe CONT invalidation (no geoRAM CODE dependency).
    jsr nmi_invalidate_cont
    jsr quit_explicit_clr
    lda #1
    sta resident_quit_done
    lda #0
    sta resident_degraded
    ; Stock BASIC + KERNAL + I/O, then READY.
    lda #CPU_PORT_STOCK
    sta $01
    cli
    jmp STOCK_READY

; quit_explicit_clr - Stock CLR semantics without cold init.
; Resets arytab/strend to vartab, fretop to memsiz, and the string stack
; pointer, leaving txttab/program text intact (clearc + temppt).
; Input: none. Output: C=0. Clobbers: A, Y.
quit_explicit_clr:
    lda BASIC_MEMSIZ
    ldy BASIC_MEMSIZ+1
    sta BASIC_FRETOP
    sty BASIC_FRETOP+1
    lda BASIC_VARTAB
    ldy BASIC_VARTAB+1
    sta BASIC_ARYTAB
    sty BASIC_ARYTAB+1
    sta BASIC_STREND
    sty BASIC_STREND+1
    lda #BASIC_TEMPST
    sta BASIC_TEMPPT
    clc
    rts
