# Backend governance and test-harness adoption

This project pins the shared Backend framework and adopts task schema epoch 2.
Requirements and design remain local product authority; Backend supplies schemas,
validation, worker admission, emulator/snapshot orchestration, and oracle contracts.

## Authority and isolation

Trusted workers define requirements, design, tests, expected results, and task
contracts. Low-level workers implement sealed contracts or perform explicitly
scoped operational work. Bulk implementation runs in patch-only isolation; a
trusted controller verifies test digests and patch paths, applies the patch to a
fresh checkout, runs authoritative tests, and records evidence.

## Test discipline

The project uses unit, functional, integration, E2E, hardware, and system layers.
Local emulation covers supported CPU/semantic cases. VICE proves hardware-visible
behavior. Warm snapshots are content-addressed by artifact, runtime, machine,
startup script, and proof contract, and are reusable only after the installed and
started state is proven. Parallel variations use isolated emulator processes,
ports, disks, snapshots, logs, and screenshots.

Every bundled demo requires a production-path E2E case and PNG evidence. Every
implemented keyword/function/statement requires versioned cases against its
authoritative compatibility oracle. Adding the governance files does not claim
that product adapters or production tests have already been implemented.

