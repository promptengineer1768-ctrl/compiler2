; src/geoasm/diagnostics.asm
; Bounded compiler diagnostic formatting and KERNAL error translation.

.include "common/zp.inc"
.include "common/constants.asm"

DIAG_ERROR       = 0
DIAG_WARNING     = 1
DIAG_CONTEXT_MAX = 32

.segment "BSS"
.export diag_record
diag_record:
    .res 5
.export diag_context_buffer
diag_context_buffer:
    .res DIAG_CONTEXT_MAX
.export diag_context_length
diag_context_length:
    .res 1
.export diag_print_count
diag_print_count:
    .res 1
diag_source_lo:
    .res 1
diag_source_hi:
    .res 1

.segment "GEOASM"

.import kernal_chrout

; diag_format_error - Format a compiler error record.
; Inputs: A = error code, X/Y = source-line pointer. Outputs: diag_record.
; Side effects: replaces current diagnostic. Clobbers: A. Flags: C clear.
; Zero page: none.
.export diag_format_error
diag_format_error:
    pha
    lda #DIAG_ERROR
    sta diag_record
    pla
    jmp _diag_store_record

; diag_format_warning - Format a non-fatal compiler warning record.
; Inputs: A = warning code, X/Y = source-line pointer. Outputs: diag_record.
; Side effects: replaces current diagnostic. Clobbers: A. Flags: C clear.
; Zero page: none.
.export diag_format_warning
diag_format_warning:
    pha
    lda #DIAG_WARNING
    sta diag_record
    pla

_diag_store_record:
    sta diag_record+1
    stx diag_record+2
    sty diag_record+3
    lda #0
    sta diag_record+4
    sta diag_context_length
    clc
    rts

; diag_format_source_context - Copy bounded source text around an error cursor.
; Inputs: A = cursor offset, X/Y = NUL-terminated source pointer.
; Outputs: diag_context_buffer/length and cursor in diag_record+4.
; Side effects: patches local load operand. Clobbers: A, X, Y.
; Flags: C clear. Zero page: none.
.export diag_format_source_context
diag_format_source_context:
    sta diag_record+4
    stx zp_src
    sty zp_src+1
    ldy #0
@copy:
    cpy #DIAG_CONTEXT_MAX
    beq @done
    lda (zp_src), y
    beq @done
    sta diag_context_buffer, y
    iny
    bne @copy
@done:
    sty diag_context_length
    clc
    rts

; diag_print_error - Commit the current formatted diagnostic to output.
; Inputs: diag_record/context populated. Outputs: "E/Wxx context" on CHROUT;
; print count advanced.
; Side effects: emits one output line. Clobbers: A, X. Flags: C clear.
; Zero page: none.
.export diag_print_error
diag_print_error:
    lda diag_record
    beq @error
    lda #'W'
    bne @severity
@error:
    lda #'E'
@severity:
    jsr _diag_append_output
    lda diag_record+1
    lsr
    lsr
    lsr
    lsr
    jsr _diag_append_hex
    lda diag_record+1
    and #$0F
    jsr _diag_append_hex
    lda #' '
    jsr _diag_append_output
    ldx #0
@context:
    cpx diag_context_length
    bcs @newline
    lda diag_context_buffer, x
    jsr _diag_append_output
    inx
    bne @context
@newline:
    lda #$0D
    jsr _diag_append_output
    inc diag_print_count
    clc
    rts

_diag_append_hex:
    cmp #10
    bcc @digit
    clc
    adc #'A'-10
    bne _diag_append_output
@digit:
    clc
    adc #'0'

_diag_append_output:
    jsr kernal_chrout
    rts

; diag_error_from_kernal - Translate KERNAL status into compiler error codes.
; Inputs: A = KERNAL error number, C = KERNAL failure flag.
; Outputs: A = Compiler 2 error code. Side effects: none. Clobbers: A.
; Flags: C clear for no KERNAL error, set for translated error. Zero page: none.
.export diag_error_from_kernal
diag_error_from_kernal:
    bcc @ok
    cmp #$04
    beq @file_not_found
    cmp #$05
    beq @device_not_present
    cmp #$06
    beq @not_input_file
@unknown:
    lda #ERR_FILE_OPEN
    sec
    rts
@file_not_found:
    lda #ERR_FILE_NOT_FOUND
    sec
    rts
@device_not_present:
    lda #ERR_DEVICE_NOT_PRESENT
    sec
    rts
@not_input_file:
    lda #ERR_NOT_INPUT_FILE
    sec
    rts
@ok:
    lda #ERR_OK
    clc
    rts
