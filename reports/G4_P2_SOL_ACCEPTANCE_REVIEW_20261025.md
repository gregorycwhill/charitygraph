# CG-G4-P2 independent supervisory product acceptance

- Review instruction: `20261025-g4-p2-sol-acceptance-review-v1`
- Mode: READ-ONLY REPORT_ONLY
- Scope: P2 bounded provider-free scope-isolation slice
- Review date: 2026-10-25 (Australia/Sydney)
- Result: **FAIL — global control stop; functional acceptance was not established.**

## Stop condition

The supplied control instruction says a genuine fence, HEAD, authority, changed-path or workspace mismatch is a global STOP. The active fence, branch, full HEAD and tree were independently checked. The workspace catalogue count was not consistent with the supplied control assertion:

- Exact `git status --porcelain=v1 -uall` count before this report: **261** records.
- Supplied control assertion: the latest supervisor workspace catalogue records **341** pre-existing dirty/untracked paths.
- The exact current status therefore does not reproduce the asserted 341-path catalogue. No attempt was made to reconcile, clean, restore, stage, overwrite, or otherwise mutate the discrepancy.

This is the only acceptance conclusion in this report. It is not a claim that the P2 code is defective; the requested acceptance work was stopped before product inspection.

## Fence, authority, branch and workspace evidence

Fence path checked read-only:

`C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\cg-g4-o1b-dormant-state-fence-20261020-v23.json`

- Fence SHA-256: `8d58d6acccaa5933075a1492e0974fc6a1080868d78b3e58532a351b5cb5c342` (matches supplied hash).
- Fence state: `ACTIVE`; fence version: `23`.
- Fence implementation revision/head: `21bb0e621f2a1c52f19b59f261d71009defa4843`.
- Fence workspace: `C:\CharityGraph-clean\charitygraph`.
- Fence branch: `gate3-cg406-remediation`.
- Fence activation records provider calls `0`, GitHub mutation `false`, publication `false`, gate closure `false`.
- Observed branch: `gate3-cg406-remediation`.
- Observed `HEAD`: `21bb0e621f2a1c52f19b59f261d71009defa4843`.
- Observed `HEAD^{tree}` (quoted verification): `f5851e02afab398326e145a34d142d9de5fe1a58` (matches supplied tree).
- Required report was absent before the review.
- Filtered process observation found no process name matching `charity`, `watch`, or `agent`; one `BridgeCommunication` process (PID 16556) was present. No watcher or competing worker was started, stopped, or controlled.

## Review actions deliberately not performed

Because of the stop condition, the following were not inspected or executed:

- P2 unified diff, diffstat, product hunks, current source/tests, architecture/governance documents, or prior reports.
- Requested SHA-256 verification of the three P2 code/test paths. Supplied expected hashes remain unverified: factory `dc7f335873789c31f016351c9dccd20f04f7ed002689d0e6dd36b981ab100dfe`; factory tests `ef7498153ef1d13b55bfd052c6c6f5aac3e88e85ccc6aeba62b4ba8cca0d1828`; governed integration tests `2912b5813743b8da6f8bced353559f4209896c8f3339952e5b2d866943f192e0`.
- Governed preflight → FactoryPlan → ReferenceFactory → SQLiteCatalog flow review, including physical-attempt scope consequences.
- Coverage/identity/retry/restart/idempotence/accounting assertion review.
- Provider-free pytest execution. No basetemp was created.
- `git diff --check) or any post-test diagnostic.

Accordingly, there are no test exit codes, pass/fail counts, duration, trace, diffstat, or product-acceptance evidence to report. This review makes no claim about paid providers, semantic model results, canonical coverage, rights-policy authority, publication, bridge completion, or Gate 4 closure.

## Pre-review exact workspace status

The following is the exact status-record output used for the stop decision (warnings from Git about inaccessible temporary paths were emitted separately by Git and are not status records):

```text
 M docs/G4_O1B_SUPERVISORY_SUBMISSION.md
 M docs/G4_O1C_SUPERVISORY_SUBMISSION.md
 M src/charitygraph/phase5_factory.py
 M tests/test_phase5_factory.py
 M tests/test_phase5_governed_factory_integration.py
?? evidence/cg406-proposition-relevance-remediation/artifact-inventory.json
?? evidence/cg406-proposition-relevance-remediation/before-after-evidence-family-matrix.md
?? evidence/cg406-proposition-relevance-remediation/handoff.json
?? evidence/cg406-proposition-relevance-remediation/prepared-request-identity-manifest.json
?? evidence/cg406-proposition-relevance-remediation/summary.md
?? evidence/cg406-proposition-relevance-remediation/test-results.md
?? evidence/cg406-proposition-relevance-remediation/validation-results.json
?? evidence/cg406-provider-development-replay/accounting-token-spend-ledger.md
?? evidence/cg406-provider-development-replay/artifact-sha256-inventory.json
?? evidence/cg406-provider-development-replay/frozen-development-result-manifest.json
?? evidence/cg406-provider-development-replay/handoff.json
?? evidence/cg406-provider-development-replay/per-row-old-new-mechanical-comparison.json
?? evidence/cg406-provider-development-replay/prepared-run-identity.json
?? evidence/cg406-provider-development-replay/provider-visible-corpus-summary.md
?? evidence/cg406-provider-development-replay/summary.md
?? evidence/cg406-provider-development-replay/terminal-result-ledger.json
?? evidence/cg406-provider-development-replay/validation-results.json
?? evidence/cg406-provider-development-replay/validation-results.md
?? evidence/cg406-public-source-transmission-policy/artifact-inventory.md
?? evidence/cg406-public-source-transmission-policy/before-after-classification.md
?? evidence/cg406-public-source-transmission-policy/handoff.json
?? evidence/cg406-public-source-transmission-policy/prepared-request-manifest.json
?? evidence/cg406-public-source-transmission-policy/provider-visible-corpus-summary.md
?? evidence/cg406-public-source-transmission-policy/summary.md
?? evidence/cg406-public-source-transmission-policy/validation-and-test-results.md
?? evidence/cg406-rights-catalog-resolution/classification-rules.md
?? evidence/cg406-rights-catalog-resolution/handoff.json
?? evidence/cg406-rights-catalog-resolution/inventory.json
?? evidence/cg406-rights-catalog-resolution/prepared-request-identity.md
?? evidence/cg406-rights-catalog-resolution/product-owner-decision.md
?? evidence/cg406-rights-catalog-resolution/summary.md
?? evidence/cg406-rights-catalog-resolution/test-results.md
?? evidence/cg406-v12-development-replay/accounting-reconciliation.json
?? evidence/cg406-v12-development-replay/artifact-inventory.json
?? evidence/cg406-v12-development-replay/frozen-result-manifest.json
?? evidence/cg406-v12-development-replay/handoff.json
?? evidence/cg406-v12-development-replay/mechanical-old-new-comparison.json
?? evidence/cg406-v12-development-replay/per-row-proposition-scope-assessment.json
?? evidence/cg406-v12-development-replay/post-run-tests.json
?? evidence/cg406-v12-development-replay/prepared-run-identity.json
?? evidence/cg406-v12-development-replay/provider-visible-family-coverage.json
?? evidence/cg406-v12-development-replay/resume-verification.json
?? evidence/cg406-v12-development-replay/summary.md
?? evidence/cg406-v12-development-replay/terminal-result-ledger.json
?? evidence/cg406-v12-development-replay/validation-results.json
?? evidence/cg406-v12-inference-integrity/artifact-inventory.json
?? evidence/cg406-v12-inference-integrity/forensic-diagnosis.json
?? evidence/cg406-v12-inference-integrity/handoff.json
?? evidence/cg406-v12-inference-integrity/preparation-summary.json
?? evidence/cg406-v12-inference-integrity/source-relevance-matrix.json
?? evidence/cg406-v12-inference-integrity/summary.md
?? evidence/cg406-v12-inference-integrity/test-results.json
?? evidence/cg406-v12-inference-integrity/typed-demand-contract.json
?? evidence/cg406-v13-development-replay/accounting-reconciliation.json
?? evidence/cg406-v13-development-replay/artifact-inventory.json
?? evidence/cg406-v13-development-replay/evidence-source-relevance-details.json
?? evidence/cg406-v13-development-replay/execution-control-investigation.json
?? evidence/cg406-v13-development-replay/frozen-result-manifest.json
?? evidence/cg406-v13-development-replay/handoff.json
?? evidence/cg406-v13-development-replay/mechanical-v12-v13-comparison.json
?? evidence/cg406-v13-development-replay/prepared-execution-reconciliation.json
?? evidence/cg406-v13-development-replay/resume-verification.json
?? evidence/cg406-v13-development-replay/summary.md
?? evidence/cg406-v13-development-replay/terminal-result-ledger.json
?? evidence/cg406-v13-development-replay/test-results.json
?? evidence/cg406-v13-development-replay/validation-results.json
?? evidence/cg406-v14-final-development-replay/accounting-reconciliation.json
?? evidence/cg406-v14-final-development-replay/artifact-inventory.json
?? evidence/cg406-v14-final-development-replay/build_inventory.py
?? evidence/cg406-v14-final-development-replay/compile_v14_handoff.py
?? evidence/cg406-v14-final-development-replay/execution-authorization-record.txt
?? evidence/cg406-v14-final-development-replay/execution-control.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_05548f0ccf7149e6de515c588d0e0fc9660b8e3a29c84818a5c6c15f4895a678.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_0c8670382dd4e601bfae3df3499433ae572c1bd9e691b92b24a7262715df5574.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_2351ed3c9bcbfb14e0c71dcf29d09f035fcbffc1b4fa3728119ea64a5ad4a9de.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_29c9ea5b8d8494a24ec9f53af0939c7c6067400a45e0fa7ff3a5d43bbef077aa.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_35e5b2fc771d8b1c99ae2f6a44a82687079c409bee7fc745dd47b250854cb1de.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_60b971d6426bc384dc834b0e195e74c612a92eca5da94917f41c27504f288f30.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_622dd70fc49e331b0f4d3bfa118473dce96b5d0452cd318b447d5ad02f25e207.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_681c2dac224e4f58586ecb4b766346ef426a3da5edbfb93acd88958aadd62f67.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_8111f774ba82ba935ec0b95d25e6ebaa4a678e58e2642168fb74b63713a5571b.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_ab0adb34716c60bb9423e44b8b3191ab0cf9675536a9554fe0a38e957d828e57.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_e8c236a6e42905ecc32f0787a809319b425df2d970d0bac785954f8cd9504c47.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_ee6509de8f51dd822038923084dbff8efd896bd8537c21afd7926e70eff2e549.json
?? evidence/cg406-v14-final-development-replay/freeze_v14_terminal_results.py
?? evidence/cg406-v14-final-development-replay/frozen-result-manifest.json
?? evidence/cg406-v14-final-development-replay/mechanical-v13-v14-comparison.json
?? evidence/cg406-v14-final-development-replay/postfreeze-analysis.json
?? evidence/cg406-v14-final-development-replay/prepared-run-identity.json
?? evidence/cg406-v14-final-development-replay/resume-verification.json
?? evidence/cg406-v14-final-development-replay/sol-handoff.json
?? evidence/cg406-v14-final-development-replay/summary.md
?? evidence/cg406-v14-final-development-replay/targeted-diagnostics.md
?? evidence/cg406-v14-final-development-replay/terminal-result-ledger.json
?? evidence/cg406-v14-final-development-replay/test-results.json
?? evidence/cg406-v14-final-development-replay/validate_v14_terminal_results.py
?? evidence/cg406-v14-final-development-replay/validation-results.json
?? evidence/cg406-v14-final-development-replay/verify_v14_packet.py
?? evidence/gate3-cg405-identity-reconciliation-review/artifact-inventory.json
?? evidence/gate3-cg405-identity-reconciliation-review/bounded-freshness-methodology.md
?? evidence/gate3-cg405-identity-reconciliation-review/exposure-eligibility-audit.json
?? evidence/gate3-cg405-identity-reconciliation-review/five-match-architecture-audit.json
?? evidence/gate3-cg405-identity-reconciliation-review/question-designer-handoff-inventory.json
?? evidence/gate3-cg405-identity-reconciliation-review/successor-eligible-subject-universe.json
?? evidence/gate3-cg405-identity-reconciliation-review/successor-excluded-subjects.json
?? evidence/gate3-cg405-identity-reconciliation-review/successor-subject-universe-manifest.json
?? evidence/gate3-cg405-identity-reconciliation-review/verification-results.json
?? evidence/gate3-cg405-identity-reconciliation/artifact-inventory.json
?? evidence/gate3-cg405-identity-reconciliation/cg405-identity-crosswalk.json
?? evidence/gate3-cg405-identity-reconciliation/historical-identity-lineage-analysis.md
?? evidence/gate3-cg405-identity-reconciliation/updated-exposure-ledger.json
?? evidence/gate3-cg405-identity-reconciliation/verification-results.json
?? evidence/gate3-final-semantic-review/artifact-inventory.json
?? evidence/gate3-final-semantic-review/case-assessments.json
?? evidence/gate3-final-semantic-review/identity-verification.json
?? evidence/gate3-final-semantic-review/scoring-methodology.md
?? evidence/gate3-final-semantic-review/summary.md
?? evidence/gate3-fresh-36-builder-preparation/artifact-inventory.json
?? evidence/gate3-fresh-36-builder-preparation/corpus-identity-manifest.json
?? evidence/gate3-fresh-36-builder-preparation/frozen-input-verification.json
?? evidence/gate3-fresh-36-builder-preparation/handoff.json
?? evidence/gate3-fresh-36-builder-preparation/preparation-contract-validation.json
?? evidence/gate3-fresh-36-builder-preparation/prepared-request-status.json
?? evidence/gate3-fresh-36-builder-preparation/provider-corpus-admission-ledger.json
?? evidence/gate3-fresh-36-builder-preparation/provider-free-guard.json
?? evidence/gate3-fresh-36-builder-preparation/source-acquisition-ledger.json
?? evidence/gate3-fresh-36-builder-preparation/source-acquisition-summary.json
?? evidence/gate3-fresh-36-builder-preparation/source-coverage-matrix.json
?? evidence/gate3-fresh-36-builder-preparation/source-gap-register.json
?? evidence/gate3-fresh-36-builder-preparation/summary.md
?? evidence/gate3-fresh-36-builder-preparation/test-results.json
?? evidence/gate3-fresh-36-executable-demand-specification/artifact-inventory.json
?? evidence/gate3-fresh-36-executable-demand-specification/candidate-executable-demand-specifications.json
?? evidence/gate3-fresh-36-executable-demand-specification/contract-gap-matrix.json
?? evidence/gate3-fresh-36-executable-demand-specification/deterministic-instantiation-procedure.json
?? evidence/gate3-fresh-36-executable-demand-specification/evidence-corpus-continuity.json
?? evidence/gate3-fresh-36-executable-demand-specification/handoff.json
?? evidence/gate3-fresh-36-executable-demand-specification/oracle-compatibility-analysis.json
?? evidence/gate3-fresh-36-executable-demand-specification/proposed-executable-demand-specification-schema.json
?? evidence/gate3-fresh-36-executable-demand-specification/required-semantic-decisions.json
?? evidence/gate3-fresh-36-executable-demand-specification/summary.md
?? evidence/gate3-fresh-36-executable-demand-specification/test-results.json
?? evidence/gate3-fresh-semantic-holdout-preparation/artifact-inventory.json
?? evidence/gate3-fresh-semantic-holdout-preparation/baseline.json
?? evidence/gate3-fresh-semantic-holdout-preparation/build_holdout_packet.py
?? evidence/gate3-fresh-semantic-holdout-preparation/content-artifact-inventory.json
?? evidence/gate3-fresh-semantic-holdout-preparation/demand-definition-vocabulary.json
?? evidence/gate3-fresh-semantic-holdout-preparation/domain-distribution.json
?? evidence/gate3-fresh-semantic-holdout-preparation/eligibility-audit.json
?? evidence/gate3-fresh-semantic-holdout-preparation/excluded-case-inventory.json
?? evidence/gate3-fresh-semantic-holdout-preparation/frozen-selected-holdout-manifest.json
?? evidence/gate3-fresh-semantic-holdout-preparation/handoff.json
?? evidence/gate3-fresh-semantic-holdout-preparation/independence-and-blindness-audit.json
?? evidence/gate3-fresh-semantic-holdout-preparation/indicative-provider-budget.json
?? evidence/gate3-fresh-semantic-holdout-preparation/later-execution-and-blindness-protocol.md
?? evidence/gate3-fresh-semantic-holdout-preparation/packet-structural-test-results.json
?? evidence/gate3-fresh-semantic-holdout-preparation/preregistered-scoring-rubric.md
?? evidence/gate3-fresh-semantic-holdout-preparation/repository-test-results.json
?? evidence/gate3-fresh-semantic-holdout-preparation/sealed-oracle-construction-instructions.md
?? evidence/gate3-fresh-semantic-holdout-preparation/selection-algorithm.json
?? evidence/gate3-fresh-semantic-holdout-preparation/summary.md
?? evidence/gate3-fresh-semantic-holdout-preparation/verify_holdout_packet.py
?? evidence/gate3-fresh36-bounded-recovery-v1/artifact-inventory.json
?? evidence/gate3-fresh36-bounded-recovery-v1/inventory-sha256.txt
?? evidence/gate3-fresh36-bounded-recovery-v1/recovery-status.json
?? evidence/gate3-fresh36-bounded-recovery-v1/source-lineage-recovery.json
?? evidence/gate3-fresh36-bounded-recovery-v1/successor-acquisition.json
?? evidence/gate3-fresh36-bounded-recovery-v1/summary.md
?? evidence/gate3-fresh36-semantic-execution-v1/artifact-sha256-inventory.json
?? evidence/gate3-fresh36-semantic-execution-v1/attempt-ledger.json
?? evidence/gate3-fresh36-semantic-execution-v1/execution-manifest.json
?? evidence/gate3-fresh36-semantic-execution-v1/experiment-configuration.json
?? evidence/gate3-fresh36-semantic-execution-v1/failures-and-missingness.json
?? evidence/gate3-fresh36-semantic-execution-v1/inventory-sha256.txt
?? evidence/gate3-fresh36-semantic-execution-v1/raw-responses.jsonl
?? evidence/gate3-fresh36-semantic-execution-v1/record_blocked_attempts.py
?? evidence/gate3-fresh36-semantic-execution-v1/request-compilation-status.json
?? evidence/gate3-fresh36-semantic-execution-v1/rights-binding-ledger.json
?? evidence/gate3-fresh36-semantic-execution-v1/trusted-authorization-status.json
?? evidence/gate3-fresh36-semantic-execution-v1/validation-results.json
?? evidence/gate3-fresh36-semantic-execution-v1/verified-frozen-inputs.json
?? evidence/gate3-fresh36-semantic-execution-v2/artifact-inventory.json
?? evidence/gate3-fresh36-semantic-execution-v2/governance/product-owner-government-data-transmission-decision.json
?? evidence/gate3-fresh36-semantic-execution-v2/status-and-blocker.md
?? evidence/gate3-generic-discovery-contract-v15/17-gap-root-cause-resolution-matrix.json
?? evidence/gate3-generic-discovery-contract-v15/36-template-compatibility-matrix.json
?? evidence/gate3-generic-discovery-contract-v15/artifact-inventory.json
?? evidence/gate3-generic-discovery-contract-v15/identity-and-source-governance-verification.json
?? evidence/gate3-generic-discovery-contract-v15/implementation-changes.md
?? evidence/gate3-generic-discovery-contract-v15/missing-semantics-treatment.json
?? evidence/gate3-generic-discovery-contract-v15/provider-free-test-results.json
?? evidence/gate3-generic-discovery-contract-v15/synthetic-execution-results.json
?? evidence/gate3-generic-discovery-contract-v15/v14-regression-verification.json
?? evidence/gate3-generic-discovery-contract-v15/v15-contract-schema.json
?? evidence/gate3-generic-discovery-contract-v15/verified-input-package-provenance.json
?? evidence/gate3-generic-discovery-contract/17-gap-root-cause-analysis.md
?? evidence/gate3-generic-discovery-contract/architecture-compliance-verification.json
?? evidence/gate3-generic-discovery-contract/artifact-inventory.json
?? evidence/gate3-generic-discovery-contract/fixture-isolation-verification.json
?? evidence/gate3-generic-discovery-contract/generic-discovery-contract-status.md
?? evidence/gate3-generic-discovery-contract/handoff.json
?? evidence/gate3-generic-discovery-contract/per-template-lowering-compatibility-report.json
?? evidence/gate3-generic-discovery-contract/provider-free-test-results.json
?? evidence/gate3-question-first-subject-universe/artifact-inventory.json
?? evidence/gate3-question-first-subject-universe/eligibility-methodology.md
?? evidence/gate3-question-first-subject-universe/eligible-subject-universe.json
?? evidence/gate3-question-first-subject-universe/excluded-subjects.json
?? evidence/gate3-question-first-subject-universe/exposure-ledger.json
?? evidence/gate3-question-first-subject-universe/subject-universe-manifest.json
?? evidence/gate3-question-first-subject-universe/verification-results.json
?? evidence/gate3-question-first-v15-preflight/artifact-inventory.json
?? evidence/gate3-question-first-v15-preflight/blockers-and-limitations.json
?? evidence/gate3-question-first-v15-preflight/execution-cost-forecast.json
?? evidence/gate3-question-first-v15-preflight/frozen-execution-packet-manifest.json
?? evidence/gate3-question-first-v15-preflight/frozen-sample-verification.json
?? evidence/gate3-question-first-v15-preflight/no-oracle-no-provider-attestation.json
?? evidence/gate3-question-first-v15-preflight/per-case-lowering-results.json
?? evidence/gate3-question-first-v15-preflight/preflight-test-results.json
?? evidence/gate3-question-first-v15-preflight/provider-visible-evidence-manifest.json
?? evidence/gate3-question-first-v15-preflight/retained-evidence-body-inventory.json
?? evidence/gate3-question-first-v15-preflight/source-acquisition-and-admission-ledger.json
?? evidence/gate3-v15-execution-envelope-preflight/artifact-inventory.json
?? evidence/gate3-v15-execution-envelope-preflight/blockers-and-limitations.json
?? evidence/gate3-v15-execution-envelope-preflight/derived-execution-envelope-contract.json
?? evidence/gate3-v15-execution-envelope-preflight/evaluation-baseline-chronology.json
?? evidence/gate3-v15-execution-envelope-preflight/field-level-authority-matrix.json
?? evidence/gate3-v15-execution-envelope-preflight/frozen-input-verification.json
?? evidence/gate3-v15-execution-envelope-preflight/generic-synthetic-tests.json
?? evidence/gate3-v15-execution-envelope-preflight/per-instance-lowering-results.json
?? evidence/gate3-v15-provider-free-execution-preflight/artifact-sha256-inventory.json
?? evidence/gate3-v15-provider-free-execution-preflight/compatibility-audit-ledger.json
?? evidence/gate3-v15-provider-free-execution-preflight/cost-forecast.json
?? evidence/gate3-v15-provider-free-execution-preflight/evidence-admission-ledger.json
?? evidence/gate3-v15-provider-free-execution-preflight/frozen-execution-envelopes.json
?? evidence/gate3-v15-provider-free-execution-preflight/frozen-execution-packets.json
?? evidence/gate3-v15-provider-free-execution-preflight/validation-results.json
?? evidence/gate3-v151-implementation/artifact-inventory.json
?? evidence/gate3-v151-implementation/implementation-summary.md
?? evidence/gate3-v151-implementation/verification-results.json
?? reports/G4_A3E_INTEGRATED_OFFLINE_20261021_V2.md
?? reports/G4_BRIDGE_RECOVERY_ROUNDTRIP_20261024.md
?? reports/G4_INDUSTRIALISATION_EVIDENCE_REVIEW_20261021_A2.md
?? reports/G4_O1B_CONTROLLED_WINDOWS_CUTOVER_2026-10-20.md
?? reports/G4_O1C_SUPERVISORY_READONLY_20261021_A1.md
?? reports/G4_O1D_SUPERVISORY_ACCEPTANCE_20261021.md
?? reports/G4_O1E_O1F_CONTROLLED_CUTOVER_20261024.md
?? reports/G4_O1E_O1F_DOUBLE_LOOP_BOOTSTRAP_20261021.md
?? reports/G4_O1E_O1F_FAIL_CLOSED_REPAIR_20261024.md
?? reports/G4_O1E_O1F_RECERTIFICATION_20261024.md
?? reports/G4_O1E_O1F_RECERTIFICATION_20261024_REPAIR2.md
?? reports/G4_O1E_O1F_RECERTIFICATION_20261024_REPAIR2_FINAL.md
?? reports/G4_O1E_O1F_SUPERVISORY_ACCEPTANCE_20261022.md
?? reports/G4_P1_GOVERNED_FACTORY_INTEGRATION_20261025.md
?? reports/G4_P2_GOVERNED_SCOPE_ISOLATION_20261025.md
?? reports/G4_P2_GOVERNED_SCOPE_ISOLATION_CORRECTED_20261025.md
?? reports/G4_P2_SOL_P1_ARCHAEOLOGY_20261025.md
```

All 261 records above were treated as pre-existing and preserved. In particular, the three P2 dirty paths and all other dirty/untracked paths were not changed.

## Post-review status

The only permitted mutation was creation of this new report. The expected and subsequently checked post-review status is the pre-review status above plus this one new untracked path:

```text
 M docs/G4_O1B_SUPERVISORY_SUBMISSION.md
 M docs/G4_O1C_SUPERVISORY_SUBMISSION.md
 M src/charitygraph/phase5_factory.py
 M tests/test_phase5_factory.py
 M tests/test_phase5_governed_factory_integration.py
?? evidence/cg406-proposition-relevance-remediation/artifact-inventory.json
?? evidence/cg406-proposition-relevance-remediation/before-after-evidence-family-matrix.md
?? evidence/cg406-proposition-relevance-remediation/handoff.json
?? evidence/cg406-proposition-relevance-remediation/prepared-request-identity-manifest.json
?? evidence/cg406-proposition-relevance-remediation/summary.md
?? evidence/cg406-proposition-relevance-remediation/test-results.md
?? evidence/cg406-proposition-relevance-remediation/validation-results.json
?? evidence/cg406-provider-development-replay/accounting-token-spend-ledger.md
?? evidence/cg406-provider-development-replay/artifact-sha256-inventory.json
?? evidence/cg406-provider-development-replay/frozen-development-result-manifest.json
?? evidence/cg406-provider-development-replay/handoff.json
?? evidence/cg406-provider-development-replay/per-row-old-new-mechanical-comparison.json
?? evidence/cg406-provider-development-replay/prepared-run-identity.json
?? evidence/cg406-provider-development-replay/provider-visible-corpus-summary.md
?? evidence/cg406-provider-development-replay/summary.md
?? evidence/cg406-provider-development-replay/terminal-result-ledger.json
?? evidence/cg406-provider-development-replay/validation-results.json
?? evidence/cg406-provider-development-replay/validation-results.md
?? evidence/cg406-public-source-transmission-policy/artifact-inventory.md
?? evidence/cg406-public-source-transmission-policy/before-after-classification.md
?? evidence/cg406-public-source-transmission-policy/handoff.json
?? evidence/cg406-public-source-transmission-policy/prepared-request-manifest.json
?? evidence/cg406-public-source-transmission-policy/provider-visible-corpus-summary.md
?? evidence/cg406-public-source-transmission-policy/summary.md
?? evidence/cg406-public-source-transmission-policy/validation-and-test-results.md
?? evidence/cg406-rights-catalog-resolution/classification-rules.md
?? evidence/cg406-rights-catalog-resolution/handoff.json
?? evidence/cg406-rights-catalog-resolution/inventory.json
?? evidence/cg406-rights-catalog-resolution/prepared-request-identity.md
?? evidence/cg406-rights-catalog-resolution/product-owner-decision.md
?? evidence/cg406-rights-catalog-resolution/summary.md
?? evidence/cg406-rights-catalog-resolution/test-results.md
?? evidence/cg406-v12-development-replay/accounting-reconciliation.json
?? evidence/cg406-v12-development-replay/artifact-inventory.json
?? evidence/cg406-v12-development-replay/frozen-result-manifest.json
?? evidence/cg406-v12-development-replay/handoff.json
?? evidence/cg406-v12-development-replay/mechanical-old-new-comparison.json
?? evidence/cg406-v12-development-replay/per-row-proposition-scope-assessment.json
?? evidence/cg406-v12-development-replay/post-run-tests.json
?? evidence/cg406-v12-development-replay/prepared-run-identity.json
?? evidence/cg406-v12-development-replay/provider-visible-family-coverage.json
?? evidence/cg406-v12-development-replay/resume-verification.json
?? evidence/cg406-v12-development-replay/summary.md
?? evidence/cg406-v12-development-replay/terminal-result-ledger.json
?? evidence/cg406-v12-development-replay/validation-results.json
?? evidence/cg406-v12-inference-integrity/artifact-inventory.json
?? evidence/cg406-v12-inference-integrity/forensic-diagnosis.json
?? evidence/cg406-v12-inference-integrity/handoff.json
?? evidence/cg406-v12-inference-integrity/preparation-summary.json
?? evidence/cg406-v12-inference-integrity/source-relevance-matrix.json
?? evidence/cg406-v12-inference-integrity/summary.md
?? evidence/cg406-v12-inference-integrity/test-results.json
?? evidence/cg406-v12-inference-integrity/typed-demand-contract.json
?? evidence/cg406-v13-development-replay/accounting-reconciliation.json
?? evidence/cg406-v13-development-replay/artifact-inventory.json
?? evidence/cg406-v13-development-replay/evidence-source-relevance-details.json
?? evidence/cg406-v13-development-replay/execution-control-investigation.json
?? evidence/cg406-v13-development-replay/frozen-result-manifest.json
?? evidence/cg406-v13-development-replay/handoff.json
?? evidence/cg406-v13-development-replay/mechanical-v12-v13-comparison.json
?? evidence/cg406-v13-development-replay/prepared-execution-reconciliation.json
?? evidence/cg406-v13-development-replay/resume-verification.json
?? evidence/cg406-v13-development-replay/summary.md
?? evidence/cg406-v13-development-replay/terminal-result-ledger.json
?? evidence/cg406-v13-development-replay/test-results.json
?? evidence/cg406-v13-development-replay/validation-results.json
?? evidence/cg406-v14-final-development-replay/accounting-reconciliation.json
?? evidence/cg406-v14-final-development-replay/artifact-inventory.json
?? evidence/cg406-v14-final-development-replay/build_inventory.py
?? evidence/cg406-v14-final-development-replay/compile_v14_handoff.py
?? evidence/cg406-v14-final-development-replay/execution-authorization-record.txt
?? evidence/cg406-v14-final-development-replay/execution-control.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_05548f0ccf7149e6de515c588d0e0fc9660b8e3a29c84818a5c6c15f4895a678.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_0c8670382dd4e601bfae3df3499433ae572c1bd9e691b92b24a7262715df5574.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_2351ed3c9bcbfb14e0c71dcf29d09f035fcbffc1b4fa3728119ea64a5ad4a9de.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_29c9ea5b8d8494a24ec9f53af0939c7c6067400a45e0fa7ff3a5d43bbef077aa.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_35e5b2fc771d8b1c99ae2f6a44a82687079c409bee7fc745dd47b250854cb1de.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_60b971d6426bc384dc834b0e195e74c612a92eca5da94917f41c27504f288f30.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_622dd70fc49e331b0f4d3bfa118473dce96b5d0452cd318b447d5ad02f25e207.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_681c2dac224e4f58586ecb4b766346ef426a3da5edbfb93acd88958aadd62f67.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_8111f774ba82ba935ec0b95d25e6ebaa4a678e58e2642168fb74b63713a5571b.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_ab0adb34716c60bb9423e44b8b3191ab0cf9675536a9554fe0a38e957d828e57.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_e8c236a6e42905ecc32f0787a809319b425df2d970d0bac785954f8cd9504c47.json
?? evidence/cg406-v14-final-development-replay/first-terminal-responses/requestitem_ee6509de8f51dd822038923084dbff8efd896bd8537c21afd7926e70eff2e549.json
?? evidence/cg406-v14-final-development-replay/freeze_v14_terminal_results.py
?? evidence/cg406-v14-final-development-replay/frozen-result-manifest.json
?? evidence/cg406-v14-final-development-replay/mechanical-v13-v14-comparison.json
?? evidence/cg406-v14-final-development-replay/postfreeze-analysis.json
?? evidence/cg406-v14-final-development-replay/prepared-run-identity.json
?? evidence/cg406-v14-final-development-replay/resume-verification.json
?? evidence/cg406-v14-final-development-replay/sol-handoff.json
?? evidence/cg406-v14-final-development-replay/summary.md
?? evidence/cg406-v14-final-development-replay/targeted-diagnostics.md
?? evidence/cg406-v14-final-development-replay/terminal-result-ledger.json
?? evidence/cg406-v14-final-development-replay/test-results.json
?? evidence/cg406-v14-final-development-replay/validate_v14_terminal_results.py
?? evidence/cg406-v14-final-development-replay/validation-results.json
?? evidence/cg406-v14-final-development-replay/verify_v14_packet.py
?? evidence/gate3-cg405-identity-reconciliation-review/artifact-inventory.json
?? evidence/gate3-cg405-identity-reconciliation-review/bounded-freshness-methodology.md
?? evidence/gate3-cg405-identity-reconciliation-review/exposure-eligibility-audit.json
?? evidence/gate3-cg405-identity-reconciliation-review/five-match-architecture-audit.json
?? evidence/gate3-cg405-identity-reconciliation-review/question-designer-handoff-inventory.json
?? evidence/gate3-cg405-identity-reconciliation-review/successor-eligible-subject-universe.json
?? evidence/gate3-cg405-identity-reconciliation-review/successor-excluded-subjects.json
?? evidence/gate3-cg405-identity-reconciliation-review/successor-subject-universe-manifest.json
?? evidence/gate3-cg405-identity-reconciliation-review/verification-results.json
?? evidence/gate3-cg405-identity-reconciliation/artifact-inventory.json
?? evidence/gate3-cg405-identity-reconciliation/cg405-identity-crosswalk.json
?? evidence/gate3-cg405-identity-reconciliation/historical-identity-lineage-analysis.md
?? evidence/gate3-cg405-identity-reconciliation/updated-exposure-ledger.json
?? evidence/gate3-cg405-identity-reconciliation/verification-results.json
?? evidence/gate3-final-semantic-review/artifact-inventory.json
?? evidence/gate3-final-semantic-review/case-assessments.json
?? evidence/gate3-final-semantic-review/identity-verification.json
?? evidence/gate3-final-semantic-review/scoring-methodology.md
?? evidence/gate3-final-semantic-review/summary.md
?? evidence/gate3-fresh-36-builder-preparation/artifact-inventory.json
?? evidence/gate3-fresh-36-builder-preparation/corpus-identity-manifest.json
?? evidence/gate3-fresh-36-builder-preparation/frozen-input-verification.json
?? evidence/gate3-fresh-36-builder-preparation/handoff.json
?? evidence/gate3-fresh-36-builder-preparation/preparation-contract-validation.json
?? evidence/gate3-fresh-36-builder-preparation/prepared-request-status.json
?? evidence/gate3-fresh-36-builder-preparation/provider-corpus-admission-ledger.json
?? evidence/gate3-fresh-36-builder-preparation/provider-free-guard.json
?? evidence/gate3-fresh-36-builder-preparation/source-acquisition-ledger.json
?? evidence/gate3-fresh-36-builder-preparation/source-acquisition-summary.json
?? evidence/gate3-fresh-36-builder-preparation/source-coverage-matrix.json
?? evidence/gate3-fresh-36-builder-preparation/source-gap-register.json
?? evidence/gate3-fresh-36-builder-preparation/summary.md
?? evidence/gate3-fresh-36-builder-preparation/test-results.json
?? evidence/gate3-fresh-36-executable-demand-specification/artifact-inventory.json
?? evidence/gate3-fresh-36-executable-demand-specification/candidate-executable-demand-specifications.json
?? evidence/gate3-fresh-36-executable-demand-specification/contract-gap-matrix.json
?? evidence/gate3-fresh-36-executable-demand-specification/deterministic-instantiation-procedure.json
?? evidence/gate3-fresh-36-executable-demand-specification/evidence-corpus-continuity.json
?? evidence/gate3-fresh-36-executable-demand-specification/handoff.json
?? evidence/gate3-fresh-36-executable-demand-specification/oracle-compatibility-analysis.json
?? evidence/gate3-fresh-36-executable-demand-specification/proposed-executable-demand-specification-schema.json
?? evidence/gate3-fresh-36-executable-demand-specification/required-semantic-decisions.json
?? evidence/gate3-fresh-36-executable-demand-specification/summary.md
?? evidence/gate3-fresh-36-executable-demand-specification/test-results.json
?? evidence/gate3-fresh-semantic-holdout-preparation/artifact-inventory.json
?? evidence/gate3-fresh-semantic-holdout-preparation/baseline.json
?? evidence/gate3-fresh-semantic-holdout-preparation/build_holdout_packet.py
?? evidence/gate3-fresh-semantic-holdout-preparation/content-artifact-inventory.json
?? evidence/gate3-fresh-semantic-holdout-preparation/demand-definition-vocabulary.json
?? evidence/gate3-fresh-semantic-holdout-preparation/domain-distribution.json
?? evidence/gate3-fresh-semantic-holdout-preparation/eligibility-audit.json
?? evidence/gate3-fresh-semantic-holdout-preparation/excluded-case-inventory.json
?? evidence/gate3-fresh-semantic-holdout-preparation/frozen-selected-holdout-manifest.json
?? evidence/gate3-fresh-semantic-holdout-preparation/handoff.json
?? evidence/gate3-fresh-semantic-holdout-preparation/independence-and-blindness-audit.json
?? evidence/gate3-fresh-semantic-holdout-preparation/indicative-provider-budget.json
?? evidence/gate3-fresh-semantic-holdout-preparation/later-execution-and-blindness-protocol.md
?? evidence/gate3-fresh-semantic-holdout-preparation/packet-structural-test-results.json
?? evidence/gate3-fresh-semantic-holdout-preparation/preregistered-scoring-rubric.md
?? evidence/gate3-fresh-semantic-holdout-preparation/repository-test-results.json
?? evidence/gate3-fresh-semantic-holdout-preparation/sealed-oracle-construction-instructions.md
?? evidence/gate3-fresh-semantic-holdout-preparation/selection-algorithm.json
?? evidence/gate3-fresh-semantic-holdout-preparation/summary.md
?? evidence/gate3-fresh-semantic-holdout-preparation/verify_holdout_packet.py
?? evidence/gate3-fresh36-bounded-recovery-v1/artifact-inventory.json
?? evidence/gate3-fresh36-bounded-recovery-v1/inventory-sha256.txt
?? evidence/gate3-fresh36-bounded-recovery-v1/recovery-status.json
?? evidence/gate3-fresh36-bounded-recovery-v1/source-lineage-recovery.json
?? evidence/gate3-fresh36-bounded-recovery-v1/successor-acquisition.json
?? evidence/gate3-fresh36-bounded-recovery-v1/summary.md
?? evidence/gate3-fresh36-semantic-execution-v1/artifact-sha256-inventory.json
?? evidence/gate3-fresh36-semantic-execution-v1/attempt-ledger.json
?? evidence/gate3-fresh36-semantic-execution-v1/execution-manifest.json
?? evidence/gate3-fresh36-semantic-execution-v1/experiment-configuration.json
?? evidence/gate3-fresh36-semantic-execution-v1/failures-and-missingness.json
?? evidence/gate3-fresh36-semantic-execution-v1/inventory-sha256.txt
?? evidence/gate3-fresh36-semantic-execution-v1/raw-responses.jsonl
?? evidence/gate3-fresh36-semantic-execution-v1/record_blocked_attempts.py
?? evidence/gate3-fresh36-semantic-execution-v1/request-compilation-status.json
?? evidence/gate3-fresh36-semantic-execution-v1/rights-binding-ledger.json
?? evidence/gate3-fresh36-semantic-execution-v1/trusted-authorization-status.json
?? evidence/gate3-fresh36-semantic-execution-v1/validation-results.json
?? evidence/gate3-fresh36-semantic-execution-v1/verified-frozen-inputs.json
?? evidence/gate3-fresh36-semantic-execution-v2/artifact-inventory.json
?? evidence/gate3-fresh36-semantic-execution-v2/governance/product-owner-government-data-transmission-decision.json
?? evidence/gate3-fresh36-semantic-execution-v2/status-and-blocker.md
?? evidence/gate3-generic-discovery-contract-v15/17-gap-root-cause-resolution-matrix.json
?? evidence/gate3-generic-discovery-contract-v15/36-template-compatibility-matrix.json
?? evidence/gate3-generic-discovery-contract-v15/artifact-inventory.json
?? evidence/gate3-generic-discovery-contract-v15/identity-and-source-governance-verification.json
?? evidence/gate3-generic-discovery-contract-v15/implementation-changes.md
?? evidence/gate3-generic-discovery-contract-v15/missing-semantics-treatment.json
?? evidence/gate3-generic-discovery-contract-v15/provider-free-test-results.json
?? evidence/gate3-generic-discovery-contract-v15/synthetic-execution-results.json
?? evidence/gate3-generic-discovery-contract-v15/v14-regression-verification.json
?? evidence/gate3-generic-discovery-contract-v15/v15-contract-schema.json
?? evidence/gate3-generic-discovery-contract-v15/verified-input-package-provenance.json
?? evidence/gate3-generic-discovery-contract/17-gap-root-cause-analysis.md
?? evidence/gate3-generic-discovery-contract/architecture-compliance-verification.json
?? evidence/gate3-generic-discovery-contract/artifact-inventory.json
?? evidence/gate3-generic-discovery-contract/fixture-isolation-verification.json
?? evidence/gate3-generic-discovery-contract/generic-discovery-contract-status.md
?? evidence/gate3-generic-discovery-contract/handoff.json
?? evidence/gate3-generic-discovery-contract/per-template-lowering-compatibility-report.json
?? evidence/gate3-generic-discovery-contract/provider-free-test-results.json
?? evidence/gate3-question-first-subject-universe/artifact-inventory.json
?? evidence/gate3-question-first-subject-universe/eligibility-methodology.md
?? evidence/gate3-question-first-subject-universe/eligible-subject-universe.json
?? evidence/gate3-question-first-subject-universe/excluded-subjects.json
?? evidence/gate3-question-first-subject-universe/exposure-ledger.json
?? evidence/gate3-question-first-subject-universe/subject-universe-manifest.json
?? evidence/gate3-question-first-subject-universe/verification-results.json
?? evidence/gate3-question-first-v15-preflight/artifact-inventory.json
?? evidence/gate3-question-first-v15-preflight/blockers-and-limitations.json
?? evidence/gate3-question-first-v15-preflight/execution-cost-forecast.json
?? evidence/gate3-question-first-v15-preflight/frozen-execution-packet-manifest.json
?? evidence/gate3-question-first-v15-preflight/frozen-sample-verification.json
?? evidence/gate3-question-first-v15-preflight/no-oracle-no-provider-attestation.json
?? evidence/gate3-question-first-v15-preflight/per-case-lowering-results.json
?? evidence/gate3-question-first-v15-preflight/preflight-test-results.json
?? evidence/gate3-question-first-v15-preflight/provider-visible-evidence-manifest.json
?? evidence/gate3-question-first-v15-preflight/retained-evidence-body-inventory.json
?? evidence/gate3-question-first-v15-preflight/source-acquisition-and-admission-ledger.json
?? evidence/gate3-v15-execution-envelope-preflight/artifact-inventory.json
?? evidence/gate3-v15-execution-envelope-preflight/blockers-and-limitations.json
?? evidence/gate3-v15-execution-envelope-preflight/derived-execution-envelope-contract.json
?? evidence/gate3-v15-execution-envelope-preflight/evaluation-baseline-chronology.json
?? evidence/gate3-v15-execution-envelope-preflight/field-level-authority-matrix.json
?? evidence/gate3-v15-execution-envelope-preflight/frozen-input-verification.json
?? evidence/gate3-v15-execution-envelope-preflight/generic-synthetic-tests.json
?? evidence/gate3-v15-execution-envelope-preflight/per-instance-lowering-results.json
?? evidence/gate3-v15-provider-free-execution-preflight/artifact-sha256-inventory.json
?? evidence/gate3-v15-provider-free-execution-preflight/compatibility-audit-ledger.json
?? evidence/gate3-v15-provider-free-execution-preflight/cost-forecast.json
?? evidence/gate3-v15-provider-free-execution-preflight/evidence-admission-ledger.json
?? evidence/gate3-v15-provider-free-execution-preflight/frozen-execution-envelopes.json
?? evidence/gate3-v15-provider-free-execution-preflight/frozen-execution-packets.json
?? evidence/gate3-v15-provider-free-execution-preflight/validation-results.json
?? evidence/gate3-v151-implementation/artifact-inventory.json
?? evidence/gate3-v151-implementation/implementation-summary.md
?? evidence/gate3-v151-implementation/verification-results.json
?? reports/G4_A3E_INTEGRATED_OFFLINE_20261021_V2.md
?? reports/G4_BRIDGE_RECOVERY_ROUNDTRIP_20261024.md
?? reports/G4_INDUSTRIALISATION_EVIDENCE_REVIEW_20261021_A2.md
?? reports/G4_O1B_CONTROLLED_WINDOWS_CUTOVER_2026-10-20.md
?? reports/G4_O1C_SUPERVISORY_READONLY_20261021_A1.md
?? reports/G4_O1D_SUPERVISORY_ACCEPTANCE_20261021.md
?? reports/G4_O1E_O1F_CONTROLLED_CUTOVER_20261024.md
?? reports/G4_O1E_O1F_DOUBLE_LOOP_BOOTSTRAP_20261021.md
?? reports/G4_O1E_O1F_FAIL_CLOSED_REPAIR_20261024.md
?? reports/G4_O1E_O1F_RECERTIFICATION_20261024.md
?? reports/G4_O1E_O1F_RECERTIFICATION_20261024_REPAIR2.md
?? reports/G4_O1E_O1F_RECERTIFICATION_20261024_REPAIR2_FINAL.md
?? reports/G4_O1E_O1F_SUPERVISORY_ACCEPTANCE_20261022.md
?? reports/G4_P1_GOVERNED_FACTORY_INTEGRATION_20261025.md
?? reports/G4_P2_GOVERNED_SCOPE_ISOLATION_20261025.md
?? reports/G4_P2_GOVERNED_SCOPE_ISOLATION_CORRECTED_20261025.md
?? reports/G4_P2_SOL_ACCEPTANCE_REVIEW_20261025.md
?? reports/G4_P2_SOL_P1_ARCHAEOLOGY_20261025.md
```

No pre-existing path was altered, staged, deleted, reset, checked out, formatted, repaired, or overwritten. The new report is the sole review artifact.

## Acceptance matrix

| Question | Result |
|---|---|
| Control fence/branch/HEAD/tree | Fence, branch, HEAD and tree match; workspace catalogue count mismatch caused STOP |
| Complete scoped P2 diff and hashes | NOT RUN after STOP |
| Governed factory/catalogue flow | NOT RUN after STOP |
| Multi-reference, isolation, restart and accounting evidence | NOT RUN after STOP |
| Focused provider-free tests | NOT RUN after STOP |
| Post-test diff/check and path delta | No post-test checks; report-only path delta documented above |
| Bounded P2 acceptance | **FAIL — acceptance not established due control stop** |


