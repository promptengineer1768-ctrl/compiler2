; src/resident/irq.asm
; Pinned IRQ helper and RESTORE/NMI distrust path (DESIGN2 §8.5, §9.3).
;
; IRQ never enters expansion-native code. NMI invalidates CONT, marks compile
; state fully dirty, re-probes devices, and re-enters the editor or the
; minimal degraded editor without resuming the interrupted program.

.include "common/zp.inc"
.include "common/constants.asm"

.import detect_georam
.import resident_enter_degraded
.import resident_main
.import ctrl_sp
.import incremental_dirty_mask
.import incremental_published_valid
.import screen_cursor_irq_service

.segment "RESIDENT"

KERNAL_IO_PORT = $36
KERNAL_UDTIM = $FFEA
KERNAL_SCNKEY = $FF9F
CIA1_ICR = $DC0D
CIA2_ICR = $DD0D
KERNAL_IRQ_RETURN = $EA7E

.segment "BSS"
irq_saved_port: .res 1

.segment "RESIDENT"

.export irq_entry
.export nmi_entry
.export irq_update_jiffy
.export irq_cursor_blink
.export irq_scan_keyboard
.export irq_restore_mapping
.export nmi_invalidate_cont
.export nmi_mark_compile_dirty
.export irq_kernal_entry

; irq_kernal_entry - KERNAL CINV-compatible IRQ entry.
; The ROM preamble at $FF48 has already saved A/X/Y before jumping through
; $0314. Service the project IRQ without another frame, then use the stock
; $EA7E tail to pop those registers and RTI. This entry is distinct from the
; raw RAM hardware-vector irq_entry below.
irq_kernal_entry:
    lda #KERNAL_IO_PORT
    sta $01
    lda CIA1_ICR
    jsr irq_update_jiffy
    jsr irq_cursor_blink
    jsr irq_scan_keyboard
    jmp KERNAL_IRQ_RETURN

; nmi_entry - RESTORE key / NMI distrust path
; Does not resume interrupted code. Invalidates CONT and continuation frames,
; marks compile state fully dirty, acks CIA NMI sources, re-probes expansion,
; and re-enters the normal or minimal (error+QUIT) editor.
; Inputs: hardware NMI frame (discarded).
; Outputs: never returns to the interrupted PC.
; Clobbers: A, X, Y, stack, mapping.
nmi_entry:
    ; Distrust the interrupted stack and program state completely.
    sei
    cld
    ldx #$FF
    txs
    lda #CPU_PORT_CANONICAL
    sta $01
    ; Acknowledge CIA NMI sources so RESTORE does not re-fire immediately.
    lda CIA1_ICR
    lda CIA2_ICR
    jsr nmi_invalidate_cont
    jsr nmi_mark_compile_dirty
    ; Re-probe devices from resident code only (no expansion-native calls).
    jsr detect_georam
    bcs @no_store
    ; Store still valid: stay in full editor with refreshed profile.
    jmp resident_main
@no_store:
    ; No usable expansion store: minimal resident editor (error + QUIT only).
    jmp resident_enter_degraded

; nmi_invalidate_cont - Zero CONT/continuation state without geoRAM code.
; Writes the same fields as control-stack reset using resident-safe BSS/ZP.
; Input: none. Output: C=0. Clobbers: A.
nmi_invalidate_cont:
    lda #0
    sta zp_stop_flag
    sta zp_cont_handle
    sta zp_cont_handle+1
    sta ctrl_sp
    clc
    rts

; nmi_mark_compile_dirty - Mark compile publication fully untrusted.
; Input: none. Output: C=0. Clobbers: A.
; Side effects: incremental_dirty_mask=$FF, incremental_published_valid=0.
nmi_mark_compile_dirty:
    lda #$FF
    sta incremental_dirty_mask
    lda #0
    sta incremental_published_valid
    clc
    rts

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
    ; RAM hardware vectors bypass the KERNAL IRQ dispatcher while $01=$35,
    ; so acknowledge the CIA source here before servicing it. Without this
    ; read, Timer A remains asserted and the CPU immediately re-enters IRQ,
    ; starving the resident foreground loop.
    lda CIA1_ICR
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

; irq_cursor_blink - Reverse-video blink at the project cursor cell.
; Does not toggle zp_crsr_vis (that flag is the enable latch). Screen paint
; and saved-character restore live in screen_cursor_irq_service.
; Clobbers: A, X, Y.
irq_cursor_blink:
    jmp screen_cursor_irq_service

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
