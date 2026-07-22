; Generated from a trusted skeleton profile. Do not rename entries.

; georam_stream_load: CGS1 disk-to-geoRAM stream reader
; Inputs: A=filename length, X/Y=filename pointer
; Outputs: C=error
; Clobbers: A X Y
; Flags: return_kind:rts, stack_delta:0, preserves:none, irq_safe:false, irq_masked_ok:false
; Zero page: read:zp_georam_stream, write:zp_georam_stream
; Side effects: Opens CGS1 sidecar and decompresses chunks directly to geoRAM
.export georam_stream_load
.proc georam_stream_load
    .error "skeleton requires implementation"
.endproc
