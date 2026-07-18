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
.import irq_entry, irq_kernal_entry, nmi_entry
.import __BSS_RUN__, __BSS_SIZE__

; Bootstrap data must live in normal RAM (basicv3.prg). COMPILER is
; geoRAM-backed and unavailable during this cold path.
.segment "COMPILER_INIT"

; "BASIC V3 READY" banner (kept in COMPILER_INIT so it survives the
; editor screen clear and is the last thing drawn before the idle loop).
ready_message:     .byte "BASIC V3 READY"
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

; Bootstrap init must live in normal RAM (basicv3.prg). COMPILER is geoRAM-backed
; and is not mapped until after this cold path has already finished.
.segment "COMPILER_INIT"

; =============================================================================
; Configuration
; =============================================================================

; compiler_init - Initialize compiler configuration
; Input:  A = mode (0=standard, 1=extended)
; Output: C = error
; Clobbers: A, X, Y
.export compiler_init
compiler_init:
    ; Entered via JMP from loader_entry with IRQs masked and $01=$35.
    ; Keep SEI until vectors are installed, then CLI in init_enter_main_loop.
    sei
    pha
    jsr init_clear_bss
    pla
    sta compiler_config
    ldx #INIT_STATE_COLD
    ldy #0
    jsr compiler_state_machine
    ; Best-effort subsystem bring-up. Vectors + main loop must always run so
    ; a partial cold path cannot leave the machine hung under SEI.
    jsr init_arenas
    jsr init_editor
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
    jmp init_enter_main_loop

; =============================================================================
; Vector Setup
; =============================================================================

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

; init_arenas - Initialize arena directory
; Input:  none
; Output: none
; Clobbers: A, X, Y
.export init_arenas
init_arenas:
    jsr arena_init_all
    bcs @error
    lda #$01
    sta init_arena_state
    clc
@error:
    rts

; init_editor - Initialize editor state
; Input:  none
; Output: none
; Clobbers: A, X
.export init_editor
init_editor:
    jsr screen_init
    lda #$00
    sta init_editor_state+1
    sta init_editor_state+2
    sta init_editor_state+3
    lda #$05
    sta init_editor_state
    clc
    rts

; init_enter_main_loop - Enter main loop
; Input:  none
; Output: none
; Clobbers: A, X, Y
.export init_enter_main_loop
init_enter_main_loop:
    lda #1
    sta init_main_loop_entered
    cli
    jmp resident_main

; Keep a non-empty geoRAM-backed COMPILER segment for payload packing tools.
.segment "COMPILER"
.export compiler_cold_anchor
compiler_cold_anchor:
    rts
