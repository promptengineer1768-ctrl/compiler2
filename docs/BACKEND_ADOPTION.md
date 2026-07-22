# Backend Framework Adoption

Compiler 2 pins the sibling Backend framework and validates the shared target,
low-memory, stock-BASIC-return, and consumer-lock schemas alongside its existing
product manifests. The Backend contracts are additive: Compiler 2 requirements,
design, task evidence, runtime ABI, placement, and VICE tests remain authoritative.

The current target profile deliberately declares `non_smc` dispatch. Adopting the
framework's aligned-page self-modifying dispatcher requires a writable resident-RAM
trampoline, generated reachability/layout evidence, and production-path tests; the
framework example is not evidence that Compiler 2 already implements that path.

The C64 low-memory profile uses the framework's stock partition and keeps BASIC,
KERNAL, the stock screen, and sprite-pointer ownership live. Tape workspace is
reclaimable because Compiler 2 does not provide an active tape service. The Plus/4
profile conservatively reserves the complete shared schema window: C64 ownership
facts are never projected onto the Plus/4 reference machine.

The BASIC-return profiles specify the common ordered handoff contract. The C64
profile is an adoption-gap contract until every step has production-byte and VICE
evidence. The Plus/4 profile is reference-only and cannot become a production
adapter until its symbolic entries and ownership map are derived from authoritative
Plus/4 ROM labels.

`manifests/backend/backend.lock.json` pins the exact sibling revision and hashes
every adopted consumer input. A normal validation must fail when any locked file is
missing or changed; upgrades regenerate the lock explicitly after compatibility
review.

## Remote CI readiness

`.github/workflows/backend-consumer-ci.yml` is the first remote-consumer proof
adapter. It checks out the Backend repository at the lock revision, builds and tests
Compiler 2 on `windows-2022`, writes JUnit plus a JSON run summary, and publishes
separate downloadable artifacts for binaries/disks, manuals/generated references,
the distribution bundle, and test reports. The Backend repository is an explicit
workflow-dispatch input so the trusted publisher controls the remote used for the
proof. Actions are pinned by commit digest and workflow permissions are read-only.

Skeleton generation is intentionally absent from CI. The trusted profile converts all
405 authoritative routine records and the final trusted task renders a tracked,
fail-closed review snapshot under `generated/backend-skeletons`. Its 50 shadow modules
contain deliberate assembler errors and are not production build inputs. The snapshot
freezes routine names, module ownership, ABI descriptions, and test traceability for
design review; it is not a duplicate implementation and must never overwrite `src/`.
