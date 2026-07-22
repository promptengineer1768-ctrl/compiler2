; Generated from a trusted skeleton profile. Do not rename entries.

; fre_init: Initialize FRE profile and export free baseline
; Inputs: none
; Outputs: C clear
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:X Y, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Defaults fre_profile to expansion and fre_export_bytes to 38912
.export fre_init
.proc fre_init
    .error "skeleton requires implementation"
.endproc

; fre_query: FRE free-byte query
; Inputs: — (numeric FRE argument already discarded by caller)
; Outputs: FAC1=free bytes as float, C clear
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Reports expansion page free*256 or export free; never raw device capacity
.export fre_query
.proc fre_query
    .error "skeleton requires implementation"
.endproc

; fre_set_export_bytes: Publish export-mode free-byte count
; Inputs: A=lo, X=mid, Y=hi (24-bit little-endian free bytes)
; Outputs: C clear
; Clobbers: none
; Flags: return_kind:rts, stack_delta:0, preserves:A X Y, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Updates fre_export_bytes
.export fre_set_export_bytes
.proc fre_set_export_bytes
    .error "skeleton requires implementation"
.endproc

; fre_set_profile: Select FRE reporting profile
; Inputs: A=0 export / 1 expansion
; Outputs: C clear
; Clobbers: A
; Flags: return_kind:rts, stack_delta:0, preserves:X Y, irq_safe:false, irq_masked_ok:false
; Zero page: none
; Side effects: Updates fre_profile
.export fre_set_profile
.proc fre_set_profile
    .error "skeleton requires implementation"
.endproc
