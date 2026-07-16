; src/runtime/variables.asm
; Typed variable descriptor helpers.
;
; Variable descriptor (VD, 12 bytes):
;   +0  'V'
;   +1  'D'
;   +2  kind: 1=int, 2=float, 3=string
;   +3  descriptor generation, nonzero
;   +4  storage: 0=direct normal RAM cell, 1=arena cell
;   +5  reserved, must be zero
;   +6  direct: cell_lo      arena: arena id
;   +7  direct: cell_hi      arena: arena generation
;   +8  direct: zero         arena: relative page
;   +9  direct: zero         arena: byte offset
;   +10 direct: zero         arena: zero
;   +11 direct: zero         arena: zero
;
; Store requests:
;   VI: "VI", descriptor_ptr:u16, value:u16
;   VF: "VF", descriptor_ptr:u16, reserved:u16, FAC1 source
;   VS: "VS", descriptor_ptr:u16, source_SD_ptr:u16
;
; String cells contain a complete 12-byte SD.  String operations stage the cell
; in normal RAM because an arena-backed VD cell lives behind the same GeoRAM
; window that str_copy switches while reading and allocating string pages.

.include "common/zp.inc"
.include "common/constants.asm"
.include "arena_layout.inc"

.import arena_handle_valid
.import arena_select_page
.import math_fac_type
.import math_int_to_float
.import math_float_to_int
.import str_copy
.import str_len

.macro jcs target
    bcc *+5
    jmp target
.endmacro
.macro jcc target
    bcs *+5
    jmp target
.endmacro
.macro jeq target
    bne *+5
    jmp target
.endmacro
.macro jne target
    beq *+5
    jmp target
.endmacro

VD_KIND_INT = $01
VD_KIND_FLOAT = $02
VD_KIND_STRING = $03
VD_STORAGE_DIRECT = $00
VD_STORAGE_ARENA = $01

VD_KIND = 2
VD_GENERATION = 3
VD_STORAGE = 4
VD_RESERVED = 5
VD_CELL_LO = 6
VD_CELL_HI = 7
VD_ARENA = 6
VD_ARENA_GENERATION = 7
VD_ARENA_PAGE = 8
VD_ARENA_OFFSET = 9

.segment "BSS"
var_descriptor_ptr:       .res 2
var_request_ptr:          .res 2
var_cell_ptr:             .res 2
var_kind:                 .res 1
var_storage:              .res 1
var_arena:                .res 1
var_arena_generation:     .res 1
var_arena_page:           .res 1
var_arena_offset:         .res 1
var_store_value:          .res 2
var_copy_count:           .res 1
var_string_image:         .res 12
var_string_request:       .res 6

; HIBASIC ($E000+): frees late CODE/RAM budget; visible under $01=$35.
.segment "HIBASIC"

; Load and validate a VD descriptor, leaving descriptor metadata in BSS.
; Inputs: X/Y=VD pointer. Outputs: C=0 valid, C=1/A=error.
.proc var_load_descriptor
    stx var_descriptor_ptr
    sty var_descriptor_ptr+1
    stx zp_src
    sty zp_src+1
    ldy #$00
    lda (zp_src),y
    cmp #'V'
    jne @error
    iny
    lda (zp_src),y
    cmp #'D'
    jne @error
    ldy #VD_KIND
    lda (zp_src),y
    cmp #VD_KIND_INT
    beq @kind_ok
    cmp #VD_KIND_FLOAT
    beq @kind_ok
    cmp #VD_KIND_STRING
    jne @error
@kind_ok:
    sta var_kind
    ldy #VD_GENERATION
    lda (zp_src),y
    jeq @error
    ldy #VD_STORAGE
    lda (zp_src),y
    sta var_storage
    cmp #VD_STORAGE_DIRECT
    beq @direct
    cmp #VD_STORAGE_ARENA
    jne @error
    ldy #VD_RESERVED
    lda (zp_src),y
    jne @error
    ldy #VD_ARENA
    lda (zp_src),y
    sta var_arena
    tax
    iny
    lda (zp_src),y
    sta var_arena_generation
    tay
    jsr arena_handle_valid
    jcs @error
    ldx var_descriptor_ptr
    ldy var_descriptor_ptr+1
    stx zp_src
    sty zp_src+1
    ldy #VD_ARENA_PAGE
    lda (zp_src),y
    sta var_arena_page
    iny
    lda (zp_src),y
    sta var_arena_offset
    iny
    lda (zp_src),y
    jne @error
    iny
    lda (zp_src),y
    jne @error
    jsr var_validate_arena_payload
    jcs @error
    clc
    rts
@direct:
    ldy #VD_RESERVED
    lda (zp_src),y
    jne @error
    ldy #VD_CELL_LO
    lda (zp_src),y
    sta var_cell_ptr
    iny
    lda (zp_src),y
    sta var_cell_ptr+1
    iny
    lda (zp_src),y
    jne @error
    iny
    lda (zp_src),y
    jne @error
    iny
    lda (zp_src),y
    jne @error
    iny
    lda (zp_src),y
    jne @error
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Validate that the typed arena payload fits wholly inside the selected page.
; Arena cells are addressed through the $DE00 geoRAM window, so payloads may
; not cross $DEFF into normal RAM or an unrelated banking view.
.proc var_validate_arena_payload
    lda var_kind
    cmp #VD_KIND_INT
    beq @int
    cmp #VD_KIND_FLOAT
    beq @float
    cmp #VD_KIND_STRING
    beq @string
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
@int:
    lda var_arena_offset
    cmp #$FF
    bcs @error
    clc
    rts
@float:
    lda var_arena_offset
    cmp #$FC
    bcs @error
    clc
    rts
@string:
    lda var_arena_offset
    cmp #$F5
    bcs @error
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; Resolve the loaded descriptor to var_cell_ptr.
.proc var_resolve_loaded
    lda var_storage
    cmp #VD_STORAGE_DIRECT
    beq @direct
    lda var_arena_page
    ldx var_arena
    ldy var_arena_generation
    jsr arena_select_page
    jcs @error
    lda var_arena_offset
    sta var_cell_ptr
    lda #$DE
    sta var_cell_ptr+1
@direct:
    lda var_cell_ptr
    sta zp_dest
    lda var_cell_ptr+1
    sta zp_dest+1
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

.proc var_expect_kind
    cmp var_kind
    bne @error
    clc
    rts
@error:
    lda #ERR_TYPE_MISMATCH
    sec
    rts
.endproc

; Read a store request and validate its two-byte magic.
; Inputs: X/Y=request pointer, A=second magic byte. Outputs: descriptor ptr in X/Y.
.proc var_parse_store_request
    sta var_store_value
    stx var_request_ptr
    sty var_request_ptr+1
    stx zp_src
    sty zp_src+1
    ldy #$00
    lda (zp_src),y
    cmp #'V'
    jne @error
    iny
    lda (zp_src),y
    cmp var_store_value
    jne @error
    ldy #$02
    lda (zp_src),y
    tax
    iny
    lda (zp_src),y
    tay
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

; var_resolve
; Purpose: validate a variable descriptor and resolve its current cell.
; Inputs: X/Y=VD descriptor pointer.
; Outputs: X/Y=cell pointer, C=0; C=1/A=error on malformed/stale descriptor.
; Side effects: arena-backed descriptors select their arena page.
; Clobbers: A, X, Y. Flags: C reports failure.
; Zero page: zp_src.
.export var_resolve
var_resolve:
    jsr var_load_descriptor
    jcs @error
    jsr var_resolve_loaded
    jcs @error
    ldx var_cell_ptr
    ldy var_cell_ptr+1
    clc
    rts
@error:
    sec
    rts

; var_load_int
; Inputs: X/Y=VD integer descriptor. Outputs: X/Y=16-bit value, C=0.
.export var_load_int
var_load_int:
    jsr var_load_descriptor
    jcs @error
    lda #VD_KIND_INT
    jsr var_expect_kind
    jcs @error
    jsr var_resolve_loaded
    jcs @error
    ldy #$00
    lda (zp_dest),y
    tax
    iny
    lda (zp_dest),y
    tay
    clc
    rts
@error:
    sec
    rts

; var_store_int
; Inputs: X/Y=VI request. Outputs: C=0 or C=1/A=error.
.export var_store_int
var_store_int:
    lda #'I'
    jsr var_parse_store_request
    jcs @error
    jsr var_load_descriptor
    jcs @error
    lda #VD_KIND_INT
    jsr var_expect_kind
    jcs @error
    lda var_request_ptr
    sta zp_src
    lda var_request_ptr+1
    sta zp_src+1
    ldy #$04
    lda (zp_src),y
    sta var_store_value
    iny
    lda (zp_src),y
    sta var_store_value+1
    jsr var_resolve_loaded
    jcs @error
    ldy #$00
    lda var_store_value
    sta (zp_dest),y
    iny
    lda var_store_value+1
    sta (zp_dest),y
    clc
    rts
@error:
    sec
    rts

; var_load_float
; Inputs: X/Y=VD float descriptor. Outputs: FAC1=value, C=0.
.export var_load_float
var_load_float:
    jsr var_load_descriptor
    jcs @error
    lda #VD_KIND_FLOAT
    jsr var_expect_kind
    jcs @error
    jsr var_resolve_loaded
    jcs @error
    ldy #$00
@copy:
    lda (zp_dest),y
    sta zp_fac1,y
    iny
    cpy #$05
    bne @copy
    ; FAC now contains a packed float, so its adaptive math type must agree.
    lda #$00
    sta math_fac_type
    clc
    rts
@error:
    sec
    rts

; var_store_float
; Inputs: X/Y=VF request, FAC1=value. Outputs: C=0 or C=1/A=error.
.export var_store_float
var_store_float:
    lda #'F'
    jsr var_parse_store_request
    jcs @error
    jsr var_load_descriptor
    jcs @error
    lda #VD_KIND_FLOAT
    jsr var_expect_kind
    jcs @error
    jsr var_resolve_loaded
    jcs @error
    ldy #$00
@copy:
    lda zp_fac1,y
    sta (zp_dest),y
    iny
    cpy #$05
    bne @copy
    clc
    rts
@error:
    sec
    rts

; var_load_string
; Inputs: X/Y=VD string descriptor.
; Outputs: X/Y=validated staged SD pointer, A=length, C=0.
.export var_load_string
var_load_string:
    jsr var_load_descriptor
    jcs @error
    lda #VD_KIND_STRING
    jsr var_expect_kind
    jcs @error
    jsr var_resolve_loaded
    jcs @error
    jsr var_stage_string_cell
    ldx #<var_string_image
    ldy #>var_string_image
    jsr str_len
    jcs @error
    pha
    ldx #<var_string_image
    ldy #>var_string_image
    pla
    clc
    rts
@error:
    sec
    rts

; var_store_string
; Inputs: X/Y=VS request containing a source SD pointer.
; Copies the source value transactionally and releases the cell's old owner.
.export var_store_string
var_store_string:
    lda #'S'
    jsr var_parse_store_request
    jcs @error
    jsr var_load_descriptor
    jcs @error
    lda #VD_KIND_STRING
    jsr var_expect_kind
    jcs @error
    lda var_request_ptr
    sta zp_src
    lda var_request_ptr+1
    sta zp_src+1
    ldy #$04
    lda (zp_src),y
    sta var_store_value
    iny
    lda (zp_src),y
    sta var_store_value+1
    jsr var_resolve_loaded
    jcs @error
    jsr var_stage_string_cell
    lda #'S'
    sta var_string_request
    lda #'X'
    sta var_string_request+1
    lda #<var_string_image
    sta var_string_request+2
    lda #>var_string_image
    sta var_string_request+3
    lda var_store_value
    sta var_string_request+4
    lda var_store_value+1
    sta var_string_request+5
    ldx #<var_string_request
    ldy #>var_string_request
    jsr str_copy
    jcs @error
    ; str_copy switches the GeoRAM window, so resolve the VD cell again before
    ; publishing the new descriptor image to an arena-backed variable.
    jsr var_resolve_loaded
    jcs @error
    jsr var_publish_string_cell
    clc
    rts
@error:
    sec
    rts

; Copy the resolved 12-byte string cell into stable normal RAM.
.proc var_stage_string_cell
    ldy #$00
@copy:
    lda (zp_dest),y
    sta var_string_image,y
    iny
    cpy #12
    bne @copy
    rts
.endproc

; Publish the staged SD to the currently resolved variable cell.
.proc var_publish_string_cell
    ldy #$00
@copy:
    lda var_string_image,y
    sta (zp_dest),y
    iny
    cpy #12
    bne @copy
    rts
.endproc

; var_promote_to_float
; Inputs: X/Y=integer value. Outputs: FAC1=float equivalent, C=0/error.
.export var_promote_to_float
var_promote_to_float:
    jmp math_int_to_float

; var_coerce
; Inputs: FAC1=value, A=target VD kind. Outputs: C=0, or C=1 unsupported/lossy.
.export var_coerce
var_coerce:
    cmp #VD_KIND_FLOAT
    beq @float
    cmp #VD_KIND_INT
    beq @int
    cmp #VD_KIND_STRING
    beq @string
    lda #ERR_TYPE_MISMATCH
    sec
    rts
@float:
    clc
    rts
@int:
    lda #$00
    sta math_fac_type
    jmp math_float_to_int
@string:
    lda #ERR_TYPE_MISMATCH
    sec
    rts

; var_set_type
; Inputs: X/Y=VD descriptor, A=kind. Outputs: C=0 or C=1/A=error.
.export var_set_type
var_set_type:
    pha
    jsr var_load_descriptor
    pla
    jcs @error
    cmp #VD_KIND_INT
    beq @store
    cmp #VD_KIND_FLOAT
    beq @store
    cmp #VD_KIND_STRING
    jne @error_type
@store:
    ldx var_descriptor_ptr
    ldy var_descriptor_ptr+1
    stx zp_src
    sty zp_src+1
    ldy #VD_KIND
    sta (zp_src),y
    clc
    rts
@error_type:
    lda #ERR_TYPE_MISMATCH
@error:
    sec
    rts
