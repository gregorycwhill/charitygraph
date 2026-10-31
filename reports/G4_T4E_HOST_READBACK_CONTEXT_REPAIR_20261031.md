# G4 T4E host readback context repair

Date: 2026-10-31 (Australia/Sydney)  
Target: `gate3-cg406-remediation@9a0a7d60e920242e843f1d9f7be282a870022624`  
Fence contexts exercised: `v74`, `v75`, and `v120`

## Result

Repaired only the dormant verifier and focused tests. Historical HEAD/fence
gates were removed. HEAD, fence version, and workspace are host observations
that must agree across the raw fence, status, ledger, source records, and
candidate package evidence. The stable policy epoch and exact two-file
candidate hash/identity allowlist remain fixed. Mismatches fail closed.

Positive output is now `STRUCTURE_ONLY_UNAUTHENTICATED`, with `action=NONE`,
`host_authentication_required=true`, `adoption_grant=false`, and explicit
structural-only limitations. Caller pins, synthetic reconciliation/test
attestations, report prose, and an absent or caller-supplied trust root do not
become authenticated authority. Output remains private-material redacted and
the verifier performs no writes.

## Verification

- Focused cache-free disposable run: **21 passed, 0 failed**.
- Covered dynamic v74/v75/later contexts, fake candidate identities and caller
  pins, missing host trust root, exact candidate hashes, timeout semantics,
  root confinement/path traversal/symlinks, tamper rejection, redaction and
  no-write behavior.
- No live bridge ingress, watcher/launcher, provider, Drive, GitHub, Git,
  publication, release or gate action was performed.

Residual limitation: without host-owned immutable provenance and separate host
authentication, even a positive result remains structural evidence only and
cannot grant recovery, adoption, or execution authority.

The local change is limited to this report, `bridge/g4_t4e_host_readback.py`,
and `tests/test_g4_t4e_host_readback.py`. The requested direct-child local
commit could not be created because Git metadata is read-only in this worker
(`git add` was denied while creating `.git/index.lock`; no lock existed).
