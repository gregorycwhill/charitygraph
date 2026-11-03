# G4-O1E/O1F supervisory acceptance — 2026-10-22

## Disposition

**REJECTED for supervisory acceptance.** The checkout is the requested `064c783e283d7431ce0ce95b8eeb190789acefa9`. The implementation is provider-free and the code-changing route is inactive, but the review/dispatch boundary has material fail-open gaps and the local durable bridge has an expired `running` instruction that has not been reconciled.

No product/source code, migration, watcher, provider, GitHub, Drive, Git, or historical material was changed. This report is the only file written by this task.

## Independent claims

| Claim | Result | Evidence |
|---|---|---|
| Versioned mission/event/review ledger; monotonic and idempotent event sequencing | **PROVEN** for the tested local path | `mission_ledger.py` defines v1 schemas, SQLite tables, `BEGIN IMMEDIATE`, per-mission sequence allocation, unique event keys and payload hashes. Duplicate identical events/decisions are idempotent; changed bytes fail closed. The focused tests passed. |
| Review cursor, conflicting CAS claims, stale HEAD, restart recovery | **PARTIAL** | Temporary provider-free tests prove competing claim rejection, lease/version fencing, cursor persistence after reopen and stale-HEAD recording. However, `record_review()` accepts no review claim token/version, and accepts a cursor below the latest event. A one-off local probe accepted a review without any claim at cursor `1` while event `2` was unreviewed. |
| Scheduled reviewer cannot bypass CAS, miss events, or widen authority | **FAILED** | `record_review()` (lines 355–404) does not require a current review claim. `cursor_seq > latest` is rejected, but `cursor_seq < latest` is accepted. `dispatch()` requires a dispatch claim but does not require a current review decision/cursor or semantic disposition, so dispatcher authority is not coupled to reviewed evidence. |
| Semantic disposition separated from execution disposition | **PROVEN** as storage shape only | Separate `supervisor_decisions.execution_disposition` and `.semantic_disposition` columns and payload fields exist and are exercised by tests. No policy gate was found that makes semantic review a prerequisite for dispatch. |
| O1F exact target, dirty baseline and allowed paths | **PARTIAL** | `bounded_authority.py` validates exact repository/workspace/branch/HEAD/model, relative allowed paths, inactive route, and pre-existing dirty entries. Its direct guard tests pass. But `bridge.py`’s `_run_codex()` records only before/after status-line additions (lines 505–544); it does not call `verify_allowed_changes()` after execution, does not preserve/hash the dirty baseline there, and does not enforce allowed paths in the execution result. |
| `report_only` compatibility and inactive bounded route rejects before claim | **PROVEN** | Focused tests pass. The inactive bounded route is rejected during candidate validation before import/claim; `CODE_CHANGE_ROUTE_ACTIVE = False` remains in both bridge and authority modules. `report_only` remains the narrow five-field policy. |
| No duplicate/replay of previous five terminal executions; no ambiguous physical retry | **PARTIAL** | Read-only SQLite inspection found five prior instructions, each `attempts=1`, `status=complete`, with one submitted/claimed/started/completed sequence. The same database also contains `gate4:engineering:20261022-o1e-o1f-independent-acceptance-v1` at `status=running`, `attempts=1`, no result, only three events, and an expired lease. No replay or reconciliation was performed. This is an unresolved ambiguous physical execution. |
| Live managed watcher/fingerprint; fence v11; 007/403 exclusion; zero historical modification/deletion | **PARTIAL** | Local v11 bytes are present and hash to `f1e7ff71ee693b947f26c0f6105a50a6e52e1a9f67a078201c681f89e7807b94`, targeting this HEAD and recording 007/403 exclusion and zero historical changes. Local `status.json` records fingerprint `ff502c...d4b24e`, READY and the same target. The recorded PIDs `21616` and `396` were not present in the read-only process inventory, so the persisted status is not proof of a live managed pair. External/private Drive state and physical historical counts were not rechecked. |

## Tests and static checks

All commands were provider-free and run at this checkout with pre-existing dirty/untracked material preserved:

```text
$env:PYTHONPATH=(Join-Path (Get-Location) 'src'); python -m pytest tests/test_double_loop_harness.py -q -p no:cacheprovider -o addopts=''
7 passed in 4.67s

$env:PYTHONPATH=(Join-Path (Get-Location) 'src'); python -m pytest tests/test_autonomous_loop.py tests/test_bridge_cutover.py -q -p no:cacheprovider -o addopts=''
15 passed, 1 skipped in 6.74s

$env:PYTHONPATH=(Join-Path (Get-Location) 'src'); python -m pytest tests/test_autonomous_loop.py tests/test_bridge_cutover.py tests/test_double_loop_harness.py -q -p no:cacheprovider -o addopts=''
22 passed, 1 skipped in 11.74s
```

The single skip is the existing explicit real-Codex opt-in rehearsal. `git diff --check` for `064c783^..064c783` passed, and AST parsing of the five changed Python/test files passed. The commit contains only the reported bridge, autonomous-loop, authority, mission-ledger and focused-test paths; the working-tree dirty baseline was not staged or altered.

## Smallest safe next certification task

First quarantine/reconcile the expired current `running` report-only instruction through its authorized existing procedure; do not replay it automatically. Then certify one narrow fail-closed repair: require the current review CAS claim and an exact latest-event cursor for `record_review()`, require dispatch to consume an applicable reviewed decision, and wire a before/after `WorkspaceSnapshot` plus `verify_allowed_changes()` into the bounded execution path. Add provider-free regression tests for those cases, rerun the commands above, and independently re-establish live watcher evidence. Keep `CODE_CHANGE_ROUTE_ACTIVE` false until that certification is separately accepted.

The report cannot activate a route: it changes no activation constant, authority policy, watcher state, or instruction ledger record. A future route activation therefore cannot be inferred from this report; it would require a separately authorized supervisory action and fresh exact-target evidence.
