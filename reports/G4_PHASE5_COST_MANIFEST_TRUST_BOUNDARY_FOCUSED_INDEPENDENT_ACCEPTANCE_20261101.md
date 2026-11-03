# G4 Phase-5 cost manifest trust-boundary focused independent acceptance

Date: 2026-11-01 (Australia/Sydney)  
Target HEAD: `7654e9c8ccb370f9fa4f3cd43fdd50a76ede477f`  
Parent: `5fe83f43aea7c8f88c6ad0519bf4dc3bcd2adff2`  
Branch: `gate3-cg406-remediation`  
Fence: v89, SHA-256 `e72ff8fa5eaaa6f0b45e8aae463f508f68d4a40446f023ec5ab50cdf776f9883`

## Disposition

- **Code semantics: PASS.** The focused trust-boundary challenge fails closed.
- **Real-world cost authority: FAIL.** No independently authenticated project-wide inventory, invoice, price/FX evidence, or provider-side exactly-once evidence was established.
- **Gate 4 readiness: FAIL.** This review supports no release, gate closure, scorecard change, or AUD 10 remaining-spend claim.

## Scope and repository evidence

This was a new report-only review; the timed-out prior instruction was not
replayed or reused. `git diff-tree --no-commit-id --name-status -r
7654e9c8ccb370f9fa4f3cd43fdd50a76ede477f^ 7654e9c8ccb370f9fa4f3cd43fdd50a76ede477f`
resolves to exactly:

```text
A reports/G4_PHASE5_COST_MANIFEST_TRUST_BOUNDARY_REPAIR_20261101.md
M src/charitygraph/phase5_project_cost_reconciliation.py
M tests/test_phase5_project_cost_reconciliation.py
```

The pre-existing dirty/untracked workspace set was preserved. Before this
report was written, the tracked source/test dirty check was clean; no existing
dirty path, bridge file, fence, ledger, cache, or prior report was edited.

## Independent verification

An exact-HEAD `git archive` was expanded under
`C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101`, outside the
live checkout. Runs used `PYTHONDONTWRITEBYTECODE=1`,
`-p no:cacheprovider`, and basetemp outside the repository.

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101-pytest C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101\tests\test_phase5_project_cost_reconciliation.py
30 passed in 14.54s
```

The related bounded command covered the eight operator-health/accounting test
files `tests/test_phase5_operator_health.py`,
`tests/test_phase5_operator_health_catalogue.py`,
`tests/test_phase5_operator_health_runtime_contract.py`,
`tests/runtime/test_phase5_run_diagnostics_catalog.py`,
`tests/runtime/test_currency_accounting.py`,
`tests/runtime/test_legacy_cost_entry.py`,
`tests/runtime/test_s0_accounting.py`, and
`tests/test_phase5_t4a9_sqlite_accounting_contract.py`:

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101-related-pytest-2 C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101\tests\test_phase5_operator_health.py C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101\tests\test_phase5_operator_health_catalogue.py C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101\tests\test_phase5_operator_health_runtime_contract.py C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101\tests\runtime\test_phase5_run_diagnostics_catalog.py C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101\tests\runtime\test_currency_accounting.py C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101\tests\runtime\test_legacy_cost_entry.py C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101\tests\runtime\test_s0_accounting.py C:\CharityGraph-runtime\g4-cost-manifest-trust-accept-20261101\tests\test_phase5_t4a9_sqlite_accounting_contract.py
exit 0; 84 passed in 22.05s
```

## Focused trust-boundary result

`_trusted_population_inventory` now accepts caller manifests only for bounded
diagnostics and rejects any `scope.kind` other than `bounded`
(`src/charitygraph/phase5_project_cost_reconciliation.py:284-333`). A
structurally complete caller object with `state=source_owned`, provenance,
complete evidence, matching `run:one`/`run:two`, `scope.kind=project_wide`,
`source_owned=True`, `authenticated=True`, and forged attestation fields is
therefore rejected before it supplies expected population IDs. The population
diagnostic remains `unknown` with `MISSING_TRUSTED_RUN_INVENTORY`
(`:336-353`).

The complete local two-run schema-29 fixture consequently retains
`observed_actual_subtotal = AUD 3.3`, but returns `NOT_AUTHORITATIVE`, null
`authoritative_total`, and null `remaining_spend`. It cannot self-attest
historical population (`tests/test_phase5_project_cost_reconciliation.py:445-511`).
The explicit duplicate and omitted-ID cases also fail closed
(`tests/:514-542`).

The focused suite additionally passed the requested negative coverage:
missing pricing/FX and usage (`:108-119`), retries and contradictory
attempt/receipt identities (`:181-216`, `:288-300`), reservation/release
uncertainty (`:316-346`), and `send_ambiguous` with no cost row
(`:545-564`). Known actual rows remain visible while unsupported rows do not
become zero; the mixed unknown-cost case retains the known `AUD 1.1` subtotal
and remains non-authoritative (`:567-580`). Authority still requires complete
population, supported schema, reconciled actual charges, and no unresolved
blockers (`src/charitygraph/phase5_project_cost_reconciliation.py:1152-1175`).

The SQLite adapter remains read-only and bounded: it uses
`mode=ro&immutable=1`, `PRAGMA query_only=ON`, allowlisted tables, and selected
run IDs (`src/charitygraph/phase5_operator_health_catalogue.py:228-326`). No
provider/model call, acquisition, Drive access, private evidence, credentials,
raw provider data, GitHub mutation, publication, release, or gate action was
performed.

## Remaining evidence gap and successor

The synthetic fixture proves deterministic Decimal reconciliation and the
fail-closed caller-manifest boundary only. It does not prove historical
population, invoice truth, provider exactly-once effects, pricing/FX authority,
or an AUD 10 cumulative remainder. The next bounded authorised substantive
step is a trusted source-owned cumulative inventory evidence/adapter with
independent authenticity, scope, completeness, unique run IDs, and lineage;
alternatively, perform a second-ingress independent acceptance of that
evidence. No successor was dispatched by this review.
