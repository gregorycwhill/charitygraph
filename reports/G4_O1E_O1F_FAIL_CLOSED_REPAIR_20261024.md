# G4-O1E/O1F fail-closed supervisory boundary repair — 2026-10-24

## Scope and disposition

This report records the provider-free local repair requested by the O1E/O1F brief. No watcher restart, instruction creation, historical replay, provider call, GitHub mutation, Drive reconfiguration, policy change, or gate closure was performed.

The implementation commit is `0e57164bd0eb4a8197e21294bcfb603ff6b67ea2` on branch `gate3-cg406-remediation`. The checkout HEAD is the same full SHA. The preflight identity before the repair was the required `064c783e283d7431ce0ce95b8eeb190789acefa9`.

## Implemented repairs

- `MissionLedger.record_review()` now requires a current review CAS claim with owner, token, version/lease, mission, tranche, branch and full HEAD identity. It performs the claim, exact latest eligible event frontier, cursor and decision write in one SQLite transaction. Identical accepted decision bytes replay idempotently; changed bytes fail closed.
- `MissionLedger.dispatch()` now requires a current dispatch CAS claim plus a current `ACCEPTED` semantic review for the exact mission, tranche and repository identity. It rejects missing, stale, incomplete, superseded, partial, rejected, decision-required and already-consumed decisions, then consumes the decision authority exactly once in the same transaction.
- `WorkspaceSnapshot`/`verify_allowed_changes()` now cover complete tracked, modified, staged, deleted, renamed and untracked baselines, repository identity drift and symlink/path escapes. The real Codex path captures before and after snapshots, records an attestation on success or failure, and durably returns a non-success quarantine result for out-of-scope changes without cleanup or retry.
- `CODE_CHANGE_ROUTE_ACTIVE` remains `False` in both authority and bridge code. `report_only` remains narrow and compatible.

## Validation evidence

Command:

```text
$env:PYTHONPATH=(Join-Path (Get-Location) 'src'); python -m pytest tests/test_autonomous_loop.py tests/test_bridge_cutover.py tests/test_double_loop_harness.py -q -p no:cacheprovider -o addopts=''
29 passed, 2 skipped
```

The two skips are the existing explicit real-Codex/provider opt-in rehearsals. `git diff --check` passed and AST parsing passed for all four scoped Python/test files.

The focused harness contains negative evidence for: review without a claim; incomplete and newly-stale cursors; wrong claim owner/token/version; semantic dispositions that cannot dispatch; one-time decision consumption with competing dispatch claimants; unauthorized additions, modifications, deletions, renames and staged changes; symlink escape; and workspace attestation after both successful and failed Codex child exits. The five pre-existing historical terminal instructions remain one-attempt `complete`; the later independent O1E/O1F acceptance instruction is also terminal and was not replayed.

## Fence, worker and dormant-state reconciliation

Fence v11 remains active and untouched at:

`C:\CharityGraph-clean\charitygraph\runtime\g4-o1d-dormant-state-fence-20261020-v11.json`

Its private Drive mirror is:

`C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\cg-g4-o1b-dormant-state-fence-20261020-v11.json`

Both files are 2,687 bytes with SHA-256 `f1e7ff71ee693b947f26c0f6105a50a6e52e1a9f67a078201c681f89e7807b94`. The fence still targets the pre-repair HEAD `064c783e`, keeps Gate 2 and Gate 3 closed, excludes technical specification `007` and campaign `403`, and records zero historical deletion/modification. No dormant state was changed.

The existing managed pair was not stopped or restarted: launcher PID `21616`, watcher PID `396`, instance `g4-o1b-396-75fee3dc2112`. After the authorized source commit advanced HEAD, the unchanged v11 fence correctly caused the watcher to fail closed with `RuntimeError: fence HEAD does not match watcher workspace`. Its last durable runtime status is therefore `ERROR`, not proof of repaired live execution. The source commit is not loaded into that already-running Python process.

Runtime status/result locations:

- local status: `C:\CharityGraph-clean\charitygraph\runtime\g4-o1b-controlled-cutover-20261020\status.json`
- local bridge ledger: `C:\CharityGraph-clean\charitygraph\runtime\g4-o1b-controlled-cutover-20261020\bridge\bridge.sqlite3`
- prior independent acceptance result: `C:\CharityGraph-clean\charitygraph\runtime\g4-o1b-controlled-cutover-20261020\bridge\results\gate4_engineering_20261022-o1e-o1f-independent-acceptance-v1.json`
- prior private Drive result: `C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\cg-g4-o1c-result-gate4_engineering_20261022-o1e-o1f-independent-acceptance-v1.json`
- canonical private Drive status link: [cg-g4-o1c-cutover-status.json](https://drive.google.com/file/d/1MUOtflDgZZDEgnZbO2Gvn78sB40pIsm_/view?usp=drivesdk)

## Supervisory retest procedure

The supervising ChatGPT conversation must first review this report and the scoped commit. A separately authorized operational step must reconcile the active fence to the exact commit, load the repaired code through the supported managed launcher, and verify one launcher/one watcher with a READY preflight. Only then may ChatGPT place one fresh canonical raw private Drive instruction using the allowlisted `cg-g4-o1b-instruction-*.json` filename, exact target HEAD `0e57164bd0eb4a8197e21294bcfb603ff6b67ea2`, `operation: codex_engineering`, and `execution.change_policy: report_only` with a fresh report path. The watcher must consume that original file once; the supervisor must inspect the resulting local JSON and private Drive result independently. No historical instruction may be reused, and bounded code-changing execution remains inactive.

## Residual gap

The fail-closed implementation and provider-free negative coverage are complete, but live supervisory retest is not complete: the unchanged active watcher is fenced against the pre-repair HEAD and is in `ERROR`. Reconciliation of that fence and a fresh ChatGPT-originated test are outside this tranche’s authorization.

**PARTIAL — ACCEPTANCE GAPS**
