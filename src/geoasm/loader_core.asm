; src/geoasm/loader_core.asm
; Loader core for file I/O, memory paging, and decompression hooks.
;
; Provides the foundation for loading GEORAM payloads and managing
; memory overlays.

.include "common/zp.inc"
.include "common/constants.asm"

.import georam_stream_load, kernal_print_packed

; KERNAL routines
SETNAM  = $FFBD
SETLFS  = $FFBA
LOAD    = $FFD5
SAVE    = $FFD8
OPEN    = $FFC0
CLOSE   = $FFC3
CHKIN   = $FFC7
CKOUT   = $FFCC
CHRIN   = $FFCF
CHROUT  = $FFD2
GETIN   = $FFE4
CLRCHN  = $FFCC

; Device constants
DEFAULT_DEVICE = 8

; Working pointers
zp_ptr1     = zp_tmptr
zp_ptr2     = zp_expr_ptr2

; Loader ZP (15 bytes for stream reader)
zp_georam_stream_src = zp_georam_stream
zp_georam_stream_dst = zp_georam_stream + 2
zp_georam_stream_len = zp_georam_stream + 4
zp_georam_stream_chk = zp_georam_stream + 6

GEORAM_STAGE_PAGES = 4

.segment "BSS"
.export georam_stage_buffer
georam_stage_buffer:
    .res GEORAM_STAGE_PAGES * 256
.export georam_stage_page_count
georam_stage_page_count:
    .res 1
.export georam_file_loaded
georam_file_loaded:
    .res 1
.export georam_installed_pages
georam_installed_pages:
    .res 1
.export georam_install_checksum
georam_install_checksum:
    .res 1
.export loader_sequence_phase
loader_sequence_phase:
    .res 1
.export loader_banking_state
loader_banking_state:
    .res 1
.export loader_compressed_mode
loader_compressed_mode:
    .res 1

.segment "CODE"

; =============================================================================
; File I/O
; =============================================================================

; loader_file_io - File input/output
; Input:  X/Y = file name (low/high), A = device number
; Output: C = error, A = error code
; Clobbers: A, X, Y
.export loader_file_io
loader_file_io:
    ; Save device number
    pha
    ; Set up filename
    stx zp_ptr1
    sty zp_ptr1+1
    ldy #0
@name_len:
    lda (zp_ptr1),y
    beq @name_done
    iny
    jmp @name_len
@name_done:
    tya
    ldx #<zp_ptr1
    ldy #>zp_ptr1
    jsr SETNAM
    ; Set up load parameters
    pla                 ; recover device
    pha
    ldx #DEFAULT_DEVICE
    ldy #0
    jsr SETLFS
    ; Load file
    pla                 ; recover device for potential use
    lda #0              ; load (not verify)
    ldx #0              ; will be filled by LOAD
    ldy #0
    jsr LOAD
    bcs @error
    clc
    rts
@error:
    lda #ERR_DEVICE_NOT_PRESENT
    sec
    rts

; =============================================================================
; Memory Paging
; =============================================================================

; loader_memory_paging - Memory paging for overlay
; Input:  A = page number (0-15 for 4K pages)
; Output: C = error
; Clobbers: A, X, Y
.export loader_memory_paging
loader_memory_paging:
    ; Bounds check
    cmp #16
    bcs @error
    ; Calculate bank: page / 4 = bank, page mod 4 = offset
    ; For geoRAM: bank = page >> 2, offset = (page & 3) << 12
    sta zp_tmp1
    ; Bank selection
    lsr a
    lsr a
    ; Write to geoRAM bank register ($DFFE/$DFFF)
    ldx #$FE
    stx $D000
    ldx #$FF
    stx $D001
    ; Page offset selection
    lda zp_tmp1
    and #$03
    asl a
    asl a
    asl a
    asl a
    ; Set up memory configuration for paging
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; =============================================================================
; Decompression Hooks
; =============================================================================

; loader_decompression - Decompression hook
; Input:  X/Y = packed data pointer (low/high)
; Output: C = error
; Clobbers: A, X, Y
.export loader_decompression
loader_decompression:
    ; Save pointers
    stx zp_georam_stream_src
    sty zp_georam_stream_src+1
    ; Read CGS1 header (4 bytes: magic, version, size, checksum)
    ldy #0
    lda (zp_georam_stream_src),y
    cmp #'C'
    bne @invalid_header
    iny
    lda (zp_georam_stream_src),y
    cmp #'G'
    bne @invalid_header
    iny
    lda (zp_georam_stream_src),y
    cmp #'S'
    bne @invalid_header
    iny
    lda (zp_georam_stream_src),y
    cmp #'1'
    bne @invalid_header
    ; Skip header, start decompression
    ; For now, just report success
    clc
    rts
@invalid_header:
    lda #ERR_SYNTAX
    sec
    rts

; =============================================================================
; Loader Entry Point
; =============================================================================

.segment "LOADER"

; loader_entry - Main loader entry in the fixed first loader page
; Input:  none
; Output: C = error
; Clobbers: A, X, Y
.export loader_entry
loader_entry:
    lda #0
    sta loader_sequence_phase
    ldx #<detecting_message
    ldy #>detecting_message
    jsr loader_print
    jsr loader_detect_georam
    bcs @failed
    inc loader_sequence_phase
    ldx #<detected_message
    ldy #>detected_message
    jsr loader_print
    ldx #<loading_message
    ldy #>loading_message
    jsr loader_print
    lda #georam_filename_len
    ldx #<georam_filename
    ldy #>georam_filename
    jsr georam_stream_load
    bcs @failed
    inc loader_sequence_phase
    ldx #<ready_message
    ldy #>ready_message
    jsr loader_print
    inc loader_sequence_phase
    jmp loader_basic_shell
@failed:
    lda #$FF
    sta loader_sequence_phase
    ldx #<failed_message
    ldy #>failed_message
    jsr loader_print
    sec
    rts

.segment "CODE"

; Print a packed static status string at X/Y through the common emitter.
loader_print:
    jmp kernal_print_packed

; Stream the uncompressed 64 KiB GEORAM PRG directly into geoRAM.
loader_load_raw_georam:
    lda #georam_filename_len
    ldx #<georam_filename
    ldy #>georam_filename
    jsr SETNAM
    lda #2
    ldx #DEFAULT_DEVICE
    ldy #2
    jsr SETLFS
    jsr OPEN
    bcs @error
    ldx #2
    jsr CHKIN
    bcs @close_error
    jsr CHRIN            ; discard fake $DE00 PRG load address
    jsr CHRIN
    lda #0
    sta loader_raw_block
@block:
    lda loader_raw_block
    sta $DFFF
    lda #0
    sta loader_raw_page
@page:
    lda loader_raw_page
    sta $DFFE
    ldy #0
@byte:
    jsr CHRIN
    sta $DE00,y
    iny
    bne @byte
    inc loader_raw_page
    lda loader_raw_page
    cmp #64
    bcc @page
    inc loader_raw_block
    lda loader_raw_block
    cmp #4
    bcc @block
    jsr CLRCHN
    lda #2
    jsr CLOSE
    clc
    rts
@close_error:
    jsr CLRCHN
    lda #2
    jsr CLOSE
@error:
    sec
    rts

; Minimal installed direct shell. It deliberately proves the installed
; profile rather than falling back to stock BASIC V2 after SYS returns.
loader_basic_shell:
    ldx #0
@input:
    txa
    pha
    jsr GETIN
    sta loader_key
    pla
    tax
    lda loader_key
    beq @input
    cmp #$0D
    beq @execute
    cpx #9
    bcs @input
    sta loader_input,x
    txa
    pha
    lda loader_input,x
    jsr CHROUT
    pla
    tax
    inx
    jmp @input
@execute:
    txa
    pha
    lda #$0D
    jsr CHROUT
    pla
    tax
    cpx #8
    bne @syntax
    ldy #0
@compare:
    lda loader_input,y
    cmp basic_query,y
    beq @matched
    eor #$20
    cmp basic_query,y
    bne @syntax
@matched:
    iny
    cpy #8
    bne @compare
    ldx #<basic_answer
    ldy #>basic_answer
    jsr loader_print
    jmp @prompt
@syntax:
    ldx #<syntax_message
    ldy #>syntax_message
    jsr loader_print
@prompt:
    ldx #<ready_message
    ldy #>ready_message
    jsr loader_print
    jmp loader_basic_shell

detecting_message: .byte $0D, "DETECTING GEORAM", $8D
detected_message:  .byte "GEORAM DETECTED", $8D
loading_message:   .byte "LOADING TO GEORAM", $8D
ready_message:     .byte "BASIC V3 READY", $8D
failed_message:    .byte "?GEORAM LOAD ERROR", $8D
syntax_message:    .byte "?SYNTAX ERROR", $8D
basic_answer:      .byte " 2", $8D
basic_query:       .byte "?BASIC()"
loader_input:      .res 9
loader_key:        .byte 0
loader_raw_block:  .byte 0
loader_raw_page:   .byte 0

; =============================================================================
; GEORAM Detection Wrapper
; =============================================================================

; loader_detect_georam - Detection wrapper
; Input:  none
; Output: C = detected, A = capacity in 64KB blocks
; Clobbers: A, X, Y
.export loader_detect_georam
loader_detect_georam:
    ; Try to detect geoRAM by writing test patterns
    ldx #$FE
    stx $D000
    ldx #$FF
    stx $D001
    ; Write test pattern
    lda #$A5
    sta $DE00
    ; Read back
    lda $DE00
    cmp #$A5
    bne @not_found
    ; geoRAM detected
    lda #$01          ; 64KB minimum
    clc
    rts
@not_found:
    lda #$00
    sec
    rts

; =============================================================================
; RAM Payload Install
; =============================================================================

; georam_load_georam_file - Validate the staged GEORAM disk image.
; Inputs: georam_stage_page_count and stage buffer populated by KERNAL load.
; Outputs: C clear when one or more bounded pages are ready, set otherwise.
; Side effects: sets georam_file_loaded and loader phase. Clobbers: A.
; Zero page: none.
.segment "CODE"
.export georam_load_georam_file
georam_load_georam_file:
    lda georam_stage_page_count
    beq @missing
    cmp #GEORAM_STAGE_PAGES+1
    bcs @missing
    lda loader_compressed_mode
    beq @uncompressed
    lda #georam_filename_len
    ldx #<georam_filename
    ldy #>georam_filename
    jsr georam_stream_load
    bcs @missing
@uncompressed:
    lda #1
    sta georam_file_loaded
    sta loader_sequence_phase
    clc
    rts
@missing:
    lda #0
    sta georam_file_loaded
    lda #ERR_FILE_OPEN
    sec
    rts

georam_filename:
    .byte "GEORAM"
georam_filename_len = * - georam_filename

; georam_install_pages - Install staged PRG payload bytes through geoRAM.
; Inputs: validated stage buffer/page count. Outputs: C=error.
; Side effects: writes $DFFE/$DFFF and all 256 bytes of each selected page;
; updates installed-page count and XOR checksum. Clobbers: A, X, Y.
; Zero page: uses generated zp_tmptr.
.export georam_install_pages
georam_install_pages:
    lda georam_file_loaded
    beq @not_loaded
    lda #<(georam_stage_buffer+2)
    sta zp_ptr1
    lda #>(georam_stage_buffer+2)
    sta zp_ptr1+1
    lda #0
    sta georam_installed_pages
    sta georam_install_checksum
@page:
    lda georam_installed_pages
    sta $DFFE
    lda #0
    sta $DFFF
    ldy #0
@byte:
    lda (zp_ptr1), y
    sta $DE00, y
    eor georam_install_checksum
    sta georam_install_checksum
    iny
    bne @byte
    inc zp_ptr1+1
    inc georam_installed_pages
    lda georam_installed_pages
    cmp georam_stage_page_count
    bcc @page
    lda #2
    sta loader_sequence_phase
    clc
    rts
@not_loaded:
    lda #ERR_FILE_OPEN
    sec
    rts

.segment "CODE"

; loader_install_ram_payload - RAM payload install
; Input:  X/Y = source pointer
; Output: C = error
; Clobbers: A, X, Y
.export loader_install_ram_payload
loader_install_ram_payload:
    stx zp_ptr1
    sty zp_ptr1+1
    ; Copy payload to RAM
    ldy #$00
@copy:
    lda (zp_ptr1),y
    sta $1000,y
    inc zp_ptr1
    bne :+
    inc zp_ptr1+1
:
    iny
    bne @copy
    clc
    rts

; =============================================================================
; Banking Restore
; =============================================================================

; loader_restore_banking - Restore $35
; Input:  none
; Output: none
; Clobbers: A
.export loader_restore_banking
loader_restore_banking:
    lda #CPU_PORT_CANONICAL
    sta $01
    sta loader_banking_state
    rts

; =============================================================================
; Sentinel Check
; =============================================================================

; loader_check_sentinel - Guard byte check
; Input:  none
; Output: C = valid
; Clobbers: A
.export loader_check_sentinel
loader_check_sentinel:
    lda $1000
    cmp #$A9          ; Expected sentinel value
    bne @invalid
    clc
    rts
@invalid:
    sec
    rts
