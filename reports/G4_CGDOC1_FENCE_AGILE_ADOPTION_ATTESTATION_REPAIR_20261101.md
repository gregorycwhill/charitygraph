# G4-O1C CGDOC1 fence-agile adoption attestation repair

Date: 2026-11-01 (Australia/Sydney)  
Disposition: **PARTIAL — repair complete; preparation remains NOT_ADOPTED and NOT_ACTIVATED.**

## Scope and identity

The bounded repair was made on branch `gate3-cg406-remediation`, HEAD
`932728a0a520d8374a18d3b576a880ac5466c798`. It changes only the adoption
helper and its focused test; this report is the only new report path.

The v97-only digest constant was removed. `CleanAdoptionRequest` now requires
caller-supplied raw fence bytes, `fence_id`, `fence_version`, and a pinned
expected SHA-256. The helper checks exact canonical UTF-8 JSON, duplicate keys,
non-standard JSON constants, schema/state, ID/version, digest, and fence
workspace/branch/HEAD against the current root snapshot. It does not infer
trusted provenance from a self-consistent caller hash.

## Verification

Cache-free focused command with external basetemp:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cgdoc1-fence-agile-basetemp-20261101-d tests/test_bridge_doc_export_clean_adoption.py tests/test_bridge_doc_export_ingress.py
```

Result: **38 passed, 2 skipped**. The skips are the existing Windows symlink
privilege case and disabled real CLI rehearsal. `git diff --check` passed for
both changed code/test paths.

The focused tests include a synthetic v98-bound positive preparation, stale
v97 rejection while the v98 digest is pinned, forged bytes rejection, missing
bytes fail-closed behaviour, canonical UTF-8/BOM/newline/duplicate-key checks,
conflicting ID/version, wrong fence branch/HEAD, caller-created self-consistent
material remaining `PARTIAL`/`NOT_ADOPTED`/`NOT_ACTIVATED`, and the prior
no-side-effect, path traversal, dirty baseline, symlink/reparse, and
unexpected-overlay regressions.

## Trust and boundary

Every successful manifest continues to state
`trusted_host_proven: false`, `adoption_status: NOT_ADOPTED`, and
`activation_status: NOT_ACTIVATED`. No host activation, commit, staging,
watcher, Drive, provider, model, credential, GitHub, publication, release,
or gate operation was performed. The actual trusted-host v98 fence bytes were
not available locally; the synthetic v98 test proves the successor-fence API
shape and binding rules, not independent provenance of the supplied v98
digest. Independent trusted-host verification and any later adoption remain
separate prerequisites.

