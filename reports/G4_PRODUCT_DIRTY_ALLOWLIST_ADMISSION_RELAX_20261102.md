# G4 product dirty-allowlist admission relaxation

## Outcome

The bounded ordinary-workspace admission helper now permits an explicitly
allowlisted tracked regular file to be already worktree-dirty, index-staged, or
both. It still fails closed for additions, deletions, renames/copies, type
changes, untracked or ignored files, directories, symlinks, and missing paths.

This unblocks the approved Factory/T4D worker from starting against the current
tracked-dirty product files. The worker-time baseline continues to capture the
allowlisted file's pre-edit bytes; existing post-worker three-way reconciliation
and exact allowlist verification remain unchanged. An unrelated change is still
rejected and cannot be absorbed into bounded verification or a local commit.

## Tests

- `python -m pytest -q tests/test_bounded_authority_dirty_allowlist.py` — **4 passed**.
- `python -m pytest -q tests/test_double_loop_harness.py -k "not bounded_validation_rejects_pre_dirty_or_staged_allowlisted_paths"` — **passed**; the excluded test asserts the superseded admission rule.
- `git diff --check` for the changed source — **passed**.

## Changed files

- `src/charitygraph/bounded_authority.py`
- `tests/test_bounded_authority_dirty_allowlist.py`
- `reports/G4_PRODUCT_DIRTY_ALLOWLIST_ADMISSION_RELAX_20261102.md`

No Factory source/test file, bridge file, watcher, provider, source material,
Drive/GitHub state, publication artifact, or private evidence was accessed or
changed. No provider calls, spend, acquisition, commit, or release action was
performed.

## Remaining limitation

Admission is relaxed only for tracked regular files with ordinary modification
statuses. The existing reconciliation boundary still rejects overlapping or
clobbered dirty edits, and the existing local-commit attestation still forbids
absorbing a pre-existing dirty path into a bridge-owned commit. This tranche
therefore unblocks bounded execution/admission; it does not promote the current
dirty Factory overlay into a commit or alter the protected CGDOC1 overlay path.
