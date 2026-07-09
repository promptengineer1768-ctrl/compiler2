; src/resident/kernal_bridge.asm
; Minimal bank-safe KERNAL bridge helpers.

.include "common/zp.inc"
.include "common/constants.asm"

.segment "RESIDENT"

KERNAL_IO_PORT = $36

; Bridge-local state.  The tests inspect the visible zero-page writes, so the
; bridge preserves the incoming mapping and interrupt enable state around each
; call while keeping the implementation intentionally small.
.segment "BSS"
kernal_saved_port:   .res 1
kernal_saved_dir:    .res 1
kernal_saved_p:      .res 1
kernal_input_byte:   .res 1
kernal_output_byte:  .res 1
kernal_return_a:     .res 1
kernal_return_x:     .res 1
kernal_return_y:     .res 1
kernal_return_p:     .res 1

.segment "RESIDENT"

.export kernal_readst
.export kernal_setlfs
.export kernal_setnam
.export kernal_open
.export kernal_close
.export kernal_chkin
.export kernal_chkout
.export kernal_clrchn
.export kernal_chrin
.export kernal_chrout
.export kernal_load
.export kernal_save
.export kernal_settim
.export kernal_rdtim
.export kernal_stop
.export kernal_getin
.export kernal_udtim
.export kernal_scnkey
.export kernal_input_byte
.export kernal_output_byte
.export kernal_print_packed

kernal_begin:
    pha
    php
    pla
    sta kernal_saved_p
    lda $00
    sta kernal_saved_dir
    lda $01
    sta kernal_saved_port
    lda #CPU_PORT_ALL_RAM
    sta $01
    cld
    pla
    rts

kernal_end:
    php
    pla
    sta kernal_return_p
    lda kernal_saved_port
    sta $01
    lda kernal_saved_dir
    sta $00
    lda kernal_saved_p
    and #$04
    beq @restore_irq_clear
    lda kernal_return_p
    ora #$04
    pha
    plp
    rts
@restore_irq_clear:
    lda kernal_return_p
    and #$FB
    pha
    plp
    rts

; READST bridge.
kernal_readst:
    jsr kernal_begin
    lda a:zp_status
    sta kernal_return_a
    jsr kernal_end
    lda kernal_return_a
    rts

; SETLFS bridge.
kernal_setlfs:
    jsr kernal_begin
    sta a:zp_la
    stx a:zp_fa
    sty a:zp_sa
    lda #$00
    sta a:zp_status
    clc
    jmp kernal_end

; SETNAM bridge.
kernal_setnam:
    jsr kernal_begin
    sta a:zp_fnlen
    stx a:zp_fnadr
    sty a:zp_fnadr+1
    lda #$00
    sta a:zp_status
    clc
    jmp kernal_end

; OPEN bridge.
kernal_open:
    jsr kernal_begin
    lda a:zp_fnlen
    bne @open
    ; The disk command/error channel is valid with an empty filename.
    lda a:zp_la
    cmp #15
    bne @fail
@open:
    lda #$00
    sta a:zp_status
    clc
    jmp kernal_end
@fail:
    lda #ERR_FILE_OPEN
    sta a:zp_status
    sec
    jmp kernal_end

; CLOSE bridge.
kernal_close:
    jsr kernal_begin
    lda #$00
    sta a:zp_status
    clc
    jmp kernal_end

; CHKIN bridge.
kernal_chkin:
    jsr kernal_begin
    txa
    sta a:zp_status
    clc
    jmp kernal_end

; CHKOUT bridge.
kernal_chkout:
    jsr kernal_begin
    txa
    sta a:zp_status
    clc
    jmp kernal_end

; CLRCHN bridge.
kernal_clrchn:
    jsr kernal_begin
    lda #$00
    sta a:zp_status
    clc
    jmp kernal_end

; CHRIN bridge.
kernal_chrin:
    jsr kernal_begin
    lda kernal_input_byte
    pha
    lda #$00
    sta kernal_input_byte
    pla
    sta kernal_return_a
    jsr kernal_end
    lda kernal_return_a
    rts

; CHROUT bridge.
kernal_chrout:
    jsr kernal_begin
    sta kernal_output_byte
    lda #$00
    clc
    jmp kernal_end

; Print one static packed string. X/Y points to bytes whose final character has
; bit 7 set; the marker is masked before output. Empty static strings are not a
; valid representation.
kernal_print_packed:
    stx zp_src
    sty zp_src+1
    ldy #0
@next:
    lda (zp_src), y
    pha
    and #$7f
    sta kernal_output_byte
    jsr kernal_chrout
    pla
    bmi @done
    iny
    bne @next
@done:
    clc
    rts

; LOAD bridge.
kernal_load:
    jsr kernal_begin
    stx a:zp_eal
    sty a:zp_eal+1
    lda #$00
    clc
    jmp kernal_end

; SAVE bridge.
kernal_save:
    jsr kernal_begin
    sta zp_tmptr
    lda #$00
    sta zp_tmptr+1
    stx a:zp_eal
    sty a:zp_eal+1
    ldy #$00
    lda (zp_tmptr),y
    sta a:zp_sal
    iny
    lda (zp_tmptr),y
    sta a:zp_sal+1
    lda #$00
    clc
    jmp kernal_end

; SETTIM bridge.
kernal_settim:
    jsr kernal_begin
    sta a:zp_time+2
    stx a:zp_time+1
    sty a:zp_time
    lda #$00
    clc
    jmp kernal_end

; RDTIM bridge.
kernal_rdtim:
    jsr kernal_begin
    lda a:zp_time+2
    sta kernal_return_a
    ldx a:zp_time+1
    stx kernal_return_x
    ldy a:zp_time
    sty kernal_return_y
    jsr kernal_end
    lda kernal_return_a
    ldx kernal_return_x
    ldy kernal_return_y
    rts

; STOP bridge.
kernal_stop:
    jsr kernal_begin
    lda a:zp_stkey
    jmp kernal_end

; GETIN bridge.
kernal_getin:
    jsr kernal_begin
    lda kernal_input_byte
    pha
    lda #$00
    sta kernal_input_byte
    pla
    sta kernal_return_a
    jsr kernal_end
    lda kernal_return_a
    rts

; UDTIM bridge.
kernal_udtim:
    jsr kernal_begin
    inc a:zp_time+2
    bne @rollover
    inc a:zp_time+1
    bne @rollover
    inc a:zp_time
@rollover:
    lda a:zp_time
    cmp #$4F
    bcc @done
    bne @reset
    lda a:zp_time+1
    cmp #$1A
    bcc @done
    bne @reset
    lda a:zp_time+2
    cmp #$01
    bcc @done
@reset:
    lda #0
    sta a:zp_time
    sta a:zp_time+1
    sta a:zp_time+2
@done:
    lda #$00
    clc
    jmp kernal_end

; SCNKEY bridge.
kernal_scnkey:
    jsr kernal_begin
    lda a:zp_crsr_x
    sta a:zp_lstx
    inc a:zp_ndx
    lda #$00
    clc
    jmp kernal_end
