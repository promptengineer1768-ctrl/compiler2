; src/runtime/io.asm
; Compiler 2 runtime console and channel helpers.
;
; Public entries: io_print_value, io_print_newline, io_print_space,
; io_print_tab, io_print_comma, io_print_semicolon, io_input_value,
; io_input_string, io_get, io_cmd
; Internal helpers: _emit_byte, _emit_spaces
; Zero-page read:  zp_tmp1, zp_tmp2, zp_fac1
; Zero-page write: zp_tmp1, zp_tmp2, zp_fac1
; Clobbers: A, X, Y

.include "common/zp.inc"
.include "common/constants.asm"

.import arena_select_page
.import kernal_chrout, kernal_getin, kernal_chkout, kernal_chkin, kernal_chrin
.import kernal_clrchn
.import str_alloc, str_len, str_str, str_val
.import var_store_float, var_store_int, var_store_string
.import math_float_to_int

TYPE_FLOAT = $00
TYPE_INT1 = $01
TYPE_INT2 = $02
TYPE_INT3 = $03
TYPE_STRING = $04

.include "../build/workarea_symbols.inc"

.segment "BSS"
compiler_workarea:
    .res compiler_workarea_size
.export io_output_buf
io_output_buf = compiler_workarea + workarea_io_output
io_buffer = compiler_workarea + workarea_io_output
.export io_output_len
io_output_len:
    .res 1
.export io_input_char
io_input_char:
    .res 1
.export io_current_channel
io_current_channel:
    .res 1
io_value: .res 2
io_type: .res 1
io_negative: .res 1
io_started: .res 1
io_digit: .res 1
io_power_index: .res 1
io_saved_byte: .res 1
io_sd_ptr: .res 2
io_sd_length: .res 1
io_sd_offset: .res 1
io_fmt_request: .res 4
io_fmt_descriptor: .res 12
io_input_buf = compiler_workarea + workarea_io_input
io_input_len: .res 1
io_input_request: .res 2
io_input_dest: .res 2
io_input_prompt: .res 2
io_input_prompt_len: .res 1
io_input_channel: .res 1
io_var_request: .res 6
io_string_request: .res 5

.segment "RUNTIME"

_emit_byte:
    sta io_saved_byte
    ldx io_output_len
    cpx #64
    bcs @full
    lda io_saved_byte
    sta io_output_buf, x
    inx
    stx io_output_len
    lda io_saved_byte
    jsr kernal_chrout
    rts
@full:
    lda #ERR_STRING_TOO_LONG
    sec
    rts

_emit_spaces:
    sta io_digit
    beq @done
@loop:
    lda #' '
    jsr _emit_byte
    dec io_digit
    lda io_digit
    bne @loop
@done:
    rts

; Emit one validated arena-backed SD at X/Y.
.proc io_emit_string
    stx io_sd_ptr
    sty io_sd_ptr+1
    jsr str_len
    bcs @error
    sta io_sd_length
    lda io_sd_ptr
    sta zp_src
    lda io_sd_ptr+1
    sta zp_src+1
    ldy #8
    lda (zp_src), y
    sta io_sd_offset
    ldy #6
    lda (zp_src), y
    pha
    ldy #4
    lda (zp_src), y
    tax
    iny
    lda (zp_src), y
    tay
    pla
    jsr arena_select_page
    bcs @error
    lda #0
    sta io_power_index
@copy:
    lda io_power_index
    cmp io_sd_length
    beq @done
    clc
    adc io_sd_offset
    tay
    lda $DE00, y
    jsr _emit_byte
    bcs @error
    inc io_power_index
    bne @copy
@done:
    clc
@error:
    rts
.endproc

; io_print_value - Format adaptive numeric values or emit an SD string.
.export io_print_value
io_print_value:
    sta io_type
    cmp #TYPE_STRING
    bne :+
    jmp @string
:
    cmp #TYPE_FLOAT
    bne :+
    jmp @float
:
    cmp #TYPE_INT1
    beq @int1
    cmp #TYPE_INT2
    beq @signed_word
    cmp #TYPE_INT3
    beq :+
    jmp @error
:
    lda zp_fac1
    sta io_value
    lda zp_fac1+1
    sta io_value+1
    lda #0
    sta io_negative
    jmp @format_integer
@int1:
    lda zp_fac1
    sta io_value
    bpl @int1_positive
    lda #$ff
    bne @save_int1_high
@int1_positive:
    lda #0
@save_int1_high:
    sta io_value+1
@signed_word:
    lda io_type
    cmp #TYPE_INT2
    bne @signed_ready
    lda zp_fac1
    sta io_value
    lda zp_fac1+1
    sta io_value+1
@signed_ready:
    lda io_value+1
    and #$80
    sta io_negative
    beq @format_integer
    sec
    lda #0
    sbc io_value
    sta io_value
    lda #0
    sbc io_value+1
    sta io_value+1
@format_integer:
    lda io_negative
    beq @positive_sign
    lda #'-'
    bne @emit_sign
@positive_sign:
    lda #' '
@emit_sign:
    jsr _emit_byte
    bcc :+
    jmp @error
:
    lda #0
    sta io_started
    sta io_power_index
@power:
    lda #0
    sta io_digit
@subtract:
    ldx io_power_index
    lda io_value+1
    cmp io_decimal_hi, x
    bcc @digit_ready
    bne @take
    lda io_value
    cmp io_decimal_lo, x
    bcc @digit_ready
@take:
    sec
    lda io_value
    sbc io_decimal_lo, x
    sta io_value
    lda io_value+1
    sbc io_decimal_hi, x
    sta io_value+1
    inc io_digit
    bne @subtract
@digit_ready:
    lda io_digit
    bne @emit_digit
    lda io_started
    bne @emit_digit
    lda io_power_index
    cmp #4
    bne @next_power
@emit_digit:
    lda #1
    sta io_started
    lda io_digit
    clc
    adc #'0'
    jsr _emit_byte
    bcs @error
@next_power:
    inc io_power_index
    lda io_power_index
    cmp #5
    bne @power
    lda #' '
    jmp _emit_byte
@float:
    lda #'S'
    sta io_fmt_request
    lda #'T'
    sta io_fmt_request+1
    lda #<io_fmt_descriptor
    sta io_fmt_request+2
    lda #>io_fmt_descriptor
    sta io_fmt_request+3
    ldx #<io_fmt_request
    ldy #>io_fmt_request
    jsr str_str
    bcs @error
    ldx #<io_fmt_descriptor
    ldy #>io_fmt_descriptor
    jsr io_emit_string
    bcs @error
    lda #' '
    jmp _emit_byte
@string:
    ldx zp_fac1
    ldy zp_fac1+1
    jmp io_emit_string
@error:
    lda #ERR_TYPE_MISMATCH
    sec
    rts

; io_print_cstr - Emit a NUL-terminated PETSCII string at X/Y.
; Input:  X/Y = pointer to text. Output: C=0 on success, C=1 on overflow.
; Clobbers: A, X, Y. Side effects: CHROUT via _emit_byte.
.export io_print_cstr
io_print_cstr:
    stx zp_src
    sty zp_src+1
    ldy #0
@loop:
    lda (zp_src), y
    beq @done
    jsr _emit_byte
    bcs @error
    iny
    bne @loop
@done:
    clc
    rts
@error:
    rts

; io_print_newline - Emit a carriage return.
.export io_print_newline
io_print_newline:
    lda #$0D
    jsr _emit_byte
    rts

; io_print_space - Emit a space.
.export io_print_space
io_print_space:
    lda #' '
    jsr _emit_byte
    rts

; io_print_tab - Emit A spaces.
.export io_print_tab
io_print_tab:
    jsr _emit_spaces
    rts

; io_print_comma - Advance to the next ten-column print zone.
.export io_print_comma
io_print_comma:
    lda io_output_len
@reduce:
    cmp #10
    bcc @remainder
    sec
    sbc #10
    bcs @reduce
@remainder:
    sta io_digit
    lda #10
    sec
    sbc io_digit
    jmp _emit_spaces

; io_print_semicolon - Suppress output.
.export io_print_semicolon
io_print_semicolon:
    rts

; Parse IN: "IN", destination VD pointer, prompt pointer, prompt length,
; channel (0=keyboard), reserved:u16. Captures one bounded line.
.proc io_capture_input
    stx io_input_request
    sty io_input_request+1
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #'I'
    beq :+
    jmp @error
:
    iny
    lda (zp_src), y
    cmp #'N'
    beq :+
    jmp @error
:
    iny
    lda (zp_src), y
    sta io_input_dest
    iny
    lda (zp_src), y
    sta io_input_dest+1
    iny
    lda (zp_src), y
    sta io_input_prompt
    iny
    lda (zp_src), y
    sta io_input_prompt+1
    iny
    lda (zp_src), y
    sta io_input_prompt_len
    iny
    lda (zp_src), y
    sta io_input_channel
    iny
    lda (zp_src), y
    iny
    ora (zp_src), y
    bne @error
    lda io_input_prompt_len
    beq @default_prompt
    lda io_input_prompt
    sta zp_src
    lda io_input_prompt+1
    sta zp_src+1
    ldy #0
@prompt:
    cpy io_input_prompt_len
    beq @select
    lda (zp_src), y
    tya
    pha
    lda (zp_src), y
    jsr _emit_byte
    pla
    tay
    bcs @error
    iny
    bne @prompt
@default_prompt:
    lda #'?'
    jsr _emit_byte
    bcs @error
    lda #' '
    jsr _emit_byte
    bcs @error
@select:
    lda io_input_channel
    beq @read
    tax
    jsr kernal_chkin
    bcs @error
@read:
    lda #0
    sta io_input_len
@read_loop:
    jsr kernal_chrin
    cmp #0
    beq @done
    cmp #$0d
    beq @done
    ldx io_input_len
    cpx #63
    bcs @error_restore
    sta io_input_buf, x
    inx
    stx io_input_len
    bne @read_loop
@done:
    lda io_input_channel
    beq @success
    jsr kernal_clrchn
    bcs @error
@success:
    clc
    rts
@error_restore:
    lda io_input_channel
    beq @error
    jsr kernal_clrchn
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Materialize the captured bytes as one canonical temporary SD.
.proc io_make_input_string
    lda #'S'
    sta io_string_request
    lda #'A'
    sta io_string_request+1
    lda #<io_fmt_descriptor
    sta io_string_request+2
    lda #>io_fmt_descriptor
    sta io_string_request+3
    lda io_input_len
    sta io_string_request+4
    ldx #<io_string_request
    ldy #>io_string_request
    jsr str_alloc
    bcs @error
    lda io_input_len
    beq @done
    lda io_fmt_descriptor+6
    ldx io_fmt_descriptor+4
    ldy io_fmt_descriptor+5
    jsr arena_select_page
    bcs @error
    ldy #0
@copy:
    cpy io_input_len
    beq @done
    lda io_input_buf, y
    sta $DE00, y
    iny
    bne @copy
@done:
    ldx #<io_fmt_descriptor
    ldy #>io_fmt_descriptor
    clc
@error:
    rts
.endproc

; io_input_value - Capture, parse, coerce, and store one numeric value.
.export io_input_value
io_input_value:
    jsr io_capture_input
    bcs @error
    jsr io_make_input_string
    bcs @error
    jsr str_val
    bcs @error
    lda io_input_dest
    sta zp_src
    lda io_input_dest+1
    sta zp_src+1
    ldy #2
    lda (zp_src), y
    cmp #1
    beq @integer
    cmp #2
    bne @error
    lda #'V'
    sta io_var_request
    lda #'F'
    sta io_var_request+1
    lda io_input_dest
    sta io_var_request+2
    lda io_input_dest+1
    sta io_var_request+3
    lda #0
    sta io_var_request+4
    sta io_var_request+5
    ldx #<io_var_request
    ldy #>io_var_request
    jmp var_store_float
@integer:
    jsr math_float_to_int
    bcs @error
    stx io_var_request+4
    sty io_var_request+5
    lda #'V'
    sta io_var_request
    lda #'I'
    sta io_var_request+1
    lda io_input_dest
    sta io_var_request+2
    lda io_input_dest+1
    sta io_var_request+3
    ldx #<io_var_request
    ldy #>io_var_request
    jmp var_store_int
@error:
    lda #ERR_TYPE_MISMATCH
    sec
    rts

; io_input_string - Return the buffered input character as a one-byte string.
.export io_input_string
io_input_string:
    jsr io_capture_input
    bcs @error
    jsr io_make_input_string
    bcs @error
@store:
    lda #'V'
    sta io_var_request
    lda #'S'
    sta io_var_request+1
    lda io_input_dest
    sta io_var_request+2
    lda io_input_dest+1
    sta io_var_request+3
    lda #<io_fmt_descriptor
    sta io_var_request+4
    lda #>io_fmt_descriptor
    sta io_var_request+5
    ldx #<io_var_request
    ldy #>io_var_request
    jmp var_store_string
@error:
    lda #ERR_TYPE_MISMATCH
    sec
    rts

; io_get - Read one buffered input byte into A.
.export io_get
io_get:
    jsr kernal_getin
    sta io_input_char
    clc
    rts

; io_cmd - Select an IC record's unsigned argument-byte logical file.
.export io_cmd
io_cmd:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #'I'
    bne @error
    iny
    lda (zp_src), y
    cmp #'C'
    bne @error
    iny
    lda (zp_src), y
    sta io_current_channel
    tax
    jmp kernal_chkout
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

io_decimal_lo: .byte <$2710, <$03E8, <$0064, <$000A, <$0001
io_decimal_hi: .byte >$2710, >$03E8, >$0064, >$000A, >$0001
