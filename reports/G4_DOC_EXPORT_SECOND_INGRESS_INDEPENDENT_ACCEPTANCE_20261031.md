# G4-O1C second-ingress independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Disposition: **PARTIAL** — the local dormant decoder is accepted as a bounded
structural seam; host pickup and independent end-to-end acceptance are not
established. No product progress credit or gate closure is claimed.

## Identity and boundary

- Branch: `gate3-cg406-remediation`.
- HEAD: `e215f3ca82307bc398433c54940ef312b5cbde3e`.
- Parent: `50a9bd1a9e6450a8cdc26a12acd4cef21f67964f`.
- The supplied v83 fence SHA-256 is
  `45bcf370446de0eada2efd41e0999c88127a29ca4ce4f3a177643e4355c2db31`.
  Its bytes were not present in this local checkout, so the fence hash was not
  independently re-read. No Drive or provider access was used.
- `git diff-tree` confirms exactly four committed paths: `bridge/bridge.py`,
  `bridge/g4_doc_export_ingress.py`,
  `tests/test_bridge_doc_export_ingress.py`, and the prior implementation
  report. `bridge/managed_launcher.py` has no commit delta.
- The pre-existing dirty/untracked baseline was preserved. No unrelated path
  was staged, committed, or absorbed; no watcher, launcher, credential,
  provider, source, Drive, GitHub, publication, release, or process operation
  occurred. Disposable pytest material stayed outside the repository.

## Local acceptance

**PASS — dormant isolation and envelope validation.** `bridge.py:60-65` only
records an inert Doc-export prefix/state. `bridge.py:580-584` still returns
only `cg-g4-o1b-instruction-*.json` candidates, and `bridge.py:1495-1503`
keeps the existing single watcher path. The new module is not imported or
called by the live bridge or launcher; no import cycle or active pickup path
was found. Existing ledger duplicate/conflicting-identity semantics remained
unchanged.

`bridge/g4_doc_export_ingress.py:195-261` independently passed the exact
`CGDOC1` ASCII wrapper, unpadded base64url, decoded-byte lowercase SHA-256,
optional single export BOM, no wrapper final LF, UTF-8 embedded bytes, one
embedded LF/no BOM, sorted compact canonical JSON, duplicate-key and
non-standard-constant rejection, and envelope checks for schema, authority,
operation, model, repository/workspace/branch/HEAD, active fence and exact
allowlist. Path traversal, external paths, wrong hashes, malformed/pretty/
CRLF input and conflicting identity were rejected.

## Independent tests

The requested cache-free commands ran with `python -B`,
`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and disposable basetemp:

```text
tests/test_bridge_doc_export_ingress.py: 16 passed in 4.21s
tests/test_bridge_doc_export_ingress.py tests/test_bridge_cutover.py:
  37 passed, 1 skipped in 51.09s
```

The single skip is the explicit real Codex CLI rehearsal at
`tests/test_bridge_cutover.py:625-627`; it was not enabled. An additional
read-only/disposable probe passed nine wrapper, JSON, hash, external-path and
dormant-scan adversarial cases. Windows denied creation of a disposable
symlink (`OSError`), so no positive symlink runtime result is claimed.

## Findings and limits

1. **Future activation symlink/TOCTOU risk (PARTIAL).**
   `read_doc_export` resolves the path and checks `resolved.parent` at
   `bridge/g4_doc_export_ingress.py:263-274`, but does not explicitly reject
   `source.is_symlink()`/Windows reparse points and then performs a separate
   `read_bytes()`. The future scanner uses `path.is_file()` at lines 296-300,
   which follows symlinks. A trusted host integration must reject links and
   reparse points and use an atomic/no-follow read boundary before activation.
2. **Dirty-worktree guard is not in this decoder.** `DocExportContext` carries
   identity, fence bytes and allowlist, but no dirty-baseline snapshot. The
   existing host bridge exposes dirty paths at `bridge/bridge.py:394-483` and
   downstream bounded execution owns dirty-path enforcement; because there is
   no integration, this task does not claim Doc-export dirty-worktree
   acceptance.
3. **Activation is deliberately not trusted to this module.** The scanner
   remains empty unless both an explicit argument and the mutable module flag
   are changed (`bridge/g4_doc_export_ingress.py:281-300`). No live caller does
   so. Future activation must be an existing-host, fence/dirty-verified action,
   not a mutable global or a new trust root.

## Prior host evidence

The local prior supervisory record
`reports/G4_O1B_RECOMMISSION_AUTONOMOUS_BRIDGE_2026-10-20.md` says the native
Google Doc readback was empty, its content write was rejected, and no host
mirror existed. The local T4E reports are explicitly structural/non-actionable
and do not establish a native Doc → text/plain export → `source_file_ref` →
private Drive byte-exact probe. No such byte-exact evidence was found locally;
this worker did not access Drive or host credentials and makes no host-side
pickup or authenticated-new-trust-root claim.

## Committed file hashes

SHA-256 of the four committed paths at review time:

| Path | SHA-256 |
|---|---|
| `bridge/bridge.py` | `d087e171a0b5c5987dd666b6a3ac166241d971957fbad2840d372b950c9f4de0` |
| `bridge/g4_doc_export_ingress.py` | `70099b22642bc7c6cfc4aed161d0d3124d7e664384205732c18693d78c05b3a1` |
| `tests/test_bridge_doc_export_ingress.py` | `643a61e83b949fd83a2a3014e99c206df61e593952341006a72d55c029b7c5af` |
| `reports/G4_DOC_EXPORT_SECOND_INGRESS_DORMANT_IMPLEMENTATION_20261031.md` | `fdc12055e82e1e4207f506ce8c52fbf6bf12b10054cbf9f7eee57e0d20db2974` |

## Smallest separately bounded next task

Harden the dormant reader against symlink/reparse and TOCTOU conditions, then
wire an opt-in scan through the existing trusted host watcher only. The wiring
must carry the verified exact fence, branch/HEAD, dirty baseline and
allowlist into the existing ledger/claim path, preserve raw JSON pickup and
single-claim semantics, and add no credentials, provider path, new trust root,
or launcher authority. That must be followed by a separate real unattended
host acceptance: one native connected-Doc export, one claim/result, replay as
no-op, and wrong-identity/fence/dirty/allowlist/tamper rejection. The current
worker cannot perform that host step; no restart or process touch was made.
