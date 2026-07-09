; src/runtime/data.asm
; Runtime data-stream state with generation-checked cursors.
; An edit that reorders DATA cannot leave a compiled READ cursor bound to
; stale records.

.include "common/zp.inc"
.include "common/constants.asm"

; Data stream state variables. These are persistent stream cursors, not
; temporary scratch, so they live in BSS instead of unmanifested zero page.
.segment "BSS"

; DATA cursor pointer (points to next DATA item to read)
DATA_PTR:
    .res 2

; DATA generation (for change detection)
DATA_GENERATION:
    .res 2

; DATA line pointer (for RESTORE with line target)
DATA_LINE_PTR:
    .res 2

; Source generation (set at RUN time)
SOURCE_GENERATION:
    .res 2

; Start cursor for RUN/CLR and targetless RESTORE. The compiler/program
; publication path seeds this before data_reset.
DATA_SAVED_PTR:
    .res 2

; =============================================================================
; READ Statement
; =============================================================================

; data_read - READ statement
; Input:  X/Y = typed destination descriptor (pointer to variable)
; Output: C = error (0=ok, 1=OUT_OF_DATA)
; Clobbers: A, X, Y
; Side:   Advances generation-checked DATA cursor and coerces stock-compatible
;         value
.export data_read
data_read:
    ; Save destination descriptor
    stx zp_tmptr
    sty zp_tmptr+1
    
    ; Check if we have data items left
    lda DATA_PTR
    ora DATA_PTR+1
    beq @out_of_data
    
    ; Check generation match
    lda DATA_GENERATION
    cmp SOURCE_GENERATION
    bne @generation_mismatch
    lda DATA_GENERATION+1
    cmp SOURCE_GENERATION+1
    bne @generation_mismatch
    
    ; Read current DATA item through a generated zero-page pointer.
    lda DATA_PTR
    sta zp_src
    lda DATA_PTR+1
    sta zp_src+1
    ldy #0
    lda (zp_src),y
    
    ; Check for end of DATA items ($00 marker)
    beq @out_of_data
    
    ; Store value to destination
    ldy #0
    sta (zp_tmptr),y
    
    ; Advance cursor past this item
    inc DATA_PTR
    bne @done
    inc DATA_PTR+1
    
@done:
    clc                ; Success
    rts
    
@out_of_data:
    sec                ; Error: out of data
    rts
    
@generation_mismatch:
    ; Generation changed, data is stale
    sec
    rts

; =============================================================================
; RESTORE Statement
; =============================================================================

; data_restore - RESTORE statement
; Input:  optional line-target descriptor in X/Y
; Output: C = error (0=ok)
; Clobbers: A, X, Y
; Side:   Resolves first applicable DATA record and resets cursor
.export data_restore
data_restore:
    ; Check if line target is provided (X/Y = 0 means no target)
    txa
    tya
    beq @check_x
    bne @with_target
@check_x:
    txa
    bne @with_target
    
    ; No target: reset to beginning of DATA stream
    lda DATA_SAVED_PTR
    sta DATA_PTR
    lda DATA_SAVED_PTR+1
    sta DATA_PTR+1
    
    clc
    rts
    
@with_target:
    ; Reset to specified line
    ; X/Y = line pointer
    stx DATA_PTR
    sty DATA_PTR+1
    
    clc
    rts

; =============================================================================
; Data Stream Initialization
; =============================================================================

; data_reset - Initialize data stream state
; Input:  current source generation in X/Y
; Output: none
; Clobbers: A, X, Y
; Side:   Initializes stream state for RUN/CLR policy
.export data_reset
data_reset:
    ; Store source generation
    stx SOURCE_GENERATION
    sty SOURCE_GENERATION+1
    
    ; Reset DATA cursor to the published DATA start pointer.
    lda DATA_SAVED_PTR
    sta DATA_PTR
    lda DATA_SAVED_PTR+1
    sta DATA_PTR+1
    
    ; Initialize generation
    ldx SOURCE_GENERATION
    ldy SOURCE_GENERATION+1
    stx DATA_GENERATION
    sty DATA_GENERATION+1
    
    rts
