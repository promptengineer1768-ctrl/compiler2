; src/geoasm/compiler_init.asm
; Compiler initialization, vector setup, and state machine entry.
;
; Installs pinned IRQ/NMI vectors, saves priors for QUIT restore, and enters
; the resident main loop after BSS/arena/editor setup (DESIGN2 §8.5, §9.3).

.include "common/zp.inc"
.include "common/constants.asm"

.import resident_main
.import arena_init_all
.import screen_init
.import screen_sync_from_kernal
.import screen_cursor_on
.import kernal_print_packed
.import kernal_setnam, kernal_setlfs, kernal_load, kernal_readst
.import ram_under_io_copy_in
.import irq_entry, irq_kernal_entry, nmi_entry
.import __BSS_RUN__, __BSS_SIZE__, __IO_COLD_SIZE__
.import __EDITOR_PINNED_LOAD__, __EDITOR_PINNED_SIZE__
.import georam_call_group_0
.importzp GEORAM_ROUTINE_ID_COMPILER_INIT
.importzp GEORAM_ROUTINE_ID_INIT_ARENAS
.importzp GEORAM_ROUTINE_ID_INIT_EDITOR
.importzp GEORAM_ROUTINE_ID_INIT_ENTER_MAIN_LOOP

; Bootstrap data must live in normal RAM (basicv3.prg). COMPILER is
; geoRAM-backed and unavailable during this cold path.
.segment "COMPILER_INIT"

; "BASIC V3 READY" banner (kept in COMPILER_INIT so it survives the
; editor screen clear and is the last thing drawn before the idle loop).
; Leading HOME ($13) re-homes the stock KERNAL editor after screen_clear
; (which only resets project ZP, not PNTR/TBLX) so the banner and blink
; land at column 0 of the top row.
ready_message:     .byte $13, "BASIC V3 READY"
                   .byte $8D

; Working pointers
zp_ptr1     = zp_tmptr
zp_ptr2     = zp_expr_ptr2

; Stock KERNAL indirect IRQ/NMI vector slots.
CINV  = $0314
NMINV = $0318
KERNAL_IO_PORT = $36
HW_NMI_VECTOR = $FFFA
HW_RESET_VECTOR = $FFFC
HW_IRQ_VECTOR = $FFFE
KERNAL_RESET_ENTRY = $FCE2

; Bootstrap phase codes for compiler_state_machine (X register).
; Y must be zero; the high byte is reserved for future multi-byte state.
INIT_STATE_COLD     = $00  ; post-install cold path
INIT_STATE_REDETECT = $01  ; NMI/RESTORE re-entry (DESIGN2 §9.3 shared tail)
INIT_STATE_READY    = $02  ; arenas + editor + vectors complete

; Configuration data
compiler_config:
    .byte $00        ; mode: 0 = standard
    .byte $01        ; ieee: enabled
    .byte $00        ; debug: disabled

; Interrupt vectors (stored for diagnostics / tooling)
compiler_irq_vector:    .word 0
compiler_nmi_vector:    .word 0

.segment "BSS"
.export init_editor_state
init_editor_state:
    .res 4
.export init_main_loop_entered
init_main_loop_entered:
    .res 1
.export init_arena_state
init_arena_state:
    .res 1
; Prior KERNAL IRQ/NMI vectors saved by compiler_vectors for QUIT restore.
.export vectors_prior_irq
vectors_prior_irq:
    .res 2
.export vectors_prior_nmi
vectors_prior_nmi:
    .res 2
.export vectors_installed
vectors_installed:
    .res 1
; Latched bootstrap phase (INIT_STATE_*). Written only by compiler_state_machine.
.export init_phase
init_phase:
    .res 1

; The only normal-RAM compiler-init code is the loader hand-off.  It must clear
; BSS before entering the gate: a gate call records its nesting state in BSS,
; so an XIP clear performed after ctx_push would destroy its own return frame.
.segment "COMPILER_INIT"

; compiler_bootstrap - clear normal-RAM state, then enter compiler_init XIP.
; Input: A = mode (0 standard, 1 extended). Never returns on success.
; Clobbers: A, X, Y, zp_tmptr.  This is deliberately a tiny loader-facing
; helper; all policy/editor/arena initialization is in geoRAM pages.
.export compiler_bootstrap
compiler_bootstrap:
    sei
    pha
    jsr compiler_bootstrap_clear_bss
    pla
    ldx #<GEORAM_ROUTINE_ID_COMPILER_INIT
    jmp georam_call_group_0

; Keep this private pre-gate helper separate from init_clear_bss.  See the
; compiler_bootstrap contract above: clearing BSS while a gate context is live
; is not XIP-safe.
compiler_bootstrap_clear_bss:
    lda #<__BSS_RUN__
    sta zp_ptr1
    lda #>__BSS_RUN__
    sta zp_ptr1+1
    ldy #$00
    lda #$00
@loop:
    sta (zp_ptr1),y
    inc zp_ptr1
    bne @compare
    inc zp_ptr1+1
@compare:
    ldx zp_ptr1+1
    cpx #>(__BSS_RUN__ + __BSS_SIZE__)
    bne @loop
    ldx zp_ptr1
    cpx #<(__BSS_RUN__ + __BSS_SIZE__)
    bne @loop
    rts

; =============================================================================
; Configuration
; =============================================================================

; compiler_init - Initialize compiler configuration from XIP page 46.
; Input:  A = mode (0=standard, 1=extended)
; Output: C = error
; Clobbers: A, X, Y
.segment "GEORAM_PAGE_46"
.export compiler_init
compiler_init:
    ; Entered by compiler_bootstrap through the geoRAM gate with IRQs masked.
    ; Keep SEI until vectors are installed, then CLI in init_enter_main_loop.
    sei
    sta compiler_config
    ldx #INIT_STATE_COLD
    ldy #0
    jsr compiler_state_machine
    ; Best-effort subsystem bring-up. Vectors + main loop must always run so
    ; a partial cold path cannot leave the machine hung under SEI.
    jsr init_install_hibasic
    jsr init_install_iobasic
    ldx #<GEORAM_ROUTINE_ID_INIT_ARENAS
    jsr georam_call_group_0
    ldx #<GEORAM_ROUTINE_ID_INIT_EDITOR
    jsr georam_call_group_0
    jsr compiler_vectors
    ldx #INIT_STATE_READY
    ldy #0
    jsr compiler_state_machine
    ; Re-print the ready banner last: init_editor's screen clear would
    ; otherwise erase the READY the loader printed before vectors were set.
    ldx #<ready_message
    ldy #>ready_message
    jsr kernal_print_packed
    ; CHROUT advanced the stock KERNAL cursor; mirror it into project ZP so
    ; the IRQ reverse-video blink and key echo land on the ready line.
    jsr screen_sync_from_kernal
    jsr screen_cursor_on
    ldx #<GEORAM_ROUTINE_ID_INIT_ENTER_MAIN_LOOP
    jmp georam_call_group_0

.assert * - compiler_init <= $FA, error, "compiler_init exceeds geoRAM page 46"

; =============================================================================
; Vector Setup
; =============================================================================

.segment "COMPILER_INIT"

; compiler_vectors - Install interrupt vectors
; Saves prior CINV ($0314) and NMINV ($0318), then installs irq_entry and
; nmi_entry so KERNAL-dispatched IRQ/NMI reach the pinned resident handlers.
; Input:  X/Y = optional vector table pointer (unused; fixed project entries)
; Output: C clear on success
; Clobbers: A, X, Y
; Side effects: writes $0314-$0315 and $0318-$0319; records priors in BSS
.export compiler_vectors
compiler_vectors:
    ; Save prior IRQ vector.
    lda CINV
    sta vectors_prior_irq
    lda CINV+1
    sta vectors_prior_irq+1
    ; Save prior NMI vector.
    lda NMINV
    sta vectors_prior_nmi
    lda NMINV+1
    sta vectors_prior_nmi+1
    ; Install pinned resident handlers.
    lda #<irq_kernal_entry
    sta CINV
    lda #>irq_kernal_entry
    sta CINV+1
    lda #<nmi_entry
    sta NMINV
    lda #>nmi_entry
    sta NMINV+1
    ; The canonical runtime map banks KERNAL ROM out ($01=$35), so the CPU
    ; fetches interrupt vectors from RAM rather than entering the KERNAL ROM
    ; dispatcher. Populate the reserved hardware-vector tail before CLI.
    lda #<nmi_entry
    sta HW_NMI_VECTOR
    lda #>nmi_entry
    sta HW_NMI_VECTOR+1
    lda #<KERNAL_RESET_ENTRY
    sta HW_RESET_VECTOR
    lda #>KERNAL_RESET_ENTRY
    sta HW_RESET_VECTOR+1
    lda #<irq_entry
    sta HW_IRQ_VECTOR
    lda #>irq_entry
    sta HW_IRQ_VECTOR+1
    ; Mirror into the init-local copies for diagnostics.
    lda #<irq_entry
    sta compiler_irq_vector
    lda #>irq_entry
    sta compiler_irq_vector+1
    lda #<nmi_entry
    sta compiler_nmi_vector
    lda #>nmi_entry
    sta compiler_nmi_vector+1
    lda #1
    sta vectors_installed
    ; Re-enable CIA1 Timer A IRQ now that CINV points at the resident
    ; handler. Map KERNAL for the ICR write window, keep SEI until the
    ; bridge is used (hardware IRQ still needs HIRAM or a RAM vector).
    lda #KERNAL_IO_PORT
    sta $01
    lda #$7F
    sta $DC0D
    lda $DC0D
    lda #$81
    sta $DC0D
    lda #CPU_PORT_CANONICAL
    sta $01
    clc
    rts

; =============================================================================
; State Machine
; =============================================================================

; compiler_state_machine - Latch a known bootstrap phase honestly.
; Accepts only INIT_STATE_COLD / REDETECT / READY with Y=0. Does not invent
; success for unknown codes. READY also requires arenas constructed and IRQ/NMI
; vectors installed so a half-init path cannot claim readiness.
; Input:  X = phase (INIT_STATE_*), Y = 0
; Output: C clear and A=0 on accept; C set and A=ERR_ILLEGAL_QUANTITY on reject
; Clobbers: A, X, Y
; Side effects: writes init_phase on accept
.export compiler_state_machine
compiler_state_machine:
    cpy #0
    bne @reject
    cpx #INIT_STATE_COLD
    beq @accept
    cpx #INIT_STATE_REDETECT
    beq @accept
    cpx #INIT_STATE_READY
    bne @reject
    ; READY requires real subsystem publication, not a stub flag.
    lda init_arena_state
    beq @reject
    lda vectors_installed
    beq @reject
@accept:
    stx init_phase
    lda #0
    clc
    rts
@reject:
    lda #ERR_ILLEGAL_QUANTITY
    sec
    rts

; =============================================================================
; Initialization Helpers
; =============================================================================

; init_clear_bss - Clear BSS segment
; Input:  none
; Output: none
; Clobbers: A, X
.segment "GEORAM_PAGE_47"
.export init_clear_bss
init_clear_bss:
    lda #<__BSS_RUN__
    sta zp_ptr1
    lda #>__BSS_RUN__
    sta zp_ptr1+1
    ldy #$00
    lda #$00
@loop:
    sta (zp_ptr1),y
    inc zp_ptr1
    bne @compare
    inc zp_ptr1+1
@compare:
    ldx zp_ptr1+1
    cpx #>(__BSS_RUN__ + __BSS_SIZE__)
    bne @loop
    ldx zp_ptr1
    cpx #<(__BSS_RUN__ + __BSS_SIZE__)
    bne @loop
@done:
    rts

.assert * - init_clear_bss <= $FA, error, "init_clear_bss exceeds geoRAM page 47"

; init_arenas - Initialize arena directory
; Input:  none
; Output: none
; Clobbers: A, X, Y
.segment "GEORAM_PAGE_48"
.export init_arenas
init_arenas:
    jsr arena_init_all
    bcs @error
    lda #$01
    sta init_arena_state
    clc
@error:
    rts

.assert * - init_arenas <= $FA, error, "init_arenas exceeds geoRAM page 48"

; init_editor - Initialize editor state
; Input:  none
; Output: none
; Clobbers: A, X
.segment "GEORAM_PAGE_49"
.export init_editor
init_editor:
    ; EDITOR_PINNED is part of the separately-loaded HIBASIC image, not the
    ; normal-RAM BSS span cleared at cold start.  Its writable descriptors
    ; therefore arrive as whatever bytes were previously present at $E000.
    ; Clear the entire rw segment before any editor/store service observes it.
    ; HIBASIC code starts immediately after this linker-defined segment.
    jsr init_clear_editor_pinned
    jsr screen_init
    lda #$00
    sta init_editor_state+1
    sta init_editor_state+2
    sta init_editor_state+3
    lda #$05
    sta init_editor_state
    clc
    rts

; init_clear_editor_pinned - Clear all writable high-RAM editor metadata.
; Input: none. Output: none. Clobbers: A, X, Y, zp_tmptr.
; The linker bounds prevent this from clearing executable HIBASIC bytes.
init_clear_editor_pinned:
    lda #<__EDITOR_PINNED_LOAD__
    sta zp_ptr1
    lda #>__EDITOR_PINNED_LOAD__
    sta zp_ptr1+1
    ldy #$00
    lda #$00
@loop:
    sta (zp_ptr1),y
    inc zp_ptr1
    bne @compare
    inc zp_ptr1+1
@compare:
    ldx zp_ptr1+1
    cpx #>(__EDITOR_PINNED_LOAD__ + __EDITOR_PINNED_SIZE__)
    bne @loop
    ldx zp_ptr1
    cpx #<(__EDITOR_PINNED_LOAD__ + __EDITOR_PINNED_SIZE__)
    bne @loop
    rts

.assert * - init_editor <= $FA, error, "init_editor exceeds geoRAM page 49"

; init_install_hibasic - LOAD "HIBASIC",8,1 into $E000 when not already present.
; The program_lines / LET helpers live in hibasic.bin (RAM_HIGH). Skip if the
; EDITOR_PINNED region already looks installed (count cell zeroed and code).
; Clobbers: A, X, Y. Best-effort: carry ignored by caller.
.segment "COMPILER_INIT"
.export init_install_hibasic
init_install_hibasic:
    ; LOAD "HIBASIC",device,1 — PRG header carries $E000. Requires disk still
    ; present after geoRAM install (dual D64 ships HIBASIC alongside BASICV3).
    lda #7
    ldx #<hibasic_name
    ldy #>hibasic_name
    jsr kernal_setnam
    lda #1
    ldx $BA
    bne @dev
    ldx #8
@dev:
    ldy #1
    jsr kernal_setlfs
    lda #0
    jsr kernal_load
    rts

hibasic_name:
    .byte "HIBASIC"

; The high image has just been installed, so this second cold loader can live
; there rather than consuming the bootstrap's low-RAM budget.
.segment "HIBASIC"

; init_install_iobasic - Load the explicitly bounded cold overlay into a safe
; low-RAM staging page, then copy it behind the I/O devices through the pinned
; RAM-under-I/O gate.  No active editor/compiler code is placed there.
.export init_install_iobasic
init_install_iobasic:
    lda #7
    ldx #<iobasic_name
    ldy #>iobasic_name
    jsr kernal_setnam
    lda #1
    ldx $BA
    bne @dev
    ldx #8
@dev:
    ldy #1
    jsr kernal_setlfs
    lda #0
    jsr kernal_load
    bcs @error
    lda #<$0200
    sta zp_src
    lda #>$0200
    sta zp_src+1
    lda #<__IO_COLD_SIZE__
    ldx #$00
    ldy #$D0
    jsr ram_under_io_copy_in
@error:
    rts

iobasic_name:
    .byte "IOBASIC"

; init_enter_main_loop - Enter main loop
; Input:  none
; Output: none
; Clobbers: A, X, Y
.segment "GEORAM_PAGE_50"
.export init_enter_main_loop
init_enter_main_loop:
    lda #1
    sta init_main_loop_entered
    cli
    jmp resident_main

.assert * - init_enter_main_loop <= $FA, error, "init_enter_main_loop exceeds geoRAM page 50"

; Keep a non-empty geoRAM-backed COMPILER segment for payload packing tools.
.segment "COMPILER"
.export compiler_cold_anchor
compiler_cold_anchor:
    rts
