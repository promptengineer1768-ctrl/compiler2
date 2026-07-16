; src/arena/georam_detect.asm
; Non-destructive geoRAM detection.
;
; GeoRAM installation detector and immutable interval profile publication.
; Dual-device selection uses the real REU probe in reu_detect.asm (no $DFxx
; status-bit fakes). Prefer geoRAM when both devices validate (DESIGN2 §8.1.1).

.include "common/zp.inc"
.include "common/constants.asm"

.import detect_reu

.segment "RESIDENT"

DETECT_MIN_BLOCKS = 32
DETECT_MIN_LAST_BLOCK = DETECT_MIN_BLOCKS - 1
DETECT_LAST_PAGE = $3F
GEORAM_WINDOW = $DE00
GEORAM_PAGE = $DFFE
GEORAM_BLOCK = $DFFF

.segment "BSS"
detect_saved_port:        .res 1
detect_saved_block:       .res 1
detect_saved_page:        .res 1
detect_saved_hw_block:    .res 1
detect_saved_hw_page:     .res 1
detect_capacity_blocks:   .res 1
detect_capacity_pages_lo:  .res 1
detect_capacity_pages_hi:  .res 1
detect_saved_status:       .res 1
detect_profile_blocks:     .res 1
detect_profile_pages_lo:   .res 1
detect_profile_pages_hi:   .res 1
detect_probe_a:            .res 1
detect_probe_b:            .res 1
detect_saved_byte_a:       .res 1
detect_saved_byte_b:       .res 1
detect_saved_min_byte:      .res 1
detect_probe_block:         .res 1
detect_fingerprint:        .res 1
detect_profile_store_kind: .res 1
detect_profile_reu_assist: .res 1
detect_profile_xip_base_lo: .res 1
detect_profile_xip_base_hi: .res 1
detect_profile_xip_slots: .res 1
detect_profile_n_dma: .res 1
detect_profile_n_fill: .res 1
detect_profile_generation: .res 1
detect_geo_ok:             .res 1
detect_reu_ok:             .res 1
detect_pages_lo_tmp:       .res 1
detect_pages_hi_tmp:       .res 1

.segment "RESIDENT"

.export detect_georam
.export detect_save_state
.export detect_probe_pattern1
.export detect_probe_pattern2
.export detect_probe_aliasing
.export detect_restore_state
.export detect_check_minimum
.export detect_publish_profile
.export detect_validate_profile
.export detect_capacity_blocks
.export detect_expansion
.export detect_profile_store_kind
.export detect_profile_reu_assist
.export detect_profile_xip_base_lo
.export detect_profile_xip_base_hi
.export detect_profile_xip_slots
.export detect_profile_n_dma
.export detect_profile_n_fill
.export detect_profile_generation

detect_save_state:
    php
    pla
    sta detect_saved_status
    sei
    lda $01
    sta detect_saved_port
    lda zp_gr_block
    sta detect_saved_block
    lda zp_gr_page
    sta detect_saved_page
    ; I/O may be hidden at entry. Make the geoRAM selectors visible only after
    ; retaining the exact CPU-port value that must be restored on exit.
    lda #CPU_PORT_CANONICAL
    sta $01
    lda GEORAM_BLOCK
    sta detect_saved_hw_block
    lda GEORAM_PAGE
    sta detect_saved_hw_page
    rts

detect_restore_state:
    ; Hardware selectors are available only while I/O is visible.
    lda #CPU_PORT_CANONICAL
    sta $01
    lda detect_saved_block
    sta zp_gr_block
    lda detect_saved_page
    sta zp_gr_page
    lda detect_saved_hw_block
    sta GEORAM_BLOCK
    lda detect_saved_hw_page
    sta GEORAM_PAGE
    lda detect_saved_port
    sta $01
    lda detect_saved_status
    pha
    plp
    rts

; Detect available expansion backend and publish immutable policy profile.
; Probes geoRAM then REU (non-destructive real REC probe). Prefers geoRAM.
; A=1 geoRAM, A=2 REU; carry set when neither is usable.
; On success with geoRAM store: X/Y = published page count.
detect_expansion:
    lda #$00
    sta detect_profile_store_kind
    sta detect_profile_reu_assist
    sta detect_profile_xip_base_lo
    sta detect_geo_ok
    sta detect_reu_ok
    lda #$CE
    sta detect_profile_xip_base_hi
    lda #$01
    sta detect_profile_xip_slots
    lda #32
    sta detect_profile_n_dma
    sta detect_profile_n_fill

    jsr detect_georam
    bcs @after_geo
    lda #1
    sta detect_geo_ok
    stx detect_pages_lo_tmp
    sty detect_pages_hi_tmp
@after_geo:
    jsr detect_reu
    bcs @after_reu
    lda #1
    sta detect_reu_ok
@after_reu:
    ; Prefer geoRAM when both validate.
    lda detect_geo_ok
    beq @try_reu_only
    lda #1
    sta detect_profile_store_kind
    lda detect_reu_ok
    sta detect_profile_reu_assist
    jsr detect_publish_profile
    inc detect_profile_generation
    ; detect_publish_profile already XORs generation-less fingerprint; re-fold
    ; store/assist/thresholds after generation bump for integrity coverage.
    lda detect_profile_blocks
    eor detect_profile_pages_lo
    eor detect_profile_pages_hi
    eor detect_profile_store_kind
    eor detect_profile_n_dma
    eor detect_profile_n_fill
    sta detect_fingerprint
    ldx detect_pages_lo_tmp
    ldy detect_pages_hi_tmp
    lda #1
    clc
    rts

@try_reu_only:
    lda detect_reu_ok
    beq @none
    lda #2
    sta detect_profile_store_kind
    lda #0
    sta detect_profile_reu_assist
    jsr detect_publish_profile
    inc detect_profile_generation
    lda detect_profile_blocks
    eor detect_profile_pages_lo
    eor detect_profile_pages_hi
    eor detect_profile_store_kind
    eor detect_profile_n_dma
    eor detect_profile_n_fill
    sta detect_fingerprint
    lda #2
    clc
    rts

@none:
    lda #0
    sta detect_profile_store_kind
    sta detect_profile_reu_assist
    sec
    rts

detect_probe_pattern1:
    lda #$AA
    sta detect_probe_a
    lda #$55
    sta detect_probe_b
    jmp detect_probe_selected_patterns

detect_probe_pattern2:
    lda #$55
    sta detect_probe_a
    lda #$AA
    sta detect_probe_b
    jmp detect_probe_selected_patterns

detect_probe_selected_patterns:
    lda #$00
    sta GEORAM_BLOCK
    sta GEORAM_PAGE
    lda GEORAM_WINDOW
    sta detect_saved_byte_a
    lda #$01
    sta GEORAM_PAGE
    lda GEORAM_WINDOW
    sta detect_saved_byte_b
    lda #$00
    sta GEORAM_PAGE
    lda detect_probe_a
    sta GEORAM_WINDOW
    lda #$01
    sta GEORAM_PAGE
    lda detect_probe_b
    sta GEORAM_WINDOW
    lda #$00
    sta GEORAM_PAGE
    lda GEORAM_WINDOW
    cmp detect_probe_a
    bne @fail
    lda #$01
    sta GEORAM_PAGE
    lda GEORAM_WINDOW
    cmp detect_probe_b
    bne @fail
    jsr detect_restore_probe_bytes
    clc
    rts
@fail:
    jsr detect_restore_probe_bytes
    sec
    rts

detect_restore_probe_bytes:
    lda #$00
    sta GEORAM_BLOCK
    sta GEORAM_PAGE
    lda detect_saved_byte_a
    sta GEORAM_WINDOW
    lda #$01
    sta GEORAM_PAGE
    lda detect_saved_byte_b
    sta GEORAM_WINDOW
    rts

detect_probe_aliasing:
    jsr detect_probe_pattern1
    bcs @absent
    jsr detect_probe_pattern2
    bcs @absent
    jsr detect_probe_minimum_block
    bcs @absent
    jsr detect_measure_capacity
    bcs @absent
    sta detect_capacity_blocks
    lda detect_capacity_blocks
    sta detect_capacity_pages_lo
    lda #$00
    sta detect_capacity_pages_hi
    ldx #6
@page_shift:
    asl detect_capacity_pages_lo
    rol detect_capacity_pages_hi
    dex
    bne @page_shift
    clc
    rts
@absent:
    lda #$00
    sta detect_capacity_blocks
    sta detect_capacity_pages_lo
    sta detect_capacity_pages_hi
    sec
    rts

detect_probe_minimum_block:
    lda #DETECT_MIN_LAST_BLOCK
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda GEORAM_WINDOW
    sta detect_saved_min_byte
    lda #$A5
    sta GEORAM_WINDOW
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda GEORAM_WINDOW
    cmp #$A5
    bne @fail
    lda detect_saved_min_byte
    sta GEORAM_WINDOW
    clc
    rts
@fail:
    lda detect_saved_min_byte
    sta GEORAM_WINDOW
    sec
    rts

; Measure the first block that is not writable or aliases block zero. The probe
; modifies only the final byte in the candidate blocks and restores both values
; before returning.
; Output: A = measured block count, C clear; C set when no capacity is proven.
detect_measure_capacity:
    lda #$01
    sta detect_probe_block
@next_block:
    lda #$00
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda GEORAM_WINDOW
    sta detect_saved_byte_a

    lda detect_probe_block
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda GEORAM_WINDOW
    sta detect_saved_byte_b

    lda #$00
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda #$A5
    sta GEORAM_WINDOW

    lda detect_probe_block
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda #$5A
    sta GEORAM_WINDOW

    ; An unimplemented candidate must prove persistence before it can count as
    ; a distinct block. Reselect the window before readback so both real
    ; hardware and the stepped C64 model expose the selected geoRAM byte rather
    ; than the CPU-side I/O shadow left by the attempted write.
    lda detect_probe_block
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda GEORAM_WINDOW
    cmp #$5A
    bne @capacity_end

    lda #$00
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda GEORAM_WINDOW
    cmp #$5A
    beq @capacity_end

    ; Distinct blocks: restore candidate, then block zero.
    lda detect_probe_block
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda detect_saved_byte_b
    sta GEORAM_WINDOW
    lda #$00
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda detect_saved_byte_a
    sta GEORAM_WINDOW
    lda detect_probe_block
    cmp #$FF
    beq @capacity_end
    inc detect_probe_block
    jmp @next_block

@capacity_end:
    ; The two selections name one physical byte, or the candidate is outside
    ; the installed device. Restore through both paths so unusual selector
    ; behavior still leaves the original byte intact.
    lda detect_probe_block
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda detect_saved_byte_b
    sta GEORAM_WINDOW
    lda #$00
    sta GEORAM_BLOCK
    lda #DETECT_LAST_PAGE
    sta GEORAM_PAGE
    lda detect_saved_byte_a
    sta GEORAM_WINDOW
    lda detect_probe_block
    clc
    rts

detect_check_minimum:
    lda detect_capacity_blocks
    cmp #DETECT_MIN_BLOCKS
    bcc @fail
    clc
    rts
@fail:
    sec
    rts

detect_publish_profile:
    lda detect_capacity_blocks
    sta detect_profile_blocks
    lda detect_capacity_pages_lo
    sta detect_profile_pages_lo
    lda detect_capacity_pages_hi
    sta detect_profile_pages_hi
    lda detect_profile_blocks
    eor detect_profile_pages_lo
    eor detect_profile_pages_hi
    eor detect_profile_store_kind
    eor detect_profile_n_dma
    eor detect_profile_n_fill
    sta detect_fingerprint
    ldx detect_profile_pages_lo
    ldy detect_profile_pages_hi
    rts

detect_validate_profile:
    cpx detect_profile_pages_lo
    bne @fail
    cpy detect_profile_pages_hi
    bne @fail
    lda detect_profile_blocks
    eor detect_profile_pages_lo
    eor detect_profile_pages_hi
    eor detect_profile_store_kind
    eor detect_profile_n_dma
    eor detect_profile_n_fill
    cmp detect_fingerprint
    bne @fail
    clc
    rts
@fail:
    sec
    rts

detect_georam:
    jsr detect_save_state
    jsr detect_probe_aliasing
    bcs @restore
    jsr detect_check_minimum
    bcs @restore
    jsr detect_publish_profile
    jsr detect_restore_state
    clc
    rts
@fail:
@restore:
    jsr detect_restore_state
    sec
    rts
