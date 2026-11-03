# G4 T4A11 immutable catalogue independent acceptance

Date: 2026-10-30 (Australia/Sydney)
Worker: bounded G4-O1C, report-only, local and provider-free

## Disposition

| Area | Result | Reason |
|---|---|---|
| Narrow T4A11 implementation | **PARTIAL** | The preflight is mechanically careful and fail-closed for the tested cases, but it is not a concurrency-safe immutable snapshot or an independently authoritative source/migration attestation. |
| Factual project-wide accounting | **REJECT** | No current, complete, source-owned project-wide accounting snapshot was supplied or established. T4A11 explicitly leaves completeness, pricing, FX, route and AUD spend `NOT_ATTESTED`. |
| Focused verification | **PASS** | Fresh focused pytest: exit 0, 7 passed. |

## Exact commit and dirty-baseline check

Observed locally:

- Branch: `gate3-cg406-remediation`
- HEAD: `ebd8fdb270863aab05642c76b10eff40b2a6872d`
- Parent: `a850f8104cf3e3f9150df27c4671ab084ba0453e`
- Supplied fence: `v61`, SHA-256 `c96b1a435d3b4c5b806c97e597dc868cf146a561b4611db7a5549daf79b069a6`

The direct-child diff is exactly three added paths:

1. `src/charitygraph/phase5_t4a11_immutable_catalogue_snapshot.py`
2. `tests/test_phase5_t4a11_immutable_catalogue_snapshot.py`
3. `reports/G4_T4A11_IMMUTABLE_CATALOGUE_SNAPSHOT_20261030.md`

The implementation and test SHA-256 values match the preceding implementation
report: `6d813dc01e6c2499b6f9e1ae6dfa56e7921c8077f34a0d4ec86bd05b9bdb9901`
and `0f8cc7cb7d91b5c3b05ca2bd5d2a30294cda79b85ed54e45ac90c93d239c54e9`.
That report is historical and records the pre-commit HEAD/fence (`a850f...`,
v60), not the current acceptance identity. Its claim that `git diff --check`
was clean is not reproducible for the committed report: lines 3–5 contain
Markdown trailing spaces. No existing dirty path was changed.

## Fresh focused test

Ran exactly one fresh focused test with `PYTHONDONTWRITEBYTECODE=1`, Python
`-B`, no pytest cache provider, empty `addopts`, and an external basetemp:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts="" --basetemp C:\CharityGraph-runtime\g4-t4a11-independent-pytest-20261030-042620481 tests/test_phase5_t4a11_immutable_catalogue_snapshot.py
```

Result: `....... [100%]`, `7 passed in 0.66s`, exit `0`. The repository status
had 119 entries before and after, with no status change and no unexpected
repository path. Only synthetic SQLite fixtures in the external basetemp were
used; no runtime database or existing sidecar was opened or modified.

## Technical assessment

What is sound in the bounded preflight:

- It binds the caller-supplied expected main-file hash to the supplied identity,
  rejects missing/non-regular/symlink files, and rejects pre-existing `-wal`,
  `-shm` and `-journal` sidecars.
- It opens through a URI containing `mode=ro&immutable=1`, enables and checks
  `PRAGMA query_only`, checks the SQLite header and safe journal modes, rejects
  WAL-format headers, and rechecks the main hash and sidecars after close.
- It requires a `schema_migrations` table with the expected columns, contiguous
  positive versions and a caller-selected maximum version. Row counts are
  reported mechanically; empty views and project completeness, pricing, FX,
  route and AUD spend remain explicitly non-attested.

The limits prevent full acceptance of an “immutable catalogue snapshot”:

- `immutable=1` stops this SQLite connection consulting WAL/SHM state; it does
  not stop another process writing, replacing or briefly sidecar-ing the path.
  The separate hash/header reads and post-close checks have no file descriptor
  snapshot or writer lock. A sidecar or WAL commit that appears and disappears
  between checks, or an ABA replacement returning to the same bytes, can evade
  them. The tests contain no race, transient-sidecar or external-writer case.
- Source identity is caller data. The code validates shape, closed/active/
  mutable flags and hash equality, but does not bind the identity to a trusted
  source-owner manifest, signature or catalogue authority. `CANDIDATE_NOT_ATTESTED`
  is therefore the correct successful status; it is not source attestation.
- Migration validation does not verify migration names/checksums, SQLite
  `user_version`, or the current supported migration (`runtime/migrations.py`
  is at version 29). A caller can select an older expected version or provide
  structurally plausible migration rows. This is useful structural checking,
  not migration-authority verification.
- The seven tests do not cover invalid headers, symlink/non-regular files,
  source-identity hash mismatch, migration mismatch/sequence/checksum or
  `user_version` disagreement, journal creation during inspection, or a
  monkeypatched connection proving the negative paths perform no SQLite I/O.

The WAL rejection is appropriate for the current runtime design: the ordinary
`SQLiteCatalog` enables WAL for file-backed catalogues. A runtime owner must
first provide a closed, independently pinned main-file snapshot; this helper
must not be used to reinterpret a live WAL catalogue as complete.

## Accounting and product boundary

T4A10 remains the governing local factual accounting evidence: its inspected
source-bearing catalogue was stale/partial, lacked project-wide coverage and
independent pricing/FX/route authority, and did not justify a cumulative AUD
spend claim. T4A11 does not repair any of those facts and makes no provider,
model, network, credential, acquisition, reservation, spend, publication,
release or send-authority claim.

This advances only North Star v0.3 §20, Evidence / coverage / freshness /
corrections, at the Builder control-plane snapshot boundary. It does not
establish North Star §13 Finances or §14 Funding / dependencies, nor any
subject knowledge in sections 1–19. Public contract 0.5 and release bytes are
untouched.

## One factual next product task

Have the runtime owner produce one provider-free, closed snapshot manifest for
the current catalogue, independently pinning owner/path, main-file SHA-256,
schema/migration identity, as-of time, project/cohort/run population and every
active, failed, pending, held, ambiguous, unpriced and unknown state. Bind
pricing, FX and provider route authority separately. Accept it only after
mechanical joins and reverse links reconcile and the pin is independently
verified; until then, keep project-wide accounting `REJECT`/unattested. This is
one runtime-owner evidence task, not a request for another synthetic-test loop.

No private source material, credentials, prompts, model responses or runtime
payloads were added. This report is the only new repository path from this
acceptance task; no code or test edits were made.
