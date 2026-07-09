; src/geoasm/compiler_init.asm
; Compiler initialization, vector setup, and state machine entry.
;
; Provides the bootstrap sequence for the Compiler 2 system.

.include "common/zp.inc"
.include "common/constants.asm"

.import resident_main
.import arena_init_all
.import screen_init
.import __BSS_RUN__, __BSS_SIZE__

; Working pointers
zp_ptr1     = zp_tmptr
zp_ptr2     = zp_expr_ptr2

.segment "COMPILER_INIT"

; Configuration data
compiler_config:
    .byte $00        ; mode: 0 = standard
    .byte $01        ; ieee: enabled
    .byte $00        ; debug: disabled

; Interrupt vectors (stored in zero page for fast dispatch)
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
    jsr init_arenas
    bcs @error
    jsr init_editor
    bcs @error
    jmp init_enter_main_loop
@error:
    rts

; =============================================================================
; Vector Setup
; =============================================================================

; compiler_vectors - Install interrupt vectors
; Input:  X/Y = vector table pointer (low/high)
; Output: none
; Clobbers: A, X, Y
.export compiler_vectors
compiler_vectors:
    ; Store vector table pointer
    stx zp_ptr1
    sty zp_ptr1+1
    ; Copy vectors to zero page
    ldy #$00
    lda (zp_ptr1),y
    sta compiler_irq_vector
    iny
    lda (zp_ptr1),y
    sta compiler_irq_vector+1
    iny
    lda (zp_ptr1),y
    sta compiler_nmi_vector
    iny
    lda (zp_ptr1),y
    sta compiler_nmi_vector+1
    rts

; =============================================================================
; State Machine
; =============================================================================

; compiler_state_machine - State machine entry
; Input:  X/Y = initial state (low/high)
; Output: C = error
; Clobbers: A, X, Y
.export compiler_state_machine
compiler_state_machine:
    ; Store initial state
    stx zp_ptr1
    sty zp_ptr1+1
    ; Execute state machine
    ldy #$00
    lda (zp_ptr1),y
    ; For now, just return success
    clc
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
