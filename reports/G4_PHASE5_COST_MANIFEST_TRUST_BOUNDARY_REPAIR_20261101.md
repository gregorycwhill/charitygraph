# G4 Phase-5 cost manifest trust-boundary repair

Date: 2026-11-01 (Australia/Sydney)  
HEAD: `5fe83f43aea7c8f88c6ad0519bf4dc3bcd2adff2`  
Branch: `gate3-cg406-remediation`  
Fence: v88, SHA-256 `22b9d57358e7cf6a190150165e11e658c730fe6fe5c3b4c60c2a0960d68d18a2`

## Outcome

**PASS — bounded code repair.** Caller-provided manifests declaring
`scope.kind=project_wide` are no longer accepted as trusted inventories,
including complete, source-owned-shaped manifests with matching local run IDs
or extra claimed attestation fields. They produce
`MISSING_TRUSTED_RUN_INVENTORY`, `NOT_AUTHORITATIVE`, null
`authoritative_total`, and null `remaining_spend`.

Bounded manifests remain available for per-run diagnostics and deterministic
Decimal observed subtotals. Existing accounting vetoes remain in force.

## Verification

With `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `PYTHONPATH=src`, and
basetemp outside the repository:

- `tests/test_phase5_project_cost_reconciliation.py`: **30 passed**
- Related operator-health/accounting files: **108 passed**
- Combined: **138 passed**

Added regressions cover the exact forged matching-ID bypass, complete
source-owned claims with extra authentication/completeness fields, malformed
manifests, duplicate IDs, preserved observed subtotal `3.3`, and null
project-wide authority fields. The allowlisted code/test diff is clean under
`git diff --check`; an unrelated pre-existing dirty report has a separate
trailing-whitespace diagnostic and was not edited.

Only these code/test paths changed, plus this report:

- `src/charitygraph/phase5_project_cost_reconciliation.py`
- `tests/test_phase5_project_cost_reconciliation.py`
- this report

No provider/model call, source acquisition, Drive, watcher, GitHub, release,
publication, gate closure, private evidence, raw provider data, credentials,
or secrets were used or written. Existing unrelated dirty paths were
preserved.

## Remaining evidence gap

**FAIL — actual project-wide spend authority remains unavailable.** This
checkout has no independently authenticated source-owned complete cumulative
run-inventory adapter or registry. No signing key, credential, historical run,
provider charge, synthetic registry, or project-wide AUD 10 remainder was
invented. A future separately proven trusted-source adapter must establish
authenticity, scope, completeness, unique run IDs, and lineage before
project-wide authority can be enabled.
