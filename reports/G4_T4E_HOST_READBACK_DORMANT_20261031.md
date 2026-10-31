# G4 T4E host readback dormant tranche

Implemented only the requested dormant surfaces:

- `bridge/g4_t4e_host_readback.py`
- `tests/test_g4_t4e_host_readback.py`
- this report

The module reads a supervisor-fixed, confined private artifact bundle and
recomputes the declared byte hashes. It fails closed on missing or extra
files, symlinks and root escape, duplicate identities, noncanonical JSON,
candidate tampering, stale v73 context, active/ambiguous ledger state,
timeout upgrades, same-source reconciliation, missing test evidence and any
allowlist other than the exact two pinned candidate files.

It returns an immutable, serialisable, redacted attestation with `action`
`NONE`. Even a structurally verified result remains
`HOST_READBACK_STRUCTURALLY_VERIFIED_NONACTIONABLE`, requires later separate
host authentication and acceptance, and cannot promote recovery authority.
No helper, Git, bridge, watcher, process, provider, network or filesystem
write was invoked by the module. Existing unrelated dirty and index state
was not modified. Focused tests were run cache-free: 12 passed; no Git
transaction was performed.
