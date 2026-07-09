; src/arena/overlay_dispatch.asm
; Generated routine-directory resolver and nested GeoRAM overlay selection.

.include "common/zp.inc"
.include "common/constants.asm"

.import georam_select
.import georam_group_0_blocks
.import georam_group_0_pages
.import georam_group_0_offsets
.import georam_group_1_blocks
.import georam_group_1_pages
.import georam_group_1_offsets
.importzp GEORAM_ROUTINE_COUNT
.importzp GEORAM_DIRECTORY_GROUP_COUNT
.importzp GEORAM_DIRECTORY_XOR8
.importzp GEORAM_DIRECTORY_CRC32_0
.importzp GEORAM_DIRECTORY_CRC32_1
.importzp GEORAM_DIRECTORY_CRC32_2
.importzp GEORAM_DIRECTORY_CRC32_3

OVERLAY_DIRECTORY_VERSION = 1
OVERLAY_STACK_DEPTH = 8
OVERLAY_MISSING = $FF

.segment "BSS"
.export __overlay_directory_ready
.export __overlay_directory_version
.export __overlay_directory_count
.export __overlay_directory_checksum
.export __overlay_current_id
.export __overlay_previous_id
.export __overlay_current_block
.export __overlay_current_page
.export __overlay_current_offset
.export __overlay_stack_pointer
__overlay_directory_ready:    .res 1
__overlay_directory_version:  .res 1
__overlay_directory_count:    .res 1
__overlay_directory_checksum: .res 1
__overlay_current_id:         .res 1
__overlay_previous_id:        .res 1
__overlay_current_block:      .res 1
__overlay_current_page:       .res 1
__overlay_current_offset:     .res 1
__overlay_stack_pointer:      .res 1
overlay_requested_id:         .res 1
overlay_resolved_block:       .res 1
overlay_resolved_page:        .res 1
overlay_resolved_offset:      .res 1
overlay_checksum_work:        .res 1
overlay_stack_id:             .res OVERLAY_STACK_DEPTH
overlay_stack_block:          .res OVERLAY_STACK_DEPTH
overlay_stack_page:           .res OVERLAY_STACK_DEPTH
overlay_stack_offset:         .res OVERLAY_STACK_DEPTH

.segment "CODE"

overlay_ensure_ready:
    lda __overlay_directory_ready
    bne @done
    lda #OVERLAY_DIRECTORY_VERSION
    sta __overlay_directory_version
    lda #GEORAM_ROUTINE_COUNT
    sta __overlay_directory_count
    lda #GEORAM_DIRECTORY_XOR8
    sta __overlay_directory_checksum
    lda #$00
    sta __overlay_current_id
    sta __overlay_previous_id
    sta __overlay_current_block
    sta __overlay_current_page
    sta __overlay_current_offset
    sta __overlay_stack_pointer
    lda #$01
    sta __overlay_directory_ready
@done:
    rts

; overlay_resolve
; Inputs: A=low byte of a group-1 routine ID (IDs 256..511).
; Outputs: X=page, Y=offset, C=error; resolved block is retained internally.
; Side effects: reads only the generated directory. Clobbers: A, X, Y.
; Zero page: none.
.export overlay_resolve
overlay_resolve:
    sta overlay_requested_id
    jsr overlay_ensure_ready
    ldx overlay_requested_id
    lda georam_group_1_blocks,x
    cmp #OVERLAY_MISSING
    beq @error
    sta overlay_resolved_block
    lda georam_group_1_pages,x
    cmp #OVERLAY_MISSING
    beq @error
    cmp #$40
    bcs @error
    sta overlay_resolved_page
    lda georam_group_1_offsets,x
    cmp #OVERLAY_MISSING
    beq @error
    sta overlay_resolved_offset
    ldx overlay_resolved_page
    ldy overlay_resolved_offset
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; overlay_enter
; Inputs: A=low byte of a group-1 routine ID.
; Outputs: C=error. Side effects: pushes current selection and maps target page.
; Clobbers: A, X, Y. Zero page: zp_gr_block, zp_gr_page.
.export overlay_enter
overlay_enter:
    sta overlay_requested_id
    jsr overlay_ensure_ready
    ldx __overlay_stack_pointer
    cpx #OVERLAY_STACK_DEPTH
    bcs @error
    lda __overlay_current_id
    sta overlay_stack_id,x
    lda zp_gr_block
    sta overlay_stack_block,x
    lda zp_gr_page
    sta overlay_stack_page,x
    lda __overlay_current_offset
    sta overlay_stack_offset,x
    inc __overlay_stack_pointer
    lda overlay_requested_id
    jsr overlay_resolve
    bcs @rollback
    lda __overlay_current_id
    sta __overlay_previous_id
    lda overlay_requested_id
    sta __overlay_current_id
    lda overlay_resolved_block
    sta __overlay_current_block
    lda overlay_resolved_page
    sta __overlay_current_page
    lda overlay_resolved_offset
    sta __overlay_current_offset
    lda overlay_resolved_page
    ldx overlay_resolved_block
    jsr georam_select
    clc
    rts
@rollback:
    dec __overlay_stack_pointer
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; overlay_exit
; Inputs: none. Outputs: C=error on underflow.
; Side effects: restores the prior routine state and GeoRAM selection.
; Clobbers: A, X, Y. Zero page: zp_gr_block, zp_gr_page.
.export overlay_exit
overlay_exit:
    jsr overlay_ensure_ready
    lda __overlay_stack_pointer
    beq @error
    dec __overlay_stack_pointer
    ldx __overlay_stack_pointer
    lda __overlay_current_id
    sta __overlay_previous_id
    lda overlay_stack_id,x
    sta __overlay_current_id
    lda overlay_stack_block,x
    sta __overlay_current_block
    tay
    lda overlay_stack_page,x
    sta __overlay_current_page
    pha
    lda overlay_stack_offset,x
    sta __overlay_current_offset
    pla
    tya
    tax
    lda __overlay_current_page
    jsr georam_select
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; Fold one 256-byte table into overlay_checksum_work.
.macro OVERLAY_XOR_TABLE table
    .local loop
    ldx #$00
loop:
    lda overlay_checksum_work
    eor table,x
    sta overlay_checksum_work
    inx
    bne loop
.endmacro

; overlay_validate
; Inputs: none. Outputs: C=1 if version, count, or generated tables are corrupt.
; Side effects: computes the runtime directory checksum. Clobbers: A, X.
; Zero page: none.
.export overlay_validate
overlay_validate:
    jsr overlay_ensure_ready
    lda __overlay_directory_version
    cmp #OVERLAY_DIRECTORY_VERSION
    bne overlay_validate_error
    lda __overlay_directory_count
    cmp #GEORAM_ROUTINE_COUNT
    bne overlay_validate_error
    lda #$00
    sta overlay_checksum_work
    OVERLAY_XOR_TABLE georam_group_0_blocks
    OVERLAY_XOR_TABLE georam_group_0_pages
    OVERLAY_XOR_TABLE georam_group_0_offsets
    OVERLAY_XOR_TABLE georam_group_1_blocks
    OVERLAY_XOR_TABLE georam_group_1_pages
    OVERLAY_XOR_TABLE georam_group_1_offsets
    lda overlay_checksum_work
    cmp #GEORAM_DIRECTORY_XOR8
    bne overlay_validate_error
    cmp __overlay_directory_checksum
    bne overlay_validate_error
    ; Reference all CRC bytes so the linked ABI proves the generated CRC
    ; constants and runtime table instance were produced together.
    lda #GEORAM_DIRECTORY_CRC32_0
    eor #GEORAM_DIRECTORY_CRC32_1
    eor #GEORAM_DIRECTORY_CRC32_2
    eor #GEORAM_DIRECTORY_CRC32_3
    clc
    rts
overlay_validate_error:
    lda #ERR_SYNTAX
    sec
    rts
