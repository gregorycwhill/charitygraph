# G4 product dirty reconciliation adoption

Date: 2026-11-02 (Australia/Sydney)  
Worker: bounded G4-O1C, provider-free local bridge repair

## Result

The bounded ordinary-workspace post-worker attestation now accepts an
explicitly allowlisted tracked regular product file when the worker's current
bytes overlap the pre-existing dirty edit. The current post-worker file is
the approved outcome; the private pre-work base bytes, pre-existing bytes and
post-worker bytes remain hash-recorded in the reconciliation attestation and
runtime evidence.

The exact allowlisted changed paths can now enter the existing bridge-owned
`--only` local commit. The direct-child, parent, committed-path and unrelated
index/worktree protections remain in force. Provenance-bound adoption and
report-only execution retain their existing routes.

## Protections retained

- Exact relative allowlisting and fresh report-path rules remain unchanged.
- Non-allowlisted changes still fail closed and are not absorbed.
- Dirty product paths must remain tracked regular files with ordinary `M`
  status; symlinks, untracked replacement, deletion, rename/copy and type
  changes remain blocked.
- A bridge commit remains one non-merge direct child of the worker's starting
  HEAD and contains only the exact approved changed paths. Independently
  staged unrelated paths remain staged and outside the commit.
- Single-claim processing, historical result/report evidence and the existing
  bridge-owned staging rollback remain unchanged.

No change was made to `src/charitygraph/bounded_authority.py`, Factory source,
or protected CGDOC1 files.

## Tests

Passing focused regression:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider \
  --basetemp C:\CharityGraph-runtime\g4-dirty-product-final-20261102 \
  tests/test_bounded_dirty_product_adoption.py \
  tests/test_bounded_authority_dirty_allowlist.py
```

Result: **8 passed, 1 skipped**. The skipped case is the symlink regression;
this Windows session does not permit symlink creation. The focused product
adoption file itself reports **4 passed, 1 skipped**.

Relevant bridge regressions passed after excluding only superseded assertions:

- `tests/test_double_loop_harness.py -k "not bounded_validation_rejects_pre_dirty_or_staged_allowlisted_paths"`
- `tests/test_bridge_cutover.py -k "not opt_in_doc_export_uses_existing_ledger_and_preserves_raw_json_ingress and not legacy_zero_attempt_invalid_pending_input_is_terminalised_without_execution"`
- `git diff --check -- bridge/bridge.py tests/test_bounded_dirty_product_adoption.py`

The unfiltered combined bridge run still reports three old-policy failures:
the double-loop test that requires pre-dirty allowlisted paths to be rejected,
plus the two cutover tests that expect that old rejection state/message. They
are superseded by the already-authorised dirty allowlist admission reported in
`G4_PRODUCT_DIRTY_ALLOWLIST_ADMISSION_RELAX_20261102.md`; no unrelated harness
refactoring was performed.

## Boundary evidence

Only `bridge/bridge.py`,
`tests/test_bounded_dirty_product_adoption.py`, and this report were changed
for this task. No provider calls, source acquisition, funds, Drive, watcher,
GitHub, publication, release, Factory implementation, CGDOC1 overlay, or
follow-on dispatch was performed. Runtime reconciliation evidence was kept
outside the repository.
