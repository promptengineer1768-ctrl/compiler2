; src/geoasm/dos_wedge.asm
; Development-environment DOS wedge parser/orchestrator.
; Recognizes $ @ / ! before BASIC tokenization and dispatches to the
; normal-RAM wedge core in runtime/wedge.asm.

.include "common/constants.asm"
.include "common/zp.inc"

.import wedge_dispatch_development
.import georam_call_group_n
; The resident gate owns the generated directory tables.  Import only the
; generated ID needed by this XIP caller; including georam_pages.inc here
; would duplicate its 1,536-byte directory in normal CODE.
.import GEORAM_ROUTINE_ID_WEDGE_PARSE

zp_ptr1 = zp_tmptr

WEDGE_KIND_DIRECTORY = 0
WEDGE_KIND_STATUS    = 1
WEDGE_KIND_LOAD      = 2
WEDGE_KIND_STREAM    = 3
WEDGE_KIND_NORMAL    = $FF

.segment "GEORAM_PAGE_40"

; wedge_parse - Parse a development wedge prefix command.
; Inputs: X/Y = captured direct-mode text pointer (NUL-terminated).
; Outputs: A = kind ($=0, @=1, /=2, !=3) or $FF for normal BASIC input;
;          X preserved as the low pointer byte; C set on syntax error for a
;          recognized prefix (e.g. / or ! without a name).
; Side effects: none. Clobbers: A, Y. Zero page: zp_tmptr.
.export wedge_parse
wedge_parse:
    stx zp_ptr1
    sty zp_ptr1+1
    ldy #0
@skip_space:
    lda (zp_ptr1), y
    cmp #' '
    bne @have_first
    iny
    bne @skip_space
@have_first:
    cmp #'$'
    beq @directory
    cmp #'@'
    beq @status
    cmp #'/'
    beq @load
    cmp #'!'
    beq @stream
    lda #WEDGE_KIND_NORMAL
    clc
    rts

@directory:
    ; Bare $ only.
    iny
    lda (zp_ptr1), y
    bne @syntax
    lda #WEDGE_KIND_DIRECTORY
    clc
    rts

@status:
    ; @$ is the directory alias — report directory kind so development
    ; dispatch shares the same path as bare $.
    iny
    lda (zp_ptr1), y
    beq @status_kind
    cmp #'$'
    bne @status_kind
    iny
    lda (zp_ptr1), y
    bne @status_as_status
    lda #WEDGE_KIND_DIRECTORY
    clc
    rts
@status_as_status:
    ; Fall through: @$ with trailing junk is still an @-family form; the
    ; status handler will reject or interpret it.
@status_kind:
    lda #WEDGE_KIND_STATUS
    clc
    rts

@load:
    jsr wedge_require_name
    bcs @syntax
    lda #WEDGE_KIND_LOAD
    clc
    rts

@stream:
    jsr wedge_require_name
    bcs @syntax
    lda #WEDGE_KIND_STREAM
    clc
    rts

@syntax:
    lda #ERR_SYNTAX
    sec
    rts

; Require a non-empty filename after the first non-space prefix character.
; Uses zp_ptr1; does not depend on caller's Y.
.proc wedge_require_name
    ldy #0
@skip:
    lda (zp_ptr1), y
    cmp #' '
    bne @at_prefix
    iny
    bne @skip
@at_prefix:
    iny
    lda (zp_ptr1), y
    beq @fail
    cmp #'"'
    bne @unquoted
    iny
    lda (zp_ptr1), y
    beq @fail
    cmp #'"'
    beq @fail
    clc
    rts
@unquoted:
    cmp #','
    beq @fail
    clc
    rts
@fail:
    sec
    rts
.endproc

; Link-time XIP boundary proof: parser body and all page-local helpers fit the
; selected geoRAM page with a six-byte safety margin.
.assert * - wedge_parse <= $FA, error, "wedge_parse exceeds its geoRAM page"

.segment "WEDGE"

; wedge_run_development - Parse then dispatch one direct-mode wedge line.
; Inputs: X/Y = captured text. Outputs: C=error; A=$FF and C clear means the
; line is normal BASIC (not a wedge command).
; Side effects: may run KERNAL-backed wedge core handlers via the dispatcher.
; Clobbers: A, X, Y. Zero page: zp_tmptr and handler ZP.
.export wedge_run_development
wedge_run_development:
    sty zp_ptr1+1
    ; wedge_parse is the first production geoRAM XIP pilot.  Its generated
    ; placement is group 1 / index 113 (routine ID 369), so enter only via the
    ; resident directory gate; no normal-RAM mirror exists.
    ldx #<(GEORAM_ROUTINE_ID_WEDGE_PARSE - $100)
    jsr georam_call_group_n
    bcs @done
    cmp #WEDGE_KIND_NORMAL
    beq @done
    ldy zp_ptr1+1
    jmp wedge_dispatch_development
@done:
    rts
