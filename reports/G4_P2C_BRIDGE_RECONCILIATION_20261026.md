# G4-P2c bridge reconciliation

Date: 2026-10-26 (Australia/Sydney)  
Mode: provider-free, read-only reconciliation

## Disposition

The bounded P2c implementation outcome is independently supported by the
focused local contract tests. The bridge execution itself remains quarantined:
the result is not a successful execution attestation, and this report does not
close Gate 4 or confer broader operational acceptance.

## Evidence

- Result: `runtime/g4-o1b-controlled-cutover-20261020/bridge/results/gate4_engineering_20261025-g4-p2c-catalog-identity-hardening-v1.json`.
- Result state is `CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES`, with
  `quarantined: true`, `verified: false`, `local_commit: null`, and
  `unexpected_paths: []`.
- The recorded `baseline_error` explains the quarantine: the pre-existing dirty
  baseline for `src/charitygraph/runtime/catalog.py` and
  `tests/runtime/test_task_state.py` changed. The result's `changed_paths` are
  exactly the three allowed P2c paths: those two files and the P2c engineering
  report.
- Before hashes recorded by the result match the P2c report's pre-edit hashes:
  `catalog.py` `7e1bd2d1...49c4020` and `test_task_state.py`
  `5804053f...c8e42f`.
- Current hashes match both the result's after hashes and the P2c report's
  final hashes: `catalog.py` `f0e2b9e1...98c6ace`,
  `test_task_state.py` `fa85b7fd...5683b7`, and the P2c report
  `7f38f9bd...60008`. There is no later local drift on the P2c paths.
- `git diff` shows the expected substantive implementation/test changes
  (78/9 lines in `catalog.py`, 241/2 in `test_task_state.py`); the same result
  appears with `--ignore-space-at-eol`, so the difference is not merely line
  endings. `git diff --check` passed.

## Implementation and test review

The reviewed change hardens `prepare_physical_attempt` against duplicate
members, run/subject/scope mismatches, and immutable re-entry drift. The
replacement path validates the old member graph before insertion, preserves
run/subject/members, requires same-mode/same-run replacement identity and a
distinct reservation, preflights collisions, and validates replay identity.

The narrowly relevant provider-free rerun was:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src pytest -p no:cacheprovider \
  --basetemp C:\CharityGraph-runtime\g4-p2c-reconciliation-20261026 \
  tests/runtime/test_task_state.py
10 passed in 4.92s
```

This independently supports the bounded local implementation outcome. It does
not establish production concurrency, provider-boundary behaviour, a clean
baseline, broad historical audit, or Gate 4 acceptance. No providers, network,
source acquisition, spending, publication, GitHub, Drive, watcher, staging,
commit, reset, checkout, or existing-file mutation was performed; only this
reconciliation report was written.
