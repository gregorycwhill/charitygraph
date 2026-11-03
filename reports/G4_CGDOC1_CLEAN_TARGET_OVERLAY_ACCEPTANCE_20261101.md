# G4-O1C CGDOC1 clean-target overlay acceptance

Date: 2026-11-01 (Australia/Sydney)  
Disposition: **ACCEPTED WITH LIMITS — clean-target structural overlay verified; no commit, adoption, activation, or host pickup performed.**

## Identity

- Root branch: `gate3-cg406-remediation`
- Root HEAD: `5bf3b530eac83c9f30ea1e3a5052e4cb8c793c9a`
- Supplied fence: v97, SHA-256 `c30256e691dff8393f16bf302f3d7ed57d7630d5f08ab7bb505878402fd43e5e`
- The v97 fence bytes were not present locally; its supplied digest was not re-read.
- All four supplied HEAD/worktree blob pairs matched exactly:

| Path | HEAD blob | Worktree blob |
|---|---|---|
| `bridge/bridge.py` | `5a9dd275d5ad038288672c7a10cc2543393275b9` | `20cf87749371ba469fa43a5d1776f4c255cd8f0a` |
| `bridge/g4_doc_export_ingress.py` | `d22e0458b5a9a937803c1082b9b09ba4c5d05d5a` | `8f997bffa1088467573f28be2bd69b19f0ad85bd` |
| `tests/test_bridge_doc_export_ingress.py` | `892d169c0d825a623c6a7c62fb12d4e30dea6824` | `d84f2ee8784fe1359678ca18cb9ea652371051d6` |
| `tests/test_bridge_cutover.py` | `4990f6bbd35a2e6bb4c014c34c7b70073b2cea18` | `9d25c93d233d89cfededecbf344696860b30909d` |

The four-path diff is exactly 380 insertions and 44 deletions. The supplied
patch SHA-256 `9f60f474d6cc407ac27354083fd8d0d74632ee50` was not reproducible
from the raw Windows `git diff` serialisations available here; the exact blob
pairs above are independently confirmed. Root `git diff --check` passed for
the four paths.

## Clean-target rehearsal

Created the separate ordinary clone
`C:\CharityGraph-runtime\cgdoc1-clean-target-overlay-20261101` with
`git clone --no-local --branch gate3-cg406-remediation` (not `git worktree`).
It started clean at the exact HEAD, with no untracked files. Only the four
current root worktree bytes were copied into it.

After overlay:

- `git status --short --untracked-files=all` listed exactly the four target paths;
- no unrelated tracked path was dirty and no untracked evidence entered the clone;
- clone `git diff --check` passed;
- the clone's four worktree blobs matched the four root worktree blobs;
- the root branch, HEAD, and pre-existing dirty scope remained unchanged.

The overlay can therefore become an exact direct child of the pinned HEAD by a
future separately authorised exact-path commit in the clean target. No index,
ref, staging area, commit, or adoption was performed in any checkout.

## Verification

Cache-free focused command, run in the clean target with external basetemp
`C:\CharityGraph-runtime\cgdoc1-clean-basetemp-20261101`:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider --basetemp <external> tests/test_bridge_doc_export_ingress.py tests/test_bridge_cutover.py
```

Result: **38 passed, 2 skipped in 55.73s**. The targeted negative subset also
passed (**13 passed, 1 skipped, exit 0**), covering BOM/newline/pretty,
duplicate and hash tamper, wrong HEAD/fence, authority/allowlist, dormant scan
and raw-JSON compatibility, replay/ledger behaviour, and the opt-in path. The
single Windows skip is the symlink/TOCTOU test because disposable symlink
creation returned WinError 1314; native Windows positive reparse/TOCTOU runtime
behaviour remains unproven here. The other full-suite skip is the disabled real
Codex CLI rehearsal.

## Adoption boundary and next mechanism

Structural code readiness is established only for this provider-free clean
overlay. The safe next local adoption mechanism is the existing bridge-owned
bounded exact-path commit path (`_bridge_owned_exact_path_commit`) on a clean,
exact-HEAD target, with pre-launch dirty-baseline capture and an exact allowlist
of the four paths. It does not require a new commit harness change, and it was
not invoked here.

Authenticated native Doc export/host pickup is a separate state. The live
watcher still constructs `DocExportIngressConfig` default-off, so native host
pickup requires a new separately authorised bounded bridge harness/wiring change
that explicitly enables the scanner through the existing trusted watcher,
passes exact fence/branch/HEAD/dirty-baseline/allowlist context, and preserves
the existing raw-JSON candidate path. It must then prove native export, one
claim/result, replay no-op, and tamper/identity/fence/allowlist/dirty rejection.
This rehearsal provides none of that host authentication or native Doc evidence.

No Drive, provider, external source, model, watcher, launcher, credential,
GitHub, publication, release, gate closure, staging, commit, or follow-on task
was used. No private material was added to Git; test basetemp and clone state
remain under `C:\CharityGraph-runtime`.
