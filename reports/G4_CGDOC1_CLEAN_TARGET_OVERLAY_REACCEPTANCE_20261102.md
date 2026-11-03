# G4-O1C CGDOC1 clean-target overlay reacceptance

Date: 2026-11-02 (Australia/Sydney)  
Disposition: **PARTIAL - structural clean-target overlay accepted; fence
provenance and trusted-host/native-Doc proof remain unproven.**

## Identity and protected overlay

- Branch: `gate3-cg406-remediation`
- HEAD: `b6c9f30c98dd01978c7df3a937cd7e9001023f23`
- Supplied active fence: v101, SHA-256
  `4c295f75d30c8f987a1f3fe6ffe06ce0e2e55d173db57e8448b6e6c6370124e5`
- The named root overlay scope is exactly these four unstaged paths; no named
  path is staged. Other pre-existing root dirty/untracked paths were left
  untouched.

| Path | HEAD blob | current/worktree SHA-256 |
|---|---|---|
| `bridge/bridge.py` | `5a9dd275d5ad038288672c7a10cc2543393275b9` | `91f53253f9357be05d44ded0727391083e4b2a8626e21064c744fed5d0a26168` |
| `bridge/g4_doc_export_ingress.py` | `d22e0458b5a9a937803c1082b9b09ba4c5d05d5a` | `bfd914ded7d52bfd1d97035dd8c4d5ae393fbcd981ef9a7a38f60c75cc6a0b4d` |
| `tests/test_bridge_cutover.py` | `4990f6bbd35a2e6bb4c014c34c7b70073b2cea18` | `161c10363a510503d77e9e78660a09af542b031faac798b9098fb2fa99cf5ce0` |
| `tests/test_bridge_doc_export_ingress.py` | `892d169c0d825a623c6a7c62fb12d4e30dea6824` | `0665acd8d9c648e8ed36f44fd000031e8e83207104b723465117ac6522e83462` |

## Clean-target verification

Disposable target: `C:\CharityGraph-runtime\cgdoc1-clean-target-overlay-reacceptance-20261102`

- Cloned locally from the repository and verified at exact HEAD.
- Clean before overlay: no status output or untracked files.
- Copied only the four paths above; each source/target SHA-256 matched before
  testing.
- After overlay, target status and unstaged diff contained exactly the four
  paths; staged diff was empty.
- Target `git diff --check` passed.

Cache-free focused command with external basetemp:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider \
  --basetemp C:\CharityGraph-runtime\cgdoc1-clean-target-overlay-reacceptance-basetemp-20261102 \
  tests/test_bridge_doc_export_ingress.py tests/test_bridge_cutover.py
```

Result: **38 passed, 2 skipped in 67.07s**. The skips were the expected
Windows disposable-symlink privilege case and the disabled real Codex CLI
rehearsal. The targeted negative subset passed **19 passed, 1 skipped** and
covered default-off scanning, raw JSON compatibility, malformed/tampered
exports, identity/fence/allowlist rejection, duplicate/replay safety,
dirty-baseline rejection and no-side-effect paths.

## Limits and next step

No local repository/runtime file contained the supplied v101 identifier or
digest, so the exact raw v101 fence bytes could not be independently read and
hashed. Native Windows-positive reparse proof, trusted-host adoption and
authenticated native Doc pickup were not attempted. No provider, Drive,
credential, watcher, launcher, source, model, staging, commit, ref change,
publication or release operation occurred.

Smallest next authorised step: provide the exact v101 raw fence bytes through
the trusted host path and independently recompute the supplied digest. Do not
adopt or activate from this worker; native Windows-positive and authenticated
Doc pickup remain separate proof requirements.
