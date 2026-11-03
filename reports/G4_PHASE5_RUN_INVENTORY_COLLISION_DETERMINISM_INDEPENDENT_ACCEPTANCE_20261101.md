# G4 Phase-5 Run-Inventory Collision Determinism - Independent Acceptance

Status: PASS - bounded local acceptance.

Scope: report-only review of exact HEAD `3114fce5dff4fde3ce6bce01b740e4d49d77a4cc` on `gate3-cg406-remediation`, parent `70069adbc0e3d136786ef699f6cf84a66cac3786`, under immutable-instruction v91 SHA-256 `ebaf30b90532ab1bd04eceaab53b8412b84b77b061a160205faf7fdd98d8f0c9`.

## Evidence

- `git diff-tree --no-commit-id --name-status -r 3114fce5dff4fde3ce6bce01b740e4d49d77a4cc` reported exactly the stated three paths: `src/charitygraph/phase5_run_inventory_audit.py`, `tests/test_phase5_run_inventory_audit.py`, and the prior repair report.
- Read the local `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, and `bridge/SUPERVISOR_PROTOCOL.md`. The code and tests were inspected from a read-only `git archive` of the exact HEAD, separate from the dirty checkout.
- Independent provider-free adversarial probe: `PASS`, 4 cases and 8 orderings. It reproduced the reversed two-record counterexample, checked all six three-way permutations, exact duplicates, conflicting identity metadata, and same-source false independence. Every ordering produced identical canonical bytes and SHA-256; stable suffixes were `#1/#2` and `#1/#2/#3`.
- The probe also confirmed retained explicit missingness/provenance and exact fail-closed authority: `status=NOT_AUTHORITATIVE`, `authority.status=UNVERIFIED`, `project_wide_authoritative=false`, `authoritative_total=null`, and `remaining_spend=null`.
- Focused command, run cache-free from the exact archive:

  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider --basetemp <outside-checkout> tests/test_phase5_run_inventory_audit.py tests/test_phase5_project_cost_reconciliation.py tests/test_phase5_operator_health.py`

  Result: `80 passed in 4.58s` - 21 audit, 30 reconciliation, and 27 operator-health tests; 0 failures.

## Write-boundary and limitations

The final status check shows the pre-existing dirty and untracked material remains present; the target source and test paths are not newly dirty. This report is the only repository path changed by this acceptance. No raw/private evidence, cache, prompt, model response, provider/source access, expenditure, publication, release, GitHub mutation, watcher/process change, ledger/fence change, gate closure, or follow-on dispatch occurred. Temporary exact-HEAD test material was outside the checkout.

Cleanup of the disposable runtime archive was attempted but rejected by environment policy; it remains outside the repository and does not affect the worktree.

This is bounded local acceptance only. It does not establish authenticated, complete, source-owned provider history or receipts, and therefore grants no project-wide authority or unsupported scorecard credit. The full test suite was intentionally not run.

## Next substantive Gate 4 product task

Product Supervision should select a separate bounded Phase-5 reconciliation task for authenticated provider-owned run history and receipts against the local inventory/accounting boundary. No authority escalation is implied until that evidence is complete and independently verified.
