# G4-O1C Git-write-boundary recertification — 2026-10-26

Disposition: **FAIL CLOSED — one rollback branch remains unrecertified**

## Scope and identity

Read-only inspection of `bridge/SUPERVISOR_PROTOCOL.md`, `bridge/bridge.py`,
`src/charitygraph/bounded_authority.py`, and
`tests/test_double_loop_harness.py` at:

```text
workspace  C:\CharityGraph-clean\charitygraph
branch     gate3-cg406-remediation
target     1e814af170dcc32d4e09c5b4d74d571c1d143d88
```

The three named verification files are byte-identical to target HEAD. Tests
and live preflight were not run because both can write runtime/status or
temporary artifacts. Only this report was written; no product, harness,
configuration, process, provider, Drive, GitHub, publication, release, gate,
staging, or commit change was made.

## Findings

- **Worker boundary: PASS (static).** The bridge launches Codex with
  `--sandbox workspace-write` (`bridge/bridge.py:899-916`). For adoption, Git
  metadata operations are kept in the bridge-owned post-worker path; the
  protocol explicitly excludes worker `.git` writes (`SUPERVISOR_PROTOCOL.md:50-58`).
- **Provenance and attestation: PASS.** Before launch, the validator requires
  exact adopted/report allowlisting, current `??` regular-file status and
  hashes, completed verified non-quarantined source results, matching source
  instructions, and ancestor history (`bridge/bridge.py:698-810`). The bridge
  only enters its adoption commit path after successful workspace attestation,
  a successful worker, unchanged HEAD, and a report (`bridge/bridge.py:1051-1085`).
- **Exact-path commit and staged-path preservation: PASS.** The bridge checks
  for pre-staged adoption paths, adds only the validated paths, and uses
  `git commit --only ... -- <paths>` (`bridge/bridge.py:812-855`). The harness
  asserts that an independently staged `unrelated.txt` remains staged
  (`tests/test_double_loop_harness.py:680-723`).
- **Rollback: PARTIAL / required repair gap.** Omitted staged paths and commit
  failure call `_unstage_adoption_paths` (`bridge/bridge.py:835-850`), and the
  harness covers commit-failure rollback (`tests/test_double_loop_harness.py:726-771`).
  However, a nonzero `git add` return at `bridge/bridge.py:833-834` raises
  immediately without calling `_unstage_adoption_paths`. A partially completed
  `git add` could therefore leave bridge-owned paths staged, contrary to the
  protocol’s all-staging-failures rollback requirement. No harness case covers
  this branch.
- **Six P3c/P4 artifacts in preflight: PASS (static/read-only).** Preflight
  reads the fence and current branch/HEAD, then candidate discovery is limited
  to instruction filenames; it contains no `git add` or `git commit`
  (`bridge/bridge.py:537-547, 1184-1292`). The current index is empty and all
  six artifacts remain untracked (`??`), with these current SHA-256 values:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/runtime/rights_governance_record.py` | `e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9` |
| `tests/runtime/test_rights_governance_record.py` | `3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486ab6c06f9ca310` |
| `reports/G4_P3C_CONTENT_ADDRESSED_RIGHTS_RECORD_AUTHORITY_20261026.md` | `cf990b61a80956d1b85ecec927d075a9b349ee029d2e62d71f3dea79d7ab838` |
| `src/charitygraph/phase5_run_diagnostics.py` | `9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372` |
| `tests/test_phase5_run_diagnostics.py` | `869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325` |
| `reports/G4_P3C_P4_RUN_DIAGNOSTICS_20261026.md` | `e9760a3cc60053f0e7f4a5e1f9c3fc0a20249178b2a7eb6fdc92663c4cd9f803` |

The six files were not staged or committed by this task. The direct
`git add`-failure rollback gap must be repaired and separately recertified
before this boundary can be marked PASS.
