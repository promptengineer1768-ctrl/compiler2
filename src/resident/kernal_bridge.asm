; src/resident/kernal_bridge.asm
; Bank-safe public KERNAL jump-table bridges.

.include "common/zp.inc"
.include "common/constants.asm"

KERNAL_IO_PORT = $36

KERNAL_SCNKEY  = $FF9F
KERNAL_READST  = $FFB7
KERNAL_SETLFS  = $FFBA
KERNAL_SETNAM  = $FFBD
KERNAL_OPEN    = $FFC0
KERNAL_CLOSE   = $FFC3
KERNAL_CHKIN   = $FFC6
KERNAL_CHKOUT  = $FFC9
KERNAL_CLRCHN  = $FFCC
KERNAL_CHRIN   = $FFCF
KERNAL_CHROUT  = $FFD2
KERNAL_LOAD    = $FFD5
KERNAL_SAVE    = $FFD8
KERNAL_SETTIM  = $FFDB
KERNAL_RDTIM   = $FFDE
KERNAL_STOP    = $FFE1
KERNAL_GETIN   = $FFE4
KERNAL_UDTIM   = $FFEA

.segment "BSS"
kernal_saved_a:       .res 1
kernal_saved_port:    .res 1
kernal_saved_dir:     .res 1
kernal_saved_p:       .res 1
kernal_return_a:      .res 1
kernal_return_x:      .res 1
kernal_return_y:      .res 1
kernal_return_p:      .res 1
kernal_packed_ptr:    .res 2
kernal_packed_index:  .res 1
kernal_packed_byte:   .res 1
.export kernal_output_byte
kernal_output_byte:   .res 1

.segment "RESIDENT"

.export kernal_readst
.export kernal_setlfs
.export kernal_setnam
.export kernal_open
.export kernal_close
.export kernal_chkin
.export kernal_chkout
.export kernal_clrchn
.export kernal_chrin
.export kernal_chrout
.export kernal_load
.export kernal_save
.export kernal_settim
.export kernal_rdtim
.export kernal_stop
.export kernal_getin
.export kernal_udtim
.export kernal_scnkey
.export kernal_print_packed

.macro bridge_call vector
    jsr kernal_begin
    jsr vector
    jmp kernal_end
.endmacro

; Enter a public KERNAL call. A is preserved for the KERNAL ABI; X/Y remain
; untouched.
;
; Always map KERNAL+I/O ($01=$36) and CLI for the call itself. Serial disk,
; GETIN, and timer/keyboard service need a live IRQ path while KERNAL is
; visible. The dangerous state is CLI with KERNAL banked out ($01=$35); that
; is prevented in kernal_end, not by refusing CLI here.
kernal_begin:
    sta kernal_saved_a
    php
    pla
    sta kernal_saved_p
    sei
    lda $00
    sta kernal_saved_dir
    lda $01
    sta kernal_saved_port
    lda #KERNAL_IO_PORT
    sta $01
    cld
    cli
    lda kernal_saved_a
    rts

; Return from a KERNAL call. Preserve KERNAL result A/X/Y and non-I flags.
; Always SEI before restoring the caller's CPU port, then restore the caller's
; interrupt-enable state together with the KERNAL result flags.
kernal_end:
    sta kernal_return_a
    stx kernal_return_x
    sty kernal_return_y
    php
    pla
    sta kernal_return_p
    sei
    lda kernal_saved_dir
    sta $00
    lda kernal_saved_port
    sta $01
    lda kernal_return_p
    and #$FB
    sta kernal_return_p
    lda kernal_saved_p
    and #$04
    beq @flags_ready
    lda kernal_return_p
    ora #$04
    sta kernal_return_p
@flags_ready:
    lda kernal_return_p
    pha
    lda kernal_return_a
    ldx kernal_return_x
    ldy kernal_return_y
    plp
    rts

; READST bridge. Output: A=status; KERNAL result flags.
kernal_readst:
    bridge_call KERNAL_READST

; SETLFS bridge. Inputs: A=logical file, X=device, Y=secondary.
kernal_setlfs:
    bridge_call KERNAL_SETLFS

; SETNAM bridge. Inputs: A=name length, X/Y=name pointer.
kernal_setnam:
    bridge_call KERNAL_SETNAM

; OPEN bridge. Inputs: prior SETLFS/SETNAM state. Output: C=KERNAL error.
kernal_open:
    bridge_call KERNAL_OPEN

; CLOSE bridge. Input: A=logical file. Output: C=KERNAL error.
kernal_close:
    bridge_call KERNAL_CLOSE

; CHKIN bridge. Input: X=logical file. Output: C=KERNAL error.
kernal_chkin:
    bridge_call KERNAL_CHKIN

; CHKOUT bridge. Input: X=logical file. Output: C=KERNAL error.
kernal_chkout:
    bridge_call KERNAL_CHKOUT

; CLRCHN bridge. Output: KERNAL result flags.
kernal_clrchn:
    bridge_call KERNAL_CLRCHN

; CHRIN bridge. Output: A=input byte; KERNAL result flags.
kernal_chrin:
    bridge_call KERNAL_CHRIN

; CHROUT bridge. Input: A=output byte. Output: C=KERNAL error.
kernal_chrout:
    sta kernal_output_byte
    bridge_call KERNAL_CHROUT

; Print a packed static string at X/Y. The final character carries bit 7;
; the bridge masks that marker before handing the byte to CHROUT.
;
; Hold KERNAL+I/O ($01=$36) for the whole string under SEI. Per-character
; begin/end would restore $01=$35 with IRQs enabled between chars and vector
; into open RAM at $FFFE (loader bootstrap runs with ROM banked out).
kernal_print_packed:
    stx kernal_packed_ptr
    sty kernal_packed_ptr+1
    lda #0
    sta kernal_packed_index
    php
    sei
    lda $01
    sta kernal_saved_port
    lda #KERNAL_IO_PORT
    sta $01
@next:
    lda kernal_packed_ptr
    sta zp_tmptr
    lda kernal_packed_ptr+1
    sta zp_tmptr+1
    ldy kernal_packed_index
    lda (zp_tmptr),y
    sta kernal_packed_byte
    and #$7F
    sta kernal_output_byte
    jsr KERNAL_CHROUT
    bcs @error
    lda kernal_packed_byte
    bmi @done
    inc kernal_packed_index
    bne @next
@error:
    lda kernal_saved_port
    sta $01
    plp
    sec
    rts
@done:
    lda kernal_saved_port
    sta $01
    plp
    clc
    rts

; LOAD bridge. Inputs: A=load/verify, X/Y=alternate address.
; Outputs: C=KERNAL error, X/Y=end address.
kernal_load:
    bridge_call KERNAL_LOAD

; SAVE bridge. Inputs: A=zero-page pointer to start address, X/Y=exclusive end.
; Output: C=KERNAL error.
kernal_save:
    bridge_call KERNAL_SAVE

; SETTIM bridge. Inputs: A=low, X=middle, Y=high jiffy byte.
kernal_settim:
    bridge_call KERNAL_SETTIM

; RDTIM bridge. Outputs: A=low, X=middle, Y=high jiffy byte.
kernal_rdtim:
    bridge_call KERNAL_RDTIM

; STOP bridge. Output: KERNAL Z flag reports STOP state.
kernal_stop:
    bridge_call KERNAL_STOP

; GETIN bridge. Output: A=queued byte or zero.
kernal_getin:
    bridge_call KERNAL_GETIN

; UDTIM bridge. Advances the KERNAL jiffy clock.
kernal_udtim:
    bridge_call KERNAL_UDTIM

; SCNKEY bridge. Scans the KERNAL keyboard matrix and queue.
kernal_scnkey:
    bridge_call KERNAL_SCNKEY
