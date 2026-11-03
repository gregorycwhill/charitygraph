# G4 P2b — provider-free catalogue scope guard

Date: 2026-10-25  
Task: `20261025-g4-p2b-sol-catalog-scope-guard-v1`

## Outcome

Process completion: **complete**. The requested local implementation, focused regression, provider-free verification, report, and final repository audit are complete. No commit, staging, watcher/process action, provider/API/model call, source acquisition, GitHub mutation, publication, release, gate closure, or follow-on dispatch occurred.

Bounded product acceptance: **PASS for this direct-catalog persistence slice**. This report does not close Gate 4.

## Checkpoint and authority

- Branch: `gate3-cg406-remediation`
- HEAD: `21bb0e621f2a1c52f19b59f261d71009defa4843`
- HEAD tree: `f5851e02afab398326e145a34d142d9de5fe1a58`
- Active v23 fence: `C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\cg-g4-o1b-dormant-state-fence-20261020-v23.json`
- Fence SHA-256: `8d58d6acccaa5933075a1492e0974fc6a1080868d78b3e58532a351b5cb5c342`

Read before editing: `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, the corrected P2 acceptance report, the P2 implementation report, and the sibling Data authority/current-state/planning, integrated-model, source/evidence/publication, taxonomy, coverage/economics, implementation, rights, and test documents. Their applicable boundary is mechanical Python control, durable task/run/scope integrity, append-only history, explicit provenance, and budget/receipt discipline; no cross-product or public-contract change was needed.

The three writable code/test paths were clean at start and were checked for non-overlap with the pre-existing dirt. Pre-existing stable dirt was preserved, including `docs/G4_O1B_SUPERVISORY_SUBMISSION.md`, `docs/G4_O1C_SUPERVISORY_SUBMISSION.md`, `src/charitygraph/phase5_factory.py`, `tests/test_phase5_factory.py`, `tests/test_phase5_governed_factory_integration.py`, and the existing `evidence/` and `reports/` paths. The final task delta is limited to the two code/test paths below and this report; `tests/test_phase5_batch_bytes_and_attempts.py` remained unchanged.

## Implementation

Changed only:

- `src/charitygraph/runtime/catalog.py`
- `tests/runtime/test_task_state.py`
- `reports/G4_P2B_CATALOG_SCOPE_GUARD_20261025.md`

The key catalog hunk is:

```python
existing = conn.execute("SELECT * FROM physical_attempts WHERE physical_attempt_id=?", (physical_attempt_id,)).fetchone()
member_scopes = set()
for task_id in model_task_ids:
    task = conn.execute("SELECT run_id, subject_id, scope_id FROM tasks WHERE model_task_id=?", (task_id,)).fetchone()
    if task is None or task["run_id"] != run_id or task["subject_id"] != subject_id:
        raise ConflictError("physical attempt members must belong to its run and subject")
    member_scopes.add(task["scope_id"])
if len(member_scopes) > 1:
    raise ConflictError("physical attempt members must share one task scope_id; null and non-null scopes cannot be mixed")
if existing:
    existing_member_ids = {
        row["model_task_id"]
        for row in conn.execute("SELECT model_task_id FROM physical_attempt_members WHERE physical_attempt_id=?", (physical_attempt_id,)).fetchall()
    }
    if existing_member_ids != set(model_task_ids):
        raise ConflictError("physical attempt re-entry member set conflicts with existing attempt")
    return dict(existing)
```

The guard runs in the existing immediate transaction before physical-attempt or member insertion. It preserves null/null compatibility, same-scope bundling, one-member preparation, run/subject guards, logical/provider identities, retries, receipts, costs, reservations, ambiguous-send handling, and existing idempotent re-entry. Re-entry now rejects a different member set instead of silently returning the existing row. No `physical_attempts.scope_id` column, migration, or historical rewrite was introduced.

## Direct-catalog acceptance evidence

The new `tests/runtime/test_task_state.py` regression covers:

| Case | Result |
|---|---|
| Same run/subject/non-null scope pair | Prepared and idempotent, including reversed member order and reopen/re-entry probe |
| Same run/subject/null scope pair | Prepared and idempotent |
| Same subject, distinct non-null scopes | Deterministic `ConflictError` before writes |
| Null versus non-null scope | Deterministic `ConflictError` before writes |
| Cross-subject and cross-run members | Existing `ConflictError` retained before writes |
| Existing physical ID with a different member set | Deterministic re-entry conflict |

Independent SQLite probe at `C:\CharityGraph-runtime\cg-g4-p2b-catalog-probe-20261025` reported:

```text
valid_idempotent=True
null_null_prepared=True
rejected_errors={'physical:mixed': 'physical attempt members must share one task scope_id; null and non-null scopes cannot be mixed', 'physical:null-mixed': 'physical attempt members must share one task scope_id; null and non-null scopes cannot be mixed'}
before_rejected={'physical_attempts': 2, 'physical_attempt_members': 4, 'provider_receipts': 0, 'cost_entries': 0, 'budget_reservations': 0}
after_rejected={'physical_attempts': 2, 'physical_attempt_members': 4, 'provider_receipts': 0, 'cost_entries': 0, 'budget_reservations': 0}
rejected_side_effects_unchanged=True
```

This directly closes the old P2 probe recorded in the corrected acceptance report, where a same-subject mixed-scope member set was accepted and persisted.

## Verification

All commands used `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`, `-p no:cacheprovider`, and fresh basetemps under `C:\CharityGraph-runtime` outside the checkout.

```text
Baseline:
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p2b-catalog-scope-baseline-20261025 tests/runtime/test_task_state.py tests/test_phase5_batch_bytes_and_attempts.py tests/test_phase5_preflight.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py tests/runtime/test_source_evidence.py tests/runtime/test_budget_ledger.py
51 passed in 10.00s

Focused changed seam:
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p2b-catalog-scope-focused2-20261025 tests/runtime/test_task_state.py
6 passed in 2.38s

Final bounded regression:
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p2b-catalog-scope-final-20261025 tests/runtime/test_task_state.py tests/test_phase5_batch_bytes_and_attempts.py tests/test_phase5_preflight.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py tests/runtime/test_source_evidence.py tests/runtime/test_budget_ledger.py
53 passed in 10.19s

git diff --check
exit 0; only existing line-ending warnings for unrelated dirty files
```

No intermediate failure occurred in this task. The existing P2 Factory/governed integration tests were run read-only as part of the regression suite. No checkout cache, bytecode, database, fixture, or test temporary state was created.

## Final audit and residual risk

Final branch, HEAD, tree, fence, and protected-path identities remained unchanged. Final SHA-256 values for the three code/test paths were:

```text
7e1bd2d19732102f9840a6c7ce1a55c95042ef4d88b874cd3a6ef43aa49c4020  src/charitygraph/runtime/catalog.py
5804053f05619604896ace5f0149c2442c46dfdbaa3491811dc1a60844c8e42f  tests/runtime/test_task_state.py
e3f8a6c1566e7241f6bf10d2203fd49454b6b5a147befbacc72e6c22223f176a  tests/test_phase5_batch_bytes_and_attempts.py
```

The physical-attempt schema still has no dedicated scope column. Historical mixed-scope attempts, if any, are not rewritten. The guard protects new direct preparation and rejects inconsistent re-entry; append-only replacement paths that copy historical members remain outside this tranche and are a residual migration-free limitation. Provider billing, real model execution, source acquisition, canonical coverage, publication, and Gate 4 acceptance remain outside this task.
