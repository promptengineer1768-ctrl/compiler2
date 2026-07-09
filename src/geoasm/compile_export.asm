; src/geoasm/compile_export.asm
; Validates the records used to construct and write a source-free standalone
; image. Image construction remains a separate compiler/linker responsibility.

.include "common/zp.inc"
.include "common/constants.asm"

.import kernal_setnam, kernal_setlfs, kernal_save

EXPORT_MIN_DEVICE = 8
EXPORT_MAX_DEVICE = 11
EXPORT_FORBIDDEN_DEPENDENCIES = $F0
EXPORT_LINKED_STANDALONE = $01

.segment "RODATA"
export_default_filename:
    .byte "COMPILED"
EXPORT_DEFAULT_FILENAME_LEN = 8

.segment "BSS"
; EO: magic, name:u16, length:arg-byte, device:arg-byte, secondary:arg-byte.
export_options:
    .res 7
export_record:
    .res 2
export_start:
    .res 2
export_end:
    .res 2
export_workspace_start:
    .res 2
export_workspace_end:
    .res 2
export_command_record:
    .res 2

.segment "GEOASM"

.macro jcs target
    bcc *+5
    jmp target
.endmacro

; export_compile_command - Execute a fully prepared standalone export plan.
; Input: X/Y -> contiguous CP(6), ED(3), EL(3), EB(10), EW(11) records.
; Output: C clear after the image is saved; C set/A=error at the first rejected
; record or KERNAL failure.  The compiler/linker owns record construction; this
; routine is the single production transaction that admits and writes it.
; Clobbers: A, X, Y. Side effects: canonicalizes CP and may write a PRG.
; Zero page: zp_src.
.export export_compile_command
export_compile_command:
    stx export_command_record
    sty export_command_record+1
    jsr export_parse_command
    bcs @done
    lda #6
    jsr @record_at_offset
    jsr export_collect_dependencies
    bcs @done
    lda #9
    jsr @record_at_offset
    jsr export_link_image
    bcs @done
    lda #12
    jsr @record_at_offset
    jsr export_check_budgets
    bcs @done
    lda #22
    jsr @record_at_offset
    jmp export_write_prg
@done:
    rts
@record_at_offset:
    clc
    adc export_command_record
    tax
    lda export_command_record+1
    adc #0
    tay
    rts

; Validate the device in A. Devices 8 through 11 are supported.
.proc export_validate_device
    cmp #EXPORT_MIN_DEVICE
    bcc @error
    cmp #(EXPORT_MAX_DEVICE + 1)
    bcs @error
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; export_parse_command - Canonicalize a CP command record.
; Input: X/Y -> CP, name:u16, length:arg-byte, device:arg-byte. A zero length
; selects "COMPILED"; a zero device selects KERNAL fa at $BA.
; Output: X/Y -> persistent EO options, C clear; A=error and C set on failure.
; Clobbers: A, X, Y. Side effects: replaces export_options.
; Zero page: zp_src.
.export export_parse_command
export_parse_command:
    stx export_record
    sty export_record+1
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src),y
    cmp #'C'
    bne @error
    iny
    lda (zp_src),y
    cmp #'P'
    bne @error
    lda #'E'
    sta (zp_src),y
    iny
    lda #'O'
    sta (zp_src),y
    ldy #4
    lda (zp_src),y
    beq @default_name
    dey
    lda (zp_src),y
    dey
    ora (zp_src),y
    beq @error
    jmp @device
@default_name:
    ldy #2
    lda #<export_default_filename
    sta (zp_src),y
    iny
    lda #>export_default_filename
    sta (zp_src),y
    iny
    lda #EXPORT_DEFAULT_FILENAME_LEN
    sta (zp_src),y
@device:
    ldy #5
    lda (zp_src),y
    bne @validate_device
    lda $BA
@validate_device:
    jsr export_validate_device
    bcs @return_error
    ldy #5
    sta (zp_src),y
    iny
    lda #0
    sta (zp_src),y
    ldx export_record
    ldy export_record+1
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
@return_error:
    sec
    rts

; export_collect_dependencies - Validate a closed ED dependency bitmap.
; Input: X/Y -> "ED", flags. Bits 0..3 are standalone runtime classes; bits
; 4..7 mean editor/compiler/source/geoRAM and are rejected.
; Output: original X/Y and C clear, or A=ERR_ILLEGAL_QUANTITY and C set.
; Clobbers: A, X, Y. Side effects: none. Zero page: zp_src.
.export export_collect_dependencies
export_collect_dependencies:
    stx export_record
    sty export_record+1
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src),y
    cmp #'E'
    beq @magic_e_ok
    jmp @error
@magic_e_ok:
    iny
    lda (zp_src),y
    cmp #'D'
    bne @error
    iny
    lda (zp_src),y
    and #EXPORT_FORBIDDEN_DEPENDENCIES
    bne @error
    ldx export_record
    ldy export_record+1
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; export_link_image - Admit an image produced by the standalone linker.
; Input: X/Y -> "EL", flags. Bit 0 proves relocation/runtime closure is already
; resolved by the owning linker. This routine does not pretend to link bytes.
; Output: original X/Y and C clear, or A=ERR_ILLEGAL_QUANTITY and C set.
; Clobbers: A, X, Y. Side effects: none. Zero page: zp_src.
.export export_link_image
export_link_image:
    stx export_record
    sty export_record+1
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src),y
    cmp #'E'
    bne @error
    iny
    lda (zp_src),y
    cmp #'L'
    bne @error
    iny
    lda (zp_src),y
    and #EXPORT_LINKED_STANDALONE
    beq @error
    ldx export_record
    ldy export_record+1
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; export_check_budgets - Validate an EB range plan.
; Input: X/Y -> "EB", image_start:u16, image_end_exclusive:u16,
; workspace_start:u16, workspace_end_exclusive:u16.
; The nonempty image must lie in $0801..$CFFF and workspace must not overlap it.
; Output: C clear, or A=ERR_OUT_OF_MEMORY and C set.
; Clobbers: A, X, Y. Side effects: replaces range scratch. Zero page: zp_src.
.export export_check_budgets
export_check_budgets:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src),y
    cmp #'E'
    beq @budget_magic_e_ok
    jmp @error
@budget_magic_e_ok:
    iny
    lda (zp_src),y
    cmp #'B'
    bne @error
    ldx #0
@copy_words:
    iny
    lda (zp_src),y
    sta export_start,x
    inx
    cpx #8
    bne @copy_words

    ; image_start >= $0801
    lda export_start+1
    cmp #$08
    bcc @error
    bne @start_ok
    lda export_start
    cmp #$01
    bcc @error
@start_ok:
    ; image_end <= $D000 and image_start < image_end.
    lda export_end+1
    cmp #$D0
    bcc @end_ceiling_ok
    bne @error
    lda export_end
    bne @error
@end_ceiling_ok:
    lda export_start+1
    cmp export_end+1
    bcc @image_order_ok
    bne @error
    lda export_start
    cmp export_end
    bcs @error
@image_order_ok:
    ; Reject reversed workspace ranges.
    lda export_workspace_start+1
    cmp export_workspace_end+1
    bcc @workspace_order_ok
    bne @error
    lda export_workspace_start
    cmp export_workspace_end
    bcc @workspace_order_ok
    beq @success
    bcs @error
@workspace_order_ok:
    ; Disjoint if workspace_end <= image_start.
    lda export_workspace_end+1
    cmp export_start+1
    bcc @success
    bne @check_after
    lda export_workspace_end
    cmp export_start
    bcc @success
    beq @success
@check_after:
    ; Or if workspace_start >= image_end.
    lda export_workspace_start+1
    cmp export_end+1
    bcc @error
    bne @success
    lda export_workspace_start
    cmp export_end
    bcc @error
@success:
    clc
    rts
@error:
    lda #ERR_OUT_OF_MEMORY
    sec
    rts

; export_write_prg - Save a validated EW image through the resident bridge.
; Input: X/Y -> "EW", name:u16, length:arg-byte, device:arg-byte,
; secondary:arg-byte, start:u16, end_exclusive:u16.
; Output: C clear on success; A=error and C set on validation/KERNAL failure.
; Clobbers: A, X, Y. Side effects: SETNAM, SETLFS logical file 1, SAVE.
; Zero page: zp_src.
.export export_write_prg
export_write_prg:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src),y
    cmp #'E'
    beq @magic_e_ok
    jmp @error
@magic_e_ok:
    iny
    lda (zp_src),y
    cmp #'W'
    beq @magic_w_ok
    jmp @error
@magic_w_ok:
    ldy #4
    lda (zp_src),y
    beq @error
    pha
    ldy #2
    lda (zp_src),y
    sta export_options+2
    iny
    lda (zp_src),y
    sta export_options+3
    ora export_options+2
    beq @pop_error
    ldy #5
    lda (zp_src),y
    jsr export_validate_device
    bcs @pop_return_error
    sta export_options+5
    iny
    lda (zp_src),y
    sta export_options+6
    iny
    lda (zp_src),y
    sta export_start
    iny
    lda (zp_src),y
    sta export_start+1
    iny
    lda (zp_src),y
    sta export_end
    iny
    lda (zp_src),y
    sta export_end+1
    ; Require a nonempty forward range. Full stock budget is checked separately.
    lda export_start+1
    cmp export_end+1
    bcc @range_ok
    bne @pop_error
    lda export_start
    cmp export_end
    bcs @pop_error
@range_ok:
    pla
    ldx export_options+2
    ldy export_options+3
    jsr kernal_setnam
    jcs @return_error
    lda #1
    ldx export_options+5
    ldy export_options+6
    jsr kernal_setlfs
    jcs @return_error
    lda #<export_start
    ldx export_end
    ldy export_end+1
    jmp kernal_save
@pop_error:
    pla
@error:
    lda #ERR_ILLEGAL_QUANTITY
@return_error:
    sec
    rts
@pop_return_error:
    pla
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
