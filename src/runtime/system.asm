; src/runtime/system.asm
; Compiler 2 runtime system primitives.
;
; Public entries: system_peek, system_poke, system_sys, system_usr,
; system_wait, system_ti_load, system_ti_store, system_ti_string_load,
; system_ti_string_store
; Internal helpers: none
; Zero-page read:  zp_tmp1, zp_tmp2, zp_fac1
; Zero-page write: zp_tmp1, zp_tmp2, zp_fac1
; Clobbers: A, X, Y

.include "common/zp.inc"
.include "common/constants.asm"
.include "protected_ranges.inc"
.include "zp_protected_ranges.inc"

.import kernal_rdtim, kernal_settim, kernal_stop
.import math_u24_to_float
.import str_export_bytes, str_from_bytes

.segment "BSS"
system_ti_string:
    .export system_ti_string
    .res 7
system_last_sys:
    .export system_last_sys
    .res 2
system_wait_mask: .res 1
system_wait_xor:  .res 1
system_jiffy:     .res 3
system_value:     .res 3
system_addend:    .res 3
system_remainder: .res 1
system_count:     .res 1
system_hours:     .res 1
system_minutes:   .res 1
system_seconds:   .res 1
system_poke_value: .res 1
system_ti_dest:   .res 2
system_ti_request: .res 7

.segment "RODATA"
system_zp_protected_ranges:
    emit_compiler_zp_protected_ranges

.segment "CODE"

; system_peek - Return the byte at the requested address.
.export system_peek
system_peek:
    stx zp_tmp1
    sty zp_tmp1+1
    ldy #0
    lda (zp_tmp1), y
    rts

; system_poke - Store a byte at the requested address.
.export system_poke
system_poke:
    stx zp_tmp1
    sty zp_tmp1+1
    sta system_poke_value
    ; Compiler-owned zero page is allocated dynamically.  POKE must protect
    ; the generated occupied ranges while leaving non-compiler ZP addresses
    ; available for stock-compatible hardware/KERNAL use.
    cpy #0
    bne @normal_ram
    ldx #0
@zp_range_loop:
    cpx #(compiler_zp_protected_range_count * 2)
    beq @store
    lda zp_tmp1
    cmp system_zp_protected_ranges, x
    bcc @next_zp_range
    inx
    cmp system_zp_protected_ranges, x
    bcc @protected
    inx
    bne @zp_range_loop
@next_zp_range:
    inx
    inx
    bne @zp_range_loop
@normal_ram:
    ; The normal-RAM compiler image/workspace is one generated policy range.
    cpy #>compiler_protected_start
    bcc @high_guard
    bne @check_end
    cpx #<compiler_protected_start
    bcc @high_guard
@check_end:
    cpy #>compiler_protected_end
    bcc @protected
    bne @high_guard
    cpx #<compiler_protected_end
    bcc @protected
@high_guard:
    cpy #>compiler_high_guard_start
    bne @store
    cpx #<compiler_high_guard_start
    bcc @store
@protected:
    sec
    rts
@store:
    lda system_poke_value
    ldy #0
    sta (zp_tmp1), y
    clc
    rts

; system_sys - Call the requested machine-code address.
.export system_sys
system_sys:
    stx system_last_sys
    sty system_last_sys+1
    stx @call+1
    sty @call+2
    jsr @call
    clc
    rts
@call:
    jsr $ffff
    rts

; system_usr - Dispatch through the stock-compatible USR jump vector at $0310.
.export system_usr
system_usr:
    jsr $0310
    clc
    rts

; system_wait - Poll a real CPU address until ((value XOR xor) AND mask) != 0.
; Input: X/Y -> six-byte `SW`, address:u16, mask:u8, xor:u8 record.
; Output: C clear when satisfied; C set when STOP aborts or record is invalid.
.export system_wait
system_wait:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #'S'
    bne @error
    iny
    lda (zp_src), y
    cmp #'W'
    bne @error
    iny
    lda (zp_src), y
    sta zp_tmp1
    iny
    lda (zp_src), y
    sta zp_tmp1+1
    iny
    lda (zp_src), y
    sta system_wait_mask
    iny
    lda (zp_src), y
    sta system_wait_xor
@poll:
    ldy #0
    lda (zp_tmp1), y
    eor system_wait_xor
    and system_wait_mask
    bne @done
    jsr kernal_stop
    bne @poll
@error:
    sec
    rts
@done:
    clc
    rts

; system_ti_load - Atomically load the IRQ-owned jiffy clock into A/X/Y.
.export system_ti_load
system_ti_load:
    jsr kernal_rdtim
    jmp math_u24_to_float

; system_ti_store - Atomically store the IRQ-owned jiffy clock from A/X/Y.
.export system_ti_store
system_ti_store:
    jmp kernal_settim

; system_ti_string_load - Convert the current 60 Hz clock to a destination SD.
; Input: X/Y=destination SD pointer. Output: C=error.
.export system_ti_string_load
system_ti_string_load:
    stx system_ti_dest
    sty system_ti_dest+1
    jsr kernal_rdtim
    sta system_jiffy
    stx system_jiffy+1
    sty system_jiffy+2
    jsr _system_div60
    jsr _system_div60
    lda system_remainder
    sta system_seconds
    jsr _system_div60
    lda system_remainder
    sta system_minutes
    lda system_jiffy
    sta system_hours
    jsr _system_byte_to_ascii
    stx system_ti_string
    sty system_ti_string+1
    lda system_minutes
    jsr _system_byte_to_ascii
    stx system_ti_string+2
    sty system_ti_string+3
    lda system_seconds
    jsr _system_byte_to_ascii
    stx system_ti_string+4
    sty system_ti_string+5
    lda #0
    sta system_ti_string+6
    lda #'S'
    sta system_ti_request
    lda #'B'
    sta system_ti_request+1
    lda system_ti_dest
    sta system_ti_request+2
    lda system_ti_dest+1
    sta system_ti_request+3
    lda #<system_ti_string
    sta system_ti_request+4
    lda #>system_ti_string
    sta system_ti_request+5
    lda #6
    sta system_ti_request+6
    ldx #<system_ti_request
    ldy #>system_ti_request
    jmp str_from_bytes

; system_ti_string_store - Validate and set the clock from one source SD.
.export system_ti_string_store
system_ti_string_store:
    stx system_ti_request+2
    sty system_ti_request+3
    lda #'S'
    sta system_ti_request
    lda #'E'
    sta system_ti_request+1
    lda #<system_ti_string
    sta system_ti_request+4
    lda #>system_ti_string
    sta system_ti_request+5
    lda #6
    sta system_ti_request+6
    ldx #<system_ti_request
    ldy #>system_ti_request
    jsr str_export_bytes
    bcs @error
    cmp #6
    bne @error
    lda system_ti_string
    ldx system_ti_string+1
    jsr _system_ascii_pair
    bcs @error
    cmp #24
    bcs @error
    sta system_hours
    lda system_ti_string+2
    ldx system_ti_string+3
    jsr _system_ascii_pair
    bcs @error
    cmp #60
    bcs @error
    sta system_minutes
    lda system_ti_string+4
    ldx system_ti_string+5
    jsr _system_ascii_pair
    bcs @error
    cmp #60
    bcs @error
    sta system_seconds
    lda system_hours
    jsr _system_value_from_a
    jsr _system_mul60
    lda system_minutes
    jsr _system_add_a
    jsr _system_mul60
    lda system_seconds
    jsr _system_add_a
    jsr _system_mul60
    lda system_value
    ldx system_value+1
    ldy system_value+2
    jmp kernal_settim
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; Divide system_jiffy by 60 in place, leaving the remainder separately.
_system_div60:
    lda #0
    sta system_remainder
    ldx #24
@bit:
    asl system_jiffy
    rol system_jiffy+1
    rol system_jiffy+2
    rol system_remainder
    lda system_remainder
    cmp #60
    bcc @next
    sbc #60
    sta system_remainder
    inc system_jiffy
@next:
    dex
    bne @bit
    rts

_system_value_from_a:
    sta system_value
    lda #0
    sta system_value+1
    sta system_value+2
    rts

_system_add_a:
    clc
    adc system_value
    sta system_value
    bcc @done
    inc system_value+1
    bne @done
    inc system_value+2
@done:
    rts

; Multiply the 24-bit system_value by 60 without overflow in the clock domain.
_system_mul60:
    lda system_value
    sta system_addend
    lda system_value+1
    sta system_addend+1
    lda system_value+2
    sta system_addend+2
    lda #0
    sta system_value
    sta system_value+1
    sta system_value+2
    lda #60
    sta system_count
@add:
    clc
    lda system_value
    adc system_addend
    sta system_value
    lda system_value+1
    adc system_addend+1
    sta system_value+1
    lda system_value+2
    adc system_addend+2
    sta system_value+2
    dec system_count
    bne @add
    rts

_system_byte_to_ascii:
    ldx #0
@tens:
    cmp #10
    bcc @digits
    sec
    sbc #10
    inx
    bne @tens
@digits:
    tay
    txa
    ora #'0'
    tax
    tya
    ora #'0'
    tay
    rts

_system_ascii_pair:
    cmp #'0'
    bcc @bad
    cmp #('9'+1)
    bcs @bad
    sec
    sbc #'0'
    sta zp_tmp2
    txa
    cmp #'0'
    bcc @bad
    cmp #('9'+1)
    bcs @bad
    sec
    sbc #'0'
    tax
    lda zp_tmp2
    asl
    sta zp_tmp2
    asl
    asl
    clc
    adc zp_tmp2
    stx zp_tmp2
    adc zp_tmp2
    clc
    rts
@bad:
    sec
    rts
