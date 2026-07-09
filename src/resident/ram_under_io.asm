; src/resident/ram_under_io.asm
; RAM-under-I/O gate helpers for accessing the $D000-$DFFF hidden RAM window.

.include "common/zp.inc"
.include "common/constants.asm"

.segment "RESIDENT"

; Select all-RAM mapping and mask IRQs.
.export ram_under_io_enter
ram_under_io_enter:
    sei
    lda #$2F
    sta $00
    lda #CPU_PORT_ALL_RAM
    sta $01
    rts

; Restore the canonical Compiler 2 mapping and IRQ state expected by tests.
.export ram_under_io_exit
ram_under_io_exit:
    lda #$2F
    sta $00
    lda #CPU_PORT_CANONICAL
    sta $01
    cli
    rts

; Copy A bytes from (zp_src) to X/Y destination under I/O.
.export ram_under_io_copy_in
ram_under_io_copy_in:
    sta zp_tmp1
    stx zp_tmptr
    sty zp_tmptr+1
    jsr ram_under_io_enter
    ldy #0
@copy_in_loop:
    cpy zp_tmp1
    beq @copy_in_done
    lda (zp_src),y
    sta (zp_tmptr),y
    iny
    bne @copy_in_loop
@copy_in_done:
    jsr ram_under_io_exit
    rts

; Copy A bytes from X/Y source under I/O to (zp_dest).
.export ram_under_io_copy_out
ram_under_io_copy_out:
    sta zp_tmp1
    stx zp_tmptr
    sty zp_tmptr+1
    jsr ram_under_io_enter
    ldy #0
@copy_out_loop:
    cpy zp_tmp1
    beq @copy_out_done
    lda (zp_tmptr),y
    sta (zp_dest),y
    iny
    bne @copy_out_loop
@copy_out_done:
    jsr ram_under_io_exit
    rts
