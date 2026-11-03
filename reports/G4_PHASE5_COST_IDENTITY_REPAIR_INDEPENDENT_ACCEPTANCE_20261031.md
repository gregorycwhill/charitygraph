# G4 Phase-5 cost identity repair independent acceptance

Date: 2026-10-31 (Australia/Sydney)

## Scope and disposition

Reviewed exact branch `gate3-cg406-remediation` at HEAD `0a3a2e8f85703798aed95ee27287de3a06b5714c`, parent `4fbd894f607e11eff03307a5fc75d1955ce69c39`. The supplied immutable v86 fence SHA-256 was `2df394dd800618725bbb47aec6460ba4715e7e0d87e8052a0a19c7acac58640f`; the fence artifact itself was not available in the repository, so that hash was not independently re-derived.

Code semantics: **PASS** for the reviewed bounded repair. Report-only isolation: **PASS**, with the setup limitation recorded below. This is not a Gate 4 closure or provider-route authority decision.

## Commit and dirty-worktree checks

`git diff-tree --no-commit-id --name-status -r --no-renames` showed exactly these direct-child paths:

```text
A reports/G4_PHASE5_PROJECT_COST_IDENTITY_CONTRADICTION_REPAIR_20261031.md
M src/charitygraph/phase5_project_cost_reconciliation.py
M tests/test_phase5_project_cost_reconciliation.py
```

The archived source blob matched the committed Git blob (`a67f1dfbe6007d85c23db63b16e500da2f9c2fc5`). Code/test `git diff --check` passed. The committed repair report contains ordinary Markdown hard-break trailing spaces; this is a report formatting issue, not a code/test defect.

The live checkout was already dirty. The pre-existing hardening report remained unchanged at SHA-256 `f4b2c07c430c3e6f4a49aace62d14f2961b7e3115d2f71de6b1e78d6122e7268`; no dirty path was absorbed.

## Independent semantic review

- `linkage_for_cost` selects task attempts, requests, delivery attempts and receipts by exact persisted identifiers. A declared task-attempt `provider_request_id` disambiguates multiple request items only on an exact match; otherwise linkage is ambiguous or incomplete.
- The repaired receipt check requires a selected receipt `physical_attempt_id` and agreement with the selected physical attempt. Missing identity is `INCOMPLETE_RUNTIME_LINKAGE`; disagreement is `CONTRADICTORY_RUNTIME_IDENTITIES`.
- Provider-request identity is compared across task attempt, request, delivery attempt, physical attempt and receipt. A contradiction becomes a resolution reason, and the existing `not reasons` gate prevents known-charge inclusion. Thus neither challenged contradiction can leak into known spend.
- Missing or ambiguous receipt, request, attempt, physical identity, amount, pricing/FX or usage produces unknown/unreconciled output, not zero. `remaining_spend` is explicitly always unknown for the migration-29 export.
- A valid same-attempt receipt retains the known `1.1` AUD charge. Identical duplicate receipts are counted once; conflicting duplicate receipt evidence is removed from known totals and blocked.
- The adapter requires supported schema version 29. Decimal parsing/arithmetic is used for amounts. Safe catalogue fields include identifiers and bounded usage counts only; raw provider payload/result fields are excluded from the projection and canonical JSON.

## Disposable-overlay verification

The successful overlay was created outside the live checkout with:

```text
git archive --format=zip --output=C:\CharityGraph-runtime\g4-phase5-cost-identity-independent-20261031.zip 0a3a2e8f85703798aed95ee27287de3a06b5714c
Expand-Archive -LiteralPath C:\CharityGraph-runtime\g4-phase5-cost-identity-independent-20261031.zip -DestinationPath C:\CharityGraph-runtime\g4-phase5-cost-identity-independent-overlay-zip-20261031 -Force
```

Cache-free, bytecode-free commands and results:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-cost-identity-independent-focused-basetemp-zip-20261031 tests/test_phase5_project_cost_reconciliation.py
18 passed in 1.94s

$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-cost-identity-independent-combined-basetemp-zip-20261031 tests/test_phase5_project_cost_reconciliation.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_operator_health_runtime_contract.py tests/runtime/test_currency_accounting.py
37 passed in 3.54s
```

The negative fixtures covered receipt physical-attempt mismatch, task-attempt request mismatch, missing/ambiguous selection, and contradictory request/attempt receipt IDs. Positive fixtures covered same-attempt reconciliation, exact-ID selection and duplicate-receipt deduplication. The overlay contained no pytest cache or Python bytecode artifacts. No provider, model, external source, Drive, watcher, GitHub, publication, release or gate action was performed.

An initial disposable `git archive --format=tar | tar -xf -` attempt failed because PowerShell treated the binary stream incompatibly; it did not touch the live checkout. The ZIP overlay above was then created and used for all acceptance tests.
