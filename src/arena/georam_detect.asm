; src/arena/georam_detect.asm
; Non-destructive geoRAM detection.

.include "common/zp.inc"
.include "common/constants.asm"

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
detect_profile_blocks:     .res 1
detect_profile_pages_lo:   .res 1
detect_profile_pages_hi:   .res 1
detect_probe_a:            .res 1
detect_probe_b:            .res 1
detect_saved_byte_a:       .res 1
detect_saved_byte_b:       .res 1
detect_saved_min_byte:      .res 1
detect_fingerprint:        .res 1

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

detect_save_state:
    lda $01
    sta detect_saved_port
    lda zp_gr_block
    sta detect_saved_block
    lda zp_gr_page
    sta detect_saved_page
    lda GEORAM_BLOCK
    sta detect_saved_hw_block
    lda GEORAM_PAGE
    sta detect_saved_hw_page
    rts

detect_restore_state:
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
    lda #DETECT_MIN_BLOCKS
    sta detect_capacity_blocks
    lda #$00
    sta detect_capacity_pages_lo
    lda #$08
    sta detect_capacity_pages_hi
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
    sta detect_fingerprint
    ldx detect_profile_pages_lo
    ldy detect_profile_pages_hi
    rts

detect_validate_profile:
    cpx detect_profile_pages_lo
    bne @fail
    cpy detect_profile_pages_hi
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
    clc
    jsr detect_restore_state
    rts
@fail:
    sec
@restore:
    jsr detect_restore_state
    rts
