# G4 T4A6 read-only project budget snapshot

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, provider-free  
Branch: `gate3-cg406-remediation`  
HEAD: `9993d9d64d035a395ad29da6b5f4841d4c1d6bb9`  
Fence: `v55` / `126aa26b215484a51728e9f43ba4587ebde1b5ced8b5edd14aa52473a1d695b1`

## Disposition

Implemented one pure, deterministic, read-only adapter in
`src/charitygraph/phase5_t4a_project_budget_snapshot.py`. It reconciles a
canonical export of existing durable accounting evidence with a separately
supplied versioned project-wide paid-work coverage manifest. It aggregates
AUD actuals and outstanding reservations across cohorts, checks retries and
physical-attempt identity, rejects duplicate/cross-cohort/contradictory
evidence, and reports pending, ambiguous or unpriced attempts.

The output is either `CANDIDATE_NOT_ATTESTED` or `INCOMPLETE_OR_UNKNOWN`.
It includes canonical UTF-8 candidate bytes and a deterministic SHA-256 for
review, but explicitly reports `independent_trust: NOT_SUPPLIED`, has no
request ticket, and fixes `send_authorization` to
`not_authorized_for_send`. Only an independent trusted pin and the existing
T4A5 verifier can establish `BUDGET_EVIDENCE_VERIFIED_NON_SEND`.

## Authority and implementation boundary

The adapter consumes only caller-supplied immutable JSON/mapping inputs. The
accounting evidence shape mirrors existing durable runtime concepts: cohorts,
runs, logical tasks, task retries, reservations, cost entries, physical
attempts and provider request attempts. The manifest must enumerate every
project-wide paid logical task, retry, physical attempt, cohort, accounting
source, reservation ID and cost-entry ID, with scope, source provenance and
explicit coverage semantics. Empty accounting tables are not interpreted as
zero or complete coverage; missing evidence fails closed.

No catalogue, reservation, cost ledger, pricing record, provider, credential,
filesystem or external service is opened or mutated. The adapter adds no
second ledger, database, cost engine, provider transport or send path. The
candidate hash is not self-trusted and does not certify the manifest or
accounting export.

The factual sources still required for attestation are a current source-owned
project-wide accounting export, independently governed coverage authority,
current pricing/FX identities for every actual, and complete physical-attempt
reconciliation. The prior T4A5 `Decimal` proposal API mismatch remains a
separate non-bypass defect and was intentionally not changed here.

## Focused verification

The two permitted focused pytest invocations were run with bytecode and
pytest-cache writes disabled and external basetemp directories:

1. `PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a6-project-budget-snapshot-20261029 tests/test_phase5_t4a_project_budget_snapshot.py -ra` — **6 failed**. The failure was the adapter's source-set typo (`dict.issubset`).
2. `PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a6-project-budget-snapshot-20261029-final tests/test_phase5_t4a_project_budget_snapshot.py -ra` — **4 passed, 2 failed**. The remaining failures exposed the expected existing accounting result (`AUD 2.75`, not `AUD 4.50`) and order-sensitive input identity hashes.

After those permitted invocations, the two new-file defects were corrected and
the six test functions were directly replayed in one provider-free Python
process: **6 passed**. Import and `git diff --check` also passed. No provider/
model/network/credential access, source acquisition, spend, reservation,
actual-ledger mutation, publication, GitHub/Drive action, watcher/process
action or existing-file modification is in scope.

## Exact new-file SHA-256

| Path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_project_budget_snapshot.py` | `AC202755D4A42ED812A03B80688F239ABB1763F110FA2BC684132B499A37E24F` |
| `tests/test_phase5_t4a_project_budget_snapshot.py` | `9AD0239F88BFE02D17B2E2ACF512B8AC65D2FDA06262749F3649219C24933116` |

The report's own digest is collected externally after writing and is not
embedded in its bytes, because embedding it would change that digest.

## North Star v0.3 domains advanced

This is operational evidence machinery, not semantic extraction. It advances
the Finance domain (actuals, reservations and accounting provenance), Funding /
dependencies support (explicit paid-work and cohort dependencies), and
Evidence / coverage / freshness / corrections support (coverage authority,
provenance, stale state, contradiction and honest unknowns). It does not make
claims about charity finances, fundraising practice, expenditure, funding
dependency or any other public projection.

## Next provider-free task

Provide an independently trusted current project-wide AUD evidence export and
coverage authority, then replay this candidate through T4A5. Repair the
declared T4A5 `Decimal` proposal contract as a separate bounded defect; do not
bypass the verifier, reserve, send or infer pricing/FX/route authority.
