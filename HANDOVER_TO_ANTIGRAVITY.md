# Handover to Antigravity

Date: 3 November 2026 (Australia/Sydney).

## Executive Summary & State of play

The Product Owner permanently decommissioned the Drive Agent Bridge, JSON queue, Executor, Supervisor, Harness Repairer and overnight restarts. Do not restart or dispatch them. Development transfers to direct VS Code / Antigravity.

The managed launcher PID 47508 was stopped. Three Windows scheduled tasks (managed bridge liveness, overnight safety restart 0300 and 0800) were disabled. The Drive root bridge-status.json watcher_state is HALTED_DECOMMISSIONED. Existing queue items are archival, not instructions to execute.

This report records a preservation baseline, not product acceptance. Full multi-checkout sync is not yet certified.

## Current System & Code Base Health

No fresh full pytest run was completed during decommission. Existing reports are historical evidence only. Run offline tests before relying on the combined working state. Python >=3.12; install the dev extra from pyproject.toml. Entry point: charitygraph.cli:main; source: src/charitygraph; tests: tests/.

SQLite runtime catalogue state exists locally and has not been migrated or deleted. Pending migration status remains unverified; examine runtime/catalog.py and Data migration contracts before opening existing databases. Preserve SQLite WAL/SHM files together with their databases.

## Incomplete Work & Known Debt

Main checkout modified areas: bridge/bridge.py; bridge/g4_doc_export_ingress.py; src/charitygraph/bounded_authority.py; phase5_factory.py; phase5_t3_acnc_real_evidence_retention.py; phase5_t4d_e3_factory_handoff.py; runtime/catalog.py; source_rights.py and related tests. These represent concurrent local work, not a single reviewed implementation.

Recent work includes provider-authority binding, exact source/representation retention, physical identity and scope isolation, factory integration repair, project-cost reconciliation, operator health and real ACNC source ingestion. See reports/G4_FACTORY_INTEGRATION_THREE_TEST_REPAIR_V102_20261102.md and reports/G4_FIRST_REAL_CHARITY_PUBLICDATA_LOCAL_SOURCE_INGEST_20261103.md.

## Core Architecture Invariants for the New Agent

Read each repository AGENTS.md. Data owns canonical cross-product architecture and contracts: INTEGRATED_PRODUCT_AND_DATA_MODEL.md, SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md, TAXONOMY_AND_SCHEME_GOVERNANCE.md, IMPLEMENTATION_PLAN.md, TEST_PLAN.md and COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md.

Builder stores governed typed observations on durable subjects/scopes; public cards are release projections. Preserve subject identity, provenance, bindings, evidence, governed decisions and coverage as distinct states. SQLite is rebuildable operational state, never sole evidence authority.

Python controls deterministic preparation, scheduling, validation, cost and compilation; semantic work uses typed model tasks. Do not add language heuristics without the documented approval. Builder does not discover new source families. Admitted families: acnc_register, acnc_ais_bundle, ato_abr_dgr, official_website, annual_report, wikipedia_wikimedia, pfra. Preserve public contract 0.5 and immutable release bytes; coordinate schema/Viewer migrations explicitly. Do not manually edit generated projections.

Historical harness role restrictions are superseded only for this Owner-authorized teardown. They are not instructions to restart those roles.

## Immediate Next Tasks (Prioritized List)

1. Finish inventory and preservation of every historical worktree; verify remote refs before discarding any local directory.

2. Establish one working branch in VS Code and run the offline Builder suite; triage combined-baseline failures.

3. Verify catalogue migrations and source/representation/provider-rights lineage against the Data contracts.

4. Complete the real-charity evidence-to-answer product path and inspect the Viewer output against authoritative contracts.

5. Prioritize product delivery with the Owner; keep the harness permanently disabled.

## Exact pre-capture checkout inventory

### C:\CharityGraph-clean\charitygraph

Remote: https://github.com/gregorycwhill/charitygraph.git

Branch: gate3-cg406-remediation

HEAD: ff88fce5dbc514540e7886d2629638597f29cdf4

Local branches and tracking:
```
gate3-cg406-frozen-execution 61acc61d83c011e93cb362f377954940787f8a45 [ahead 4]
gate3-cg406-remediation ff88fce5dbc514540e7886d2629638597f29cdf4 
main cef02cb80c26ea4c52cd3c4ea97b996023ba686c
```

Recent history:
```
ff88fce bridge: commit gate4:engineering:20261103-rights-empty-v1
fbabffa bridge: commit gate4:engineering:20261103-g4-real-five-factory-v2-r01
5a2bbe3 bridge: commit gate4:engineering:20261103-g4-first-real-charity-rights-binding-clean-paths-v105-sol-005052-c8fe05c7
394e358 bridge: commit gate4:engineering:20261103-g4-factory-dirty-product-acceptance-v104-sol-002532-3e78696f
0a8f041 bridge: commit gate4:engineering:20261103-g4-first-charity-original-acnc-register-mirror-bind-v103-sol-001423-a5b1ffc4
0971e71 bridge: commit gate4:engineering:20261102-g4-first-charity-official-acnc-source-retention-v102-sol-20261102T113950Z-c5b8d103
2dba9b9 bridge: commit gate4:engineering:20261102-g4-t3-real-acnc-retention-product-v101-sol-20261102T111639Z-d75a8c13
b6c9f30 bridge: commit gate4:engineering:20261101-g4-t3-acnc-representation-receipt-rights-binding-v100-sol-20261101T092246Z-9b1da22b
c824011 bridge: commit gate4:engineering:20261101-g4-cgdoc1-clean-head-self-contained-repair-v99-sol-20261101T083200Z-4a6d8c2e
396d4cd bridge: commit gate4:engineering:20261101-g4-cgdoc1-fence-agile-adoption-attestation-repair-v98-sol-20261101T023023Z-65a766ff
932728a bridge: commit gate4:engineering:20261101-g4-cgdoc1-host-safe-clean-overlay-adoption-helper-v97-sol-20261101T021356Z-aeebac99
5bf3b53 bridge: commit gate4:engineering:20261101-g4-t3-five-subject-exact-representation-rights-v96-sol-20261101T013722Z-86b13f99
4eaa7ec bridge: commit gate4:engineering:20261101-g4-operator-alert-missing-health-repair-v95-sol-20261101T012714Z-72c6c98e
0ed0505 bridge: commit gate4:engineering:20261101-g4-operator-health-alert-contract-v94-sol-20261101T011400Z-79bb3d7f
2b95eb3 bridge: commit gate4:engineering:20261101-g4-provider-history-private-material-repair-v93-sol-20261101T010240Z-06632c5b
c571ac9 bridge: commit gate4:engineering:20261101-g4-provider-history-source-bound-adapter-v92-sol-20261101T002919Z-f47a93e0
2af1d06 bridge: commit gate4:engineering:20261101-g4-integrated-offline-recovery-rehearsal-v91-sol-20261101T000700Z-1d10779f
3114fce bridge: commit gate4:engineering:20261101-g4-run-inventory-collision-repair-v90-sol-1505-68bd27
70069ad bridge: commit gate4:engineering:20261101-g4-run-inventory-source-audit-v89-sol-1452-d2a4c9
7654e9c bridge: commit gate4:engineering:20261101-g4-cost-manifest-trust-repair-v88-sol-1406-d4d024
5fe83f4 bridge: commit gate4:engineering:20261031-g4-cost-population-authority-repair-v87-sol-4423bb96
33cf117 bridge: commit gate4:engineering:20261031-g4-cost-population-completeness-v86-sol-1235-44055b9c
0a3a2e8 bridge: commit gate4:engineering:20261031-g4-cost-identity-link-repair-v85-sol-1223-3b7cdb87
4fbd894 bridge: commit gate4:engineering:20261031-g4-phase5-project-cost-multi-attempt-hardening-v84-sol-1201-c5be0dd8
a9aa4cc bridge: commit gate4:engineering:20261031-g4-phase5-project-cost-reconcile-v83-sol-1046-6c27c1
e215f3c bridge: commit gate4:engineering:20261031-g4-doc-export-second-ingress-dormant-v82-sol-0957-04ff9b8f
50a9bd1 bridge: commit gate4:engineering:20261031-g4-operator-health-runtime-export-contract-v81-sol-0938-9a61713f
c9e349f bridge: commit gate4:engineering:20261031-g4-operator-health-usage-missingness-v80-sol-0901-8fce3f
799c85c bridge: commit gate4:engineering:20261031-g4-operator-health-catalogue-v79-sol-0837-e543a7
a058df5 bridge: commit gate4:engineering:20261031-g4-operator-health-dedup-v78-sol-0821-d3c788
```

Uncommitted inventory:
```
M bridge/bridge.py
 M bridge/g4_doc_export_ingress.py
 M docs/G4_O1B_SUPERVISORY_SUBMISSION.md
 M docs/G4_O1C_SUPERVISORY_SUBMISSION.md
 M reports/G4_E3_PRIVATE_FIVE_CHARITY_ANSWER_BRIEF_20261030.md
 M reports/G4_PHASE5_PROJECT_COST_RECONCILIATION_HARDENING_20261031.md
 M reports/G4_PROVIDER_AUTHORITY_REGISTRY_REPAIR_20261031.md
 M reports/G4_T4A4_SOURCE_OWNED_PROVIDER_CONTRACT_REGISTRY_20261029.md
 M src/charitygraph/bounded_authority.py
 M src/charitygraph/phase5_factory.py
 M src/charitygraph/phase5_t3_acnc_real_evidence_retention.py
 M src/charitygraph/phase5_t4d_e3_factory_handoff.py
 M src/charitygraph/runtime/catalog.py
 M src/charitygraph/source_rights.py
 M tests/runtime/test_task_state.py
 M tests/test_bridge_cutover.py
 M tests/test_bridge_doc_export_ingress.py
 M tests/test_phase5_factory.py
 M tests/test_phase5_governed_factory_integration.py
 M tests/test_phase5_t4d_e3_factory_handoff.py
 M tests/test_source_rights.py
?? CharityGraph-cleancharitygraphtmppytest-bridge-recovery/
?? evidence/cg406-proposition-relevance-remediation/
?? evidence/cg406-provider-development-replay/
?? evidence/cg406-public-source-transmission-policy/
?? evidence/cg406-rights-catalog-resolution/
?? evidence/cg406-v12-development-replay/
?? evidence/cg406-v12-inference-integrity/
?? evidence/cg406-v13-development-replay/
?? evidence/cg406-v14-final-development-replay/
?? evidence/gate3-cg405-identity-reconciliation-review/
?? evidence/gate3-cg405-identity-reconciliation/
?? evidence/gate3-final-semantic-review/
?? evidence/gate3-fresh-36-builder-preparation/
?? evidence/gate3-fresh-36-executable-demand-specification/
?? evidence/gate3-fresh-semantic-holdout-preparation/
?? evidence/gate3-fresh36-bounded-recovery-v1/
?? evidence/gate3-fresh36-semantic-execution-v1/
?? evidence/gate3-fresh36-semantic-execution-v2/
?? evidence/gate3-generic-discovery-contract-v15/
?? evidence/gate3-generic-discovery-contract/
?? evidence/gate3-question-first-subject-universe/
?? evidence/gate3-question-first-v15-preflight/
?? evidence/gate3-v15-execution-envelope-preflight/
?? evidence/gate3-v15-provider-free-execution-preflight/
?? evidence/gate3-v151-implementation/
?? evidence/gate4-t3-five-subject-v1/first-charity-official-acnc-source-retention-v1.json
?? evidence/gate4-t3-five-subject-v1/publicdata-20261026-four-charity-acquisition-receipts.json
?? evidence/gate4-t3-five-subject-v1/publicdata-20261026-four-charity-bindings.json
?? evidence/gate4-t3-five-subject-v1/publicdata-20261026-four-charity-rights-decisions.json
?? reports/G4_A3E_INTEGRATED_OFFLINE_20261021_V2.md
?? reports/G4_ACTUAL_PRODUCT_DISPATCH_REJECTION_DIAGNOSIS_20261102.md
?? reports/G4_BRIDGE_RECOVERY_ROUNDTRIP_20261024.md
?? reports/G4_BUILDER_OPERATOR_HEALTH_CATALOGUE_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_BUILDER_OPERATOR_HEALTH_DEDUP_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_BUILDER_OPERATOR_HEALTH_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_BUILDER_OPERATOR_HEALTH_USAGE_MISSINGNESS_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_CGDOC1_CLEAN_TARGET_OVERLAY_ACCEPTANCE_20261101.md
?? reports/G4_CGDOC1_CLEAN_TARGET_OVERLAY_REACCEPTANCE_20261102.md
?? reports/G4_CGDOC1_DIRTY_OPTIN_RECOVERY_ASSESSMENT_20261101.md
?? reports/G4_CGDOC1_FENCE_AGILE_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_CGDOC1_HOST_SAFE_ADOPTION_HELPER_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_COST_HARDENING_INDEPENDENT_REVIEW_RECOVERY_20261031.md
?? reports/G4_DOC_EXPORT_INGRESS_TIMEOUT_INDEPENDENT_REVIEW_20261031.md
?? reports/G4_DOC_EXPORT_SECOND_INGRESS_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_E1_FIVE_CHARITY_EVIDENCE_BACKED_PRODUCT_DEMONSTRATION_20261030.md
?? reports/G4_E2B_MANIFEST_SOURCE_RECORD_BINDING_INDEPENDENT_ACCEPTANCE_20261030.md
?? reports/G4_E2_SOURCE_NATIVE_ANSWER_PROJECTION_INDEPENDENT_ACCEPTANCE_20261030.md
?? reports/G4_E3_INDEPENDENT_RECONCILIATION_AND_MISSINGNESS_REVIEW_20261031.md
?? reports/G4_E3_MISSINGNESS_RIGHTS_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_FACTORY_INTEGRATION_THREE_TEST_REPAIR_V102_20261102.md
?? reports/G4_FIRST_REAL_CHARITY_PUBLICDATA_LOCAL_SOURCE_INGEST_20261103.md
?? reports/G4_FIVE_CHARITY_REAL_REGISTER_BINDING_20261103.md
?? reports/G4_GATE4_CLOSURE_GAP_AUDIT_20261031.md
?? reports/G4_INDUSTRIALISATION_EVIDENCE_REVIEW_20261021_A2.md
?? reports/G4_O1B_CONTROLLED_WINDOWS_CUTOVER_2026-10-20.md
?? reports/G4_O1C_ADOPTION_SCHEMA_EXACT_REVIEW_20261026.md
?? reports/G4_O1C_GIT_WRITE_BOUNDARY_RECERTIFICATION_20261026.md
?? reports/G4_O1C_GIT_WRITE_BOUNDARY_ROLLBACK_RECERTIFICATION_20261026.md
?? reports/G4_O1C_PROVENANCE_BOUND_ADOPTION_RECERTIFICATION_20261026.md
?? reports/G4_O1C_PROVENANCE_BOUND_ANCESTOR_RECERTIFICATION_20261026.md
?? reports/G4_O1C_SUPERVISORY_READONLY_20261021_A1.md
?? reports/G4_O1D_BRIDGE_OWNED_BOUNDED_COMMIT_BOOTSTRAP_REVIEW_20261027.md
?? reports/G4_O1D_BRIDGE_OWNED_BOUNDED_COMMIT_INDEPENDENT_RECERTIFICATION_NARROW_20261027.md
?? reports/G4_O1D_SUPERVISORY_ACCEPTANCE_20261021.md
?? reports/G4_O1E_O1F_CONTROLLED_CUTOVER_20261024.md
?? reports/G4_O1E_O1F_DOUBLE_LOOP_BOOTSTRAP_20261021.md
?? reports/G4_O1E_O1F_FAIL_CLOSED_REPAIR_20261024.md
?? reports/G4_O1E_O1F_RECERTIFICATION_20261024.md
?? reports/G4_O1E_O1F_RECERTIFICATION_20261024_REPAIR2.md
?? reports/G4_O1E_O1F_RECERTIFICATION_20261024_REPAIR2_FINAL.md
?? reports/G4_O1E_O1F_SUPERVISORY_ACCEPTANCE_20261022.md
?? reports/G4_OPERATOR_HEALTH_RUNTIME_EXPORT_INDEPENDENT_ACCEPTANCE_AND_INGRESS_FEASIBILITY_20261031.md
?? reports/G4_P1_GOVERNED_FACTORY_INTEGRATION_20261025.md
?? reports/G4_P2B_ACCEPTANCE_GATE4_READINESS_20261025.md
?? reports/G4_P2B_CATALOG_SCOPE_GUARD_20261025.md
?? reports/G4_P2C_BRIDGE_RECONCILIATION_20261026.md
?? reports/G4_P2C_CATALOG_PHYSICAL_ATTEMPT_IDENTITY_20261025.md
?? reports/G4_P2_GOVERNED_SCOPE_ISOLATION_20261025.md
?? reports/G4_P2_GOVERNED_SCOPE_ISOLATION_CORRECTED_20261025.md
?? reports/G4_P2_SOL_ACCEPTANCE_REVIEW_20261025.md
?? reports/G4_P2_SOL_ACCEPTANCE_REVIEW_CORRECTED_20261025.md
?? reports/G4_P2_SOL_P1_ARCHAEOLOGY_20261025.md
?? reports/G4_P3B1_ACCEPTANCE_P3B2_POLICY_ARCHAEOLOGY_20261026.md
?? reports/G4_P3B1_SOURCE_SUBJECT_PROVENANCE_20261026.md
?? reports/G4_P3B2_QUARANTINE_FORWARD_EVIDENCE_P3C_P4_ARCHAEOLOGY_20261026.md
?? reports/G4_P3B2_RIGHTS_POLICY_IDENTITY_20261026.md
?? reports/G4_P3C_A_INDEPENDENT_PRODUCT_CONFORMANCE_REVIEW_20261027.md
?? reports/G4_P3C_BASELINE_AND_ORDINARY_COMMIT_PROOF_20261027.md
?? reports/G4_P3C_B_P4_C_INDEPENDENT_PRODUCT_ACCEPTANCE_REVIEW_20261027.md
?? reports/G4_P3C_P4_ACCEPTED_ARTIFACT_REVISION_PROMOTION_CAPABILITY_20261026.md
?? reports/G4_P3C_P4_POST_ADOPTION_NEXT_TRANCHE_REVIEW_20261026.md
?? reports/G4_P3C_P4_PROVENANCE_BOUND_ADOPTION_20261026.md
?? reports/G4_P3C_P4_PROVENANCE_BOUND_ADOPTION_RETRY_20261026.md
?? reports/G4_P3C_PROVIDER_AUTHORITY_CLEAN_CATALOGUE_PROVENANCE_ARCHAEOLOGY_20261027.md
?? reports/G4_P3C_RIGHTS_RECORD_INDEPENDENT_ACCEPTANCE_MIGRATION_SEAM_20261026.md
?? reports/G4_P3_DURABLE_ARTIFACT_RIGHTS_FACTORY_20261026.md
?? reports/G4_P3_SOL_INDEPENDENT_ACCEPTANCE_20261026.md
?? reports/G4_P4_D_INDEPENDENT_OFFLINE_ACCEPTANCE_REVIEW_20261027.md
?? reports/G4_P4_E_INDEPENDENT_OFFLINE_ACCEPTANCE_REVIEW_20261027.md
?? reports/G4_P4_SOL_INDEPENDENT_ACCEPTANCE_P3C_AUTHORITY_20261026.md
?? reports/G4_PHASE5_COST_IDENTITY_REPAIR_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_PHASE5_COST_MANIFEST_TRUST_BOUNDARY_FOCUSED_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_PHASE5_COST_POPULATION_FALSE_POSITIVE_REPAIR_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_PHASE5_INTEGRATED_OFFLINE_RECOVERY_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_PHASE5_OPERATOR_ALERT_MALFORMED_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_PHASE5_OPERATOR_HEALTH_ALERT_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_PHASE5_PROJECT_COST_POPULATION_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_PHASE5_PROJECT_COST_RECONCILIATION_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_PHASE5_PROVIDER_HISTORY_EVIDENCE_ADAPTER_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_PHASE5_PROVIDER_HISTORY_PRIVATE_MATERIAL_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_PHASE5_RUN_INVENTORY_AUDIT_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_PHASE5_RUN_INVENTORY_COLLISION_DETERMINISM_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_PRODUCT_DIRTY_ALLOWLIST_ADMISSION_RELAX_20261102.md
?? reports/G4_PRODUCT_DIRTY_RECONCILIATION_ADOPTION_20261102.md
?? reports/G4_PROVIDER_AUTHORITY_REGISTRY_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_PROVIDER_REGISTRY_REACCEPTANCE_FORENSIC_20261031.md
?? reports/G4_T1_INTEGRATION_SEAM_RECONCILIATION_20261028.md
?? reports/G4_T2_CLEAN_ACCEPTANCE_20261029.md
?? reports/G4_T2_CLEAN_BASELINE_VERIFICATION_20261028.md
?? reports/G4_T2_EVIDENCE_BACKED_FACTORY_REHEARSAL_20261028.md
?? reports/G4_T2_T3_T4_SUPERVISORY_PLAN_20261028.md
?? reports/G4_T3_FIVE_SUBJECT_BINDER_INDEPENDENT_ACCEPTANCE_20261101.md
?? reports/G4_T3_FIVE_SUBJECT_RIGHTS_ASSESSMENT_20261028.md
?? reports/G4_T3_INTERNAL_PRIVATE_USE_INDEPENDENT_ACCEPTANCE_20261029.md
?? reports/G4_T3_T4D_PROVIDER_FREE_INTEGRATED_ACCEPTANCE_20261102.md
?? reports/G4_T3_T4_ADMISSIBILITY_DECISION_BRIEF_20261028.md
?? reports/G4_T4A10_FACTUAL_LOCAL_RUNTIME_ACCOUNTING_RECONCILIATION_20261030.md
?? reports/G4_T4A11_IMMUTABLE_CATALOGUE_INDEPENDENT_ACCEPTANCE_20261030.md
?? reports/G4_T4A2B_OFFLINE_PACKET_INDEPENDENT_ACCEPTANCE_20261029.md
?? reports/G4_T4A3_REAL_SEND_AUTHORITY_AND_BUDGET_READINESS_20261029.md
?? reports/G4_T4A4B_INDEPENDENT_ACCEPTANCE_20261029.md
?? reports/G4_T4A4_PROVIDER_CONTRACT_REGISTRY_INDEPENDENT_ACCEPTANCE_RECOVERY_20261029.md
?? reports/G4_T4A5_INDEPENDENT_ACCEPTANCE_20261029.md
?? reports/G4_T4A6_INDEPENDENT_ACCEPTANCE_20261029.md
?? reports/G4_T4A7_BUDGET_VERIFIER_EDGECASE_REPAIR_INDEPENDENT_ACCEPTANCE_20261029.md
?? reports/G4_T4A8R_DURABLE_ACCOUNTING_ADAPTER_INDEPENDENT_ACCEPTANCE_20261029.md
?? reports/G4_T4A8_READONLY_DURABLE_ACCOUNTING_SOURCE_EXPORT_20261029.md
?? reports/G4_T4A9B_SQLITE_ACCOUNTING_LINKAGE_INDEPENDENT_ACCEPTANCE_20261030.md
?? reports/G4_T4A9C_LINKAGE_COMPLETENESS_INDEPENDENT_ACCEPTANCE_20261030.md
?? reports/G4_T4A9_TIMEOUT_AND_PARTIAL_SQLITE_EXPORT_FORENSICS_20261030.md
?? reports/G4_T4A_POLICY_ACCEPTANCE_AND_T4A2_TIMEOUT_FORENSICS_20261029.md
?? reports/G4_T4A_PROVIDER_CONTRACT_IDENTITY_PROBE_INDEPENDENT_ACCEPTANCE_20261029.md
?? reports/G4_T4E_CLEAN_TARGET_CAS_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_T4E_CLEAN_TARGET_COMMIT_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_T4E_CLEAN_WORKTREE_ADOPTION_ROUTE_20261031.md
?? reports/G4_T4E_EXACT_RIGHTS_SCOPE_BOUNDARY_20261031.md
?? reports/G4_T4E_FOCUSED_TEST_DISCREPANCY_RECONCILIATION_20261031.md
?? reports/G4_T4E_HOST_READBACK_CONTEXT_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_T4E_HOST_READBACK_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_T4E_HOST_RECOVERY_INTEGRATION_DESIGN_20261031.md
?? reports/G4_T4E_RECOVERY_AUTHORITY_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_T4E_RECOVERY_AUTHORITY_REPAIR_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_T4E_TIMEOUT_DIRTY_OVERLAY_INDEPENDENT_RECONCILIATION_20261031.md
?? reports/G4_T4_E3_FACTORY_HANDOFF_INDEPENDENT_ACCEPTANCE_20261031.md
?? reports/G4_T4_FACTORY_E3_INTEGRATION_ARCHAEOLOGY_20261031.md
?? reports/G4_V101_RAW_FENCE_WINDOWS_REPARSE_INDEPENDENT_PROOF_20261102.md
?? src/charitygraph/phase5_offline_cohort_rehearsal.py
?? src/charitygraph/phase5_real_five_charity_factory.py
?? src/charitygraph/phase5_t4a8_durable_accounting_export.py
?? src/charitygraph/phase5_t4a_pilot_packet.py
?? src/charitygraph/phase5_t4a_real_pilot_preflight.py
?? src/charitygraph/phase5_t4a_sqlite_accounting_export.py
?? tests/test_bounded_authority_dirty_allowlist.py
?? tests/test_bounded_dirty_product_adoption.py
?? tests/test_phase5_governed_factory_rights.py
?? tests/test_phase5_offline_cohort_rehearsal.py
?? tests/test_phase5_rights_policy_identity_p3b2.py
?? tests/test_phase5_source_subject_provenance_p3b1.py
?? tests/test_phase5_t3_publicdata_acnc_api_source.py
?? tests/test_phase5_t3_publicdata_four_charity_real.py
?? tests/test_phase5_t4a8_durable_accounting_export.py
?? tests/test_phase5_t4a_pilot_packet.py
?? tests/test_phase5_t4a_real_pilot_preflight.py
?? tests/test_phase5_t4a_sqlite_accounting_export.py
```

Worktree inventory:
```
worktree C:/CharityGraph-clean/charitygraph
HEAD ff88fce5dbc514540e7886d2629638597f29cdf4
branch refs/heads/gate3-cg406-remediation
```

### C:\CharityGraph-clean\charitygraph-data

Remote: https://github.com/gregorycwhill/charitygraph-data.git

Branch: docs/gate3-closure-gate4-activation-2026-10-20

HEAD: f5f154cf2e3f107a9a2563c94626a0e39419fd3e

Local branches and tracking:
```
docs/gate3-closure-gate4-activation-2026-10-20 f5f154cf2e3f107a9a2563c94626a0e39419fd3e 
main 443d195abea91d7da111f5e573e90247ae823c36
```

Recent history:
```

```

Uncommitted inventory:
```

```

Worktree inventory:
```
worktree C:/CharityGraph-clean/charitygraph-data
HEAD f5f154cf2e3f107a9a2563c94626a0e39419fd3e
branch refs/heads/docs/gate3-closure-gate4-activation-2026-10-20
```

### C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph

Remote: https://github.com/gregorycwhill/charitygraph.git

Branch: charitygraph-structured-source-and-prose-harvest

HEAD: d0a4f5d12c57fa82a0eca99601f41927eddc6c41

Local branches and tracking:
```
bitemporal-governed-knowledge-v1 1fd7ecc4d46ba5f4b71813019c143781e5fca123 
cg-ethos-notability-certification-344-builder 6cd3624a5fa0bf876f760a2745971d2d041413fc 
cg-ethos-notability-foundations-341-builder febb65783538f86f6344206383f9c9de14dc9f81 
cg-ethos-notability-reality-corpus-342-builder fb1e999eca7d0d2748a5ee5df5e5bdd9b35d80b4 
cg-f2f-currentness-287 dccc7ab2440137205893d385a68d72863ca8550c 
cg-f2f-estimator-disposition-287 a7d2e66dfaff48e717491098af629909f589757e 
cg-finance-measurement-compatibility-287 215173392db12cdddfc4bff7f211fd86f2448b49 
cg-fundability-f0f1-builder c68260046ca887866a9abacdd6838ac03d3befeb 
cg-fundability-f2-builder 1f9b55c658fbbaa21356b1925e712fd58d455065 
cg-fundability-productisation-301-builder 04f02c31b5570b3788c7f3848e0cb3abbd02898b 
cg-fundability-recertification-303-builder 7de942f4f60f1b82170ffa85d2c14e6cddbd6912 
cg-fundraising-archaeology-287 a7d47f3f945a00ac3ef93efe7ab2cde8ab418b57 
cg-fundraising-cohort-regression-287 e384a5efacf9f3e6fc5856b716f4f89ded5ef5ff 
cg-fundraising-publication-288 ef55a9add5e8827e39d04d1a07750393064a7d13 
cg-fundraising-vocabulary-crosswalk-287 18d89958913313b286e9460b63691433241de4fd 
cg-industry-promotion-287 08ba60c203d70d5b70e4cb305ad3809963904388 
cg-money-attribution-grain-study-287 50af91b0c988d64ca867bc90de4dadfbafed522f 
cg-projection-compatibility-257 9b3e282cb9aeb06f8f30dc49c58f7f05595835b0 
cg-s0-attempt6-timestamp-canonicalization-repair 065c96dee91d893b61d89b50114a4cdd3237bd1c 
cg-s0-baseline-reconciliation-302 1eabebe7952792c88a436a225098cc94f10349d4 
cg-s0-cleanroom-reproducibility-286 b6eafaa92fd5815b7abdfc5f514d08c46baedac5 
cg-s0-locator-identity-286 08b499d00b03ee9d10822e3f6ed647c4cbd1cd81 
cg-s0-northstar-gap-audit-286 2fd804dd5b4ca3be48c12ab0a19813f043c83575 
cg-s0-observation-invariants-a1 99522687fc564086e6e3a5dfb014cbb7f8f9e1ab 
cg-s0-owner-attestation-binding-repair-001 c6d7c5dbccfbc3403b6074ef6a5f8ebe440c0590 
cg-s0-prelive-blocker-repair-002 ec4a194fef84590c4957191428e957e19eef747a 
cg-s0-structured-a3-endtoend-repair-284 0cf0017552e2a0608cd123ee16849767d7092a78 
cg-s0-structured-a3-endtoend-repair-286-consolidated a0f684ecd94f63dd30221c2aac22ff5dcf78ed2a 
cg-s0-t23-runtime-robustness-286 0df408d9d0edc277644eba7f42cfa7c94e984735 
cg-s0-t24-failure-injection-286 bff6e099435d275ed0882780bf6a50a71ba3bbdc 
cg-s0-typed-relationships-286 9bb0fe3a3e7bb23e5c4313b6629def426bb5bfbf 
cg-s0-usd-accounting-repair-001 c5a4ce32464f831bf616396a8be3859722ef81dc 
cg-s1-readiness-286 1b76c67f773bda6e9b5d84429aa3dd3626e0a186 
cg-semantic-demand-corrections-324 7d4626e9f705b650687c864f47ec77d0b7b03b5e 
cg-semantic-demand-corrections-325 6ef4a99ff51e42ffa15f6d9d4e0093d2785d8382 
cg-semantic-demand-corrections-326-terra e0119d581fa21f0148ef8b804611825678968e9e 
cg-source-universe-v1-publication 88cee017ad3ec4073f68f219c71e6db634110e17 [behind 1]
cg-t10-bounded-real-fundraising-cohort e384a5efacf9f3e6fc5856b716f4f89ded5ef5ff 
cg-t10-bounded-real-fundraising-cohort-v2 bdb65d3161068695402d545690e06df9ea893617 
cg-t13-precision-cohort 69a2e9dc107921bc3802cb9204ceb01b938fe648 
cg-typed-practice-campaign-provider-contracts-287 a54d5267d02afb4a0fadb1ed21df57f933cc76bc 
cg-visible-fundraising-profile-287 2c8a3312d471d83cc217362fe2154b222d98a257 
cg306-builder-machinery 5d983d4f4d683a20561fb4bbb18243e7b740a5f2 
cg309-builder-corrective 284fe605370164ad0a5e558dc1536bfa0ec1f413 
charitygraph-baseline-charity-corpus-v1 e9884c27a7a6f04949ec755fa7fd717ce6aadf71 
charitygraph-brand-reuse-builder 2b5a30041ce0123b34c2e2919c5cd12d9ba32c3a 
charitygraph-builder-pr2-minimum-contracts c67b794531cbf3f18aa808e7ac7325d963894d9d 
charitygraph-builder-pr3-sqlite-ledger d5e096fdd0f299402ada41c9bdda5e4cc0ca5b5e 
charitygraph-builder-prA-evidence-source-registry 4885507af5e543c2f87ccd1637df2a33bcbdf81a 
charitygraph-builder-prB-knowledge-persistence f8497afecdffae99d40a4103b905b6c0a8b03bbb 
charitygraph-compact-consolidated-hardening 8acf60fc2436e18a28d8ca45097c5d74ccdad559 
charitygraph-compact-knowledge-end-to-end 7ff0ec430be6aa87186c20b6a86cb11dbe95cfaa 
charitygraph-compact-knowledge-persistence e53ea17f84e7a6a9e0b3d74d751715b387a39c65 
charitygraph-compact-knowledge-reality-slice 26b2d2640ebc28a82bb83936d580e521434c360e 
charitygraph-complete-card-reality-slice 8d597e214db5b6bc53c385f03ba10bc6549e0271 
charitygraph-conduct-compliance-phase3 1793b852604893b43999eea724fe20214c0ce3ae 
charitygraph-direct-service-phase3 00a1484b4843a7cc4a87b334afa1b387653ed6fc [gone]
charitygraph-direct-service-real-run-phase3 e8641f1135ac7294f5f64c5fbacc87b51a77590d 
charitygraph-discovery-operational-status c16c17a7765cf123daf266ef37ed74c26a04258a 
charitygraph-discovery-v2-dispatch 21c9dc7c58e3eac7025620673b20b95070ef033e 
charitygraph-fresh18-v2-parser-repair 3f14d9f18dae3401af3634164cc174d810c65002 
charitygraph-full-corpus-compact-reality-slice d6e138d0308933a89cd8a0b171d3c94467a63e27 
charitygraph-governed-un-sdg-v1 1cd25842fc331f4e9f43e7acc3e5b32d5d42fea8 
charitygraph-model-execution-safety 1c45a0359914285fd2b96b21c9cc62a5f5c61347 
charitygraph-modest-website-luna-classie-v06 3b759d207bdef8a47f051bc9beca7cba7c9649f4 
charitygraph-native-discovery-executor 28b39e210a05a7840d7cb268b5752fef77baf706 
charitygraph-native-induction-v1 3db9c9b61d2833a31042295e609eb0a4625faf84 
charitygraph-native-lifecycle-harness 5d9aa70ed469a976edc3b12f84b2c36223267ecf 
charitygraph-native-program-discovery a78345aa83ee2948f8cae714f9b00faae0f07fc5 
charitygraph-native-v4-faceted-disposition 12c5e7fa8841a0bd599e49b6d91d54758a845998 
charitygraph-native-v4r-faceted-disposition-repair 9eb2f4210b4861f967f364495e57ee839113c6c3 
charitygraph-native-v5-overlay-lifecycle 875727141c076b943a6bc13846c56ad2a0f1ade9 
charitygraph-native-v5r-overlay-quality-lifecycle df5033ae982e2df185c94ab078826f22dec811d2 
charitygraph-native-v5rr-executable-lifecycle 2a7110554bee56829b294b2d423ac477e59d8780 [behind 286]
charitygraph-native-v5rr-overlay-lifecycle 0366c625c427470ff6917b2eb31381fea9913c9c 
charitygraph-north-star-projection-lens 6aa9f96179c281dda6674ec8efdd1054836ce93a 
charitygraph-phase1-pre-run-engine d526c666e72d7a7c17f8517432491688cd42abb6 
charitygraph-phase3-relationship-role-proof 72a3918b89235c98558e3123eed989256d59bf1c 
charitygraph-playbooks-cross-repo-links c443f64c499f3b3cf2383a4ebe810d15a7b515b2 
charitygraph-product-docs-v2-links 55bdacc226a6f01ad70cece3f978ceeea16bcbb7 
charitygraph-product-docs-vnext b1727557ed16182ae611cfef23053ebbafdaacf4 
charitygraph-program-discovery-v3-1-fresh12 e72c954574ae8c695e4b344bc0c0344591fbd40f 
charitygraph-program-discovery-v3-contract c991e86a371fc57233a2aedde41ec365c18036fe 
charitygraph-program-subject-promotion 64f593dc766ec594fc008544978539dbe9a64d6e 
charitygraph-prospective-repeatability-safety bbce87ea27e872aa71dbf81b223b8ec9b306c27d 
charitygraph-reality-slice1-dev-preflight 1a9d76a8993cb4891b5a7b944ee6b3430e5c49a3 
charitygraph-reality-slice1-llm-semantic-economics 5c4e790725f14cce4e334d5b1b7996c761f4870b 
charitygraph-reality-slice1-program-evidence-expansion eb26968ae2b5fd789d64641d4116aa792749b1ae 
charitygraph-reality-slice1-scoped-benchmark-v2 f8c7aea1bfde8d7d85e7e1d24d0df35efa5f4fd0 
charitygraph-section18-evaluation-pressure-case 07f3843c0276ecef89a56821ebc072e9d29fff65 
charitygraph-semantic-llm-gate 0ba15272e9984cdccdc3f5c5036fcb4021c56aa5 
charitygraph-semantic-result-lineage 38d80a115e4f30cc1f54cec3c116d33345b86813 
charitygraph-sparse-luna-classie-v05 3d4b27dce8514d568b6759696188d7cabe421ddd 
charitygraph-sparse-whole-card-calibration-v01 365fcdea5c70b303367ca5b3d5c25066f96518cf 
charitygraph-structured-source-and-prose-harvest d0a4f5d12c57fa82a0eca99601f41927eddc6c41 [ahead 13]
charitygraph-task-1 adaf182b51bc897a6b8be1e05e586ef580e7727e 
charitygraph-task-1-test-baseline cabe6b37a0bec6b2c010a368d706d52304678998 
charitygraph-v07-domain-graph-semantics 8442efae4f1f1a5ee21423e19864da1e565bdb30 
charitygraph-whole-card-calibration-v01 7bc5545ac0619896aa990005ded086ab82d4f91c 
charitygraph-whole-card-calibration-v01-luna-retry 02ba678fc40addf40b62405d817bca739dc51b0c 
charitygraph-worldvision-luna-knowledge-v02 d67cd52971e16db9a522d039811414e53221a3ad 
charitygraph-worldvision-luna-sdg-v03 d09c48af1adbac1c8cbc2668f2e6350c081aafbc 
charitygraph-worldvision-terra-sdg-review-v04 53fad72a1001fe3be90c1fc7354617a50f105ebd 
docs-builder-machinery-v1 afcf4628cfc44ff1c5ba308dac1971b178ffaab7 [behind 13]
main 3b0794e9dac1c40ea68f290110ad7645b3661bc2 [behind 276]
phase4-p4e1-packaging-routing-v1 ebb659a4afc9a1af0882a5b96d72ab5c08c72a81 
phase5-direct-service-v1.2-cutover-v1 3c8049293de8839a4cdc184bd8996382abc5dec1 
phase5-execution-packet-v1 804ab80b90eddf7739da2d2b9633cab9e3c829f0 
phase5-factory-chaos-rehearsal-v1 a3af91d301ed6bcc711764bac23c74e816ccec3c 
phase5-factory-core-chaos-v1 048e3a638fea91264b72819860292fc097fc3884 
phase5-factory-delivery-economics-v1 ba8cc87003a7361f1e9e851b117009ef27e662cf 
phase5-first-paid-discovery-control-v1 b69ab9f3ec7c3479d1c2a6829a67fa4198f5746a 
phase5-north-star-completion-v1 f247c8c68ff6dcf4424df641eabe70a0cad6fd68 
phase5-openai-batch-adapter-v1 499a20ec3a1f295f12489c2e52a4c45d4472f729 
phase5-overnight-specialist-closure 49ae6d54910d8001ce08197dd95adf11b5d26f44 
phase5-real-provider-dry-run-v1 697c1130a0d3972abf77fea8c6ce4d439e697d15 
phase5-semantic-contract-registry-v1 9dd6f7b4517b17191f08d822a2d3bd131b270493 
phase5-top100-baseline-corpus-v1 5c2bcc0274bf5bb1584ba655a655ca13636675f9 
phase5-top100-factory-preflight-v1 4f53a8a83555a6d7c01faa5a44c16f2dfb8012ba 
phase5-top100-subject-bootstrap-v1 dff11b45ff2165f73000f3d98750a3587824a131 
phase5-tranche-c1-section7-reprojection cf7d27a9de4474792edb72b5d8467f207db44e40 
phase5-tranche-c2-section14-funding 515f692feeef0e312ddb73ad05fb9796145627de 
phase5-tranche-c3-sections3-6-11 8605ffc14198a9ae9ddebee7bc41a398b1ee144e 
phase5-tranche-c4-section13-finance c20396fdfed4ff481d7bce556bafa2f5ce616ecc 
phase5-tranche-c5-cross-cutting 526baec3fb555afacac449470b7be3cd6446caf2 
review-snapshot-2026-09-11 b69ab9f3ec7c3479d1c2a6829a67fa4198f5746a 
s0-attempt10-prelaunch 780285c3679a543a4eb15d4e9ee25baeb655fdf1 
s0-attempt18-locator-body-repair fe854c5bcae2ec264cae78a3de7bac32f136f61d 
s0-attempt21-successor-builder 228066e00bc7dec07a00ddcd45fed07372f0bda7 
s0-attempt9-locator-search-packet-repair 537a365edec461b0da6afabfc82354eeb1deb3b1 
s0-canonical-provider-accounting 0fb663ae5865be416cfa42f378307c2edd03af91 
s0-checkpoint-attempt-generic-v1 ebb7c0e3c8e367537e7bf0c7ac8ff39dea7d4a9b 
s0-identity-lineage-repair-builder abe60fb6ecffddefae8bd2625128271b8124bc74 
s0-live-boundary-integration-repair-v1 529550c36f169e8693311bb084fe238cc89a3e03 
s0-locator-http-adapter-repair 54ff44379b798390c9717c26f7b81b37d5177167 
s0-locator-subject-population-repair-v1 b99282613a7ffafccdc95f728e316fd8510ecad2 
s0-orchestration-runtime-v1 815d64c189d5eb66a9d096a502a3a33cb7d832ed 
s0-physical-bundle-crossing-semantics-repair-v1 696e08e5bf5132d109161226b70800d118ab521b 
s0-poststabilisation-local-repair dcbdb41e822cba81cc021f18c631904a84a68560 
s0-runtime-source-authority-repair-v1 499d86596be99537418c24292c5fccb56077ca90 
s0-web-locator-discovery-repair c415172beb7ce1c3251e1b00b7ad054caf610224 
s0-web-search-sources-accounting-repair 293740420feb73aa985664d9c03120b0841c2052 
scale-s0-acquisition-packet-bridge dd8f3fcf0426753a798169b03b6b00f48b2e61ec [behind 109]
scale-s0-authorisation-package 22fa3cf5e8e6be2b7ed7e19ed3dff992009ed4b8 
scale-s0-execution-identity-binding 918de807eb557a48cb1d6448b20e1800529671e6 
scale-s0-factory-hardening 68574a0b0dcc0985369ce933195a0678c235b555 [ahead 2, behind 3]
scale-s0-policy-calibration 535d8701cad0236cfe0a679372f770dd092a9697 
scale-s0-product-owner-authorisations 8262f538ccd1ccfbf289532cd5001e61a3f26a0e 
semantic-lab-principles c8c31dd1c2798bfc2cb40bf368e90f59c1101b55 
spike-10-reconnect-islands-ii-terra-161 4eefe7c272a1b3442bb72f44801f20ee53e8b72f 
t04-practice-campaign-provider 4b2adfb02838b465b5d1be3f59817522754508d6 
terra-s0-provider-boundary-a1 a5526fce88ef60e8d677b7504d1daeaa05c294e8 
terra-s0-structured-authority-repair c91f8b99edc66b0b770c3ab8017d7eb15e7e8972 
terra/fundraising-canonical-vocabulary-v1 741b73081f44b0146f230b6a7c98f84a2afe039c 
terra/t02-close-highest-method-gap dc1c96bfd10f26c304b1c3946cae7e4514893fff 
terra/t03-close-second-method-gap 1704cf0ece42f8433b544967d59ed5e28a0f2714 
terra/t03-source-acquisition-cache 28c0ef46f54268ef1a548f4b0cc51f70d285bee7 
terra/t04-temporal-method-history 4ecb3f67916616b01b18d9aa449e92af6e7184d1 
terra/t05-provider-platform-network 8b15adcf59e5d80f67a7ccd479eef2b30ea21056 
terra/t06-enforce-safe-fundraising-financial-derivatives 88221ceef5302a1cec9d03118b8a9d93aa53a621 
terra/t06-identity-binding-hardening 63cc629b17fecc5c3039e24866fcfaec16f187f4 
terra/t06-multiyear-fundraising-finance 9cdc84c29dae09edeada7cabf4742a950e73c655 
terra/t07-evidence-dedup-conflict ecc9dff1185f4d875d234b3ac5fc6ef9fcd25fb8 
terra/t07-govern-industry-source-promotion-paths 05a28f42f127d6ff35ed1291ad21628410f8ba42 
terra/t07-practice-campaign-provider-disambiguation 9e1ab701c3a72ac153a7e8bd665c20738403062f 
terra/t08-contradiction-negative-controls 470f7d4b5c932fa9328a7e4091dbbb7128b492c0 
terra/t08-migrate-legacy-fundraising-observation cb1ca40a07c5f7183944d0bc1c165039415f4f95 
terra/t08-typed-money-scope-linkage bda2a7cc48c10aad9eaab13d89d99794e6de3db0 
terra/t09-finance-extraction-normalisation 89bec488d5ee33697c5068e177102d142dd9d557 
terra/t09-integrate-visible-fundraising-card-api 9ebe417e6d2dd7f79acbe86f0546bdd763387301 
terra/t09-safe-derived-financial-metrics 0aede0cd03176f77b86b7f644f21c085c3548550 
terra/t09-user-question-regression d0a4f5d12c57fa82a0eca99601f41927eddc6c41 
terra/t09-user-question-regression-clean a0590c86abdc54110218805306be53db7db5a21d 
terra/t10-cross-section-integrity 0edd49403c32ff14323793f699729c6a15e67a31
```

Recent history:
```

```

Uncommitted inventory:
```
M AGENTS.md
 M ARCHITECTURE.md
 M scripts/run_v12_from_preflight.py
 D scripts/run_v12_large_harvest.py
 M src/charitygraph/models.py
 M src/charitygraph/north_star_projection.py
?? .campaign-builder/
?? .s0-factory-builder/
?? .s0-owner-attestation-builder/
?? .s0-validation/
?? .t06-fundraising-vocabulary/
?? .t08-typed-money-scope-linkage/
?? .t09-safe-derived-financial-metrics/
?? BUILDER_MACHINERY.md
?? artifacts/
?? charitygraph-archaeology-inventory.json
?? charitygraph-archaeology-summary.md
?? charitygraph-artefact-lineage-edges.json
?? docs/FUNDRAISING_CARD_PROJECTION_V1.md
?? scripts/finalize_megarun8_limits.py
?? scripts/reality_spike.py
?? scripts/reality_spike_4_disposable_bridge.py
?? scripts/reality_spike_5_disposable_bridge.py
?? scripts/reality_spike_6_source_ablation.py
?? scripts/reality_spike_8_architecture_inversion.py
?? scripts/reality_spike_v2_acnc_first.py
?? scripts/reality_spike_v3_sunrise_acnc_data.py
?? scripts/run_megarun3_blind_cohort.py
?? scripts/run_megarun3_product_blind_test.py
?? scripts/run_megarun3_raw_report_furnace.ps1
?? scripts/run_megarun3_twenty_charity_dryrun.py
?? scripts/run_megarun4_representation_boundary.py
?? scripts/run_megarun6_forced_report_replay.py
?? scripts/run_megarun7_archive_rich.py
?? scripts/run_megarun8_rich_semantic_furnace.py
?? scripts/run_megarun8b_direct_semantic.py
?? src/charitygraph/fundraising_joint_coverage.py
?? src/charitygraph/projection_compatibility.py
?? src/charitygraph/wikipedia_acquisition.py
?? tests/contracts/test_projection_compatibility.py
?? tests/fixtures/fundraising_card_projection.json
?? tests/test_fundraising_card_projection.py
?? tests/test_fundraising_joint_coverage.py
?? tests/test_reality_spike_v3_acnc_adapter.py
?? tests/test_wikipedia_acquisition.py
```

Worktree inventory:
```
worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph
HEAD d0a4f5d12c57fa82a0eca99601f41927eddc6c41
branch refs/heads/charitygraph-structured-source-and-prose-harvest

worktree C:/CharityGraph-runtime/attempt18-builder
HEAD fe854c5bcae2ec264cae78a3de7bac32f136f61d
branch refs/heads/s0-attempt18-locator-body-repair

worktree C:/CharityGraph-runtime/attempt19-builder
HEAD 92683f96bc5fbe50e71a82466919380b0293f108
detached

worktree C:/CharityGraph-runtime/attempt20-cert
HEAD 6f00f222c9991f8f9d7f008d9a6acf1251ca1451
detached

worktree C:/CharityGraph-runtime/attempt20-history-reconcile-20260926
HEAD 175b74c7736bd8a038b03aa08253979a6ffdda27
detached

worktree C:/CharityGraph-runtime/attempt6-prelive-20260921
HEAD 065c96dee91d893b61d89b50114a4cdd3237bd1c
branch refs/heads/cg-s0-attempt6-timestamp-canonicalization-repair

worktree C:/CharityGraph-runtime/attempt8-builder-canonical
HEAD d4b07799fc6a26ee088cccf8db1295d2e1b1b23e
detached

worktree C:/CharityGraph-runtime/builder-corrective
HEAD 284fe605370164ad0a5e558dc1536bfa0ec1f413
branch refs/heads/cg309-builder-corrective

worktree C:/CharityGraph-runtime/builder-s0-web-search-sources-accounting-repair
HEAD 293740420feb73aa985664d9c03120b0841c2052
branch refs/heads/s0-web-search-sources-accounting-repair

worktree C:/CharityGraph-runtime/cg-builder-machinery-v1
HEAD 4eefe7c272a1b3442bb72f44801f20ee53e8b72f
branch refs/heads/spike-10-reconnect-islands-ii-terra-161

worktree C:/CharityGraph-runtime/cg-ethos-notability-certification-344-builder
HEAD 6cd3624a5fa0bf876f760a2745971d2d041413fc
branch refs/heads/cg-ethos-notability-certification-344-builder

worktree C:/CharityGraph-runtime/cg-ethos-notability-foundations-builder-341
HEAD fb1e999eca7d0d2748a5ee5df5e5bdd9b35d80b4
branch refs/heads/cg-ethos-notability-reality-corpus-342-builder

worktree C:/CharityGraph-runtime/cg-f2f-currentness-287
HEAD dccc7ab2440137205893d385a68d72863ca8550c
branch refs/heads/cg-f2f-currentness-287

worktree C:/CharityGraph-runtime/cg-f2f-estimator-disposition-287
HEAD a7d2e66dfaff48e717491098af629909f589757e
branch refs/heads/cg-f2f-estimator-disposition-287

worktree C:/CharityGraph-runtime/cg-finance-measurement-compatibility-287
HEAD 215173392db12cdddfc4bff7f211fd86f2448b49
branch refs/heads/cg-finance-measurement-compatibility-287

worktree C:/CharityGraph-runtime/cg-fundability-builder
HEAD 1f9b55c658fbbaa21356b1925e712fd58d455065
branch refs/heads/cg-fundability-f2-builder

worktree C:/CharityGraph-runtime/cg-fundability-product-builder
HEAD 04f02c31b5570b3788c7f3848e0cb3abbd02898b
branch refs/heads/cg-fundability-productisation-301-builder

worktree C:/CharityGraph-runtime/cg-fundraising-archaeology-287
HEAD a7d47f3f945a00ac3ef93efe7ab2cde8ab418b57
branch refs/heads/cg-fundraising-archaeology-287

worktree C:/CharityGraph-runtime/cg-fundraising-cohort-regression-287
HEAD e384a5efacf9f3e6fc5856b716f4f89ded5ef5ff
branch refs/heads/cg-fundraising-cohort-regression-287

worktree C:/CharityGraph-runtime/cg-fundraising-publication-288
HEAD ef55a9add5e8827e39d04d1a07750393064a7d13
branch refs/heads/cg-fundraising-publication-288

worktree C:/CharityGraph-runtime/cg-fundraising-t03
HEAD 1704cf0ece42f8433b544967d59ed5e28a0f2714
branch refs/heads/terra/t03-close-second-method-gap

worktree C:/CharityGraph-runtime/cg-fundraising-t11-cleanroom
HEAD 5424296e94dfc679008e300aef214be8aa0e092d
detached

worktree C:/CharityGraph-runtime/cg-industry-promotion-287
HEAD 08ba60c203d70d5b70e4cb305ad3809963904388
branch refs/heads/cg-industry-promotion-287

worktree C:/CharityGraph-runtime/cg-money-attribution-grain-study-287
HEAD 50af91b0c988d64ca867bc90de4dadfbafed522f
branch refs/heads/cg-money-attribution-grain-study-287

worktree C:/CharityGraph-runtime/cg-s0-baseline-302
HEAD 1eabebe7952792c88a436a225098cc94f10349d4
branch refs/heads/cg-s0-baseline-reconciliation-302

worktree C:/CharityGraph-runtime/cg-s0-cleanroom-286-builder
HEAD b6eafaa92fd5815b7abdfc5f514d08c46baedac5
branch refs/heads/cg-s0-cleanroom-reproducibility-286

worktree C:/CharityGraph-runtime/cg-s0-locator-identity-286
HEAD 08b499d00b03ee9d10822e3f6ed647c4cbd1cd81
branch refs/heads/cg-s0-locator-identity-286

worktree C:/CharityGraph-runtime/cg-s0-observation-invariants-a1
HEAD 99522687fc564086e6e3a5dfb014cbb7f8f9e1ab
branch refs/heads/cg-s0-observation-invariants-a1

worktree C:/CharityGraph-runtime/cg-s0-prelive-blocker-repair-002
HEAD c5a4ce32464f831bf616396a8be3859722ef81dc
branch refs/heads/cg-s0-usd-accounting-repair-001

worktree C:/CharityGraph-runtime/cg-s0-typed-relationships-286
HEAD 9bb0fe3a3e7bb23e5c4313b6629def426bb5bfbf
branch refs/heads/cg-s0-typed-relationships-286

worktree C:/CharityGraph-runtime/cg-s1-readiness-286
HEAD 1b76c67f773bda6e9b5d84429aa3dd3626e0a186
branch refs/heads/cg-s1-readiness-286

worktree C:/CharityGraph-runtime/cg-t02-method-gap
HEAD dc1c96bfd10f26c304b1c3946cae7e4514893fff
branch refs/heads/terra/t02-close-highest-method-gap

worktree C:/CharityGraph-runtime/cg-t08-contradiction-negative-controls
HEAD 470f7d4b5c932fa9328a7e4091dbbb7128b492c0
branch refs/heads/terra/t08-contradiction-negative-controls

worktree C:/CharityGraph-runtime/cg-t10-bounded-real-fundraising-cohort
HEAD bdb65d3161068695402d545690e06df9ea893617
branch refs/heads/cg-t10-bounded-real-fundraising-cohort-v2

worktree C:/CharityGraph-runtime/cg-t10-cross-section-integrity
HEAD 0edd49403c32ff14323793f699729c6a15e67a31
branch refs/heads/terra/t10-cross-section-integrity

worktree C:/CharityGraph-runtime/cg-t13-precision-cohort
HEAD 69a2e9dc107921bc3802cb9204ceb01b938fe648
branch refs/heads/cg-t13-precision-cohort

worktree C:/CharityGraph-runtime/cg-typed-practice-campaign-provider-contracts-287
HEAD a54d5267d02afb4a0fadb1ed21df57f933cc76bc
branch refs/heads/cg-typed-practice-campaign-provider-contracts-287

worktree C:/CharityGraph-runtime/cg-visible-fundraising-profile-287
HEAD 2c8a3312d471d83cc217362fe2154b222d98a257
branch refs/heads/cg-visible-fundraising-profile-287

worktree C:/CharityGraph-runtime/cg306/builder
HEAD 5d983d4f4d683a20561fb4bbb18243e7b740a5f2
branch refs/heads/cg306-builder-machinery

worktree C:/CharityGraph-runtime/cg348-pilot-builder
HEAD 74689a9a04f2e5ee58fc7303a29157c503495f02
detached

worktree C:/CharityGraph-runtime/cg355-builder
HEAD 5a9ca4e594c8082ea091e717876e1d2013e8f059
detached

worktree C:/CharityGraph-runtime/cg358-builder-audit
HEAD 5a9ca4e594c8082ea091e717876e1d2013e8f059
detached

worktree C:/CharityGraph-runtime/cg383-builder
HEAD cef02cb80c26ea4c52cd3c4ea97b996023ba686c
detached

worktree C:/CharityGraph-runtime/cg401c-builder
HEAD cef02cb80c26ea4c52cd3c4ea97b996023ba686c
detached

worktree C:/CharityGraph-runtime/cg401f-builder
HEAD 2bfd86d424fd47ec35ae6a97b056cdb448ea3802
detached

worktree C:/CharityGraph-runtime/cg403-builder
HEAD 8e76372406fbf08a52beb3aa39ba93fa735b7e8b
detached

worktree C:/CharityGraph-runtime/projection-compatibility-257
HEAD 9b3e282cb9aeb06f8f30dc49c58f7f05595835b0
branch refs/heads/cg-projection-compatibility-257

worktree C:/CharityGraph-runtime/projection-compatibility-261-baseline
HEAD eedf561a204d14bf235fdc5e322054f036b7fcb0
detached

worktree C:/CharityGraph-runtime/s0-attempt20-final-rebind-builder
HEAD 9b84b09dcdde0f31ba8662e471d56b514cf6064c
detached

worktree C:/CharityGraph-runtime/s0-attempt21-successor-builder
HEAD 228066e00bc7dec07a00ddcd45fed07372f0bda7
branch refs/heads/s0-attempt21-successor-builder

worktree C:/CharityGraph-runtime/s0-attempt3-preparation-builder
HEAD e43ca61a44c250d4baad2c370870d3fdd15639ec
detached

worktree C:/CharityGraph-runtime/s0-attempt4-preparation/builder
HEAD ca587fc54eabc683684b95e3f6cda4b2a330e1ee
detached

worktree C:/CharityGraph-runtime/s0-attempt7-builder
HEAD d4dd962aac2630c48310a89551a03dfa7caf8f7a
detached

worktree C:/CharityGraph-runtime/s0-identity-lineage-builder
HEAD abe60fb6ecffddefae8bd2625128271b8124bc74
branch refs/heads/s0-identity-lineage-repair-builder

worktree C:/CharityGraph-runtime/s0-locator-http-adapter-repair
HEAD 54ff44379b798390c9717c26f7b81b37d5177167
branch refs/heads/s0-locator-http-adapter-repair

worktree C:/CharityGraph-runtime/s0-locator-subject-population-repair
HEAD b99282613a7ffafccdc95f728e316fd8510ecad2
branch refs/heads/s0-locator-subject-population-repair-v1

worktree C:/CharityGraph-runtime/s0-postmerge-main
HEAD 00d3abb71c03122759a158b15d78abdb89452c69
detached

worktree C:/CharityGraph-runtime/s0-poststabilisation-builder
HEAD dcbdb41e822cba81cc021f18c631904a84a68560
branch refs/heads/s0-poststabilisation-local-repair

worktree C:/CharityGraph-runtime/s0-runtime-source-authority-repair-v1-builder
HEAD 499d86596be99537418c24292c5fccb56077ca90
branch refs/heads/s0-runtime-source-authority-repair-v1

worktree C:/CharityGraph-runtime/s0-web-locator-builder
HEAD c415172beb7ce1c3251e1b00b7ad054caf610224
branch refs/heads/s0-web-locator-discovery-repair

worktree C:/CharityGraph-runtime/t03-source-acquisition-cache
HEAD 28c0ef46f54268ef1a548f4b0cc51f70d285bee7
branch refs/heads/terra/t03-source-acquisition-cache

worktree C:/CharityGraph-runtime/t04-practice-campaign-provider
HEAD 4b2adfb02838b465b5d1be3f59817522754508d6
branch refs/heads/t04-practice-campaign-provider

worktree C:/CharityGraph-runtime/t05-provider-platform-network
HEAD 8b15adcf59e5d80f67a7ccd479eef2b30ea21056
branch refs/heads/terra/t05-provider-platform-network

worktree C:/CharityGraph-runtime/t06-identity-binding-hardening
HEAD 63cc629b17fecc5c3039e24866fcfaec16f187f4
branch refs/heads/terra/t06-identity-binding-hardening

worktree C:/CharityGraph-runtime/t06-safe-fundraising-financial-derivatives
HEAD 88221ceef5302a1cec9d03118b8a9d93aa53a621
branch refs/heads/terra/t06-enforce-safe-fundraising-financial-derivatives

worktree C:/CharityGraph-runtime/terra-attempt13-builder
HEAD 529550c36f169e8693311bb084fe238cc89a3e03
branch refs/heads/s0-live-boundary-integration-repair-v1

worktree C:/CharityGraph-runtime/terra-fundraising-canonical-vocabulary-v1
HEAD 741b73081f44b0146f230b6a7c98f84a2afe039c
branch refs/heads/terra/fundraising-canonical-vocabulary-v1

worktree C:/CharityGraph-runtime/terra-s0-a3-endtoend-repair-284
HEAD 0cf0017552e2a0608cd123ee16849767d7092a78
branch refs/heads/cg-s0-structured-a3-endtoend-repair-284

worktree C:/CharityGraph-runtime/terra-s0-a3-endtoend-repair-286-consolidated
HEAD a0f684ecd94f63dd30221c2aac22ff5dcf78ed2a
branch refs/heads/cg-s0-structured-a3-endtoend-repair-286-consolidated

worktree C:/CharityGraph-runtime/terra-s0-stabilisation
HEAD 513d5579f8d839b15fbd5f8150b208a4a5af71d2
detached

worktree C:/CharityGraph-runtime/terra-s0-structured-authority-repair
HEAD c91f8b99edc66b0b770c3ab8017d7eb15e7e8972
branch refs/heads/terra-s0-structured-authority-repair

worktree C:/CharityGraph-runtime/terra-t04-temporal-method-history
HEAD 4ecb3f67916616b01b18d9aa449e92af6e7184d1
branch refs/heads/terra/t04-temporal-method-history

worktree C:/CharityGraph-runtime/terra-t06-multiyear-fundraising-finance
HEAD 9cdc84c29dae09edeada7cabf4742a950e73c655
branch refs/heads/terra/t06-multiyear-fundraising-finance

worktree C:/CharityGraph-runtime/terra-t07-evidence-dedup-conflict
HEAD ecc9dff1185f4d875d234b3ac5fc6ef9fcd25fb8
branch refs/heads/terra/t07-evidence-dedup-conflict

worktree C:/CharityGraph-runtime/terra-t07-industry-promotion
HEAD 05a28f42f127d6ff35ed1291ad21628410f8ba42
branch refs/heads/terra/t07-govern-industry-source-promotion-paths

worktree C:/CharityGraph-runtime/terra-t07-practice-campaign-provider
HEAD 9e1ab701c3a72ac153a7e8bd665c20738403062f
branch refs/heads/terra/t07-practice-campaign-provider-disambiguation

worktree C:/CharityGraph-runtime/terra-t08-migrate-legacy-fundraising-observation
HEAD cb1ca40a07c5f7183944d0bc1c165039415f4f95
branch refs/heads/terra/t08-migrate-legacy-fundraising-observation

worktree C:/CharityGraph-runtime/terra-t09-integrate-visible-fundraising-card-api
HEAD 9ebe417e6d2dd7f79acbe86f0546bdd763387301
branch refs/heads/terra/t09-integrate-visible-fundraising-card-api

worktree C:/CharityGraph-runtime/terra-t09-user-question-regression
HEAD d0a4f5d12c57fa82a0eca99601f41927eddc6c41
branch refs/heads/terra/t09-user-question-regression

worktree C:/CharityGraph-runtime/terra-t09-user-question-regression-clean
HEAD a0590c86abdc54110218805306be53db7db5a21d
branch refs/heads/terra/t09-user-question-regression-clean

worktree C:/CharityGraph-runtime/terra-t23-runtime-robustness
HEAD 0df408d9d0edc277644eba7f42cfa7c94e984735
branch refs/heads/cg-s0-t23-runtime-robustness-286

worktree C:/CharityGraph-runtime/terra-t24-failure-injection
HEAD bff6e099435d275ed0882780bf6a50a71ba3bbdc
branch refs/heads/cg-s0-t24-failure-injection-286

worktree C:/tmp/c10-normal/charitygraph
HEAD 49ae6d54910d8001ce08197dd95adf11b5d26f44
detached

worktree C:/tmp/cgc9-normal/charitygraph
HEAD 04da061f43e727ddee59235663909470fec77151
detached

worktree C:/tmp/charitygraph-brand-reuse-builder
HEAD 2b5a30041ce0123b34c2e2919c5cd12d9ba32c3a
branch refs/heads/charitygraph-brand-reuse-builder

worktree C:/tmp/charitygraph-native-lifecycle-harness
HEAD 0366c625c427470ff6917b2eb31381fea9913c9c
branch refs/heads/charitygraph-native-v5rr-overlay-lifecycle

worktree C:/tmp/charitygraph-native-v4-faceted-disposition
HEAD 12c5e7fa8841a0bd599e49b6d91d54758a845998
branch refs/heads/charitygraph-native-v4-faceted-disposition

worktree C:/tmp/charitygraph-native-v4r-faceted-disposition-repair
HEAD 9eb2f4210b4861f967f364495e57ee839113c6c3
branch refs/heads/charitygraph-native-v4r-faceted-disposition-repair

worktree C:/tmp/charitygraph-phase3-integrated-card-closeout
HEAD 4f53a8a83555a6d7c01faa5a44c16f2dfb8012ba
branch refs/heads/phase5-top100-factory-preflight-v1

worktree C:/tmp/charitygraph-phase3-relationship-role-proof
HEAD 72a3918b89235c98558e3123eed989256d59bf1c
branch refs/heads/charitygraph-phase3-relationship-role-proof

worktree C:/tmp/charitygraph-phase5-top100-baseline-corpus
HEAD 697c1130a0d3972abf77fea8c6ce4d439e697d15
branch refs/heads/phase5-real-provider-dry-run-v1

worktree C:/tmp/charitygraph-semantic-lab-docs
HEAD 3db9c9b61d2833a31042295e609eb0a4625faf84
branch refs/heads/charitygraph-native-induction-v1

worktree C:/tmp/charitygraph-v5
HEAD 875727141c076b943a6bc13846c56ad2a0f1ade9
branch refs/heads/charitygraph-native-v5-overlay-lifecycle

worktree C:/tmp/charitygraph-v5r
HEAD df5033ae982e2df185c94ab078826f22dec811d2
branch refs/heads/charitygraph-native-v5r-overlay-quality-lifecycle

worktree C:/tmp/charitygraph-v5rr
HEAD 2a7110554bee56829b294b2d423ac477e59d8780
branch refs/heads/charitygraph-native-v5rr-executable-lifecycle

worktree C:/Users/grego/AppData/Local/Temp/cgc1-suite/charitygraph
HEAD cf7d27a9de4474792edb72b5d8467f207db44e40
detached
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc1builder
HEAD cf7d27a9de4474792edb72b5d8467f207db44e40
branch refs/heads/phase5-tranche-c1-section7-reprojection
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc2-suite/charitygraph
HEAD 515f692feeef0e312ddb73ad05fb9796145627de
detached
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc2builder
HEAD 515f692feeef0e312ddb73ad05fb9796145627de
branch refs/heads/phase5-tranche-c2-section14-funding
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc3-suite/charitygraph
HEAD b3c1770ccbbe5a2f2a7ef3dd77d1ab9554c20d48
detached
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc3a-suite/charitygraph
HEAD 8605ffc14198a9ae9ddebee7bc41a398b1ee144e
detached
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc3builder
HEAD 8605ffc14198a9ae9ddebee7bc41a398b1ee144e
branch refs/heads/phase5-tranche-c3-sections3-6-11
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc4builder
HEAD c20396fdfed4ff481d7bce556bafa2f5ce616ecc
branch refs/heads/phase5-tranche-c4-section13-finance
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc5-normal/charitygraph
HEAD 526baec3fb555afacac449470b7be3cd6446caf2
detached
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc5builder
HEAD 526baec3fb555afacac449470b7be3cd6446caf2
branch refs/heads/phase5-tranche-c5-cross-cutting
prunable gitdir file points to non-existent location

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg345-builder
HEAD f52e4b894b05526eeb940f24f22c186289b356d8
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg385-builder
HEAD cef02cb80c26ea4c52cd3c4ea97b996023ba686c
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg385-builder/.cg386-builder
HEAD ccf8f32281c7dcd630df9ce880228562c0cdad5c
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.codex-v5rr-worktree
HEAD b63de6533a6cb50696fd4e9d64267ea953e5055b
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.northstar-gap-audit-286
HEAD 2fd804dd5b4ca3be48c12ab0a19813f043c83575
branch refs/heads/cg-s0-northstar-gap-audit-286

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/fundability-recert-builder-303
HEAD 7de942f4f60f1b82170ffa85d2c14e6cddbd6912
branch refs/heads/cg-fundability-recertification-303-builder

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/phase5-north-star-builder
HEAD f247c8c68ff6dcf4424df641eabe70a0cad6fd68
branch refs/heads/phase5-north-star-completion-v1

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/semantic-demand-builder-324
HEAD 7d4626e9f705b650687c864f47ec77d0b7b03b5e
branch refs/heads/cg-semantic-demand-corrections-324

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/semantic-demand-builder-325
HEAD e0119d581fa21f0148ef8b804611825678968e9e
branch refs/heads/cg-semantic-demand-corrections-326-terra

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/source-universe-builder
HEAD 88cee017ad3ec4073f68f219c71e6db634110e17
branch refs/heads/cg-source-universe-v1-publication

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-attempt10-prelaunch
HEAD 780285c3679a543a4eb15d4e9ee25baeb655fdf1
branch refs/heads/s0-attempt10-prelaunch

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-attempt9-locator-packet-repair
HEAD 537a365edec461b0da6afabfc82354eeb1deb3b1
branch refs/heads/s0-attempt9-locator-search-packet-repair

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-authorisation-builder
HEAD 8262f538ccd1ccfbf289532cd5001e61a3f26a0e
branch refs/heads/scale-s0-product-owner-authorisations

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-canon-builder
HEAD 4f1ed1724c8e4277bd4d9e5e251833d7d9707fe8
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-factory-merge-builder
HEAD 535d8701cad0236cfe0a679372f770dd092a9697
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-orchestration-runtime-v1
HEAD 815d64c189d5eb66a9d096a502a3a33cb7d832ed
branch refs/heads/s0-orchestration-runtime-v1

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-orchestration-runtime-v1/.s0-provider-boundary-a1
HEAD a5526fce88ef60e8d677b7504d1daeaa05c294e8
branch refs/heads/terra-s0-provider-boundary-a1

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-policy-builder
HEAD 22fa3cf5e8e6be2b7ed7e19ed3dff992009ed4b8
branch refs/heads/scale-s0-authorisation-package

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-reconcile-builder
HEAD 7cede8bddfbd5cc3c83169dfbcccbf83ed777a7c
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/bitemporal-governed-knowledge-v1
HEAD 1fd7ecc4d46ba5f4b71813019c143781e5fca123
branch refs/heads/bitemporal-governed-knowledge-v1

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/cg346-empirical-builder
HEAD ef2ce41703f3609521be6824413c09683b387157
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.campaign-builder
HEAD 49ae6d54910d8001ce08197dd95adf11b5d26f44
branch refs/heads/phase5-overnight-specialist-closure

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.s0-factory-builder
HEAD 68574a0b0dcc0985369ce933195a0678c235b555
branch refs/heads/scale-s0-factory-hardening

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.s0-owner-attestation-builder
HEAD c6d7c5dbccfbc3403b6074ef6a5f8ebe440c0590
branch refs/heads/cg-s0-owner-attestation-binding-repair-001

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.t06-fundraising-vocabulary
HEAD 18d89958913313b286e9460b63691433241de4fd
branch refs/heads/cg-fundraising-vocabulary-crosswalk-287

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.t06-fundraising-vocabulary/charitygraph/.t10-bounded-fundraising-cohort
HEAD e384a5efacf9f3e6fc5856b716f4f89ded5ef5ff
branch refs/heads/cg-t10-bounded-real-fundraising-cohort

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.t08-typed-money-scope-linkage
HEAD bda2a7cc48c10aad9eaab13d89d99794e6de3db0
branch refs/heads/terra/t08-typed-money-scope-linkage

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.t09-safe-derived-financial-metrics
HEAD 0aede0cd03176f77b86b7f644f21c085c3548550
branch refs/heads/terra/t09-safe-derived-financial-metrics

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph-t09-finance-extraction
HEAD 89bec488d5ee33697c5068e177102d142dd9d557
branch refs/heads/terra/t09-finance-extraction-normalisation

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/phase5-execution-packet
HEAD 3c8049293de8839a4cdc184bd8996382abc5dec1
branch refs/heads/phase5-direct-service-v1.2-cutover-v1

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/phase5-semantic-contract-registry
HEAD 9dd6f7b4517b17191f08d822a2d3bd131b270493
branch refs/heads/phase5-semantic-contract-registry-v1

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/s0-acquisition-packet-bridge-builder
HEAD 918de807eb557a48cb1d6448b20e1800529671e6
branch refs/heads/scale-s0-execution-identity-binding
```

### C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph-data

Remote: https://github.com/gregorycwhill/charitygraph-data.git

Branch: phase5-direct-service-v1.2-closeout

HEAD: cdd534e4e549bf2a6e78a4dbfc669d97ef07b50a

Local branches and tracking:
```
bitemporal-governed-knowledge-data-v1 6113ec85eeac4726cd2b68d606408c2051cae94b 
cg-ethos-notability-certification-344-data 93a2621e9e1feb492a2f2e00767e1e4a396962b6 
cg-ethos-notability-foundations-341-data 34ff489f5c0762faed77aecbbd796adab15f3f77 
cg-ethos-notability-reality-corpus-342-data 3ab8b6d405e0d98fba9ca223ce193b6d7f793b07 
cg-fundability-f0f1-data 516d64137dd1359b9497e6d7b5372b668ba275c6 
cg-fundability-f2-data 9874dc339c30d6b0a64d8ba6bc7ec047e8da5831 
cg-fundability-productisation-301-data 2be9feb81465e648babac5481ba705698d56ac43 
cg-fundability-recertification-303-data 0a02166450081e863b6e2028de0c8ce7e9c0898b 
cg-s0-attempt6-prelive-identity-invalid-record f722bf46b5f28edf4fd406c66f91c35218a58ba9 
cg-s0-doc-code-drift-286-terra-t15 cfb32b43d4d914d07688bf0d7bd8e9b5c7c2bae3 
cg-semantic-demand-catalogue-pilot fe3d1ff09c8d0112e2abeb3c4c5aa7399541cf74 
cg-semantic-demand-catalogue-pilot-completion 2ec8b9e90c1f7dffb7e37d06ca4da77e7b7eb8b6 [ahead 2, behind 7]
cg-semantic-demand-corrections-324 e6ed78c81d46a7668dc55d8880a7fb778a66e061 
cg-semantic-demand-corrections-325 3b42672d6714afbbba3f9ea718d3e74bd2a31ad5 
cg-semantic-demand-corrections-326-terra 0b15014e7363a31e82a1682f597b11d7ef2af831 
cg-semantic-demand-persona-final-curation-327 587ee2c23734f82e111de292971c01eddb08bf5a 
cg-source-universe-v1-publication f0c12c9fabfd62fc714cc32520b0320152a7fc21 [behind 6]
cg306-data-northstar-v03 2c0c865b3d6a1d065dab8fe02da23d445c8b7c44 
cg309-data-corrective cf118f425f2edf22e4683caae0db687be7cf641c 
cg316-data-reconciliation c9ad8f62d6ab8e68b4722124825c2bb200537cc7 [behind 8]
cg399-semantic-canonical fcdd01256eac54384b843fc65b714754950d7eda 
charitygraph-ai-discoverability-docs 2e41dcd7c8bb495c8358f7dd83103a2820a89762 
charitygraph-brand-reuse-data 2044e28efa90a0b0a1518d89a82773199f84ad63 
charitygraph-classification-layers-v1 02281f8b1c77d1ea82f8de983a0c9bbdb31035ac 
charitygraph-data-cutover-docs 00079d069f1ab92d31ebb9acab398d59c9a362d0 [behind 165]
charitygraph-donation-ranking-2024 ac256ee1aca5981b29578383f4eb6a7ca99f5600 
charitygraph-native-architecture-decisions bb113b48140f0ff55c2e9b8092b9437f846396b3 
charitygraph-native-overlay-architecture 56a59975b5756d0c0adb63bd8b4329704981698f 
charitygraph-north-star-roadmap-v21 f86143bfc4548d29082327ea7493474fa2262fee 
charitygraph-playbooks-product-docs 09a32cd6ed4ab681abd988a542213c4882b7ca80 
charitygraph-product-docs-v2 981f8a727a9bac08683ac20ff61f3c95d4fa622a 
charitygraph-product-docs-vnext 18d81c7f99cb53dbb143f03ad774d82694cbbd8d 
charitygraph-roadmap-phase3-alignment-20260831 4d826a12b7eca8dc3462d7e5069caa4aa4b660a1 
charitygraph-semantic-extraction-decisions-20260831 017597bad5983c33d3a6d717daaf1ce15e7655d1 
charitygraph-semantic-llm-gate bc64b3d11ae9a389ebb97be20e0157d1f92a95b3 
charitygraph-semantic-reliability-methodology 33dc7f9989d2bf681805eb8986e7cc475610fdfd 
charitygraph-task-1 9e9d28db781d70fd939372ce21d1faee7e820eb3 
charitygraph-taxonomy-plural-optional-classie 23002041bf8459882aa4b14972230823ee0b6548 
docs-builder-machinery-v1 d1c5974b893af8dfe260a7fb4d14bce10a659e6f [behind 16]
docs/prospective-repeatability-reliability-2026-08-28 45db7ddbe0fdf2ba15bb6997fe9dfb42ddc0b205 
main c537ae5660e5637f0bc0e795b3df0a6995cf1c06 [behind 113]
phase4-closeout-phase5-activation c537ae5660e5637f0bc0e795b3df0a6995cf1c06 
phase5-direct-service-v1.2-closeout cdd534e4e549bf2a6e78a4dbfc669d97ef07b50a [ahead 42]
phase5-north-star-completion-v1 2919f329eb054347a79081ef7b35a11ae8ebaf9a 
phase5-north-star-retained-evidence-review 29674d5d9f2b69d531a4b7cf9eabe329d219d639 
phase5-overnight-specialist-closure 349860de83364d2adf17750a090d9e34d69e6004 
phase5-product-value-canon-2026-09-15 112765fd0e2442ca1d6b1eecacd12553a6980348 
phase5-tranche-c1-section7-reprojection fb5c97c10d0a7333815f0ca959a542c294451706 
phase5-tranche-c2-section14-funding b08ae6918ab80ac4fdcdbf6c439043ca4a8aa700 
phase5-tranche-c3-sections3-6-11 baae4c2782e25f8ea5950b81e73fb5d33a900da5 
phase5-tranche-c4-section13-finance b9825c6a2f5533112cad4c000f6de1e9dfc807f9 
phase5-tranche-c5-cross-cutting 4b384bf9381308bae46a8fb09d178c78da142898 
reality-slice-1-acceptance-packet 0b92dde174d7037e44b61d005ac47497419f917c 
review-readiness-2026-09-11 533d76b04939415533c59db6efb69dd07f41e5b6 
s0-attempt18-authority-local f733bf2b85fef704528624008fc3faa38d957157 
s0-attempt20-final-authority-rebind-v1 baf5e01e4a5ddecdcdd672e33389041a51b24fb5 
s0-attempt21-successor-data 191f6140cfd65cc74e70f854e40918e76026cbee 
s0-attempt8-identity-reconciliation-v1 7ec3236b07229674017f078b9276505b903800cc 
s0-attempt9-option-a-terminal-history 8bbdf45450c6b0f7fcb0e02f28718517daf3b31d 
s0-identity-lineage-repair-data bc1f71ba0715d4a7e671faff5274a043a4ceef71 
s0-live-locator-activation-v1 01a7c6fe126cfc58d6bb42c765674d9f27e987ec 
s0-runtime-source-authority-repair-v1 05595755a88c88a4bc209a8c56a66c14d1b847e4 
s0-web-locator-discovery-repair 1668d2a54e5d3f7d06478ebfab7e1ecc5d1d8135 
scale-s0-acquisition-bridge-certification 788bc83718a1bee509a952b075a2f11fb19790d5 [behind 64]
scale-s0-authorisation 5f6b5ff7c9d796f4e5f21385091095cfd546bb3a 
scale-s0-execution e92a31fa4e8362eaa85782e12b45ac60cbce61b8 
scale-s0-execution-attempt-2 4eea9319ac06fe2db0ec52b94e058bd4e88893a7 
scale-s0-execution-identity-certification 81ad41752432366079736ffa815a9566fb7a9432 
scale-s0-factory-hardening e99c761622122fcbca5a21d90e7ee77cca964488 [ahead 2, behind 4]
scale-s0-policy-calibration 155ee65576231ae4ce94a15a29043f17ede8fa5b 
scale-s0-product-owner-authorisations 635068e97e78a26423fe3fa17f91594c7b19aa0b 
scale-s0-recovery-authorisation 4e408f3c33427d93fa816b907fc73ac738f07b10 
semantic-lab-knowledge-consolidation 959645cfb24ccf91164dd5875ae61fc576695096 
semantic-lab-v1d-findings 8b20684495ee0ad8f8ed007da52b0f08dcc271ba 
semantic-lab-v1e-decision-capture 8011a2c593cf13d7cc6423590d2b143e64c3c42c 
t04-practice-campaign-provider-data 74d35eab4219dc88069679ba2493a46d6bab5b62
```

Recent history:
```

```

Uncommitted inventory:
```
M AGENTS.md
 M DEVELOPMENT_METHOD.md
 M DOCUMENT_AUTHORITY.md
 M NORTH_STAR_TARGET_CARD_V0_3.md
 M SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md
?? .campaign-data/
?? .s0-factory-data/
?? BUILDER_TO_65K_PLAN.md
?? LEGACY_74_DEMAND_INVENTORY_CANDIDATE.json
?? SEMANTIC_DEMAND_CATALOGUE_CANDIDATE_G2.json
?? SEMANTIC_DEMAND_CATALOGUE_CANDIDATE_G2.md
?? SEMANTIC_DEMAND_CATALOGUE_REVIEW_DOSSIER_G2.md
?? docs/history/phase6-reality-slice-execution-2026-09-12.zip
```

Worktree inventory:
```
worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph-data
HEAD cdd534e4e549bf2a6e78a4dbfc669d97ef07b50a
branch refs/heads/phase5-direct-service-v1.2-closeout

worktree C:/CharityGraph-runtime/attempt18-authority-data
HEAD f733bf2b85fef704528624008fc3faa38d957157
branch refs/heads/s0-attempt18-authority-local

worktree C:/CharityGraph-runtime/attempt20-data-canonical
HEAD 18a0b74e87f7dd16403013ec92c8ae35c62c5410
detached

worktree C:/CharityGraph-runtime/attempt6-prelive-20260921-data-authority
HEAD f722bf46b5f28edf4fd406c66f91c35218a58ba9
branch refs/heads/cg-s0-attempt6-prelive-identity-invalid-record

worktree C:/CharityGraph-runtime/attempt8-data-canonical
HEAD 6cb3d2839331e1aece99ec3f3f5af2d5d8b1376d
detached

worktree C:/CharityGraph-runtime/cg-data-machinery-v1
HEAD d1c5974b893af8dfe260a7fb4d14bce10a659e6f
branch refs/heads/docs-builder-machinery-v1

worktree C:/CharityGraph-runtime/cg-ethos-notability-certification-344-data
HEAD 93a2621e9e1feb492a2f2e00767e1e4a396962b6
branch refs/heads/cg-ethos-notability-certification-344-data

worktree C:/CharityGraph-runtime/cg-ethos-notability-foundations-data-341
HEAD 3ab8b6d405e0d98fba9ca223ce193b6d7f793b07
branch refs/heads/cg-ethos-notability-reality-corpus-342-data

worktree C:/CharityGraph-runtime/cg-fundability-data
HEAD 9874dc339c30d6b0a64d8ba6bc7ec047e8da5831
branch refs/heads/cg-fundability-f2-data

worktree C:/CharityGraph-runtime/cg-fundability-product-data
HEAD 2be9feb81465e648babac5481ba705698d56ac43
branch refs/heads/cg-fundability-productisation-301-data

worktree C:/CharityGraph-runtime/cg-s0-cleanroom-286-data
HEAD 191f6140cfd65cc74e70f854e40918e76026cbee
detached

worktree C:/CharityGraph-runtime/cg-s0-data-validation-286
HEAD 1513648ec358645c23ff49a34769ae91365bf47e
detached

worktree C:/CharityGraph-runtime/cg-semantic-demand-persona-final-curation-327
HEAD 587ee2c23734f82e111de292971c01eddb08bf5a
branch refs/heads/cg-semantic-demand-persona-final-curation-327

worktree C:/CharityGraph-runtime/cg306/data
HEAD 2c0c865b3d6a1d065dab8fe02da23d445c8b7c44
branch refs/heads/cg306-data-northstar-v03

worktree C:/CharityGraph-runtime/cg348-pilot-data
HEAD 93a2621e9e1feb492a2f2e00767e1e4a396962b6
detached

worktree C:/CharityGraph-runtime/cg399-legacy-demand-reconciliation-luna
HEAD 0f506c38de396bc7a22c610d420e68fe514d4b5c
detached

worktree C:/CharityGraph-runtime/cg399-legacy-demand-recovery-data
HEAD b082d30784494b7d8570edbd5e05da36e040d2c4
detached

worktree C:/CharityGraph-runtime/cg401c-data
HEAD 443d195abea91d7da111f5e573e90247ae823c36
detached

worktree C:/CharityGraph-runtime/cg401f-data
HEAD 443d195abea91d7da111f5e573e90247ae823c36
detached

worktree C:/CharityGraph-runtime/cg403-data
HEAD 443d195abea91d7da111f5e573e90247ae823c36
detached

worktree C:/CharityGraph-runtime/data-corrective
HEAD cf118f425f2edf22e4683caae0db687be7cf641c
branch refs/heads/cg309-data-corrective

worktree C:/CharityGraph-runtime/s0-attempt20-final-authority-rebind-v1
HEAD baf5e01e4a5ddecdcdd672e33389041a51b24fb5
branch refs/heads/s0-attempt20-final-authority-rebind-v1

worktree C:/CharityGraph-runtime/s0-attempt20-final-rebind-data
HEAD b991e6180e47c6b3c4c683b7ab2b830df43ea10a
detached

worktree C:/CharityGraph-runtime/s0-attempt21-successor-data
HEAD cfb32b43d4d914d07688bf0d7bd8e9b5c7c2bae3
branch refs/heads/cg-s0-doc-code-drift-286-terra-t15

worktree C:/CharityGraph-runtime/s0-attempt3-preparation-data
HEAD e4b938b4825ec859f8134abd030ed4be8eec675c
detached

worktree C:/CharityGraph-runtime/s0-attempt4-preparation/data
HEAD e4b938b4825ec859f8134abd030ed4be8eec675c
detached

worktree C:/CharityGraph-runtime/s0-attempt7-data
HEAD 70e273fa3bdf25188ea4e4ef4959a8def7500bf4
detached

worktree C:/CharityGraph-runtime/s0-attempt8-identity-reconciliation-v1
HEAD 7ec3236b07229674017f078b9276505b903800cc
branch refs/heads/s0-attempt8-identity-reconciliation-v1

worktree C:/CharityGraph-runtime/s0-identity-lineage-data
HEAD bc1f71ba0715d4a7e671faff5274a043a4ceef71
branch refs/heads/s0-identity-lineage-repair-data

worktree C:/CharityGraph-runtime/s0-live-locator-activation-v1-data
HEAD 01a7c6fe126cfc58d6bb42c765674d9f27e987ec
branch refs/heads/s0-live-locator-activation-v1

worktree C:/CharityGraph-runtime/s0-postmerge-data
HEAD 0f73f399b0d5feeff75b0716fc31da07866b6d14
detached

worktree C:/CharityGraph-runtime/s0-poststabilisation-data
HEAD f4da30d0410e107351f215ea573abdcce264e6f2
detached

worktree C:/CharityGraph-runtime/s0-runtime-source-authority-repair-v1-data
HEAD 05595755a88c88a4bc209a8c56a66c14d1b847e4
branch refs/heads/s0-runtime-source-authority-repair-v1

worktree C:/CharityGraph-runtime/s0-web-locator-data
HEAD 1668d2a54e5d3f7d06478ebfab7e1ecc5d1d8135
branch refs/heads/s0-web-locator-discovery-repair

worktree C:/CharityGraph-runtime/semantic-demand-catalogue-completion
HEAD 2ec8b9e90c1f7dffb7e37d06ca4da77e7b7eb8b6
branch refs/heads/cg-semantic-demand-catalogue-pilot-completion

worktree C:/CharityGraph-runtime/semantic-demand-catalogue-pilot
HEAD fe3d1ff09c8d0112e2abeb3c4c5aa7399541cf74
branch refs/heads/cg-semantic-demand-catalogue-pilot

worktree C:/CharityGraph-runtime/t04-practice-campaign-provider-data
HEAD 74d35eab4219dc88069679ba2493a46d6bab5b62
branch refs/heads/t04-practice-campaign-provider-data

worktree C:/tmp/c10-normal/charitygraph-data
HEAD 0b1e717c73db7f6162eba9fb3a04ef6091746239
detached

worktree C:/tmp/cgc9-normal/charitygraph-data
HEAD 294ef7ba1ada14125f2fb815afd2c8d153cf4471
detached

worktree C:/tmp/charitygraph-brand-reuse-data
HEAD 2044e28efa90a0b0a1518d89a82773199f84ad63
branch refs/heads/charitygraph-brand-reuse-data

worktree C:/Users/grego/AppData/Local/Temp/cg5b
HEAD 29674d5d9f2b69d531a4b7cf9eabe329d219d639
branch refs/heads/phase5-north-star-retained-evidence-review
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc1-suite/charitygraph-data
HEAD fb5c97c10d0a7333815f0ca959a542c294451706
detached
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc1data
HEAD fb5c97c10d0a7333815f0ca959a542c294451706
branch refs/heads/phase5-tranche-c1-section7-reprojection
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc2-suite/charitygraph-data
HEAD b08ae6918ab80ac4fdcdbf6c439043ca4a8aa700
detached
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc2data
HEAD b08ae6918ab80ac4fdcdbf6c439043ca4a8aa700
branch refs/heads/phase5-tranche-c2-section14-funding
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc3-suite/charitygraph-data
HEAD 52c2df176ebb4bc3f4c1d3c232789571fcf8845f
detached
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc3a-suite/charitygraph-data
HEAD baae4c2782e25f8ea5950b81e73fb5d33a900da5
detached
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc3data
HEAD baae4c2782e25f8ea5950b81e73fb5d33a900da5
branch refs/heads/phase5-tranche-c3-sections3-6-11
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc4data
HEAD b9825c6a2f5533112cad4c000f6de1e9dfc807f9
branch refs/heads/phase5-tranche-c4-section13-finance
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc5-normal/charitygraph-data
HEAD 059c5682a79e112b150bcaaed40bca211a5f0051
detached
prunable gitdir file points to non-existent location

worktree C:/Users/grego/AppData/Local/Temp/cgc5data
HEAD 4b384bf9381308bae46a8fb09d178c78da142898
branch refs/heads/phase5-tranche-c5-cross-cutting
prunable gitdir file points to non-existent location

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg316-data-reconciliation
HEAD c9ad8f62d6ab8e68b4722124825c2bb200537cc7
branch refs/heads/cg316-data-reconciliation

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg345-data
HEAD 93a2621e9e1feb492a2f2e00767e1e4a396962b6
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg398-data-clean
HEAD 4e86109167693427ac96afe6a45a491230f4a954
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/cg399-semantic
HEAD fcdd01256eac54384b843fc65b714754950d7eda
branch refs/heads/cg399-semantic-canonical

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/charitygraph-data
HEAD 112765fd0e2442ca1d6b1eecacd12553a6980348
branch refs/heads/phase5-product-value-canon-2026-09-15

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/fundability-recert-data-303
HEAD 0a02166450081e863b6e2028de0c8ce7e9c0898b
branch refs/heads/cg-fundability-recertification-303-data

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/phase5-north-star-data
HEAD 2919f329eb054347a79081ef7b35a11ae8ebaf9a
branch refs/heads/phase5-north-star-completion-v1

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/semantic-demand-data-324
HEAD e6ed78c81d46a7668dc55d8880a7fb778a66e061
branch refs/heads/cg-semantic-demand-corrections-324

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/semantic-demand-data-325
HEAD 0b15014e7363a31e82a1682f597b11d7ef2af831
branch refs/heads/cg-semantic-demand-corrections-326-terra

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/source-universe-data
HEAD f0c12c9fabfd62fc714cc32520b0320152a7fc21
branch refs/heads/cg-source-universe-v1-publication

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-authorisation-data
HEAD 635068e97e78a26423fe3fa17f91594c7b19aa0b
branch refs/heads/scale-s0-product-owner-authorisations

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-canon-data
HEAD 5240337fb8ea3e44dc34ff394f466245689a2075
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-execution-data
HEAD e92a31fa4e8362eaa85782e12b45ac60cbce61b8
branch refs/heads/scale-s0-execution

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-factory-merge-data
HEAD 524d98dabf9c8f8c5d05b2d108331f895512d880
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-policy-data
HEAD 155ee65576231ae4ce94a15a29043f17ede8fa5b
branch refs/heads/scale-s0-policy-calibration

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-reconcile-data
HEAD 7148f4cfae4b12d8dbce5a435bd4038a24c50844
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/bitemporal-governed-knowledge-data-v1
HEAD 6113ec85eeac4726cd2b68d606408c2051cae94b
branch refs/heads/bitemporal-governed-knowledge-data-v1

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/cg346-empirical-data
HEAD 91d3c13a4e5d165ea78f21a3a828de6fb8eacdd5
detached

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph-data/.campaign-data
HEAD 349860de83364d2adf17750a090d9e34d69e6004
branch refs/heads/phase5-overnight-specialist-closure

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph-data/.s0-factory-data
HEAD e99c761622122fcbca5a21d90e7ee77cca964488
branch refs/heads/scale-s0-factory-hardening

worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/s0-acquisition-bridge-certification-data
HEAD 81ad41752432366079736ffa815a9566fb7a9432
branch refs/heads/scale-s0-execution-identity-certification
```

### C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph-viewer

Remote: https://github.com/gregorycwhill/charitygraph-viewer.git

Branch: review-readiness-2026-09-11

HEAD: b66168074c2111363020463749ac283f9024bbd7

Local branches and tracking:
```
charitygraph-brand-reuse-viewer 4502871e3764852f0587e7b9965409f6b6b341ae 
charitygraph-branding-followup 5f15be61296c1ece3730004e2693617b8b683f0d 
charitygraph-playbooks-cross-repo-links 71a38c82f5dd3162cf5026ef094674c88da4c534 
charitygraph-task-1 300db0dfe5947f49e91664dac9d63c65430350b8 
charitygraph-viewer-docs-brand-cleanup 462a145b25427318a589de34de482f607df18fa7 
charitygraph-viewer-pages-fix 863870b27225139b187b2465ed9f6eeb593782a6 
gh-pages f942049626e0c390ba658acf76a607a72643b3d9 [behind 20]
main bd169f612fbc86bb6bfa140d48672485fced20be 
review-readiness-2026-09-11 b66168074c2111363020463749ac283f9024bbd7
```

Recent history:
```

```

Uncommitted inventory:
```
?? debug.log
```

Worktree inventory:
```
worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph-viewer
HEAD b66168074c2111363020463749ac283f9024bbd7
branch refs/heads/review-readiness-2026-09-11

worktree C:/tmp/charitygraph-brand-reuse-viewer
HEAD 4502871e3764852f0587e7b9965409f6b6b341ae
branch refs/heads/charitygraph-brand-reuse-viewer
```

### C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph-playbooks

Remote: https://github.com/gregorycwhill/charitygraph-playbooks.git

Branch: review-readiness-2026-09-11

HEAD: f0cd9fe76b9fd402ec53b82210e148feeb984af6

Local branches and tracking:
```
charitygraph-playbooks-publication-links 4d7f94519d4c6fac61f39e5352fc8afd9b4b495e 
main dbd7e0816e2560666dede01986cab4e6d59bb929 
review-readiness-2026-09-11 f0cd9fe76b9fd402ec53b82210e148feeb984af6
```

Recent history:
```

```

Uncommitted inventory:
```

```

Worktree inventory:
```
worktree C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph-playbooks
HEAD f0cd9fe76b9fd402ec53b82210e148feeb984af6
branch refs/heads/review-readiness-2026-09-11
```
## Decommission verification limits
Main preservation commit ffe28120f4b5ce0423042209e4681bce73b2706d was verified on origin/gate3-cg406-remediation. Both clean-root repositories pushed all local branches. Historical OneDrive branch pushes encountered non-fast-forward rejections; archival refs under decommission-20261103 preserve the older histories without overwriting origin. Full cleanup remains incomplete: main checkout still has 29 untracked evidence/temp entries, additional OneDrive changes and historical worktrees need capture, and one pytest directory reports permission denied. No fresh test result or complete all-checkout clean status is certified. No files were deleted to manufacture a clean status.

