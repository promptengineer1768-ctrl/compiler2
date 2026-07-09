; src/runtime/arrays.asm
; Arena-backed typed array descriptors with a page-level suballocator.
;
; AD descriptor (16 bytes):
;   +0 "AD", +2 kind, +3 descriptor generation, +4 dimensions,
;   +5 element size, +6 array arena id, +7 arena generation,
;   +8 start page, +9 page count, +10 total elements:u16,
;   +12 bound0 inclusive:u16, +14 bound1 inclusive:u16.
;
; AM DIM request (14 bytes):
;   +0 "AM", +2 descriptor pointer:u16, +4 kind, +5 dimensions,
;   +6..7 reserved zero, +8 bound0:u16, +10 bound1:u16,
;   +12..13 reserved zero.
;
; AE element request (12 bytes):
;   +0 "AE", +2 descriptor pointer:u16, +4 sub0:u16, +6 sub1:u16,
;   +8 destination SD pointer:u16 for string arrays, +10..11 reserved zero.
;
; AS store request (12 bytes):
;   +0 "AS", +2 descriptor pointer:u16, +4 sub0:u16, +6 sub1:u16,
;   +8 int value or source SD pointer:u16, +10..11 reserved zero.
;   Float stores take their value from FAC1 and require bytes +8..+11 zero.

.include "common/zp.inc"
.include "common/constants.asm"
.include "arena_layout.inc"

.import arena_handle_valid
.import arena_select_page
.import str_copy
.import str_free

.macro jcs target
    bcc *+5
    jmp target
.endmacro
.macro jcc target
    bcs *+5
    jmp target
.endmacro
.macro jne target
    beq *+5
    jmp target
.endmacro
.macro jeq target
    bne *+5
    jmp target
.endmacro

ARRAY_ARENA = ARENA_TYPE_ARRAYS
ARRAY_ARENA_GENERATION = 1
ARRAY_PAGE_CAPACITY = ARENA_MIN_PAGES_ARRAYS

ARRAY_KIND_INT = 1
ARRAY_KIND_FLOAT = 2
ARRAY_KIND_STRING = 3

AD_KIND = 2
AD_GENERATION = 3
AD_DIMENSIONS = 4
AD_ELEMENT_SIZE = 5
AD_ARENA = 6
AD_ARENA_GENERATION = 7
AD_START_PAGE = 8
AD_PAGE_COUNT = 9
AD_TOTAL_LO = 10
AD_TOTAL_HI = 11
AD_BOUND0_LO = 12
AD_BOUND0_HI = 13
AD_BOUND1_LO = 14
AD_BOUND1_HI = 15

.segment "BSS"
arr_page_owner:          .res ARRAY_PAGE_CAPACITY
arr_generation_counter:  .res 1
arr_descriptor_ptr:      .res 2
arr_request_ptr:         .res 2
arr_kind:                .res 1
arr_dimensions:          .res 1
arr_element_size:        .res 1
arr_arena_generation:    .res 1
arr_start_page:          .res 1
arr_page_count:          .res 1
arr_total:               .res 2
arr_bound0:              .res 2
arr_bound1:              .res 2
arr_sub0:                .res 2
arr_sub1:                .res 2
arr_index:               .res 2
arr_multiplier:          .res 2
arr_offset:              .res 2
arr_candidate:           .res 1
arr_scan:                .res 1
arr_run:                 .res 1
arr_owner_value:         .res 1
arr_store_value:         .res 3
arr_claimed_total:       .res 2
arr_claimed_pages:       .res 1
arr_float_value:         .res 5
arr_string_old:          .res 12
arr_string_new:          .res 12
arr_string_request:      .res 6

.segment "CODE"

; arr_reset - Release all array suballocator ownership.
; Input: none. Output: C clear. Clobbers: A, X and flags.
; Side effects: invalidates all existing AD page ownership.
.export arr_reset
arr_reset:
    lda #0
    ldx #ARRAY_PAGE_CAPACITY-1
@clear:
    sta arr_page_owner,x
    dex
    bpl @clear
    inc arr_generation_counter
    clc
    rts

arr_error_illegal:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

arr_error_redim:
    lda #ERR_REDIM_ARRAY
    sec
    rts

arr_error_bad_subscript:
    lda #ERR_BAD_SUBSCRIPT
    sec
    rts

; Point zp_src at arr_request_ptr.
.proc arr_request_to_zp
    lda arr_request_ptr
    sta zp_src
    lda arr_request_ptr+1
    sta zp_src+1
    rts
.endproc

; Point zp_src at arr_descriptor_ptr.
.proc arr_descriptor_to_zp
    lda arr_descriptor_ptr
    sta zp_src
    lda arr_descriptor_ptr+1
    sta zp_src+1
    rts
.endproc

.proc arr_kind_to_size
    lda arr_kind
    cmp #ARRAY_KIND_INT
    beq @int
    cmp #ARRAY_KIND_FLOAT
    bne @string
    jmp @float
@string:
    cmp #ARRAY_KIND_STRING
    jne arr_error_illegal
    lda #12
    sta arr_element_size
    clc
    rts
@int:
    lda #2
    sta arr_element_size
    clc
    rts
@float:
    lda #5
    sta arr_element_size
    clc
    rts
.endproc

; Validate and load a live AD descriptor.
.proc arr_load_descriptor
    stx arr_descriptor_ptr
    sty arr_descriptor_ptr+1
    jsr arr_descriptor_to_zp
    ldy #0
    lda (zp_src),y
    cmp #'A'
    jne arr_error_illegal
    iny
    lda (zp_src),y
    cmp #'D'
    jne arr_error_illegal
    ldy #AD_KIND
    lda (zp_src),y
    sta arr_kind
    jsr arr_kind_to_size
    jcs arr_error_illegal
    ldy #AD_GENERATION
    lda (zp_src),y
    jeq arr_error_illegal
    sta arr_owner_value
    ldy #AD_DIMENSIONS
    lda (zp_src),y
    cmp #1
    beq @dimensions
    cmp #2
    jne arr_error_illegal
@dimensions:
    sta arr_dimensions
    iny
    lda (zp_src),y
    cmp arr_element_size
    jne arr_error_illegal
    ldy #AD_ARENA
    lda (zp_src),y
    cmp #ARRAY_ARENA
    jne arr_error_illegal
    iny
    lda (zp_src),y
    sta arr_arena_generation
    tay
    ldx #ARRAY_ARENA
    jsr arena_handle_valid
    jcs arr_error_illegal
    jsr arr_descriptor_to_zp
    ldy #AD_START_PAGE
    lda (zp_src),y
    sta arr_start_page
    iny
    lda (zp_src),y
    jeq arr_error_illegal
    sta arr_page_count
    clc
    adc arr_start_page
    jcs arr_error_illegal
    cmp #ARRAY_PAGE_CAPACITY + 1
    jcs arr_error_illegal
    ldy #AD_TOTAL_LO
    lda (zp_src),y
    sta arr_total
    iny
    lda (zp_src),y
    sta arr_total+1
    lda arr_total
    ora arr_total+1
    jeq arr_error_illegal
    lda arr_total
    sta arr_claimed_total
    lda arr_total+1
    sta arr_claimed_total+1
    lda arr_page_count
    sta arr_claimed_pages
    iny
    lda (zp_src),y
    sta arr_bound0
    iny
    lda (zp_src),y
    sta arr_bound0+1
    iny
    lda (zp_src),y
    sta arr_bound1
    iny
    lda (zp_src),y
    sta arr_bound1+1
    jsr arr_compute_total
    jcs arr_error_illegal
    lda arr_total
    cmp arr_claimed_total
    jne arr_error_illegal
    lda arr_total+1
    cmp arr_claimed_total+1
    jne arr_error_illegal
    jsr arr_compute_page_count
    jcs arr_error_illegal
    lda arr_page_count
    cmp arr_claimed_pages
    jne arr_error_illegal
    ; Every page must still belong to this descriptor generation.
    ldx arr_start_page
    lda arr_page_count
    sta arr_run
@owner:
    lda arr_page_owner,x
    cmp arr_owner_value
    jne arr_error_illegal
    inx
    dec arr_run
    bne @owner
    clc
    rts
.endproc

; Parse AM request and load requested shape.
.proc arr_parse_dim_request
    stx arr_request_ptr
    sty arr_request_ptr+1
    jsr arr_request_to_zp
    ldy #0
    lda (zp_src),y
    cmp #'A'
    jne arr_error_illegal
    iny
    lda (zp_src),y
    cmp #'M'
    jne arr_error_illegal
    iny
    lda (zp_src),y
    sta arr_descriptor_ptr
    iny
    lda (zp_src),y
    sta arr_descriptor_ptr+1
    iny
    lda (zp_src),y
    sta arr_kind
    jsr arr_kind_to_size
    jcs arr_error_illegal
    lda #ARRAY_ARENA_GENERATION
    sta arr_arena_generation
    jsr arr_request_to_zp
    ldy #5
    lda (zp_src),y
    cmp #1
    beq @dimensions
    cmp #2
    jne arr_error_illegal
@dimensions:
    sta arr_dimensions
    iny
    lda (zp_src),y
    iny
    ora (zp_src),y
    jne arr_error_illegal
    iny
    lda (zp_src),y
    sta arr_bound0
    iny
    lda (zp_src),y
    sta arr_bound0+1
    iny
    lda (zp_src),y
    sta arr_bound1
    iny
    lda (zp_src),y
    sta arr_bound1+1
    iny
    lda (zp_src),y
    iny
    ora (zp_src),y
    jne arr_error_illegal
    lda arr_dimensions
    cmp #1
    bne @ok
    lda arr_bound1
    ora arr_bound1+1
    jne arr_error_illegal
@ok:
    clc
    rts
.endproc

; Reject a live AD descriptor. Any other bytes are treated as empty storage.
.proc arr_require_empty
    jsr arr_descriptor_to_zp
    ldy #0
    lda (zp_src),y
    cmp #'A'
    bne @empty
    iny
    lda (zp_src),y
    cmp #'D'
    bne @empty
    ldy #AD_GENERATION
    lda (zp_src),y
    jne arr_error_redim
@empty:
    clc
    rts
.endproc

; total=(bound0+1) for 1D, or (bound0+1)*(bound1+1) for 2D.
.proc arr_compute_total
    lda arr_bound0
    clc
    adc #1
    sta arr_total
    lda arr_bound0+1
    adc #0
    sta arr_total+1
    jcs arr_error_illegal
    lda arr_total
    ora arr_total+1
    jeq arr_error_illegal
    lda arr_dimensions
    cmp #1
    beq @done
    lda arr_bound1
    clc
    adc #1
    sta arr_multiplier
    lda arr_bound1+1
    adc #0
    sta arr_multiplier+1
    jcs arr_error_illegal
    lda arr_multiplier
    ora arr_multiplier+1
    jeq arr_error_illegal
    lda arr_total
    sta arr_index
    lda arr_total+1
    sta arr_index+1
    lda #0
    sta arr_total
    sta arr_total+1
@multiply:
    lda arr_total
    clc
    adc arr_index
    sta arr_total
    lda arr_total+1
    adc arr_index+1
    sta arr_total+1
    jcs arr_error_illegal
    lda arr_multiplier
    bne :+
    dec arr_multiplier+1
:
    dec arr_multiplier
    lda arr_multiplier
    ora arr_multiplier+1
    bne @multiply
@done:
    clc
    rts
.endproc

; page_count=ceil(total*element_size/256), rejecting >64 pages.
.proc arr_compute_page_count
    lda #0
    sta arr_offset
    sta arr_offset+1
    lda arr_element_size
    sta arr_run
@add:
    lda arr_offset
    clc
    adc arr_total
    sta arr_offset
    lda arr_offset+1
    adc arr_total+1
    sta arr_offset+1
    jcs arr_error_illegal
    dec arr_run
    bne @add
    lda arr_offset+1
    sta arr_page_count
    lda arr_offset
    beq :+
    inc arr_page_count
:
    lda arr_page_count
    jeq arr_error_illegal
    cmp #ARRAY_PAGE_CAPACITY + 1
    jcs arr_error_illegal
    clc
    rts
.endproc

; Find and claim a contiguous first-fit page run.
.proc arr_allocate_pages
    lda #0
    sta arr_candidate
@candidate:
    lda arr_candidate
    clc
    adc arr_page_count
    jcs arr_error_illegal
    cmp #ARRAY_PAGE_CAPACITY + 1
    jcs arr_error_illegal
    lda arr_candidate
    sta arr_scan
    lda #0
    sta arr_run
@scan:
    ldx arr_scan
    lda arr_page_owner,x
    bne @next_candidate
    inc arr_scan
    inc arr_run
    lda arr_run
    cmp arr_page_count
    bne @scan
    inc arr_generation_counter
    bne :+
    inc arr_generation_counter
:
    lda arr_generation_counter
    sta arr_owner_value
    ldx arr_candidate
    lda arr_page_count
    sta arr_run
@claim:
    lda arr_owner_value
    sta arr_page_owner,x
    inx
    dec arr_run
    bne @claim
    lda arr_candidate
    sta arr_start_page
    clc
    rts
@next_candidate:
    inc arr_candidate
    jmp @candidate
.endproc

.proc arr_release_pages
    ldx arr_start_page
    lda arr_page_count
    sta arr_run
@release:
    lda #0
    sta arr_page_owner,x
    inx
    dec arr_run
    bne @release
    clc
    rts
.endproc

.proc arr_clear_payload
    lda #0
    sta arr_scan
@page:
    lda arr_start_page
    clc
    adc arr_scan
    ldx #ARRAY_ARENA
    ldy #ARRAY_ARENA_GENERATION
    jsr arena_select_page
    jcs @error
    lda #0
    ldy #0
@byte:
    sta $DE00,y
    iny
    bne @byte
    inc arr_scan
    lda arr_scan
    cmp arr_page_count
    bne @page
    clc
    rts
@error:
    jmp arr_error_illegal
.endproc

.proc arr_publish_descriptor
    jsr arr_descriptor_to_zp
    ldy #0
    lda #'A'
    sta (zp_src),y
    iny
    lda #'D'
    sta (zp_src),y
    ldy #AD_KIND
    lda arr_kind
    sta (zp_src),y
    iny
    lda arr_owner_value
    sta (zp_src),y
    iny
    lda arr_dimensions
    sta (zp_src),y
    iny
    lda arr_element_size
    sta (zp_src),y
    iny
    lda #ARRAY_ARENA
    sta (zp_src),y
    iny
    lda #ARRAY_ARENA_GENERATION
    sta (zp_src),y
    iny
    lda arr_start_page
    sta (zp_src),y
    iny
    lda arr_page_count
    sta (zp_src),y
    iny
    lda arr_total
    sta (zp_src),y
    iny
    lda arr_total+1
    sta (zp_src),y
    iny
    lda arr_bound0
    sta (zp_src),y
    iny
    lda arr_bound0+1
    sta (zp_src),y
    iny
    lda arr_bound1
    sta (zp_src),y
    iny
    lda arr_bound1+1
    sta (zp_src),y
    clc
    rts
.endproc

; Parse AE or AS request. A=second magic byte.
.proc arr_parse_element_request
    sta arr_store_value
    stx arr_request_ptr
    sty arr_request_ptr+1
    jsr arr_request_to_zp
    ldy #0
    lda (zp_src),y
    cmp #'A'
    jne arr_error_illegal
    iny
    lda (zp_src),y
    cmp arr_store_value
    jne arr_error_illegal
    iny
    lda (zp_src),y
    sta arr_descriptor_ptr
    iny
    lda (zp_src),y
    sta arr_descriptor_ptr+1
    iny
    lda (zp_src),y
    sta arr_sub0
    iny
    lda (zp_src),y
    sta arr_sub0+1
    iny
    lda (zp_src),y
    sta arr_sub1
    iny
    lda (zp_src),y
    sta arr_sub1+1
    ldx arr_descriptor_ptr
    ldy arr_descriptor_ptr+1
    jmp arr_load_descriptor
.endproc

.proc arr_check_subscripts
    lda arr_sub0+1
    cmp arr_bound0+1
    bcc @sub0_ok
    jne arr_error_bad_subscript
    lda arr_sub0
    cmp arr_bound0
    bcc @sub0_ok
    beq @sub0_ok
    jmp arr_error_bad_subscript
@sub0_ok:
    lda arr_dimensions
    cmp #1
    bne @sub1
    lda arr_sub1
    ora arr_sub1+1
    jne arr_error_bad_subscript
    clc
    rts
@sub1:
    lda arr_sub1+1
    cmp arr_bound1+1
    bcc @ok
    jne arr_error_bad_subscript
    lda arr_sub1
    cmp arr_bound1
    bcc @ok
    beq @ok
    jmp arr_error_bad_subscript
@ok:
    clc
    rts
.endproc

; Compute row-major element index.
.proc arr_compute_index
    lda arr_dimensions
    cmp #1
    bne @two
    lda arr_sub0
    sta arr_index
    lda arr_sub0+1
    sta arr_index+1
    clc
    rts
@two:
    lda arr_bound1
    clc
    adc #1
    sta arr_multiplier
    lda arr_bound1+1
    adc #0
    sta arr_multiplier+1
    lda #0
    sta arr_index
    sta arr_index+1
    lda arr_sub0
    sta arr_total
    lda arr_sub0+1
    sta arr_total+1
@multiply:
    lda arr_total
    ora arr_total+1
    beq @add_sub1
    lda arr_index
    clc
    adc arr_multiplier
    sta arr_index
    lda arr_index+1
    adc arr_multiplier+1
    sta arr_index+1
    jcs arr_error_bad_subscript
    lda arr_total
    bne :+
    dec arr_total+1
:
    dec arr_total
    jmp @multiply
@add_sub1:
    lda arr_index
    clc
    adc arr_sub1
    sta arr_index
    lda arr_index+1
    adc arr_sub1+1
    sta arr_index+1
    jcs arr_error_bad_subscript
    clc
    rts
.endproc

; Resolve loaded descriptor/subscripts to selected $DE00 cell.
.proc arr_resolve_loaded
    jsr arr_check_subscripts
    jcs @error
    jsr arr_compute_index
    jcs @error
    lda #0
    sta arr_offset
    sta arr_offset+1
    lda arr_element_size
    sta arr_run
@scale:
    lda arr_offset
    clc
    adc arr_index
    sta arr_offset
    lda arr_offset+1
    adc arr_index+1
    sta arr_offset+1
    jcs arr_error_bad_subscript
    dec arr_run
    bne @scale
    lda arr_offset+1
    cmp arr_page_count
    jcs arr_error_bad_subscript
    clc
    adc arr_start_page
    ldx #ARRAY_ARENA
    ldy arr_arena_generation
    jsr arena_select_page
    jcs @error
    ldx arr_offset
    ldy #$DE
    clc
    rts
@error:
    rts
.endproc

; Select the geoRAM page containing arr_offset and return its byte index in X.
.proc arr_select_offset
    lda arr_offset+1
    cmp arr_page_count
    jcs arr_error_bad_subscript
    clc
    adc arr_start_page
    ldx #ARRAY_ARENA
    ldy arr_arena_generation
    jsr arena_select_page
    jcs @error
    ldx arr_offset
    clc
@error:
    rts
.endproc

.proc arr_advance_offset
    inc arr_offset
    bne :+
    inc arr_offset+1
:
    rts
.endproc

.proc arr_read_string_cell
    lda #0
    sta arr_run
@copy:
    jsr arr_select_offset
    jcs @error
    lda $DE00,x
    ldy arr_run
    sta arr_string_old,y
    jsr arr_advance_offset
    inc arr_run
    lda arr_run
    cmp #12
    bne @copy
    clc
@error:
    rts
.endproc

.proc arr_write_string_cell
    lda #0
    sta arr_run
@copy:
    jsr arr_select_offset
    jcs @error
    ldy arr_run
    lda arr_string_new,y
    sta $DE00,x
    jsr arr_advance_offset
    inc arr_run
    lda arr_run
    cmp #12
    bne @copy
    clc
@error:
    rts
.endproc

.proc arr_copy_string
    lda #'S'
    sta arr_string_request
    lda #'X'
    sta arr_string_request+1
    lda zp_dest
    sta arr_string_request+2
    lda zp_dest+1
    sta arr_string_request+3
    lda zp_src
    sta arr_string_request+4
    lda zp_src+1
    sta arr_string_request+5
    ldx #<arr_string_request
    ldy #>arr_string_request
    jmp str_copy
.endproc

.proc arr_init_string_payload
    lda arr_kind
    cmp #ARRAY_KIND_STRING
    bne @done
    lda #'S'
    sta arr_string_new
    lda #'D'
    sta arr_string_new+1
    lda #1
    sta arr_string_new+2
    lda #0
    sta arr_string_new+3
    lda #ARENA_TYPE_STRINGS
    sta arr_string_new+4
    lda #1
    sta arr_string_new+5
    lda #0
    ldx #6
@zero:
    sta arr_string_new,x
    inx
    cpx #12
    bne @zero
    lda #0
    sta arr_offset
    sta arr_offset+1
    lda arr_total
    sta arr_index
    lda arr_total+1
    sta arr_index+1
@cell:
    jsr arr_write_string_cell
    jcs @error
    lda arr_index
    bne :+
    dec arr_index+1
:
    dec arr_index
    lda arr_index
    ora arr_index+1
    bne @cell
@done:
    clc
@error:
    rts
.endproc

; arr_dim - dimension and allocate one typed array.
.export arr_dim
arr_dim:
    jsr arr_parse_dim_request
    jcs @error
    jsr arr_require_empty
    jcs @error
    jsr arr_compute_total
    jcs @error
    jsr arr_compute_page_count
    jcs @error
    jsr arr_allocate_pages
    jcs @error
    jsr arr_clear_payload
    bcs @rollback
    jsr arr_init_string_payload
    bcc @publish
@rollback:
    jsr arr_release_pages
    sec
    rts
@publish:
    jmp arr_publish_descriptor
@error:
    rts

; arr_resolve_element - resolve AE request to selected geoRAM cell.
.export arr_resolve_element
arr_resolve_element:
    lda #'E'
    jsr arr_parse_element_request
    jcs @error
    jmp arr_resolve_loaded
@error:
    rts

; arr_load_element - load typed element through AE request.
.export arr_load_element
arr_load_element:
    jsr arr_resolve_element
    jcs @error
    lda arr_kind
    cmp #ARRAY_KIND_INT
    beq @int
    cmp #ARRAY_KIND_FLOAT
    beq @float
    jsr arr_read_string_cell
    jcs @error
    jsr arr_request_to_zp
    ldy #8
    lda (zp_src),y
    sta zp_dest
    iny
    lda (zp_src),y
    sta zp_dest+1
    iny
    lda (zp_src),y
    iny
    ora (zp_src),y
    jne arr_error_illegal
    lda #<arr_string_old
    sta zp_src
    lda #>arr_string_old
    sta zp_src+1
    jmp arr_copy_string
@int:
    jsr arr_select_offset
    jcs @error
    lda $DE00,x
    sta arr_store_value
    jsr arr_advance_offset
    jsr arr_select_offset
    jcs @error
    ldy $DE00,x
    ldx arr_store_value
    clc
    rts
@float:
    lda #0
    sta arr_run
@float_copy:
    jsr arr_select_offset
    jcs @error
    lda $DE00,x
    ldy arr_run
    sta zp_fac1,y
    jsr arr_advance_offset
    inc arr_run
    lda arr_run
    cmp #5
    bne @float_copy
    clc
    rts
@error:
    rts

; arr_store_element - store typed element through AS request.
.export arr_store_element
arr_store_element:
    stx arr_request_ptr
    sty arr_request_ptr+1
    ldy #0
@save_fac:
    lda zp_fac1,y
    sta arr_float_value,y
    iny
    cpy #5
    bne @save_fac
    ldx arr_request_ptr
    ldy arr_request_ptr+1
    lda #'S'
    jsr arr_parse_element_request
    jcs @error
    jsr arr_request_to_zp
    ldy #8
    lda (zp_src),y
    sta arr_store_value
    iny
    lda (zp_src),y
    sta arr_store_value+1
    iny
    lda (zp_src),y
    sta arr_store_value+2
    iny
    lda (zp_src),y
    jne arr_error_illegal
    jsr arr_resolve_loaded
    jcs @error
    lda arr_kind
    cmp #ARRAY_KIND_INT
    beq @int
    cmp #ARRAY_KIND_FLOAT
    bne @string
    jmp @float
@string:
    lda #<arr_string_new
    sta zp_dest
    lda #>arr_string_new
    sta zp_dest+1
    lda arr_store_value
    sta zp_src
    lda arr_store_value+1
    sta zp_src+1
    jsr arr_copy_string
    jcs @error
    jsr arr_resolve_loaded
    jcs @release_new
    jsr arr_read_string_cell
    jcs @release_new
    sec
    lda arr_offset
    sbc #12
    sta arr_offset
    lda arr_offset+1
    sbc #0
    sta arr_offset+1
    jsr arr_write_string_cell
    jcs @release_new
    ; Ownership moved to the array cell. Remove the temporary alias without
    ; releasing it; a later str_copy must not treat the staging SD as live.
    lda #0
    ldx #0
@clear_new:
    sta arr_string_new,x
    inx
    cpx #12
    bne @clear_new
    ldx #<arr_string_old
    ldy #>arr_string_old
    jmp str_free
@release_new:
    ldx #<arr_string_new
    ldy #>arr_string_new
    jsr str_free
    sec
    rts
@int:
    jsr arr_select_offset
    jcs @error
    lda arr_store_value
    sta $DE00,x
    jsr arr_advance_offset
    jsr arr_select_offset
    jcs @error
    lda arr_store_value+1
    sta $DE00,x
    clc
    rts
@float:
    lda arr_store_value
    ora arr_store_value+1
    ora arr_store_value+2
    jne arr_error_illegal
    lda #0
    sta arr_run
@float_copy:
    jsr arr_select_offset
    jcs @error
    ldy arr_run
    lda arr_float_value,y
    sta $DE00,x
    jsr arr_advance_offset
    inc arr_run
    lda arr_run
    cmp #5
    bne @float_copy
    clc
    rts
@error:
    rts

; arr_redim - reject a live AD descriptor.
.export arr_redim
arr_redim:
    stx arr_descriptor_ptr
    sty arr_descriptor_ptr+1
    jsr arr_require_empty
    bcc @invalid
    rts
@invalid:
    jmp arr_error_illegal

; arr_free - release pages and clear AD descriptor.
.export arr_free
arr_free:
    jsr arr_load_descriptor
    jcs @error
    lda arr_kind
    cmp #ARRAY_KIND_STRING
    bne @release
    lda #0
    sta arr_offset
    sta arr_offset+1
    lda arr_total
    sta arr_index
    lda arr_total+1
    sta arr_index+1
@free_string:
    jsr arr_read_string_cell
    jcs @error
    ldx #<arr_string_old
    ldy #>arr_string_old
    jsr str_free
    jcs @error
    lda arr_index
    bne :+
    dec arr_index+1
:
    dec arr_index
    lda arr_index
    ora arr_index+1
    bne @free_string
@release:
    jsr arr_release_pages
    jsr arr_descriptor_to_zp
    lda #0
    ldy #0
@clear:
    sta (zp_src),y
    iny
    cpy #16
    bne @clear
    clc
    rts
@error:
    rts

; arr_check_bounds - direct helper retained as a typed primitive.
.export arr_check_bounds
arr_check_bounds:
    sta arr_bound0
    lda #0
    sta arr_bound0+1
    stx arr_sub0
    sty arr_sub0+1
    lda arr_sub0+1
    jne arr_error_bad_subscript
    lda arr_sub0
    cmp arr_bound0
    jcs arr_error_bad_subscript
    clc
    rts
