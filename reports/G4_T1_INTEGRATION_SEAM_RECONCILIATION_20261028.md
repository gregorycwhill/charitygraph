# G4-O1C Tranche 1 integration-seam reconciliation

Date: 2026-10-28 (Australia/Sydney)  
Mode: local, provider-free, report-only  
Target: branch `gate3-cg406-remediation`, clean HEAD `4bf112726f289b191c9f765e0c3bfc3f0d0cd021`, tree `3345687565be6f275da06b3c4619ef7ca6b458fc`, fence v40

## Decision

**Do not absorb the dirty rights/Factory path.** Option 1 rights governance is already the applicable product direction: private content-addressed record authority, rebuildable SQLite projection, and optional expiry. The clean v29 record/projection substrate is present, but the clean Phase5 governed preflight is not connected to it. The smallest safe next slice is a provider-free clean-authority preflight integration; it must remain fail-closed for provider transmission until Data/Product Owner supplies an exact source-owned provider-policy ID/version registry.

The unresolved provider-policy identity/version is a genuine governance decision. It is separate from, and does not invalidate, the already-approved Option 1 rights-record/projection architecture.

## Repository and dirty boundary

The worktree was already dirty. It contained 10 modified tracked paths and 75 untracked status entries before this report; no pre-existing path was changed, staged, reset, checked out, or deleted. The required report was absent before this write.

| Path | Clean HEAD blob | Current worktree SHA-256 | State / finding |
|---|---|---|---|
| `src/charitygraph/source_rights.py` | `bab1f855c5c4721e093f6d169b2f5ce022c12691` | `72f0cc0b3fb1f1ad0f3bb92700e6fe26bc85a9a97510a261e4ae285e66da79bc` | modified |
| `src/charitygraph/phase5_governed_factory_integration.py` | `b2a381ede6e3958ac9400292e16f85b0862359bc` | `503d357761ab4884c4099b58e8ff15becb7214611984b46af7d68b236a8b0224` | modified |
| `src/charitygraph/runtime/catalog.py` | `5954ce82334bb4a00d0d20c697f66babca427e18` | `3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1` | modified |
| `tests/test_phase5_governed_factory_integration.py` | `9cbedec2d601c91a166950c6746660847d179744` | `9c71f762bcae0363cff34552f68e0fe9a18c5fdd2c472f2edadf1c0eede0c01d` | modified |
| `tests/test_source_rights.py` | `1a110fb5ef81ff28957511bab4c4bff3bda8f98c` | `933177298b63d03a7bd51a2defa37f2a94780d9a5581cc72979b1debbd22274` | modified |
| `tests/test_phase5_governed_factory_rights.py` | absent | `dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281` | untracked |

Related dirty scope isolation changes also exist in `src/charitygraph/phase5_factory.py`, `tests/test_phase5_factory.py`, and `tests/runtime/test_task_state.py`.

## What clean HEAD can and cannot do

Read: `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, the available sibling Data `DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, `IMPLEMENTATION_PLAN.md`, `TEST_PLAN.md`, `INTEGRATED_PRODUCT_AND_DATA_MODEL.md`, `SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`, `TAXONOMY_AND_SCHEME_GOVERNANCE.md`, `COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`, `SEMANTIC_HEURISTIC_APPROVALS.md`, and the latest P3c/P4 reports including `G4_P3C_PROVIDER_AUTHORITY_CLEAN_CATALOGUE_PROVENANCE_ARCHAEOLOGY_20261027.md` and `G4_P4_E_INDEPENDENT_OFFLINE_ACCEPTANCE_REVIEW_20261027.md`.

- Clean `src/charitygraph/runtime/rights_governance_record.py` is the content-addressed authority substrate. It delegates substantive policy vocabulary to clean `source_rights.py` and rejects an authorized provider axis when no exact source-owned provider registry exists (`:281-303`).
- Clean `src/charitygraph/runtime/migrations.py` has numbered v29 `rights_projection_*` tables (`:1196-1261`). `rights_governance_projection.py` rebuilds them transactionally from `RightsGovernanceStore` (`:212-241`); this is the correct rebuildable projection seam.
- Clean `source_rights.py` has `ArtifactRightsDecision` and `require_provider_rights`, but no `governed_rights_policy()`, no `PROVIDER_POLICY_REGISTRY`, and no exact-representation/version/authority fields required by the dirty adapter.
- Clean `phase5_governed_factory_integration.py` has representation hash validation, but `GovernedReference` has no `rights_decision_ids` and `preflight_governed_references()` does not read the rights record or v29 projection. The clean preflight can lower a representation-valid task without an integrated Option 1 rights decision.

Therefore clean P3c record + v29 projection + Phase5 preflight do **not** run end-to-end as one governed path at this HEAD. This is an integration seam defect, not evidence that the v29 projection is absent.

## What the dirty changes already implement

The dirty changes are a partial Tranche 1 prototype, not a safe clean implementation:

- `source_rights.py:55-67, 100-133, 260-328` adds an exact resolver for the rights-policy registry, representation binding, decision status, supersession, optional expiry, and stronger source/lineage matching. It does **not** add an exact provider-policy registry; the provider version is accepted as a free string. `governed_rights_policy()` validates only the CharityGraph rights-policy registry.
- `phase5_governed_factory_integration.py:341-520, 522-620` adds rights diagnostics and blocks missing, conflicting, mismatched, denied, revoked/superseded, and expired decisions before Factory lowering. It calls dirty-only `SQLiteCatalog` rights methods and therefore does not consume `RightsGovernanceStore` or v29 `rights_projection_*` current rows.
- `runtime/catalog.py:77-124, 475-496, 2993-3123` side-installs `artifact_rights_decisions`, events, and diagnostics outside numbered migrations. `material_json` is persisted there as the decision store. This is distinct from, and not a rebuild adapter for, clean v29.
- `phase5_factory.py` and the dirty integration test additionally separate physical packages by `(subject_id, scope_id, bundle)`. The dirty rights test covers positive fake execution, restart idempotence, rights mismatch/expiry/lineage cases, and scope isolation. These are useful behavioural cases, but their fixtures exercise the dirty catalog path.

The worktree suite passed **87 tests** in 13.17s using `python -B -m pytest -o addopts= -p no:cacheprovider` and an external basetemp under `C:\CharityGraph-runtime`. This is provider-free synthetic evidence only.

## Physical-attempt residual risk

The clean `runtime/catalog.py` has two re-entry/replacement bypasses:

1. `prepare_physical_attempt()` returns an existing row before checking changed mode, provider request ID, reservation, batch ID, or member set.
2. `create_zero_crossing_pre_send_replacement()` returns an existing replacement after checking only request-item/material identity; it does not revalidate new attempt/job/reservation identity, run/subject/mode, or copied member scope.

The dirty catalog changes at `:4063-4118` and `:4355-4417` close these gaps with unique member checks, single-scope enforcement, durable re-entry identity checks, and replacement run/subject/mode/reservation/member validation. The dirty `tests/runtime/test_task_state.py` exercises those cases and passed in the worktree suite. This is a safe implementation direction, but the current bytes are dirty and must not be silently absorbed into a rights tranche.

## Clean test evidence

An external `git archive HEAD` was tested with bytecode and pytest cache disabled. Result: **67 passed, 1 failed** across the clean source-rights, governed Factory integration, task-state, rights-record, rights-projection, and migration tests. The sole failure is committed `tests/runtime/test_rights_governance_record.py::test_compatibility_matches_existing_artifact_rights_decision_and_sqlite_projection`: clean `ArtifactRightsDecision` rejects the newer fields `representation_artifact_id`, `rights_policy_version`, `provider_processing_policy_version`, and `assessment_authority` supplied by the compatibility test. This confirms a clean cross-layer schema mismatch.

A clean import probe reported: `governed_rights_policy=False`, `PROVIDER_POLICY_REGISTRY=False`, `v29=29`, and `GovernedReference` has no `rights_decision_ids`. The clean projection and migration subsets themselves passed (6 and 4 tests respectively).

No provider, model, source acquisition, network, spend, publication, release, watcher, GitHub, or follow-on action occurred. No synthetic source corpus was created.

## Safest next bounded allowlist

After a clean baseline is supplied for the overlapping dirty files, allow only:

- `src/charitygraph/runtime/rights_governance_projection.py` — add/read a narrow current-record lookup that verifies the v29 projection row and reloads the authoritative content-addressed record;
- `src/charitygraph/phase5_governed_factory_integration.py` — consume that authority for exact subject/scope/source/role/artifact/hash/lineage/policy binding before lowering;
- the corresponding focused projection and governed-preflight tests, plus one report.

Reuse the existing Fake Factory and v29 migration/projection tests; no new harness, provider adapter, source corpus, or scheduler is needed. Keep `runtime/catalog.py` out of this first integration slice unless a separately allowlisted physical-attempt hardening tranche is requested. Do not promote the dirty `artifact_rights_*` tables or dirty policy helper.

Acceptance cases: exact binding succeeds only for the current authoritative record; any changed subject, scope, source record, source role, representation artifact/hash, acquisition lineage, policy identity, supersession or revocation fails before task creation; absent expiry and equality at expiry are accepted, later dates fail; duplicate current/corrupt/missing authority fails closed; every blocked case creates no task, physical attempt, reservation, receipt, or cost row; re-entry and replacement identity changes create no side effects.

Provider-positive acceptance remains blocked pending the precise Data/Product Owner decision for the source-owned provider-policy ID/version registry, effective evidence, no-sharing posture, and renewal rule. That decision is the only genuine product authority missing for provider transmission; Option 1 rights governance itself is not missing.

