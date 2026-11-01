# G4-O1C CGDOC1 host-safe overlay adoption helper

Date: 2026-11-01 (Australia/Sydney)  
Disposition: **PARTIAL — preparation only; NOT_ADOPTED; NOT_ACTIVATED.**

## Bounded result

Added only the permitted helper and focused test. The helper is read-only and
uses the existing ingress module's no-follow regular-file reader; it does not
stage, commit, move a ref, launch a watcher, activate native Doc export, read a
Google Doc, or modify the four existing dirty paths.

The attestation request binds:

- branch `gate3-cg406-remediation` and HEAD
  `5bf3b530eac83c9f30ea1e3a5052e4cb8c793c9a`;
- fence v97 SHA-256
  `c30256e691dff8393f16bf302f3d7ed57d7630d5f08ab7bb505878402fd43e5e`;
- exact allowlist `bridge/bridge.py`, `bridge/g4_doc_export_ingress.py`,
  `tests/test_bridge_doc_export_ingress.py`, and `tests/test_bridge_cutover.py`;
- each path's exact HEAD/worktree Git blob pair, complete root dirty-baseline
  path/status/blob fingerprint, clean-target branch/HEAD/tree, and exactly the
  four unstaged overlay paths.

It fails closed on stale/ref-moved identity, missing or changed bytes, extra
overlay paths, staged/ambiguous target state, duplicate/conflicting identities,
path traversal, symlink/reparse points, and file identity changes during read.
The returned manifest is canonical content-hashed and includes
`PARTIAL`, `NOT_ADOPTED`, `NOT_ACTIVATED`, `refs/heads/<branch>`, the exact
parent HEAD and four-path commit scope, plus successor-fence/native-Doc steps.

## Verification

Cache-free command, with basetemp outside the repository:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cgdoc1-adoption-basetemp-20261101 tests/test_bridge_doc_export_clean_adoption.py tests/test_bridge_doc_export_ingress.py
```

Result: **26 passed, 2 skipped in 19.49s**. The new helper suite alone was
**10 passed, 1 skipped**. The new negatives cover stale HEAD/fence, altered
worktree hash, traversal, duplicate identity, unrelated dirty-baseline bytes,
extra overlay, stale target ref, missing path, symlink/reparse rejection, and
no-side-effect preservation of refs, status, bytes, and index diff. The one
new-test skip is Windows symlink creation unavailable under the test account;
the existing ingress symlink/TOCTOU test had the same Windows privilege skip.

The live root was inspected read-only after implementation: branch/HEAD were
not changed, the baseline reader observed 391 dirty entries, and no adoption
operation was attempted. No provider/model call, source acquisition, Drive,
credential, watcher, launcher, staging, commit, GitHub, publication, release,
or private-material addition occurred. The four original dirty paths and all
other pre-existing dirty state remain untouched.

SHA-256:

- `bridge/g4_doc_export_clean_adoption.py`:
  `ea319f5eb9ec93c3b4729326a1295aa95bd074ae29facebce46d9623e4dc2ad3`
- `tests/test_bridge_doc_export_clean_adoption.py`:
  `02b0e1036c55230d509c5ce2d59fbe25699b9deb0107af795a277c8558f1ab5c`

## Narrow successor

A separately authorised trusted host must re-attest the same disposable clean
target and invoke the existing
`_bridge_owned_exact_path_commit(parent_head=HEAD, paths=exact_allowlist)`
there, verifying one direct child on `refs/heads/gate3-cg406-remediation` and
writing a successor exact fence before any activation. A further separately
authorised bridge harness must then enable the dormant native Doc scanner and
prove authenticated native export, one claim/result, replay no-op, and
tamper/identity/fence/allowlist/dirty rejection end to end. This worker could
not prove trusted-host identity, so the result remains **PARTIAL**.
