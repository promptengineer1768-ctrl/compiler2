; src/common/constants.asm
; Project-wide equates, error codes, and version bytes.

COMPILER_VERSION = $01

; Error Codes
ERR_OK                    = $00
ERR_TOO_MANY_FILES        = $01
ERR_FILE_OPEN             = $02
ERR_FILE_NOT_OPEN         = $03
ERR_FILE_NOT_FOUND        = $04
ERR_DEVICE_NOT_PRESENT    = $05
ERR_NOT_INPUT_FILE        = $06
ERR_NOT_OUTPUT_FILE       = $07
ERR_MISSING_FILE_NAME     = $08
ERR_ILLEGAL_DEVICE_NUMBER = $09
ERR_NEXT_WITHOUT_FOR      = $0A
ERR_SYNTAX                = $0B
ERR_RETURN_WITHOUT_GOSUB  = $0C
ERR_OUT_OF_DATA           = $0D
ERR_ILLEGAL_QUANTITY      = $0E
ERR_OVERFLOW              = $0F
ERR_OUT_OF_MEMORY         = $10
ERR_UNDEFINED_STATEMENT   = $11
ERR_BAD_SUBSCRIPT         = $12
ERR_REDIM_ARRAY           = $13
ERR_DIVISION_BY_ZERO      = $14
ERR_ILLEGAL_DIRECT        = $15
ERR_TYPE_MISMATCH         = $16
ERR_STRING_TOO_LONG       = $17
ERR_FILE_DATA             = $18
ERR_FORMULA_TOO_COMPLEX   = $19
ERR_CANT_CONTINUE         = $1A
ERR_UNDEFINED_FUNCTION    = $1B
ERR_VERIFY                = $1C
ERR_LOAD                  = $1D
ERR_BREAK                 = $1E

; CPU Port constants
CPU_PORT_ALL_RAM        = $30
CPU_PORT_CANONICAL      = $35
