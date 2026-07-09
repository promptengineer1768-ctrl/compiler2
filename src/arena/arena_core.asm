; src/arena/arena_core.asm
; Typed manifest-defined arena directory backed by generation-stamped page extents.

.include "common/zp.inc"
.include "common/constants.asm"
.include "arena_layout.inc"

.import page_alloc_init
.import page_alloc
.import page_free
.import page_check_in_range
.import page_select_offset
.import page_clear_extent

ARENA_CANARY = $A5

.segment "BSS"
__arena_core_generation_value: .res 2
__arena_core_ready:            .res 1
.export __arena_core_canary
__arena_core_canary:           .res ARENA_COUNT + 1
arena_active:                  .res ARENA_COUNT + 1
arena_type:                    .res ARENA_COUNT + 1
arena_generation:              .res ARENA_COUNT + 1
arena_capacity_lo:             .res ARENA_COUNT + 1
arena_capacity_hi:             .res ARENA_COUNT + 1
arena_extent_slot:             .res ARENA_COUNT + 1
arena_extent_generation:       .res ARENA_COUNT + 1
arena_checksum:                .res ARENA_COUNT + 1
arena_request:                 .res 5
arena_work_id:                 .res 1
arena_work_generation:         .res 1
arena_work_capacity:           .res 2

.segment "RODATA"
arena_default_capacity_lo:
    .byte $00
    .byte <ARENA_MIN_PAGES_TOKENIZED_PROGRAM
    .byte <ARENA_MIN_PAGES_COMPILED_IMAGE
    .byte <ARENA_MIN_PAGES_SCALARS
    .byte <ARENA_MIN_PAGES_ARRAYS
    .byte <ARENA_MIN_PAGES_STRINGS
    .byte <ARENA_MIN_PAGES_SYMBOLS_IR
    .byte <ARENA_MIN_PAGES_OVERLAY_METADATA
    .byte <ARENA_MIN_PAGES_SCRATCH
    .byte <ARENA_MIN_PAGES_PROGRAM_STAGING
arena_default_capacity_hi:
    .byte $00
    .byte >ARENA_MIN_PAGES_TOKENIZED_PROGRAM
    .byte >ARENA_MIN_PAGES_COMPILED_IMAGE
    .byte >ARENA_MIN_PAGES_SCALARS
    .byte >ARENA_MIN_PAGES_ARRAYS
    .byte >ARENA_MIN_PAGES_STRINGS
    .byte >ARENA_MIN_PAGES_SYMBOLS_IR
    .byte >ARENA_MIN_PAGES_OVERLAY_METADATA
    .byte >ARENA_MIN_PAGES_SCRATCH
    .byte >ARENA_MIN_PAGES_PROGRAM_STAGING

.segment "GEOASM"

; __arena_core_init
; Inputs: none. Outputs: C=0. Clobbers: A, X, Y.
; Side effects: clears the directory and resets the shared page allocator.
; Zero page: none.
.export __arena_core_init
__arena_core_init:
    jsr page_alloc_init
    lda #$00
    sta __arena_core_ready
    sta __arena_core_generation_value+1
    ldx #ARENA_COUNT
@clear:
    sta arena_active,x
    sta arena_type,x
    sta arena_generation,x
    sta arena_capacity_lo,x
    sta arena_capacity_hi,x
    sta arena_extent_slot,x
    sta arena_extent_generation,x
    sta __arena_core_canary,x
    sta arena_checksum,x
    dex
    bpl @clear
    lda #$01
    sta __arena_core_generation_value
    sta __arena_core_ready
    clc
    rts

arena_ensure_ready:
    lda __arena_core_ready
    bne :+
    jsr __arena_core_init
:
    rts

; Compute metadata checksum for X=id, returning A.
arena_compute_checksum:
    lda arena_type,x
    eor arena_generation,x
    eor arena_capacity_lo,x
    eor arena_capacity_hi,x
    eor arena_extent_slot,x
    eor arena_extent_generation,x
    eor __arena_core_canary,x
    rts

arena_store_checksum:
    jsr arena_compute_checksum
    sta arena_checksum,x
    rts

; __arena_core_generation
; Inputs: none. Outputs: X/Y=directory generation. Clobbers: A, X, Y.
; Flags: C=0. Zero page: none.
.export __arena_core_generation
__arena_core_generation:
    jsr arena_ensure_ready
    ldx __arena_core_generation_value
    ldy __arena_core_generation_value+1
    clc
    rts

; arena_init_all
; Inputs: none. Outputs: C=0 or allocation failure. Clobbers: A, X, Y.
; Side effects: constructs every manifest-defined typed arena.
; Zero page: none.
.export arena_init_all
arena_init_all:
    jsr __arena_core_init
    lda #$01
    sta arena_work_id
@create:
    ldx arena_work_id
    lda arena_default_capacity_lo,x
    sta arena_work_capacity
    lda arena_default_capacity_hi,x
    sta arena_work_capacity+1
    txa
    ldx arena_work_capacity
    ldy arena_work_capacity+1
    jsr arena_create
    bcs @error
    inc arena_work_id
    lda arena_work_id
    cmp #ARENA_COUNT + 1
    bcc @create
    clc
@error:
    rts

; arena_create
; Inputs: A=type/id (1..8), X/Y=capacity pages.
; Outputs: X=id, Y=generation, C=error. Clobbers: A, X, Y.
; Side effects: allocates one owned extent and publishes its directory entry.
; Zero page: none.
.export arena_create
arena_create:
    sta arena_work_id
    stx arena_work_capacity
    sty arena_work_capacity+1
    jsr arena_ensure_ready
    lda arena_work_id
    beq @invalid
    cmp #ARENA_COUNT + 1
    bcs @invalid
    tax
    lda arena_active,x
    bne @invalid
    lda arena_work_capacity
    ora arena_work_capacity+1
    beq @invalid
    lda arena_work_capacity
    sta arena_request
    lda arena_work_capacity+1
    sta arena_request+1
    lda #$01
    sta arena_request+2
    lda #$00
    sta arena_request+3
    lda arena_work_id
    sta arena_request+4
    ldx #<arena_request
    ldy #>arena_request
    jsr page_alloc
    bcs @error
    stx arena_work_capacity
    sty arena_work_capacity+1
    ldx arena_work_id
    lda arena_work_id
    sta arena_type,x
    lda arena_work_capacity
    sta arena_extent_slot,x
    lda arena_work_capacity+1
    sta arena_extent_generation,x
    lda arena_request
    sta arena_capacity_lo,x
    lda arena_request+1
    sta arena_capacity_hi,x
    inc arena_generation,x
    bne :+
    inc arena_generation,x
:
    lda #$01
    sta arena_active,x
    lda #ARENA_CANARY
    sta __arena_core_canary,x
    jsr arena_store_checksum
    ldy arena_generation,x
    clc
    rts
@invalid:
    lda #ERR_ILLEGAL_QUANTITY
    sec
@error:
    rts

; arena_handle_valid
; Inputs: X=id, Y=generation. Outputs: C=0 valid, C=1 stale/corrupt.
; Clobbers: A, flags. Side effects: validates the backing extent too.
; Zero page: none.
.export arena_handle_valid
arena_handle_valid:
    stx arena_work_id
    sty arena_work_generation
    jsr arena_ensure_ready
    ldx arena_work_id
    cpx #$01
    bcc @error
    cpx #ARENA_COUNT + 1
    bcs @error
    lda arena_active,x
    beq @error
    lda arena_type,x
    cmp arena_work_id
    bne @error
    lda arena_generation,x
    cmp arena_work_generation
    bne @error
    lda __arena_core_canary,x
    cmp #ARENA_CANARY
    bne @error
    jsr arena_compute_checksum
    cmp arena_checksum,x
    bne @error
    ldy arena_extent_generation,x
    lda arena_extent_slot,x
    tax
    jsr page_check_in_range
    bcs @error
    ldx arena_work_id
    ldy arena_work_generation
    clc
    rts
@error:
    ldx arena_work_id
    ldy arena_work_generation
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; arena_open
; Inputs: A=arena id. Outputs: X=id, Y=current generation, C=0 when active;
; C=1/A=error when the id is invalid or the arena is not active.
; This is the only supported way for a subsystem to acquire an existing arena
; handle; consumers must not assume an initial generation value.
.export arena_open
arena_open:
    tax
    cpx #$01
    bcc @error
    cpx #ARENA_COUNT + 1
    bcs @error
    lda arena_active,x
    beq @error
    ldy arena_generation,x
    jmp arena_handle_valid
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; arena_check_integrity
; Inputs: X/Y=arena handle. Outputs: C=1 on corruption.
; Clobbers: A, X, Y. Side effects: none. Zero page: none.
.export arena_check_integrity
arena_check_integrity:
    jmp arena_handle_valid

; arena_destroy
; Inputs: X/Y=arena handle. Outputs: C=error. Clobbers: A, X, Y.
; Side effects: releases the extent and invalidates the generation.
; Zero page: none.
.export arena_destroy
arena_destroy:
    jsr arena_handle_valid
    bcs @error
    ldx arena_work_id
    ldy arena_extent_generation,x
    lda arena_extent_slot,x
    tax
    jsr page_free
    bcs @error
    ldx arena_work_id
    lda #$00
    sta arena_active,x
    sta __arena_core_canary,x
    sta arena_checksum,x
    inc arena_generation,x
    bne :+
    inc arena_generation,x
:
    jsr __arena_core_bump_generation
    clc
@error:
    rts

; arena_invalidate_generation
; Inputs: X/Y=arena handle. Outputs: X=id, Y=new generation, C=error.
; Clobbers: A, X, Y. Side effects: invalidates outstanding arena handles.
; Zero page: none.
.export arena_invalidate_generation
arena_invalidate_generation:
    jsr arena_handle_valid
    bcs @error
    ldx arena_work_id
    inc arena_generation,x
    bne :+
    inc arena_generation,x
:
    lda arena_generation,x
    sta arena_work_generation
    jsr arena_store_checksum
    jsr __arena_core_bump_generation
    ldx arena_work_id
    ldy arena_work_generation
    clc
@error:
    rts

; arena_reset
; Inputs: X/Y=arena handle. Outputs: X=id, Y=new generation, C=error.
; Side effects: invalidates logical contents while retaining owned pages.
; Clobbers: A, X, Y. Zero page: none.
.export arena_reset
arena_reset:
    jsr arena_handle_valid
    bcs @error
    ldx arena_work_id
    ldy arena_extent_generation,x
    lda arena_extent_slot,x
    tax
    jsr page_clear_extent
    bcs @error
    ldx arena_work_id
    ldy arena_work_generation
    jmp arena_invalidate_generation
@error:
    rts

; arena_get_handle
; Inputs: X/Y=arena handle, A=arena-relative page offset.
; Outputs: X/Y=backing extent handle, C=error.
; Clobbers: A, X, Y. Side effects: validates metadata and backing extent.
; Zero page: none.
.export arena_get_handle
arena_get_handle:
    sta arena_work_capacity
    jsr arena_handle_valid
    bcs @error
    ldx arena_work_id
    lda arena_capacity_hi,x
    bne @resolved
    lda arena_work_capacity
    cmp arena_capacity_lo,x
    bcs @error
@resolved:
    lda arena_extent_slot,x
    pha
    lda arena_extent_generation,x
    tay
    pla
    tax
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; arena_select_page
; Inputs: X/Y=arena handle, A=arena-relative page offset.
; Outputs: C=0 with the page selected, C=1 for stale/out-of-range input.
; Clobbers: A, X, Y. Side effects: changes the selected geoRAM block/page.
; Zero page: none.
.export arena_select_page
arena_select_page:
    sta arena_work_capacity
    jsr arena_handle_valid
    bcs @error
    ldx arena_work_id
    lda arena_work_capacity
    pha
    ldy arena_extent_generation,x
    lda arena_extent_slot,x
    tax
    pla
    jmp page_select_offset
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; __arena_core_bump_generation
; Inputs: none. Outputs: X/Y=incremented directory generation, C=0.
; Clobbers: A, X, Y. Side effects: advances directory mutation generation.
; Zero page: none.
.export __arena_core_bump_generation
__arena_core_bump_generation:
    jsr arena_ensure_ready
    inc __arena_core_generation_value
    bne :+
    inc __arena_core_generation_value+1
:
    ldx __arena_core_generation_value
    ldy __arena_core_generation_value+1
    clc
    rts
