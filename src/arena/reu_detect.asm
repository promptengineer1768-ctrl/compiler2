; src/arena/reu_detect.asm
; Non-destructive REU (REC $DF00-$DF0A) detection per REU_DESIGN.md §3.
;
; Proves at least 512 KiB of non-aliased REU memory, restores every REU byte
; and REC register touched by the probe, and publishes capacity + fingerprint.

.include "common/zp.inc"
.include "common/constants.asm"

.segment "RESIDENT"

; REC registers
REU_STATUS  = $DF00
REU_COMMAND = $DF01
REU_C64_LO  = $DF02
REU_C64_HI  = $DF03
REU_REU_LO  = $DF04
REU_REU_HI  = $DF05
REU_REU_BNK = $DF06
REU_LEN_LO  = $DF07
REU_LEN_HI  = $DF08
REU_IRQMASK = $DF09
REU_ADDRCTL = $DF0A

; Command: execute + transfer mode
REU_CMD_TO_REU   = $80        ; C64 -> REU
REU_CMD_FROM_REU = $81        ; REU -> C64
REU_IRQ_DISABLED = $1F
REU_ADDR_BOTH_INC = $00

; Minimum capacity: 512 KiB = 8 * 64 KiB banks
DETECT_REU_MIN_BANKS = 8
DETECT_REU_MIN_KIB_LO = $00
DETECT_REU_MIN_KIB_HI = $02   ; 512 = $0200 KiB

.segment "BSS"
reu_saved_port:         .res 1
reu_saved_command:      .res 1
reu_saved_c64_lo:       .res 1
reu_saved_c64_hi:       .res 1
reu_saved_reu_lo:       .res 1
reu_saved_reu_hi:       .res 1
reu_saved_reu_bnk:      .res 1
reu_saved_len_lo:       .res 1
reu_saved_len_hi:       .res 1
reu_saved_irqmask:      .res 1
reu_saved_addrctl:      .res 1
; Saved original REU bytes at three probe sites
reu_saved_byte0:        .res 1
reu_saved_byte1:        .res 1
reu_saved_byte2:        .res 1
; Transfer scratch (must live in normal RAM, not I/O)
reu_xfer_byte:          .res 1
.export detect_reu_capacity_banks
detect_reu_capacity_banks:
    .res 1
.export detect_reu_capacity_kib_lo
detect_reu_capacity_kib_lo:
    .res 1
.export detect_reu_capacity_kib_hi
detect_reu_capacity_kib_hi:
    .res 1
.export detect_reu_fingerprint
detect_reu_fingerprint:
    .res 1
.export detect_reu_valid
detect_reu_valid:
    .res 1

.segment "RESIDENT"

.export detect_reu
.export detect_reu_save_state
.export detect_reu_restore_state
.export detect_reu_check_minimum

; ---------------------------------------------------------------------------
; detect_reu_save_state
; Save CPU port, processor status bits we care about, and REC registers.
; Clobbers: A
; ---------------------------------------------------------------------------
detect_reu_save_state:
    lda $01
    sta reu_saved_port
    lda REU_COMMAND
    sta reu_saved_command
    lda REU_C64_LO
    sta reu_saved_c64_lo
    lda REU_C64_HI
    sta reu_saved_c64_hi
    lda REU_REU_LO
    sta reu_saved_reu_lo
    lda REU_REU_HI
    sta reu_saved_reu_hi
    lda REU_REU_BNK
    sta reu_saved_reu_bnk
    lda REU_LEN_LO
    sta reu_saved_len_lo
    lda REU_LEN_HI
    sta reu_saved_len_hi
    lda REU_IRQMASK
    sta reu_saved_irqmask
    lda REU_ADDRCTL
    sta reu_saved_addrctl
    rts

; ---------------------------------------------------------------------------
; detect_reu_restore_state
; Restore REC registers and CPU port. Does not restore REU memory bytes
; (those are restored by the probe itself before calling this).
; Preserves flags (including carry used as the detect result).
; Clobbers: A
; ---------------------------------------------------------------------------
detect_reu_restore_state:
    php
    lda reu_saved_command
    sta REU_COMMAND
    lda reu_saved_c64_lo
    sta REU_C64_LO
    lda reu_saved_c64_hi
    sta REU_C64_HI
    lda reu_saved_reu_lo
    sta REU_REU_LO
    lda reu_saved_reu_hi
    sta REU_REU_HI
    lda reu_saved_reu_bnk
    sta REU_REU_BNK
    lda reu_saved_len_lo
    sta REU_LEN_LO
    lda reu_saved_len_hi
    sta REU_LEN_HI
    lda reu_saved_irqmask
    sta REU_IRQMASK
    lda reu_saved_addrctl
    sta REU_ADDRCTL
    lda reu_saved_port
    sta $01
    plp
    rts

; ---------------------------------------------------------------------------
; detect_reu_init_rec - known synchronous, no-autoload, no-interrupt REC state
; Clobbers: A
; ---------------------------------------------------------------------------
detect_reu_init_rec:
    lda #REU_IRQ_DISABLED
    sta REU_IRQMASK
    lda #REU_ADDR_BOTH_INC
    sta REU_ADDRCTL
    lda #$00
    sta REU_COMMAND
    rts

; ---------------------------------------------------------------------------
; detect_reu_dma_byte
; Transfer one byte between reu_xfer_byte and the REU address in
; (zp_tmp1=lo, zp_tmp2=hi, zp_tmp3=bank). A = command (TO/FROM REU).
; Output: C=0 transfer completed (status EOB observed), C=1 no REC response.
; Clobbers: A, X, Y
; ---------------------------------------------------------------------------
detect_reu_dma_byte:
    pha
    ; For REU->C64, poison the scratch so a no-op DMA cannot look successful.
    pla
    pha
    cmp #REU_CMD_FROM_REU
    bne @program
    lda #$00
    sta reu_xfer_byte
@program:
    lda #<reu_xfer_byte
    sta REU_C64_LO
    lda #>reu_xfer_byte
    sta REU_C64_HI
    lda zp_tmp1
    sta REU_REU_LO
    lda zp_tmp2
    sta REU_REU_HI
    lda zp_tmp3
    sta REU_REU_BNK
    lda #1
    sta REU_LEN_LO
    lda #0
    sta REU_LEN_HI
    lda #REU_ADDR_BOTH_INC
    sta REU_ADDRCTL
    lda #REU_IRQ_DISABLED
    sta REU_IRQMASK
    pla
    sta REU_COMMAND
    ; Require end-of-block status so a missing REC cannot fake success via RAM.
    lda REU_STATUS
    and #$40
    beq @no_rec
    clc
    rts
@no_rec:
    sec
    rts

; Set probe address site index X (0,1,2) into zp_tmp1/2/3.
; Site 0: bank 0, addr $0000
; Site 1: bank 4, addr $0000  (256 KiB)
; Site 2: bank 7, addr $FF00  (near end of 512 KiB)
detect_reu_set_site:
    cpx #0
    beq @site0
    cpx #1
    beq @site1
    ; site 2
    lda #$00
    sta zp_tmp1
    lda #$FF
    sta zp_tmp2
    lda #7
    sta zp_tmp3
    rts
@site0:
    lda #$00
    sta zp_tmp1
    sta zp_tmp2
    sta zp_tmp3
    rts
@site1:
    lda #$00
    sta zp_tmp1
    sta zp_tmp2
    lda #4
    sta zp_tmp3
    rts

; ---------------------------------------------------------------------------
; detect_reu_check_minimum
; Input: detect_reu_capacity_banks filled
; Output: C=0 if >= 8 banks (512 KiB), C=1 otherwise
; ---------------------------------------------------------------------------
detect_reu_check_minimum:
    lda detect_reu_capacity_banks
    cmp #DETECT_REU_MIN_BANKS
    bcc @fail
    clc
    rts
@fail:
    sec
    rts

; ---------------------------------------------------------------------------
; detect_reu - full non-destructive probe
; Output: C=0 present+>=512KiB, C=1 absent/undersized/failed restore
;         On success: capacity banks/kib and fingerprint published
; Clobbers: A, X, Y
; ---------------------------------------------------------------------------
detect_reu:
    lda #0
    sta detect_reu_valid
    sta detect_reu_capacity_banks
    sta detect_reu_capacity_kib_lo
    sta detect_reu_capacity_kib_hi
    sta detect_reu_fingerprint

    jsr detect_reu_save_state
    lda #CPU_PORT_CANONICAL
    sta $01
    jsr detect_reu_init_rec

    ; --- Save original REU bytes at three separated sites ---
    ldx #0
@save_loop:
    txa
    pha
    jsr detect_reu_set_site
    lda #REU_CMD_FROM_REU
    jsr detect_reu_dma_byte
    bcs @fail_restore_pop
    pla
    tax
    lda reu_xfer_byte
    cpx #0
    bne :+
    sta reu_saved_byte0
    jmp @save_next
:
    cpx #1
    bne :+
    sta reu_saved_byte1
    jmp @save_next
:
    sta reu_saved_byte2
@save_next:
    inx
    cpx #3
    bcc @save_loop
    jmp @patterns

@fail_restore_pop:
    pla
    jmp @fail_restore

@patterns:
    ; --- Write distinct patterns ---
    ; site0 = $A5, site1 = $5A, site2 = $C3
    ldx #0
    lda #$A5
    jsr detect_reu_write_pattern
    bcs @fail_restore
    ldx #1
    lda #$5A
    jsr detect_reu_write_pattern
    bcs @fail_restore
    ldx #2
    lda #$C3
    jsr detect_reu_write_pattern
    bcs @fail_restore

    ; --- Verify patterns persist and do not alias ---
    ldx #0
    lda #$A5
    jsr detect_reu_verify_pattern
    bcs @fail_restore
    ldx #1
    lda #$5A
    jsr detect_reu_verify_pattern
    bcs @fail_restore
    ldx #2
    lda #$C3
    jsr detect_reu_verify_pattern
    bcs @fail_restore

    ; Cross-check: rewrite site0 and confirm site1/site2 unchanged
    ldx #0
    lda #$3C
    jsr detect_reu_write_pattern
    bcs @fail_restore
    ldx #1
    lda #$5A
    jsr detect_reu_verify_pattern
    bcs @fail_restore
    ldx #2
    lda #$C3
    jsr detect_reu_verify_pattern
    bcs @fail_restore

    ; --- Restore original REU bytes ---
    jsr detect_reu_restore_probe_bytes
    bcs @fail_after_restore

    ; Proven contiguous 512 KiB (8 banks)
    lda #DETECT_REU_MIN_BANKS
    sta detect_reu_capacity_banks
    lda #DETECT_REU_MIN_KIB_LO
    sta detect_reu_capacity_kib_lo
    lda #DETECT_REU_MIN_KIB_HI
    sta detect_reu_capacity_kib_hi
    ; Fingerprint mixes capacity with a probe-signature constant
    lda detect_reu_capacity_banks
    eor detect_reu_capacity_kib_hi
    eor #$A5
    eor #$5A
    eor #$C3
    sta detect_reu_fingerprint
    lda #1
    sta detect_reu_valid

    jsr detect_reu_restore_state
    clc
    rts

@fail_restore:
    jsr detect_reu_restore_probe_bytes
@fail_after_restore:
    lda #0
    sta detect_reu_valid
    sta detect_reu_capacity_banks
    sta detect_reu_capacity_kib_lo
    sta detect_reu_capacity_kib_hi
    sta detect_reu_fingerprint
    jsr detect_reu_restore_state
    sec
    rts

; A = pattern, X = site; C=1 on DMA/REC failure
detect_reu_write_pattern:
    sta reu_xfer_byte
    txa
    pha
    jsr detect_reu_set_site
    lda #REU_CMD_TO_REU
    jsr detect_reu_dma_byte
    pla
    tax
    rts

; A = expected pattern, X = site; C=1 mismatch or DMA failure
detect_reu_verify_pattern:
    sta zp_tmp4
    txa
    pha
    jsr detect_reu_set_site
    lda #REU_CMD_FROM_REU
    jsr detect_reu_dma_byte
    bcs @bad_pop
    pla
    tax
    lda reu_xfer_byte
    cmp zp_tmp4
    bne @bad
    clc
    rts
@bad_pop:
    pla
@bad:
    sec
    rts

; Restore the three saved REU probe bytes and verify site0.
detect_reu_restore_probe_bytes:
    ldx #0
    lda reu_saved_byte0
    jsr detect_reu_write_pattern
    bcs @done
    ldx #1
    lda reu_saved_byte1
    jsr detect_reu_write_pattern
    bcs @done
    ldx #2
    lda reu_saved_byte2
    jsr detect_reu_write_pattern
    bcs @done
    ldx #0
    lda reu_saved_byte0
    jsr detect_reu_verify_pattern
@done:
    rts
