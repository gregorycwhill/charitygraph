# G4 T4A6 independent acceptance

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free, report-only  
Disposition: **PARTIAL**

## Commit and boundary

The local branch is `gate3-cg406-remediation` at
`59d982d0862c76d7af5bcefd8ba1e138e31af637`, with fence v56
`e9996da194468a768b680cead3a4b72df20b9281c62dede47fc1c41e2f23b7fb`.
The commit is a single-parent, non-merge direct child of
`9993d9d64d035a395ad29da6b5f4841d4c1d6bb9` and changes exactly these three
paths:

- `src/charitygraph/phase5_t4a_project_budget_snapshot.py`
- `tests/test_phase5_t4a_project_budget_snapshot.py`
- `reports/G4_T4A6_READONLY_PROJECT_BUDGET_SNAPSHOT_20261029.md`

The pre-review worktree already had unrelated dirty tracked and untracked
paths. The three target paths were clean before and after review; no dirty
baseline path was absorbed or modified. No provider, model, network,
credential, source acquisition, spend, reservation, GitHub/Drive action,
publication, watcher or process action occurred.

SHA-256 of the committed/worktree target files:

| Path | SHA-256 |
| --- | --- |
| `src/charitygraph/phase5_t4a_project_budget_snapshot.py` | `AC202755D4A42ED812A03B80688F239ABB1763F110FA2BC684132B499A37E24F` |
| `tests/test_phase5_t4a_project_budget_snapshot.py` | `9AD0239F88BFE02D17B2E2ACF512B8AC65D2FDA06262749F3649219C24933116` |
| `reports/G4_T4A6_READONLY_PROJECT_BUDGET_SNAPSHOT_20261029.md` | `1BA36514C208791A4BBC29AD36AC08051AAF80BCA182AB329BB3735F50D9908F` |

## Independent focused verification

Exactly one independent invocation was run:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts="" --basetemp C:\CharityGraph-runtime\g4-t4a6-independent-acceptance-20261029 tests/test_phase5_t4a_project_budget_snapshot.py`

Exit code: **0**. Result: **6 passed, 0 failed**. The external basetemp,
disabled bytecode and disabled pytest cache provided no repository test/cache
write. The worker report's earlier history (6 failed, then 4 passed/2 failed,
then direct in-process replay 6 passed after corrections) is not counted as a
clean independent pytest run; the result above is the independent run for the
committed files.

The worker report's claim that `git diff --check` passed is not reproducible
against this exact commit: the committed allowlisted report has trailing
whitespace and the committed test has a blank line at EOF. This is a hygiene
defect only; no files were edited to repair it.

## Technical and product assessment

**Code acceptance: ACCEPT for the narrow provider-free boundary.** Inspection,
the six focused tests and the exact file hashes support:

- canonical deterministic replay and order-invariant normalization of supplied
  mapping/list inputs;
- AUD actual and outstanding-reservation arithmetic across cohorts, with
  reservation/release reconciliation and identity-key deduplication;
- retry and physical-attempt identity checks, including cross-cohort and
  contradictory evidence rejection;
- fail-closed missing, pending, ambiguous, unpriced and stale/as-of evidence;
- a separately supplied manifest with explicit project-wide coverage,
  accounting-source and authority/provenance fields;
- candidate bytes and SHA-256 as reproducibility output only. The API has no
  trusted-pin input, reports `independent_trust: NOT_SUPPLIED`, has no budget
  attestation, no request ticket and fixes `send_authorization` to
  `not_authorized_for_send`;
- no catalogue, database, filesystem, network or provider side effect in the
  adapter. Its imports are limited to deterministic standard-library
  processing plus canonical JSON bytes.

The source/authority checks validate caller-supplied shape and linkage, but do
not independently prove that the manifest authority, source hashes or coverage
claims are truthful. In particular, the adapter is not itself a source-owned
ledger authority.

**Factual product acceptance: NOT ACCEPTED.** The current project-wide factual
snapshot is still missing. Existing `budget_position` and
`accounting_budget_position` catalogue views are cohort-scoped mutable runtime
accounting calculations, not an independently trusted project-wide export.
Empty or absent evidence is therefore not interpreted as zero spend.

**T4A5 mismatch and coverage gaps:** T4A5 still declares
`proposed_max_one_request_reservation_aud` as `str | Decimal` while its parser
accepts only strings; a `Decimal` proposal fails closed. T4A6 does not bypass
that defect. The focused tests do not independently cover duplicate JSON keys,
naive/future timestamps, source-provenance hash mismatch or staleness, exact
provider-attempt-to-retry linkage, and a real source-owned project-wide export.

This review accepts neither a live provider contract/route, current pricing or
FX authority, real-send readiness, nor Gate 4 closure. It accepts only the
bounded code path as a read-only candidate adapter.

## Smallest next bounded task

First, perform one provider-free repair/test slice for the declared T4A5
`Decimal` contract and the listed edge cases, including independent source
authority/hash linkage. Separately, obtain a current trusted accounting export
from the existing durable runtime owner, complete across cohorts, retries,
physical attempts, reservations, actuals and pricing/FX identities; then feed
that export through T4A5. Do not infer zero, reserve, send or treat the
candidate SHA as an attestation.
