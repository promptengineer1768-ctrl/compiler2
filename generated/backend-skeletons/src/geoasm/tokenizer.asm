; Generated from a trusted skeleton profile. Do not rename entries.

; token_data: DATA handler: stores uninterpreted
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmptr
; Side effects: Collects DATA values as raw tokens until EOL
.export token_data
.proc token_data
    .error "skeleton requires implementation"
.endproc

; token_identifier: O(candidate length + declared transition bound), with no full-table fallback
; Inputs: active dialect table and scan state
; Outputs: A=keyword ID or `$00`; identifier in scratch
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmptr, write:zp_tmp1, write:zp_tmp2
; Side effects: Traverses generated first-character trie; accepts only enabled dialect nodes
.export token_identifier
.proc token_identifier
    .error "skeleton requires implementation"
.endproc

; token_init: Initialize tokenizer for line
; Inputs: X/Y=source ptr
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmptr
; Side effects: Sets up tokenizer state for a new line
.export token_init
.proc token_init
    .error "skeleton requires implementation"
.endproc

; token_next: Primary tokenizer entry: scan and return next token
; Inputs: none
; Outputs: A=token, C=1 if end-of-line
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmptr, write:zp_tmp1
; Side effects: Advances to next token; updates scan pointer
.export token_next
.proc token_next
    .error "skeleton requires implementation"
.endproc

; token_number: Numeric literal tokenization
; Inputs: none
; Outputs: value in FAC1 or integer register
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmptr, write:zp_fac1
; Side effects: Scans numeric literal, converts to internal form
.export token_number
.proc token_number
    .error "skeleton requires implementation"
.endproc

; token_peek: Peek for parser
; Inputs: none
; Outputs: A=token, C=1 if end-of-line
; Clobbers: A X
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmptr
; Side effects: Looks ahead one token without advancing
.export token_peek
.proc token_peek
    .error "skeleton requires implementation"
.endproc

; token_rem: REM handler: pass through verbatim
; Inputs: none
; Outputs: none
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmptr
; Side effects: Skips rest of line (REM content)
.export token_rem
.proc token_rem
    .error "skeleton requires implementation"
.endproc

; token_skip_whitespace: Whitespace consumption
; Inputs: none
; Outputs: none
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmptr
; Side effects: Advances past spaces/tabs
.export token_skip_whitespace
.proc token_skip_whitespace
    .error "skeleton requires implementation"
.endproc

; token_string: String literal tokenization
; Inputs: none
; Outputs: string data in buffer, length
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: write:zp_tmptr
; Side effects: Scans quoted string literal (respects quote mode)
.export token_string
.proc token_string
    .error "skeleton requires implementation"
.endproc
