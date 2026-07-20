; src/geoasm/compile_export.asm
; Validates the records used to construct and write a source-free standalone
; image. Image construction remains a separate compiler/linker responsibility.
;
; Stock budget policy (DESIGN2 §6.4 / COMPILE_EXPORT.md): soft edge-triggered
; 80%/100% warnings; hard-fail only invalid ranges; oversize export allowed.
; Dual layouts: stock ($CE00 free) vs developer ($CE00 reserved). Hot pages
; $C800-$CDFF are never permanent export reservations.

.include "common/zp.inc"
.include "common/constants.asm"

.import kernal_setnam, kernal_setlfs, kernal_save
.import diag_format_warning, diag_format_source_context, diag_print_error
.import georam_call_group_n, georam_call_group_n_xy
.import GEORAM_ROUTINE_ID_EXPORT_PARSE_COMMAND
.import GEORAM_ROUTINE_ID_EXPORT_COLLECT_DEPENDENCIES
.import GEORAM_ROUTINE_ID_EXPORT_LINK_IMAGE
.import GEORAM_ROUTINE_ID_EXPORT_CHECK_BUDGETS
.import GEORAM_ROUTINE_ID_EXPORT_WRITE_PRG
.import GEORAM_ROUTINE_ID_EXPORT_APPLY_SOFT_BUDGETS
.import GEORAM_ROUTINE_ID_EXPORT_SELECT_LAYOUT

EXPORT_MIN_DEVICE = 8
EXPORT_MAX_DEVICE = 11
EXPORT_FORBIDDEN_DEPENDENCIES = $F0
EXPORT_LINKED_STANDALONE = $01

; Layout profile published by export_check_budgets (internal metadata).
EXPORT_LAYOUT_STOCK     = 0   ; $CE00 free in export runtime
EXPORT_LAYOUT_DEVELOPER = 1   ; $CE00 reserved (developer/XIP layout)

; export_budget_state bits: latched side of soft thresholds.
EXPORT_STATE_GE_80  = $01
EXPORT_STATE_GE_100 = $02

; Soft warning codes (diag severity WARNING).
WARN_NEAR_STOCK     = $01
WARN_NEAR_CLEAR     = $02
WARN_EXCEEDS_STOCK  = $03
WARN_EXCEEDS_CLEAR  = $04

; Stock image high-water marks (exclusive end). Ceiling payload ends by $CFFF.
EXPORT_STOCK_BASE     = $0801
EXPORT_STOCK_END      = $D000
; 80% of ($D000-$0801) = floor($C7FF*4/5) = $9FFF → high-water $A800.
EXPORT_STOCK_80_END   = $A800
; Developer XIP primary page (exclusive end $CF00).
EXPORT_CE00_PAGE      = $CE00
EXPORT_CE00_END       = $CF00
; Hot XIP cache window — never a permanent export reservation.
EXPORT_HOT_START      = $C800
EXPORT_HOT_END        = $CE00

.segment "RODATA"
export_default_filename:
    .byte "COMPILED"
EXPORT_DEFAULT_FILENAME_LEN = 8

export_msg_near:
    .byte "NEAR STOCK LIMIT", 0
export_msg_near_clear:
export_msg_exceeds_clear:
    .byte "OK", 0
export_msg_exceeds:
    .byte "EXCEEDS STOCK RAM", 0

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
; Soft budget edge-trigger latches (bits EXPORT_STATE_*).
.export export_budget_state
export_budget_state:
    .res 1
; EXPORT_LAYOUT_STOCK or EXPORT_LAYOUT_DEVELOPER.
.export export_layout_profile
export_layout_profile:
    .res 1
; Bit0 = $CE00 reserved; hot-page permanent bits are never set.
.export export_layout_flags
export_layout_flags:
    .res 1

EXPORT_FLAG_CE00_RESERVED = $01

.segment "GEOASM"

.macro jcs target
    bcc *+5
    jmp target
.endmacro

; export_compile_command - Execute a fully prepared standalone export plan.
; Input: X/Y -> contiguous CP/EO(7), ED(3), EL(3), EB(10), EW(11) plan.
;   CP is canonicalized in place to EO (secondary byte occupies slot 6).
;   Offsets: ED@7, EL@10, EB@13, EW@23.
; Output: C clear after the image is saved; C set/A=error at the first rejected
; record or KERNAL failure. Soft budget warnings do not abort the transaction.
; Clobbers: A, X, Y. Side effects: canonicalizes CP; may warn; may write a PRG.
; Zero page: zp_src.
.export export_compile_command
export_compile_command:
    stx export_command_record
    sty export_command_record+1
    ; CP parsing is a page-bound XIP entry.  The XY gate preserves the command
    ; descriptor arguments while selecting its generated geoRAM page.
    lda #<GEORAM_ROUTINE_ID_EXPORT_PARSE_COMMAND
    jsr georam_call_group_n_xy
    bcs @done
    lda #7
    jsr @record_at_offset
    lda #<GEORAM_ROUTINE_ID_EXPORT_COLLECT_DEPENDENCIES
    jsr georam_call_group_n_xy
    bcs @done
    lda #10
    jsr @record_at_offset
    lda #<GEORAM_ROUTINE_ID_EXPORT_LINK_IMAGE
    jsr georam_call_group_n_xy
    bcs @done
    lda #13
    jsr @record_at_offset
    lda #<GEORAM_ROUTINE_ID_EXPORT_CHECK_BUDGETS
    jsr georam_call_group_n_xy
    bcs @done
    lda #23
    jsr @record_at_offset
    lda #<GEORAM_ROUTINE_ID_EXPORT_WRITE_PRG
    jmp georam_call_group_n_xy
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

.segment "GEORAM_PAGE_35"

; export_parse_command - Canonicalize a CP command record.
; Input: X/Y -> CP, name:u16, length:arg-byte, device:arg-byte. A zero length
; selects "COMPILED"; a zero device selects KERNAL fa at $BA. Plan slot is 7
; bytes so secondary can be stored without clobbering the following ED record.
; Output: X/Y -> EO options, C clear; A=error and C set on failure.
; Clobbers: A, X, Y. Side effects: replaces in-place record and export_options.
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
    ldy #0
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
    ; Mirror the EO options for callers that inspect export_options.
    ldy #0
@copy_options:
    lda (zp_src),y
    sta export_options,y
    iny
    cpy #7
    bne @copy_options
    ldx export_record
    ldy export_record+1
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
@return_error:
    sec
    rts

; Validate the device in A. Kept in the same page as its only caller: an XIP
; routine cannot use a normal-RAM mirror of a private helper as a hidden
; implementation escape.  It follows the public entry so the generated
; directory's required offset-zero target is the actual callable routine.
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

.assert * - export_parse_command <= $FA, error, "export parse XIP page exceeds geoRAM page"

.segment "GEORAM_PAGE_36"

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

.assert * - export_collect_dependencies <= $FA, error, "export dependency XIP page exceeds geoRAM page"

.segment "GEORAM_PAGE_37"

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

.assert * - export_link_image <= $FA, error, "export link XIP page exceeds geoRAM page"

.segment "GEORAM_PAGE_38"

; export_check_budgets - Soft stock budget + dual layout policy.
; Input: X/Y -> "EB", image_start:u16, image_end_exclusive:u16,
; workspace_start:u16, workspace_end_exclusive:u16.
; Hard-fail (C set, A=ERR_OUT_OF_MEMORY): bad magic, image_start < $0801,
; empty/reversed image, reversed workspace, or image/workspace overlap.
; Soft policy: edge-triggered 80% / 100% stock warnings; oversize allowed.
; Layout: stock ($CE00 free) when image+workspace fit stock normal RAM without
; a permanent $CE00 claim; otherwise developer ($CE00 reserved). Hot pages
; $C800-$CDFF are never marked permanent.
; Output: C clear on admissible plan (including oversize); C set on hard fail.
; Clobbers: A, X, Y. Side effects: export_layout_*, export_budget_state, diags.
; Zero page: zp_src.
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
    beq @copy_begin
    jmp @error
@copy_begin:
    ldx #0
@copy_words:
    iny
    lda (zp_src),y
    sta export_start,x
    inx
    cpx #8
    bne @copy_words

    ; image_start >= $0801 (stock load base contract).
    lda export_start+1
    cmp #$08
    bcc @error
    bne @start_ok
    lda export_start
    cmp #$01
    bcc @error
@start_ok:
    ; Nonempty forward image range (image_start < image_end).
    lda export_start+1
    cmp export_end+1
    bcc @image_order_ok
    bne @error
    lda export_start
    cmp export_end
    bcs @error
@image_order_ok:
    ; Workspace may be empty (start == end); reject reversed only.
    lda export_workspace_start+1
    cmp export_workspace_end+1
    bcc @workspace_order_ok
    bne @error
    lda export_workspace_start
    cmp export_workspace_end
    bcc @workspace_order_ok
    beq @disjoint_ok
    bcs @error
@workspace_order_ok:
    ; Disjoint if workspace_end <= image_start.
    lda export_workspace_end+1
    cmp export_start+1
    bcc @disjoint_ok
    bne @check_after
    lda export_workspace_end
    cmp export_start
    bcc @disjoint_ok
    beq @disjoint_ok
@check_after:
    ; Or if workspace_start >= image_end.
    lda export_workspace_start+1
    cmp export_end+1
    bcc @error
    bne @disjoint_ok
    lda export_workspace_start
    cmp export_end
    bcc @error
@disjoint_ok:
    ldx #<GEORAM_ROUTINE_ID_EXPORT_APPLY_SOFT_BUDGETS
    jsr georam_call_group_n
    bcs @error
    ldx #<GEORAM_ROUTINE_ID_EXPORT_SELECT_LAYOUT
    jsr georam_call_group_n
    bcs @error
    clc
    rts
@error:
    lda #ERR_OUT_OF_MEMORY
    sec
    rts

.assert * - export_check_budgets <= $FA, error, "export budget XIP page exceeds geoRAM page"

; Edge-triggered soft stock warnings against high-water image_end.
; 80%: image_end >= $A800; 100% exceed: image_end > $D000.
.segment "GEORAM_PAGE_43"

.export export_apply_soft_budgets
.proc export_apply_soft_budgets
    lda #0
    sta zp_tmp1                 ; new state bits

    ; --- 80% high-water ---
    lda export_end+1
    cmp #>EXPORT_STOCK_80_END
    bcc @below_80
    ; hi >= $A8 → at/above 80%
    lda zp_tmp1
    ora #EXPORT_STATE_GE_80
    sta zp_tmp1
@below_80:

    ; --- 100% exceed (strictly past stock end) ---
    lda export_end+1
    cmp #>EXPORT_STOCK_END
    bcc @below_100
    bne @at_100
    lda export_end
    beq @below_100              ; exactly $D000 still fits
@at_100:
    lda zp_tmp1
    ora #EXPORT_STATE_GE_100
    sta zp_tmp1
@below_100:

    ; Edge 80% enter
    lda export_budget_state
    and #EXPORT_STATE_GE_80
    bne @had_80
    lda zp_tmp1
    and #EXPORT_STATE_GE_80
    beq @skip_80_enter
    lda #WARN_NEAR_STOCK
    ldx #<export_msg_near
    ldy #>export_msg_near
    jsr export_emit_warning
    jmp @skip_80_leave
@had_80:
    lda zp_tmp1
    and #EXPORT_STATE_GE_80
    bne @skip_80_leave
    lda #WARN_NEAR_CLEAR
    ldx #<export_msg_near_clear
    ldy #>export_msg_near_clear
    jsr export_emit_warning
@skip_80_enter:
@skip_80_leave:

    ; Edge 100% enter
    lda export_budget_state
    and #EXPORT_STATE_GE_100
    bne @had_100
    lda zp_tmp1
    and #EXPORT_STATE_GE_100
    beq @skip_100_enter
    lda #WARN_EXCEEDS_STOCK
    ldx #<export_msg_exceeds
    ldy #>export_msg_exceeds
    jsr export_emit_warning
    jmp @skip_100_leave
@had_100:
    lda zp_tmp1
    and #EXPORT_STATE_GE_100
    bne @skip_100_leave
    lda #WARN_EXCEEDS_CLEAR
    ldx #<export_msg_exceeds_clear
    ldy #>export_msg_exceeds_clear
    jsr export_emit_warning
@skip_100_enter:
@skip_100_leave:

    lda zp_tmp1
    sta export_budget_state
    clc
    rts
.endproc

; A=warning code, X/Y=NUL-terminated message.
.proc export_emit_warning
    sta zp_tmp2
    stx zp_tmp3
    sty zp_tmp4
    lda zp_tmp2
    ldx #0
    ldy #0
    jsr diag_format_warning
    lda #0
    ldx zp_tmp3
    ldy zp_tmp4
    jsr diag_format_source_context
    jmp diag_print_error
.endproc

; Select stock vs developer layout from measured ranges.
; Stock-compatible: image and workspace fit stock normal RAM ($..$CFFF). In that
; profile $CE00 is free (program may occupy it as ordinary RAM) and hot pages
; $C800-$CDFF are never permanent reservations.
; Developer: image or workspace exceeds the stock ceiling — export still
; proceeds, but metadata reserves $CE00 like the installed development layout.
.assert * - export_apply_soft_budgets <= $FA, error, "export warning XIP page exceeds geoRAM page"

.segment "GEORAM_PAGE_44"

.export export_select_layout
.proc export_select_layout
    lda #EXPORT_LAYOUT_STOCK
    sta export_layout_profile
    lda #0
    sta export_layout_flags

    ; Oversize image → developer (cannot run on stock without expansion).
    lda export_end+1
    cmp #>EXPORT_STOCK_END
    bcc @image_fits
    bne @developer
    lda export_end
    bne @developer
@image_fits:
    ; Workspace past stock normal-RAM ceiling → developer.
    lda export_workspace_end+1
    cmp #>EXPORT_STOCK_END
    bcc @workspace_fits
    bne @developer
    lda export_workspace_end
    bne @developer
@workspace_fits:
    ; Stock: $CE00 free. Hot pages are never flagged permanent.
    rts
@developer:
    lda #EXPORT_LAYOUT_DEVELOPER
    sta export_layout_profile
    lda #EXPORT_FLAG_CE00_RESERVED
    sta export_layout_flags
    clc
    rts
.endproc

.assert * - export_select_layout <= $FA, error, "export layout XIP page exceeds geoRAM page"

; export_write_prg - Save a validated EW image through the resident bridge.
; Input: X/Y -> "EW", name:u16, length:arg-byte, device:arg-byte,
; secondary:arg-byte, start:u16, end_exclusive:u16.
; Output: C clear on success; A=error and C set on validation/KERNAL failure.
; Clobbers: A, X, Y. Side effects: SETNAM, SETLFS logical file 1, SAVE.
; Zero page: zp_src.
.segment "GEORAM_PAGE_39"

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
    jsr export_write_validate_device
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
    ; Require a nonempty forward range. Soft stock budget is checked separately.
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

; The writer's device check is page-local.  Calling the parser page's private
; validator would depend on whichever geoRAM page a previous gate selected.
.proc export_write_validate_device
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

.assert * - export_write_prg <= $FA, error, "export write XIP page exceeds geoRAM page"
