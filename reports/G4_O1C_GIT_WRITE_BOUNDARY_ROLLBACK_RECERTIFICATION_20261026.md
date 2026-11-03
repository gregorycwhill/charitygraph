# G4-O1C Git-write-boundary rollback recertification — 2026-10-26

Disposition: **PASS — corrected rollback repair recertified**

## Target and scope

- Branch: `gate3-cg406-remediation`
- Target HEAD: `fe8dbe0c7b83acd4270f97b1e5ab2c94b8f6cccb`
- Inspected: `bridge/bridge.py` and `tests/test_double_loop_harness.py`
- Verification was local and read-only; no product, harness, configuration,
  process, provider, Drive, GitHub, publication, release, gate, staging, or
  commit change was made. This report is the only file written.

## Findings

- **Exact rollback: PASS.** In `_bridge_owned_adoption_commit`, every nonzero
  `git add` result and every nonzero `git commit` result calls
  `_unstage_adoption_paths` before raising `DirtyBaselineViolation`. The
  rollback command is `git reset -- <sorted validated adoption paths>` only;
  it does not reset unrelated paths. The missing-path guard uses the same
  rollback.
- **Staged-work boundary: PASS.** The bridge rejects adoption paths that were
  already staged, stages only the validated paths, and invokes
  `git commit --only ... -- <paths>`. The harness success case confirms an
  independently staged `unrelated.txt` remains staged.
- **Fail-closed: PASS.** Bridge commit/rollback failures become an attestation
  error, set `quarantined` true and `verified` false, and terminate as
  `CODEX_EXECUTION_FAILED_COMMIT`.
- **Harness: PASS.** `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
  -p no:cacheprovider tests/test_double_loop_harness.py` completed with 28
  passed and 1 skipped (the existing platform-dependent symlink case).
  Relevant tests cover successful exact-path adoption, nonzero commit
  rollback, and partial nonzero-add rollback.

## Six P3c/P4 artifacts

The index was empty and all six remained untracked (`??`):

1. `src/charitygraph/runtime/rights_governance_record.py`
2. `tests/runtime/test_rights_governance_record.py`
3. `reports/G4_P3C_CONTENT_ADDRESSED_RIGHTS_RECORD_AUTHORITY_20261026.md`
4. `src/charitygraph/phase5_run_diagnostics.py`
5. `tests/test_phase5_run_diagnostics.py`
6. `reports/G4_P3C_P4_RUN_DIAGNOSTICS_20261026.md`

`bridge/bridge.py` and `tests/test_double_loop_harness.py` are byte-identical
to target HEAD. Existing unrelated worktree changes were preserved.
