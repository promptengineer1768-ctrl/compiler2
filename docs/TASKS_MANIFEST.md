# Task Manifest and Completion Evidence

`manifests/tasks.json` is the source of truth for both `TASKS.md` and
`REU_TASKS.md`. It owns every checkbox, task identifier, completion status, and
evidence record; the Markdown files are generated views. Every task also owns
`requirements` (stable requirement IDs or wildcard groups) and `design_refs`
(design-document anchors). Validation rejects an unanchored task and rejects a
traceability requirement that has no owning task.

Use the following workflow:

```powershell
python tools/task_manifest.py validate
python tools/task_manifest.py render
```

Do not edit a generated checkbox. Update the matching `tasks[]` record in the
manifest, add evidence, then render and validate. A complete (`"x"`) task must
have passing evidence and cannot have failing, stale, skipped, missing, or
invalidated evidence. The validator also rejects a stale rendered view.

Evidence has this shape:

```json
{
  "kind": "test",
  "target": "tests/unit/test_editor.py::test_cursor_blink",
  "status": "passing",
  "claim": "The cursor_blink public entry satisfies its unit contract."
}
```

`kind` can also be `artifact`, `symbol`, `command`, `vice_e2e`, or a more
specific project evidence type. The target is machine-addressable; the claim
states exactly what that evidence proves. A multi-test completion claim is
represented by multiple records, one for each test or acceptance command.
The migration preserved the prior conformance audit as `claim_ledger` evidence
with status `invalidated`, so it cannot silently coexist with a complete task.

The checked-in source documents are validated against `REQUIREMENTS.md`,
`REU_REQUIREMENTS.md`, `DESIGN.md`, `REU_DESIGN.md`, and
`manifests/traceability.json` by the ordinary build/traceability workflow.
