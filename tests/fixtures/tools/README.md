# Host Tool Fixtures

Host-tool fixture data is grouped by the owning tool:

```text
tests/fixtures/tools/
  zp_alloc/
  georam_pages/
  generate_contracts/
  linker_config/
  extract_segments/
  prepare_compressor_segments/
  package_d64/
  validate_build/
  test_harness/
  generate_reference/
```

Tests may construct small per-case inputs in pytest temporary directories.
Checked-in golden files belong in the corresponding directory above and must
contain only stable semantic content.

Generated-output comparisons normalize CRLF to LF and may ignore timestamps
and absolute host paths through the shared helpers in `conftest.py`. They must
not ignore ordering, addresses, sizes, identifiers, checksums, payload bytes,
or any other semantic field. A timestamp or host path is ignored only when it
is explicitly non-contractual; release artifacts are expected to omit both.
