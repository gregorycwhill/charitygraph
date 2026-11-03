# G4-O1E/O1F independent fail-closed recertification — 2026-10-24

## Conclusion

**REJECTED.** The repair is materially stronger and passes the focused provider-free suite, but dispatch still accepts a superseded accepted decision, and the bridge does not enforce the exact `report_only` execution shape. There is **not** enough evidence to proceed to a separate live code-change certification. The bounded route remains inactive; O1G/O1H is not started.

This was read-only and report-only. No provider, source, Drive, GitHub, watcher-management, publication, gate, policy, or production-SQLite mutation was performed.

## Identity, fence, and supervisor state

- `git branch --show-current`: `gate3-cg406-remediation`.
- `git rev-parse HEAD`: `0e57164bd0eb4a8197e21294bcfb603ff6b67ea2`.
- Active local fence: `runtime/g4-o1d-dormant-state-fence-20261020-v12.json`; `state=ACTIVE`, target branch/HEAD match, implementation revision matches, Gate 2/Gate 3 remain closed. SHA-256: `d6a4afe2ace0b532d65700a616c9af315bc50b23c066dd2e925d61dac4052b0d`.
- v12 records legacy execution ineligible, exact technical spec `007` claims `0`, no consumed `007` marker, campaign `403` execution ineligible, and zero historical deletion/modification. The older local v11 is preserved historical evidence, not the active fence.
- `CODE_CHANGE_ROUTE_ACTIVE` search found only `bridge/bridge.py:60` and `src/charitygraph/bounded_authority.py:17`; both are `False`.
- Read-only process facts: launcher PID `31584` and watcher PID `16700` were present; prior Codex PID `17324` was absent. The bridge SQLite read-only query showed six older terminal instructions, each `attempts=1` with `submitted,claimed,started,completed`, and the current instruction `gate4:engineering:20261024-o1e-o1f-independent-recertification-v1` as `running`, owner `g4-o1b-16700-e6b8488e5a07:single-worker`, lease through `2026-10-24T04:35:29Z`, with `submitted,claimed,started`. The current row is this running instruction and was not misclassified as an expired ambiguity.
- `Get-CimInstance Win32_Process` was access-denied; `Get-Process` was used for the available PID fact. No duplicate worker was started.

## MissionLedger review and dispatch probes

Code inspected: `src/charitygraph/mission_ledger.py:452-518` (`record_review`) and `:537-565` (`dispatch`). Each probe used a temporary SQLite fixture, never the live ledger.

`record_review()` uses `BEGIN IMMEDIATE`, validates mission contract branch/HEAD/tranche, requires the current review claim owner/token/version and unexpired lease, computes the exact eligible evidence frontier, rejects any cursor other than that frontier, and writes decision plus cursor in one transaction. Isolated probes produced:

| Probe | Result |
|---|---|
| missing claim; wrong owner/token/version; expired lease | rejected: `ReviewClaimRequired`, `CompareAndSwapConflict`, `SupervisorClaimUnavailable` |
| incomplete, future, and intervening-append cursors | rejected: `StaleReviewCursor` |
| wrong repository HEAD/tranche | rejected: `StaleMissionIdentity` |
| changed replay bytes | rejected: `DuplicateMissionEvent` |
| identical accepted replay | idempotent duplicate accepted |

An intervening evidence append moved the eligible frontier from `2` to `4`; the old cursor was rejected. Identical replay is deliberately checked before claim/identity validation (`:456-473`), which is consistent with idempotence but means an identical terminal replay does not reacquire authority.

`dispatch()` independently requires a current dispatch CAS claim and an unconsumed `ACCEPTED` semantic review whose mission, tranche, repository identity and cursor match the current frontier. Missing, stale, PARTIAL, REJECTED, DECISION_REQUIRED, semantic-partial, wrong-HEAD, already-consumed, and competing dispatch-claim cases all rejected in the isolated probes; the first valid dispatch consumed authority once.

**Residual failure:** two accepted reviews were recorded for the same mission and same evidence frontier (`old`, then `new`). Dispatching `old` succeeded. `dispatch()` checks the selected decision’s cursor against the frontier, but does not require the selected decision to be the latest applicable decision or otherwise mark older decisions superseded. This directly fails the required superseded-decision rejection.

Static trace confirms `_run_codex()` contains no dispatch call; a child Codex result cannot confer new product authority.

## Workspace attestation and report-only path

`capture_workspace()` (`src/charitygraph/bounded_authority.py:78-99`) records branch, full HEAD and all currently dirty/staged/deleted/renamed/untracked paths; `_file_sha()` preserves file, missing and symlink identity. `verify_allowed_changes()` (`:147-183`) compares before/after paths, rejects baseline changes, unexpected paths, repository identity drift, and symlink/path escapes. `bridge/bridge.py:_run_codex()` captures before launch (`:507-515`), after exit (`:538-544`), invokes `verify_allowed_changes()` (`:551-556`) for both normal success and non-zero failure, and returns a durable non-success quarantine state for forbidden changes (`:581-597`) without cleanup or retry.

Independent isolated `_run_codex()` tracing with a patched child showed one `verify_allowed_changes` call each for success, failed exit, and forbidden-change execution. Results were respectively `CODEX_ENGINEERING_COMPLETED`/verified, `CODEX_EXECUTION_FAILED`/verified, and `CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES`/quarantined with `forbidden.txt` unexpected. Existing tests additionally cover modified, deleted, renamed, staged, untracked, baseline and symlink cases.

Residual strictness gap: `_validate_engineering()` (`bridge/bridge.py:404-462`) checks for unsupported report-only fields but does not require exact field equality and defaults a missing `timeout_seconds` to `300` (`:457`). The dedicated `report_only_execution()` helper is exact (`bounded_authority.py:186-190`) but is not called by the bridge. Bounded implementation fields are still rejected in report-only mode and the bounded route remains inactive.

## Tests and diff

Exact command:

```text
$env:PYTHONPATH=(Join-Path (Get-Location) 'src'); python -m pytest tests/test_autonomous_loop.py tests/test_bridge_cutover.py tests/test_double_loop_harness.py -q -p no:cacheprovider -o addopts=''
29 passed, 2 skipped in 14.62s
```

Skips were the explicit real-Codex opt-in rehearsal and the symlink test when Windows symlink creation is unavailable. `python -B -m py_compile` passed for the scoped bridge, authority, ledger, autonomous-loop and three test modules. `git diff --check` passed. `git show --stat HEAD` shows only the four intended commit paths: `bridge/bridge.py`, `src/charitygraph/bounded_authority.py`, `src/charitygraph/mission_ledger.py`, and `tests/test_double_loop_harness.py` (452 insertions, 60 deletions). The working tree had pre-existing dirty/untracked material; this task added only this report.

## Previously rejected findings

1. **Review CAS / exact cursor / restart boundary — PROVEN for the provider-free path.** Evidence: the code pointers above, all negative probes, idempotent replay probe, and the 29-test focused run. Remaining gap: no live supervisor re-certification was inferred from the current instruction.
2. **Dispatcher semantic-review coupling — PARTIAL.** Missing/stale/incomplete/negative/wrong-identity decisions and one-time consumption are now fail-closed, but the superseded-decision probe succeeded when it must reject. Recommendation: require the latest applicable accepted decision (or durable supersession relation) in the same dispatch transaction, then add a competing-review regression test.
3. **O1F workspace and execution boundary — PARTIAL.** Before/after attestation, path/baseline/symlink checks, success/failure invocation, and quarantine were independently exercised. Exact report-only schema enforcement remains incomplete. Recommendation: route report-only through the exact helper or require exact base-field equality, then retest.

## Recommendation

Do not activate the bounded route or begin O1G/O1H. Correct and separately recertify superseded-decision rejection and exact report-only validation. A future live code-change certification must be a separate, explicit ChatGPT-authorised task after those repairs; this report grants no authority.

Temporary fixtures were provider-free and outside the repository under `C:\CharityGraph-runtime`; no production evidence or source bytes were used. Some Windows fixture cleanup was blocked by ACL/SQLite-handle behavior; no repository file, production ledger, watcher, or fence was altered.
