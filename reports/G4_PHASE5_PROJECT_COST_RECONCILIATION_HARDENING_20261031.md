# G4 Phase-5 project-cost multi-attempt hardening — independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Disposition: **PARTIAL** — bounded local hardening is accepted; project-wide spend authority is not established.

## Authority and path proof

Audited branch `gate3-cg406-remediation` at exact HEAD
`4fbd894f607e11eff03307a5fc75d1955ce69c39`, parent
`a9aa4ccc4b97be7cad80a69aedd59d80314a0ba9`, for instruction
`gate4:engineering:20261031-g4-phase5-project-cost-multi-attempt-hardening-v84-sol-1201-c5be0dd8`.
The supplied immutable v85 fence is recorded as
`a6ce616ba5832c69687bf6c31cc91d41180a896aac72d3cdc38c9f7e2057a3ea`; no
separate v85 fence artifact was present locally for an independent byte
recalculation.

`git diff-tree --no-commit-id --name-status -r 4fbd894f607e11eff03307a5fc75d1955ce69c39`
shows exactly these three committed paths:

1. `src/charitygraph/phase5_project_cost_reconciliation.py` — Git blob
   `27630eb87d99021d531264377e0e2c0ea56e3d4b`
2. `tests/test_phase5_project_cost_reconciliation.py` — Git blob
   `042983fb1062948ac1fa50dbaabc29212a17aae3`
3. `reports/G4_PHASE5_PROJECT_COST_RECONCILIATION_HARDENING_20261031.md` —
   Git blob at the audited commit
   `9ed6c7a0008865e55eff63695112628b38b1f4c6`

The source and test worktree bytes matched the commit. No staged changes or
unrelated dirty material were absorbed. The four unadopted CGDOC1 ingress
paths remained present and untouched:

- `runtime/g4-o1b-controlled-cutover-20261020/bridge/inbox/gate4_engineering_20261031-g4-doc-export-ingress-hardening-optin-v83-sol-1018-50f8ef0a.json`
- `runtime/g4-o1b-controlled-cutover-20261020/bridge/inbox/gate4_engineering_20261031-g4-doc-export-second-ingress-dormant-v82-sol-0957-04ff9b8f.json`
- `runtime/g4-o1b-controlled-cutover-20261020/bridge/inbox/gate4_engineering_20261031-g4-doc-export-second-ingress-independent-accept-v83-sol-1010-4cd6c671.json`
- `runtime/g4-o1b-controlled-cutover-20261020/bridge/inbox/gate4_engineering_20261031-g4-doc-export-timeout-independent-review-v83-sol-1036-f0ec86.json`

## Independent verification

Commands were local-only, provider-free, bytecode-disabled and cache-free;
pytest used a disposable basetemp under `C:\CharityGraph-runtime`:

```text
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-cost-acceptance-d37b380f7aa14abbace813f88c598e9e tests/test_phase5_project_cost_reconciliation.py
15 passed

python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-cost-acceptance-d37b380f7aa14abbace813f88c598e9e tests/test_phase5_project_cost_reconciliation.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_operator_health_runtime_contract.py tests/test_phase5_t4a9_sqlite_accounting_contract.py tests/test_phase5_t4a8_durable_accounting_export.py tests/runtime/test_currency_accounting.py
55 passed
```

The implementation and migration-29 catalogue contract were read against the
architecture, Builder machinery, supervisor protocol, Data documentation
authority, current policies/plans/tests and North Star v0.3. The focused tests
and code inspection verify:

- all safe-exported request, delivery-attempt, physical-attempt and receipt
  rows are retained and reconciled as groups; first-row selection is not used
  for charge identity resolution;
- contradictory request/attempt/physical/receipt identities emit
  `CONTRADICTORY_RUNTIME_IDENTITIES`; unresolved crossings emit
  `AMBIGUOUS_LINKAGE` or `INCOMPLETE_ATTEMPT_HISTORY`, and affected actuals
  are excluded from a known total;
- identical receipt replays are not double-counted, conflicting receipts fail
  closed, and partial linkage does not become a project total;
- reservation identity/amount conflicts and unreconciled releases fail
  closed; gross, active-status reserved, explicit released and net amounts
  remain distinct, while `remaining_spend` stays `UNKNOWN`;
- actual charges, reservations and explicit estimates remain separate and
  use `Decimal`; canonical ordering and SHA-256 output are stable;
- stale/unsupported schema, missing runs and missing authenticated complete
  project-wide ledger coverage are represented as unknown/incomplete rather
  than zero; and
- the allowlist excludes raw prompts, provider payloads/results, credentials
  and transport exceptions. The read-only SQLite fixture hash is asserted
  unchanged by the focused tests.

No provider/model/source acquisition, provider call, spend, publication,
bridge/watchers/process change or GitHub mutation occurred. No new semantic
bug was reproducibly found in this bounded review.

## Unresolved authority and disposition

The local diagnostic does not establish a source-owned provider route,
pricing authority, FX authority, invoice/exactly-once effect reconciliation,
or an authenticated complete project ledger. The cumulative approved AUD10
provider-call ceiling remains unknown from this export and is not a spend
ledger. These gaps prevent a full PASS and do not authorise provider work.

North Star v0.3 impact is limited to internal operational evidence supporting
sections 13 Finances, 14 Funding / dependencies, and 20 Evidence / coverage /
freshness / corrections. It is not charity expenditure knowledge or a public
release projection. Gate 1 remains CLOSED, Gate 2 ACTIVE, 12% earned; this
report claims no scorecard progress, Gate 4 closure or release.

Highest-value successor: obtain an independently authenticated, source-owned
project-ledger export with exact run coverage, provider contract identity,
pricing/FX snapshots, reservation-release semantics and receipt identity;
then add a read-only acceptance fixture for stale scope, retries and
contradictory identities.

No private material, runtime database, cache, prompt, model response,
credential, raw source or generated public projection was added or modified.
