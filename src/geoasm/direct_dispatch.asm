; src/geoasm/direct_dispatch.asm
; Immediate-mode front door and direct/program execution policy.
;
; Separates direct-only commands from single-line temporary execution.

.include "common/constants.asm"
.include "common/zp.inc"
.include "keyword_constants.inc"

.import codegen_get_code_ptr
.import georam_call_group_n_xy
.import GEORAM_ROUTINE_ID_PIPELINE_COMPILE_LINE
.import GEORAM_ROUTINE_ID_PIPELINE_COMPILE_PROGRAM
.import export_compile_command
.import ctrl_cont
.import rio_load, rio_save, rio_verify
.import inspect_clr
.import semantic_set_dialect, semantic_set_numeric_mode
.import quit_to_stock
.import program_lines_clear, program_lines_list, program_lines_run

; Keep dispatch policy tied to the generated manifest table. BASIC2/BASIC3.5
; share BASIC_TOKEN_BASIC and FPMODE uses its two-byte token prefix.
TOKEN_DIM         = BASIC_TOKEN_DIM
TOKEN_LET         = BASIC_TOKEN_LET
TOKEN_GOTO        = BASIC_TOKEN_GOTO
TOKEN_RUN         = BASIC_TOKEN_RUN
TOKEN_GOSUB       = BASIC_TOKEN_GOSUB
TOKEN_NEW         = BASIC_TOKEN_NEW
TOKEN_VERIFY      = BASIC_TOKEN_VERIFY
TOKEN_LOAD        = BASIC_TOKEN_LOAD
TOKEN_SAVE        = BASIC_TOKEN_SAVE
TOKEN_DEF         = BASIC_TOKEN_DEF
TOKEN_POKE        = BASIC_TOKEN_POKE
TOKEN_PRINT       = BASIC_TOKEN_PRINT
TOKEN_CONT        = BASIC_TOKEN_CONT
TOKEN_LIST        = BASIC_TOKEN_LIST
TOKEN_CLR         = BASIC_TOKEN_CLR
TOKEN_SYS         = BASIC_TOKEN_SYS
TOKEN_BASIC       = BASIC_TOKEN_BASIC
TOKEN_BASIC3_5    = BASIC_TOKEN_BASIC3_5
TOKEN_BASIC2      = BASIC_TOKEN_BASIC2
TOKEN_FPMODE      = BASIC_TOKEN_FPMODE
TOKEN_FPMODE_TAIL = 48
TOKEN_COMPILE     = BASIC_TOKEN_COMPILE
TOKEN_QUIT        = BASIC_TOKEN_QUIT

DIRECT_CLASS_COMMAND   = $00
DIRECT_CLASS_TEMPORARY = $01
DIRECT_CLASS_INVALID   = $FF

.segment "BSS"
.export direct_last_path
direct_last_path:
    .res 1
.export direct_last_token
direct_last_token:
    .res 1
.export direct_last_ptr
direct_last_ptr:
    .res 2
.export direct_temporary_generation
direct_temporary_generation:
    .res 1

.segment "GEOASM"

; direct_probe_prefix - Recognize a DOS wedge prefix without tokenizing it.
; Inputs: X/Y = captured text pointer (low/high).
; Outputs: A = wedge kind ($=0, @=1, /=2, !=3, normal=$FF).
; Side effects: writes zp_src. Clobbers: A, X, Y.
; Flags: C clear. Zero page: zp_src.
.export direct_probe_prefix
direct_probe_prefix:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #'$'
    beq @directory
    cmp #'@'
    beq @status
    cmp #'/'
    beq @load
    cmp #'!'
    beq @stream
    lda #$FF
    clc
    rts
@directory:
    lda #0
    clc
    rts
@status:
    lda #1
    clc
    rts
@load:
    lda #2
    clc
    rts
@stream:
    lda #3
    clc
    rts

; direct_classify - Classify the first token of a validated statement record.
; Inputs: X/Y = statement record pointer; byte zero is the command token.
; Outputs: A = command(0), temporary(1), or invalid($FF).
; Side effects: writes zp_src. Clobbers: A, X, Y.
; Flags: C clear for a legal direct form, set for program-only/unknown tokens.
; Zero page: zp_src.
.export direct_classify
direct_classify:
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    cmp #TOKEN_RUN
    beq @command
    cmp #TOKEN_LIST
    beq @command
    cmp #TOKEN_NEW
    beq @command
    cmp #TOKEN_LOAD
    beq @command
    cmp #TOKEN_SAVE
    beq @command
    cmp #TOKEN_VERIFY
    beq @command
    cmp #TOKEN_CONT
    beq @command
    cmp #TOKEN_CLR
    beq @command
    cmp #TOKEN_COMPILE
    beq @command
    cmp #TOKEN_QUIT
    beq @command
    cmp #TOKEN_BASIC
    beq @command
    cmp #TOKEN_FPMODE
    beq @command
    cmp #TOKEN_DIM
    beq @temporary
    cmp #TOKEN_LET
    beq @temporary
    cmp #TOKEN_GOTO
    beq @temporary
    cmp #TOKEN_GOSUB
    beq @temporary
    cmp #TOKEN_DEF
    beq @temporary
    cmp #TOKEN_PRINT
    beq @temporary
    cmp #TOKEN_SYS
    beq @temporary
    cmp #TOKEN_POKE
    beq @temporary
    lda #DIRECT_CLASS_INVALID
    sec
    rts
@command:
    lda #DIRECT_CLASS_COMMAND
    clc
    rts
@temporary:
    lda #DIRECT_CLASS_TEMPORARY
    clc
    rts

; direct_execute_command - Record and dispatch a validated direct-only command.
; Inputs: X/Y = direct-command record; byte zero is the command token. COMPILE
; is followed by its contiguous CP/ED/EL/EB/EW export plan.
; Outputs: direct_last_path/token set. COMPILE returns export_compile_command's
; C/A result; QUIT never returns (soft-reset leave path); other validated
; command tokens return the owning service result.
; Clobbers: A, X, Y. Zero page: zp_src.
.export direct_execute_command
direct_execute_command:
    lda #DIRECT_CLASS_COMMAND
    sta direct_last_path
    stx direct_last_ptr
    sty direct_last_ptr+1
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    sta direct_last_token
    ; Absolute JMPs keep branch distances short as handlers grow.
    cmp #TOKEN_QUIT
    bne @not_quit
    jmp quit_to_stock
@not_quit:
    cmp #TOKEN_COMPILE
    bne @not_compile
    jmp @compile
@not_compile:
    cmp #TOKEN_RUN
    bne @not_run
    jmp @run
@not_run:
    cmp #TOKEN_LOAD
    bne @not_load
    jmp @load
@not_load:
    cmp #TOKEN_SAVE
    bne @not_save
    jmp @save
@not_save:
    cmp #TOKEN_VERIFY
    bne @not_verify
    jmp @verify
@not_verify:
    cmp #TOKEN_CONT
    bne @not_cont
    jmp @cont
@not_cont:
    cmp #TOKEN_LIST
    bne @not_list
    jmp program_lines_list
@not_list:
    cmp #TOKEN_CLR
    bne @not_clr
    jmp inspect_clr
@not_clr:
    cmp #TOKEN_NEW
    bne @not_new
    jmp @new
@not_new:
    cmp #TOKEN_BASIC
    bne @not_basic
    jmp @basic
@not_basic:
    cmp #TOKEN_FPMODE
    bne @unsupported
    jmp @fpmode
    ; Other gateway query forms have no production service yet.
    ; Do not convert those missing dependencies to a success no-op.
@unsupported:
    lda #ERR_UNDEFINED_FUNCTION
    sec
    rts
@compile:
    ; The token is the direct dispatcher header, not part of the export plan.
    jsr direct_payload_ptr
    jsr export_compile_command
    rts
@run:
    ; Bare RUN (payload starts with 0 / empty) executes the PETSCII line table.
    ; Non-empty payloads keep the program-generation compile path.
    jsr direct_payload_ptr
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    beq @run_lines
    ldx zp_src
    ldy zp_src+1
    lda #<GEORAM_ROUTINE_ID_PIPELINE_COMPILE_PROGRAM
    jsr georam_call_group_n_xy
    bcs @done
    jsr codegen_get_code_ptr
    stx @run_code+1
    sty @run_code+2
@run_code:
    jsr $FFFF
    clc
    rts
@run_lines:
    jmp program_lines_run
@load:
    jsr direct_payload_ptr
    jmp rio_load
@save:
    jsr direct_payload_ptr
    jmp rio_save
@verify:
    jsr direct_payload_ptr
    jmp rio_verify
@cont:
    jsr direct_payload_ptr
    jsr ctrl_cont
    bcc @done
    lda #ERR_CANT_CONTINUE
    sec
    rts
@new:
    ; Clear the interim PETSCII program and runtime variables (CLR semantics).
    jsr program_lines_clear
    jmp inspect_clr
@basic:
    jsr direct_payload_ptr
    jsr direct_match_basic2
    bcc @basic2
    jsr direct_payload_ptr
    jsr direct_match_basic35
    bcc @basic35
    jmp @unsupported
@basic2:
    lda #0
    jmp semantic_set_dialect
@basic35:
    lda #1
    jmp semantic_set_dialect
@fpmode:
    jsr direct_payload_ptr
    jsr direct_match_fp0
    bcc @fpmode0
    jsr direct_payload_ptr
    jsr direct_match_fp1
    bcc @fpmode1
    jmp @unsupported
@fpmode0:
    lda #0
    jmp semantic_set_numeric_mode
@fpmode1:
    lda #1
    jmp semantic_set_numeric_mode
@syntax_error:
    lda #ERR_SYNTAX
    sec
    rts
@done:
    rts

; Keep the generated public directory entry page-bounded.  The private parser
; helpers and implementation follow the module's final directory entry so they
; do not become part of direct_execute_command's placed extent.
.export direct_execute_temporary
direct_execute_temporary:
    jmp direct_execute_temporary_impl

.proc direct_payload_ptr
    lda direct_last_ptr
    clc
    adc #1
    tax
    lda direct_last_ptr+1
    adc #0
    tay
    rts
.endproc

.proc direct_match_basic2
    stx zp_src
    sty zp_src+1
    lda #'2'
    sta zp_tmptr
    jmp direct_match_text
.endproc

.proc direct_match_basic35
    stx zp_src
    sty zp_src+1
    lda #'5'
    sta zp_tmptr
    jmp direct_match_text
.endproc

.proc direct_match_fp0
    stx zp_src
    sty zp_src+1
    lda #'0'
    sta zp_tmptr
    jmp direct_match_text
.endproc

.proc direct_match_fp1
    stx zp_src
    sty zp_src+1
    lda #'1'
    sta zp_tmptr
    jmp direct_match_text
.endproc

; Shared NUL-terminated matcher for BASIC/FPMODE direct commands.
direct_match_text:
    ldy #0
@loop:
    lda (zp_src),y
    beq @end
    iny
    bne @loop
@end:
    dey
    lda (zp_src),y
    cmp zp_tmptr
    bne @no
@done:
    clc
    rts
@no:
    sec
    rts

.segment "GEOASM"

; direct_execute_temporary - Enter the single-line temporary compiler path.
; Inputs: X/Y = direct record; byte zero is the statement token and the
; following bytes are its NUL-terminated canonical source.
; Outputs: direct_last_path=1 and direct_last_token set. Side effects: compiles
; and executes one disposable native generation, then advances its generation.
; Clobbers: A, X, Y. Flags: C clear on success, set on compile failure.
; Zero page: zp_src.
direct_execute_temporary_impl:
    lda #DIRECT_CLASS_TEMPORARY
    sta direct_last_path
    stx direct_last_ptr
    sty direct_last_ptr+1
    stx zp_src
    sty zp_src+1
    ldy #0
    lda (zp_src), y
    sta direct_last_token
    lda direct_last_ptr
    clc
    adc #1
    tax
    lda direct_last_ptr+1
    adc #0
    tay
    lda #<GEORAM_ROUTINE_ID_PIPELINE_COMPILE_LINE
    jsr georam_call_group_n_xy
    bcs @failed
    inc direct_temporary_generation
    jsr codegen_get_code_ptr
    stx @execute+1
    sty @execute+2
@execute:
    jsr $FFFF
    clc
    rts
@failed:
    sec
    rts
