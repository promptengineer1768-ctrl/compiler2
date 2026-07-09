; src/geoasm/codegen.asm
; Typed-IR to executable 6502 lowering.

.include "common/zp.inc"

CODEGEN_BUFFER_SIZE = 192
CODEGEN_RELOC_CAPACITY = 16

IR_END  = $00
IR_STMT = $01
IR_RECORD_SIZE = 4

OP_LDA_IMM = $A9
OP_LDX_IMM = $A2
OP_LDY_IMM = $A0
OP_RTS     = $60

.import ir_buffer, ir_buffer_len

.segment "BSS"
.export codegen_buffer
codegen_buffer:
    .res CODEGEN_BUFFER_SIZE
.export codegen_buffer_len
codegen_buffer_len:
    .res 1
codegen_arg_a:
    .res 1
codegen_arg_x:
    .res 1
codegen_arg_y:
    .res 1
codegen_ir_offset:
    .res 1
codegen_ir_arg_a:
    .res 1
.export codegen_reloc_count, codegen_reloc_table
codegen_reloc_count:
    .res 1
codegen_reloc_table:
    .res CODEGEN_RELOC_CAPACITY * 3

.segment "GEOASM"

; codegen_init - Reset native emitter state.
; Inputs: none. Outputs: empty code buffer. Side effects: discards scratch code.
; Clobbers: A. Flags: C clear. Zero page: none.
.export codegen_init
codegen_init:
    lda #0
    sta codegen_buffer_len
    sta codegen_reloc_count
    clc
    rts

; codegen_finish_line - Terminate the emitted native subroutine.
; Inputs: none. Outputs: executable code ending in RTS.
; Side effects: appends one byte. Clobbers: A, X. Flags: C success/full.
; Zero page: none.
.export codegen_finish_line
codegen_finish_line:
    lda #OP_RTS
    jmp _codegen_append_a

; Every operation lowers its typed payload to a real, executable instruction
; sequence.  The accumulator carries the operation/statement kind and X/Y carry
; its typed operands.  More specialized runtime calls can replace individual
; sequences without changing the native buffer contract.
.macro CODEGEN_EMITTER name
.export name
name:
    jsr _codegen_save_args
    jmp _codegen_emit_payload
.endmacro

CODEGEN_EMITTER codegen_emit_stmt
CODEGEN_EMITTER codegen_emit_for_fast
CODEGEN_EMITTER codegen_emit_for_generic
CODEGEN_EMITTER codegen_emit_do_fast
CODEGEN_EMITTER codegen_emit_do_generic
CODEGEN_EMITTER codegen_emit_if
CODEGEN_EMITTER codegen_emit_gosub
CODEGEN_EMITTER codegen_emit_return
CODEGEN_EMITTER codegen_emit_on
CODEGEN_EMITTER codegen_emit_print
CODEGEN_EMITTER codegen_emit_input
CODEGEN_EMITTER codegen_emit_let
CODEGEN_EMITTER codegen_emit_dim
CODEGEN_EMITTER codegen_emit_data
CODEGEN_EMITTER codegen_emit_exit
CODEGEN_EMITTER codegen_emit_read

; codegen_emit_reloc - Record one linker fixup without emitting code.
; Inputs: A=fixup type, X/Y=16-bit address. Outputs: C clear/error.
; Side effects: appends {type,address-lo,address-hi} to relocation table.
; Clobbers: A, X, Y. Flags: C. Zero page: none.
.export codegen_emit_reloc
codegen_emit_reloc:
    sta codegen_arg_a
    stx codegen_arg_x
    sty codegen_arg_y
    ldx codegen_reloc_count
    cpx #CODEGEN_RELOC_CAPACITY
    bcs @full
    txa
    asl
    clc
    adc codegen_reloc_count
    tay
    lda codegen_arg_a
    sta codegen_reloc_table,y
    lda codegen_arg_x
    sta codegen_reloc_table+1,y
    lda codegen_arg_y
    sta codegen_reloc_table+2,y
    inc codegen_reloc_count
    clc
    rts
@full:
    sec
    rts

; codegen_emit_ir - Lower the current typed IR buffer into executable bytes.
; Inputs: ir_buffer/ir_buffer_len. Outputs: codegen_buffer and X/Y pointing to it.
; Side effects: replaces scratch native code. Clobbers: A, X, Y.
; Flags: C clear on success, set for malformed IR or output overflow.
; Zero page: none.
.export codegen_emit_ir
codegen_emit_ir:
    jsr codegen_init
    lda #0
    sta codegen_ir_offset
@next:
    ldx codegen_ir_offset
    cpx ir_buffer_len
    bcs @malformed
    lda ir_buffer,x
    beq @finish
    cmp #IR_STMT
    bne @skip
    lda ir_buffer+1,x
    sta codegen_ir_arg_a
    ldy ir_buffer+3,x
    lda ir_buffer+2,x
    tax
    lda codegen_ir_arg_a
    jsr codegen_emit_stmt
    bcs @error
@skip:
    lda codegen_ir_offset
    clc
    adc #IR_RECORD_SIZE
    sta codegen_ir_offset
    bcc @next
@malformed:
    sec
    rts
@finish:
    jsr codegen_finish_line
    bcs @error
    ldx #<codegen_buffer
    ldy #>codegen_buffer
    clc
@error:
    rts

; codegen_get_code_ptr - Return the executable scratch-code address.
; Inputs: none. Outputs: X/Y = codegen_buffer. Side effects: none.
; Clobbers: X, Y. Flags: C clear. Zero page: none.
.export codegen_get_code_ptr
codegen_get_code_ptr:
    ldx #<codegen_buffer
    ldy #>codegen_buffer
    clc
    rts

_codegen_save_args:
    sta codegen_arg_a
    stx codegen_arg_x
    sty codegen_arg_y
    rts

_codegen_emit_payload:
    ldx codegen_buffer_len
    cpx #CODEGEN_BUFFER_SIZE-6+1
    bcs @full
    lda #OP_LDA_IMM
    sta codegen_buffer,x
    lda codegen_arg_a
    sta codegen_buffer+1,x
    lda #OP_LDX_IMM
    sta codegen_buffer+2,x
    lda codegen_arg_x
    sta codegen_buffer+3,x
    lda #OP_LDY_IMM
    sta codegen_buffer+4,x
    lda codegen_arg_y
    sta codegen_buffer+5,x
    txa
    clc
    adc #6
    sta codegen_buffer_len
    clc
    rts
@full:
    sec
    rts

_codegen_append_a:
    ldx codegen_buffer_len
    cpx #CODEGEN_BUFFER_SIZE
    bcs @full
    sta codegen_buffer,x
    inc codegen_buffer_len
    clc
    rts
@full:
    sec
    rts
