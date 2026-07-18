; src/runtime/wedge.asm
; Normal-RAM DOS wedge core: directory, load, status/command, SEQ stream.
; Included by the installed runtime and standalone COMPILE exports.

.include "common/constants.asm"
.include "common/zp.inc"

.import kernal_setnam, kernal_setlfs, kernal_open, kernal_close
.import kernal_chkin, kernal_clrchn, kernal_chrin, kernal_chrout
.import kernal_load, kernal_readst, kernal_stop
.import screen_put_petscii, screen_cursor_down
.import keyword_name_lo, keyword_name_hi, keyword_length, keyword_token
.import keyword_count_value

WEDGE_DIRECTORY = 0
WEDGE_STATUS    = 1
WEDGE_LOAD      = 2
WEDGE_STREAM    = 3
WEDGE_OUTPUT_MAX = 80

.segment "BSS"
.export wedge_last_command
wedge_last_command:
    .res 1
.export wedge_output_buffer
wedge_output_buffer:
    .res WEDGE_OUTPUT_MAX
.export wedge_output_length
wedge_output_length:
    .res 1
.export wedge_current_device
wedge_current_device:
    .res 1
.export wedge_destructive_confirmed
wedge_destructive_confirmed:
    .res 1
wedge_request: .res 2
wedge_name: .res 2
wedge_name_length: .res 1
wedge_byte: .res 1
wedge_logical: .res 1
wedge_secondary: .res 1
wedge_quoted: .res 1
wedge_link: .res 2
wedge_line: .res 2
wedge_emit_tmp: .res 1

.segment "RODATA"
wedge_directory_name: .byte '$'

; Normal-RAM CODE: kept in the low image so local KERNAL stubs (above the
; RAM_HIGH install, currently $F900+) cannot overwrite the wedge core.
; Standalone exports include this segment with the rest of the runtime image.
.segment "CODE"

; wedge_dispatch_development - Dispatch one validated development command.
; Inputs: A = command kind ($=0, @=1, /=2, !=3), X/Y = command text pointer.
; Outputs: C=error. Side effects: records kind and runs the matching core path.
; Clobbers: A, X, Y. Flags: C set for invalid kind or handler error.
; Zero page: as used by the selected handler.
.export wedge_dispatch_development
wedge_dispatch_development:
    cmp #4
    bcs @invalid
    sta wedge_last_command
    cmp #WEDGE_DIRECTORY
    beq @directory
    cmp #WEDGE_STATUS
    beq @status
    cmp #WEDGE_LOAD
    beq @load
    jmp wedge_stream_seq
@directory:
    jmp wedge_directory
@status:
    jmp wedge_status_or_command
@load:
    jmp wedge_load_absolute
@invalid:
    lda #ERR_SYNTAX
    sec
    rts

; wedge_format_directory - Format one validated directory entry.
; Inputs: X/Y -> NUL-terminated entry text. Outputs: bounded output buffer.
; Side effects: replaces output. Clobbers: A, X, Y. Flags: C clear.
; Zero page: none.
.export wedge_format_directory
wedge_format_directory:
    stx @read+1
    sty @read+2
    ldy #0
@copy:
    cpy #WEDGE_OUTPUT_MAX
    beq @done
@read:
    lda $FFFF, y
    beq @done
    sta wedge_output_buffer, y
    iny
    bne @copy
@done:
    sty wedge_output_length
    clc
    rts

; Parse a prefix followed by an optional quoted filename. The returned name
; points into the caller's command buffer and excludes quotes. Unquoted names
; end at comma, colon (streamed as part of DOS forms after the name start is
; already past the prefix), end-of-line, or a closing quote.
.proc wedge_parse_name
    stx wedge_request
    sty wedge_request+1
    stx zp_src
    sty zp_src+1
    lda #0
    sta wedge_quoted
    ldy #1
    lda (zp_src),y
    cmp #'"'
    bne @start
    lda #1
    sta wedge_quoted
    iny
@start:
    tya
    clc
    adc wedge_request
    sta wedge_name
    lda wedge_request+1
    adc #0
    sta wedge_name+1
    ldx #0
@scan:
    lda (zp_src),y
    beq @done
    cmp #'"'
    beq @quoted_done
    lda wedge_quoted
    bne @accept
    lda (zp_src),y
    cmp #','
    beq @done
@accept:
    inx
    iny
    bne @scan
@quoted_done:
    iny
    lda (zp_src),y
    bne @error
@done:
    stx wedge_name_length
    cpx #0
    beq @error
    clc
    rts
@error:
    lda #ERR_SYNTAX
    sec
    rts
.endproc

.proc wedge_open_input
    ; SETNAM/SETLFS do not report failure in C; only OPEN/CHKIN do. A stale C
    ; from a prior bridge must not abort the setup.
    lda wedge_name_length
    ldx wedge_name
    ldy wedge_name+1
    clc
    jsr kernal_setnam
    lda wedge_logical
    ldx $BA
    ldy wedge_secondary
    clc
    jsr kernal_setlfs
    jsr kernal_open
    bcs @done
    ldx wedge_logical
    jsr kernal_chkin
@done:
    rts
.endproc

.proc wedge_stream_channel
    ; Stock SEQ/directory stream: CHRIN first, then READST. Checking status
    ; before the first read can exit immediately on a stale $90 left by the
    ; geoRAM loader or prior KERNAL I/O.
    ;
    ; Paint through the project screen path (not KERNAL CHROUT). After the
    ; geoRAM loader the stock screen-editor ZP (PNT/PNTR/TBLX) is not always
    ; coherent enough for CHROUT to hit visible cells, while PRINT works only
    ; because it first re-seeds that state. Directory bytes are ordinary
    ; PETSCII; CR advances the project cursor.
    ;
    ; STKEY ($91) must be $7F for KERNAL STOP to report "not pressed".
    lda #$7F
    sta $91
@next:
    jsr kernal_chrin
    sta wedge_byte
    jsr kernal_readst
    pha
    lda wedge_byte
    cmp #$0D
    beq @cr
    cmp #$0A
    beq @status
    ; Skip non-printable controls from the DOS listing stream.
    cmp #$20
    bcc @status
    jsr screen_put_petscii
    jmp @status
@cr:
    lda #0
    sta zp_crsr_x
    jsr screen_cursor_down
@status:
    pla
    bne @close
    jsr kernal_stop
    beq @close
    jmp @next
@close:
    jsr kernal_clrchn
    lda wedge_logical
    jsr kernal_close
    clc
    rts
.endproc

; wedge_directory - Open "$" on the current device and stream it without
; loading over BASIC memory.
; Inputs: X/Y = textual $ / @$ command. Outputs: C=KERNAL error.
; Side effects: KERNAL channels and screen output. Clobbers: A, X, Y.
.export wedge_directory
wedge_directory:
    lda #WEDGE_DIRECTORY
    sta wedge_last_command
    ; Ensure no leftover KERNAL channels / stale status from the geoRAM loader.
    jsr kernal_clrchn
    lda #0
    sta $90
    lda #1
    ldx #<wedge_directory_name
    ldy #>wedge_directory_name
    sta wedge_name_length
    stx wedge_name
    sty wedge_name+1
    ; Stock directory listing: OPEN lf,fa,0,"$" then CHKIN/CHRIN stream.
    ; Use LF 2 so LF 1 is free if the loader left it marked open.
    lda #2
    sta wedge_logical
    lda #0
    sta wedge_secondary
    ; Prefer the last-used device; fall back to 8 when fa was cleared.
    lda $BA
    bne @have_fa
    lda #8
    sta $BA
@have_fa:
    ; Close LF first so a stale table entry cannot make OPEN fail silently.
    lda wedge_logical
    jsr kernal_close
    jsr wedge_open_input
    bcc @stream
    ; Record open failure for diagnostics; still return handled.
    lda #1
    sta wedge_output_length
    sec
    rts
@stream:
    lda #0
    sta wedge_output_length
    jmp wedge_stream_directory
@done:
    rts

; OPEN "$",sa=0 yields a tokenized BASIC *program* image of the directory
; (same bytes as LOAD "$"), not plain PETSCII. Detokenize line-by-line and
; paint through the project screen path.
.proc wedge_stream_directory
    ; Skip 2-byte PRG load address (OPEN "$",sa=0 is the LOAD "$" image).
    jsr kernal_chrin
    jsr kernal_readst
    bne @close
    jsr kernal_chrin
    jsr kernal_readst
    bne @close
@line:
    jsr kernal_chrin
    sta wedge_link
    jsr kernal_readst
    bne @close
    jsr kernal_chrin
    sta wedge_link+1
    jsr kernal_readst
    bne @close
    lda wedge_link
    ora wedge_link+1
    beq @close
    jsr kernal_chrin
    sta wedge_line
    jsr kernal_chrin
    sta wedge_line+1
    jsr wedge_print_u16
    lda #' '
    jsr screen_put_petscii
@body:
    jsr kernal_chrin
    sta wedge_byte
    jsr kernal_readst
    pha
    lda wedge_byte
    beq @eol
    bmi @tok
    jsr screen_put_petscii
    jmp @more
@tok:
    jsr wedge_emit_token
@more:
    pla
    bne @close
    jmp @body
@eol:
    pla
    lda #0
    sta zp_crsr_x
    jsr screen_cursor_down
    jmp @line
@close:
    jsr kernal_clrchn
    lda wedge_logical
    jsr kernal_close
    clc
    rts
.endproc

; Print wedge_line (u16) as decimal PETSCII via the project screen.
.proc wedge_print_u16
    lda #0
    sta wedge_quoted
    lda #<10000
    ldx #>10000
    jsr @digit
    lda #<1000
    ldx #>1000
    jsr @digit
    lda #<100
    ldx #>100
    jsr @digit
    lda #<10
    ldx #>10
    jsr @digit
    lda wedge_line
    ora #'0'
    jmp screen_put_petscii
@digit:
    sta wedge_link
    stx wedge_link+1
    lda #0
    sta wedge_emit_tmp
@sub:
    lda wedge_line+1
    cmp wedge_link+1
    bcc @emit
    bne @take
    lda wedge_line
    cmp wedge_link
    bcc @emit
@take:
    lda wedge_line
    sec
    sbc wedge_link
    sta wedge_line
    lda wedge_line+1
    sbc wedge_link+1
    sta wedge_line+1
    inc wedge_emit_tmp
    bne @sub
@emit:
    lda wedge_emit_tmp
    bne @out
    lda wedge_quoted
    beq @done
@out:
    lda #1
    sta wedge_quoted
    lda wedge_emit_tmp
    ora #'0'
    jsr screen_put_petscii
@done:
    rts
.endproc

; Emit BASIC token A ($80+) as its keyword name, or '?' if unknown.
.proc wedge_emit_token
    sta wedge_emit_tmp
    ldx #0
@find:
    cpx keyword_count_value
    beq @unk
    lda keyword_token, x
    cmp wedge_emit_tmp
    beq @found
    inx
    bne @find
@unk:
    lda #'?'
    jmp screen_put_petscii
@found:
    lda keyword_name_lo, x
    sta zp_src
    lda keyword_name_hi, x
    sta zp_src+1
    lda keyword_length, x
    sta wedge_emit_tmp
    ldy #0
@copy:
    cpy wedge_emit_tmp
    beq @done
    lda (zp_src), y
    sty wedge_quoted
    jsr screen_put_petscii
    ldy wedge_quoted
    iny
    bne @copy
@done:
    rts
.endproc

; wedge_load_absolute - Absolute PRG load equivalent to LOAD "name",fa,1.
; Inputs: X/Y = /filename text. Outputs: C=KERNAL error.
; Side effects: records load dispatch; may replace program memory via LOAD.
; Clobbers: A, X, Y. Zero page: zp_src.
.export wedge_load_absolute
wedge_load_absolute:
    lda #WEDGE_LOAD
    sta wedge_last_command
    jsr wedge_parse_name
    bcs @done
    lda wedge_name_length
    ldx wedge_name
    ldy wedge_name+1
    jsr kernal_setnam
    bcs @done
    lda #1
    ldx $BA
    ldy #1
    jsr kernal_setlfs
    bcs @done
    lda #0
    ldx #0
    ldy #0
    jmp kernal_load
@done:
    rts

; wedge_status_or_command - Bare @ status, @8-@11 device select, @$ directory,
; or @command sent on the command channel (with confirmation for S/N forms).
; Inputs: X/Y = validated @ command text. Outputs: C=error or declined.
; Side effects: may write fa ($BA), open channels, stream status. Clobbers: A,X,Y.
.export wedge_status_or_command
wedge_status_or_command:
    lda #WEDGE_STATUS
    sta wedge_last_command
    stx wedge_request
    sty wedge_request+1
    stx zp_src
    sty zp_src+1
    ldy #1
    lda (zp_src),y
    ; @$ is the Action Replay directory alias.
    cmp #'$'
    beq @at_directory
    cmp #'1'
    beq @two_digit_device
    cmp #'8'
    bcc @command
    cmp #('9'+1)
    bcc @single_device
    jmp @command
@at_directory:
    iny
    lda (zp_src),y
    bne @command
    jmp wedge_directory
@two_digit_device:
    iny
    lda (zp_src),y
    cmp #'0'
    bne @check_eleven
    jmp @device_ten
@check_eleven:
    cmp #'1'
    bne @two_digit_fail
    jmp @device_eleven
@two_digit_fail:
    jmp @command
@single_device:
    sec
    sbc #'0'
    ldy #2
    pha
    lda (zp_src),y
    bne @command_pop
    pla
    sta $BA
    sta wedge_current_device
    clc
    rts
@command_pop:
    pla
@command:
    ; Bare @ opens the command/error channel with an empty KERNAL filename.
    ldy #1
    lda (zp_src),y
    bne @named_command
    lda wedge_request
    clc
    adc #1
    sta wedge_name
    lda wedge_request+1
    adc #0
    sta wedge_name+1
    lda #0
    sta wedge_name_length
    lda #15
    sta wedge_logical
    sta wedge_secondary
    jsr wedge_open_input
    bcs @done
    jmp wedge_stream_channel
@named_command:
    ; Scratch (S...) and NEW/format (N...) require prior confirmation.
    ldy #1
    lda (zp_src),y
    cmp #'"'
    bne @check_destructive
    iny
    lda (zp_src),y
@check_destructive:
    and #$7F
    cmp #'S'
    beq @need_confirm
    cmp #'N'
    beq @need_confirm
    jmp @send_named
@need_confirm:
    ldx #<wedge_destructive_confirmed
    ldy #>wedge_destructive_confirmed
    jsr wedge_confirm_destructive
    bcs @declined
    lda #0
    sta wedge_destructive_confirmed
@send_named:
    ldx wedge_request
    ldy wedge_request+1
    jsr wedge_parse_name
    bcs @done
    lda #15
    sta wedge_logical
    sta wedge_secondary
    jsr wedge_open_input
    bcs @done
    jmp wedge_stream_channel
@device_ten:
    lda #10
    bne @two_digit
@device_eleven:
    lda #11
@two_digit:
    ldy #3
    pha
    lda (zp_src),y
    bne @command_pop
    pla
    sta $BA
    sta wedge_current_device
    clc
    rts
@declined:
    lda #ERR_SYNTAX
    sec
@done:
    rts

; wedge_stream_seq - Stream a SEQ file's PETSCII to the current screen.
; Inputs: X/Y = !filename text. Outputs: C=error or STOP. STOP closes the file.
; Side effects: KERNAL channels and screen output. Clobbers: A, X, Y.
.export wedge_stream_seq
wedge_stream_seq:
    lda #WEDGE_STREAM
    sta wedge_last_command
    jsr wedge_parse_name
    bcs @done
    lda #2
    sta wedge_logical
    sta wedge_secondary
    jsr wedge_open_input
    bcs @done
    jmp wedge_stream_channel
@done:
    rts

; wedge_confirm_destructive - Require an explicit confirmation byte.
; Inputs: X/Y -> flag record; byte zero nonzero confirms. Outputs: C clear
; when confirmed, set when declined. Side effects: none. Clobbers: A, X, Y.
; Zero page: none.
.export wedge_confirm_destructive
wedge_confirm_destructive:
    stx @read+1
    sty @read+2
@read:
    lda $FFFF
    beq @declined
    clc
    rts
@declined:
    sec
    rts
