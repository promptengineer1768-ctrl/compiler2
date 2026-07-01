# Stock Semantic Reference Fixtures

Expected stock-language semantics are generated from clean VICE sessions:

- `c64_basicv2/`: `x64sc.exe` with stock C64 BASIC V2 and KERNAL;
- `plus4_basicv35/`: `xplus4.exe` with stock Plus/4 BASIC V3.5.

Each fixture records:

```text
schema_version
profile
machine
vice_executable
vice_version
rom_checksums
source_text
input_sequence
reference_mode
raw_screen
raw_error
raw_state
normalized_result
normalization_rules
generator_version
regeneration_fingerprint
```

Reference mode is `immediate` or `program`. Compiler 2 compile-mode E2E tests
use the matching stock program-mode fixture and separately prove that compiled
native code ran.

Stock BASIC V2 and implemented BASIC V3.5 fixtures normally are generated once
for the lifetime of the project because the selected stock ROM semantics do not
change. Generate new cases when additional edge cases are discovered.

Existing fixture regeneration is explicit and reviewed, and is limited to a
documented oracle/ROM correction, generator or normalization fix, or schema
migration. Compiler 2 implementation changes are not a reason to regenerate
expected results. Expected values are not edited by hand when an equivalent
stock keyword can be observed in VICE.

Plus/4 fixtures are semantic references only. They do not define C64 token
bytes, memory addresses, screen layout, or hardware behavior.
