; src/runtime/runtime_io.asm
; Typed, bank-safe runtime file and channel I/O.
;
; Numeric expressions reach command lowering as FLOAT/INT1/INT2/INT3. They
; must pass math_to_arg_byte before becoming any arg-byte field below.
; Arg-byte is an unsigned command-storage domain, not the signed INT1 type.
;
; RL (12): "RL", name:u16, length/device/secondary:arg-byte, mode:u8,
;          address:u16, reserved:u16.
; RS (11): "RS", name:u16, length/device/secondary:arg-byte,
;          start:u16, end:u16 (exclusive). For language SAVE the start/end
;          range is the CPU workspace that receives emitted format bytes.
; RO (8):  "RO", logical/device/secondary/length:arg-byte, name:u16.
; RC/RI (3): magic plus logical:arg-byte.
; RW (4): "RW", logical:arg-byte, value:arg-byte.
;
; Language SAVE emits token-class format bytes (C2-only > Plus/4 3.5 > V2)
; for the published program, materializes them into the RS workspace, then
; calls KERNAL SAVE. Language VERIFY compares pure byte equality against
; exactly those SAVE emission bytes (DESIGN2.md §5).
;
; C=1 rejects malformed records or propagates a KERNAL failure. All external
; I/O traverses resident kernal_bridge entries.

.include "common/zp.inc"
.include "common/constants.asm"
.include "program_formats.inc"

.import kernal_setlfs, kernal_setnam, kernal_open, kernal_close
.import kernal_chkin, kernal_chkout, kernal_clrchn, kernal_chrin, kernal_chrout
.import kernal_load, kernal_save
.import arena_select_page
.import program_select_save_format
.import program_encode_stock
.import program_encode_basic35
.import program_encode_extended
.import __program_store_published

.segment "BSS"
rio_request:       .res 2
rio_name:          .res 2
rio_length:        .res 1
rio_logical:       .res 1
rio_device:        .res 1
rio_secondary:     .res 1
rio_mode:          .res 1
rio_address:       .res 2
rio_end:           .res 2
rio_saved_byte:    .res 1
rio_saved_status:  .res 1
rio_save_start:    .res 2
rio_emit_desc:     .res 2
rio_emit_length:   .res 2
rio_emit_index:    .res 2
rio_emit_arena:    .res 1
rio_emit_generation: .res 1
rio_emit_start_page: .res 1
rio_emit_cursor:   .res 2
rio_format:        .res 1

.segment "RUNTIME"

.macro jcs target
    bcc *+5
    jmp target
.endmacro
.macro jcc target
    bcs *+5
    jmp target
.endmacro
.macro jne target
    beq *+5
    jmp target
.endmacro
.macro jeq target
    bne *+5
    jmp target
.endmacro

; Common RL/RS filename fields at offsets 2..6.
.proc rio_parse_name
    stx rio_request
    sty rio_request+1
    stx zp_src
    sty zp_src+1
    ldy #2
    lda (zp_src), y
    sta rio_name
    iny
    lda (zp_src), y
    sta rio_name+1
    iny
    lda (zp_src), y
    beq @error
    sta rio_length
    iny
    lda (zp_src), y
    sta rio_device
    iny
    lda (zp_src), y
    sta rio_secondary
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

.proc rio_set_name_and_lfs
    lda rio_length
    ldx rio_name
    ldy rio_name+1
    jsr kernal_setnam
    jcs @error
    lda rio_logical
    ldx rio_device
    ldy rio_secondary
    jmp kernal_setlfs
@error:
    sec
    rts
.endproc

.proc rio_parse_load
    sta rio_saved_status
    stx rio_request
    sty rio_request+1
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #'R'
    bne @error
    iny
    lda (zp_src), y
    cmp #'L'
    bne @error
    ldx rio_request
    ldy rio_request+1
    jsr rio_parse_name
    jcs @error
    lda rio_request
    sta zp_src
    lda rio_request+1
    sta zp_src+1
    ldy #7
    lda (zp_src), y
    cmp rio_saved_status
    bne @error
    sta rio_mode
    iny
    lda (zp_src), y
    sta rio_address
    iny
    lda (zp_src), y
    sta rio_address+1
    iny
    lda (zp_src), y
    iny
    ora (zp_src), y
    bne @error
    lda #1
    sta rio_logical
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

.export rio_load
rio_load:
    lda #0
    jsr rio_parse_load
    jcs @error
    jsr rio_set_name_and_lfs
    jcs @error
    lda #0
    ldx rio_address
    ldy rio_address+1
    jmp kernal_load
@error:
    sec
    rts

; Encode the published program into the token-class SAVE format.
; Outputs: X/Y = encoded PS descriptor, rio_format set, C=error.
.proc rio_encode_published
    ldx #<__program_store_published
    ldy #>__program_store_published
    jsr program_select_save_format
    jcs @error
    sta rio_format
    ldx #<__program_store_published
    ldy #>__program_store_published
    lda rio_format
    cmp #SAVE_FORMAT_V2
    beq @encode_v2
    cmp #SAVE_FORMAT_BASICV35
    beq @encode_35
    cmp #SAVE_FORMAT_C2P1
    beq @encode_c2
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
@encode_v2:
    jsr program_encode_stock
    rts
@encode_35:
    jsr program_encode_basic35
    rts
@encode_c2:
    jsr program_encode_extended
    rts
@error:
    sec
    rts
.endproc

; Probe an encoded PS descriptor in X/Y into rio_emit_* fields.
.proc rio_probe_emit
    stx rio_emit_desc
    sty rio_emit_desc+1
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #'P'
    bne @error
    iny
    lda (zp_src), y
    cmp #'S'
    bne @error
    iny
    lda (zp_src), y
    sta rio_emit_length
    iny
    lda (zp_src), y
    sta rio_emit_length+1
    iny
    lda (zp_src), y
    sta rio_emit_arena
    iny
    lda (zp_src), y
    sta rio_emit_generation
    iny
    lda (zp_src), y
    sta rio_emit_start_page
    iny
    lda (zp_src), y
    bne @error
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Materialize the probed emit stream into CPU memory at rio_save_start.
; Requires [rio_save_start, rio_end) to hold the full emission.
.proc rio_materialize_emit
    lda rio_end+1
    cmp rio_save_start+1
    bcc @to_error
    bne @span
    lda rio_end
    cmp rio_save_start
    bcc @to_error
    beq @to_error
    jmp @span
@to_error:
    jmp @error
@span:
    sec
    lda rio_end
    sbc rio_save_start
    sta rio_emit_cursor
    lda rio_end+1
    sbc rio_save_start+1
    sta rio_emit_cursor+1
    lda rio_emit_cursor+1
    cmp rio_emit_length+1
    bcc @to_error
    bne @fit
    lda rio_emit_cursor
    cmp rio_emit_length
    bcc @to_error
@fit:
    lda rio_save_start
    sta rio_emit_cursor
    lda rio_save_start+1
    sta rio_emit_cursor+1
    lda #$00
    sta rio_emit_index
    sta rio_emit_index+1
@byte:
    lda rio_emit_index+1
    cmp rio_emit_length+1
    bne @more
    lda rio_emit_index
    cmp rio_emit_length
    beq @done
@more:
    lda rio_emit_index+1
    clc
    adc rio_emit_start_page
    bcs @to_error
    ldx rio_emit_arena
    ldy rio_emit_generation
    jsr arena_select_page
    bcs @to_error
    ldy rio_emit_index
    lda $DE00, y
    sta rio_saved_byte
    lda rio_emit_cursor
    sta zp_src
    lda rio_emit_cursor+1
    sta zp_src+1
    ldy #0
    lda rio_saved_byte
    sta (zp_src), y
    inc rio_emit_cursor
    bne :+
    inc rio_emit_cursor+1
:
    inc rio_emit_index
    bne @byte
    inc rio_emit_index+1
    jmp @byte
@done:
    ; Exclusive end = start + length.
    clc
    lda rio_save_start
    adc rio_emit_length
    sta rio_end
    lda rio_save_start+1
    adc rio_emit_length+1
    sta rio_end+1
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Compare probed emit stream to CPU memory at rio_address for pure equality.
.proc rio_compare_emit
    lda #$00
    sta rio_emit_index
    sta rio_emit_index+1
    lda rio_address
    sta rio_emit_cursor
    lda rio_address+1
    sta rio_emit_cursor+1
@byte:
    lda rio_emit_index+1
    cmp rio_emit_length+1
    bne @more
    lda rio_emit_index
    cmp rio_emit_length
    beq @match
@more:
    lda rio_emit_index+1
    clc
    adc rio_emit_start_page
    bcs @cmp_error
    ldx rio_emit_arena
    ldy rio_emit_generation
    jsr arena_select_page
    bcs @cmp_error
    ldy rio_emit_index
    lda $DE00, y
    sta rio_saved_byte
    lda rio_emit_cursor
    sta zp_src
    lda rio_emit_cursor+1
    sta zp_src+1
    ldy #0
    lda (zp_src), y
    cmp rio_saved_byte
    bne @mismatch
    inc rio_emit_cursor
    bne :+
    inc rio_emit_cursor+1
:
    inc rio_emit_index
    bne @byte
    inc rio_emit_index+1
    jmp @byte
@match:
    clc
    rts
@mismatch:
    lda #ERR_VERIFY
    sec
    rts
@cmp_error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Language VERIFY: pure byte equality vs what SAVE would write.
.export rio_verify
rio_verify:
    lda #1
    jsr rio_parse_load
    jcs @error
    jsr rio_encode_published
    jcs @error
    jsr rio_probe_emit
    jcs @error
    jsr rio_compare_emit
    rts
@error:
    sec
    rts

; Language SAVE: emit token-class format bytes then KERNAL SAVE.
.export rio_save
rio_save:
    stx rio_request
    sty rio_request+1
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #'R'
    jne @error
    iny
    lda (zp_src), y
    cmp #'S'
    jne @error
    ldx rio_request
    ldy rio_request+1
    jsr rio_parse_name
    jcs @error
    lda rio_request
    sta zp_src
    lda rio_request+1
    sta zp_src+1
    ldy #7
    lda (zp_src), y
    sta rio_save_start
    iny
    lda (zp_src), y
    sta rio_save_start+1
    iny
    lda (zp_src), y
    sta rio_end
    iny
    lda (zp_src), y
    sta rio_end+1
    lda rio_end+1
    cmp rio_save_start+1
    jcc @error
    bne @range_ok
    lda rio_end
    cmp rio_save_start
    jcc @error
    jeq @error
@range_ok:
    jsr rio_encode_published
    jcs @error
    jsr rio_probe_emit
    jcs @error
    jsr rio_materialize_emit
    jcs @error
    lda #1
    sta rio_logical
    jsr rio_set_name_and_lfs
    jcs @error
    ; KERNAL SAVE requires A = ZP pointer to start address.
    lda rio_save_start
    sta zp_src
    lda rio_save_start+1
    sta zp_src+1
    lda #<zp_src
    ldx rio_end
    ldy rio_end+1
    jmp kernal_save
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

.export rio_open
rio_open:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #'R'
    bne @error
    iny
    lda (zp_src), y
    cmp #'O'
    bne @error
    iny
    lda (zp_src), y
    sta rio_logical
    iny
    lda (zp_src), y
    sta rio_device
    iny
    lda (zp_src), y
    sta rio_secondary
    iny
    lda (zp_src), y
    beq @error
    sta rio_length
    iny
    lda (zp_src), y
    sta rio_name
    iny
    lda (zp_src), y
    sta rio_name+1
    jsr rio_set_name_and_lfs
    jcs @error
    jmp kernal_open
@error:
    jmp rio_record_error

; Parse RC/RI. A is the second magic byte.
.proc rio_parse_channel
    sta rio_saved_status
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #'R'
    bne @error
    iny
    lda (zp_src), y
    cmp rio_saved_status
    bne @error
    iny
    lda (zp_src), y
    sta rio_logical
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

.export rio_close
rio_close:
    lda #'C'
    jsr rio_parse_channel
    bcs rio_record_error
    lda rio_logical
    jmp kernal_close

.export rio_chrin
rio_chrin:
    lda #'I'
    jsr rio_parse_channel
    bcs rio_record_error
    ldx rio_logical
    jsr kernal_chkin
    jcs @error
    jsr kernal_chrin
    sta rio_saved_byte
    bcs @input_error
    jsr kernal_clrchn
    jcs @error
    lda rio_saved_byte
    clc
    rts
@input_error:
    ; CHRIN's error is primary, but the selected channel must still be
    ; released before returning to the caller.
    jsr kernal_clrchn
    lda rio_saved_byte
    sec
    rts
@error:
    sec
    rts

.export rio_chrout
rio_chrout:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #'R'
    bne rio_record_error
    iny
    lda (zp_src), y
    cmp #'W'
    bne rio_record_error
    iny
    lda (zp_src), y
    tax
    iny
    lda (zp_src), y
    sta rio_saved_byte
    jsr kernal_chkout
    jcs @error
    lda rio_saved_byte
    jsr kernal_chrout
    jcs @restore_error
    jsr kernal_clrchn
    rts
@restore_error:
    sta rio_saved_status
    php
    jsr kernal_clrchn
    plp
    lda rio_saved_status
@error:
    sec
    rts

rio_record_error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

.export rio_clrchn
rio_clrchn:
    jmp kernal_clrchn
