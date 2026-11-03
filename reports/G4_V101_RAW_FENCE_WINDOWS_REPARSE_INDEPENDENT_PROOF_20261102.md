# G4-O1C v101 raw-fence and Windows reparse independent proof

Date: 2026-11-02 (Australia/Sydney)  
Disposition: **PARTIAL — raw fence provenance proven; Windows-positive native
reparse proof unavailable / not proven.**

## RAW FENCE PROVENANCE — PROVEN

The exact bytes were read from the local Drive-synchronised path before any
JSON parsing or re-serialisation:

`C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\cg-g4-o1b-dormant-state-fence-20261020-v101.json`

- Byte length: `3893` (expected `3893`)
- SHA-256: `4c295f75d30c8f987a1f3fe6ffe06ce0e2e55d173db57e8448b6e6c6370124e5`
  (expected exact match)
- UTF-8 BOM: absent; final byte is LF
- The file was parsed read-only only after the byte hash was computed.

Parsed fence checks all passed:

- Schema: `charitygraph.g4-o1b-dormant-fence/v1`
- State: `ACTIVE`
- Fence ID/version: `cg-g4-o1b-dormant-state-fence-20261020-v101` / `101`
- Workspace: `C:\CharityGraph-clean\charitygraph`
- Branch: `gate3-cg406-remediation`
- `head`: `b6c9f30c98dd01978c7df3a937cd7e9001023f23`
- `implementation_revision`: `b6c9f30c98dd01978c7df3a937cd7e9001023f23`

## Read-only checkout binding

Git inspection reported:

- Branch: `gate3-cg406-remediation`
- HEAD: `b6c9f30c98dd01978c7df3a937cd7e9001023f23`
- HEAD tree: `c2fff9b26acbab02cee6214cebaa5d733c9c43f6`

The raw fence workspace, branch, HEAD, and implementation revision all match
the exact current checkout. `git status` emitted pre-existing permission
warnings for two disposable directories and reported 391 porcelain rows; no
status-mutating operation was used.

## WINDOWS-POSITIVE NATIVE REPARSE — UNAVAILABLE / NOT PROVEN

Platform and privilege observations:

- Windows: `Microsoft Windows NT 10.0.26200.0`
- Identity: `HP_Laptop\CodexSandboxOffline`
- Administrator role: `False`
- Developer-mode registry value: unavailable; no OS policy was changed.

A fresh disposable target was created outside the checkout, bridge runtime,
and Drive-synchronised artifacts:

`C:\Users\grego\AppData\Local\Temp\cg-g4-v101-reparse-proof-20261102-142eb581c4094e25a122971156ec206b`

It contained only a harmless fixture file. A native Python `os.symlink`
creation attempt failed with the actual Windows error:

`OSError: [WinError 1314] A required privilege is not held by the client`

The link was not created, so there is no native reparse identity or
`st_file_attributes` evidence to report. Existing ingress/containment checks
were not credited against a synthetic or reconstructed link, and no positive
result was inferred from the privilege failure. The disposable attempt was
not reused or used to alter repository state.

## Protection attestation and remaining gaps

Only this fresh report was written in the repository. No product code, bridge
code, tests, overlay file, fence/status/ledger/workspace file, Git index,
branch/ref, Drive artifact, provider, source, credential, watcher, launcher,
or process state was changed. The pre-existing dirty/untracked worktree,
including the historical 471-entry protection baseline, was left untouched.

Remaining acceptance gaps are the positive native Windows reparse/symlink
creation and fail-closed exercise against an actual native link, trusted-host
adoption, and authenticated native Google Doc pickup. This report does not
claim trusted-host adoption, authenticated native pickup, publication,
release, or Gate 4 closure.
