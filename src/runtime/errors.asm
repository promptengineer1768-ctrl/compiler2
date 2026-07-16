; src/runtime/errors.asm
; Compiler 2 runtime error helpers.
;
; Public entries: err_raise, err_raise_direct, err_from_kernal, err_syntax,
; err_type, err_overflow, err_outofmemory, err_undefdfunction, err_break,
; err_save_cont
; Internal helpers: none
; Zero-page read:  zp_errnum, zp_errline, zp_errptr, zp_cont_handle,
; zp_cont_generation, zp_stop_flag
; Zero-page write: zp_errnum, zp_errline, zp_errptr, zp_cont_handle,
; zp_cont_generation, zp_stop_flag
; Clobbers: A, X, Y

.include "common/zp.inc"
.include "common/constants.asm"

.import ctrl_reset, editor_ready_transition, graphics_exit
.import kernal_chrout, kernal_clrchn

.segment "BSS"
.export err_message_buffer, err_message_length
err_message_buffer: .res 48
err_message_length: .res 1
err_saved_code:     .res 1
err_saved_line:     .res 2
err_include_line:   .res 1

.segment "CODE"

; Append A to the bounded formatted-message buffer.
_err_append:
    ldx err_message_length
    cpx #48
    bcs @done
    sta err_message_buffer, x
    inc err_message_length
@done:
    rts

; Append the unsigned 16-bit source line in err_saved_line as decimal.
_err_append_line:
    lda #0
    sta zp_tmp1
    ldx #0
@ten_thousands:
    lda err_saved_line+1
    cmp #>10000
    bcc @thousands
    bne @sub_10000
    lda err_saved_line
    cmp #<10000
    bcc @thousands
@sub_10000:
    sec
    lda err_saved_line
    sbc #<10000
    sta err_saved_line
    lda err_saved_line+1
    sbc #>10000
    sta err_saved_line+1
    inx
    bne @ten_thousands
@thousands:
    txa
    beq @hundreds_setup
    ora #'0'
    jsr _err_append
    lda #1
    sta zp_tmp1
@hundreds_setup:
    ldx #0
@thousands_loop:
    lda err_saved_line+1
    cmp #>1000
    bcc @emit_thousands
    bne @sub_1000
    lda err_saved_line
    cmp #<1000
    bcc @emit_thousands
@sub_1000:
    sec
    lda err_saved_line
    sbc #<1000
    sta err_saved_line
    lda err_saved_line+1
    sbc #>1000
    sta err_saved_line+1
    inx
    bne @thousands_loop
@emit_thousands:
    txa
    bne @write_thousands
    lda zp_tmp1
    beq @hundreds
    txa
@write_thousands:
    ora #'0'
    jsr _err_append
    lda #1
    sta zp_tmp1
@hundreds:
    ldx #0
@hundreds_loop:
    lda err_saved_line+1
    bne @sub_100
    lda err_saved_line
    cmp #100
    bcc @emit_hundreds
@sub_100:
    sec
    lda err_saved_line
    sbc #100
    sta err_saved_line
    lda err_saved_line+1
    sbc #0
    sta err_saved_line+1
    inx
    bne @hundreds_loop
@emit_hundreds:
    txa
    bne @write_hundreds
    lda zp_tmp1
    beq @tens
    txa
@write_hundreds:
    ora #'0'
    jsr _err_append
    lda #1
    sta zp_tmp1
@tens:
    ldx #0
@tens_loop:
    lda err_saved_line
    cmp #10
    bcc @emit_tens
    sec
    sbc #10
    sta err_saved_line
    inx
    bne @tens_loop
@emit_tens:
    txa
    bne @write_tens
    lda zp_tmp1
    beq @ones
    txa
@write_tens:
    ora #'0'
    jsr _err_append
@ones:
    lda err_saved_line
    ora #'0'
    jmp _err_append

; Format err_saved_code and optional err_saved_line into err_message_buffer.
_err_format:
    lda #0
    sta err_message_length
    lda #'?'
    jsr _err_append
    lda err_saved_code
    cmp #1
    bcc @normalize
    cmp #30
    bcc @index
@normalize:
    lda #ERR_FILE_OPEN
    sta err_saved_code
@index:
    sec
    sbc #1
    tax
    lda error_message_lo, x
    sta zp_src
    lda error_message_hi, x
    sta zp_src+1
    ldy #0
@copy:
    lda (zp_src), y
    pha
    and #$7f
    jsr _err_append
    pla
    bmi @suffix
    iny
    bne @copy
@suffix:
    ldy #0
@suffix_loop:
    lda error_suffix, y
    pha
    and #$7f
    jsr _err_append
    pla
    bmi @line
    iny
    bne @suffix_loop
@line:
    lda err_include_line
    beq @done
    lda #' '
    jsr _err_append
    lda #'I'
    jsr _err_append
    lda #'N'
    jsr _err_append
    lda #' '
    jsr _err_append
    jsr _err_append_line
@done:
    rts

; Emit the formatted message, unwind runtime state, and enter development READY.
; ctrl_reset runs after READY publication: kernal_print_packed uses zp_tmptr,
; which is co-allocated with zp_cont_handle, so an earlier reset would be
; clobbered by the message path.
_err_unwind:
    jsr kernal_clrchn
    lda #0
    jsr graphics_exit
    ldy #0
@emit:
    cpy err_message_length
    beq @newline
    lda err_message_buffer, y
    jsr kernal_chrout
    iny
    bne @emit
@newline:
    lda #$0d
    jsr kernal_chrout
    jsr editor_ready_transition
    jsr ctrl_reset
    lda err_saved_code
    sec
    rts

_err_raise_common:
    sta err_saved_code
    sta zp_errnum
    jsr _err_format
    jmp _err_unwind

; err_raise - Record a BASIC error and its source line.
; Inputs: A=error code, X/Y=source line low/high.
; Outputs: A unchanged, C=1. Side effects: updates current error record.
; Clobbers: flags. Zero page: writes zp_errnum and zp_errline.
.export err_raise
err_raise:
    sta err_saved_code
    sta zp_errnum
    stx zp_errline
    sty zp_errline+1
    stx err_saved_line
    sty err_saved_line+1
    lda #1
    sta err_include_line
    lda err_saved_code
    jsr _err_format
    jmp _err_unwind

; err_raise_direct - Record a direct-mode BASIC error.
; Inputs: A=error code. Outputs: A unchanged, C=1.
; Side effects: updates current error number. Clobbers: flags.
; Zero page: writes zp_errnum.
.export err_raise_direct
err_raise_direct:
    pha
    lda #0
    sta err_include_line
    pla
    jmp _err_raise_common

; err_from_kernal - Translate a stock KERNAL error result.
; Inputs: A=KERNAL error number, C=KERNAL failure flag.
; Outputs: A=BASIC error code and C=1 on failure; A=ERR_OK and C=0 on success.
; Side effects: updates current error number. Clobbers: flags.
; Zero page: writes zp_errnum.
;
; Stock KERNAL error numbers 1..9 are the corresponding BASIC errors. A
; carry-set result outside that defined range is normalized to FILE OPEN.
.export err_from_kernal
err_from_kernal:
    bcc @ok
    cmp #ERR_TOO_MANY_FILES
    bcc @unknown
    cmp #(ERR_ILLEGAL_DEVICE_NUMBER + 1)
    bcs @unknown
    sta zp_errnum
    sec
    rts
@unknown:
    lda #ERR_FILE_OPEN
    sta zp_errnum
    sec
    rts
@ok:
    lda #ERR_OK
    sta zp_errnum
    clc
    rts

; err_syntax - Syntax error shortcut.
.export err_syntax
err_syntax:
    lda #ERR_SYNTAX
    jmp err_raise_direct

; err_type - Type mismatch error shortcut.
.export err_type
err_type:
    lda #ERR_TYPE_MISMATCH
    jmp err_raise_direct

; err_overflow - Overflow error shortcut.
.export err_overflow
err_overflow:
    lda #ERR_OVERFLOW
    jmp err_raise_direct

; err_outofmemory - Out of memory error shortcut.
.export err_outofmemory
err_outofmemory:
    lda #ERR_OUT_OF_MEMORY
    jmp err_raise_direct

; err_undefdfunction - Undefined function error shortcut.
.export err_undefdfunction
err_undefdfunction:
    lda #ERR_UNDEFINED_FUNCTION
    jmp err_raise_direct

; err_break - Record a resumable break point.
.export err_break
err_break:
    stx zp_cont_handle
    sty zp_cont_handle+1
    lda #$01
    sta zp_stop_flag
    lda #ERR_OK
    sta zp_errnum
    sec
    rts

; err_save_cont - Save a resumable continuation.
.export err_save_cont
err_save_cont:
    stx zp_cont_handle
    sty zp_cont_handle+1
    lda zp_cont_generation
    clc
    rts

error_suffix: .byte " ERRO", $d2

error_message_lo:
    .lobytes err01, err02, err03, err04, err05, err06, err07, err08, err09
    .lobytes err10, err11, err12, err13, err14, err15, err16, err17, err18
    .lobytes err19, err20, err21, err22, err23, err24, err25, err26, err27
    .lobytes err28, err29
error_message_hi:
    .hibytes err01, err02, err03, err04, err05, err06, err07, err08, err09
    .hibytes err10, err11, err12, err13, err14, err15, err16, err17, err18
    .hibytes err19, err20, err21, err22, err23, err24, err25, err26, err27
    .hibytes err28, err29

; Packed exactly like the stock BASIC ROM table: the final character carries
; bit 7, so no terminator byte is stored or scanned.
err01: .byte "TOO MANY FILE", $d3
err02: .byte "FILE OPE", $ce
err03: .byte "FILE NOT OPE", $ce
err04: .byte "FILE NOT FOUN", $c4
err05: .byte "DEVICE NOT PRESEN", $d4
err06: .byte "NOT INPUT FIL", $c5
err07: .byte "NOT OUTPUT FIL", $c5
err08: .byte "MISSING FILE NAM", $c5
err09: .byte "ILLEGAL DEVICE NUMBE", $d2
err10: .byte "NEXT WITHOUT FO", $d2
err11: .byte "SYNTA", $d8
err12: .byte "RETURN WITHOUT GOSU", $c2
err13: .byte "OUT OF DAT", $c1
err14: .byte "ILLEGAL QUANTIT", $d9
err15: .byte "OVERFLO", $d7
err16: .byte "OUT OF MEMOR", $d9
err17: .byte "UNDEF'D STATEMEN", $d4
err18: .byte "BAD SUBSCRIP", $d4
err19: .byte "REDIM'D ARRA", $d9
err20: .byte "DIVISION BY ZER", $cf
err21: .byte "ILLEGAL DIREC", $d4
err22: .byte "TYPE MISMATC", $c8
err23: .byte "STRING TOO LON", $c7
err24: .byte "FILE DAT", $c1
err25: .byte "FORMULA TOO COMPLE", $d8
err26: .byte "CAN'T CONTINU", $c5
err27: .byte "UNDEF'D FUNCTIO", $ce
err28: .byte "VERIF", $d9
err29: .byte "LOA", $c4
