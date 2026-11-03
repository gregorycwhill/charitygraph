# G4-O1C provenance-bound adoption recertification

Date: 2026-10-26  
Target HEAD: `1e3e4b8f36ca8b4591a786e6cda1f0ff56265ece`

## Result

Recertified at the target HEAD. The focused harness run completed with **24 passed, 1 skipped** (`PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider tests/test_double_loop_harness.py`). The skip is the existing platform-dependent symlink case.

## Adoption preflight requirements

- The instruction must use `codex_exec`, `provenance_bound_adoption`, the approved authority envelope, the `luna-high` model, the fixed implementation authority/scope, `local_commit_only`, a fresh `reports/` report path, and an exact relative allowlist.
- `adopted_artifacts` must be non-empty; each item must contain only the exact path, lowercase SHA-256, completed source instruction ID, source result filename, and source-result SHA-256.
- The allowlist must contain exactly the adopted artifact paths plus the fresh report path; paths must be unique, relative, and free of traversal or symlink escape.
- Before launch, each artifact must still be an untracked regular file with the declared hash. Its pinned result must be valid JSON with the expected schema, matching instruction ID, `CODEX_ENGINEERING_COMPLETED`, verified and non-quarantined workspace attestation, the current starting HEAD, and evidence that the artifact was newly created with the same hash.
- Post-run adoption requires one non-merge direct-child local commit containing every adopted path, no non-allowlisted path, and no pre-existing dirty path. Unrelated dirty paths remain protected.

## Protected exclusions

No provider or external-source access, spending, Drive or GitHub mutation, publication, merge, release, gate closure, watcher/process management, historical reset/checkout/deletion, or follow-on dispatch is permitted. Reports are diagnostic evidence, not product acceptance. Existing dirty and untracked paths in this checkout were not changed, staged, committed, or absorbed.

## Route use

**Code-changing route used: no.** This recertification used inspection and the read-only/report-only harness test run; no bounded implementation or provenance-bound adoption execution was dispatched, and no code, test, configuration, process, or commit change was made.
