# G4 T4A8 read-only durable accounting source export

Date: 2026-10-29 (Australia/Sydney)
Worker: bounded G4-O1C, provider-free
Branch: `gate3-cg406-remediation`
Starting HEAD: `aeca5ce1bc57f381a0612f7b302c83db1680569b`
Fence: `v57` / `546fd536da2fa28c91bcf78583323146525090d453794d06718e85d5e70ce3b`

## Disposition

Implemented a side-effect-free, source-bound adapter in
`src/charitygraph/phase5_t4a8_durable_accounting_export.py`.
`ReadOnlyDurableAccountingView` accepts already-open caller-owned views of the
existing durable accounting and physical-attempt record classes. The adapter
requires explicit source authority, content identity, retention identity and
project-wide coverage assertions; inventories cohorts, runs, logical tasks,
retries, reservations, cost entries and provider attempts; reconciles pricing /
FX identities; and delegates candidate construction to the existing T4A6
canonical format. It does not create a ledger, open the catalogue, mutate a
database, read or write a file, contact a provider, or issue a send ticket.

The adapter returns `CANDIDATE_NOT_ATTESTED` only when the supplied source view
reconciles mechanically. Missing authority/coverage/data is
`NOT_ATTESTABLE`; unresolved, unpriced or unknown physical attempts are
`BLOCKED`. Every result remains `independent_trust: NOT_SUPPLIED` and
`send_authorization: not_authorized_for_send`. T4A5/T4A7 independent pin
verification remains separate.

No live durable source view was available or opened in this tranche. The
passing candidate (`1901cb825b13c48b032ded16ce5cd55a99678f208afd4903a8c68b5d2cb79468`,
1,773 bytes) is generated from focused in-memory contract fixtures only; it is
not project-wide factual evidence and must not be used as a ledger snapshot.

## Durable owner and boundary

The inspected authoritative runtime schema is the existing SQLite catalogue:
`cohorts`, `runs`, `tasks`, `task_attempts`, `budget_reservations`,
`cost_entries`, `physical_attempts`, `physical_attempt_members`, and
`provider_request_attempts`. Migration 20 binds accounting amounts/currency;
migrations 10 and 13 bind physical/provider attempt identity. Existing
`budget_position` / `accounting_budget_position` views remain cohort-scoped;
this task adds no second ledger or project-wide database query path.

## Verification

Exactly two focused pytest invocations were used, both with
`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts=''`
and unique external `--basetemp` directories:

1. First run: exit **0**, **7 passed, 0 failed**.
2. Final run: exit **0**, **8 passed, 0 failed**.

The tests cover all-cohort/retry reconciliation without physical double
counting; duplicate records; ambiguous, unpriced and unknown physical states;
missing coverage; missing/unauthorised retention identity; independent pin
separation; deterministic replay; canonical bytes; and no filesystem/network
side effect. AST parsing and targeted `git diff --check` also passed.

## Hash citations

| Material | SHA-256 |
|---|---|
| New adapter | `6fc68a6a1ccbca9f8188c38d36286505f34af100882f8ca34264b32590395fe0` |
| New focused tests | `321c1061ccd5f93cbdcf62c27b5d7cb4e0f4bfd11191436d925d3cfc2e327bf5` |
| Durable source schema (`runtime/migrations.py`) | `75b257c5756dd49155a4b11f0acd7dc32b45f86d5a27981e339a154f2661380c` |
| Reused T4A6 candidate adapter | `ac202755d4a42ed812a03b80688f239abb1763f110fa2bc684132b499a37e24f` |

The exact hashes above were collected before writing this report. The report's
own digest is collected externally because embedding it would change its bytes.

## Commit boundary

The requested exact-three-path local commit could not be staged. `git add` exit
code was **128** with: `fatal: Unable to create
'C:/CharityGraph-clean/charitygraph/.git/index.lock': Permission denied`.
No path was staged, no commit was created, and no permission or unrelated dirty
path was changed.

No private evidence, runtime database, cache, credentials, raw source,
provider payload or generated test artefact was added to Git. No provider/model/
network/credential call, acquisition, spend, reservation, publication,
GitHub/Drive action, watcher/process action, release, gate closure or real-send
authority occurred. This tranche is implementation evidence only and cannot
authorize real-send or Gate 4 acceptance.
