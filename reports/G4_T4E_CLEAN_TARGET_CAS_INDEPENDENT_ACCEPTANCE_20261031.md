# G4 T4E clean-target CAS repair independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Verdict: **PASS — dormant host helper only**

## Scope and identity

Reviewed branch `gate3-cg406-remediation`, HEAD
`070c96a854e1a2ba8e674f21d06f3df602d86006`, parent
`ce624f6fd81a26572744fdbce538f563c417804f`, fence `v71`
(`b7eee29b72031f3b3ca501c381921ac28a139304a5782d5709b02159e7bab689`).
The exact commit changes only the helper, its focused test, and
`G4_T4E_CLEAN_TARGET_CAS_REPAIR_20261031.md`.

## Independent verification

- Copied the exact helper and focused test into a disposable directory outside
  the checkout, with an isolated package initializer. Ran
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider --basetemp <external-temp>`.
  Result: **9 passed, exit code 0**; no bytecode or pytest-cache files.
- Independently forced `_compare_and_swap_ref` to fail in a fresh external Git
  repository containing a dirty worktree and staged index entry. The
  machine-readable exception attestation verified: `FETCH_HEAD` bytes/hash
  unchanged; branch HEAD, original worktree bytes, and original index/status
  unchanged; `objects_may_have_been_installed` exactly covered every reachable
  object absent before import; all such objects were observed afterward;
  `unlink_performed: false`; and the policy requires a later host reachability
  audit before normal GC/prune.

## Code and side-effect findings

- Validation, exact allowlist/manifest/anchor checks, pinned branch/HEAD, and
  clean isolated-target checks occur before host import
  (`src/charitygraph/g4_clean_target_commit.py:238-373`). Tree construction and
  byte verification are isolated in a temporary clone/index
  (`375-399`).
- Non-dry-run import now uses `fetch --no-write-fetch-head`, inventories
  reachable objects and pre-existing objects, and emits before/after
  `FETCH_HEAD` hashes plus conservative object accounting
  (`400-431`). Expected-old `update-ref` CAS rejects concurrent branch movement
  without claiming object rollback (`432-452`). This is the correct residual
  side-effect boundary: unreachable objects may remain and require safe later
  host GC, not immediate deletion.
- Dry-run remains host-import-free (`455-468`). No new live-repository,
  provider, network, credential, bridge, watcher, or publication action was
  performed. `git diff --check` found one trailing-whitespace marker in the
  already committed repair report’s date line; it is documentation-only.
- Manifest/anchor self-consistency proves integrity and correspondence, not
  independent origin: the helper accepts caller-supplied objects and has no
  signature or supervisor provenance check (`254-303`). This is an integration
  precondition, not a dormant-helper failure.

## Minimum safe integration seam

Do not wire this into ordinary worker adoption or invoke it on the dirty live
checkout. The existing adoption contract requires an exact newly-created
untracked artifact and a completed verified bridge result, and explicitly
rejects tracked-dirty paths (`bridge/bridge.py:732-845`,
`bridge/SUPERVISOR_PROTOCOL.md:50-70`). The minimum seam is a separately
authorised bridge-owned clean-target route, as also identified in
`reports/G4_T4E_CLEAN_WORKTREE_ADOPTION_ROUTE_20261031.md:80-106`:

1. Provision/bind a separate clean target at the exact repository, branch, and
   expected HEAD; preserve the live checkout and its index untouched.
2. Independently bind the exact allowlist, candidate bytes and hashes to an
   immutable supervisor/bridge provenance record (including source instruction
   and result identity, repository/branch/workspace/HEAD, manifest hash and
   source-anchor hash). The bridge, not the helper or worker, must establish
   that provenance before passing the values to this helper.
3. Call the helper with that clean target and `dry_run=False`; verify its
   object-import attestation, expected-old CAS result, exact direct-child
   paths/parent, and preservation of all pre-existing dirty paths. Retain any
   unreachable objects for a later reachability-audited host maintenance pass.
4. Record the resulting local commit and create the required exact-HEAD
   successor fence before watcher restoration. This is a new bridge route, not
   an adoption exception or worker-side Git workaround.

Private evidence, credentials, caches, raw sources, and runtime artifacts were
not added to this report or the repository.
