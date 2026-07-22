# Claude worker policy

This repository's complete agent policy is in `AGENTS.md`. The following
authority rule applies even when the surrounding tool does not automatically
load that file.

## Worker authority tiers

At task start, self-identify the model. Sonnet 5, Sol 5.6, Terra 5.6, Opus
4.8, Kimi K3, and Fable 5 are high-capability trusted workers. Every other
model defaults to low-level authority unless a human explicitly grants
high-level permission in the chat interface.

Only trusted authority may choose or change requirements, design decisions,
schemas, task authority, acceptance criteria, tests, expected results,
fixtures, snapshots, compatibility oracles, or stale-test resolutions.
Low-level workers may implement approved tasks and may also, when specifically
requested, update named non-normative documentation/files, answer questions,
build, test, format, benchmark, commit, clean the verified repository
`debug/` directory, push an approved branch, or start an approved GitHub
Actions workflow. External mutations require explicit human authorization but
not high-level model status.

A failing approved test may not be weakened or changed by a low-level worker.
Suspected stale tests or ambiguous contracts enter `review_required` for a
trusted pass. “Complete all low level tasks” does not authorize normative
changes, but a high-capability worker may perform low-level tasks.

For unattended batches, treat the worker as an untrusted patch producer:
protect the canonical checkout, tests, manifests, Git metadata, and credentials;
admit only an in-scope text patch; then build, test, and record evidence in a
fresh trusted checkout.


