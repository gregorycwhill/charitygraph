# Gate 4 autonomous development loop — engineering report

**Disposition:** `PARTIAL` — supervisory review required  
**Canonicality:** `LOCAL_ONLY`  
**Active gate:** Gate 4 — Builder Industrialised  
**Gate decision:** not requested; Gate 4 remains active and unearned

## Outcome

The local outcome now has a durable, fail-closed ingress/result adapter and a repeatable provider-free three-subject Builder rehearsal. The existing Factory and SQLite runtime remain the execution machinery. No source acquisition, paid provider call, semantic promotion, publication, merge, release, or gate decision occurred.

The development-model objective is incomplete because the available Drive connector is not host-claimable from this Windows workspace. The instruction used for the local demonstration was created by the rehearsal script, not transferred from ChatGPT through an independently observed ingress. This is a platform/bridge limitation, not a reason to claim autonomous transport.

## Transport investigation and implementation

The connected Drive surface can search and read accessible Drive files and has native-file creation/upload operations. The local host has no credentialed Drive watcher, durable polling adapter, or connector-to-filesystem claim path. The repository also contained no checked-in supervisor/watcher implementation to repair. GitHub publication is guarded and was not used as an unapproved transport.

The smallest safe adapter is implemented in `src/charitygraph/autonomous_loop.py`:

- immutable instruction identity and content SHA-256;
- approved ChatGPT-origin and bounded-operation validation;
- exact repository, branch, HEAD and workspace verification;
- SQLite-backed single claim, lease, attempt and event records;
- explicit stale-ownership and ambiguous-interruption handling;
- atomic, hash-addressed result surface;
- duplicate submission and duplicate completion protection;
- fail-closed rejection of publication, merge, acquisition, paid execution and gate-closure operations.

One bootstrap action remains: install/authorise a host-side Drive mirror that materialises the ChatGPT-created immutable instruction into this adapter's `inbox` and publishes the adapter's result file back to the same approved surface. The mirror must preserve envelope bytes and hash, and must not become a second scheduler. Until that action exists, the local adapter is a rehearsal/host transport, not an accepted ChatGPT-to-host bus.

Negative tests cover invalid authority, forbidden operation, conflicting duplicate content, active lease ownership, stale lease ambiguity and explicit reconciliation. Repeated inspection and completion are idempotent.

## Builder demonstration

The script `scripts/run_gate4_autonomous_demo.py` reused the first three non-holdout subjects from the retained Gate 3 review packet. Their only input lineage is the retained review artifact `evidence/gate3-final-semantic-review/case-assessments.json`, SHA-256 `63f2eed81d5ab0dd7317840408a5d32ce10d7b70a1fa81b35e0653d9fd076eca`.

The run produced:

- 3 logical tasks and 3 physical packages;
- bounded parallel execution with 2 workers;
- 2 successful fake-provider receipts and 1 isolated terminal structural failure, while the other two subjects completed;
- repeat execution with no additional receipts;
- an interruption after a receipt was persisted, followed by restart/resume with no duplicate send;
- simulated rehearsal cost of AUD 0.004000, explicitly not actual provider expenditure;
- candidate/coverage output with `not_promoted` projection status for successful subjects and explicit failure/missingness status for the failed subject.

The durable result is at `runtime/gate4-autonomous-loop-20261020-commit2/bridge/results/gate4_autonomous-builder-demo_20261020_v5.json`.

Result SHA-256: `12266b9de0ae73340ca77ffee7835a0b57cbb4810940d78170cc743121eefdc1`.

Runtime databases are local, rebuildable and Git-ignored: `runtime/gate4-autonomous-loop-20261020-commit2/`.

## Gate 4 evidence matrix

| Criterion | Disposition | Evidence |
|---|---|---|
| Model/cost routing | Partial | Existing delivery policy/tests plus fake Standard route and simulated ledger; no live provider/fallback crossing. |
| Batch execution | Partial | Existing Factory batch-control tests pass; this private run used Standard to avoid paid work. |
| Concurrency | Established for provider-free rehearsal | Three physical packages, two bounded workers, deterministic task identity. |
| Restart/resume | Established locally | Receipt persisted before interruption; resume reused it; receipt count stayed 1. |
| Idempotence | Established locally | Repeated equivalent run produced no new receipt. |
| Scheduling/admission | Partial | Durable instruction admission and Factory task/package admission work; no long-running production scheduler claimed. |
| Monitoring | Partial | Durable instruction status/events and per-task SQLite state are inspectable; no operational dashboard. |
| Failure isolation | Established locally | One subject terminally failed while two independent authorised subjects succeeded. |
| Cost telemetry | Established as simulated telemetry | Fake tariff and usage accounting recorded; actual expenditure is zero. |

This is meaningful Gate 4 evidence, but it is not Gate 4 closure evidence by itself and does not establish 65,000-charity readiness.

## Defects and repairs

1. Windows-invalid `:` instruction IDs were being used directly as filenames. Logical IDs remain unchanged in records; filesystem names are now safely normalised.
2. An expired lease was marked ambiguous and immediately raised before the SQLite transaction committed, so the state reverted to the prior lease. The ambiguity event/state is now committed before raising, and explicit reconciliation is required before reclaim.

## Verification

Focused command:

```text
python -m pytest tests/test_autonomous_loop.py tests/test_phase5_factory.py tests/test_phase5_factory_chaos.py tests/test_phase5_batch_bytes_and_attempts.py tests/test_standard_delivery_job.py tests/runtime/test_task_state.py -q -p no:cacheprovider -o addopts=''
```

Result: **29 passed**. `uv` is not installed on this host; the tests used the installed Python 3.13 interpreter at `C:\Users\grego\AppData\Local\Programs\Python\Python313\python.exe`.

The full repository suite reached 99% but had 15 pre-existing environment-dependent failures in the S0 authorisation/identity tests because the private `.s0-policy-data` package is absent from this workspace (`C:\CharityGraph-clean\.s0-policy-data`). Those failures occur before or outside the changed adapter and were not repaired by copying or recreating protected policy material.

Integration instance:

- Builder branch: `gate3-cg406-remediation`
- Builder HEAD during the final execution: `84b792114a628f02cf1a2344520759f929426507`
- Implementation commit: `2e15b2d61b13a9dd2c67d4a415c0351042aaa5ad`; rehearsal-identity commit: `84b792114a628f02cf1a2344520759f929426507`
- Data handoff commit: `f5f154cf2e3f107a9a2563c94626a0e39419fd3e`
- Builder workspace: `C:\CharityGraph-clean\charitygraph`
- Data evidence: retained local review packet, not regenerated or modified
- Canonical/public publication: none

## Acceptance disposition

| Acceptance item | State |
|---|---|
| A. ChatGPT-originated ingress | Missing for this tranche; one host-side Drive mirror bootstrap remains. |
| B. Autonomous engineering | Partial/established locally; diagnosis, repair and tests proceeded without Greg intervention. |
| C. ChatGPT-readable return path | Partial; local result is durable and inspectable, but no direct connector result surface is wired to the host. |
| D. Multi-charity output | Established as bounded private candidate/coverage/failure output for three retained subjects. |
| E. Industrial controls | Partial; provider-free controls are evidenced, live provider delivery and production scheduling are not. |
| F. Instance consistency | Established for the local run; exact branch, HEAD, workspace, Python and input hash recorded. |
| G. Boundary integrity | Established; no acquisition, spend, promotion, publication, merge, release or gate mutation. |

## Human-intervention ledger

| Category | Count | Note |
|---|---:|---|
| Genuine Product Owner decision | 0 | No consequential decision requested. |
| One-time environment/bootstrap action | 0 completed | The required Drive mirror bootstrap remains outstanding. |
| External authority/publication approval | 0 | No external mutation attempted. |
| Routine transport/manual transfer | 0 | Local rehearsal used the adapter; it was not ChatGPT-originated. |
| Routine engineering diagnosis/repair | 0 by Greg | Codex diagnosed and repaired the two ordinary defects above. |
| Unclassified | 0 | — |

## Remaining material risk and next outcome

The material blocker is end-to-end transport identity: a ChatGPT-created instruction must be materialised and claimed by the host without Greg copying its body, and the result must return to a ChatGPT-readable surface. The next highest-value Gate 4 outcome is the single host-side Drive mirror bootstrap, followed by one real immutable instruction and its negative tests. No Gate 4 closure or subsequent product tranche is proposed here.
