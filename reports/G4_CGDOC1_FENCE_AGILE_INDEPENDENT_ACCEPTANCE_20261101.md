# G4-O1C CGDOC1 fence-agile independent acceptance

Date: 2026-11-01 (Australia/Sydney)  
Disposition: **REJECTED for exact-HEAD acceptance; deterministic current-dirty-overlay evidence is PARTIAL.**

## Scope and identity

Checked branch `gate3-cg406-remediation`, HEAD
`396d4cd0470a843bb6aa42d9bf8aba9a4ab11cee`, parent
`932728a0a520d8374a18d3b576a880ac5466c798`, and the supplied active v99
SHA-256 `8a5e594fdef3210a4ceb4aaf7012915b372d6b9265ee1e73f7ecc0c7d1578190`.
The supervisor protocol is at `bridge/SUPERVISOR_PROTOCOL.md` (not the
repository root).

The exact HEAD direct-child diff is only:

```text
M bridge/g4_doc_export_clean_adoption.py
A reports/G4_CGDOC1_FENCE_AGILE_ADOPTION_ATTESTATION_REPAIR_20261101.md
M tests/test_bridge_doc_export_clean_adoption.py
```

Current helper SHA-256 is
`5728c27f6c87c52967d32f3d8bb3de2646468464fc124697cdb553ad14bc025c` and
focused-test SHA-256 is
`419ff01ae4f94ab141c78655df0454071d986695a62426d60be4df5ebac046e0`; both
match HEAD. `bridge/g4_doc_export_ingress.py` is a pre-existing dirty path,
not in that direct-child diff. A disposable clone of exact HEAD cannot import
the helper: it raises `ImportError` because HEAD ingress lacks the imported
`_has_reparse_attribute` and `_read_regular_file_no_follow` symbols. The
current dirty overlay supplies them, so current-worktree results cannot be
promoted to exact-HEAD acceptance.

## Verification

Cache-free focused command with external basetemp:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cgdoc1-fence-agile-independent-basetemp-20261101-a tests/test_bridge_doc_export_clean_adoption.py tests/test_bridge_doc_export_ingress.py
```

Result: **38 passed, 2 skipped** in 48.61s. The skips are the existing
Windows symlink-privilege case and disabled real CLI rehearsal.

Disposable synthetic probes passed for canonical synthetic v99 binding,
stale v98 against the active v99 digest, altered/missing fence bytes,
UTF-8/BOM/newline/whitespace/duplicate-key/non-standard-constant handling,
conflicting ID/version, wrong workspace/branch/HEAD, traversal, synthetic
reparse rejection, dirty-baseline preservation, unexpected overlay, and
unchanged HEAD/status/index/refs. Logged subprocess argv contained only
read-only Git commands. The synthetic success manifests remained
`PARTIAL`, `NOT_ADOPTED`, `NOT_ACTIVATED`, and `trusted_host_proven: false`.

## Precise blockers and boundary

1. Exact v99 fence bytes were not available locally; only the supplied digest
   was available. A self-created canonical v99 fence proves API binding only,
   not the active immutable fence. The supplied digest correctly rejects the
   fabricated bytes.
2. Native Windows-positive symlink/reparse proof was unavailable (`os.symlink`
   raised `OSError`); only the deterministic synthetic reparse guard ran.
3. Trusted-host provenance and authenticated native Doc export/replay remain
   unproven. The helper itself performs no Doc, credential, Drive, provider,
   staging, index/ref, watcher, or activation operation.

## Smallest safe next tranche

Make the no-follow ingress dependency part of the exact accepted HEAD (or make
the helper depend only on committed interfaces), then rerun this acceptance in
a clean checkout. Separately supply the exact v99 bytes through the trusted
host path and perform native Windows-positive and authenticated-Doc proof.
No adoption, activation, staging, commit, publication, release, or private
material acquisition was performed.
