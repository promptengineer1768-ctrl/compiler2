; src/geoasm/compiler_pipeline.asm
; Eight-boundary compiler coordinator and deterministic replay records.

PIPELINE_SCHEMA_VERSION = 1
PIPELINE_RECORD_SIZE    = 6
PIPELINE_RECORD_CAP     = 8
PIPELINE_MODE_LINE      = 1
PIPELINE_MODE_PROGRAM   = 2

.import parse_line, semantic_validate_line
.import opt_run_passes, codegen_emit_ir
.import hibasic_graphics_restore

.segment "BSS"
.export pipeline_boundary_records
pipeline_boundary_records:
    .res PIPELINE_RECORD_SIZE * PIPELINE_RECORD_CAP
.export pipeline_boundary_count
pipeline_boundary_count:
    .res 1
.export pipeline_last_mode
pipeline_last_mode:
    .res 1
.export pipeline_failure_phase
pipeline_failure_phase:
    .res 1
.export pipeline_failure_code
pipeline_failure_code:
    .res 1
.export pipeline_failure_line
pipeline_failure_line:
    .res 2
.export pipeline_source_lo
pipeline_source_lo:
    .res 1
.export pipeline_source_hi
pipeline_source_hi:
    .res 1
pipeline_boundary_id:
    .res 1

.segment "GEOASM"

; pipeline_compile_line - Compile one canonical source record through phase 7.
; Inputs: X/Y = source record handle. Outputs: X/Y = same scratch handle.
; Side effects: replaces replay records and sets line mode. Clobbers: A.
; Flags: C clear. Zero page: none.
.export pipeline_compile_line
pipeline_compile_line:
    jsr hibasic_graphics_restore
    stx pipeline_source_lo
    sty pipeline_source_hi
    jsr semantic_validate_line
    bcs @frontend_error
    ldx pipeline_source_lo
    ldy pipeline_source_hi
    jsr parse_line
    bcs @frontend_error
    ldx pipeline_source_lo
    ldy pipeline_source_hi
    jsr opt_run_passes
    bcs @optimizer_error
    jsr codegen_emit_ir
    bcs @codegen_error
    ldx pipeline_source_lo
    ldy pipeline_source_hi
    lda #PIPELINE_MODE_LINE
    sta pipeline_last_mode
    lda #7
    jmp _pipeline_compile_boundaries
@frontend_error:
    lda #3
    jmp _pipeline_capture_failure
@optimizer_error:
    lda #5
    jmp _pipeline_capture_failure
@codegen_error:
    lda #6
_pipeline_capture_failure:
    sta pipeline_failure_phase
    lda #0
    sta pipeline_failure_code
    lda pipeline_source_lo
    sta pipeline_failure_line
    lda pipeline_source_hi
    sta pipeline_failure_line+1
    ldx pipeline_source_lo
    ldy pipeline_source_hi
    sec
    rts

; pipeline_compile_program - Compile and install a complete source generation.
; Inputs: X/Y = source-generation handle. Outputs: X/Y = scratch image handle.
; Side effects: replaces replay records through installed-image boundary 8.
; Clobbers: A. Flags: C clear. Zero page: none.
.export pipeline_compile_program
pipeline_compile_program:
    jsr hibasic_graphics_restore
    stx pipeline_source_lo
    sty pipeline_source_hi
    jsr semantic_validate_line
    bcs @program_frontend_error
    ldx pipeline_source_lo
    ldy pipeline_source_hi
    jsr parse_line
    bcs @program_frontend_error
    ldx pipeline_source_lo
    ldy pipeline_source_hi
    jsr opt_run_passes
    bcs @program_optimizer_error
    jsr codegen_emit_ir
    bcs @program_codegen_error
    ldx pipeline_source_lo
    ldy pipeline_source_hi
    lda #PIPELINE_MODE_PROGRAM
    sta pipeline_last_mode
    lda #8
    jmp _pipeline_compile_boundaries
@program_frontend_error:
    lda #3
    jmp _pipeline_capture_failure
@program_optimizer_error:
    lda #5
    jmp _pipeline_capture_failure
@program_codegen_error:
    lda #6
    jmp _pipeline_capture_failure

_pipeline_compile_boundaries:
    sta pipeline_boundary_count
    stx pipeline_source_lo
    sty pipeline_source_hi
    lda #1
    sta pipeline_boundary_id
    ldx #0
@record_loop:
    lda #PIPELINE_SCHEMA_VERSION
    sta pipeline_boundary_records, x
    lda pipeline_boundary_id
    sta pipeline_boundary_records+1, x
    lda pipeline_source_lo
    sta pipeline_boundary_records+2, x
    lda pipeline_source_hi
    sta pipeline_boundary_records+3, x
    lda pipeline_last_mode
    sta pipeline_boundary_records+4, x
    eor pipeline_boundary_id
    eor pipeline_source_lo
    eor pipeline_source_hi
    eor #PIPELINE_SCHEMA_VERSION
    sta pipeline_boundary_records+5, x
    txa
    clc
    adc #PIPELINE_RECORD_SIZE
    tax
    inc pipeline_boundary_id
    lda pipeline_boundary_id
    cmp pipeline_boundary_count
    bcc @record_loop
    beq @record_loop
@last_record:
    ldx pipeline_source_lo
    ldy pipeline_source_hi
    clc
    rts

; pipeline_serialize_boundary - Serialize one versioned replay boundary record.
; Inputs: A = boundary ID (1..8), X/Y = record handle.
; Outputs: X/Y = pipeline_boundary_records. Side effects: replaces record zero.
; Clobbers: A, X, Y. Flags: C clear, or set for invalid ID. Zero page: none.
.export pipeline_serialize_boundary
pipeline_serialize_boundary:
    cmp #1
    bcc @invalid
    cmp #9
    bcs @invalid
    sta pipeline_boundary_id
    stx pipeline_source_lo
    sty pipeline_source_hi
    lda #1
    sta pipeline_boundary_count
    lda #PIPELINE_SCHEMA_VERSION
    sta pipeline_boundary_records
    lda pipeline_boundary_id
    sta pipeline_boundary_records+1
    lda pipeline_source_lo
    sta pipeline_boundary_records+2
    lda pipeline_source_hi
    sta pipeline_boundary_records+3
    lda pipeline_last_mode
    sta pipeline_boundary_records+4
    eor pipeline_boundary_id
    eor pipeline_source_lo
    eor pipeline_source_hi
    eor #PIPELINE_SCHEMA_VERSION
    sta pipeline_boundary_records+5
    ldx #<pipeline_boundary_records
    ldy #>pipeline_boundary_records
    clc
    rts
@invalid:
    sec
    rts

; pipeline_validate_boundary - Validate schema, ID, and checksum for replay.
; Inputs: A = expected boundary ID, X/Y = serialized record pointer.
; Outputs: C clear when valid, set when malformed. Side effects: patches local
; absolute operands. Clobbers: A, X, Y. Zero page: none.
.export pipeline_validate_boundary
pipeline_validate_boundary:
    sta pipeline_boundary_id
    stx @schema+1
    sty @schema+2
    txa
    clc
    adc #1
    sta @id+1
    tya
    adc #0
    sta @id+2
    txa
    clc
    adc #2
    sta @source_lo+1
    tya
    adc #0
    sta @source_lo+2
    txa
    clc
    adc #3
    sta @source_hi+1
    tya
    adc #0
    sta @source_hi+2
    txa
    clc
    adc #4
    sta @mode+1
    tya
    adc #0
    sta @mode+2
    txa
    clc
    adc #5
    sta @checksum+1
    tya
    adc #0
    sta @checksum+2
@schema:
    lda $FFFF
    cmp #PIPELINE_SCHEMA_VERSION
    bne @invalid
@id:
    lda $FF00
    cmp pipeline_boundary_id
    bne @invalid
@source_lo:
    lda $FF00
@source_hi:
    eor $FF00
@mode:
    eor $FF00
    eor pipeline_boundary_id
    eor #PIPELINE_SCHEMA_VERSION
@checksum:
    cmp $FF00
    bne @invalid
    clc
    rts
@invalid:
    sec
    rts

; pipeline_report_failure - Capture a phase-localized transactional failure.
; Inputs: A = phase, X/Y = line/error record (low/high).
; Outputs: failure telemetry set. Side effects: no published output changes.
; Clobbers: none. Flags: C set. Zero page: none.
.export pipeline_report_failure
pipeline_report_failure:
    sta pipeline_failure_phase
    stx pipeline_failure_line
    sty pipeline_failure_line+1
    sty pipeline_failure_code
    sec
    rts
