; Compiler 2 production BASIC bootstrap entry.
;
; The tokenized one-line BASIC program is:
;
;   2026 SYS2061
;
; It occupies $0801-$080C, so loader_entry follows at the documented $080D.

.segment "LOADER"

.export compiler2_entry
compiler2_entry:
    .word basic_end
    .word 2026
    .byte $9E
    .byte "2061"
    .byte 0
basic_end:
    .word 0
