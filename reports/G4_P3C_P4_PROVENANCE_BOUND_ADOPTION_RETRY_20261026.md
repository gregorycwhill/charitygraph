# G4 P3c/P4 provenance-bound adoption retry — 2026-10-26

Status: **FAIL CLOSED — adoption not staged or committed**

## Authority and boundary

The bridge's mandatory `provenance_bound_adoption` PRELAUNCH VALIDATOR is
the provenance authority for this correction. It verified the exact raw
source-result files in its configured Drive-synced `artifacts_root`, matching
instruction/result identities and hashes, completed non-quarantined source
attestations, ancestor history, untracked status, and the exact six artifact
hashes before this worker started. This worker therefore did not impose a
second requirement for those source-result files under
`C:\CharityGraph-runtime\artifacts`, and did not access providers, Drive, or
external sources.

The six files below were rechecked locally as `??` files and remained
byte-for-byte unchanged. P3b2 was not adopted, the earlier no-commit report
was preserved, and no product implementation was edited.

| path | SHA-256 |
|---|---|
| `src/charitygraph/runtime/rights_governance_record.py` | `e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9` |
| `tests/runtime/test_rights_governance_record.py` | `3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486706ab6c06f9ca310` |
| `reports/G4_P3C_CONTENT_ADDRESSED_RIGHTS_RECORD_AUTHORITY_20261026.md` | `cf990b61a80956d1b85ecec927d075a9b349ee029d2e62d71f3dea79d7ab838c` |
| `src/charitygraph/phase5_run_diagnostics.py` | `9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372` |
| `tests/test_phase5_run_diagnostics.py` | `869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325` |
| `reports/G4_P3C_P4_RUN_DIAGNOSTICS_20261026.md` | `e9760a3cc60053f0e7f4a5e1f9c3fc0a20249178b2a7eb6fdc92663c4cd9f803` |

## Verification and blocker

- Focused provider-free tests: `20 passed` — the rights-record and run-diagnostics suites.
- Related provider-free regression tests: `101 passed` — standard transport, factory, governed integration/rights, source rights, and task state.
- The exact seven-path `git add --` attempt was rejected before index mutation because Git could not create `.git/index.lock` (`Permission denied`). No path is staged.
- No local commit was created. The `.git` metadata is ACL-protected against writes for this session; no stale lock or Git process was found. This is a real local authorization contradiction, so the task fails closed rather than bypassing Git metadata protections.
- All unrelated tracked modifications and untracked evidence/reports remain outside the index and unchanged.

## Remaining PARTIAL P3c/P4 gaps

P3c still needs an approved durable rights-record authority, migration/rebuild
semantics, exact current-decision uniqueness, and provider-boundary
revalidation. P4 remains an offline synthetic diagnostic/projection seam: it
does not yet prove real run/ledger joins, complete accounting compatibility,
provider receipts or ambiguity/restart evidence, or an approved industrial
pilot. These gaps do not authorize source-family expansion, P3b2 adoption,
publication, or Gate 4 closure.
