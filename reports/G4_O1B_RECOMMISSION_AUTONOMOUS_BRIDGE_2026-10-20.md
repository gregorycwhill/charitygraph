# G4-O1B recommissioning report

**Final disposition:** `PARTIAL`  
**Boundary A:** `PARTIAL` — local preparation and exact submission contract complete; host-side connected-file mirror is not available  
**Boundary B:** `PENDING_EXTERNAL_VERIFICATION`  
**Watcher:** not started  
**Publication/provider spend/source acquisition:** none

## Starting state

The Builder began on branch `gate3-cg406-remediation`, initially at the
reported G4-O1 evidence state `c04226669984e357ed74c6630dbef89b2d5ff49b`.
There was one worktree, no active bridge/Codex/watcher process, and no
checked-in `SUPERVISOR_PROTOCOL.md`, `CHATGPT_BOOTSTRAP.md`, launcher, queue,
claim, session, or host-action implementation in this checkout. The mandate
explicitly records that the old bridge was deliberately shut down for the
Gate 3 Greg-as-bus experiment; its absence was not treated as an incident.

The existing untracked Gate 3 evidence inventory and runtime archive were
preserved. No reset, clean, replay, deletion, or protected `.s0-policy-data`
mutation was performed.

## Architecture decision

There is one local claim path for this tranche:

- `LocalAutonomousBridge` owns immutable instruction identity, schema/authority
  checks, target workspace/model validation, durable ingress records, leases,
  stale ownership, explicit ambiguous-interruption reconciliation, result
  persistence, and concise status.
- The existing Builder SQLite runtime and `ReferenceFactory` remain the owner
  of logical tasks, physical attempts, receipts, restart/resume, cost ledger,
  and Builder execution semantics.
- The bridge does not create a second scheduler, semantic store, provider
  transport, or publication path. A future host mirror only materializes a
  connected-file export and calls the adapter importer.
- Guarded GitHub publication remains outside the adapter and was not used.

The old managed bridge cannot be reconciled in code because its implementation
and launcher are not present locally. This is recorded as historical shutdown,
not silently replaced as an active watcher.

The adapter now rejects unsupported target models and accepts only the exact
engineering model `luna-high`. It accepts only UTF-8, no-BOM, one-line
canonical JSON materializations and exposes `status_summary()` backed by its
durable SQLite row.

## Ingress investigation

A dedicated native Google Doc was created through the connected Drive surface:

- ID: `1CfAdNTSHoa0f1KqI1BliuXCbAErD-OH-GSb0Rtu0M6A`
- URL: <https://docs.google.com/document/d/1CfAdNTSHoa0f1KqI1BliuXCbAErD-OH-GSb0Rtu0M6A/edit?usp=drivesdk>
- Title: `CharityGraph G4-O1B Autonomous Ingress Test`

The connector readback verified that the document is empty. The content write
was rejected by the connector because ownership/trust for repository/workspace
metadata egress was not established. No instruction text or private workspace
metadata was written to Drive.

The exact schema, harmless probe, target commit, encoding rules, and minimum
host-mirror action are recorded in
`docs/G4_O1B_SUPERVISORY_SUBMISSION.md`.

The exact probe is intentionally inert:

```text
Record a harmless transport probe only; do not start a watcher, call a provider, acquire sources, publish, merge, or modify product state.
```

The local importer is ready for a future host-side export. It computes the
materialized-byte SHA, rejects BOM/pretty/multi-line/non-UTF-8 input, validates
the envelope, and submits it into the single durable claim path.

## Result transport

The local result surface remains the Git-ignored runtime directory:

`runtime/gate4-autonomous-loop-20261020-commit2/bridge/results/`

It is durable and directly inspectable from the shared workspace, but it is
not currently published to a ChatGPT-readable connected Drive surface. The
return path therefore remains partial. A host mirror would need read access to
the dedicated ingress document and narrowly scoped write access to one private
result location.

## Verification and commits

Focused command:

```text
python -m pytest tests/test_autonomous_loop.py tests/test_phase5_factory.py tests/test_phase5_factory_chaos.py tests/test_phase5_batch_bytes_and_attempts.py tests/test_standard_delivery_job.py tests/runtime/test_task_state.py -q -p no:cacheprovider -o addopts=''
```

Result: **31 passed**.

Relevant local commits:

- `2e15b2d` — initial G4-O1 adapter, rehearsal, tests and report
- `84b7921` — rehearsal identity refresh
- `c042266` — G4-O1 evidence report
- `a23993e` — target-model and materialized-ingress hardening
- `91c00bc` — supervisory submission contract and durable status summary

The previously reported full-suite result remains unchanged: 15 S0
authorisation/identity tests require the absent protected `.s0-policy-data`
package. Those fixtures were not copied, recreated, or modified.

## Recovery and negative evidence

Local tests demonstrate:

- duplicate instruction delivery with the same hash is a no-op;
- duplicate identity with different content is rejected;
- wrong authority and forbidden operations are rejected;
- unsupported target model is rejected;
- active ownership cannot be stolen;
- an expired lease becomes `reconciliation_required` and cannot be reclaimed
  without explicit actor/rationale reconciliation;
- materialized UTF-8 canonical bytes are accepted once;
- BOM and pretty/multi-line JSON are rejected;
- result completion is idempotent and status is durably inspectable.

The existing G4-O1 provider-free Builder artifact remains preserved and records
three retained subjects, bounded concurrency, isolated failure, idempotent
repeat, and restart/resume without duplicate receipt:

`runtime/gate4-autonomous-loop-20261020-commit2/bridge/results/gate4_autonomous-builder-demo_20261020_v5.json`

## Watcher disposition

The dormant watcher was **not started**. No supported launcher or host-side
connected-file adapter exists locally, and historical READY work could not be
shown safe to replay. Starting a watcher would therefore violate the mandate's
fenced-startup and exactly-once conditions.

## Acceptance matrix

| Criterion | State | Evidence |
|---|---|---|
| Dormant-state safety | PASS | No watcher started; no historical queue replayed. |
| Single execution authority | PASS locally | One adapter claim path plus existing Builder runtime; no competing watcher present. |
| Direct ingress | PARTIAL | Native Doc exists, but connector write was rejected and no host mirror exists. |
| Durable integrity | PASS locally | Versioned schema, content hash, target branch/HEAD/model, canonical-byte importer. |
| Controlled execution | PARTIAL | `luna-high` validation is enforced; Codex process/session launch is not wired locally. |
| Return path | PARTIAL | Durable local result exists; connected result publication is not wired. |
| Recovery | PASS locally | Stale ownership, explicit reconciliation, and prior restart/resume evidence. |
| Idempotence | PASS locally | Duplicate submission/completion and Builder repeat tests. |
| Negative testing | PASS locally | Invalid, stale, contradictory, unsupported-model, BOM and ambiguous cases. |
| Local Builder preservation | PASS | Gate 3/G4-O1 evidence and runtime artifacts retained. |
| Live round-trip | PENDING_EXTERNAL_VERIFICATION | Requires trusted connector write plus host mirror. |
| Authority compliance | PASS | No spend, acquisition, publication, merge, release, or gate mutation. |

## Minimum bootstrap and next supervisory action

The one-time external action is to establish trust/egress for this specific
private Doc and one private result location, then provide a host-side exporter
with read access to the Doc and result write access only. No broad Drive scope,
public repository, token in Git, Windows service, or scheduled task is needed
for the first probe.

After that action, the supervising ChatGPT session should write the exact
canonical JSON object in `docs/G4_O1B_SUPERVISORY_SUBMISSION.md` to the named
Doc. The host mirror should export it, call
`import_materialized_instruction()`, and publish the resulting status/result
artifact. ChatGPT should then read that result and repeat the read/submission
to verify no duplicate execution.

Until the connector trust and host export path exist, the correct disposition
is `PENDING_EXTERNAL_VERIFICATION`, not a claim of autonomous completion.
