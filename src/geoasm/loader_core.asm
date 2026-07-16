; src/geoasm/loader_core.asm
; Loader core: dual-device install (geoRAM + REU), paging, and decompression.
;
; Prefer geoRAM when both devices validate. REU uses the real REC probe from
; reu_detect.asm. Session expansion profile is published via expansion_profile.

.include "common/zp.inc"
.include "common/constants.asm"

.import georam_stream_load, georam_stream_device
.import detect_georam, compiler_init
.import detect_capacity_blocks
.import detect_reu
.import detect_reu_capacity_banks
.import detect_reu_valid
.import expansion_clear
.import expansion_publish
.import expansion_mark_ready
.import expansion_check_skip_reload
.import expansion_store
.import expansion_reu_assist
.import expansion_capacity_georam
.import expansion_capacity_reu
.import expansion_reason
.import expansion_session_ready
.import expansion_image_fingerprint
.import compressor_stream
.import kernal_chrin, kernal_chkin, kernal_clrchn
.import kernal_close, kernal_load, kernal_open
.import kernal_print_packed, kernal_setlfs, kernal_setnam

; Expansion store / reason constants (must match expansion_profile.asm)
EXPANSION_STORE_NONE   = 0
EXPANSION_STORE_GEORAM = 1
EXPANSION_STORE_REU    = 2
EXPANSION_REASON_NONE     = 0
EXPANSION_REASON_GEORAM   = 1
EXPANSION_REASON_REU      = 2
EXPANSION_REASON_FALLBACK = 3

; REU registers (install path DMA)
REU_COMMAND = $DF01
REU_C64_LO  = $DF02
REU_C64_HI  = $DF03
REU_REU_LO  = $DF04
REU_REU_HI  = $DF05
REU_REU_BNK = $DF06
REU_LEN_LO  = $DF07
REU_LEN_HI  = $DF08
REU_IRQMASK = $DF09
REU_ADDRCTL = $DF0A
REU_CMD_TO_REU = $80

DEFAULT_DEVICE = 8

zp_ptr1     = zp_tmptr
zp_ptr2     = zp_expr_ptr2

zp_georam_stream_src = zp_georam_stream
zp_georam_stream_dst = zp_georam_stream + 2
zp_georam_stream_len = zp_georam_stream + 4
zp_georam_stream_chk = zp_georam_stream + 6

; Bounded stage: PRG header + two payload pages (install validation / REU DMA).
GEORAM_STAGE_PAGES = 2
GEORAM_STAGE_BYTES = 2 + (GEORAM_STAGE_PAGES * 256)

.segment "BSS"
.export georam_stage_buffer
georam_stage_buffer:
    .res GEORAM_STAGE_BYTES
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
.export loader_georam_ok
loader_georam_ok:
    .res 1
.export loader_reu_ok
loader_reu_ok:
    .res 1
.export loader_candidate_image_fp
loader_candidate_image_fp:
    .res 1
loader_geo_pages_lo:
    .res 1
loader_geo_pages_hi:
    .res 1
loader_reu_bank:
    .res 1
loader_reu_page:
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
    pha
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
    jsr kernal_setnam
    pla
    pha
    ldx #DEFAULT_DEVICE
    ldy #0
    jsr kernal_setlfs
    pla
    lda #0
    ldx #0
    ldy #0
    jsr kernal_load
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
    cmp #16
    bcs @error
    sta zp_tmp1
    lsr a
    lsr a
    sta zp_gr_block
    sta $DFFF
    lda zp_tmp1
    and #$03
    asl a
    asl a
    asl a
    asl a
    sta zp_gr_page
    sta $DFFE
    clc
    rts
@error:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; =============================================================================
; Decompression Hooks
; =============================================================================

; loader_decompression - In-memory CGS1/RLE decompress hook
; Input:  X/Y = packed data pointer (low/high)
; Output: C=0 success with A=unpacked length; C=1 and A=error on bad input
; Clobbers: A, X, Y
; Side effects: writes compressor_out_buffer (or zp_georam_stream+2 dest)
; Note: disk-to-geoRAM CGS1 install uses georam_stream_load, not this path.
.export loader_decompression
loader_decompression:
    jmp compressor_stream

; =============================================================================
; Loader Entry Point
; =============================================================================

.segment "LOADER"

; loader_entry - Dual-device install at $080D
; Probe geoRAM+REU, prefer geoRAM store, fingerprint skip-reload, load image,
; publish expansion profile; neither device → fail. Success → compiler_init.
; Input:  none
; Output: C = error (failure path); success jumps to compiler_init
; Clobbers: A, X, Y
.export loader_entry
loader_entry:
    lda #$00
    sta loader_sequence_phase
    lda #$2F
    sta $00
    lda #CPU_PORT_CANONICAL
    sta $01
    ldx #<detecting_message
    ldy #>detecting_message
    jsr loader_print
    jsr loader_detect_georam
    bcs @failed
    inc loader_sequence_phase

    ; Candidate image fingerprint for skip-reload (stable per build class)
    lda #$C1
    eor expansion_store
    eor expansion_capacity_georam
    eor expansion_capacity_reu
    sta loader_candidate_image_fp
    lda loader_candidate_image_fp
    jsr expansion_check_skip_reload
    bcc @skip_reload

    ldx #<detected_message
    ldy #>detected_message
    jsr loader_print
    ldx #<loading_message
    ldy #>loading_message
    jsr loader_print

    lda expansion_store
    cmp #EXPANSION_STORE_GEORAM
    beq @load_georam
    cmp #EXPANSION_STORE_REU
    beq @load_reu
    jmp @failed

@load_georam:
    jsr loader_install_selected_georam
    bcs @failed
    jmp @loaded

@load_reu:
    jsr loader_load_georam_into_reu
    bcs @failed
    jsr loader_apply_reu_patch
    bcs @failed

@loaded:
    lda loader_candidate_image_fp
    jsr expansion_mark_ready
    jsr expansion_publish
    inc loader_sequence_phase
    jmp @ready

@skip_reload:
    inc loader_sequence_phase

@ready:
    jsr loader_restore_banking
    ldx #<ready_message
    ldy #>ready_message
    jsr loader_print
    inc loader_sequence_phase
    jmp compiler_init

@failed:
    lda #$FF
    sta loader_sequence_phase
    jsr expansion_clear
    jsr loader_restore_banking
    ldx #<failed_message
    ldy #>failed_message
    jsr loader_print
    lda #ERR_LOAD
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
    jsr kernal_setnam
    lda #2
    ldx georam_stream_device
    ldy #2
    jsr kernal_setlfs
    jsr kernal_open
    bcs @error
    ldx #2
    jsr kernal_chkin
    bcs @close_error
    jsr kernal_chrin     ; discard fake $DE00 PRG load address
    jsr kernal_chrin
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
    jsr kernal_chrin
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
    jsr kernal_clrchn
    lda #2
    jsr kernal_close
    clc
    rts
@close_error:
    jsr kernal_clrchn
    lda #2
    jsr kernal_close
@error:
    sec
    rts

; Load the geoRAM-canonical GEORAM image into REU via per-page DMA.
; Opens "GEORAM", skips the fake $DE00 PRG header, DMA-writes pages to REU
; addresses that match geoRAM linear order (bank = block, page offset).
loader_load_georam_into_reu:
    lda #georam_filename_len
    ldx #<georam_filename
    ldy #>georam_filename
    jsr kernal_setnam
    lda #2
    ldx georam_stream_device
    ldy #2
    jsr kernal_setlfs
    jsr kernal_open
    bcs @error
    ldx #2
    jsr kernal_chkin
    bcs @close_error
    jsr kernal_chrin
    jsr kernal_chrin
    lda #0
    sta loader_reu_bank
    lda #$1F
    sta REU_IRQMASK
    lda #0
    sta REU_ADDRCTL
@bank:
    lda #0
    sta loader_reu_page
@page:
    ldy #0
@byte:
    jsr kernal_chrin
    sta georam_stage_buffer,y
    iny
    bne @byte
    ; DMA 256 bytes from stage buffer to REU
    lda #<georam_stage_buffer
    sta REU_C64_LO
    lda #>georam_stage_buffer
    sta REU_C64_HI
    lda #0
    sta REU_REU_LO
    lda loader_reu_page
    sta REU_REU_HI
    lda loader_reu_bank
    sta REU_REU_BNK
    lda #0
    sta REU_LEN_LO
    lda #1                      ; length 256
    sta REU_LEN_HI
    lda #REU_CMD_TO_REU
    sta REU_COMMAND
    inc loader_reu_page
    lda loader_reu_page
    cmp #64
    bcc @page
    inc loader_reu_bank
    lda loader_reu_bank
    cmp #4
    bcc @bank
    jsr kernal_clrchn
    lda #2
    jsr kernal_close
    clc
    rts
@close_error:
    jsr kernal_clrchn
    lda #2
    jsr kernal_close
@error:
    sec
    rts

; Apply the small REU patch file ("REU") if present.
; Envelope: magic 'R''E''U''1', version u16, image fingerprint byte.
; Rejects fingerprint mismatch with the installed image.
loader_apply_reu_patch:
    lda #reu_filename_len
    ldx #<reu_filename
    ldy #>reu_filename
    jsr kernal_setnam
    lda #2
    ldx georam_stream_device
    ldy #2
    jsr kernal_setlfs
    jsr kernal_open
    bcs @error
    ldx #2
    jsr kernal_chkin
    bcs @close_error
    ldx #0
@magic:
    jsr kernal_chrin
    cmp reu_patch_magic,x
    bne @close_error
    inx
    cpx #4
    bcc @magic
    jsr kernal_chrin                    ; version lo
    jsr kernal_chrin                    ; version hi
    jsr kernal_chrin                    ; paired GEORAM image fingerprint
    cmp loader_candidate_image_fp
    bne @close_error
    jsr kernal_clrchn
    lda #2
    jsr kernal_close
    clc
    rts
@close_error:
    jsr kernal_clrchn
    lda #2
    jsr kernal_close
@error:
    sec
    rts

reu_patch_magic:
    .byte "REU1"

detecting_message: .byte $0D, "DETECTING GEORAM", $8D
detected_message:  .byte "GEORAM DETECTED", $8D
loading_message:   .byte "LOADING TO GEORAM", $8D
ready_message:     .byte "BASIC V3 READY", $8D
failed_message:    .byte "?GEORAM LOAD ERROR", $8D
loader_raw_block:  .byte 0
loader_raw_page:   .byte 0

; =============================================================================
; Dual-device detection wrapper
; =============================================================================

; loader_detect_georam - Dual probe: detect_georam + detect_reu, prefer geoRAM
; Input:  none
; Output: C=0 selected store published (X/Y=geo pages when geo store),
;         C=1 neither device valid
; Clobbers: A, X, Y
.export loader_detect_georam
loader_detect_georam:
    lda #CPU_PORT_CANONICAL
    sta $01
    lda #0
    sta loader_georam_ok
    sta loader_reu_ok
    ; Clear selection fields only. Keep expansion_session_ready /
    ; expansion_image_fingerprint so fingerprint skip-reload can still match
    ; after a successful re-probe (QUIT re-entry / second SYS).
    sta expansion_store
    sta expansion_reu_assist
    sta expansion_capacity_georam
    sta expansion_capacity_reu
    sta expansion_reason

    jsr detect_georam
    bcs @after_geo
    lda #1
    sta loader_georam_ok
    stx loader_geo_pages_lo
    sty loader_geo_pages_hi
@after_geo:
    jsr detect_reu
    bcs @after_reu
    lda #1
    sta loader_reu_ok
@after_reu:
    ; Selection: prefer geoRAM when both OK
    lda loader_georam_ok
    beq @try_reu_only
    lda #EXPANSION_STORE_GEORAM
    sta expansion_store
    lda detect_capacity_blocks
    sta expansion_capacity_georam
    lda loader_reu_ok
    sta expansion_reu_assist
    beq @geo_cap_reu_zero
    lda detect_reu_capacity_banks
    sta expansion_capacity_reu
    jmp @geo_reason
@geo_cap_reu_zero:
    lda #0
    sta expansion_capacity_reu
@geo_reason:
    lda #EXPANSION_REASON_GEORAM
    sta expansion_reason
    jsr expansion_publish
    ldx loader_geo_pages_lo
    ldy loader_geo_pages_hi
    clc
    rts

@try_reu_only:
    lda loader_reu_ok
    beq @neither
    lda #EXPANSION_STORE_REU
    sta expansion_store
    lda #0
    sta expansion_reu_assist
    sta expansion_capacity_georam
    lda detect_reu_capacity_banks
    sta expansion_capacity_reu
    lda #EXPANSION_REASON_REU
    sta expansion_reason
    jsr expansion_publish
    clc
    rts

@neither:
    ; Full clear including skip-reload state: no store is usable this session.
    jsr expansion_clear
    lda #ERR_DEVICE_NOT_PRESENT
    sec
    rts

; Install the compressed CGS1 sidecar when present, falling back to the
; canonical raw image. The stream reader rejects a raw sidecar before writing
; payload bytes, so this retry cannot corrupt a successfully detected device.
loader_install_selected_georam:
    lda zp_fa
    cmp #8
    bcc @default_device
    cmp #12
    bcs @default_device
    bne @device_ready
@default_device:
    lda #DEFAULT_DEVICE
@device_ready:
    sta georam_stream_device
    lda #georam_filename_len
    ldx #<georam_filename
    ldy #>georam_filename
    jsr georam_stream_load
    bcc @installed
    jsr loader_load_raw_georam
    bcs @error
@installed:
    lda #2
    sta loader_sequence_phase
    clc
    rts
@error:
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

reu_filename:
    .byte "REU"
reu_filename_len = * - reu_filename

; georam_install_pages - Install staged PRG payload bytes through geoRAM.
; Inputs: validated stage buffer/page count. Outputs: C=error.
; Side effects: writes $DFFE/$DFFF and all 256 bytes of each selected page;
; updates installed-page count and XOR checksum. Clobbers: A, X, Y.
; Zero page: uses generated zp_tmptr.
.export georam_install_pages
georam_install_pages:
    lda georam_file_loaded
    beq @not_loaded
    lda #<(georam_stage_buffer + 2)
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
    ldy #$00
@copy:
    lda (zp_ptr1),y
    sta $1000,y
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
    cmp #$A9
    bne @invalid
    clc
    rts
@invalid:
    sec
    rts
