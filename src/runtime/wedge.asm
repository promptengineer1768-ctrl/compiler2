; src/runtime/wedge.asm
; Development DOS wedge dispatch and bounded output formatting.

.include "common/constants.asm"
.include "common/zp.inc"

.import kernal_setnam, kernal_setlfs, kernal_open, kernal_close
.import kernal_chkin, kernal_clrchn, kernal_chrin, kernal_chrout
.import kernal_load, kernal_readst, kernal_stop

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
wedge_request: .res 2
wedge_name: .res 2
wedge_name_length: .res 1
wedge_byte: .res 1
wedge_logical: .res 1
wedge_secondary: .res 1

.segment "RODATA"
wedge_directory_name: .byte '$'

.segment "CODE"

; wedge_dispatch_development - Dispatch one validated development command.
; Inputs: A = command kind, X/Y = command record. Outputs: C=error.
; Side effects: records dispatch kind. Clobbers: A. Flags: C clear for 0..3,
; set otherwise. Zero page: none.
.export wedge_dispatch_development
wedge_dispatch_development:
    cmp #4
    bcs @invalid
    sta wedge_last_command
    clc
    rts
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
; points into the caller's command buffer and excludes quotes.
.proc wedge_parse_name
    stx wedge_request
    sty wedge_request+1
    stx zp_src
    sty zp_src+1
    ldy #1
    lda (zp_src),y
    cmp #'"'
    bne @start
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
    lda wedge_name_length
    ldx wedge_name
    ldy wedge_name+1
    jsr kernal_setnam
    bcs @done
    lda wedge_logical
    ldx $BA
    ldy wedge_secondary
    jsr kernal_setlfs
    bcs @done
    jsr kernal_open
    bcs @done
    ldx wedge_logical
    jsr kernal_chkin
@done:
    rts
.endproc

.proc wedge_stream_channel
@next:
    jsr kernal_readst
    bne @close
    jsr kernal_stop
    beq @close
    jsr kernal_chrin
    sta wedge_byte
    jsr kernal_chrout
    bcs @close_error
    jmp @next
@close:
    jsr kernal_clrchn
    lda wedge_logical
    jsr kernal_close
    clc
    rts
@close_error:
    php
    jsr kernal_clrchn
    lda wedge_logical
    jsr kernal_close
    plp
    sec
    rts
.endproc

; wedge_directory - Open "$" on the current device and stream it without
; loading over BASIC memory.
; Inputs: X/Y = textual $ command. Outputs: C=KERNAL error.
; Side effects: KERNAL channels and screen output. Clobbers: A, X, Y.
.export wedge_directory
wedge_directory:
    lda #WEDGE_DIRECTORY
    sta wedge_last_command
    lda #1
    ldx #<wedge_directory_name
    ldy #>wedge_directory_name
    sta wedge_name_length
    stx wedge_name
    sty wedge_name+1
    lda #2
    sta wedge_logical
    sta wedge_secondary
    jsr wedge_open_input
    bcs @done
    jmp wedge_stream_channel
@done:
    rts

; wedge_load_absolute - Select absolute-load semantics.
; Inputs: X/Y = filename/current-device record. Outputs: C clear.
; Side effects: records load dispatch. Clobbers: A. Zero page: none.
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

; wedge_status_or_command - Select status/device/command semantics.
; Inputs: A = status/command selector, X/Y = validated command record.
; Outputs: C clear. Side effects: records status dispatch. Clobbers: A.
; Zero page: none.
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
    cmp #'1'
    beq @two_digit_device
    cmp #'8'
    bcc @command
    cmp #('9'+1)
    bcc @single_device
    jmp @command
@two_digit_device:
    iny
    lda (zp_src),y
    cmp #'0'
    beq @device_ten
    cmp #'1'
    beq @device_eleven
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
@done:
    rts

; wedge_stream_seq - Select sequential-file streaming.
; Inputs: X/Y = filename/output record. Outputs: C clear.
; Side effects: records stream dispatch. Clobbers: A. Zero page: none.
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
; Inputs: X/Y -> command record; byte zero nonzero confirms. Outputs: C clear
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
