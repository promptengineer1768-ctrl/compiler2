# Compiler 2 Test Plan

This document defines the complete test coverage for Compiler 2, organized by
scope and execution environment. Every callable assembly subroutine must have
direct unit coverage. Multi-routine paths have integration coverage. User-visible
features have functional coverage. Build and environment invariants have system
contract coverage.

## Test Organization

Tests are organized under `tests/` with the following structure:

```text
tests/
  unit/                           # Direct unit tests for individual routines
  integration/                    # Multi-routine integration tests
  functional/                     # User-visible feature tests
  system/                         # Build, linker, artifact contract tests
  e2e/                            # End-to-end BASIC language tests
  hardware/                       # VICE hardware integration tests
  fixtures/                       # Reference fixtures and test data
    reference/                    # Stock VICE semantic fixtures
```

## Unit Tests by Module

### 6.1 `src/common/constants.asm`

No subroutines. Equates only. Validate that:
- Error codes match `c64rom` BASIC V2 error table indices
- Type tags are unique and non-overlapping
- Dialect/mode flag values are distinct
- Constant coverage includes `ERR_TOO_MANY_FILES`, `ERR_FILE_OPEN`,
  `ERR_FILE_NOT_OPEN`, `ERR_FILE_NOT_FOUND`, `ERR_DEVICE_NOT_PRESENT`,
  `ERR_NOT_INPUT_FILE`, `ERR_NOT_OUTPUT_FILE`, `ERR_MISSING_FILE_NAME`,
  `ERR_ILLEGAL_DEVICE_NUMBER`, `ERR_NEXT_WITHOUT_FOR`, `ERR_SYNTAX`,
  `ERR_RETURN_WITHOUT_GOSUB`, `ERR_OUT_OF_DATA`, `ERR_ILLEGAL_QUANTITY`,
  `ERR_OVERFLOW`, `ERR_OUT_OF_MEMORY`, `ERR_UNDEFINED_STATEMENT`,
  `ERR_BAD_SUBSCRIPT`, `ERR_REDIM_ARRAY`, `ERR_DIVISION_BY_ZERO`,
  `ERR_ILLEGAL_DIRECT`, `ERR_TYPE_MISMATCH`, `ERR_STRING_TOO_LONG`,
  `ERR_FILE_DATA`, `ERR_FORMULA_TOO_COMPLEX`, `ERR_CANT_CONTINUE`,
  `ERR_UNDEFINED_FUNCTION`, `ERR_VERIFY`, `ERR_LOAD`, `ERR_BREAK`,
  `TYPE_NONE`, `TYPE_INTEGER`, `TYPE_FLOAT`, `TYPE_STRING`, `TYPE_ARRAY`,
  `TYPE_FUNCTION`, `BASIC2_DIALECT`, `BASIC35_DIALECT`,
  `IEEE_MODE_LEGACY`, `IEEE_MODE_IEEE`, `BASIC_VERSION`,
  `RUNTIME_ABI_VERSION`, `GUARD_BYTE`, and `GEORAM_MIN_BLOCKS`

### 6.2 `src/common/macros.asm`

No subroutines. Assembly-time macros only. Validate that:
- `assert_canonical` generates correct `$01` check
- `assert_irq_disabled` generates IRQ-state assertion
- `debug_trap` generates BRK with facility ID
- `zp_clobber_check` generates poison/verify sequence
- `page_check` generates boundary assertion
- `stack_balance` generates SP check

### 6.3 `src/resident/irq.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_irq_entry_basic` | unit | local | Verify IRQ entry saves A/X/Y, calls UDTIM, restores registers |
| `test_irq_entry_keyboard` | unit | local | Verify IRQ entry calls SCNKEY after cursor service |
| `test_irq_update_jiffy` | unit | local | Verify IRQ-private jiffy update calls UDTIM only from IRQ entry |
| `test_irq_scan_keyboard` | unit | local | Verify IRQ-private keyboard scan calls SCNKEY only from IRQ entry |
| `test_irq_cursor_blink` | unit | local | Verify cursor visibility toggle |
| `test_irq_restore_mapping` | unit | local | Verify `$01` and P restored correctly |
| `test_irq_nested_irq_safe` | unit | local | Verify IRQ does not touch geoRAM selection |
| `test_irq_jiffy_advance` | unit | local | Verify jiffy clock advances by 1 |
| `test_irq_keyboard_matrix` | unit | local | Verify keyboard state updated |

### 6.4 `src/resident/screen.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_screen_init` | unit | local | Verify screen cleared, cursor at (0,0) |
| `test_screen_clear` | unit | local | Verify screen cleared, cursor homed |
| `test_screen_scroll_up` | unit | local | Verify screen content scrolls up one line |
| `test_screen_putchar` | unit | local | Verify character written at cursor, cursor advances |
| `test_screen_getchar` | unit | local | Verify character read at cursor position |
| `test_screen_cursor_on_off` | unit | local | Verify cursor visibility flag toggles |
| `test_screen_cursor_off` | unit | local | Verify cursor hidden state is idempotent |
| `test_screen_cursor_right` | unit | local | Verify cursor advances, wraps at right edge |
| `test_screen_cursor_left` | unit | local | Verify cursor retreats, wraps at left edge |
| `test_screen_cursor_down` | unit | local | Verify cursor advances, scrolls at bottom |
| `test_screen_cursor_up` | unit | local | Verify cursor retreats |
| `test_screen_line_input` | unit | local | Verify line capture into buffer with quote mode |

### 6.5 `src/resident/kernal_bridge.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_kernal_readst` | unit | local | Verify status read through bridge |
| `test_kernal_setlfs` | unit | local | Verify logical/device/secondary parameters set |
| `test_kernal_setnam` | unit | local | Verify filename set for next operation |
| `test_kernal_open` | unit | local | Verify file opens with correct parameters |
| `test_kernal_close` | unit | local | Verify file closes and table updated |
| `test_kernal_chkin` | unit | local | Verify input channel set |
| `test_kernal_chkout` | unit | local | Verify output channel set |
| `test_kernal_clrchn` | unit | local | Verify channels restored to defaults |
| `test_kernal_chrin` | unit | local | Verify byte read from input channel |
| `test_kernal_chrout` | unit | local | Verify byte written to output channel |
| `test_kernal_load` | unit | local | Verify load from device with correct parameters |
| `test_kernal_save` | unit | local | Verify save to device with correct parameters |
| `test_kernal_settim` | unit | local | Verify jiffy clock set |
| `test_kernal_rdtim` | unit | local | Verify jiffy clock read |
| `test_kernal_stop` | unit | local | Verify STOP key check |
| `test_kernal_getin` | unit | local | Verify keyboard buffer read |
| `test_kernal_udtim` | unit | local | Verify jiffy clock advance |
| `test_kernal_scnkey` | unit | local | Verify keyboard matrix scan |
| `test_kernal_banking_restore` | unit | local | Verify `$01` restored after bridge call |
| `test_kernal_irq_state_save_restore` | unit | local | Verify interrupt state preserved across bridge |

### 6.6 `src/resident/georam_gate.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_georam_call_group` | unit | georam | Verify routine dispatch through group table |
| `test_georam_tail_group` | unit | georam | Verify tail transfer reuses context frame |
| `test_georam_call_group_n` | unit | georam | Verify generated `georam_call_group_n` entries dispatch through group table |
| `test_georam_tail_group_n` | unit | georam | Verify generated `georam_tail_group_n` entries tail-transfer through group table |
| `test_georam_ctx_push` | unit | georam | Verify block/page/registers saved to context stack |
| `test_georam_ctx_pop` | unit | georam | Verify block/page/registers restored from context stack |
| `test_georam_select` | unit | georam | Verify `$DFFE`/`$DFFF` written and mirror updated |
| `test_georam_read_byte` | unit | georam | Verify handle-based byte read with validation |
| `test_georam_read_word` | unit | georam | Verify handle-based word read with boundary check |
| `test_georam_write_byte` | unit | georam | Verify handle-based byte write with validation |
| `test_georam_write_word` | unit | georam | Verify handle-based word write with boundary check |
| `test_georam_copy_from_ram` | unit | georam | Verify bulk ingress from normal RAM |
| `test_georam_copy_to_ram` | unit | georam | Verify bulk egress to normal RAM |
| `test_georam_copy_pages` | unit | georam | Verify geoRAM-to-geoRAM copy |
| `test_georam_checksum` | unit | georam | Verify extent checksum calculation |
| `test_georam_verify_mirror` | unit | georam | Verify software mirror matches hardware |
| `test_georam_nested_calls` | unit | georam | Verify nested call context saving |
| `test_georam_irq_selection_restore` | unit | georam | Verify geoRAM selection restored after IRQ |

### 6.7 `src/resident/ram_under_io.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_ram_under_io_enter` | unit | local | Verify all-RAM mapping selected, IRQ masked |
| `test_ram_under_io_exit` | unit | local | Verify `$35` mapping restored, IRQ restored |
| `test_ram_under_io_copy_in` | unit | local | Verify bytes copied into `$D000-$DFFF` |
| `test_ram_under_io_copy_out` | unit | local | Verify bytes copied from `$D000-$DFFF` |

### 6.8 `src/loader/loader.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_loader_entry` | unit | local | Verify full install sequence completes |
| `test_loader_detect_georam_present` | unit | local | Verify geoRAM detection succeeds |
| `test_loader_detect_georam_absent` | unit | local | Verify geoRAM detection fails gracefully |
| `test_georam_load_georam_file` | unit | local | Verify GEORAM file loaded from disk |
| `test_georam_install_pages` | unit | georam | Verify pages installed byte-by-byte |
| `test_georam_stream_load` | unit | local | Verify CGS1 sidecar streaming decompression |
| `test_georam_stream_header_validate` | unit | local | Verify CGS1 signature and header validation |
| `test_georam_stream_chunk_loop` | unit | local | Verify chunk iteration and decompression |
| `test_georam_stream_page_boundary` | unit | georam | Verify page boundary handling during streaming |
| `test_georam_stream_error_recovery` | unit | local | Verify open/read failure recovery |
| `test_loader_install_ram_payload` | unit | local | Verify RAM payload copied to runtime |
| `test_loader_restore_banking` | unit | local | Verify `$01=$35` restored |
| `test_loader_check_sentinel_valid` | unit | local | Verify sentinel check passes |
| `test_loader_check_sentinel_missing` | unit | local | Verify sentinel check fails |

### 6.9 `src/loader/compiler_init.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_compiler_init` | unit | local | Verify BSS cleared, arenas constructed, editor entered |
| `test_init_clear_bss` | unit | local | Verify `COMPILER_BSS` segment zeroed |
| `test_init_arenas` | unit | local | Verify arena directory constructed with generations |
| `test_init_editor` | unit | local | Verify editor state initialized, screen cleared |
| `test_init_enter_main_loop` | unit | local | Verify initialization transfers to resident main loop |

### 6.10 `src/geoasm/tokenizer.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_token_init` | unit | local | Verify tokenizer state initialized for new line |
| `test_token_next_keyword` | unit | local | Verify keyword token returned with correct ID |
| `test_token_next_identifier` | unit | local | Verify identifier scanned correctly |
| `test_token_identifier` | unit | local | Verify identifier helper accepts BASIC name syntax |
| `test_token_next_number` | unit | local | Verify numeric literal tokenized |
| `test_token_number` | unit | local | Verify number helper preserves stock numeric forms |
| `test_token_next_string` | unit | local | Verify string literal tokenized |
| `test_token_string` | unit | local | Verify string helper handles quotes and terminators |
| `test_token_next_eol` | unit | local | Verify end-of-line detected |
| `test_token_peek` | unit | local | Verify lookahead without advancing |
| `test_token_skip_whitespace` | unit | local | Verify spaces/tabs skipped |
| `test_token_rem` | unit | local | Verify REM content passed verbatim |
| `test_token_data` | unit | local | Verify DATA values collected as raw tokens |
| `test_token_dialect_filter` | unit | local | Verify disabled dialect tokens rejected |
| `test_token_trie_lookup` | unit | local | Verify first-character trie traversal |

### 6.11 `src/geoasm/parser.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_parse_line_simple` | unit | local | Verify simple statement parsed |
| `test_parse_line_compound` | unit | local | Verify compound statement parsed |
| `test_parse_statement` | unit | local | Verify statement dispatcher |
| `test_parse_expression_arithmetic` | unit | local | Verify arithmetic expression parsed |
| `test_parse_expression_comparison` | unit | local | Verify comparison operators parsed |
| `test_parse_comparison` | unit | local | Verify comparison helper returns operator and operands |
| `test_parse_primary_number` | unit | local | Verify primary number parsed |
| `test_parse_primary_string` | unit | local | Verify primary string parsed |
| `test_parse_primary_variable` | unit | local | Verify variable reference parsed |
| `test_parse_primary_function` | unit | local | Verify function call parsed |
| `test_parse_function_call` | unit | local | Verify function-call helper parses arguments |
| `test_parse_array_ref` | unit | local | Verify array-reference helper parses dimensions |
| `test_parse_primary_parenthesized` | unit | local | Verify parenthesized expression parsed |
| `test_parse_term` | unit | local | Verify term-level precedence |
| `test_parse_factor` | unit | local | Verify factor-level precedence |
| `test_parse_for` | unit | local | Verify FOR statement parsed |
| `test_parse_gosub` | unit | local | Verify GOSUB statement parsed |

### 6.12 `src/geoasm/semantic.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_semantic_validate_dialect_valid` | unit | local | Verify valid token accepted |
| `test_semantic_validate_dialect_invalid` | unit | local | Verify invalid token rejected |
| `test_semantic_classify_direct` | unit | local | Verify direct-only command classified |
| `test_semantic_classify_program` | unit | local | Verify program-capable command classified |
| `test_semantic_validate_line_valid` | unit | local | Verify valid syntax accepted |
| `test_semantic_validate_line_invalid` | unit | local | Verify invalid syntax rejected |
| `test_semantic_check_dialect` | unit | local | Verify current dialect returned |
| `test_semantic_check_for_dialect` | unit | local | Verify dialect query returns BASIC2/BASIC35 flag |
| `test_semantic_set_dialect` | unit | local | Verify dialect mode changed |
| `test_semantic_get_numeric_mode` | unit | local | Verify numeric mode query is independent of dialect |
| `test_semantic_set_numeric_mode` | unit | local | Verify numeric mode update preserves dialect state |
| `test_semantic_numeric_mode` | unit | local | Verify legacy/IEEE mode independent of dialect |

### 6.13 `src/geoasm/ir_builder.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_ir_init` | unit | local | Verify IR buffer cleared, write pointer reset |
| `test_ir_emit_stmt` | unit | local | Verify statement record written |
| `test_ir_emit_expr` | unit | local | Verify expression tree node written |
| `test_ir_emit_var_ref` | unit | local | Verify variable reference written |
| `test_ir_emit_array_ref` | unit | local | Verify array reference written |
| `test_ir_emit_string_ref` | unit | local | Verify string reference written |
| `test_ir_emit_branch` | unit | local | Verify branch record written |
| `test_ir_emit_loop` | unit | local | Verify loop descriptor written |
| `test_ir_emit_literal_int` | unit | local | Verify integer literal written |
| `test_ir_emit_literal_float` | unit | local | Verify float literal written |
| `test_ir_emit_literal_str` | unit | local | Verify string literal written |
| `test_ir_finish_line` | unit | local | Verify IR completeness validated |
| `test_ir_get_buf_ptr` | unit | local | Verify current IR write pointer returned |

### 6.14 `src/geoasm/optimizer.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_opt_run_passes` | unit | local | Verify optimization passes executed |
| `test_opt_build_effect_summaries` | unit | local | Verify read/write/escape summaries built |
| `test_opt_eligible_for_for_fast` | unit | local | Verify FOR/NEXT fast-path eligibility |
| `test_opt_eligible_for_do_fast` | unit | local | Verify DO/LOOP fast-path eligibility |
| `test_opt_check_invalidation` | unit | local | Verify invalidation barriers detected |
| `test_opt_check_aliasing` | unit | local | Verify aliasing detected |
| `test_opt_propagate_dirty` | unit | local | Verify dirty masks propagated |
| `test_opt_select_branch_polarity` | unit | local | Verify WHILE/UNTIL polarity selected |
| `test_opt_check_stop_poll` | unit | local | Verify STOP polling eligibility |

### 6.15 `src/geoasm/codegen.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_codegen_init` | unit | local | Verify emitter state reset |
| `test_codegen_emit_stmt` | unit | local | Verify native code emitted for statement |
| `test_codegen_emit_for_fast` | unit | local | Verify FOR/NEXT fast path emitted |
| `test_codegen_emit_for_generic` | unit | local | Verify FOR/NEXT generic frame emitted |
| `test_codegen_emit_do_fast` | unit | local | Verify DO/LOOP fast path emitted |
| `test_codegen_emit_do_generic` | unit | local | Verify DO/LOOP generic frame emitted |
| `test_codegen_emit_if` | unit | local | Verify IF/THEN/ELSE emitted |
| `test_codegen_emit_gosub` | unit | local | Verify GOSUB emitted |
| `test_codegen_emit_return` | unit | local | Verify RETURN emitted |
| `test_codegen_emit_on` | unit | local | Verify ON GOTO/GOSUB emitted |
| `test_codegen_emit_print` | unit | local | Verify PRINT emitted |
| `test_codegen_emit_input` | unit | local | Verify INPUT emitted |
| `test_codegen_emit_let` | unit | local | Verify LET/assignment emitted |
| `test_codegen_emit_dim` | unit | local | Verify DIM emitted |
| `test_codegen_emit_data` | unit | local | Verify DATA record emitted |
| `test_codegen_emit_read` | unit | local | Verify READ emitted |
| `test_codegen_emit_reloc` | unit | local | Verify relocation entry recorded |
| `test_codegen_emit_exit` | unit | local | Verify generated exit path restores runtime state |
| `test_codegen_finish_line` | unit | local | Verify line emission finalization patches branches |
| `test_codegen_get_code_ptr` | unit | local | Verify current code emission pointer returned |

### 6.16 `src/geoasm/diagnostics.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_diag_format_error` | unit | local | Verify error string formatted with line number |
| `test_diag_format_warning` | unit | local | Verify warning formatted |
| `test_diag_format_source_context` | unit | local | Verify source context extracted |
| `test_diag_print_error` | unit | local | Verify error output to screen |
| `test_diag_error_from_kernal` | unit | local | Verify KERNAL error translated |

### 6.17 `src/geoasm/math_trig.asm`

Use legacy project Python proxy accuracy fixtures and proven trig source as
preferred oracle material. Tests must still verify the ported code follows
Compiler 2 ABI, generated ZP allocation, and geoRAM placement rather than the
legacy memory map.

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_math_sin` | unit | local | Verify SIN function |
| `test_math_cos` | unit | local | Verify COS function |
| `test_math_tan` | unit | local | Verify TAN function |
| `test_math_atn` | unit | local | Verify ATN function |
| `test_math_acs` | unit | local | Verify ACS function |
| `test_math_asn` | unit | local | Verify ASN function |

### 6.18 `src/geoasm/math_trans.asm`

Use legacy project Python proxy accuracy fixtures and proven transcendental /
IEEE source as preferred oracle material. Stock BASIC V2 behavior still governs
inherited legacy-mode operations where applicable; IEEE-only operations use the
independent IEEE oracle.

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_math_log` | unit | local | Verify LOG function |
| `test_math_exp` | unit | local | Verify EXP function |
| `test_math_sqr` | unit | local | Verify SQR function |
| `test_math_pow` | unit | local | Verify exponentiation |
| `test_math_rnd` | unit | local | Verify RND function |
| `test_math_fma` | unit | local | Verify fused multiply-add |
| `test_math_remain` | unit | local | Verify IEEE remainder |
| `test_math_min` | unit | local | Verify IEEE minimum |
| `test_math_max` | unit | local | Verify IEEE maximum |
| `test_math_scalb` | unit | local | Verify scale by power of 2 |
| `test_math_logb` | unit | local | Verify unbiased exponent |
| `test_math_mant` | unit | local | Verify mantissa extraction |
| `test_math_rint` | unit | local | Verify round to integer |
| `test_math_nextup` | unit | local | Verify next larger representable |
| `test_math_nextdown` | unit | local | Verify next smaller representable |
| `test_math_copysign` | unit | local | Verify copy sign |
| `test_math_totalorder` | unit | local | Verify total ordering comparison |
| `test_math_isnan` | unit | local | Verify is NaN |
| `test_math_issnan` | unit | local | Verify is signaling NaN |
| `test_math_isinf` | unit | local | Verify is infinite |
| `test_math_isfin` | unit | local | Verify is finite |
| `test_math_isnorm` | unit | local | Verify is normalized |
| `test_math_iszero` | unit | local | Verify is zero |
| `test_math_sgnbit` | unit | local | Verify sign bit extraction |
| `test_math_isunord` | unit | local | Verify is unordered |
| `test_math_bin32str` | unit | local | Verify binary32 to hex string |
| `test_math_val32` | unit | local | Verify hex string to numeric |

### 6.19 `src/runtime/variables.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_var_resolve` | unit | local | Verify descriptor to address resolution |
| `test_var_load_int` | unit | local | Verify 16-bit integer load |
| `test_var_store_int` | unit | local | Verify 16-bit integer store |
| `test_var_load_float` | unit | local | Verify 5-byte float load |
| `test_var_store_float` | unit | local | Verify 5-byte float store |
| `test_var_load_string` | unit | local | Verify string descriptor load |
| `test_var_store_string` | unit | local | Verify string descriptor store |
| `test_var_set_type` | unit | local | Verify descriptor type tag update |
| `test_var_promote_to_float` | unit | local | Verify integer to float promotion |
| `test_var_coerce` | unit | local | Verify type coercion with error |

### 6.20 `src/runtime/arrays.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_arr_dim` | unit | local | Verify array allocation |
| `test_arr_resolve_element` | unit | local | Verify element offset computed |
| `test_arr_load_element` | unit | local | Verify typed element load |
| `test_arr_store_element` | unit | local | Verify typed element store |
| `test_arr_redim` | unit | local | Verify existing array guard |
| `test_arr_free` | unit | local | Verify array deallocation |
| `test_arr_check_bounds` | unit | local | Verify bounds check |

### 6.21 `src/runtime/strings.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_str_alloc` | unit | local | Verify string allocation |
| `test_str_free` | unit | local | Verify string deallocation |
| `test_str_assign` | unit | local | Verify string assignment |
| `test_str_copy` | unit | local | Verify string copy |
| `test_str_concat` | unit | local | Verify string concatenation |
| `test_str_left` | unit | local | Verify LEFT$ function |
| `test_str_right` | unit | local | Verify RIGHT$ function |
| `test_str_mid` | unit | local | Verify MID$ function |
| `test_str_len` | unit | local | Verify LEN function |
| `test_str_cmp` | unit | local | Verify string comparison |
| `test_str_chr` | unit | local | Verify CHR$ function |
| `test_str_asc` | unit | local | Verify ASC function |
| `test_str_val` | unit | local | Verify VAL function |
| `test_str_str` | unit | local | Verify STR$ function |

### 6.22 `src/runtime/math_core.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_math_add` | unit | local | Verify float addition |
| `test_math_sub` | unit | local | Verify float subtraction |
| `test_math_mul` | unit | local | Verify float multiplication |
| `test_math_div` | unit | local | Verify float division |
| `test_math_div_zero` | unit | local | Verify division by zero error |
| `test_math_negate` | unit | local | Verify float negation |
| `test_math_cmp` | unit | local | Verify float comparison |
| `test_math_int` | unit | local | Verify INT function |
| `test_math_sgn` | unit | local | Verify SGN function |
| `test_math_abs` | unit | local | Verify ABS function |
| `test_math_fpe` | unit | local | Verify floating-point examine |
| `test_math_int_to_float` | unit | local | Verify integer to float |
| `test_math_float_to_int` | unit | local | Verify float to integer |
| `test_math_add_int` | unit | local | Verify integer addition |
| `test_math_sub_int` | unit | local | Verify integer subtraction |
| `test_math_mul_int` | unit | local | Verify integer multiplication |
| `test_math_div_int` | unit | local | Verify integer division |

### 6.23 `src/runtime/control.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_ctrl_for_init` | unit | local | Verify FOR frame pushed |
| `test_ctrl_push_loop_frame` | unit | local | Verify generic loop frame push |
| `test_ctrl_pop_loop_frame` | unit | local | Verify generic loop frame pop |
| `test_ctrl_for_next_continue` | unit | local | Verify loop continues |
| `test_ctrl_for_next_done` | unit | local | Verify loop exits |
| `test_ctrl_do_init` | unit | local | Verify DO frame pushed |
| `test_ctrl_loop_test_while` | unit | local | Verify WHILE condition |
| `test_ctrl_loop_test_until` | unit | local | Verify UNTIL condition |
| `test_ctrl_exit_loop` | unit | local | Verify EXIT DO jumps past LOOP |
| `test_ctrl_gosub` | unit | local | Verify GOSUB pushes return |
| `test_ctrl_return` | unit | local | Verify RETURN pops address |
| `test_ctrl_on_goto` | unit | local | Verify ON GOTO branch |
| `test_ctrl_on_gosub` | unit | local | Verify ON GOSUB call |
| `test_ctrl_stop` | unit | local | Verify STOP publishes continuation |
| `test_ctrl_end` | unit | local | Verify END exits cleanly |
| `test_ctrl_cont` | unit | local | Verify CONT restores state |
| `test_ctrl_check_stop` | unit | local | Verify STOP key polled |

### 6.24 `src/runtime/io.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_io_print_value_int` | unit | local | Verify integer printed |
| `test_io_print_value_float` | unit | local | Verify float printed |
| `test_io_print_value_string` | unit | local | Verify string printed |
| `test_io_print_newline` | unit | local | Verify CR output |
| `test_io_print_space` | unit | local | Verify space output |
| `test_io_print_tab` | unit | local | Verify tab stops |
| `test_io_print_comma` | unit | local | Verify zone advance |
| `test_io_print_semicolon` | unit | local | Verify no separator |
| `test_io_input_value` | unit | local | Verify INPUT value read |
| `test_io_input_string` | unit | local | Verify INPUT string read |
| `test_io_get` | unit | local | Verify GET single character |
| `test_io_cmd` | unit | local | Verify CMD redirect |

### 6.25 `src/runtime/runtime_io.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_rio_load` | unit | local | Verify LOAD through KERNAL |
| `test_rio_save` | unit | local | Verify SAVE through KERNAL |
| `test_rio_verify` | unit | local | Verify VERIFY through KERNAL |
| `test_rio_open` | unit | local | Verify OPEN through KERNAL |
| `test_rio_close` | unit | local | Verify CLOSE through KERNAL |
| `test_rio_chrin` | unit | local | Verify CHRIN through KERNAL |
| `test_rio_chrout` | unit | local | Verify CHROUT through KERNAL |
| `test_rio_clrchn` | unit | local | Verify CLRCHN through KERNAL |

### 6.26 `src/runtime/errors.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_err_raise` | unit | local | Verify error formatted and raised |
| `test_err_raise_direct` | unit | local | Verify direct mode error |
| `test_err_from_kernal` | unit | local | Verify KERNAL error translated |
| `test_err_syntax` | unit | local | Verify syntax error shortcut |
| `test_err_type` | unit | local | Verify type mismatch error |
| `test_err_overflow` | unit | local | Verify overflow error |
| `test_err_outofmemory` | unit | local | Verify out of memory error |
| `test_err_undefdfunction` | unit | local | Verify undefined function error |
| `test_err_break` | unit | local | Verify BREAK with CONT descriptor |
| `test_err_save_cont` | unit | local | Verify CONT state saved |

### 6.27 `src/runtime/inspection.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_inspect_shell` | unit | local | Verify REPL loop |
| `test_inspect_parse_command` | unit | local | Verify grammar validation |
| `test_inspect_print_var` | unit | local | Verify variable printing |
| `test_inspect_print_string_var` | unit | local | Verify string variable printing |
| `test_inspect_cont` | unit | local | Verify CONT in shell |
| `test_inspect_list_loader` | unit | local | Verify `2026 SYS2061` output |
| `test_inspect_run` | unit | local | Verify RUN |
| `test_inspect_load` | unit | local | Verify LOAD |
| `test_inspect_save` | unit | local | Verify SAVE |
| `test_inspect_verify` | unit | local | Verify VERIFY |
| `test_inspect_clr` | unit | local | Verify CLR |
| `test_inspect_wedge` | unit | local | Verify wedge commands |

### 6.28 `src/arena/arena_core.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_arena_init_all` | unit | georam | Verify arena directory constructed |
| `test_arena_create` | unit | georam | Verify single arena created |
| `test_arena_destroy` | unit | georam | Verify arena destroyed |
| `test_arena_check_integrity_valid` | unit | georam | Verify integrity check passes |
| `test_arena_check_integrity_corrupt` | unit | georam | Verify integrity check fails |
| `test_arena_reset` | unit | georam | Verify arena reset with generation bump |
| `test_arena_invalidate_generation` | unit | georam | Verify generation incremented |
| `test_arena_get_handle` | unit | georam | Verify offset to handle resolved |
| `test_arena_handle_valid` | unit | georam | Verify handle validation |

### 6.29 `src/arena/page_alloc.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_page_alloc_init` | unit | georam | Verify free bitmap initialized |
| `test_page_alloc` | unit | georam | Verify page allocation |
| `test_page_free` | unit | georam | Verify page deallocation |
| `test_page_alloc_count` | unit | georam | Verify free page count |
| `test_page_alloc_largest` | unit | georam | Verify largest contiguous extent |
| `test_page_check_in_range` | unit | georam | Verify bounds check |

### 6.30 `src/arena/overlay_dispatch.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_overlay_enter` | unit | georam | Verify overlay page swapped in |
| `test_overlay_exit` | unit | georam | Verify previous page restored |
| `test_overlay_resolve` | unit | georam | Verify routine ID to page/offset |
| `test_overlay_validate` | unit | georam | Verify directory integrity |

### 6.31 `src/arena/georam_detect.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_detect_georam_present` | unit | georam | Verify detection succeeds |
| `test_detect_georam_absent` | unit | georam | Verify detection fails gracefully |
| `test_detect_save_state` | unit | georam | Verify state preserved |
| `test_detect_probe_pattern1` | unit | georam | Verify first probe pattern |
| `test_detect_probe_pattern2` | unit | georam | Verify second probe pattern |
| `test_detect_probe_aliasing` | unit | georam | Verify capacity detection |
| `test_detect_restore_state` | unit | georam | Verify state restored |
| `test_detect_check_minimum` | unit | georam | Verify minimum capacity check |
| `test_detect_publish_profile` | unit | georam | Verify profile published |
| `test_detect_validate_profile` | unit | georam | Verify profile validation |

### 6.32 `src/arena/context_stack.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_ctx_init` | unit | georam | Verify stack pointer reset |
| `test_ctx_push` | unit | georam | Verify context saved |
| `test_ctx_pop` | unit | georam | Verify context restored |
| `test_ctx_depth` | unit | georam | Verify depth query |
| `test_ctx_check_overflow` | unit | georam | Verify overflow guard |
| `test_ctx_underflow` | unit | georam | Verify underflow detection |

### 6.33 `src/resident/resident_main.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_resident_main_loop` | unit | local | Verify input captured and dispatched |
| `test_resident_poll_input` | unit | local | Verify foreground GETIN called |
| `test_resident_submit_line` | unit | local | Verify line submitted to dispatch |
| `test_resident_assert_boundary` | unit | local | Verify boundary assertion |

### 6.34 `src/resident/fatal.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_fatal_georam` | unit | georam | Verify fatal cleanup and report |
| `test_fatal_restore_machine` | unit | local | Verify machine state restored |

### 6.35 `src/geoasm/editor_svc.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_editor_submit_line` | unit | georam | Verify line parsed and published |
| `test_editor_delete_line` | unit | georam | Verify line deleted with repair |
| `test_editor_detokenize_line` | unit | georam | Verify LIST conversion |
| `test_editor_list_range` | unit | georam | Verify range listing |
| `test_editor_ready_transition` | unit | georam | Verify READY state transition |

### 6.36 `src/geoasm/program_codec.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_program_classify_stock` | unit | local | Verify stock format classified |
| `test_program_classify_extended` | unit | local | Verify extended format classified |
| `test_program_classify_file` | unit | local | Verify file classifier distinguishes stock, extended, and invalid inputs |
| `test_program_decode_stock` | unit | local | Verify BASIC V2 import |
| `test_program_encode_stock` | unit | local | Verify BASIC V2 export |
| `test_program_decode_extended` | unit | local | Verify extended import |
| `test_program_encode_extended` | unit | local | Verify extended export |

### 6.37 `src/geoasm/program_store.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_program_tx_begin` | unit | georam | Verify transaction started |
| `test_program_tx_put_line` | unit | georam | Verify line staged |
| `test_program_tx_delete_line` | unit | georam | Verify deletion staged |
| `test_program_tx_commit` | unit | georam | Verify atomic publish |
| `test_program_tx_abort` | unit | georam | Verify rollback |
| `test_program_replace_from_load` | unit | georam | Verify transactional LOAD |

### 6.38 `src/geoasm/direct_dispatch.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_direct_probe_prefix_wedge` | unit | local | Verify `$`, `/`, `@`, `!` detected |
| `test_direct_probe_prefix_normal` | unit | local | Verify normal input classified |
| `test_direct_classify_direct` | unit | local | Verify direct-only command |
| `test_direct_classify_program` | unit | local | Verify program-capable command |
| `test_direct_execute_command` | unit | local | Verify direct command executed |
| `test_direct_execute_temporary` | unit | local | Verify temporary program executed |

### 6.39 `src/geoasm/compiler_pipeline.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_pipeline_compile_line` | unit | local | Verify single line compiled |
| `test_pipeline_compile_program` | unit | local | Verify whole program compiled |
| `test_pipeline_serialize_boundary` | unit | local | Verify boundary serialized |
| `test_pipeline_validate_boundary` | unit | local | Verify boundary validated |
| `test_pipeline_report_failure` | unit | local | Verify failure reported without side effects |

### 6.40 `src/geoasm/incremental.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_incremental_fingerprint` | unit | local | Verify fingerprint computed |
| `test_incremental_mark_dependents` | unit | local | Verify dirty set computed |
| `test_incremental_resolve_dirty` | unit | local | Verify dirty records recompiled |
| `test_incremental_publish` | unit | local | Verify atomic publication |
| `test_incremental_can_run` | unit | local | Verify RUN guard |
| `test_incremental_abort` | unit | local | Verify rollback |

### 6.41 `src/geoasm/compile_export.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_export_parse_command` | unit | local | Verify COMPILE command parsed |
| `test_export_collect_dependencies` | unit | local | Verify runtime closure collected |
| `test_export_link_image` | unit | local | Verify standalone image linked |
| `test_export_check_budgets` | unit | local | Verify code/workspace budgets |
| `test_export_write_prg` | unit | local | Verify PRG written to device |

### 6.42 `src/geoasm/dos_wedge.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_wedge_parse` | unit | local | Verify prefix command parsed |
| `test_wedge_dispatch_development` | unit | local | Verify development dispatch |
| `test_wedge_format_directory` | unit | local | Verify directory formatted |

### 6.43 `src/runtime/graphics.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_graphics_enter` | unit | local | Verify bitmap mode entered |
| `test_graphics_exit` | unit | local | Verify text mode restored |
| `test_graphics_matrix_copy` | unit | local | Verify screen matrix copied |
| `test_graphics_validate_bounds` | unit | local | Verify bounds validated |

### 6.44 `src/runtime/ieee_state.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_fp_get_mode` | unit | local | Verify mode query |
| `test_fp_set_mode` | unit | local | Verify mode change |
| `test_fp_get_flags` | unit | local | Verify flags read |
| `test_fp_clear_flags` | unit | local | Verify flags cleared |
| `test_fp_set_rounding` | unit | local | Verify rounding mode set |
| `test_fp_test_flags` | unit | local | Verify flag testing |
| `test_fp_load_constant` | unit | local | Verify IEEE constants |

### 6.45 `src/runtime/data.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_data_read` | unit | local | Verify READ advances cursor |
| `test_data_restore` | unit | local | Verify RESTORE resets cursor |
| `test_data_reset` | unit | local | Verify stream state initialized |

### 6.46 `src/runtime/system.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_system_peek` | unit | local | Verify PEEK reads address |
| `test_system_poke` | unit | local | Verify POKE writes address |
| `test_system_poke_protected` | unit | local | Verify POKE denied to protected range |
| `test_system_sys` | unit | local | Verify SYS calls user code |
| `test_system_usr` | unit | local | Verify USR calls user routine |
| `test_system_wait` | unit | local | Verify WAIT polls address |
| `test_system_ti_load` | unit | local | Verify TI read |
| `test_system_ti_store` | unit | local | Verify TI set |
| `test_system_ti_string_load` | unit | local | Verify TI$ formatted |
| `test_system_ti_string_store` | unit | local | Verify TI$ parsed and set |

### 6.47 `src/runtime/wedge.asm`

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_wedge_directory` | unit | local | Verify directory streamed |
| `test_wedge_load_absolute` | unit | local | Verify `/` load |
| `test_wedge_status_or_command` | unit | local | Verify `@` status/command |
| `test_wedge_stream_seq` | unit | local | Verify `!` SEQ streaming |
| `test_wedge_confirm_destructive` | unit | local | Verify confirmation guard |

## Integration Tests

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_loader_full_install` | integration | local | Complete loader sequence from entry to compiler_init |
| `test_georam_full_dispatch_cycle` | integration | georam | Full geoRAM call through gate, context, and return |
| `test_tokenizer_to_parser` | integration | local | Tokenizer output fed to parser |
| `test_parser_to_codegen` | integration | local | Parser output fed to codegen |
| `test_pipeline_full_compile` | integration | local | Full pipeline from source to compiled code |
| `test_arena_page_lifecycle` | integration | georam | Arena create, allocate, use, free, destroy |
| `test_overlay_dispatch_cycle` | integration | georam | Overlay enter, use, exit, re-enter |
| `test_error_unwind_full` | integration | local | Error raised through all layers to shell |
| `test_kernal_bridge_full_cycle` | integration | local | Bridge call with banking save/restore |
| `test_program_tx_full_cycle` | integration | georam | Transaction begin, modify, commit |

## Host Tool Tests

Host tool tests exercise the Python generators and validators described in
`SKELETON.md` section 7. Unit tests cover deterministic function behavior with
fixtures; integration tests run tool chains against checked-in manifests and
build artifacts.

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_zp_alloc_load_manifest` | tool-unit | host | `tools/zp_alloc.py` loads `manifests/zero_page.json` and ROM call domains |
| `test_zp_alloc_color_graph` | tool-unit | host | `tools/zp_alloc.py` assigns deterministic non-overlapping ZP colors |
| `test_zp_alloc_generate_output` | tool-integration | host | `tools/zp_alloc.py` writes `zp_symbols.inc`, `zp_allocation.json`, `zp_allocation.md`, and `zp_interference.dot` |
| `test_georam_pages_assign_placement` | tool-unit | host | `tools/georam_pages.py` assigns bounded routine placements |
| `test_georam_pages_generate_directory` | tool-integration | host | `tools/georam_pages.py` writes `routine_directory.json` and test exports |
| `test_generate_contracts_outputs` | tool-integration | host | `tools/generate_contracts.py` writes command, ABI, arena, entry, and format contracts |
| `test_linker_config_write_config` | tool-integration | host | `tools/linker_config.py` writes `compiler.cfg` with valid memory and vectors |
| `test_extract_segments_payload` | tool-integration | host | `tools/extract_segments.py` writes `compile.bin` from file-backed segments only |
| `test_prepare_compressor_segments` | tool-integration | host | `tools/prepare_compressor_segments.py` writes `segments/compiler_main.bin` and `compressor_layout.cfg` |
| `test_package_d64_outputs` | tool-integration | host | `tools/package_d64.py` validates `basicv3.prg`, `georam.bin`, and `compiler.d64` |
| `test_validate_build_contracts` | tool-integration | host | `tools/validate_build.py` verifies manifests, layout, references, artifacts, and fingerprint |
| `test_test_harness_matrix` | tool-integration | host | `tools/test_harness.py` collects callable coverage and writes traceability matrices |
| `test_generate_reference_outputs` | tool-integration | host | `tools/generate_reference.py` writes deterministic `API.md` and `MAP.md` |

## Functional Tests

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_line_entry_submit` | functional | local | User types line, it is parsed and stored |
| `test_line_delete` | functional | local | User deletes numbered line |
| `test_immediate_execution` | functional | local | User executes immediate command |
| `test_program_load_save` | functional | local | Program LOAD/SAVE round-trip |
| `test_compile_export` | functional | local | COMPILE command produces standalone PRG |
| `test_list_output` | functional | local | LIST displays program correctly |
| `test_dos_wedge_dollar` | functional | local | `$` shows directory |
| `test_dos_wedge_slash` | functional | local | `/` loads file |
| `test_dos_wedge_at` | functional | local | `@` shows status |
| `test_dos_wedge_bang` | functional | local | `!` streams SEQ file |
| `test_stop_cont_cycle` | functional | local | STOP then CONT resumes |
| `test_for_next_loop` | functional | local | FOR/NEXT executes correctly |
| `test_do_loop_cycle` | functional | local | DO/LOOP executes correctly |
| `test_gosub_return_cycle` | functional | local | GOSUB/RETURN executes correctly |
| `test_on_goto_branch` | functional | local | ON GOTO branches correctly |
| `test_input_prompt` | functional | local | INPUT shows prompt and reads |
| `test_print_formatting` | functional | local | PRINT formats output correctly |

## System Contract Tests

### Build and Toolchain

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_ca65_version` | system | static | Required ca65 version recorded |
| `test_ld65_version` | system | static | Required ld65 version recorded |
| `test_compressor_version` | system | static | Required compressor version recorded |
| `test_deterministic_build` | system | static | Clean build equals incremental no-change |
| `test_no_stale_generated` | system | static | No stale generated files |

### Linker and Memory Layout

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_linker_memory_segments` | system | static | MEMORY/SEGMENT settings valid |
| `test_linker_no_overlap` | system | static | No segment overlaps |
| `test_linker_vectors` | system | static | NMI/RESET/IRQ vectors at `$FFFA-$FFFF` |
| `test_linker_resident_budget` | system | static | Resident code within budget |
| `test_linker_geoRAM_budget` | system | static | geoRAM code within budget |

### Banking and Vectors

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_canonical_banking` | system | static | `$35` mapping during runtime |
| `test_only_approved_writers` | system | static | Only KERNAL bridge writes `$01` |
| `test_irq_nmi_pinned` | system | static | IRQ/NMI code pinned correctly |
| `test_high_memory_reserved` | system | static | `$FFF9-$FFFF` reserved |

### Generated Metadata

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_routine_ids` | system | static | Routine IDs unique and complete |
| `test_geoRAM_page_placement` | system | static | geoRAM pages assigned correctly |
| `test_call_directory` | system | static | `routine_directory.json` matches placements, ABI, and checksums |
| `test_zp_allocation` | system | static | `zp_symbols.inc`, `zp_allocation.json`, `zp_allocation.md`, and `zp_interference.dot` are valid and consistent |
| `test_arena_layout` | system | static | `arena_layout.json` matches arena policy and linker map |
| `test_runtime_abi` | system | static | `runtime_abi.json` has stable public compiled-code dependencies |
| `test_entry_manifests` | system | static | `production_entries.json` and `test_entries.json` match routine manifests and linked exports |
| `test_keyword_lookup_report` | system | static | `keyword_lookup_report.json` proves trie bounds, timing, and command coverage |
| `test_requirements_matrix` | system | static | `requirements_matrix.json` and `requirements_matrix.md` cover requirements, fixtures, and tests |

### Generated References

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_api_completeness` | system | static | `API.md` contains all production entries |
| `test_api_calling_conventions` | system | static | Calling conventions consistent |
| `test_map_sorted` | system | static | `MAP.md` sorted and non-overlapping |
| `test_map_totals` | system | static | Occupied/free totals balance |
| `test_generated_reference_deterministic` | system | static | `API.md` and `MAP.md` are UTF-8/LF, stable ordered, and free of host paths |

### Binary Artifacts

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_build_directories` | system | static | `obj/`, `listings/`, and `generated/` exist only as declared build outputs |
| `test_linked_image` | system | static | `compiler.bin`, `compiler.map`, and `compiler.lbl` agree on linked labels and ranges |
| `test_payload_extract` | system | static | `compile.bin` contains only file-backed RAM payload ranges |
| `test_prg_format` | system | static | `basicv3.prg` load address and `2026 SYS2061` loader line are valid |
| `test_georam_image` | system | static | `georam.bin` image size/order/padding are valid |
| `test_compressed_georam_sidecar` | system | static | `GEORAM_compressed.prg` and `GEORAM_compressed.json` have CGS1 integrity and round-trip |
| `test_d64_contents` | system | static | `compiler.d64` directory and file types are valid |
| `test_d64_checksums` | system | static | File checksums in D64 |
| `test_build_manifests` | system | static | `build_manifest.json`, `loader_manifest.json`, and `size_report.json` match produced artifacts |

### Resource Budgets

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_resident_byte_budget` | system | static | Resident code within byte limit |
| `test_geoRAM_page_budget` | system | static | geoRAM pages within limit |
| `test_stack_depth` | system | static | Maximum stack depth within limit |
| `test_context_depth` | system | static | Maximum context nesting within limit |
| `test_loader_size_budget` | system | static | Loader + georam_stream_reader within budget |

### Compressor Integration

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_compressor_available` | system | static | Compressor tools found at expected paths |
| `test_georam_stream_config` | system | static | `georam_stream.cfg` valid |
| `test_georam_compression_roundtrip` | system | static | Compress/decompress produces identical output |
| `test_georam_sidecar_verify` | system | static | Sidecar verified by `lzss_unpacker` |

## E2E Language Tests

### BASIC V2 Profile

| Module | Scope | Environment | Description |
|---|---|---|---|
| `test_e2e_basicv2_functions.py` | e2e | vice | Complete BASIC V2 function surface |
| `test_e2e_basicv2_statements.py` | e2e | vice | Complete BASIC V2 statement surface |

### BASIC V3 Profile

| Module | Scope | Environment | Description |
|---|---|---|---|
| `test_e2e_basicv3_functions.py` | e2e | vice | BASIC V3 functions (inherited + extensions) |
| `test_e2e_basicv3_statements.py` | e2e | vice | BASIC V3 statements (inherited + extensions) |

### BASIC V3.5 Profile

| Module | Scope | Environment | Description |
|---|---|---|---|
| `test_e2e_basicv35_functions.py` | e2e | vice | BASIC V3.5 functions |
| `test_e2e_basicv35_statements.py` | e2e | vice | BASIC V3.5 statements |

### IEEE Extensions

| Module | Scope | Environment | Description |
|---|---|---|---|
| `test_e2e_basicv3_functions_ieee.py` | e2e | vice | IEEE 754 functions |
| `test_e2e_basicv3_statements_ieee.py` | e2e | vice | IEEE 754 statements |

### Execution Modes

Every E2E test runs in applicable modes:
- `immediate`: submit directly at READY
- `program`: store numbered lines and RUN
- `compile`: use COMPILE and execute native artifact

## Hardware Tests

| Test | Scope | Environment | Description |
|---|---|---|---|
| `test_keyboard_full_path` | hardware | vice | Key event -> CIA -> IRQ -> SCNKEY -> GETIN -> editor |
| `test_irq_timer` | hardware | vice | CIA Timer A configured correctly |
| `test_irq_vector` | hardware | vice | IRQ vector reaches pinned code |
| `test_udtim_advance` | hardware | vice | Jiffy clock advances |
| `test_cursor_service` | hardware | vice | Cursor blink service bounded |
| `test_scnkey_order` | hardware | vice | SCNKEY follows UDTIM |
| `test_stop_key` | hardware | vice | STOP key closes channels |
| `test_device_load_save` | hardware | vice | Real KERNAL load/save |
| `test_banking_switch` | hardware | vice | ROM/I/O banking correct |
| `test_georam_capacity` | hardware | vice | geoRAM capacity profiles |
| `test_irq_during_compile` | hardware | vice | IRQ during long compile |
| `test_irq_during_math` | hardware | vice | IRQ during math operations |

## Smoke Test Selection

The smoke subset includes:
- One public-entry ABI unit test
- One multi-routine integration test
- One linker/memory-map system contract test
- One generated-artifact system contract test
- One geoRAM selection/call test
- One function and one statement from each active language profile
- Immediate, program, and compile execution
- One snapshot-backed E2E READY-to-result path
- One focused keyboard/IRQ health test when VICE smoke is requested

## Regression Placement

Regressions extend the owning suite:
- Routine contract failures -> unit suite
- Multi-routine failures -> integration suite
- User-visible feature failures -> functional suite
- Linker/layout/artifact/environment failures -> system contract module
- Language semantic failures -> E2E case table
- IRQ/keyboard/device/timing failures -> hardware suite

Never create `tests/regressions/`, a `regression` marker, or ad hoc regression
files. Add named parameters or focused tests to existing modules.

## Completion Rule

A feature is complete when:
- Every new callable subroutine has direct unit coverage
- Multi-subroutine paths have integration coverage
- User-visible behavior has functional coverage
- Build/layout/artifact obligations have system contract coverage
- Applicable profile/mode/kind E2E matrix cells are present
- Stock-compatible E2E assertions have traceable reference fixtures
- Requirements are mapped to tests
- Static and local layers pass
- Relevant VICE integration passes
- Resident and geoRAM size deltas are recorded
- Documentation and generated schemas agree
- `API.md` and `MAP.md` are present, deterministic, current, and consistent
