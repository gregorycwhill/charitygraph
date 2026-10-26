# G4 P3c/P4 provenance-bound adoption — bridge commit readiness

Date: 2026-10-26 (Australia/Sydney)  
Status: **WORKER READY — bridge-owned adoption commit**

## Scope and boundary

The bridge prelaunch validator owns raw source-result, ancestor, immutable
source/artifact-hash, untracked-status, and exact-allowlist verification. This
worker inspected only the six allowlisted artifacts below, did not access
Drive, providers, external sources, or unrelated runtime artifacts, and did
not run Git staging or commit operations. P3b2 remains quarantined and
excluded.

## Six-artifact local verification

All six paths remained regular files with Git status `??` before and after the
tests. Their post-test SHA-256 values match the bridge allowlist and the
pre-test values:

| path | SHA-256 |
|---|---|
| `src/charitygraph/runtime/rights_governance_record.py` | `e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9` |
| `tests/runtime/test_rights_governance_record.py` | `3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486706ab6c06f9ca310` |
| `reports/G4_P3C_CONTENT_ADDRESSED_RIGHTS_RECORD_AUTHORITY_20261026.md` | `cf990b61a80956d1b85ecec927d075a9b349ee029d2e62d71f3dea79d7ab838` |
| `src/charitygraph/phase5_run_diagnostics.py` | `9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372` |
| `tests/test_phase5_run_diagnostics.py` | `869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325` |
| `reports/G4_P3C_P4_RUN_DIAGNOSTICS_20261026.md` | `e9760a3cc60053f0e7f4a5e1f9c3fc0a20249178b2a7eb6fdc92663c4cd9f803` |

Current branch is `gate3-cg406-remediation` at HEAD
`fe8dbe0c7b83acd4270f97b1e5ab2c94b8f6cccb`.

## Provider-free verification

- Focused P3c/P4 suites: **20 passed** (`test_rights_governance_record.py`,
  `test_phase5_run_diagnostics.py`).
- Appropriate regression suites: **121 passed** (the focused suites plus
  standard transport, factory, governed integration/rights, source rights,
  and runtime task-state tests).
- Tests used `PYTHONDONTWRITEBYTECODE=1`, disabled pytest cache, and fresh
  basetemps under `C:\CharityGraph-runtime`.

## Bridge handoff

Worker-side readiness is **YES** for the v32 bridge to stage exactly these six
unchanged artifacts plus this fresh report and create its one direct-child,
non-merge local-only commit. No path was staged or committed by the worker;
unrelated dirty, staged, untracked files and prior failed adoption reports
remain protected. The bridge owns post-worker attestation and rollback.

This is not full product or semantic acceptance. P3c rights-policy,
subject/scope, SQLite projection/rebuild, and provider-bound revalidation gaps
remain open. P4 real ledger/run joining, valid accounting, and ambiguous
crossing evidence remain open. No publication, release, gate closure, fence
change, watcher/process action, spending, or follow-on dispatch occurred.
