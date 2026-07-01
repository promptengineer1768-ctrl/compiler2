# System Contract Tests

System tests validate the complete build or execution environment rather than
one subroutine or one user-visible feature.

Canonical modules are:

```text
test_system_toolchain.py
test_system_linker_contract.py
test_system_memory_map.py
test_system_banking_vectors.py
test_system_generated_metadata.py
test_system_generated_reference.py
test_system_binary_artifacts.py
test_system_resource_budgets.py
test_system_test_environment.py
```

Typical inputs are ca65 listings, ld65 maps/labels, generated manifests,
`API.md`, `MAP.md`, linked binaries, geoRAM images, PRGs, D64 images, build
fingerprints, and test-harness configuration.

`test_system_generated_reference.py` proves API entry completeness and calling
conventions, memory-map ordering/non-overlap/totals, cross-artifact agreement,
deterministic regeneration, and manifest checksums.

A helper algorithm is still a unit-test subject. A BASIC operation is still a
functional/E2E subject. Use `system` when the property belongs to the assembled
image, build pipeline, packaging, resource contract, or emulator/reference
environment.

Graphics system tests include the VIC bank and `$D018` contract, bitmap and
screen-matrix bounds, exclusion of `$FFF9-$FFFF`, allocator ceiling `$DBFF`,
graphics-exit text/color restoration, and proof that underlying `$DC00-$DFE7`
RAM is reached only through the RAM-under-I/O gate.
