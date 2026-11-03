# G4-P2c physical-attempt identity hardening

Date: 2026-10-25 (Australia/Sydney)  
Mode: provider-free local engineering task  
Self-assessment: **PASS for the bounded implementation and tests; PARTIAL for broader operational acceptance.** This does not close Gate 4 or confer independent acceptance.

## Control and preservation

- Workspace: `C:\CharityGraph-clean\charitygraph`
- Branch: `gate3-cg406-remediation`
- HEAD: `21bb0e621f2a1c52f19b59f261d71009defa4843`
- HEAD tree: `f5851e02afab398326e145a34d142d9de5fe1a58`
- Retained v23 fence evidence: `ACTIVE`, version `23`, SHA-256 `8d58d6acccaa5933075a1492e0974fc6a1080868d78b3e58532a351b5cb5c342`; provider calls `0`, GitHub mutation `false`, publication `false`, gate closure `false`.
- The required report was absent before this task.
- Pre-edit hashes matched the task authority: `catalog.py` `7e1bd2d19732102f9840a6c7ce1a55c95042ef4d88b874cd3a6ef43aa49c4020`; `test_task_state.py` `5804053f05619604896ace5f0149c2442c46dfdbaa3491811dc1a60844c8e42f`.
- Existing dirty and untracked paths were preserved. Git emitted the known permission warnings for the 80 synthetic pytest bridge-recovery identities; no broad status cleanup, staging, commit, reset, checkout, or GitHub action was used.

## Bounded change

Code archaeology found two actual physical-attempt insert paths: direct preparation and the append-only pre-send replacement copier. The change is limited to `src/charitygraph/runtime/catalog.py` and `tests/runtime/test_task_state.py`.

`prepare_physical_attempt` now:

- rejects duplicate member IDs before writes;
- validates one run, one subject, and one task scope, with null/null allowed and null/non-null rejected;
- validates persisted members on reentry, including historical mixed scope;
- treats run, subject, delivery mode, provider request ID, reservation ID, and supplied provider-batch ID as immutable reentry identity and raises `ConflictError` on drift;
- retains order-independent same-member idempotent retry.

The replacement path now validates the old persisted member graph before copying, rejects historical run/subject/scope corruption, preserves the original run/subject/member set, requires a same-mode same-run replacement job and distinct replacement reservation, preflights execution-ID collisions, and validates all durable replacement identity on replay. Existing reservation replacement and provider-batch binding remain explicit lifecycle operations; they are not implicit reentry mutation.

All validation remains before the first replacement insert inside the existing `BEGIN IMMEDIATE` transaction. No migration or schema change was added. Historical invalid rows are not rewritten; they fail closed with explicit repair-required evidence.

## Evidence and tests

Baseline before the implementation: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`, `pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p2c-baseline-20261025 tests/runtime/test_task_state.py` — **6 passed**.

Final focused command: `... --basetemp C:\CharityGraph-runtime\g4-p2c-final-targeted-20261025 tests/runtime/test_task_state.py` — **10 passed**.

Final related provider-free command over the governed factory, FactoryPlan/ReferenceFactory integration, batch, replacement, S0 attempt/locator, delivery, and mandate suites, with basetemp `C:\CharityGraph-runtime\g4-p2c-final-related-20261025` — **92 passed**.

The focused SQLite tests exercise public catalogue entrypoints and actual file-backed SQLite persistence. They cover same-scope replacement, null/null and null/scoped preparation, cross-run/subject rejection, changed immutable reentry arguments, idempotent retry, duplicate members, historical mixed-scope rejection in both paths, and unchanged counts for `physical_attempts`, `physical_attempt_members`, `provider_receipts`, `cost_entries`, `budget_reservations`, `provider_request_attempts`, and `provider_pre_send_replacements` on failure.

One separate attempted command including `tests/test_standard_delivery_job.py` stopped at collection because that file imports `tests.test_phase5_standard_transport` while the mandated `PYTHONPATH=src` does not expose `tests` as an importable package. No test body ran from that command; the applicable lifecycle files passed in the 92-test command.

`git diff --check` passed, with only pre-existing line-ending warnings on unrelated dirty files. Final allowlisted hashes were:

```text
f0e2b9e190111e39129a1ad47f9750a85d1ce73e9d311c7d85e412a7b98c6ace  src/charitygraph/runtime/catalog.py
fa85b7fdf949e58a0e0819634e97d1265e27e97a90ac4ca867874ab6ab5683b7  tests/runtime/test_task_state.py
```

## Limits

No provider, model, spend, source, Drive setting, watcher, bridge, publication, release, GitHub, or external-source action was used. The local tests do not establish production concurrency, provider crossing, broad historical catalogue audit, or Gate 4 closure. The implementation deliberately leaves existing invalid historical rows in place and only prevents their reuse or propagation.
