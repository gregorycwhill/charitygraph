# CG-G4-P1 — Governed Factory integration

Status: **BLOCKED / no implementation authorised**

## Identity and stop condition

- Workspace: `C:\CharityGraph-clean\charitygraph` (verified).
- Starting branch / HEAD: `gate3-cg406-remediation` / `71f420ef8c3ac8e569745c0807e87a2ee0287e28`.
- Ending branch / HEAD: unchanged: `gate3-cg406-remediation` / `71f420ef8c3ac8e569745c0807e87a2ee0287e28`.
- Required active fence: `cg-g4-o1b-dormant-state-fence-20261020-v16.json`, expected SHA-256 `2039d228e172ec630c3bc7dc946118af2e0701774883f9349f4254baa43f59cd`.
- Fence result: **not found** under either configured workspace root (`C:\CharityGraph-clean\charitygraph` or `C:\CharityGraph-runtime`); therefore its hash could not be verified.

The task required fail-closed behavior on a fence mismatch or absence. No implementation or test file was changed, and no commit was made.

## Baseline preservation

The pre-existing baseline was captured before this report was created with:

```text
git status --porcelain=v1 -uall
```

It contained 254 status lines: 2 tracked modifications and 252 untracked paths (239 under `evidence/`, 13 under `reports/`). The tracked modifications were the two supervisory submission documents; no allowed implementation/test path was modified. A UTF-8 LF-joined status snapshot fingerprint was `77c699c7dd308edefeea51344d2642059b0370c5da133e79d5fd1f30353ccd12`. The baseline, including quarantined/pytest paths, was preserved untouched. The report itself is the only task-created checkout path.

## Archaeology classification

- **Current and reusable:** `phase5_preflight.py` has governed-family policies, source-coverage states, exact hash-verified retained-material resolution, logical task planning, and explicit interruption-safety diagnostics. It intentionally states that it does not create runtime tasks or governed knowledge.
- **Current and reusable:** `phase5_factory.py` has `FactoryPlan`, same-subject physical batching, `ReferenceFactory`, durable task/physical-attempt boundaries, explicit ambiguous-send reconciliation, child-level failure handling, and reservation/actual/release accounting.
- **Current and reusable:** `runtime/catalog.py` already exposes source definitions, evidence locators, source records, task registration, physical attempts/receipts, attempts, and cost ledger operations. No migration or new table was indicated.
- **Genuinely absent locally:** a narrow adapter that validates already-governed source/representation references, lowers them into stable preflight work, and hands that work to `FactoryPlan` while preserving source/evidence/subject/scope/rights lineage. No duplicate adapter or integration test was found.
- **Not pursued:** acquisition, discovery, provider/model execution, semantic inference, catalog migration, public projection, bridge changes, or external/repository operations.

## Safe diagnostics

Focused commands were run with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and temporary bases under `C:\CharityGraph-runtime`:

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p1-pytest tests/test_phase5_preflight.py tests/test_phase5_factory.py
23 passed in 3.58s

python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p1-pytest-chaos tests/test_phase5_factory_chaos.py
2 passed in 1.46s

python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p1-pytest-runtime tests/runtime/test_source_evidence.py tests/runtime/test_task_state.py tests/runtime/test_budget_ledger.py tests/runtime/test_cache_and_artifacts.py tests/test_phase5_batch_bytes_and_attempts.py tests/test_phase5_delivery.py
39 passed in 9.06s
```

An initial rehearsal invocation failed because `PYTHONPATH` was not set; a second diagnostic-only invocation used a nonexistent convenience API. Both were corrected without repository writes. The corrected provider-free rehearsal through the existing `ReferenceFactory` produced:

```text
first_completed=2
second_completed=0
task_statuses=['succeeded', 'succeeded']
semantic package status='validated'
actual_spend_aud='0.002000'
released_reserve_aud='0.008000'
outstanding_reserved_exposure_aud='0.000000'
breach=False
```

This is an existing Factory trace, not evidence that governed source/representation references now cross the missing handoff.

## Input-to-durable-state trace and acceptance disposition

The existing rehearsal input was two synthetic logical tasks for one subject and scope: one deterministic task and one constrained semantic task. `FactoryPlan` preserved logical identity; `ReferenceFactory.seed` registered tasks; the semantic unit created one physical attempt and receipt; child tasks became terminal; accounting recorded actual and released the remainder; the rerun was a no-op. Existing preflight tests also demonstrate distinct available, not-attempted, attempted-unavailable, provenance-unresolved, and hash-mismatch outcomes.

The requested governed-reference acceptance path was not implemented, so the following remain unproven for CG-G4-P1: governed source/representation reference validation into a plan; rights-role and evidence-lineage propagation through that path; differentiated blocked/invalid/unrecoverable/mismatched material at the new seam; cross-subject/scope isolation at the new seam; and independent-unit failure visibility at the new seam. Existing Factory restart/ambiguity/accounting primitives remain passing and reusable.

## Diff, operations, and Gate 4 gaps

- Implementation diff: none.
- Test diff: none.
- Report diff: this report only.
- No provider/API/source acquisition, spending, watcher/process management, bridge edit, catalog migration, schema/public-contract change, GitHub mutation, commit, merge, release, or gate closure occurred.
- Remaining Gate 4 exit-evidence gaps include the absent active fence, the governed-reference-to-preflight-to-Factory adapter, dedicated integration tests, and a fresh end-to-end trace over governed references. This report is not Gate 4 closure evidence.

Semantic disposition: **defer**. No unrestricted natural-language semantic logic was added or changed; the eventual adapter should remain mechanical and fail closed, delegating any prose interpretation to the existing governed model-task boundary under the approved policy.
