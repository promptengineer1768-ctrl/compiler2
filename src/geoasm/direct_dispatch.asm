; src/geoasm/direct_dispatch.asm
; Immediate-mode front door and direct/program execution policy.
;
; SKELETON (design audit 2026-07-09): QUIT soft-reset, token-class SAVE/VERIFY,
; and most direct commands are not implemented (DESIGN2 §4, §5, §8.5).

.include "common/constants.asm"
.include "common/zp.inc"

.import pipeline_compile_line, codegen_get_code_ptr

TOKEN_DIM       = 134
TOKEN_LET       = 136
TOKEN_GOTO      = 137
TOKEN_RUN       = 138
TOKEN_GOSUB     = 141
TOKEN_NEW       = 147
TOKEN_VERIFY    = 148
TOKEN_LOAD      = 149
TOKEN_SAVE      = 150
TOKEN_POKE      = 151
TOKEN_PRINT     = 153
TOKEN_CONT      = 154
TOKEN_LIST      = 155
TOKEN_CLR       = 156
TOKEN_SYS       = 158
TOKEN_BASIC3_5  = 205
TOKEN_BASIC2    = 206
TOKEN_COMPILE   = 207
TOKEN_QUIT      = 211

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
    cmp #TOKEN_COMPILE
    beq @command
    cmp #TOKEN_QUIT
    beq @command
    cmp #TOKEN_BASIC3_5
    beq @command
    cmp #TOKEN_DIM
    beq @temporary
    cmp #TOKEN_LET
    beq @temporary
    cmp #TOKEN_GOTO
    beq @temporary
    cmp #TOKEN_GOSUB
    beq @temporary
    cmp #TOKEN_PRINT
    beq @temporary
    cmp #TOKEN_SYS
    beq @temporary
    cmp #TOKEN_POKE
    beq @temporary
    cmp #TOKEN_CLR
    beq @temporary
    cmp #TOKEN_BASIC2
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
; SKELETON: previously returned success for SAVE/LOAD/VERIFY/QUIT without
; performing design behavior. COMPILE path is demoted with export_compile_command.
; Inputs: X/Y = direct-command record; byte zero is the command token.
; Outputs: direct_last_path/token set; C set, A = ERR_UNDEFINED_FUNCTION.
; Clobbers: A, Y. Zero page: zp_src.
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
    lda #ERR_UNDEFINED_FUNCTION
    sec
    rts

; direct_execute_temporary - Enter the single-line temporary compiler path.
; Inputs: X/Y = direct record; byte zero is the statement token and the
; following bytes are its NUL-terminated canonical source.
; Outputs: direct_last_path=1 and direct_last_token set. Side effects: compiles
; and executes one disposable native generation, then advances its generation.
; Clobbers: A, X, Y. Flags: C clear on success, set on compile failure.
; Zero page: zp_src.
.export direct_execute_temporary
direct_execute_temporary:
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
    jsr pipeline_compile_line
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
