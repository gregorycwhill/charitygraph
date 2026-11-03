# G4-O1C CGDOC1 host-safe adoption helper — independent acceptance

Date: 2026-11-01 (Australia/Sydney)  
Disposition: **REJECTED for the requested v98 acceptance; structurally PARTIAL under the older v97 identity.**

## Scope and identity

Reviewed exact branch `gate3-cg406-remediation`, HEAD
`932728a0a520d8374a18d3b576a880ac5466c798`, parent
`5bf3b530eac83c9f30ea1e3a5052e4cb8c793c9a`, and supplied v98 fence SHA-256
`28d69375504c4b904a932059ab5af3ad2048b96ffa9cfc8e1da6f22c3d8b671a`.
The direct-child diff contains exactly the helper, its focused test, and the
prior worker report. Current helper/test SHA-256 values match the commit:
`ea319f5e…4dc2ad3` and `02b0e103…f1ab5c`.

## Deterministic evidence

Cache-free focused run, external basetemp:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cgdoc1-independent-basetemp-20261101-a tests/test_bridge_doc_export_clean_adoption.py tests/test_bridge_doc_export_ingress.py
```

Result: **26 passed, 2 skipped**. Disposable synthetic probes also passed
stale root/target HEAD, altered bytes, duplicate IDs, traversal, forged dirty
baseline, unexpected target changes, canonical-manifest tamper detection,
synthetic reparse rejection, TOCTOU identity change, and no-side-effect checks.
Windows symlink creation was unavailable; native Windows-positive reparse
behaviour is therefore unproven. No malformed-manifest consumer/verifier is
implemented; the probe only detected mutation by recomputing the emitted
manifest digest.

## Security and trust-boundary finding

The helper is preparation-only. It uses only read-only Git subprocesses and
the existing no-follow/reparse-aware regular-file reader. It has no staging,
index/ref/commit operation, watcher activation, Doc/credential access,
provider call, or authenticated-ingress claim. Its manifest is canonical and
content-hashed, reports `PARTIAL`, `NOT_ADOPTED`, `NOT_ACTIVATED`, and
`trusted_host_proven: false`; the existing Doc scanner remains default-off.

The blocking mismatch is exact and material: the code pins
`FENCE_V97_SHA256 = c30256e6…fd43e5e` and rejects every other fence, while the
requested acceptance is fenced to v98. A request carrying the supplied v98
digest was independently rejected. Consequently no v98-bound attestation or
safe adoption claim can be accepted from this artifact.

## Smallest next tranche

After an authorised bounded identity repair (or an explicit reissue of the
acceptance fence), provide the exact v98 fence bytes, re-run the focused and
native Windows security probes, and generate a v98-bound manifest in a clean
target. Only then may the trusted host re-attest, invoke the existing exact
four-path commit seam, verify one direct child and a successor fence, and
separately prove authenticated native Doc export/replay/tamper behaviour.
No adoption, activation, credentials, provider/Drive operation, private
material, Git staging, or Git mutation was performed.
