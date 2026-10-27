# G4-O1D bridge-owned bounded commit implementation

Date: 2026-10-27 (Australia/Sydney)  
Fenced checkout: `gate3-cg406-remediation@7671932137312ad0ee0e22c351eccaeb5bdcf0ef`

## Disposition

Implemented and tested locally. **NOT ACTIVE. NOT COMMITTED.** No watcher,
launcher, fence, Git metadata, provider, source, Drive, GitHub, publication,
release or gate state was changed. The current checkout remains at the fenced
HEAD for a separately privileged host cutover.

## Exact diff

- `bridge/bridge.py`: ordinary `bounded_workspace` now uses the same host-owned
  exact-path commit seam as adoption; it requires unchanged worker HEAD,
  verifies the attested changed set, stages only those paths, verifies the
  staged-set delta, uses `git commit --only`, records bridge actor, exact paths,
  message, parent/new HEAD and staged-set evidence in `local_commit`, and
  rolls back only its own paths on staging, index inspection, process or commit
  failure. Adoption provenance validation remains a separate path.
- `src/charitygraph/bounded_authority.py`: added clean ordinary launch-path
  validation and post-worker regular-file/non-symlink commit-candidate
  attestation; duplicate allowlist paths are rejected.
- `tests/test_double_loop_harness.py`: disposable-repository coverage for
  bridge-owned success, worker index denial, unrelated staged preservation,
  pre-dirty/staged rejection, stale parent, directory/symlink rejection,
  adoption bridge commit and rollback paths.
- `tests/test_bridge_cutover.py`: disposable cutover coverage for exact
  ordinary bridge commit, duplicate/replay after a new exact fence, and the
  existing stale-fence/launcher constraints.
- This report is the only new report artifact.

`bridge/managed_launcher.py` was not changed: its existing rule already
requires a different exact active fence matching the current branch and HEAD
before a stopped child can reload.

## Verification

Provider-free command:

```text
$env:PYTHONPATH = "$PWD\src;$PWD"; pytest -q tests/test_double_loop_harness.py tests/test_bridge_cutover.py
```

54 tests were collected; the run completed without failures, with the
pre-existing opt-in real-CLI test skipped. `git diff --check` passed and the
checkout identity remained the fenced branch and HEAD above.

The tests use disposable repositories for all Git add/commit/reset operations.
No Git add, commit, reset or checkout was run in this actual checkout.

## Safety and bootstrap limitations

The worker-side HEAD-changing path is quarantined; only the host bridge may
create the one direct-child non-merge commit. Ordinary bounded paths must be
clean at launch, and worker changes must be allowlisted regular non-symlink
files. The bridge preserves unrelated staged/dirty/untracked state and never
uses broad add/reset operations. A failed or quarantined result remains
diagnostic and does not become semantic product acceptance.

This stage does not activate the route. A separately privileged host must
inspect the diff and result, perform the host cutover at the exact fenced
checkout, verify the resulting direct-child commit and preserved unrelated
state, and obtain a fresh immutable exact post-commit fence before any watcher
restoration. Pre-existing unrelated dirty and untracked paths in this checkout
were not modified.
