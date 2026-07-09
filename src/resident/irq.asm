; src/resident/irq.asm
; Pinned IRQ helper with bounded state save/restore.
;
; SKELETON (design audit 2026-07-09): NMI RESTORE distrust path is missing
; (DESIGN2 §8.5 / §9.3). IRQ path is partial and kept for structure.

.include "common/zp.inc"
.include "common/constants.asm"

.segment "RESIDENT"

KERNAL_IO_PORT = $36
KERNAL_UDTIM = $FFEA
KERNAL_SCNKEY = $FF9F

.segment "BSS"
irq_saved_port: .res 1

.segment "RESIDENT"

.export irq_entry
.export nmi_entry
.export irq_update_jiffy
.export irq_cursor_blink
.export irq_scan_keyboard
.export irq_restore_mapping

; nmi_entry - RESTORE key / NMI distrust path (SKELETON)
; Design: invalidate CONT, mark compile fully dirty, re-probe devices,
; republish expansion profile or enter minimal editor; never resume code.
nmi_entry:
    rti

irq_entry:
    pha
    txa
    pha
    tya
    pha
    php
    lda $01
    pha
    lda #KERNAL_IO_PORT
    sta $01
    jsr irq_update_jiffy
    jsr irq_cursor_blink
    jsr irq_scan_keyboard
    pla
    jsr irq_restore_mapping
    plp
    pla
    tay
    pla
    tax
    pla
    rti

irq_update_jiffy:
    jsr KERNAL_UDTIM
    rts

irq_cursor_blink:
    lda zp_crsr_vis
    eor #$01
    sta zp_crsr_vis
    rts

irq_scan_keyboard:
    jsr KERNAL_SCNKEY
    rts

irq_restore_mapping:
    sta irq_saved_port
    lda #$2F
    sta $00
    lda #KERNAL_IO_PORT
    sta $01
    lda irq_saved_port
    sta $01
    rts
