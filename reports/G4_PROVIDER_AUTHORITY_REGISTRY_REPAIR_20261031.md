# G4 provider authority registry repair — independent acceptance

Date: 2026-10-31 (Australia/Sydney)
Worker: bounded G4-O1C, provider-free and report-only
Target: `gate3-cg406-remediation@3eb28abf4647136132e7fe558900d091c21d814b`
Parent: `85f6ff5753124dee6716aeae3fc9c2dccbc657d4`
Fence: `v77`

## Verdict

- Dormant fail-closed structural control: **ACCEPT** — structural consistency
  only; it is explicitly unauthenticated and never send-ready.
- Source-owned product authorization: **REJECT / still missing** — no durable
  Data-owned provider authority binding or independently authenticated trust
  root was available, and none was invented.
- Overall tranche: **PARTIAL**, limited to the dormant structural control.

The prior independent REJECT is addressed for its two concrete defects: a
coherent caller-created record plus matching caller pin now returns
`STRUCTURE_ONLY_UNAUTHENTICATED`, with `authority_verified=False`, `action=NONE`
and `real_send_ready=False`; and the record's
`authority_content_sha256` is checked against exact, separately supplied,
canonical `authority_document_bytes`. Missing, non-canonical, mismatched and
self-referential document bytes block. Caller pins, locators, policy names and
defaults do not certify source ownership.

## Scope and authority

The exact direct-child diff contains only the four requested paths:

- `src/charitygraph/g4_provider_policy_registry.py`
- `src/charitygraph/phase5_governed_rights_preflight.py`
- `tests/test_g4_provider_policy_registry.py`
- `reports/G4_PROVIDER_AUTHORITY_REGISTRY_REPAIR_20261031.md`

I reviewed Builder `ARCHITECTURE.md` and `BUILDER_MACHINERY.md`, the prior
independent REJECT, and the sibling Data repository's
`DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, `COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`,
`INTEGRATED_PRODUCT_AND_DATA_MODEL.md`,
`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`,
`TAXONOMY_AND_SCHEME_GOVERNANCE.md`, `IMPLEMENTATION_PLAN.md`, `TEST_PLAN.md`
and `SEMANTIC_HEURISTIC_APPROVALS.md`. The canonical boundary remains that
source rights, local retention, provider transmission and public redistribution
are independent axes; v29 is a projection, not an authority root; and public
projections are release representations rather than canonical knowledge.

## Clean exact-archive validation

Both revisions were extracted with `git archive` and tested from isolated
source trees with `python -B`, `PYTHONDONTWRITEBYTECODE=1`,
`-p no:cacheprovider`, and external disposable basetemps. No dirty Factory,
rights or runtime files were copied into either archive.

| Selection | Clean parent | Repaired HEAD |
|---|---:|---:|
| Focused registry/adversarial test file | 13 passed | 19 passed |
| Preflight + Factory + governed Factory integration | 15 passed | 15 passed |
| Broader relevant selection below | 119 passed, 1 failed | 125 passed, 1 failed |

The broader selection was:
`test_g4_provider_policy_registry.py`,
`test_phase5_t4a_provider_contract_registry.py`,
`test_phase5_t4a_provider_contract_identity_probe.py`,
`test_phase5_provider_processing_policy.py`,
`test_phase5_governed_rights_preflight.py`,
`test_phase5_governed_factory_integration.py`, `test_source_rights.py`,
`tests/runtime/test_rights_governance_record.py` and
`tests/runtime/test_rights_governance_projection.py`.

The one failure is identical on parent and repaired HEAD, in
`tests/runtime/test_rights_governance_record.py::test_compatibility_matches_existing_artifact_rights_decision_and_sqlite_projection`.
The legacy `ArtifactRightsDecision` fixture rejects four extra fields. It is
outside all four allowed paths and is therefore not introduced by this repair.
No repair-path test failed in either clean archive.

This reconciles the worker's dirty-worktree `73 passed / 1 skipped / 12 failed`
summary: that count is not a clean exact-HEAD result. The clean archives show
the same pre-existing compatibility failure on both revisions and no repair
regression. The worker's clean-preflight `16 passed / 1 skipped` likewise was
affected by the dirty rights seam; the exact parent and repaired archives both
run the complete selected subset as `15 passed / 0 skipped`.

An additional provider-free adversarial probe passed **14/14**. It covered
forged record+pin handling, caller-promotion rejection, exact separate-document
hash and canonicality, missing/mismatched/self-reference blocking,
stale/renewal-expired status, route drift, no-sharing posture, distinct local
retention/provider-transmission failures, missing/mismatched v29 projection,
absent host route/authority, and `NONE`/not-ready gate output.

The optional `provider_policy_authority` argument remains compatibility-only in
no-send preflight. Clean preflight tests passed with fake-provider lowering;
the lowered task path remains `provider_id="fake"`. The explicit
`require_authenticated_provider_authority_for_real_send` boundary is separate
and fails closed for unauthenticated authority, absent rights, absent or
mismatched v29, and absent/mismatched route. Static inspection found no caller
that turns this dormant gate or no-send preflight into real-send authority.

## Integrity and boundary

`git diff --check` is clean for all four direct-child paths. The current local
baseline is branch `gate3-cg406-remediation` at the exact target HEAD above;
the unrelated pre-existing dirty and untracked worktree paths were preserved.
Only this report path was written by this task.

No source acquisition, external source or network access, provider/model call,
credential use, budget reservation, spend, Drive/GitHub/bridge/watcher action,
publication, release, gate closure, code change, Git metadata change or runtime
state change was performed. Temporary clean archives and test basetemps were
disposable and private; no private evidence or runtime material was added to
the repository.

## Minimal next step

Provide and independently authenticate the durable Data-owned provider-policy
authority binding at the real provider boundary, then rerun this clean
parent-vs-child acceptance. Until then, retain the structural control as
dormant diagnostics only; do not treat it as source authorization or a send
grant.
