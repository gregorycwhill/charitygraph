# CG-G4-P2 — governed Factory scope isolation

## Process completion

Complete for this bounded local task. The required v23 fence was independently read at:

`C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\cg-g4-o1b-dormant-state-fence-20261020-v23.json`

Its SHA-256 was `8d58d6acccaa5933075a1492e0974fc6a1080868d78b3e58532a351b5cb5c342`; it records `ACTIVE`, branch `gate3-cg406-remediation`, HEAD `21bb0e621f2a1c52f19b59f261d71009defa4843`, provider calls `0`, and no publication or gate closure. Branch and HEAD remained unchanged. HEAD tree was `f5851e02afab398326e145a34d142d9de5fe1a58`.

Read-only authority checks covered `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, the retained P1 archaeology, and the sibling Data repository's `DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, roadmap, implementation/test plans, integrated model, source/publication governance, taxonomy/scheme governance, coverage/economics policy and semantic-heuristic approvals. The archaeology's current P1 finding was reproduced: both Factory grouping paths omitted `scope_id`.

Pre-existing tracked modifications and untracked evidence/report paths were preserved. No pre-existing modification overlapped the task allowlist. No source acquisition, provider/API call, model call, Git staging/commit, bridge/watcher/process operation, external mutation, publication, schema migration or public-contract change occurred.

## Changes and bounded product acceptance

Product acceptance for the requested scope-isolation defect: **PASS for the provider-free bounded slice**.

- `FactoryPlan.packages()` and `physical_packages()` now include `scope_id` in compatibility keys. Deterministic ordering remains safe for both scoped and unscoped tasks.
- The unit regression proves same-subject/same-scope compatible tasks bundle, while different scopes and subjects remain separate in both logical and physical plans.
- The integrated regression uses durable synthetic records: source definition, acquisition receipt, source record, content-addressed raw and derived representations, derived-from lineage, evidence locator, governed references, preflight and the real `ReferenceFactory`/`SQLiteCatalog` path.
- Four accepted references produce two same-scope members in one physical attempt, one separate attempt for the second scope, and one separate attempt for the other subject. SQLite inspection found 3 physical attempts, 3 receipts, and every attempt's members had exactly one subject and one scope.
- Existing and strengthened tests retain differentiated `missing`, `blocked`, `structurally_invalid`, `not_applicable`, `not_processed`, `retrieval_failed`, `mismatched` and `unrecoverable` diagnostics. An accepted peer still lowers to exactly one task; non-ready references fabricate neither task nor evidence.
- Restart/reopen and rerun produced zero additional physical attempts, receipts or cost entries. The existing ambiguous `send_started` path remained held for explicit reconciliation and did not blind-resend.
- Synthetic accounting reconciled 3 actual entries plus 3 release entries, `AUD 0.006000` actual spend, `AUD 0.000000` outstanding reserve, and no budget breach. This is not paid-provider billing or canonical coverage production evidence.

## Verification

Commands were run with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `PYTHONPATH=src`, and pytest bases outside the checkout under `C:\CharityGraph-runtime`.

- Baseline exact command: `$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p2-scope-isolation-baseline tests/test_phase5_preflight.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py tests/runtime/test_source_evidence.py tests/runtime/test_budget_ledger.py` — **35 passed**.
- Final exact command: `$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p2-scope-isolation-final tests/test_phase5_preflight.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py tests/runtime/test_source_evidence.py tests/runtime/test_budget_ledger.py` — **37 passed in 6.24s**.
- Additional exact command: `$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p2-scope-isolation-additional tests/test_phase5_batch_bytes_and_attempts.py tests/test_phase5_delivery.py tests/runtime/test_task_state.py tests/runtime/test_cache_and_artifacts.py` — **31 passed in 3.31s**.
- Baseline focused command over preflight, Factory, governed integration, source-evidence and budget-ledger tests: **35 passed**.
- First changed run: **1 failed, 36 passed**; the test expectation incorrectly counted 3 ledger rows instead of the correct 6 actual/release rows.
- Corrected rerun: **1 failed, 36 passed**; the test used `outstanding_reserved_exposure` instead of the existing `_aud` field.
- The changed-run failure output was respectively `assert cost_count == 3` with actual `6`, then `AttributeError: 'BudgetPosition' object has no attribute 'outstanding_reserved_exposure'`; both were test assertions corrected within the allowlist, not product defects.
- `git diff --check`: no whitespace errors; Git emitted only existing line-ending warnings for dirty files.

Pre/post control commands included `git status --porcelain=v1 -uall`, `git branch --show-current`, `git rev-parse HEAD`, `git rev-parse 'HEAD^{tree}'`, `git diff --check` and direct SHA-256 hashing of each changed source/test file. No genuine global stop was observed.

Final SHA-256 values:

```text
dc7f335873789c31f016351c9dccd20f04f7ed002689d0e6dd36b981ab100dfe  src/charitygraph/phase5_factory.py
ef7498153ef1d13b55bfd052c6c6f5aac3e88e85ccc6aeba62b4ba8cca0d1828  tests/test_phase5_factory.py
2912b5813743b8da6f8bced353559f4209896c8f3339952e5b2d866943f192e0  tests/test_phase5_governed_factory_integration.py
```

Only the allowlisted source, two test files and this report were changed by this task. The SQLite databases and pytest temporary state were outside the checkout. No raw/private evidence, prompts, model responses, credentials, caches or runtime state were added to Git.

The final read-only audit observed older ignored `.pytest_cache`, `__pycache__` and runtime SQLite material already present inside the checkout; these were not created or modified by this task and were left untouched.

## Residual limitations

The existing physical-attempt schema stores subject identity and task-member lineage but not a dedicated `scope_id` column; this task intentionally makes no schema or catalog migration. Scope isolation is enforced and verified through the scoped task members and packaging identity. Provider billing, real model execution, canonical coverage, artifact-bound rights-policy resolution, source acquisition and publication remain outside this provider-free rehearsal.
