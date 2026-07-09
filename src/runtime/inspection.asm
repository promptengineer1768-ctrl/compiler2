; src/runtime/inspection.asm
; Source-free shell for standalone COMPILE exports.
; The generated command table accepts one-term ?/PRINT, CONT, loader-only LIST,
; RUN, LOAD, SAVE, VERIFY, CLR, and every $, /, @, ! wedge form.
; It rejects assignment, compound expressions, numbered-line entry, editing,
; and arbitrary BASIC statements.

.include "common/zp.inc"
.include "common/constants.asm"

.import ctrl_cont, ctrl_reset
.import ctx_init
.import data_reset
.import fp_clear_flags
.import io_print_value
.import kernal_chrout, kernal_getin, kernal_print_packed
.import rio_load, rio_save, rio_verify
.import arr_reset, str_reset
.import var_load_float, var_load_int, var_load_string
.import wedge_directory, wedge_load_absolute
.import wedge_status_or_command, wedge_stream_seq

TYPE_FLOAT = $00
TYPE_INT2 = $02
TYPE_STRING = $04

; Input buffer
INPUT_BUFFER = $0200

.segment "BSS"
; Standalone linker writes the native program restart address here.  Keeping
; this explicit avoids coupling RUN to either the development loader or a
; fixed generated-code address.
.export inspect_program_entry
inspect_program_entry: .res 2
; Standalone linker publishes a compact symbol table here. Each six-byte row is
; name-1, name-2 (zero when absent), suffix ('$' or zero), VD low, VD high,
; reserved. Names are uppercase PETSCII and the row count is explicit.
.export inspect_symbol_table, inspect_symbol_count
inspect_symbol_table: .res 2
inspect_symbol_count: .res 1
inspect_operand_name: .res 3

.segment "RUNTIME"

; =============================================================================
; Inspection Shell Main Loop
; =============================================================================

; inspect_shell - Main REPL loop (never returns normally)
; Input:  none
; Output: none (loops forever)
; Clobbers: A, X, Y
; Side:   Reads input, dispatches restricted grammar
.export inspect_shell
inspect_shell:
    ; Print READY prompt
    jsr @print_ready
    
@loop:
    ; Read input line
    jsr @read_line
    
    ; Parse command
    ldx #<INPUT_BUFFER
    ldy #>INPUT_BUFFER
    jsr inspect_parse_command
    bcs @invalid
    
    ; Dispatch valid command
    ldx #<INPUT_BUFFER
    ldy #>INPUT_BUFFER
    jsr @dispatch
    bcs @invalid
    
    ; Continue loop
    jmp @loop
    
@invalid:
    ; Print ?SYNTAX ERROR
    jsr @print_error
    jmp @loop
    
@print_ready:
    ldx #<READY_MSG
    ldy #>READY_MSG
    jmp kernal_print_packed
    
@print_error:
    ; Print "?SYNTAX ERROR"
    ldx #<SYNTAX_ERR
    ldy #>SYNTAX_ERR
    jmp kernal_print_packed
    
@read_line:
    ; Read a line of input
    ldx #0
@read_loop:
    jsr kernal_getin
    beq @read_loop     ; Wait for input
    cmp #$0D           ; Return key?
    beq @line_done
    sta INPUT_BUFFER,x
    inx
    jmp @read_loop
@line_done:
    lda #$00
    sta INPUT_BUFFER,x ; Null terminate
    rts

@dispatch:
    stx zp_tmptr
    sty zp_tmptr+1
    jsr @dispatch_skip_spaces
    ldy #0
    lda (zp_tmptr),y
    cmp #'?'
    beq @dispatch_print
    cmp #'P'
    beq @dispatch_print
    cmp #'C'
    beq @dispatch_c
    cmp #'L'
    beq @dispatch_l
    cmp #'R'
    beq @dispatch_run
    cmp #'S'
    beq @dispatch_save
    cmp #'V'
    beq @dispatch_verify
    cmp #'$'
    beq @dispatch_wedge
    cmp #'/'
    beq @dispatch_wedge
    cmp #'@'
    beq @dispatch_wedge
    cmp #'!'
    beq @dispatch_wedge
    sec
    rts
@dispatch_c:
    iny
    lda (zp_tmptr),y
    cmp #'O'
    beq @dispatch_cont
    ldx zp_tmptr
    ldy zp_tmptr+1
    jmp inspect_clr
@dispatch_l:
    iny
    lda (zp_tmptr),y
    cmp #'I'
    beq @dispatch_list
    ldx zp_tmptr
    ldy zp_tmptr+1
    jmp inspect_load
@dispatch_cont:
    ldx zp_cont_handle
    ldy zp_cont_handle+1
    jmp inspect_cont
@dispatch_list:
    jmp inspect_list_loader
@dispatch_run:
    jmp inspect_run
@dispatch_save:
    ldx zp_tmptr
    ldy zp_tmptr+1
    jmp inspect_save
@dispatch_verify:
    ldx zp_tmptr
    ldy zp_tmptr+1
    jmp inspect_verify
@dispatch_wedge:
    ldx zp_tmptr
    ldy zp_tmptr+1
    jmp inspect_wedge
@dispatch_print:
    ldx zp_tmptr
    ldy zp_tmptr+1
    jsr inspect_resolve_operand
    bcs @dispatch_print_done
    lda inspect_operand_name+2
    cmp #'$'
    beq @dispatch_print_string
    jmp inspect_print_var
@dispatch_print_string:
    jmp inspect_print_string_var
@dispatch_print_done:
    rts
@dispatch_skip_spaces:
    ldy #0
@dispatch_space_loop:
    lda (zp_tmptr),y
    cmp #' '
    bne @dispatch_space_done
    inc zp_tmptr
    bne @dispatch_space_loop
    inc zp_tmptr+1
    bne @dispatch_space_loop
@dispatch_space_done:
    rts

; =============================================================================
; Command Parsing
; =============================================================================

; inspect_parse_command - Grammar validation
; Input:  X/Y = input buffer pointer
; Output: C = 1 if invalid, C = 0 if valid
; Clobbers: A, X, Y
.export inspect_parse_command
inspect_parse_command:
    ; Save buffer pointer
    stx zp_tmptr
    sty zp_tmptr+1

    jsr @skip_spaces
    jsr @reject_assignment
    bcc :+
    jmp @invalid
:

    ldy #0
    lda (zp_tmptr),y
    bne :+
    jmp @invalid
:
    cmp #'?'
    beq @valid_one_char
    cmp #'P'
    beq @match_print
    cmp #'C'
    beq @match_c
    cmp #'L'
    bne :+
    jmp @match_l
:
    cmp #'R'
    bne :+
    jmp @match_run
:
    cmp #'S'
    bne :+
    jmp @match_save
:
    cmp #'V'
    bne :+
    jmp @match_verify
:
    cmp #'$'
    beq @valid_one_char
    cmp #'/'
    beq @valid_one_char
    cmp #'@'
    beq @valid_one_char
    cmp #'!'
    beq @valid_one_char
    cmp #'0'
    bcs :+
    jmp @invalid
:
    cmp #('9'+1)
    bcs :+
    jmp @invalid
:
    jmp @invalid

@valid_one_char:
    clc
    rts

@match_print:
    ldy #1
    lda (zp_tmptr),y
    cmp #'R'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'I'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'N'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'T'
    beq :+
    jmp @invalid
:
    clc
    rts

@match_c:
    ldy #1
    lda (zp_tmptr),y
    cmp #'O'
    beq @match_cont_tail
    cmp #'L'
    beq @match_clr_tail
    jmp @invalid

@match_cont_tail:
    iny
    lda (zp_tmptr),y
    cmp #'N'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'T'
    beq :+
    jmp @invalid
:
    clc
    rts

@match_clr_tail:
    iny
    lda (zp_tmptr),y
    cmp #'R'
    beq :+
    jmp @invalid
:
    clc
    rts

@match_l:
    ldy #1
    lda (zp_tmptr),y
    cmp #'I'
    beq @match_list_tail
    cmp #'O'
    beq @match_load_tail
    jmp @invalid

@match_list_tail:
    iny
    lda (zp_tmptr),y
    cmp #'S'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'T'
    beq :+
    jmp @invalid
:
    clc
    rts

@match_load_tail:
    iny
    lda (zp_tmptr),y
    cmp #'A'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'D'
    beq :+
    jmp @invalid
:
    clc
    rts

@match_run:
    ldy #1
    lda (zp_tmptr),y
    cmp #'U'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'N'
    beq :+
    jmp @invalid
:
    clc
    rts

@match_save:
    ldy #1
    lda (zp_tmptr),y
    cmp #'A'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'V'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'E'
    beq :+
    jmp @invalid
:
    clc
    rts

@match_verify:
    ldy #1
    lda (zp_tmptr),y
    cmp #'E'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'R'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'I'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'F'
    beq :+
    jmp @invalid
:
    iny
    lda (zp_tmptr),y
    cmp #'Y'
    beq :+
    jmp @invalid
:
    clc
    rts

@skip_spaces:
    ldy #0
@skip_loop:
    lda (zp_tmptr),y
    cmp #' '
    bne @skip_done
    inc zp_tmptr
    bne @skip_loop
    inc zp_tmptr+1
    bne @skip_loop
@skip_done:
    rts

@reject_assignment:
    ldy #0
@assign_loop:
    lda (zp_tmptr),y
    beq @assign_clear
    cmp #'='
    beq @assign_found
    iny
    bne @assign_loop
@assign_clear:
    clc
    rts
@assign_found:
    sec
    rts

@invalid:
    sec
    rts

; =============================================================================
; Variable Printing
; =============================================================================

; inspect_resolve_operand - Resolve the one-term ?/PRINT grammar.
; Input: X/Y -> NUL-terminated command text.
; Output: X/Y -> linked VD, C clear; C set/A=ERR_SYNTAX if malformed or absent.
; Side effects: operand scratch only. Clobbers: A, X, Y.
; Zero page: zp_src.
.export inspect_resolve_operand
inspect_resolve_operand:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src),y
    cmp #'?'
    beq @after_keyword
    ; Parser has already admitted PRINT, so skip its five letters.
    ldy #5
@after_keyword:
    iny
@spaces:
    lda (zp_src),y
    cmp #' '
    bne @name
    iny
    bne @spaces
@name:
    cmp #'A'
    bcc @bad
    cmp #('Z'+1)
    bcs @bad
    sta inspect_operand_name
    iny
    lda (zp_src),y
    cmp #'A'
    bcc @suffix
    cmp #('Z'+1)
    bcs @suffix
    sta inspect_operand_name+1
    iny
    lda (zp_src),y
    jmp @have_tail
@suffix:
    ldx #0
    stx inspect_operand_name+1
@have_tail:
    ldx #0
    stx inspect_operand_name+2
    cmp #'$'
    bne @end
    sta inspect_operand_name+2
    iny
    lda (zp_src),y
@end:
    cmp #0
    bne @bad
    lda inspect_symbol_count
    beq @bad
    lda inspect_symbol_table
    sta zp_tmptr
    lda inspect_symbol_table+1
    sta zp_tmptr+1
    ldx inspect_symbol_count
@row:
    ldy #0
    lda (zp_tmptr),y
    cmp inspect_operand_name
    bne @next
    iny
    lda (zp_tmptr),y
    cmp inspect_operand_name+1
    bne @next
    iny
    lda (zp_tmptr),y
    cmp inspect_operand_name+2
    bne @next
    iny
    lda (zp_tmptr),y
    pha
    iny
    lda (zp_tmptr),y
    tay
    pla
    tax
    clc
    rts
@next:
    lda zp_tmptr
    clc
    adc #6
    sta zp_tmptr
    bcc :+
    inc zp_tmptr+1
:
    dex
    bne @row
@bad:
    lda #ERR_SYNTAX
    sec
    rts

; inspect_print_var - ?A / PRINT A resolved-variable handler
; Input:  X/Y = validated numeric VD descriptor
; Output: C = error
; Clobbers: A, X, Y
; Side:   Resolves the descriptor and prints its current value
.export inspect_print_var
inspect_print_var:
    ; VD +2 is the public variable kind (1=integer, 2=float, 3=string).
    stx zp_tmptr
    sty zp_tmptr+1
    ldy #2
    lda (zp_tmptr),y
    cmp #1
    beq @integer
    cmp #2
    beq @float
    sec
    rts
@integer:
    ldx zp_tmptr
    ldy zp_tmptr+1
    jsr var_load_int
    bcs @done
    stx zp_fac1
    sty zp_fac1+1
    lda #TYPE_INT2
    jmp io_print_value
@float:
    ldx zp_tmptr
    ldy zp_tmptr+1
    jsr var_load_float
    bcs @done
    lda #TYPE_FLOAT
    jmp io_print_value
@done:
    rts

; inspect_print_string_var - ?A$(N) / PRINT A$(N) resolved-variable handler
; Input:  X/Y = validated string VD descriptor
; Output: C = error
; Clobbers: A, X, Y
; Side:   Resolves the descriptor and prints its current SD contents
.export inspect_print_string_var
inspect_print_string_var:
    jsr var_load_string
    bcs @done
    lda #TYPE_STRING
    jmp io_print_value
@done:
    rts

; =============================================================================
; CONT Statement
; =============================================================================

; inspect_cont - CONT in inspection shell
; Input:  valid continuation handle/generation
; Output: none
; Clobbers: A, X, Y
; Side:   Restores compiled continuation descriptor and runtime state
.export inspect_cont
inspect_cont:
    jmp ctrl_cont

; =============================================================================
; LIST Command
; =============================================================================

; inspect_list_loader - Source-free LIST behavior
; Input:  optional whitespace only
; Output: prints "2026 SYS2061"
; Clobbers: A, X, Y
.export inspect_list_loader
inspect_list_loader:
    ; Print the only source-visible loader line retained by a standalone image.
    ldx #<SYS_MSG
    ldy #>SYS_MSG
    jmp kernal_print_packed

; =============================================================================
; RUN Command
; =============================================================================

; inspect_run - RUN
; Input:  optional whitespace only
; Output: does not return on success
; Clobbers: A, X, Y
; Side:   Reinitializes and enters current compiled image
.export inspect_run
inspect_run:
    lda inspect_program_entry
    ora inspect_program_entry+1
    beq @missing_entry
    jsr inspect_clr
    jmp (inspect_program_entry)
@missing_entry:
    sec
    rts

; =============================================================================
; File Operations
; =============================================================================

; inspect_load - LOAD
; Input:  X/Y = generated LOAD grammar
; Output: C = error
; Clobbers: A, X, Y
; Side:   Uses standalone KERNAL file path/current fa
.export inspect_load
inspect_load:
    jmp rio_load

; inspect_save - SAVE
; Input:  X/Y = generated SAVE grammar
; Output: C = error
; Clobbers: A, X, Y
; Side:   Uses standalone KERNAL file path/current fa
.export inspect_save
inspect_save:
    jmp rio_save

; inspect_verify - VERIFY
; Input:  X/Y = generated VERIFY grammar
; Output: C = error
; Clobbers: A, X, Y
; Side:   Uses standalone KERNAL file path/current fa
.export inspect_verify
inspect_verify:
    jmp rio_verify

; =============================================================================
; CLR Command
; =============================================================================

; inspect_clr - CLR
; Input:  optional whitespace only
; Output: none
; Clobbers: A, X, Y
; Side:   Clears variables, arrays, strings, frames, continuation
.export inspect_clr
inspect_clr:
    ; Runtime-owned descriptors become unreachable when generated program
    ; initialization runs again.  Clear every independently resumable state
    ; here so direct-mode CLR cannot retain stale execution state.
    jsr ctrl_reset
    jsr ctx_init
    jsr data_reset
    jsr arr_reset
    jsr str_reset
    lda #$ff
    jsr fp_clear_flags
    clc
    rts

; =============================================================================
; Wedge Commands
; =============================================================================

; inspect_wedge - $, /, @, ! wedge dispatcher
; Input:  X/Y = validated prefix command
; Output: C = error
; Clobbers: A, X, Y
; Side:   Calls standalone wedge service; shares fa
.export inspect_wedge
inspect_wedge:
    ; Get prefix character
    stx zp_tmptr
    sty zp_tmptr+1
    ldy #0
    lda (zp_tmptr),y
    
    ; Dispatch based on prefix
    cmp #'$'
    beq @wedge_dir
    cmp #'/'
    beq @wedge_load
    cmp #'@'
    beq @wedge_status
    cmp #'!'
    beq @wedge_stream
    
    ; Unknown wedge
    sec
    rts
    
@wedge_dir:
    ldx zp_tmptr
    ldy zp_tmptr+1
    jmp wedge_directory
    
@wedge_load:
    ldx zp_tmptr
    ldy zp_tmptr+1
    jmp wedge_load_absolute
    
@wedge_status:
    ldx zp_tmptr
    ldy zp_tmptr+1
    jmp wedge_status_or_command
    
@wedge_stream:
    ldx zp_tmptr
    ldy zp_tmptr+1
    jmp wedge_stream_seq

; =============================================================================
; Messages
; =============================================================================

READY_MSG:
    .byte "READY.", $8D

SYNTAX_ERR:
    .byte "?SYNTAX ERROR", $8D

SYS_MSG:
    .byte "2026 SYS2061", $8D
