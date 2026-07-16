; src/resident/expansion_profile.asm
; Dual-device expansion profile published after install-time selection.
;
; Fields follow DESIGN2 §8.1.1 / REU_DESIGN.md §1.1. Gates consult this
; immutable session record; they do not re-probe on every call.

.include "common/zp.inc"
.include "common/constants.asm"

.segment "RESIDENT"

; store values
EXPANSION_STORE_NONE   = 0
EXPANSION_STORE_GEORAM = 1
EXPANSION_STORE_REU    = 2

; selection reasons
EXPANSION_REASON_NONE      = 0
EXPANSION_REASON_GEORAM    = 1  ; only geoRAM, or preferred geoRAM when both
EXPANSION_REASON_REU       = 2  ; only REU
EXPANSION_REASON_FALLBACK  = 3  ; preferred failed, fell back to other

.segment "BSS"
.export expansion_store
expansion_store:
    .res 1
.export expansion_reu_assist
expansion_reu_assist:
    .res 1
.export expansion_capacity_georam
expansion_capacity_georam:
    .res 1                       ; 16 KiB blocks (geoRAM convention)
.export expansion_capacity_reu
expansion_capacity_reu:
    .res 1                       ; 64 KiB banks
.export expansion_fingerprint
expansion_fingerprint:
    .res 1
.export expansion_image_fingerprint
expansion_image_fingerprint:
    .res 1
.export expansion_reason
expansion_reason:
    .res 1
.export expansion_generation
expansion_generation:
    .res 1
.export expansion_session_ready
expansion_session_ready:
    .res 1

.segment "RESIDENT"

.export expansion_clear
.export expansion_publish
.export expansion_mark_ready
.export expansion_check_skip_reload

; expansion_clear - zero the profile (pre-probe / fatal)
; Clobbers: A
expansion_clear:
    lda #0
    sta expansion_store
    sta expansion_reu_assist
    sta expansion_capacity_georam
    sta expansion_capacity_reu
    sta expansion_fingerprint
    sta expansion_image_fingerprint
    sta expansion_reason
    sta expansion_session_ready
    rts

; expansion_publish
; Inputs (caller-filled BSS candidates before call, or registers):
;   expansion_store, expansion_reu_assist, capacity fields, reason already set
;   by loader selection. Recomputes session fingerprint and bumps generation.
; Clobbers: A
expansion_publish:
    lda expansion_store
    eor expansion_reu_assist
    eor expansion_capacity_georam
    eor expansion_capacity_reu
    eor expansion_reason
    sta expansion_fingerprint
    inc expansion_generation
    rts

; expansion_mark_ready
; Input: A = image fingerprint of the installed GEORAM/REU image
; Marks session ready so a later loader entry may skip reload.
; Clobbers: A
expansion_mark_ready:
    sta expansion_image_fingerprint
    lda #1
    sta expansion_session_ready
    rts

; expansion_check_skip_reload
; Input: A = candidate image fingerprint the installer would load
; Output: C=0 skip reload (session ready + matching image fp + valid store)
;         C=1 must reload
; Clobbers: A
expansion_check_skip_reload:
    tax
    lda expansion_session_ready
    beq @must
    lda expansion_store
    beq @must
    cpx expansion_image_fingerprint
    bne @must
    clc
    rts
@must:
    sec
    rts
