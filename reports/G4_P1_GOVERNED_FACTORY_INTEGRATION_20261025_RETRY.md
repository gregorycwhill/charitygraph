# CG-G4-P1 — Governed Factory integration retry

Status: **implemented bounded integration; Gate 4 remains open**

## Identity, fence and baseline

- Workspace: `C:\CharityGraph-clean\charitygraph`.
- Starting branch / HEAD: `gate3-cg406-remediation` / `71f420ef8c3ac8e569745c0807e87a2ee0287e28`.
- Ending branch / HEAD: `gate3-cg406-remediation` / `71f420ef8c3ac8e569745c0807e87a2ee0287e28` (unchanged; local commit was blocked by repository permissions).
- Active fence was read read-only from `C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\cg-g4-o1b-dormant-state-fence-20261020-v16.json`; SHA-256 matched `2039d228e172ec630c3bc7dc946118af2e0701774883f9349f4254baa43f59cd`.
- The pre-existing baseline was preserved: 255 `git status --porcelain=v1 -uall` lines, 2 tracked modifications, 253 untracked paths; UTF-8 LF-joined status fingerprint `5ece0fca0201ac8545db92a4f9ec0662009f1d05bad1f826e250e04ab87a110e`. The two supervisory-document modifications and quarantined/pytest-path warnings were not touched.

## Archaeology and implementation

- `phase5_preflight.py`: current/reusable exact retained-material resolution and logical planning. It now carries governed source, evidence, representation, rights and reference-hash fields on planned tasks.
- `phase5_factory.py`: current/reusable FactoryPlan/ReferenceFactory restart, batching and accounting seam. Runtime tasks now preserve those references and can register an existing typed `ModelTask` so evidence bindings and task parameters are durable.
- `runtime/catalog.py`: current/reusable source-definition, acquisition, artifact, lineage, evidence-locator, typed-task, physical-attempt and accounting APIs. No catalog change or migration was required.
- New `phase5_governed_factory_integration.py`: the genuinely absent narrow adapter. It validates only already-durable IDs, subject/scope ownership, acquisition outcomes, source-family/hash identity, artifact availability/hash, representation lineage, evidence attachment and supplied rights roles. It lowers only `available` material into deterministic `PlannedLogicalTask` plus `FactoryPlan`; every other state remains a diagnostic.
- New `tests/test_phase5_governed_factory_integration.py`: provider-free durable trace, differentiated missingness, scope isolation, ambiguous restart and independent-unit failure coverage.

No acquisition, discovery, external provider, model execution, semantic heuristic, projection, schema/public-contract change or catalog migration was added.

## Demonstrated input-to-durable-state trace

The synthetic fixture used an existing governed chain: source definition → available acquisition receipt and raw artifact → derived representation artifact with recorded lineage → subject-bound source record → evidence locator. The adapter verified the exact hashes and emitted stable logical task `semtask:b9ddc66e2c005d03668d5dcb7a641abb2e1801405b4e1fbb6912179abcf82c35`. `FactoryPlan` retained subject/scope and source/evidence/representation/rights references. `ReferenceFactory.seed` registered a typed task with a durable evidence binding; execution created one physical attempt and receipt, independently terminalised the logical task, reconciled actual/released accounting, and produced a validated physical state.

Observed provider-free rehearsal: accepted `1`, diagnostics `0`, first completion `1`, rerun completion `0`, durable task `succeeded`, physical `validated`, actual spend `AUD 0.002000`, released reserve `AUD 0.008000`, outstanding reserve `AUD 0.000000`, breach `False`.

## Missingness, restart, isolation and failure outcomes

- Explicit `missing`, `blocked`, `structurally_invalid`, `unrecoverable`, `mismatched`, `not_applicable`, `not_processed` and `retrieval_failed` inputs remain differentiated diagnostics and produce no Factory task.
- A missing/quarantined/unreadable or hash-mismatched representation is held; no invented positive claim or processed-success state is created.
- A scope owned by another subject is rejected as `mismatched`; physical batching remains subject-isolated even when bundle opportunities are equal.
- An ambiguous send remains `send_started`; explicit reconciliation persists the receipt without a resend, and the rerun is a no-op.
- Two independent subjects were run together with one synthetic structural failure. The failed unit became `failed_terminal`, the successful unit remained `succeeded`, and a rerun completed `0`; successful work was not repeated and accounting did not breach.

## Tests and diagnostics

Focused Phase 5 command, cache disabled and temporary base outside checkout:

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p1-pytest-retry-final tests/test_phase5_preflight.py tests/test_phase5_factory.py tests/test_phase5_factory_chaos.py tests/test_phase5_batch_bytes_and_attempts.py tests/test_phase5_delivery.py tests/test_phase5_governed_factory_integration.py
53 passed in 8.36s
```

Affected runtime/catalog command:

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p1-pytest-runtime-retry tests/runtime/test_source_evidence.py tests/runtime/test_task_state.py tests/runtime/test_budget_ledger.py tests/runtime/test_cache_and_artifacts.py tests/runtime/test_knowledge_persistence.py
25 passed in 6.45s
```

The provider-free end-to-end entry-point rehearsal used the same temporary fixture and `preflight_governed_references → GovernedFactoryPreflight.factory_plan → ReferenceFactory.seed/run → SQLiteCatalog` path; its result is recorded above. All test bases were under `C:\CharityGraph-runtime`; no pytest artifacts were written to the checkout.

## Diff, operations and remaining evidence gaps

- Allowed implementation/test/report paths only: `phase5_preflight.py`, `phase5_factory.py`, new `phase5_governed_factory_integration.py`, new integration test, and this report.
- No other file was edited, created, deleted, moved or quarantined. No raw/private evidence, runtime database, prompt, model response, cache, credential or log was added to Git.
- No watcher/process management, Drive setting change, provider/API/source access, GitHub mutation, push, PR, merge, release, gate closure or follow-on dispatch occurred. An explicit `git add`/`git commit` attempt could not create `.git/index.lock` (`Permission denied`); no index lock remained and no commit was created.
- Remaining Gate 4 exit-evidence gaps include real governed-cohort breadth, independent rights/publication audit evidence, real provider authorization/execution evidence, model-result governance/promotion, and complete release/Viewer acceptance. This is bounded integration evidence, not Gate 4 closure.

Semantic disposition recommendation: **accept this mechanical adapter boundary and defer semantic execution**. The diff uses exact identifiers, hashes, catalog relationships and explicit state values only; unrestricted prose interpretation remains delegated to the existing governed model-task boundary.

Final local commit SHA: **recorded by the post-run supervisory reconciliation**. The worker's original commit attempt was blocked by a transient `.git/index.lock` permission denial; the bounded diff and its focused provider-free tests were independently rechecked before this local-only finalization.
