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
.import irq_entry
.import nmi_entry
.import __BSS_RUN__, __BSS_SIZE__

; Working pointers
zp_ptr1     = zp_tmptr
zp_ptr2     = zp_expr_ptr2

; Stock KERNAL indirect IRQ/NMI vector slots.
CINV  = $0314
NMINV = $0318

; Bootstrap phase codes for compiler_state_machine (X register).
; Y must be zero; the high byte is reserved for future multi-byte state.
INIT_STATE_COLD     = $00  ; post-install cold path
INIT_STATE_REDETECT = $01  ; NMI/RESTORE re-entry (DESIGN2 §9.3 shared tail)
INIT_STATE_READY    = $02  ; arenas + editor + vectors complete

.segment "COMPILER_INIT"

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

.segment "COMPILER"

; =============================================================================
; Configuration
; =============================================================================

; compiler_init - Initialize compiler configuration
; Input:  A = mode (0=standard, 1=extended)
; Output: C = error
; Clobbers: A, X, Y
.export compiler_init
compiler_init:
    pha
    jsr init_clear_bss
    pla
    sta compiler_config
    ; Publish cold-start phase before any subsystem init.
    ldx #INIT_STATE_COLD
    ldy #0
    jsr compiler_state_machine
    bcs @error
    jsr init_arenas
    bcs @error
    jsr init_editor
    bcs @error
    jsr compiler_vectors
    bcs @error
    ; READY is accepted only when arenas and vectors actually published.
    ldx #INIT_STATE_READY
    ldy #0
    jsr compiler_state_machine
    bcs @error
    jmp init_enter_main_loop
@error:
    rts

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
    lda #<irq_entry
    sta CINV
    lda #>irq_entry
    sta CINV+1
    lda #<nmi_entry
    sta NMINV
    lda #>nmi_entry
    sta NMINV+1
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
