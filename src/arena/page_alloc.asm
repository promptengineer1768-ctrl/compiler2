; src/arena/page_alloc.asm
; GeoRAM free-page bitmap allocator with generation-stamped extent handles.
;
; Extent request (X/Y pointer): count:u16, alignment:u16, owner:u8.
; Extent handle: X=slot (1..255), Y=slot generation.  Physical page ranges
; remain allocator-owned so callers cannot retain unstable window addresses.

.include "common/zp.inc"
.include "common/constants.asm"

.import detect_capacity_blocks
.import georam_select

PAGE_ALLOC_MIN_BLOCKS = 32
PAGE_ALLOC_SLOT_COUNT = 255

.segment "BSS"
page_bitmap:                 .res 256
page_slot_active:            .res 256
page_slot_generation:        .res 256
page_slot_owner:             .res 256
page_slot_start_lo:          .res 256
page_slot_start_hi:          .res 256
page_slot_count_lo:          .res 256
page_slot_count_hi:          .res 256

page_capacity_lo:            .res 1
page_capacity_hi:            .res 1
page_free_lo:                .res 1
page_free_hi:                .res 1
page_request_count:          .res 2
page_request_alignment:      .res 2
page_request_owner:          .res 1
page_candidate:              .res 2
page_cursor:                 .res 2
page_remaining:              .res 2
page_run:                    .res 2
page_largest:                .res 2
page_bitmap_index:           .res 1
page_bit_index:              .res 1
page_handle_slot:            .res 1
page_handle_generation:      .res 1
page_saved_block:             .res 1
page_saved_page:              .res 1
page_ready:                  .res 1

.segment "RODATA"
page_bit_masks:
    .byte $01, $02, $04, $08, $10, $20, $40, $80
page_bit_clear_masks:
    .byte $FE, $FD, $FB, $F7, $EF, $DF, $BF, $7F

.segment "CODE"

; page_alloc_init
; Inputs: none. Outputs: C=0. Clobbers: A, X, Y.
; Side effects: clears bitmap/handles and snapshots detected capacity.
; Zero page: none.
.export page_alloc_init
page_alloc_init:
    lda detect_capacity_blocks
    bne :+
    lda #PAGE_ALLOC_MIN_BLOCKS
:
    cmp #PAGE_ALLOC_MIN_BLOCKS
    bcs :+
    lda #PAGE_ALLOC_MIN_BLOCKS
:
    ; The current detector publishes the supported 512 KiB profile: 32
    ; 16 KiB blocks = 2,048 256-byte pages.  Never index beyond the bitmap if
    ; a corrupt or future unsupported profile value appears here.
    cmp #PAGE_ALLOC_MIN_BLOCKS + 1
    bcc :+
    lda #PAGE_ALLOC_MIN_BLOCKS
:
    lsr
    lsr
    sta page_capacity_hi
    lda #$00
    sta page_capacity_lo
    sta page_free_lo
    sta page_ready
    lda page_capacity_hi
    sta page_free_hi
    ldx #$00
    lda #$00
@clear:
    sta page_bitmap,x
    sta page_slot_active,x
    sta page_slot_owner,x
    sta page_slot_start_lo,x
    sta page_slot_start_hi,x
    sta page_slot_count_lo,x
    sta page_slot_count_hi,x
    inx
    bne @clear
    lda #$01
    sta page_ready
    clc
    rts

page_ensure_ready:
    lda page_ready
    bne :+
    jsr page_alloc_init
:
    rts

; Decode and validate the request record addressed by X/Y.
page_read_request:
    stx zp_src
    sty zp_src+1
    ldy #$00
    lda (zp_src),y
    sta page_request_count
    iny
    lda (zp_src),y
    sta page_request_count+1
    iny
    lda (zp_src),y
    sta page_request_alignment
    iny
    lda (zp_src),y
    sta page_request_alignment+1
    iny
    lda (zp_src),y
    sta page_request_owner
    lda page_request_count
    ora page_request_count+1
    beq @error
    lda page_request_alignment
    ora page_request_alignment+1
    beq @error
    lda page_request_owner
    beq @error
    ; Alignment must be a power of two.  Test n & (n-1) over 16 bits.
    sec
    lda page_request_alignment
    sbc #$01
    sta page_cursor
    lda page_request_alignment+1
    sbc #$00
    sta page_cursor+1
    lda page_cursor
    and page_request_alignment
    sta page_cursor
    lda page_cursor+1
    and page_request_alignment+1
    ora page_cursor
    bne @error
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; Return Z=1 when page_candidate is aligned to the request power of two.
page_candidate_aligned:
    sec
    lda page_request_alignment
    sbc #$01
    sta page_cursor
    lda page_request_alignment+1
    sbc #$00
    sta page_cursor+1
    lda page_candidate
    and page_cursor
    sta page_remaining
    lda page_candidate+1
    and page_cursor+1
    ora page_remaining
    rts

; Return A=0 for a free page and nonzero for an allocated page.
; Input is page_cursor (0..65535); valid capacity is checked by callers.
page_bitmap_test:
    lda page_cursor
    and #$07
    sta page_bit_index
    lda page_cursor
    lsr
    lsr
    lsr
    sta page_bitmap_index
    lda page_cursor+1
    asl
    asl
    asl
    asl
    asl
    ora page_bitmap_index
    tay
    ldx page_bit_index
    lda page_bitmap,y
    and page_bit_masks,x
    rts

; Set/clear the bit for page_cursor according to A (zero=clear, nonzero=set).
page_bitmap_write:
    pha
    lda page_cursor
    and #$07
    sta page_bit_index
    lda page_cursor
    lsr
    lsr
    lsr
    sta page_bitmap_index
    lda page_cursor+1
    asl
    asl
    asl
    asl
    asl
    ora page_bitmap_index
    tay
    ldx page_bit_index
    pla
    beq @clear
    lda page_bitmap,y
    ora page_bit_masks,x
    sta page_bitmap,y
    rts
@clear:
    lda page_bitmap,y
    and page_bit_clear_masks,x
    sta page_bitmap,y
    rts

; Compare page_cursor with capacity. C=1 when cursor >= capacity.
page_cursor_at_capacity:
    lda page_cursor+1
    cmp page_capacity_hi
    bne :+
    lda page_cursor
    cmp page_capacity_lo
:
    rts

; Advance page_cursor and decrement page_remaining.
page_advance_remaining:
    inc page_cursor
    bne :+
    inc page_cursor+1
:
    sec
    lda page_remaining
    sbc #$01
    sta page_remaining
    lda page_remaining+1
    sbc #$00
    sta page_remaining+1
    rts

; Find a free aligned run. Returns candidate in page_candidate, C=0.
page_find_run:
    lda #$00
    sta page_candidate
    sta page_candidate+1
@candidate:
    lda page_candidate+1
    cmp page_capacity_hi
    bcc :+
    bne @fail
    lda page_candidate
    cmp page_capacity_lo
    bcs @fail
:
    jsr page_candidate_aligned
    bne @next
    lda page_candidate
    sta page_cursor
    lda page_candidate+1
    sta page_cursor+1
    lda page_request_count
    sta page_remaining
    lda page_request_count+1
    sta page_remaining+1
@probe:
    lda page_remaining
    ora page_remaining+1
    beq @found
    jsr page_cursor_at_capacity
    bcs @fail
    jsr page_bitmap_test
    bne @next
    jsr page_advance_remaining
    jmp @probe
@next:
    inc page_candidate
    bne @candidate
    inc page_candidate+1
    jmp @candidate
@found:
    clc
    rts
@fail:
    lda #ERR_OUT_OF_DATA
    sec
    rts

page_find_slot:
    ldx #$01
@loop:
    lda page_slot_active,x
    beq @found
    inx
    bne @loop
    lda #ERR_OUT_OF_DATA
    sec
    rts
@found:
    stx page_handle_slot
    clc
    rts

; Mark the requested candidate range with A=zero/free or nonzero/allocated.
page_mark_candidate:
    sta page_handle_generation
    lda page_candidate
    sta page_cursor
    lda page_candidate+1
    sta page_cursor+1
    lda page_request_count
    sta page_remaining
    lda page_request_count+1
    sta page_remaining+1
@loop:
    lda page_remaining
    ora page_remaining+1
    beq @done
    lda page_handle_generation
    jsr page_bitmap_write
    jsr page_advance_remaining
    jmp @loop
@done:
    rts

; page_alloc
; Inputs: X/Y=request pointer. Outputs: X=slot, Y=generation, C=error.
; Side effects: allocates an aligned contiguous extent and records ownership.
; Clobbers: A, X, Y. Zero page: none.
.export page_alloc
page_alloc:
    jsr page_ensure_ready
    jsr page_read_request
    bcs @error
    ; Reject requests larger than the free-page total before scanning.
    lda page_free_hi
    cmp page_request_count+1
    bcc @oom
    bne :+
    lda page_free_lo
    cmp page_request_count
    bcc @oom
:
    jsr page_find_slot
    bcs @error
    jsr page_find_run
    bcs @error
    lda #$01
    jsr page_mark_candidate
    ldx page_handle_slot
    inc page_slot_generation,x
    bne :+
    inc page_slot_generation,x
:
    lda page_slot_generation,x
    sta page_handle_generation
    lda #$01
    sta page_slot_active,x
    lda page_request_owner
    sta page_slot_owner,x
    lda page_candidate
    sta page_slot_start_lo,x
    lda page_candidate+1
    sta page_slot_start_hi,x
    lda page_request_count
    sta page_slot_count_lo,x
    lda page_request_count+1
    sta page_slot_count_hi,x
    sec
    lda page_free_lo
    sbc page_request_count
    sta page_free_lo
    lda page_free_hi
    sbc page_request_count+1
    sta page_free_hi
    ldx page_handle_slot
    ldy page_handle_generation
    clc
    rts
@oom:
    lda #ERR_OUT_OF_DATA
    sec
@error:
    rts

; Validate X/Y as a live extent handle. Preserves X/Y; C=0 valid.
page_validate_handle:
    stx page_handle_slot
    sty page_handle_generation
    cpx #$00
    beq @error
    lda page_slot_active,x
    beq @error
    lda page_slot_generation,x
    cmp page_handle_generation
    bne @error
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; page_free
; Inputs: X=slot, Y=generation. Outputs: C=0 or stale-handle error.
; Side effects: checks generation/owner metadata and releases exactly the extent.
; Clobbers: A, X, Y. Zero page: none.
.export page_free
page_free:
    jsr page_ensure_ready
    jsr page_validate_handle
    bcs @error
    ldx page_handle_slot
    lda page_slot_owner,x
    beq @error
    lda page_slot_start_lo,x
    sta page_candidate
    lda page_slot_start_hi,x
    sta page_candidate+1
    lda page_slot_count_lo,x
    sta page_request_count
    lda page_slot_count_hi,x
    sta page_request_count+1
    lda #$00
    jsr page_mark_candidate
    clc
    lda page_free_lo
    adc page_request_count
    sta page_free_lo
    lda page_free_hi
    adc page_request_count+1
    sta page_free_hi
    ldx page_handle_slot
    lda #$00
    sta page_slot_active,x
    sta page_slot_owner,x
    clc
    rts
@error:
    sec
    rts

; page_alloc_count
; Inputs: none. Outputs: X/Y=free pages, C=0. Clobbers: A, X, Y.
.export page_alloc_count
page_alloc_count:
    jsr page_ensure_ready
    ldx page_free_lo
    ldy page_free_hi
    clc
    rts

; page_alloc_largest
; Inputs: none. Outputs: X/Y=largest contiguous free run, C=0.
; Clobbers: A, X, Y. Zero page: none.
.export page_alloc_largest
page_alloc_largest:
    jsr page_ensure_ready
    lda #$00
    sta page_cursor
    sta page_cursor+1
    sta page_run
    sta page_run+1
    sta page_largest
    sta page_largest+1
@scan:
    jsr page_cursor_at_capacity
    bcs @done
    jsr page_bitmap_test
    bne @used
    inc page_run
    bne :+
    inc page_run+1
:
    lda page_run+1
    cmp page_largest+1
    bcc @advance
    bne @new_largest
    lda page_run
    cmp page_largest
    bcc @advance
@new_largest:
    lda page_run
    sta page_largest
    lda page_run+1
    sta page_largest+1
    jmp @advance
@used:
    lda #$00
    sta page_run
    sta page_run+1
@advance:
    inc page_cursor
    bne @scan
    inc page_cursor+1
    jmp @scan
@done:
    ldx page_largest
    ldy page_largest+1
    clc
    rts

; page_check_in_range
; Inputs: X=slot, Y=generation. Outputs: C=0 only for a live in-profile extent.
; Clobbers: A. Zero page: none.
.export page_check_in_range
page_check_in_range:
    jsr page_ensure_ready
    jsr page_validate_handle
    bcs @error
    ldx page_handle_slot
    clc
    lda page_slot_start_lo,x
    adc page_slot_count_lo,x
    sta page_cursor
    lda page_slot_start_hi,x
    adc page_slot_count_hi,x
    sta page_cursor+1
    lda page_cursor+1
    cmp page_capacity_hi
    bcc @ok
    bne @error
    lda page_cursor
    cmp page_capacity_lo
    bcc @ok
    beq @ok
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
@ok:
    clc
    rts

; page_select_offset
; Inputs: X=extent slot, Y=generation, A=relative page offset.
; Outputs: C=0 with the resolved page selected, C=1 on stale/out-of-range input.
; Clobbers: A, X, Y. Side effects: changes the selected geoRAM block/page.
; Zero page: none.
.export page_select_offset
page_select_offset:
    sta page_cursor
    lda #$00
    sta page_cursor+1
    jsr page_ensure_ready
    jsr page_validate_handle
    bcs @error
    ldx page_handle_slot
    lda page_cursor+1
    cmp page_slot_count_hi,x
    bcc @resolve
    bne @error
    lda page_cursor
    cmp page_slot_count_lo,x
    bcs @error
@resolve:
    clc
    lda page_cursor
    adc page_slot_start_lo,x
    sta page_cursor
    lda page_cursor+1
    adc page_slot_start_hi,x
    sta page_cursor+1
    lda page_cursor
    and #$3F
    pha
    lda page_cursor
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    sta page_bitmap_index
    lda page_cursor+1
    asl
    asl
    ora page_bitmap_index
    tax
    pla
    jsr georam_select
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; page_clear_extent
; Inputs: X=slot, Y=generation. Outputs: C=error.
; Side effects: zeroes every byte in the owned GeoRAM extent and restores the
; caller's selected block/page through the pinned selection gate.
; Clobbers: A, X, Y. Zero page: zp_gr_block, zp_gr_page.
.export page_clear_extent
page_clear_extent:
    jsr page_ensure_ready
    jsr page_validate_handle
    bcs @error
    lda zp_gr_block
    sta page_saved_block
    lda zp_gr_page
    sta page_saved_page
    ldx page_handle_slot
    lda page_slot_start_lo,x
    sta page_cursor
    lda page_slot_start_hi,x
    sta page_cursor+1
    lda page_slot_count_lo,x
    sta page_remaining
    lda page_slot_count_hi,x
    sta page_remaining+1
@page:
    lda page_remaining
    ora page_remaining+1
    beq @restore
    lda page_cursor
    and #$3F
    pha
    lda page_cursor
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    sta page_bitmap_index
    lda page_cursor+1
    asl
    asl
    ora page_bitmap_index
    tax
    pla
    jsr georam_select
    ldx #$00
    lda #$00
@clear_page:
    sta $DE00,x
    inx
    bne @clear_page
    jsr page_advance_remaining
    jmp @page
@restore:
    lda page_saved_page
    ldx page_saved_block
    jsr georam_select
    clc
    rts
@error:
    sec
    rts
