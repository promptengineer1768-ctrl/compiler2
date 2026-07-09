; Arena-backed string values. There is one representation and no raw-pointer ABI.
;
; SD (12 bytes): "SD", generation:u8, length:u8, arena id:u8,
; arena generation:u8, start page:u16, offset:u8, page count:u8,
; owner generation:u16. Empty values own no page.
;
; Typed requests (all pointers are little endian):
; SA ["SA",dest SD,len]; SF ["SF",SD];
; SX ["SX",dest SD,source SD]; SC ["SC",dest,left,right];
; SL/SR [magic,dest,source,count]; SM ["SM",dest,source,start,count];
; SP ["SP",left,right]; SH ["SH",dest,char]; ST ["ST",dest];
; SB ["SB",dest,source bytes,length]; SE ["SE",source SD,dest bytes,capacity].
; Mutating operations allocate and populate a new value before releasing dest.

.include "common/zp.inc"
.include "common/constants.asm"
.include "arena_layout.inc"

.import arena_handle_valid
.import arena_select_page
.import math_int_to_float
.import math_float_to_int
.import math_mul
.import math_add
.import math_negate
.import math_fac_type

STRING_ARENA = ARENA_TYPE_STRINGS
STRING_ARENA_GENERATION = 1
STRING_PAGE_CAPACITY = ARENA_MIN_PAGES_STRINGS

SD_GENERATION = 2
SD_LENGTH = 3
SD_ARENA = 4
SD_ARENA_GENERATION = 5
SD_PAGE_LO = 6
SD_PAGE_HI = 7
SD_OFFSET = 8
SD_PAGE_COUNT = 9
SD_OWNER_LO = 10
SD_OWNER_HI = 11

.macro jcs target
    bcc *+5
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

.segment "BSS"
str_page_owner_lo: .res STRING_PAGE_CAPACITY
str_page_owner_hi: .res STRING_PAGE_CAPACITY
str_owner_counter: .res 2
str_request_ptr: .res 2
str_dest_ptr: .res 2
str_left_ptr: .res 2
str_right_ptr: .res 2
str_owner: .res 2
str_old_owner: .res 2
str_page: .res 1
str_old_page: .res 1
str_right_page: .res 1
str_length: .res 1
str_left_length: .res 1
str_right_length: .res 1
str_count: .res 1
str_index: .res 1
str_source_offset: .res 1
str_char: .res 1
str_sign: .res 1
str_decimals: .res 1
str_value: .res 2
str_fac_save: .res 5
str_exponent: .res 2
str_seen_digit: .res 1
str_seen_dot: .res 1
str_descriptor_image: .res 12
str_byte_ptr: .res 2

.segment "CODE"

; str_reset - Release all string suballocator ownership.
; Input: none. Output: C clear. Clobbers: A, X and flags.
; Side effects: invalidates all existing SD page ownership.
.export str_reset
str_reset:
    lda #0
    ldx #STRING_PAGE_CAPACITY-1
@clear:
    sta str_page_owner_lo,x
    sta str_page_owner_hi,x
    dex
    bpl @clear
    inc str_owner_counter
    bne :+
    inc str_owner_counter+1
:
    clc
    rts

.proc str_error
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
.endproc

.proc str_req_zp
    lda str_request_ptr
    sta zp_src
    lda str_request_ptr+1
    sta zp_src+1
    rts
.endproc

; Validate request magic A and read dest at +2.
.proc str_parse_dest_request
    sta str_char
    stx str_request_ptr
    sty str_request_ptr+1
    jsr str_req_zp
    ldy #0
    lda (zp_src),y
    cmp #'S'
    jne str_error
    iny
    lda (zp_src),y
    cmp str_char
    jne str_error
    iny
    lda (zp_src),y
    sta str_dest_ptr
    iny
    lda (zp_src),y
    sta str_dest_ptr+1
    clc
    rts
.endproc

; Load and validate SD at X/Y into descriptor image and working metadata.
.proc str_load
    stx zp_src
    sty zp_src+1
    ldy #0
@copy:
    lda (zp_src),y
    sta str_descriptor_image,y
    iny
    cpy #12
    bne @copy
    lda str_descriptor_image
    cmp #'S'
    jne str_error
    lda str_descriptor_image+1
    cmp #'D'
    jne str_error
    lda str_descriptor_image+SD_GENERATION
    jeq str_error
    lda str_descriptor_image+SD_ARENA
    cmp #STRING_ARENA
    jne str_error
    lda str_descriptor_image+SD_ARENA_GENERATION
    tay
    ldx #STRING_ARENA
    jsr arena_handle_valid
    jcs str_error
    lda str_descriptor_image+SD_PAGE_HI
    ora str_descriptor_image+SD_OFFSET
    jne str_error
    lda str_descriptor_image+SD_LENGTH
    sta str_length
    lda str_length
    beq @empty
    lda str_descriptor_image+SD_PAGE_COUNT
    cmp #1
    jne str_error
    lda str_descriptor_image+SD_PAGE_LO
    cmp #STRING_PAGE_CAPACITY
    jcs str_error
    tax
    lda str_page_owner_lo,x
    cmp str_descriptor_image+SD_OWNER_LO
    jne str_error
    lda str_page_owner_hi,x
    cmp str_descriptor_image+SD_OWNER_HI
    jne str_error
    lda str_descriptor_image+SD_OWNER_LO
    ora str_descriptor_image+SD_OWNER_HI
    jeq str_error
    clc
    rts
@empty:
    lda str_descriptor_image+SD_PAGE_LO
    ora str_descriptor_image+SD_PAGE_HI
    ora str_descriptor_image+SD_PAGE_COUNT
    ora str_descriptor_image+SD_OWNER_LO
    ora str_descriptor_image+SD_OWNER_HI
    jne str_error
    clc
    rts
.endproc

.proc str_next_owner
    inc str_owner_counter
    bne :+
    inc str_owner_counter+1
:
    lda str_owner_counter
    ora str_owner_counter+1
    bne :+
    inc str_owner_counter
:
    lda str_owner_counter
    sta str_owner
    lda str_owner_counter+1
    sta str_owner+1
    rts
.endproc

.proc str_claim_page
    jsr str_next_owner
    ldx #0
@scan:
    lda str_page_owner_lo,x
    ora str_page_owner_hi,x
    beq @found
    inx
    cpx #STRING_PAGE_CAPACITY
    bne @scan
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts
@found:
    lda str_owner
    sta str_page_owner_lo,x
    lda str_owner+1
    sta str_page_owner_hi,x
    stx str_page
    clc
    rts
.endproc

.proc str_release_working
    lda str_descriptor_image+SD_PAGE_COUNT
    beq @done
    ldx str_descriptor_image+SD_PAGE_LO
    lda #0
    sta str_page_owner_lo,x
    sta str_page_owner_hi,x
@done:
    rts
.endproc

.proc str_publish
    lda str_dest_ptr
    sta zp_dest
    lda str_dest_ptr+1
    sta zp_dest+1
    ldy #0
@copy:
    lda str_descriptor_image,y
    sta (zp_dest),y
    iny
    cpy #12
    bne @copy
    clc
    rts
.endproc

; Save old dest if live, then publish new image and release old ownership.
.proc str_commit
    lda str_dest_ptr
    sta zp_src
    lda str_dest_ptr+1
    sta zp_src+1
    lda #0
    sta str_old_page
    sta str_old_owner
    sta str_old_owner+1
    ldy #0
    lda (zp_src),y
    cmp #'S'
    bne @publish
    iny
    lda (zp_src),y
    cmp #'D'
    bne @publish
    ldy #SD_PAGE_COUNT
    lda (zp_src),y
    beq @publish
    ldy #SD_PAGE_LO
    lda (zp_src),y
    sta str_old_page
    ldy #SD_OWNER_LO
    lda (zp_src),y
    sta str_old_owner
    iny
    lda (zp_src),y
    sta str_old_owner+1
@publish:
    jsr str_publish
    lda str_old_owner
    ora str_old_owner+1
    beq @done
    ldx str_old_page
    lda str_page_owner_lo,x
    cmp str_old_owner
    bne @done
    lda str_page_owner_hi,x
    cmp str_old_owner+1
    bne @done
    lda #0
    sta str_page_owner_lo,x
    sta str_page_owner_hi,x
@done:
    clc
    rts
.endproc

.proc str_make_image
    lda #'S'
    sta str_descriptor_image
    lda #'D'
    sta str_descriptor_image+1
    lda #1
    sta str_descriptor_image+SD_GENERATION
    lda str_length
    sta str_descriptor_image+SD_LENGTH
    lda #STRING_ARENA
    sta str_descriptor_image+SD_ARENA
    lda #STRING_ARENA_GENERATION
    sta str_descriptor_image+SD_ARENA_GENERATION
    lda str_page
    sta str_descriptor_image+SD_PAGE_LO
    lda #0
    sta str_descriptor_image+SD_PAGE_HI
    sta str_descriptor_image+SD_OFFSET
    lda str_length
    beq @empty
    lda #1
    sta str_descriptor_image+SD_PAGE_COUNT
    lda str_owner
    sta str_descriptor_image+SD_OWNER_LO
    lda str_owner+1
    sta str_descriptor_image+SD_OWNER_HI
    rts
@empty:
    sta str_descriptor_image+SD_PAGE_LO
    sta str_descriptor_image+SD_PAGE_HI
    sta str_descriptor_image+SD_PAGE_COUNT
    sta str_descriptor_image+SD_OWNER_LO
    sta str_descriptor_image+SD_OWNER_HI
    ldx #8
@reserved:
    sta str_descriptor_image,x
    inx
    cpx #12
    bne @reserved
    rts
.endproc

.proc str_select_working_page
    lda str_page
    ldx #STRING_ARENA
    ldy #STRING_ARENA_GENERATION
    jmp arena_select_page
.endproc

; Allocate destination SD. SA reserves one page only for nonempty strings.
.export str_alloc
str_alloc:
    lda #'A'
    jsr str_parse_dest_request
    jcs @error
    jsr str_req_zp
    ldy #4
      lda (zp_src),y
      sta str_length
      sta str_count
      lda str_count
    sta str_length
    lda str_length
    beq @empty
    jsr str_claim_page
    jcs @error
    jsr str_select_working_page
    bcc @clear
    ldx str_page
    lda #0
    sta str_page_owner_lo,x
    sta str_page_owner_hi,x
    sec
    rts
@clear:
    lda #0
    ldy #0
@clear_loop:
    sta $DE00,y
    iny
    bne @clear_loop
    jmp @publish
@empty:
    lda #0
    sta str_page
    sta str_owner
    sta str_owner+1
@publish:
    jsr str_make_image
    jmp str_commit
@error:
    rts

.export str_free
str_free:
    stx str_dest_ptr
    sty str_dest_ptr+1
    jsr str_load
    jcs @error
    jsr str_release_working
    lda str_dest_ptr
    sta zp_dest
    lda str_dest_ptr+1
    sta zp_dest+1
    lda #0
    ldy #0
@clear:
    sta (zp_dest),y
    iny
    cpy #12
    bne @clear
    clc
@error:
    rts

; Import bytes from normal memory into an arena-backed destination SD.
; SB request: magic, destination SD pointer, source pointer, length.
.export str_from_bytes
str_from_bytes:
    lda #'B'
    jsr str_parse_dest_request
    jcs @error
    jsr str_req_zp
    ldy #4
    lda (zp_src),y
    sta str_byte_ptr
    iny
    lda (zp_src),y
    sta str_byte_ptr+1
    iny
    lda (zp_src),y
    sta str_length
    beq @empty
    jsr str_claim_page
    jcs @error
    jsr str_select_working_page
    jcs @rollback
    lda str_byte_ptr
    sta zp_src
    lda str_byte_ptr+1
    sta zp_src+1
    ldy #0
@copy:
    lda (zp_src),y
    sta $DE00,y
    iny
    cpy str_length
    bne @copy
    jmp @commit
@empty:
    lda #0
    sta str_page
    sta str_owner
    sta str_owner+1
@commit:
    jsr str_make_image
    jmp str_commit
@rollback:
    ldx str_page
    lda #0
    sta str_page_owner_lo,x
    sta str_page_owner_hi,x
    sec
@error:
    rts

; Export one validated SD payload to a bounded normal-memory buffer.
; SE request: magic, source SD pointer, destination pointer, capacity.
.export str_export_bytes
str_export_bytes:
    stx str_request_ptr
    sty str_request_ptr+1
    jsr str_req_zp
    ldy #0
    lda (zp_src),y
    cmp #'S'
    jne str_error
    iny
    lda (zp_src),y
    cmp #'E'
    jne str_error
    iny
    lda (zp_src),y
    tax
    iny
    lda (zp_src),y
    tay
    jsr str_load
    jcs @error
    jsr str_req_zp
    ldy #6
    lda str_length
    cmp (zp_src),y
    beq @fits
    bcc @fits
    jmp str_error
@fits:
    ldy #4
    lda (zp_src),y
    sta str_byte_ptr
    iny
    lda (zp_src),y
    sta str_byte_ptr+1
    lda str_length
    beq @done
    lda str_descriptor_image+SD_PAGE_LO
    ldx #STRING_ARENA
    ldy #STRING_ARENA_GENERATION
    jsr arena_select_page
    jcs @error
    lda str_byte_ptr
    sta zp_dest
    lda str_byte_ptr+1
    sta zp_dest+1
    ldy #0
@copy:
    lda $DE00,y
    sta (zp_dest),y
    iny
    cpy str_length
    bne @copy
@done:
    lda str_length
    clc
@error:
    rts

; Copy source payload into the currently claimed page.
.proc str_copy_loaded_source
    lda str_length
    beq @done
    lda str_descriptor_image+SD_PAGE_LO
    sta str_old_page
    jsr str_select_working_page
    jcs @error
    ; source page cannot remain selected, so stage byte-by-byte across selections.
    lda #0
    sta str_index
@loop:
    lda str_old_page
    ldx #STRING_ARENA
    ldy #STRING_ARENA_GENERATION
    jsr arena_select_page
    jcs @error
    ldy str_index
    lda $DE00,y
    sta str_char
    jsr str_select_working_page
    jcs @error
    ldy str_index
    lda str_char
    sta $DE00,y
    inc str_index
    lda str_index
    cmp str_length
    bne @loop
@done:
    clc
@error:
    rts
.endproc

.export str_assign
.export str_copy
str_assign:
str_copy:
    lda #'X'
    jsr str_parse_dest_request
    jcs @error
    jsr str_req_zp
    ldy #4
    lda (zp_src),y
    tax
    iny
    lda (zp_src),y
    tay
    jsr str_load
    jcs @error
    lda str_length
    beq @empty
    lda str_descriptor_image+SD_PAGE_LO
    sta str_old_page
    jsr str_claim_page
    jcs @error
    ; copy source page saved above into new page
    lda #0
    sta str_index
@loop:
    lda str_old_page
    ldx #STRING_ARENA
    ldy #STRING_ARENA_GENERATION
    jsr arena_select_page
    jcs @rollback
    ldy str_index
    lda $DE00,y
    sta str_char
    jsr str_select_working_page
    jcs @rollback
    ldy str_index
    lda str_char
    sta $DE00,y
    inc str_index
    lda str_index
    cmp str_length
    bne @loop
    jmp @commit
@empty:
    lda #0
    sta str_page
    sta str_owner
    sta str_owner+1
@commit:
    jsr str_make_image
    jmp str_commit
@rollback:
    ldx str_page
    lda #0
    sta str_page_owner_lo,x
    sta str_page_owner_hi,x
    sec
@error:
    rts

; Remaining operations use SD handles and preserve transactional destination rules.
.export str_len
str_len:
    jsr str_load
    jcs @error
    lda str_length
@error:
    rts

.export str_asc
str_asc:
    jsr str_load
    jcs @error
    lda str_length
    bne :+
    jmp str_error
:
    lda str_descriptor_image+SD_PAGE_LO
    ldx #STRING_ARENA
    ldy #STRING_ARENA_GENERATION
    jsr arena_select_page
    jcs @error
    lda $DE00
    clc
@error:
    rts

; CHR$ request SH,dest,char.
.export str_chr
str_chr:
    lda #'H'
    jsr str_parse_dest_request
    jcs @error
    jsr str_req_zp
    ldy #4
    lda (zp_src),y
    sta str_char
    lda #1
    sta str_length
    jsr str_claim_page
    jcs @error
    jsr str_select_working_page
    jcs @rollback
    lda str_char
    sta $DE00
    jsr str_make_image
    jmp str_commit
@rollback:
    ldx str_page
    lda #0
    sta str_page_owner_lo,x
    sta str_page_owner_hi,x
    sec
@error:
    rts

; Lexicographic compare SP,left,right; A=$ff/0/1.
.export str_cmp
str_cmp:
    stx str_request_ptr
    sty str_request_ptr+1
    jsr str_req_zp
    ldy #0
    lda (zp_src),y
    cmp #'S'
    jne str_error
    iny
    lda (zp_src),y
    cmp #'P'
    jne str_error
    iny
    lda (zp_src),y
    sta str_left_ptr
    iny
    lda (zp_src),y
    sta str_left_ptr+1
    iny
    lda (zp_src),y
    sta str_right_ptr
    iny
    lda (zp_src),y
    sta str_right_ptr+1
    ldx str_left_ptr
    ldy str_left_ptr+1
    jsr str_load
    jcs @error
    lda str_length
    sta str_left_length
    lda str_descriptor_image+SD_PAGE_LO
    sta str_old_page
    ldx str_right_ptr
    ldy str_right_ptr+1
    jsr str_load
    jcs @error
    lda str_length
    sta str_right_length
    lda str_descriptor_image+SD_PAGE_LO
    sta str_page
    lda #0
    sta str_index
@loop:
    lda str_index
    cmp str_left_length
    beq @lengths
    cmp str_right_length
    beq @lengths
    lda str_old_page
    ldx #STRING_ARENA
    ldy #STRING_ARENA_GENERATION
    jsr arena_select_page
    jcs @error
    ldy str_index
    lda $DE00,y
    sta str_char
    lda str_page
    ldx #STRING_ARENA
    ldy #STRING_ARENA_GENERATION
    jsr arena_select_page
    jcs @error
    ldy str_index
    lda str_char
    cmp $DE00,y
    bcc @less
    bne @greater
    inc str_index
    bne @loop
@lengths:
    lda str_left_length
    cmp str_right_length
    bcc @less
    bne @greater
    lda #0
    clc
    rts
@less:
    lda #$ff
    clc
    rts
@greater:
    lda #1
    clc
@error:
    rts

; VAL consumes an SD and parses the stock numeric prefix (spaces, sign,
; decimal point, and E exponent).  Parsing stops at the first nonnumeric byte.
.export str_val
str_val:
    jsr str_load
    jcs @error
    lda str_descriptor_image+SD_PAGE_LO
    ldx #STRING_ARENA
    ldy #STRING_ARENA_GENERATION
    jsr arena_select_page
    jcs @error
    lda #0
    sta zp_fac1
    sta zp_fac1+1
    sta zp_fac1+2
    sta zp_fac1+3
    sta zp_fac1+4
    sta str_sign
    sta str_exponent
    sta str_exponent+1
    sta str_seen_digit
    sta str_seen_dot
    ldy #0
@spaces:
    cpy str_length
    bne :+
    jmp @scale
:
    lda $DE00,y
    cmp #' '
    bne @sign
    iny
    bne @spaces
@sign:
    cmp #'-'
    bne @plus
    lda #$80
    sta str_sign
    iny
    bne @digits
@plus:
    cmp #'+'
    bne @digits
    iny
@digits:
    cpy str_length
    beq @scale
    lda $DE00,y
    cmp #'.'
    bne @digit
    lda str_seen_dot
    bne @scale
    inc str_seen_dot
    iny
    bne @digits
@digit:
    cmp #'0'
    bcc @maybe_exp
    cmp #'9'+1
    bcs @maybe_exp
    sec
    sbc #'0'
    sta str_char
    inc str_seen_digit
    tya
    pha
    jsr str_fac_times_ten
    bcs @digit_error
    jsr str_fac_add_digit
    bcs @digit_error
    pla
    tay
    lda str_seen_dot
    beq :+
    dec str_exponent
    lda str_exponent
    cmp #$ff
    bne :+
    dec str_exponent+1
:
    iny
    bne @digits
@digit_error:
    pla
    sec
    rts
@maybe_exp:
    cmp #'E'
    beq @exponent
    cmp #'e'
    bne @scale
@exponent:
    lda str_seen_digit
    beq @scale
    iny
    jsr str_parse_exponent
@scale:
    lda str_seen_digit
    bne :+
    lda #0
    sta zp_fac1
:
    lda str_exponent+1
    bmi @scale_down
@scale_up:
    lda str_exponent
    ora str_exponent+1
    beq @apply
    jsr str_fac_times_ten
    jcs @error
    dec str_exponent
    lda str_exponent
    cmp #$ff
    bne @scale_up
    dec str_exponent+1
    jmp @scale_up
@scale_down:
    jsr str_fac_div_ten
    jcs @error
    inc str_exponent
    bne @scale_down
    inc str_exponent+1
    bmi @scale_down
@apply:
    lda str_sign
    beq @success
    jsr math_negate
@success:
    clc
@error:
    rts

.proc str_fac_times_ten
    lda #$84
    sta zp_arg
    lda #$20
    sta zp_arg+1
    lda #0
    sta zp_arg+2
    sta zp_arg+3
    sta zp_arg+4
    jmp math_mul
.endproc

.proc str_fac_div_ten
    ; Multiplication avoids the divide entry's ARG/FAC operand ordering.
    ; C64 packed 0.1 is $7d,$4c,$cc,$cc,$cd.
    lda #$7d
    sta zp_arg
    lda #$4c
    sta zp_arg+1
    lda #$cc
    sta zp_arg+2
    sta zp_arg+3
    lda #$cd
    sta zp_arg+4
    jmp math_mul
.endproc

.proc str_fac_add_digit
    ldx #0
@save:
    lda zp_fac1,x
    sta str_fac_save,x
    inx
    cpx #5
    bne @save
    ldx str_char
    ldy #0
    jsr math_int_to_float
    ldx #0
@arg:
    lda str_fac_save,x
    sta zp_arg,x
    inx
    cpx #5
    bne @arg
    jmp math_add
.endproc

; Y points just beyond E.  A malformed exponent is ignored, as stock VAL does.
.proc str_parse_exponent
    lda #0
    sta str_value
    sta str_value+1
    sta str_char
    cpy str_length
    bne :+
    jmp @done
:
    lda $DE00,y
    cmp #'-'
    bne @plus
    inc str_char
    iny
    bne @loop
@plus:
    cmp #'+'
    bne @loop
    iny
@loop:
    cpy str_length
    beq @apply
    lda $DE00,y
    cmp #'0'
    bcc @apply
    cmp #'9'+1
    bcs @apply
    sec
    sbc #'0'
    pha
    lda str_value
    sta str_left_ptr
    lda str_value+1
    sta str_left_ptr+1
    asl str_value
    rol str_value+1
    asl str_left_ptr
    rol str_left_ptr+1
    asl str_left_ptr
    rol str_left_ptr+1
    asl str_left_ptr
    rol str_left_ptr+1
    clc
    lda str_value
    adc str_left_ptr
    sta str_value
    lda str_value+1
    adc str_left_ptr+1
    sta str_value+1
    pla
    clc
    adc str_value
    sta str_value
    bcc :+
    inc str_value+1
:
    iny
    bne @loop
@apply:
    lda str_char
    beq @positive
    sec
    lda str_exponent
    sbc str_value
    sta str_exponent
    lda str_exponent+1
    sbc str_value+1
    sta str_exponent+1
    rts
@positive:
    clc
    lda str_exponent
    adc str_value
    sta str_exponent
    lda str_exponent+1
    adc str_value+1
    sta str_exponent+1
@done:
    rts
.endproc

.export str_left
.export str_right
.export str_mid
.export str_concat
.export str_str

; Copy str_count bytes from str_old_page/str_source_offset to str_page/str_index.
.proc str_copy_page_range
    lda str_count
    beq @done
@loop:
    lda str_old_page
    ldx #STRING_ARENA
    ldy #STRING_ARENA_GENERATION
    jsr arena_select_page
    jcs @error
    ldy str_source_offset
    lda $DE00,y
    sta str_char
    jsr str_select_working_page
    jcs @error
    ldy str_index
    lda str_char
    sta $DE00,y
    inc str_source_offset
    inc str_index
    dec str_count
    bne @loop
@done:
    clc
@error:
    rts
.endproc

str_concat:
    lda #'C'
    jsr str_parse_dest_request
    jcs @error
    jsr str_req_zp
    ldy #4
    lda (zp_src),y
    sta str_left_ptr
    iny
    lda (zp_src),y
    sta str_left_ptr+1
    iny
    lda (zp_src),y
    sta str_right_ptr
    iny
    lda (zp_src),y
    sta str_right_ptr+1
    ldx str_left_ptr
    ldy str_left_ptr+1
    jsr str_load
    jcs @error
    lda str_length
    sta str_left_length
    lda str_descriptor_image+SD_PAGE_LO
    sta str_old_page
    ldx str_right_ptr
    ldy str_right_ptr+1
    jsr str_load
    jcs @error
    lda str_length
    sta str_right_length
    clc
    adc str_left_length
    bcs @too_long
    sta str_length
    lda str_descriptor_image+SD_PAGE_LO
    sta str_right_page
    lda str_length
    beq @empty
    jsr str_claim_page
    jcs @error
    lda #0
    sta str_index
    sta str_source_offset
    lda str_left_length
    sta str_count
    jsr str_copy_page_range
    jcs @rollback
    lda str_right_page
    sta str_old_page
    lda #0
    sta str_source_offset
    lda str_right_length
    sta str_count
    jsr str_copy_page_range
    jcs @rollback
    jmp @commit
@empty:
    lda #0
    sta str_page
    sta str_owner
    sta str_owner+1
@commit:
    jsr str_make_image
    jmp str_commit
@rollback:
    ldx str_page
    lda #0
    sta str_page_owner_lo,x
    sta str_page_owner_hi,x
    sec
    rts
@too_long:
    lda #ERR_STRING_TOO_LONG
    sec
@error:
    rts

; Shared LEFT/RIGHT parser; A is magic, str_source_offset selected by caller.
.proc str_parse_slice
    jsr str_parse_dest_request
    jcs @error
    jsr str_req_zp
    ldy #4
    lda (zp_src),y
    tax
    iny
    lda (zp_src),y
    tay
    jsr str_load
    jcs @error
    lda str_descriptor_image+SD_PAGE_LO
    sta str_old_page
    jsr str_req_zp
    ldy #6
    lda (zp_src),y
    sta str_count
    clc
@error:
    rts
.endproc

.proc str_finish_slice
    lda str_count
    sta str_length
    beq @empty
    jsr str_claim_page
    jcs @error
    lda #0
    sta str_index
    jsr str_copy_page_range
    jcs @rollback
    jmp @commit
@empty:
    lda #0
    sta str_page
    sta str_owner
    sta str_owner+1
@commit:
    jsr str_make_image
    jmp str_commit
@rollback:
    ldx str_page
    lda #0
    sta str_page_owner_lo,x
    sta str_page_owner_hi,x
    sec
@error:
    rts
.endproc

str_left:
    lda #'L'
    jsr str_parse_slice
    jcs @error
    lda str_count
    cmp str_length
    bcc :+
    lda str_length
    sta str_count
:
    lda #0
    sta str_source_offset
    jmp str_finish_slice
@error:
    rts

str_right:
    lda #'R'
    jsr str_parse_slice
    jcs @error
    lda str_count
    cmp str_length
    bcc :+
    lda str_length
    sta str_count
:
    lda str_length
    sec
    sbc str_count
    sta str_source_offset
    jmp str_finish_slice
@error:
    rts

str_mid:
    lda #'M'
    jsr str_parse_dest_request
    jcs @error
    jsr str_req_zp
    ldy #4
    lda (zp_src),y
    tax
    iny
    lda (zp_src),y
    tay
    jsr str_load
    jcs @error
    lda str_descriptor_image+SD_PAGE_LO
    sta str_old_page
    jsr str_req_zp
    ldy #6
    lda (zp_src),y
    beq @illegal
    sec
    sbc #1
    sta str_source_offset
    iny
    lda (zp_src),y
    sta str_count
    lda str_source_offset
    cmp str_length
    bcs @empty
    lda str_length
    sec
    sbc str_source_offset
    cmp str_count
    bcs :+
    sta str_count
:
    jmp str_finish_slice
@empty:
    lda #0
    sta str_count
    jmp str_finish_slice
@illegal:
    jmp str_error
@error:
    rts

; Stock formatting needed by the runtime contract: integral values and .5 form.
str_str:
    lda #'T'
    jsr str_parse_dest_request
    jcs @error
    lda zp_fac1+1
    and #$80
    beq @positive_sign
    lda #'-'
    bne @save_sign
@positive_sign:
    lda #' '
@save_sign:
    sta str_sign
    lda #0
    sta str_decimals
@try_integer:
    lda #0
    sta math_fac_type
    jsr math_float_to_int
    bcc @integer_ready
    lda str_decimals
    cmp #6
    bcc :+
    jmp @error
:
    ; Scale by ten until the finite value becomes integral.
    lda #$84
    sta zp_arg
    lda #$20
    sta zp_arg+1
    lda #0
    sta zp_arg+2
    sta zp_arg+3
    sta zp_arg+4
    jsr math_mul
    jcs @error
    inc str_decimals
    jmp @try_integer
@integer_ready:
    stx str_value
    sty str_value+1
    lda str_sign
    cmp #'-'
    bne @allocate
    sec
    lda #0
    sbc str_value
    sta str_value
    lda #0
    sbc str_value+1
    sta str_value+1
@allocate:
    lda #8
    sta str_length
    jsr str_claim_page
    jcs @error
    jsr str_select_working_page
    jcs @rollback
    lda str_sign
    sta $DE00
    lda #0
    sta str_index
    ldx #0
@powers:
    lda #0
    sta str_count
@subtract:
    lda str_value+1
    cmp decimal_pow10_hi,x
    bcc @digit
    bne @take
    lda str_value
    cmp decimal_pow10_lo,x
    bcc @digit
@take:
    sec
    lda str_value
    sbc decimal_pow10_lo,x
    sta str_value
    lda str_value+1
    sbc decimal_pow10_hi,x
    sta str_value+1
    inc str_count
    jmp @subtract
@digit:
    lda str_count
    ora str_index
    beq @next
    lda str_count
    clc
    adc #'0'
    sta str_char
    ldy str_index
    iny
    lda str_char
    tay
    ; recover destination index after using Y for the byte value
    ldy str_index
    iny
    sta $DE00,y
    inc str_index
@next:
    inx
    cpx #5
    bne @powers
    lda str_index
    bne :+
    lda #'0'
    sta $DE01
    lda #1
    sta str_index
:
    ; Insert decimal point before the final str_decimals digits.
    lda str_decimals
    beq @length
    lda str_index
    cmp str_decimals
    bcs @shift
    ; Values below one use the stock " .digits" spelling.
    ldy str_index
@shift_small:
    lda $DE01,y
    sta $DE02,y
    dey
    bne @shift_small
    lda #'.'
    sta $DE01
    inc str_index
    jmp @length
@shift:
    lda str_index
    sec
    sbc str_decimals
    clc
    adc #1
    sta str_source_offset
    ldy str_index
@shift_loop:
    lda $DE00,y
    sta $DE01,y
    cpy str_source_offset
    beq @dot
    dey
    bne @shift_loop
@dot:
    ldy str_source_offset
    lda #'.'
    sta $DE00,y
    inc str_index
@length:
    lda str_index
    clc
    adc #1
    sta str_length
@publish:
    jsr str_make_image
    jmp str_commit
@rollback:
    ldx str_page
    lda #0
    sta str_page_owner_lo,x
    sta str_page_owner_hi,x
    sec
@error:
    rts

decimal_pow10_lo: .byte $10,$E8,$64,$0A,$01
decimal_pow10_hi: .byte $27,$03,$00,$00,$00
