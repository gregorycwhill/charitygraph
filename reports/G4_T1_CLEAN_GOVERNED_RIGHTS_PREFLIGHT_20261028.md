# G4-O1C Tranche 1B — clean governed-rights preflight

Date: 2026-10-28 (Australia/Sydney)
Clean target: `gate3-cg406-remediation` HEAD `4bf112726f289b191c9f765e0c3bfc3f0d0cd021`
Mode: local, provider-free, no acquisition, no model, no network, no spend

## Accepted proof

- Added a narrow public bridge from the private content-addressed `RightsGovernanceStore` through a verified v29 `rights_projection_current` lookup into the existing clean Phase5 governed-reference preflight and `FactoryPlan`.
- Authority is reloaded by exact record SHA. The bridge verifies current projection identity, subject, scope, source artifact/record, origin, source role, representation artifact/SHA, acquisition receipt lineage, local-retention authority, representation bytes and direct artifact lineage before lowering.
- Current-state lookup fails closed for stale dates, missing/corrupt rows and duplicate current identities. `RightsGovernanceRecord.can_promote()` preserves optional expiry, revoked and superseded behaviour; expiry equality remains accepted by the existing authority contract.
- The request does not accept a copied rights-policy ID as authority; policy identity and version come from the authoritative record. The committed source-rights module has no exact `PROVIDER_POLICY_REGISTRY`, so provider transmission remains blocked/fail-closed. The positive test uses only the existing local FakeProvider rehearsal with provider transmission blocked.
- Denied authority paths perform reads only and create zero tasks, physical attempts, reservations, receipts or cost entries. Positive restart/idempotence is proven in the clean archive test.

## Allowlisted diff

- `src/charitygraph/runtime/rights_governance_projection.py`: added `current_record()` as a verified read-only v29 current-state lookup.
- `src/charitygraph/phase5_governed_rights_preflight.py`: new explicit authority-to-Factory preflight adapter.
- `tests/test_phase5_governed_rights_preflight.py`: provider-free fixture covering positive lowering/restart, denied side-effect-free paths and absent provider registry.
- This report.

Dirty prototype files, dirty tests, `artifact_rights_*` side tables and physical-attempt hardening were not changed or used as authority.

## Tests

Using `python -B -m pytest -o addopts= -p no:cacheprovider` with basetemp under `C:\CharityGraph-runtime`:

- Clean archive focused set: **33 passed** — new bridge, v29 rights projection, migrations, clean governed Factory integration and Phase5 preflight.
- Clean archive rights-record suite: **18 passed, 1 known committed failure** in `test_compatibility_matches_existing_artifact_rights_decision_and_sqlite_projection`; clean `ArtifactRightsDecision` rejects newer compatibility fields (`representation_artifact_id`, policy versions and `assessment_authority`). This is the documented schema mismatch and was not weakened.
- Live dirty worktree new test: **2 passed, 1 skipped**. The positive clean-seam test is explicitly skipped when the pre-existing dirty integration module exposes `rights_decision_ids`, because that prototype requires dirty `artifact_rights_*` rows. Clean archive proof is the accepted result.
- `git diff --check` passed for the allowlisted implementation/test paths.

## Boundary and residuals

No private source bytes, reports, prompts, model responses, runtime state, caches, credentials, logs or debug files were added. No provider/model/network/source acquisition/spend or external mutation occurred. The main Git index and object database are ACL read-only for this worker (`git add` fails with permission denied); an alternate runtime index also cannot insert objects into `.git/objects`. Therefore the required exact-allowlist commit was not creatable in this environment. No permissions were changed and no unrelated dirty/staged work was touched. Provider-positive production processing remains blocked pending a source-owned provider-policy ID/version registry and governing decision.
