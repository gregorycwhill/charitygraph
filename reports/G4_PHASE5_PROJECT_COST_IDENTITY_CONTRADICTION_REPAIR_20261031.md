# G4 Phase-5 project cost identity contradiction repair

Date: 2026-10-31 (Australia/Sydney)  
Branch/HEAD: `gate3-cg406-remediation` / `4fbd894f607e11eff03307a5fc75d1955ce69c39`  
Supplied immutable fence v85: `a6ce616ba5832c69687bf6c31cc91d41180a896aac72d3cdc38c9f7e2057a3ea`

## Disposition

Bounded code/test repair complete; expected semantic disposition is **repaired, pending separate independent semantic acceptance**. This report claims no Gate 4 closure or scorecard credit.

## Repair

- A selected receipt is now checked against the selected request/attempt physical identity. A missing physical identity is `INCOMPLETE_RUNTIME_LINKAGE`; a disagreement is `CONTRADICTORY_RUNTIME_IDENTITIES`, so the actual cannot be known or counted as spent.
- `task_attempts.provider_request_id` is now included in the existing exact provider-request identity comparison. A disagreement fails closed.
- Focused tests cover both negative cases, valid same-attempt reconciliation, exact-ID disambiguation, and duplicate-receipt non-double-counting. Existing grouping, replay/conflict exclusion, reservation/release accounting, unknown remaining spend, Decimal arithmetic, schema gating, and safe projection paths remain covered.

## Verification

Direct worktree focused command (cache-free, bytecode-free, disposable basetemp):

```text
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-cost-identity-repair-basetemp-focused tests/test_phase5_project_cost_reconciliation.py
18 passed in 1.86s
```

Clean isolation used a `git archive --format=zip HEAD` overlay at `C:\CharityGraph-runtime\g4-phase5-cost-identity-repair-overlay-zip-4fbd894f`, with only the two candidate files overlaid, then ran:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-cost-identity-repair-basetemp-related-overlay-zip tests/test_phase5_project_cost_reconciliation.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_operator_health_runtime_contract.py tests/runtime/test_currency_accounting.py
37 passed in 3.63s
```

Negative evidence: the receipt physical-attempt mutation yields `unknown`, no charge, and `CONTRADICTORY_RUNTIME_IDENTITIES`; the task-attempt provider-request mutation yields the same fail-closed result. The positive cases reconcile `1.1` AUD for the valid physical identity, select the exact declared request among multiple requests, and retain one charge for a duplicate receipt.

`git diff --check -- src/charitygraph/phase5_project_cost_reconciliation.py tests/test_phase5_project_cost_reconciliation.py` passed. A full-worktree `git diff --check` also reports one pre-existing trailing-whitespace line in `reports/G4_T4A4_SOURCE_OWNED_PROVIDER_CONTRACT_REGISTRY_20261029.md`; that dirty path was not touched. The pre-existing dirty hardening report was preserved byte-for-byte (worktree SHA-256 `f4b2c07c430c3e6f4a49aace62d14f2961b7e3115d2f71de6b1e78d6122e7268`). Source, focused test, and this new report are the only task paths written; unrelated dirty paths were not absorbed.

No provider calls, model calls, source acquisition, external network, expense, publication, release, GitHub mutation, watcher/launcher action, Drive operation, gate closure, or successor dispatch occurred. The cumulative AUD10 provider cap is untouched. Full acceptance remains subject to the separately requested independent semantic review.
