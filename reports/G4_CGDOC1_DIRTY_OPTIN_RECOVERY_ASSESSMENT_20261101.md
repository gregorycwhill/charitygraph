# G4-O1C CGDOC1 dirty opt-in recovery assessment

Date: 2026-11-01 (Australia/Sydney)  
Disposition: **PARTIAL -- code-ready for clean-target local adoption; not safe to adopt or live-activate from this checkout.**

## Identity and baseline

- Branch: `gate3-cg406-remediation`
- HEAD: `5bf3b530eac83c9f30ea1e3a5052e4cb8c793c9a`
- Supplied immutable fence: v97, SHA-256
  `c30256e691dff8393f16bf302f3d7ed57d7630d5f08ab7bb505878402fd43e5e`
- No v97 fence bytes or local fence file were present, so the supplied fence
  hash was not independently re-read. No Drive, provider, source, watcher,
  launcher, credential, GitHub, publication, or model operation was used.

The current four-path overlay is exactly the timeout patch already described by
`G4_DOC_EXPORT_INGRESS_TIMEOUT_INDEPENDENT_REVIEW_20261031.md`: patch SHA-256
`9f60f474d6cc407ac27354083fd8d0d74632ee50`.

| Path | HEAD blob | Current worktree blob |
|---|---|---|
| `bridge/bridge.py` | `5a9dd275d5ad038288672c7a10cc2543393275b9` | `20cf87749371ba469fa43a5d1776f4c255cd8f0a` |
| `bridge/g4_doc_export_ingress.py` | `d22e0458b5a9a937803c1082b9b09ba4c5d05d5a` | `8f997bffa1088467573f28be2bd69b19f0ad85bd` |
| `tests/test_bridge_doc_export_ingress.py` | `892d169c0d825a623c6a7c62fb12d4e30dea6824` | `d84f2ee8784fe1359678ca18cb9ea652371051d6` |
| `tests/test_bridge_cutover.py` | `4990f6bbd35a2e6bb4c014c34c7b70073b2cea18` | `9d25c93d233d89cfededecbf344696860b30909d` |

Before this report was written, the worktree had 20 modified tracked paths and
366 untracked paths. The other 16 modified tracked paths and all untracked
paths are unrelated baseline material and were not read as adoption candidates,
staged, overwritten, or absorbed.

## Independent local evidence

Command used:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider \
  --basetemp C:\CharityGraph-runtime\cgdoc1-assessment-basetemp-20261101 \
  tests/test_bridge_doc_export_ingress.py tests/test_bridge_cutover.py
```

Result: **38 passed, 2 skipped in 56.91s**. The skips were the expected
Windows disposable-symlink privilege case and the explicitly disabled real
Codex CLI rehearsal. `git diff --check` passed for all four target paths.

The tests and static review cover:

- direct-child filename/path restriction, regular-file checks, Windows reparse
  attribute checks, POSIX no-follow opening, opened-file identity checks, and a
  simulated replacement/TOCTOU rejection;
- CGDOC1 exact wrapper, optional export BOM, no wrapper newline, base64url and
  embedded-byte SHA-256, UTF-8/canonical JSON, and rejection of BOM, newline,
  pretty, duplicate-key, malformed and hash-tampered payloads;
- exact active fence, workspace/branch/HEAD, authority, operation, model and
  allowlist checks;
- existing ledger duplicate/conflict/single-claim behaviour, dirty-baseline
  rejection through the existing `_validate_engineering` path, raw JSON
  compatibility, and default-off scanning/activation.

The implementation is therefore structurally adequate as an injected,
default-off local seam. The four-path patch is not itself evidence of native
connected-Doc export, authenticated host pickup, or a completed end-to-end
result.

## Findings and limits

1. `bridge/g4_doc_export_ingress.py` provides the no-follow/read identity
   boundary and `bridge/bridge.py` routes a validated export into the existing
   `LocalAutonomousBridge` ledger and engineering validation. The raw JSON
   candidate set remains unchanged.
2. `DocExportIngressConfig` is default-off. The production CLI construction at
   `bridge/bridge.py:1618` does not pass an opt-in configuration, so the live
   watcher cannot currently pick up a text export merely because one exists.
   That is the required safety posture, not a failed test.
3. Dirty-baseline protection is inherited from the existing host admission
   path: `_process_doc_export` validates the decoded envelope, then
   `_process_candidate` calls `_validate_engineering`, which captures the
   current workspace and rejects pre-dirty/staged paths. The new decoder does
   not independently persist a baseline snapshot; it must not be treated as a
   replacement for that host check.
4. Windows did not permit creation of the disposable symlink, so positive
   Windows reparse-point runtime behaviour remains unproven. The static
   `FILE_FLAG_OPEN_REPARSE_POINT` and attribute checks are present, and the
   portable TOCTOU substitution probe passed.
5. The supplied v97 fence and any connected Google Doc credentials are absent
   locally. This worker cannot establish trusted host authentication or native
   Doc export bytes, and no assertion of live authenticated ingestion is made.

## Smallest next bounded tranche (<=600 seconds)

Use a separate clean-target mechanism at exact HEAD
`5bf3b530eac83c9f30ea1e3a5052e4cb8c793c9a` (for example a disposable clean
worktree under `C:\CharityGraph-runtime`), then overlay only these exact four
paths from the current root:

```text
bridge/bridge.py
bridge/g4_doc_export_ingress.py
tests/test_bridge_doc_export_ingress.py
tests/test_bridge_cutover.py
```

Verify the clean target starts with no dirty/untracked files, apply the
four-path patch without broad checkout/reset or add-all operations, rerun the
focused cache-free suites and `git diff --check`, and preserve the resulting
clean target for independent acceptance. This path-by-path overlay cannot
absorb or overwrite the current root's other tracked edits or untracked
evidence. No additional code change is required for local code-readiness.

Only after that clean-target result is independently accepted is a separate
host tranche appropriate: provide the exact v97 fence bytes and trusted host
configuration/credentials, opt in the existing watcher explicitly, and prove
one native Doc export -> claim/result, replay no-op, and tamper, identity,
fence, allowlist and dirty rejection. That would be live authenticated Doc
export ingestion; this report establishes only provider-free local feasibility.

No gate closure, adoption, activation, publication, release, replay, or
follow-on dispatch is claimed.
