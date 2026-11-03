# G4 second-ingress timeout independent review

Date: 2026-10-31 (Australia/Sydney)  
Disposition: **PARTIAL**. The dirty four-path implementation is structurally
promising and passed isolated tests, but it is not safe to adopt or activate
from this dirty checkout. No Gate 4 closure or progress credit is claimed.

## Identity and scope

- Branch: `gate3-cg406-remediation`
- HEAD: `e215f3ca82307bc398433c54940ef312b5cbde3e`
- HEAD commit: `bridge: commit gate4:engineering:20261031-g4-doc-export-second-ingress-dormant-v82-sol-0957-04ff9b8f`
- Supplied immutable v83 fence SHA-256:
  `45bcf370446de0eada2efd41e0999c88127a29ca4ce4f3a177643e4355c2db31`
- The v83 fence bytes and timeout result were not present in the local
  checkout; the terminal facts (`CODEX_EXECUTION_TIMEOUT`, 10:33:48Z, no
  bridge-owned commit/report) are taken from the bounded task input. No Drive,
  provider, source, watcher, launcher, or GitHub operation was performed.

The exact dirty diff contains only the four supplied paths: 380 insertions and
44 deletions. Patch SHA-256: `9f60f474d6cc407ac27354083fd8d0d74632ee50`.
No other change was absorbed. Working-tree versus HEAD blob hashes are:

| Path | Working tree | HEAD |
|---|---|---|
| `bridge/bridge.py` | `20cf87749371ba469fa43a5d1776f4c255cd8f0a` | `5a9dd275d5ad038288672c7a10cc2543393275b9` |
| `bridge/g4_doc_export_ingress.py` | `8f997bffa1088467573f28be2bd69b19f0ad85bd` | `d22e0458b5a9a937803c1082b9b09ba4c5d05d5a` |
| `tests/test_bridge_doc_export_ingress.py` | `d84f2ee8784fe1359678ca18cb9ea652371051d6` | `892d169c0d825a623c6a7c62fb12d4e30dea6824` |
| `tests/test_bridge_cutover.py` | `9d25c93d233d89cfededecbf344696860b30909d` | `4990f6bbd35a2e6bb4c014c34c7b70073b2cea18` |

The checkout remains dirty with 155 status entries (19 modified tracked and
136 untracked) in addition to this report. No local commit was made.

## Implemented versus intended

Implemented in the dirty paths:

- `CGDOC1` exports gain explicit opt-in scanning, direct-child checks,
  non-regular/link/reparse rejection, no-follow descriptor reads and opened
  file-identity checks before/during read.
- The accepted export is decoded to exact raw instruction bytes and routed
  through the existing engineering validation, ledger, single-claim and
  result path. Raw JSON pickup remains separate.
- `DocExportIngressConfig` is default-off; the existing CLI construction does
  not enable it.
- Tests add BOM/newline/duplicate/conflict/tamper, canonical identity/SHA,
  authority, HEAD/fence, allowlist, ledger replay/conflict, dirty-baseline,
  default-off/raw-JSON, and opt-in integration coverage.

Not established by these changes:

- Native connected-Doc export, authenticated host pickup, or end-to-end host
  result publication.
- Positive Windows symlink/reparse-point runtime behaviour. The test host
  denied disposable symlink creation with `WinError 1314`; static reparse and
  no-follow checks were inspected, but not runtime-proven here.
- Safe activation on this checkout. A read-only `capture_workspace` /
  `validate_clean_commit_paths` probe rejected the pre-dirty
  `bridge/bridge.py` baseline, and unrelated dirty paths remain protected.

## Tests and probes

Executed in a disposable clone at exact HEAD with only the four dirty files
overlaid, using `python -B`, `PYTHONDONTWRITEBYTECODE=1`, and
`-p no:cacheprovider`:

- `tests/test_bridge_doc_export_ingress.py`: **16 passed, 1 skipped** in
  2.93s. Skip: Windows symlink privilege (`WinError 1314`).
- `tests/test_bridge_cutover.py`: **22 passed, 1 skipped** in 52.03s. Skip:
  explicit real Codex CLI rehearsal (`CG_RUN_REAL_CODEX` not enabled).
- Additional provider-free probe: simulated TOCTOU replacement rejected with
  `Doc export file identity changed before read`; external-parent traversal
  rejected; default-off scan empty; explicit trusted-root scan passed.
- Bridge default-off probe: `_doc_export_paths()` returned empty for a
  present `.txt` export and raw-JSON candidate enumeration remained empty.
- `git diff --check` passed for all four dirty paths.

There were no test failures. Test subprocesses and disposable runtime state
were outside the repository; no raw evidence, credentials, provider data,
Drive material, or logs were added to Git. A final read-only process inventory
showed pre-existing `codex.exe`/`pythonw.exe` processes; this worker did not
start, stop, signal, or otherwise control them, and no watcher operation was
performed.

## Decision and next bounded task

**PARTIAL, do not adopt.** The integration is default-off and its local
failure boundaries are conservative, but the timeout-produced files are dirty
and unadopted, Windows reparse proof is incomplete, and host acceptance is
absent.

Recommend one clean-target, local-only recovery task: reconstruct the reviewed
four-path patch on a clean target at this exact HEAD, add a Windows-capable
reparse/symlink test or retain an explicit privilege limitation, then rerun the
focused suites and verify exact fence/HEAD, dirty-baseline, allowlist,
single-claim and raw-JSON invariants before any separately authorised host
activation. Do not replay the timed-out instruction or activate the new
ingress from this checkout.

Canonical Builder-to-65k state is unchanged: Gate 1 CLOSED, Gate 2 ACTIVE,
12% earned, and independent read-only Product Supervision preserved.
