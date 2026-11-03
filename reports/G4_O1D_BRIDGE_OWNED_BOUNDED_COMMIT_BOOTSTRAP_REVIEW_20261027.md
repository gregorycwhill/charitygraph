# G4-O1D bridge-owned bounded commit bootstrap review

Date: 2026-10-27 (Australia/Sydney)  
Inspection target: `gate3-cg406-remediation` at `7671932137312ad0ee0e22c351eccaeb5bdcf0ef`  
Disposition: **NO-GO for bootstrap on the current live route**

## Finding

The current bridge can attest an ordinary `bounded_workspace` edit to clean
tracked files, but it cannot safely commit and activate that edit when the
worker cannot create `.git/index.lock`. The ordinary path in `bridge/bridge.py`
only calls `verify_local_commit` when the worker has already changed HEAD
(lines 1038-1048); otherwise it uses worktree attestation. There is no
bridge-owned commit branch for `bounded_workspace`. A worker-side `git commit`
therefore fails at the denied index write, while a successful no-commit worker
run leaves an attested dirty bridge but no durable activation.

The existing `provenance_bound_adoption` route is not a bootstrap transport for
this purpose. Its validator requires each adopted path to be the exact,
currently untracked, non-symlink regular file and to be proven by a completed
ancestor run (`bridge/bridge.py:697-810`; `bounded_authority.py:212-232`). A
tracked `bridge/bridge.py`, `bounded_authority.py`, launcher, or test file
cannot satisfy that precondition. Copying to an alternate untracked path would
commit the wrong path; copying back would be an unallowlisted mutation.
Symlink substitution, auto-replay, and broad copy are therefore rejected.

## Mechanisms already implemented

- Exact authority, target identity, version, scope, relative allowlist and
  `local_commit_only` validation are present (`bridge/bridge.py:583-695`).
- Worktree snapshots preserve unrelated dirty/staged/untracked state and use
  exact path comparison, three-way dirty-file reconciliation, and symlink/path
  escape rejection (`bounded_authority.py:110-168,241-360`).
- Local-commit attestation requires one non-merge direct child, exactly one
  commit, allowlisted paths only, no pre-existing dirty path absorption, no
  symlink, and every adopted artifact committed (`bounded_authority.py:363-413`).
- Adoption-only bridge commit stages exact paths, uses `commit --only`, rejects
  pre-staged adoption paths, and rolls back only its own exact-path staging on
  failure (`bridge/bridge.py:811-869`). The harness covers these adoption
  boundaries, including unrelated staged work and partial staging rollback.
- The launcher accepts a new child only after a different exact active fence
  matches workspace, branch and HEAD (`managed_launcher.py:42-67,153-163`). The
  supervisor protocol requires a new immutable post-commit fence before any
  watcher restoration. The latest baseline report records the live index-lock
  failure and an otherwise empty index; that failure was not retried.

## Required staged repair design

This needs an explicit host-authority bootstrap, outside the denied worker
index write, before ordinary bounded commits are enabled:

1. A fresh immutable engineering instruction must target the verified current
   branch/HEAD and exact paths only. The worker may edit and test the proposed
   bridge machinery and write the fresh report, but must be instructed not to
   use Git metadata. The current bridge must first attest that HEAD and branch
   are unchanged and that only the allowlist changed.
2. A separately approved host/bridge cutover must then stage and commit the
   exact allowlist. Generalise the adoption helper into an
   `_bridge_owned_exact_path_commit` used by `bounded_workspace`, while
   retaining adoption provenance as an additional requirement only for the
   adoption policy. For ordinary bounded commits, reject any allowlisted path
   already dirty or staged at launch, require regular non-symlink files, stage
   only exact paths, verify the staged set, use `git commit --only`, and reset
   only those paths on any staging/commit failure. Failure, including an index
   lock denial, is terminal and quarantined; it must not replay.
3. Re-attest the resulting HEAD with the existing direct-child verifier. Record
   the actor, exact staged paths, commit message, commit HEAD and pre/post
   identity in `workspace_attestation.local_commit`. Do not accept a report as
   product acceptance.
4. Stop the old child normally. The supervisor creates a new immutable fence
   from the prior template with incremented version, `supersedes`, exact new
   HEAD, branch and implementation revision. The launcher remains idle until
   that different fence is observed and exact; a stale fence cannot reload the
   bridge. Independent recertification must inspect the diff, result, fence,
   status and dirty-path preservation before another instruction.

The minimum implementation paths are `bridge/bridge.py` and
`src/charitygraph/bounded_authority.py`; the minimum harness additions are
`tests/test_double_loop_harness.py` plus fence/reload assertions in
`tests/test_bridge_cutover.py`. Update `bridge/SUPERVISOR_PROTOCOL.md` only if
the final authority shape changes. `bridge/managed_launcher.py` needs no
semantic change if it keeps the existing different-exact-fence rule.

## Required tests (disposable repositories only)

Positive cases: ordinary bounded worker edits clean tracked bridge files and a
fresh report without worker Git access; host exact-path commit succeeds as one
direct child; unrelated staged and dirty paths remain byte-identical; the
result records the bridge actor and commit; a newer exact fence permits one
reload.

Adversarial cases: worker attempts Git/index access; stale target or fence;
pre-staged or pre-dirty allowlisted path; unallowlisted edit, deletion,
rename, directory, symlink or path escape; partial `add`; commit/index-lock
failure; non-direct-child or merge commit; missing allowlisted change;
duplicate/replayed instruction; old fence, wrong HEAD/branch, or active claim.
Each failure must leave unrelated state untouched, quarantine the result, and
permit no automatic replay or reload.

## Minimum next instruction

**Do not dispatch ordinary `bounded_workspace` yet.** First obtain explicit
host-authority approval for the staged bootstrap above, with a fresh immutable
`charitygraph.autonomous-instruction/v1` transport and an exact allowlist for
the two implementation files, the two test files, and one fresh report. The
bootstrap result must be independently recertified and fenced at its new
direct-child HEAD before any normal bounded commit is attempted.

This review changed no code, tests, Git index/commit, permissions, watcher,
launcher, fence, registry or external state, and ran no checkout-mutating
tests. Existing dirty, untracked and historical material remains protected.
