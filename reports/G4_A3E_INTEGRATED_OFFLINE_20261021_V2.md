# Gate 4 integrated offline rehearsal — 21 October 2026

Disposition: `PROVEN_OFFLINE` for the existing control-plane seams; not Gate 4 closure evidence. This was one local, provider-free, report-only rehearsal. No source acquisition, network/provider call, model interpretation, spend, publication, merge/release, watcher/process management, dormant-fence change, or GitHub mutation occurred.

## 1. Identity, authority, dirty baseline, and scorecard conflict

- Verified before testing: branch `gate3-cg406-remediation`; full HEAD `3d90ff90201e10c1f717d5b3ef82e1f9831a05c4`.
- The pre-existing dirty baseline contained modified `docs/G4_O1B_SUPERVISORY_SUBMISSION.md` and `docs/G4_O1C_SUPERVISORY_SUBMISSION.md`, numerous untracked Gate 3/CG406 evidence directories, and earlier G4 reports. The pre-existing `.pytest_cache` and the status-scan permission warning for `CharityGraph-runtimecg405-pytest/` were preserved. No baseline file was edited.
- Read: `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, and prior `reports/G4_INDUSTRIALISATION_EVIDENCE_REVIEW_20261021_A2.md`. The local authority says Builder consumes governed evidence, Python controls mechanics/cost/state, model output is not a human decision, and the seven-family Source Universe v1 is exhaustive.
- Dated status conflict retained without resolution: the operator direction for this task is Gates 1–3 closed and Gate 4 active; `reports/GATE4_AUTONOMOUS_DEVELOPMENT_LOOP_2026-10-20.md` says Gate 4 is active and unearned. Published Data `main` may still state Gate 2 active. External/published Data access was prohibited here, so this worker did not reconcile that conflict and makes no cross-product status claim.

## 2. Actual local evidence/cohort and provenance

The inspected genuine bounded cohort manifest is `cohort/reality_slice1_development_manifest.json`: 7 development subjects plus 3 sealed holdouts, with authority `charitygraph-data` Data `main` commit `f8fc0ea70de21e397d64bd8a3fd21f941a2ca395`, packet `REALITY_SLICE_1_ACCEPTANCE_PACKET.md`, private-preflight mode, AUD 25 budget cap, human approval required for paid semantic execution, and publication forbidden. Its acquisition status is `planned`, not acquired. Its expected families also include non-admitted classes such as education-evaluation, grantmaking-research, service-regulator and DFAT evaluation families, so this worker correctly failed closed and did not use it as a Source Universe v1 cohort. The 10-row count is reported because the manifest was actually inspected; it is not a Gate 4 execution cohort.

The retained Gate 3 review dossier `evidence/gate3-final-semantic-review/case-assessments.json` is a separate historical subject/evidence reference, schema `charitygraph.gate3.final-semantic-review.case-assessments/v1`, containing exactly 36 subject/question rows. Its SHA-256 is `63f2eed81d5ab0dd7317840408a5d32ce10d7b70a1fa81b35e0653d9fd076eca`. The retained summary says those Builder rows used 36 ACNC Register and 36 ACNC AIS representations; this is historical evaluation evidence, not a current Gate 4 source corpus. The prior private autonomous demo selected its first three retained subjects and recorded the dossier hash, but no source facts were regenerated here.

No current governed 30-subject source/evidence manifest, durable source bytes, or complete v1 representation bundle was found and used. The 30-subject Gate 5 manifest is not a Gate 4 prerequisite and was neither fabricated nor inferred. The inspected `governed-inputs/knowledge-validation-v1` files are human-review policy/decision material (`auto_promotion=false`, 22 approved decisions from a 48-case review), not a source cohort.

## 3. Current production-path graph and missing joints

```text
governed source/subject material
  -> phase5_preflight.resolve_governed_source_material()
  -> build_source_inventory() / build_planned_tasks()
  -> FactoryPlan.from_manifest()
  -> ReferenceFactory.seed() -> SQLiteCatalog.register_task()
  -> prepare_package()
  -> reserve_cost() -> prepare_physical_attempt()
  -> mark_physical_send_started()
  -> provider receipt boundary
  -> persist receipt -> finalise children -> record actual/release reservation
```

Exact current pointers:

- Source readiness and explicit missingness: `src/charitygraph/phase5_preflight.py:104-129,293-320,360-376` (`resolve_governed_source_material`, `build_source_inventory`, `build_planned_tasks`, `preflight_interruption_safety`).
- Deterministic planning and same-subject packaging: `src/charitygraph/phase5_factory.py:18-40` (`FactoryPlan.from_manifest`, `physical_packages`).
- Fake-only integrated rehearsal: `src/charitygraph/phase5_factory.py:91-219` (`ReferenceFactory`, `prepare_package`, `reconcile_ambiguous_package`, `finalise_package_children`, `run`). `RehearsalFakeProvider` is explicitly not a knowledge producer.
- Delivery policy and economics: `src/charitygraph/phase5_delivery.py:24-71,122-188`; fake state adapter: `:199-240`.
- Standard bounded feeder: `src/charitygraph/phase5_standard_transport.py:305-513` (`StandardCampaignCoordinator`), including pinned-body validation, concurrency, stop conditions and ambiguous classification.
- Durable lifecycle/accounting: `src/charitygraph/runtime/catalog.py:1595-1947,2618-2708,3873-4521` for cohorts/runs/tasks/leases, operations, reservations/costs, physical attempts, traces, delivery jobs, request attempts/items and receipts.
- Local ingress/result diagnostics: `src/charitygraph/autonomous_loop.py:167-458` (`LocalAutonomousBridge`); this is a transport adapter, not a Builder source/semantic orchestrator.

Missing joints are material: no source-ready, v1-admitted manifest is wired through preflight into this Factory path; the fake path emits no semantic payload; no canonical candidate/decision/promotion/release path was exercised; and no live provider crossing or production scheduler/monitoring surface was established.

## 4. Exact validations and evidence

All commands set `PYTHONDONTWRITEBYTECODE=1` and used `-p no:cacheprovider`; no pytest cache was enabled. Test databases and files were confined to pytest temporary directories.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest tests/test_autonomous_loop.py tests/test_phase5_factory.py tests/test_phase5_factory_chaos.py tests/test_phase5_batch_bytes_and_attempts.py tests/test_standard_delivery_job.py tests/runtime/test_task_state.py -q -p no:cacheprovider -o addopts=''
```

Exit 0; **31 passed** in 3.58s. This covered durable instruction claim/result idempotence, Factory logical/physical identity, fake receipts, terminal no-op, task leasing, package receipt persistence, batch-byte/attempt integrity, and multi-item Standard job closure.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest tests/test_openai_batch_transport.py tests/test_phase5_standard_transport.py tests/runtime/test_budget_ledger.py tests/test_phase5_openai_dry_run.py tests/test_phase5_cost_rounding.py tests/test_phase5_cost_cap_partition.py tests/test_phase5_cost_cap_certification.py tests/test_phase5_reconciliation.py tests/test_phase5_preflight.py -q -p no:cacheprovider -o addopts=''
```

Exit 0; **91 passed** in 4.39s. This covered the 93-item provider-free Standard feeder, bounded concurrency and systemic/item/ambiguous isolation, saved-response and terminal replay without POST, batch submission/reconciliation and ambiguous-create no-resend, budget reservation/release/overrun/duplicate-entry behavior, conservative cost calculation, payload identity, and source-material/preflight fail-closed rules. Provider-facing tests use fake clients, monkeypatches, or default-deny gates; they did not call a provider.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest tests/test_bridge_cutover.py -q -p no:cacheprovider -o addopts=''
```

Exit 0; **8 passed, 1 skipped** in 5.74s. The skip is the explicit opt-in real Codex CLI rehearsal. The inactive bounded implementation route was rejected before claim.

Observed behavior: deterministic logical/request/physical identities; cost reserved before fake semantic execution and reconciled with actual plus release entries; pre-send failures did not cross a send boundary; terminal and duplicate replays were no-ops; an ambiguous started send required reconciliation and could not resend; task/package failures remained isolated; receipts, usage, failure class, lease, trace, and cost rows were durable. These are local lifecycle results only. No source facts or semantic model response was created.

## 5. Gate 4 exit criteria

| Criterion | Status | Limitation |
|---|---|---|
| Model/cost routing | `PROVEN_OFFLINE` | Delivery policy, conservative dry-run pricing, reservations and actual/release accounting are exercised; no live model route or 65k cohort proof. |
| Batch execution | `PROVEN_OFFLINE` | Existing batch transport and fake clients persist job/item state and reconcile mixed outcomes; no provider batch submission. |
| Concurrency | `PROVEN_OFFLINE` | Standard feeder bounds workers and exercises 93 items; no sustained production load or throughput/SLO evidence. |
| Scheduling | `PROVEN_OFFLINE` | Task leases, eligibility and feeder stop behavior are durable; no long-running production scheduler or admission service. |
| Restart/resume | `PROVEN_OFFLINE` | Saved receipts/results and terminal states resume without another local send; no external provider recovery proof. |
| Idempotence | `PROVEN_OFFLINE` | Local deterministic identities and replay no-ops are proven; provider-side exactly-once effect after an ambiguous crossing remains `UNKNOWN`. |
| Monitoring | `NOT_FOUND` | Structured traces, states and counts exist, but no operator dashboard, alerting, health report or live run diagnostic surface was found. |
| Failure isolation | `PROVEN_OFFLINE` | Pre-send, terminal, systemic and ambiguous outcomes are separated; independent items continue where policy allows. No real charity-data failure run. |
| Cost telemetry | `PROVEN_OFFLINE` | Ledger mechanics and simulated usage-to-cost reconciliation pass; actual expenditure is zero here. Retained real-provider spend is `HISTORICAL_ONLY`, not current exit proof. |

## 6. Operator diagnostics

| Durable/inspectable now | Missing or not established |
|---|---|
| Branch/HEAD and manifest hashes; cohort/run IDs; logical task and subject IDs; task status, lease owner/expiry and attempt state. | A current governed source/cohort manifest and source-byte/representation inventory attached to this run. |
| Delivery mode/model route, delivery job, request item/attempt identities, client trace/body hash, send-started state, provider receipt reference, raw-result reference and usage. | A live provider receipt/reconciliation surface and provider-side duplicate-effect evidence. |
| Reservation ID, budget cap, actual/release entries, pricing/FX references and budget position. | Live spend, latency, throughput, alert/SLO and operator health aggregation. |
| Failure class/message, ambiguous quarantine, bridge instruction status/events/result hash and explicit `not promoted` boundary in the historical demo. | Semantic candidate payload, governed decision/promotion state, coverage report, correction state and release projection for this rehearsal. |

## 7. One coherent bounded next tranche

Implement one **evidence-bound offline Factory integration seam**, reusing the existing paths rather than adding an orchestrator: connect the output of `src/charitygraph/phase5_preflight.py` to `FactoryPlan`/`ReferenceFactory` in `src/charitygraph/phase5_factory.py`, preserve the evidence/representation references through `SQLiteCatalog.register_task()` in `src/charitygraph/runtime/catalog.py`, and add only the focused acceptance coverage in `tests/test_phase5_integrated_offline.py`.

Acceptance: a separately designated immutable local subject/source manifest is hashed and identity-checked; absent, ambiguous or non-recoverable source material fails closed; existing preflight tasks compile to deterministic Factory logical/physical identities; fake execution records reservations, receipts, failure isolation, restart/no-resend and accounting reconciliation; operator diagnostics expose the complete run/task/evidence-reference chain; no semantic output is promoted. No source fixture, discovery, source-family expansion or model/provider call is allowed.

Expected product delta: one inspectable offline path from governed references to the existing task/delivery/catalog machinery, with explicit coverage gaps instead of a disconnected fake rehearsal. Safe publication boundary: private rebuildable runtime/temporary directories only; no public cards, immutable release bytes, schema, Viewer selection, GitHub state, or gate status changes.

## 8. Inactive bounded-workspace authority and certification boundary

The exact local implementation authority is `charitygraph.g4-o1d-local-implementation/v1`, scope `bounded_local_builder_code_change`, with `active=false`. This is recorded in `reports/G4_O1D_SUPERVISORY_ACCEPTANCE_20261021.md` and enforced by `tests/test_bridge_cutover.py:253-273`; the route rejects execution before claim. This report does not activate it.

Any later code change requires a separately authorized route activation and its own provider-free certification. Any provider-bound Standard row must separately pass the exact hydrated-row checks in `src/charitygraph/phase5_pre_send_certification.py:14-68`, including mandate, reservation, route, schema/body identity, prepared request/attempt state, and no prior provider crossing. Offline rehearsal evidence cannot substitute for that certification or for Product Owner/Data authority.

## 9. Gate 5 dependencies and unresolved sufficiency

Gate 5 still depends on a Product Owner-approved bounded subject/source manifest, current Data authority and policy versions, durable identity bindings, exact retained source/representation references, rights/transmission decisions, typed task contracts, semantic benchmark/abstention rules, human or approved-policy promotion, correction handling, and a reproducible cost/coverage ledger. The retained 36-row Gate 3 review is useful provenance but only observed ACNC Register/AIS representations; it does not establish sufficiency across all seven admitted families or population-scale coverage.

Unresolved gaps remain first-party/source visibility, current governed source-material availability, semantic sufficiency for operational/giving/policy/evaluation propositions, live provider crossing and external exactly-once behavior, and operator monitoring. Sparse evidence is recorded as a coverage/source-policy question; it is not permission for discovery or source-policy expansion. Gate 2 specification 007, campaign 403, dormant state, publication, merge/release, and follow-on dispatch remain out of scope.

