# G4 Phase 5 provider-history private-material repair — independent acceptance

Date: 2026-11-01 (Australia/Sydney)  
Disposition: **PARTIAL — local repair PASS; real provider-history evidence remains unavailable**

This is a provider-free, report-only local acceptance. No provider, model,
Drive, watcher, GitHub, publication, release, or spend action is performed.

## Scope and isolation

- Required HEAD: `2b95eb320560d21b7336ca92b137b76cc79a86cc` on
  `gate3-cg406-remediation`.
- Required parent: `c571ac9aa1030e4a0aa5b4240c975ff6408b6ea7`.
- Required immutable fence: v94,
  `f11be96d1df9c9551689b5a5769323ce1d47e822ae0a81eebbfbfa9fd5bbcac7`.
- The checkout had pre-existing unrelated dirty tracked and untracked paths;
  they are outside this acceptance and will not be staged or changed.
- This report is the only path authorised for new work by this task.

## Exact baseline and direct-child verification

The checkout was at the required HEAD and branch. The exact-parent checks were:

```text
git rev-parse HEAD
2b95eb320560d21b7336ca92b137b76cc79a86cc

git rev-parse 2b95eb320560d21b7336ca92b137b76cc79a86cc^
c571ac9aa1030e4a0aa5b4240c975ff6408b6ea7

git diff-tree --no-commit-id --name-status -r c571ac9aa1030e4a0aa5b4240c975ff6408b6ea7 2b95eb320560d21b7336ca92b137b76cc79a86cc
A reports/G4_PHASE5_PROVIDER_HISTORY_PRIVATE_MATERIAL_AND_RUN_ATTEMPT_REPAIR_20261101.md
M src/charitygraph/phase5_provider_history_evidence_adapter.py
M tests/test_phase5_provider_history_evidence_adapter.py
```

The worktree contained a pre-existing dirty baseline of unrelated tracked and
untracked paths. The adapter, its test, and the worker report remained
unchanged in the worktree; only this new report is attributable to this task.
No staging or broad Git operation was used.

## Exact test commands and counts

Both commands used `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and an
external basetemp under `C:\CharityGraph-runtime`:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-provider-history-independent-20261101-adapter tests/test_phase5_provider_history_evidence_adapter.py
27 passed in 0.62s

$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-provider-history-independent-20261101-small tests/test_phase5_run_inventory_audit.py tests/test_phase5_project_cost_reconciliation.py
51 passed in 2.80s
```

Focused and small-suite result: **78 passed, 0 failed**.

## Independent reproducer evidence

The exact outer invocation was `$env:PYTHONDONTWRITEBYTECODE='1'; $script |
python -`, where `$script` was an in-memory harness that imported the adapter
through `src` and made no filesystem writes. It independently checked:

- A nested `source_identity` containing unknown fields, alias collisions,
  malformed recognised values, credentials/tokens, raw-source and billing
  structures, Unicode and nested values. The canonical projection retained
  exactly `source_id`, `provider_id`, `account_id`, and `identity_version`, and
  emitted both unknown-field and malformed-field omission diagnostics.
- Seven byte/projection surfaces were scanned: `canonical_json`, the canonical
  helper output, `as_dict()` canonical bytes, document JSON, diagnostics JSON,
  the existing generated worker report, and this report. None contained any
  synthetic private sentinel. Sentinel values were process-local, never
  printed, and are not recorded here.
- Four missing run-attempt forms (null, blank, list, and nested mapping), one
  valid attempt, duplicate run records, and conflicting physical attempts.
  `MISSING_RUN_PHYSICAL_ATTEMPT_ID` was present; missing rows retained
  `physical_attempt_id: null`; no physical attempt was invented; duplicate and
  conflicting IDs remained separately diagnosed.
- Receipt orphan and missing-attempt cases remained distinct through
  `UNKNOWN_ORPHAN_RECEIPT_RUN_IDS`,
  `UNKNOWN_ORPHAN_RECEIPT_PHYSICAL_ATTEMPT_IDS`,
  `BROKEN_RECEIPT_RUN_FOREIGN_KEY`, and
  `MISSING_RECEIPT_PHYSICAL_ATTEMPT_ID`.
- Reversed record permutations preserved normalised observations and reason
  codes. Each raw-export SHA-256 matched its exact input bytes; reversed input
  bytes intentionally produced a different source SHA and projection hash.
- Across private-identity, run-index, and receipt cases—including caller
  assertions of authentication, verification, completeness and source
  ownership—`project_wide_authoritative` stayed `false`,
  `authoritative_total` stayed `null`, and `remaining_spend` stayed `null`.

Independent harness summary: **PASS; 7 private-material byte surfaces, 4
missing-attempt cases, 4 receipt/authority distinctions, and permutation/SHA
provenance checks completed**.

## Acceptance result

**PASS for the bounded local private-field and missing-attempt repair.** The
allowlisted projection and explicit missing-attempt diagnostics are present,
private-material exclusion held across inspected outputs, and authority stayed
fail-closed. Overall disposition remains **PARTIAL** because this task did not
and could not establish real provider-history completeness, cumulative run
inventory, invoice truth, pricing/FX truth, or budget authority.

## Real-provider-history limitation

No authenticated provider-native cumulative run inventory, billing/receipt
population, trusted host attestation, or source-owned completeness boundary is
available to this provider-free acceptance. Local checks cannot establish
provider completeness, invoice truth, pricing/FX truth, or budget authority.

