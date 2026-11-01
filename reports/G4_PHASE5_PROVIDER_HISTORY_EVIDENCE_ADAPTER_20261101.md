# G4 Phase-5 provider-history evidence adapter

Date: 2026-11-01 (Australia/Sydney)  
Disposition: **PARTIAL** — provider-free local adapter implemented; authenticated
provider history and project-wide completeness remain unverified.

## Bounded change

This tranche adds one pure, read-only seam at
`src/charitygraph/phase5_provider_history_evidence_adapter.py`, its focused
tests, and this report. It accepts explicitly supplied immutable export bytes
and source/acquisition metadata, records the export SHA-256, normalises only a
small provider-neutral JSON envelope, and emits canonical `OBSERVED` evidence
with source origin, scope, time window, schema/version, missingness and
identity/linkage diagnostics. Raw bytes are not retained by the adapter or
added to Git.

The adapter delegates run-population comparison to the existing
`phase5_run_inventory_audit` contract when reconciliation inputs are supplied;
it does not create a ledger, aggregate charges, infer FX/pricing, or produce an
authoritative total or remaining budget. Existing cost and budget contracts are
unchanged.

## Safety result

The evidence projection can preserve a valid observed subset, but its authority
decision is always fail-closed in this bounded task. Caller-provided
`source_owned`, `authenticated`, `complete`, signed-looking strings, matching
IDs, timestamps, project-wide flags and cost values are treated as observations
or diagnostics only. Missing or unverified host attestation and missing
source-owned completeness produce explicit blockers; unsupported/stale formats,
malformed identity, duplicate/conflicting records, broken foreign keys, mixed or
partial windows, source silence and missing cost/FX/pricing remain visible and
never become zero or complete.

## Real-world gap / exact prerequisite

No independently authenticated provider-native cumulative run index, billing or
receipt export was available in the local repository, and no existing trusted
host input safely establishes provider provenance inside this task. The exact
integration prerequisite is a host-authenticated, read-only ingress that
delivers immutable cumulative run-index and billing/receipt export bytes plus a
verifiable attestation binding source identity, acquisition/observation times,
scope/window, schema/version, completeness boundary, and exact byte SHA-256.
That ingress must then feed the existing run-inventory and project-cost
reconciliation contracts. Until independently accepted, the adapter's
`project_wide_authoritative`, `authoritative_total`, and `remaining_spend`
fields remain false/null.

## Verification

Focused adapter command:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-provider-history-focused-20261101-v3 tests\test_phase5_provider_history_evidence_adapter.py
20 passed in 0.94s
```

Focused plus the existing cost/inventory/operator/budget contracts:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-provider-history-regression-20261101 tests\test_phase5_provider_history_evidence_adapter.py tests\test_phase5_run_inventory_audit.py tests\test_phase5_project_cost_reconciliation.py tests\test_phase5_operator_health_runtime_contract.py tests\test_phase5_t4a_project_budget_snapshot.py
83 passed in 5.26s
```

Additional existing operator-health/catalogue diagnostics:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-provider-history-related-20261101 tests\test_phase5_operator_health_catalogue.py tests\test_phase5_operator_health.py tests\runtime\test_phase5_run_diagnostics_catalog.py
46 passed in 10.36s
```

The final implementation/test SHA-256 values are:

```text
751d48a5747ae3408a704043fca1cc4554b75005258f963b5e620fa5b6344898  src/charitygraph/phase5_provider_history_evidence_adapter.py
c147bb767fbaa9c59cef0b448fc0d325e6601361e8d925f514c463ffc2f396c7  tests/test_phase5_provider_history_evidence_adapter.py
```

The implementation covers:

- immutable raw-byte SHA binding without raw-byte retention/output;
- source/acquisition identity, scope, window, schema/version and missingness;
- permutation-stable normalisation of records and reconciliation inputs;
- explicit duplicate/conflict, identity contradiction, mixed-window,
  source-silence, orphan/unknown-ID and broken-foreign-key diagnostics;
- receipt-level cost, currency, pricing and FX missingness without sums;
- caller-forgery resistance for authentication/completeness-shaped fields;
- existing `phase5_run_inventory_audit` delegation and reference-only handling
  for the existing project-cost contract; and
- permanent `FAIL_CLOSED` authority with null authoritative total/remainder.

The real-world evidence gap remains: no independently authenticated provider
native cumulative run index or billing/receipt export, trusted host attestation,
or source-owned completeness boundary is present locally. The exact next
integration prerequisite is a host-authenticated read-only ingress that binds
immutable cumulative run-index and billing/receipt bytes to source identity,
acquisition/observation timestamps, scope/window, schema/version, a proven
completeness boundary and exact SHA-256, then supplies those records to the
existing run-inventory and project-cost reconciliation contracts. This task
does not invent that verifier, acquire it, or claim provider completeness.

The repository already contained unrelated dirty tracked and untracked paths at
launch; they were not edited, staged or absorbed. No raw/private evidence,
provider export, runtime database, cache, credential, prompt, model response or
generated public projection was added to Git. No provider/model/source access,
spend, Drive/bridge/watcher action, GitHub mutation, publication, release, gate
closure or follow-on dispatch occurred.

No provider/model calls, source acquisition, credentials, Drive/bridge/watcher
operations, GitHub mutation, publication, release, gate closure or paid spend
are in scope.
