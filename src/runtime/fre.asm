; src/runtime/fre.asm
; Profile-aware FRE free-byte reporting (DESIGN2 §3.1 / REQUIREMENTS R3.1).
;
; fre_profile:
;   0 = stock-compatible COMPILE export (normal-RAM dynamic free)
;   1 = installed development environment (expansion arena free)
;
; fre_query discards no argument itself (callers evaluate and drop the stock
; FRE argument). It publishes free bytes as a packed float in FAC1 via
; math_u24_to_float. FRE never reports raw device capacity.

.include "common/zp.inc"
.include "common/constants.asm"

.import page_alloc_count
.import math_u24_to_float

; Default stock-like free after a typical standalone image (38912 = $9800).
FRE_EXPORT_DEFAULT_LO = $00
FRE_EXPORT_DEFAULT_MID = $98
FRE_EXPORT_DEFAULT_HI = $00

FRE_PROFILE_EXPORT = 0
FRE_PROFILE_EXPANSION = 1

.segment "BSS"
.export fre_profile
fre_profile: .res 1
.export fre_export_bytes
fre_export_bytes: .res 3
fre_ready: .res 1

; HIBASIC ($E000+): frees late CODE/RAM budget; visible under $01=$35.
.segment "HIBASIC"

; fre_init - Default to expansion profile with stock export free baseline.
; Inputs: none. Outputs: C clear. Clobbers: A.
.export fre_init
fre_init:
    lda #FRE_PROFILE_EXPANSION
    sta fre_profile
    lda #FRE_EXPORT_DEFAULT_LO
    sta fre_export_bytes
    lda #FRE_EXPORT_DEFAULT_MID
    sta fre_export_bytes+1
    lda #FRE_EXPORT_DEFAULT_HI
    sta fre_export_bytes+2
    lda #1
    sta fre_ready
    clc
    rts

; fre_set_profile - Select FRE reporting profile.
; Inputs: A = 0 export / 1 expansion. Outputs: C clear. Clobbers: A.
.export fre_set_profile
fre_set_profile:
    sta fre_profile
    clc
    rts

; fre_set_export_bytes - Publish the export-mode free count (24-bit little).
; Inputs: A=lo, X=mid, Y=hi. Outputs: C clear. Clobbers: none beyond stores.
.export fre_set_export_bytes
fre_set_export_bytes:
    sta fre_export_bytes
    stx fre_export_bytes+1
    sty fre_export_bytes+2
    clc
    rts

; fre_query - Profile-aware free bytes into FAC1.
; Inputs: none (numeric FRE argument already discarded by caller).
; Outputs: FAC1 = free bytes as float, C clear.
; Side effects: may call page_alloc_count (ensures allocator ready).
; Clobbers: A, X, Y. Zero page: FAC1 via math_u24_to_float.
.export fre_query
fre_query:
    lda fre_ready
    bne @ready
    jsr fre_init
@ready:
    lda fre_profile
    beq @export

    ; Expansion: free_bytes = free_pages << 8.
    ; page_alloc_count returns X/Y = pages; A=0 becomes low byte of free bytes.
    jsr page_alloc_count
    lda #0
    jmp math_u24_to_float

@export:
    ; Source-free export: normal-RAM dynamic free remaining after image.
    lda fre_export_bytes
    ldx fre_export_bytes+1
    ldy fre_export_bytes+2
    jmp math_u24_to_float
