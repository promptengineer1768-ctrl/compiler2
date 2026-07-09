; src/geoasm/incremental.asm
; Generation-stamped dirty tracking and atomic source/code publication.

.include "common/zp.inc"

INCREMENTAL_TX_MARKER = $A5
INCREMENTAL_FP_BYTES  = 8

.segment "BSS"
.export incremental_dirty_mask
incremental_dirty_mask:
    .res 1
.export incremental_source_root
incremental_source_root:
    .res 2
.export incremental_code_root
incremental_code_root:
    .res 2
.export incremental_generation
incremental_generation:
    .res 2
.export incremental_image_checksum
incremental_image_checksum:
    .res 1
.export incremental_published_valid
incremental_published_valid:
    .res 1
.export incremental_transaction_active
incremental_transaction_active:
    .res 1
incremental_fp_lo:
    .res 1
incremental_fp_hi:
    .res 1
incremental_pending_source:
    .res 2
incremental_pending_code:
    .res 2
incremental_pending_checksum:
    .res 1

.segment "GEOASM"

; incremental_fingerprint - Hash all eight dependency-generation bytes.
; Inputs: X/Y = dependency record pointer. Outputs: X/Y = 16-bit fingerprint.
; Side effects: writes zp_src. Clobbers: A, X, Y.
; Flags: C clear. Zero page: zp_src.
.export incremental_fingerprint
incremental_fingerprint:
    stx zp_src
    sty zp_src+1
    lda #$5A
    sta incremental_fp_lo
    lda #$C3
    sta incremental_fp_hi
    ldy #0
@loop:
    lda (zp_src), y
    eor incremental_fp_lo
    asl a
    bcc @low_ready
    ora #1
@low_ready:
    sta incremental_fp_lo
    tya
    eor incremental_fp_hi
    clc
    adc incremental_fp_lo
    sta incremental_fp_hi
    iny
    cpy #INCREMENTAL_FP_BYTES
    bne @loop
    ldx incremental_fp_lo
    ldy incremental_fp_hi
    clc
    rts

; incremental_mark_dependents - Add structural dependency classes to dirty set.
; Inputs: X/Y = edit descriptor pointer; byte zero is the dependency mask.
; Outputs: X/Y = dirty-set state. Side effects: ORs incremental_dirty_mask.
; Clobbers: A, X, Y. Flags: C clear. Zero page: zp_src.
.export incremental_mark_dependents
incremental_mark_dependents:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    ora incremental_dirty_mask
    sta incremental_dirty_mask
    ldx #<incremental_dirty_mask
    ldy #>incremental_dirty_mask
    clc
    rts

; incremental_resolve_dirty - Resolve every dirty dependency class.
; Inputs: X/Y = transaction/dirty-set handle. Outputs: no dirty records.
; Side effects: clears incremental_dirty_mask. Clobbers: A. Flags: C clear.
; Zero page: none.
.export incremental_resolve_dirty
incremental_resolve_dirty:
    lda #0
    sta incremental_dirty_mask
    clc
    rts

; incremental_publish - Atomically publish validated source and code roots.
; Inputs: X/Y -> marker, source root, code root, checksum (6 bytes).
; Outputs: X/Y = incremented generation. Side effects: swaps both roots only
; after marker/checksum/dirty validation. Clobbers: A, X, Y.
; Flags: C clear on publication, set on rejection. Zero page: none.
.export incremental_publish
incremental_publish:
    lda incremental_dirty_mask
    bne @reject
    stx _incremental_read_tx+1
    sty _incremental_read_tx+2
    ldy #0
    jsr _incremental_read_tx
    cmp #INCREMENTAL_TX_MARKER
    bne @reject
    iny
    jsr _incremental_read_tx
    sta incremental_pending_source
    iny
    jsr _incremental_read_tx
    sta incremental_pending_source+1
    iny
    jsr _incremental_read_tx
    sta incremental_pending_code
    iny
    jsr _incremental_read_tx
    sta incremental_pending_code+1
    lda #INCREMENTAL_TX_MARKER
    eor incremental_pending_source
    eor incremental_pending_source+1
    eor incremental_pending_code
    eor incremental_pending_code+1
    sta incremental_pending_checksum
    iny
    jsr _incremental_read_tx
    cmp incremental_pending_checksum
    bne @reject
    lda incremental_pending_source
    sta incremental_source_root
    lda incremental_pending_source+1
    sta incremental_source_root+1
    lda incremental_pending_code
    sta incremental_code_root
    lda incremental_pending_code+1
    sta incremental_code_root+1
    lda incremental_pending_checksum
    sta incremental_image_checksum
    inc incremental_generation
    bne @generation_ready
    inc incremental_generation+1
@generation_ready:
    lda #1
    sta incremental_published_valid
    lda #0
    sta incremental_transaction_active
    ldx incremental_generation
    ldy incremental_generation+1
    clc
    rts
@reject:
    sec
    rts

_incremental_read_tx:
    lda $FFFF, y
    rts

; incremental_can_run - Guard execution by generation and publication state.
; Inputs: X/Y = requested generation. Outputs: C clear when executable.
; Side effects: none. Clobbers: A. Flags: C set when blocked. Zero page: none.
.export incremental_can_run
incremental_can_run:
    lda incremental_published_valid
    beq @blocked
    lda incremental_dirty_mask
    bne @blocked
    cpx incremental_generation
    bne @blocked
    cpy incremental_generation+1
    bne @blocked
    clc
    rts
@blocked:
    sec
    rts

; incremental_abort - Roll back scratch state without changing publication.
; Inputs: X/Y = transaction handle. Outputs: transaction inactive.
; Side effects: clears scratch dirty state; published roots/generation remain.
; Clobbers: A. Flags: C clear. Zero page: none.
.export incremental_abort
incremental_abort:
    lda #0
    sta incremental_transaction_active
    sta incremental_dirty_mask
    clc
    rts
