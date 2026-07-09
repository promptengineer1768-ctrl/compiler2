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
;          start:u16, end:u16 (exclusive).
; RO (8):  "RO", logical/device/secondary/length:arg-byte, name:u16.
; RC/RI (3): magic plus logical:arg-byte.
; RW (4): "RW", logical:arg-byte, value:arg-byte.
;
; C=1 rejects malformed records or propagates a KERNAL failure. All external
; I/O traverses resident kernal_bridge entries.

.include "common/zp.inc"
.include "common/constants.asm"

.import kernal_setlfs, kernal_setnam, kernal_open, kernal_close
.import kernal_chkin, kernal_chkout, kernal_clrchn, kernal_chrin, kernal_chrout
.import kernal_load, kernal_save

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

.segment "RUNTIME"

.macro jcs target
    bcc *+5
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

.export rio_verify
rio_verify:
    lda #1
    jsr rio_parse_load
    jcs @error
    jsr rio_set_name_and_lfs
    jcs @error
    lda #1
    ldx rio_address
    ldy rio_address+1
    jmp kernal_load
@error:
    sec
    rts

.export rio_save
rio_save:
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
    cmp #'S'
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
    bcc @error
    bne @range_ok
    lda rio_end
    cmp rio_save_start
    bcc @error
    beq @error
@range_ok:
    lda #1
    sta rio_logical
    jsr rio_set_name_and_lfs
    jcs @error
    lda #<rio_save_start
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
    jsr kernal_clrchn
    jcs @error
    lda rio_saved_byte
    clc
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
    php
    jsr kernal_clrchn
    plp
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
