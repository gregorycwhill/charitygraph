# G4 P3c-B versioned SQLite rights projection rebuild

Date: 2026-10-27 (Australia/Sydney)
Result: **PARTIAL — bounded offline conformance complete; no Gate 4 or Product Owner acceptance**

## Control and scope

- Repository: `C:\CharityGraph-clean\charitygraph`
- Branch / fenced HEAD: `gate3-cg406-remediation` / `006f6350e813a255b504f16518830420ec3d3962`
- Fence: v36
- No provider, source acquisition, network, spend, production database, GitHub, commit, release, watcher or follow-on task was used.
- Existing dirty `runtime/catalog.py`, `source_rights.py`, Factory paths and unrelated work were preserved.

## Implementation

- Added numbered migration **v29** (`rebuildable_private_rights_projection`) with checksum, lifecycle checks, foreign keys, indexes and a database-enforced one-current-row key.
- Added `runtime/rights_governance_projection.py`. It rebuilds transactionally from the private `RightsGovernanceStore`, verifies record/event content addresses and event targets, uses deterministic current-frontier resolution, and stores only IDs, hashes and safe query metadata. Private bodies remain file-authoritative.
- Added provider-free projection tests. Provider transmission is never inferred; the fixture remains blocked because the committed source-rights module still lacks the exact provider-version authority.

Read-only byte comparison classified the pre-existing overlap as follows: clean HEAD `src/charitygraph/runtime/catalog.py` blob `5954ce82334bb4a00d0d20c697f66babca427e18`; dirty worktree blob `7691f24a8faa6d74895a42a3411ac1a6b0f80068`. HEAD migrations ended at v28; the worktree migration adds v29. The dirty catalog contains side-installed `artifact_rights_*` and diagnostics DDL in `_ensure_artifact_rights_tables()`. The v29 schema uses distinct `rights_projection_*` names, so this task did not edit or silently absorb the dirty catalog hook. Factory/provider integration remains out of scope.

## Verification

```text
python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3c-b-focused-20261027 tests/runtime/test_migrations.py tests/runtime/test_rights_governance_projection.py
10 passed

python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3c-b-regression-20261027 tests/runtime/test_migrations.py tests/runtime/test_rights_governance_projection.py tests/runtime/test_rights_governance_record.py tests/test_source_rights.py
60 passed

git diff --check
clean
```

Coverage includes v28→v29 upgrade/checksum and reopen, corruption/hash mismatch, missing event target, deterministic rebuild and idempotence, transactional rollback, lifecycle cross-binding/duplicate-current/cycle conflicts, expired/review-due/revoked omission, unsupported policy rejection, provider/public non-over-authorization, temporary-root SQLite, and uniqueness constraints.

## Limitations

This is a private, provider-free rebuildable projection only. It does not authorize provider transmission, replace `source_rights.py`, integrate Factory or P3c-A, remove the side-installed dirty catalog DDL, establish production migration readiness, publish data, or close Gate 4. No Product Owner acceptance is claimed. No private evidence, runtime database, cache or test artifact was added to the repository.
