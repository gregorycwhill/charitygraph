# G4 T4E clean-worktree adoption route

Date: 2026-10-31 (Australia/Sydney)  
Task: report-only reconnaissance; no tests, Git writes, provider calls, or
process/bridge actions performed.

## Answer

There is no protocol-safe adoption path in the current checkout. The exact
T4E bytes are present at the supplied hashes, but both paths are already
tracked and dirty, and the source execution was a timeout rather than
`CODEX_ENGINEERING_COMPLETED`. The current `provenance_bound_adoption` route
therefore must reject them before worker start. A direct-child commit cannot
simultaneously contain those two path changes and not absorb a pre-existing
dirty tracked path; the current protocol correctly refuses that contradiction.

## Observed pre-state

- Repository identity: branch `gate3-cg406-remediation`, HEAD
  `d41fd766e8e5d9c1f9e63d17b30350c956bbcfc2`.
- Current fence: v69, SHA-256
  `1280b4ad04f68535aca6e363002b371c61138befc8c1cf4d2413787a19daaf00`.
- The read-only status observation had 347 entries, no staged paths, and these
  two target paths as ` M`:
  `src/charitygraph/phase5_t4d_e3_factory_handoff.py` and
  `tests/test_phase5_t4d_e3_factory_handoff.py`.
- Current target hashes are respectively
  `e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8` and
  `38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7`.
  These are the source and final-test hashes in the prior reconciliation
  report (`reports/G4_T4E_TIMEOUT_DIRTY_OVERLAY_INDEPENDENT_RECONCILIATION_20261031.md:17-29`).

## What the bridge actually permits

1. Fence and target binding are exact: the launcher accepts only a fence whose
   workspace path, branch and HEAD match the checkout
   (`bridge/managed_launcher.py:51-80`); the watcher repeats those checks
   (`bridge/bridge.py:488-500`). Bounded admission also requires the target
   workspace, branch and full HEAD to match the captured workspace
   (`src/charitygraph/bounded_authority.py:197-212`).
2. Ordinary bounded commits reject any pre-dirty or staged allowlisted path
   (`src/charitygraph/bounded_authority.py:278-308`).
3. Adoption is narrower, not an exemption: the candidate must be an untracked
   regular file whose hash is still present, and its immutable source result
   must be completed, verified, non-quarantined, hash-consistent, and on an
   ancestor of the target HEAD (`bridge/bridge.py:732-845`). The protocol
   explicitly rejects tracked, altered, failed, missing or unrelated artifacts
   (`bridge/SUPERVISOR_PROTOCOL.md:50-58`). T4E meets none of the tracked-file
   and completed-source-result prerequisites.
4. When eligible, the bridge stages exact paths, verifies the staged set,
   commits with `git commit --only`, checks the parent is the captured HEAD,
   and rolls back only its own exact-path staging on failure
   (`bridge/bridge.py:847-953`). Local attestation then requires one
   non-merge direct child, every committed path allowlisted, and no pre-existing
   dirty path committed (`src/charitygraph/bounded_authority.py:461-511`).
5. Existing tests cover preclaim rejection, ancestor binding, preservation of
   unrelated staged work, exact-path commit, and staging rollback
   (`tests/test_double_loop_harness.py:707-929`). The worker-index test only
   denies worker Git metadata access via `GIT_INDEX_FILE`
   (`tests/test_double_loop_harness.py:610-660`). There is no implementation
   or test for `git worktree`, `GIT_INDEX_FILE` isolation by the host, or a
   reset/reapply transaction in the bridge source/tests.

## Route decision

- A separate clean worktree is not usable by the current protocol merely by
  creating it: the supported launcher is fixed to the configured workspace
  (`bridge/README.md:8-24`), and exact workspace/branch/HEAD identity is part
  of admission. A detached worktree commit would not advance the configured
  branch; checking out the same branch in a second worktree is itself outside
  the implemented launcher/adapter route. The main dirty checkout must remain
  untouched.
- A preclaim snapshot/reset/reapply route does not exist. More importantly,
  the protocol says a dirty file can never be absorbed into a local commit;
  only a clean three-way reconciliation may prove preservation
  (`bridge/SUPERVISOR_PROTOCOL.md:60-70`). Resetting or reapplying the two
  tracked paths would introduce a new destructive Git transaction and would
  change that invariant. It must not be improvised here.

## Smallest controlled successor design

The least expansive safe option is a new, separately authorised bridge route
that operates on a supervisor-provisioned clean target workspace at the exact
source HEAD. It must not replay the timed-out instruction or use another
worker. Before eligibility, the target must have: the exact repository and
branch; source HEAD as an ancestor/current target HEAD as explicitly bound; no
staged, modified, deleted, renamed, ignored or untracked paths; and a fresh
immutable source/evidence record that the bridge accepts as provenance for
exactly the two hashes above. The exact allowlist must be only:

```
src/charitygraph/phase5_t4d_e3_factory_handoff.py
tests/test_phase5_t4d_e3_factory_handoff.py
reports/<fresh-successor-report>.md
```

The bridge change must add a clean-target transaction (or an equivalent
host-owned isolated-index implementation) that: verifies those preconditions;
constructs one tree containing only the two approved blobs plus the report;
CAS-checks the original HEAD; creates one direct-child local commit; preserves
the dirty main checkout and its index; and re-runs the existing path, parent,
allowlist, and no-merge attestations. Tests must cover stale HEAD, dirty
clean-target rejection, mismatched blob/hash, unexpected path, preserved
main-checkout dirty/index state, exact direct-child identity, and failure
rollback. This is a new bridge feature, not an adoption exception or a
worker-side Git workaround.

## Fence conclusion

Do not create a v70 same-HEAD fence for this report or to replay T4E; v69 still
describes the current checkout. If the new route is approved, a new fence is
required before launch whenever the clean target workspace identity differs.
After the bridge-owned commit, the supervisor must create the next immutable
fence for the exact new HEAD before any watcher restoration, as required by
`bridge/SUPERVISOR_PROTOCOL.md:60-66`. No adoption, acceptance, Gate 4
closure, or release is claimed here.
