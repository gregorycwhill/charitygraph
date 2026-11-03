# G4-O1C P3c provider authority / clean-catalogue provenance archaeology

Date: 2026-10-27 (Australia/Sydney)  
Mode: strictly read-only, local, provider-free  
Fence: branch `gate3-cg406-remediation`, HEAD `7fffe4197681feba3d6c1607504076a742628481` (v38)

## Decision

| Area | Decision | Bounded meaning |
|---|---|---|
| A. Provider registry | **BLOCKED** | An exact provider-policy ID/version allowlist cannot be established from the source-owned versioned authority currently present. Do not invent a version or promote the dirty helper. |
| B. Clean catalogue projection | **READY** | The clean v29 migration and private-record projection/rebuild are independently implementable and testable without the dirty catalogue additions. This is offline/rebuildable control state, not provider readiness. |
| C. P4 clean fixture | **CONDITIONAL** | The clean-checkout persisted-run adapter and file-backed FakeProvider fixture import and pass provider-free tests. It proves only a synthetic/local diagnostic seam, not a historical production run or provider-side exactly-once behavior. |

Gate 4 remains open. No Product Owner acceptance, provider authorization, publication, release or gate closure is implied.

## Authority and provenance findings

The sibling Data repository was read at clean HEAD `f5f154cf2e3f107a9a2563c94626a0e39419fd3e`. Its `DOCUMENT_AUTHORITY.md` (blob `2e43f4994a12d998d6fe77c72d2439cff2bb045a`, current authority hierarchy and source/evidence authority), `NORTH_STAR_TARGET_CARD.md` (`e741d3b2941b82e9ef376c86bf9edd27cff9d3a8`), `INTEGRATED_PRODUCT_AND_DATA_MODEL.md` (`de8afa01efe516df6c537dd285571920a2a067df`), `SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md` (`59498c00f89ed558520ba5ddaefb31809b701b57`), `COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md` (`67096bb3656680c610b6ad41ceb6e8c906ba6d41`), `TAXONOMY_AND_SCHEME_GOVERNANCE.md` (`d5059c698c657013ede0022c076ff6d4c14bcd47`), `IMPLEMENTATION_PLAN.md` (`2814eb467de213fceacba76d7f43a52a5dbc7e96`), `TEST_PLAN.md` (`3d61b73d9d338ec19bea03f46bbfed329cec1826`) and `CURRENT_STATE.md` (`e5474bc8d2aff81545e8ffefb7299adbf639bc25`) were read. The relevant authority rule is: source/evidence governance owns rights/provenance; historical assessments and plans do not silently create current execution authority.

Candidate source-owned policy and historical artefacts:

| Candidate | Exact provenance in local Git | What it proves / does not prove |
|---|---|---|
| Builder `src/charitygraph/source_rights.py` | Current HEAD blob `bab1f855c5c4721e093f6d169b2f5ce022c12691`; last path-changing commit `3a784129e550564acdd19fcc67bdcdf595e846be`; enclosing HEAD `7fffe419…` | Owns `RIGHTS_POLICY_REGISTRY`, including rights policies at version `1.0.0`, and the constant `OPENAI_PROVIDER_POLICY_ID = OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1`. It has no `PROVIDER_POLICY_REGISTRY` and no provider-policy version mapping. |
| Data `SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md` | Current Data blob `59498c00f89ed558520ba5ddaefb31809b701b57`; last path-changing commit `f0c12c9fabfd62fc714cc32520b0320152a7fc21`; Data HEAD `f5f154cf…` | Canonically approves Fair Dealing policy `AU_FAIR_DEALING_ANALYTICAL_PROCESSING_V1` version `1.0.0`; names the OpenAI provider-policy ID as a condition; explicitly says the selected service, policy version and no-opt-in posture must be rechecked. It is normative text, not an exact provider ID/version registry. |
| Data `CURRENT_STATE.md` | Blob `e5474bc8d2aff81545e8ffefb7299adbf639bc25`; last path-changing commit `f5f154cf2e3f107a9a2563c94626a0e39419fd3e` | Records the 13 September Product Owner approval of the Fair Dealing policy and the historical 0/12 V3 rights-ready result. It does not add a provider version or current send authority. |
| Data `PHASE6_V3_POST_POLICY_RIGHTS_ASSESSMENT_2026-09-13.md` | Blob `755c9f20cee73912f6c0944803eee2bc83763153`; last path-changing commit `112765fd0e2442ca1d6b1eecacd12553a6980348` | Historical offline assessment binds exact representations and lineage and repeats the provider ID. Its status says V3 was unexecuted/not cleared; no version registry is present. |
| Data historical V4 `docs/history/phase6-corrected-confirmation-v4-2026-09-13/README.md` | Blob `0d78843169dc881e1d173a9bc66a7bdbc085c838`; last path-changing commit `112765fd0e2442ca1d6b1eecacd12553a6980348` | Historical table and owner attestation record the provider ID and attestation SHA `e64a9edf…`; the document explicitly has no current execution authority and supplies no exact provider version registry. |

Therefore the answer to “can an exact provider-policy ID/version allowlist be established?” is **no**. The specific missing governance decision is a Data/Product Owner-approved, source-owned versioned provider-policy registry: it must decide the exact provider policy identity/version, effective/evidence record and no-sharing posture, and the authority/renewal rule. This report intentionally supplies none of those values.

## Clean versus dirty implementation

The clean/dirty comparison used `git show HEAD:path`, `git rev-parse HEAD:path`, `git hash-object` and raw SHA-256; no checkout or Git metadata was changed.

| Path | Clean HEAD | Dirty worktree | Finding |
|---|---|---|---|
| `src/charitygraph/source_rights.py` | Git blob `bab1f855…`; raw SHA `13824bbe…` | Git blob `95e7aaaebfd5f3de63c88bb2f4d01e765dda1632`; raw SHA `72f0cc0b…` | Dirty-only `governed_rights_policy()` is a rights-registry resolver, not provider authority. Clean source has no such helper and no provider registry. |
| `src/charitygraph/runtime/catalog.py` | Git blob `5954ce82334bb4a00d0d20c697f66babca427e18`; raw SHA `079d1717…` | Git blob `7691f24a8faa6d74895a42a3411ac1a6b0f80068`; raw SHA `3e1a4cea…` | Dirty-only `ARTIFACT_RIGHTS_TABLE_SQL` side-installs `artifact_rights_decisions`, `artifact_rights_decision_events` and `provider_rights_diagnostics` (worktree lines 77–124), installs them from `_ensure_artifact_rights_tables()` (475–496), and exposes persistence/query methods (2993–3123). It has no commit provenance and was not absorbed. |

The clean catalogue contains none of the `artifact_rights_*` or provider-diagnostic DDL. Its exact rights projection is instead `rights_projection_records`, `rights_projection_events` and `rights_projection_current` in migration v29 (`src/charitygraph/runtime/migrations.py`, blob `9dac65cb45f6e4408fb65a9bfa0e92c352aed91b`, introduced by commit `0d88635f334dedc42bc3cecb29909597f10bc818`). `src/charitygraph/runtime/rights_governance_projection.py` (blob `6e006bc87aa931fa1e5715a0073c17eaa0b96bf6`, same commit) rebuilds only safe IDs, hashes, lifecycle and query metadata from the private content-addressed `RightsGovernanceStore`; private record bytes remain authoritative.

The clean record authority is `src/charitygraph/runtime/rights_governance_record.py` (blob `afd7f77176adc9ec38d1b5d8ca37b073c277c385`, remediation commit `006f6350e813a255b504f16518830420ec3d3962`). Its provider-axis check looks for `source_rights.PROVIDER_POLICY_REGISTRY` and fails closed when absent or mismatched. It does not import or promote the dirty helper.

## Clean-checkout proof

A `git archive HEAD` snapshot was created outside the checkout at `C:\CharityGraph-runtime\g4-o1c-clean-snapshot-20261027-01`; the dirty worktree and Git metadata were untouched. `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider` and an external pytest basetemp were used.

Direct clean import reported:

```text
clean_import_ok
provider_registry_present=False
openai_provider_id=OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1
supported_version=29
clean_catalog_rights_ddl=False
```

Selected clean-snapshot tests passed: `14 passed` across `tests/runtime/test_migrations.py`, `tests/runtime/test_rights_governance_projection.py` and `tests/runtime/test_phase5_run_diagnostics_catalog.py`. This proves clean import, v29 migration/reopen/projection behaviour and the P4 catalog adapter without dirty catalogue code. It does not prove provider authorization or a historical production run.

The P4 adapter/test provenance is clean HEAD `src/charitygraph/phase5_run_diagnostics_catalog.py` blob `279399f454ab1b10dc0ad097ca01e373fe8f67ce` and `tests/runtime/test_phase5_run_diagnostics_catalog.py` blob `7503d5dd294720c6aa34e716d307a2f15a47c90b`, both introduced by `7fffe4197681feba3d6c1607504076a742628481`. The fixture is file-backed and provider-free, but generated by the existing FakeProvider seam; it is not production-run evidence.

## Smallest next bounded tranche

Proceed only with the clean, provider-free paths below; keep the provider route and all dirty overlapping paths quarantined.

1. **Provider authority decision first (blocked prerequisite):** Product Owner/Data governance supplies the exact source-owned provider registry decision and versioned evidence. Then allowlist only `src/charitygraph/source_rights.py`, `src/charitygraph/runtime/rights_governance_record.py`, their focused tests, and a new report. Do not add a guessed version or reuse `governed_rights_policy()`.
2. **Clean catalogue projection:** allowlist `src/charitygraph/runtime/migrations.py`, `src/charitygraph/runtime/rights_governance_projection.py`, `tests/runtime/test_migrations.py`, `tests/runtime/test_rights_governance_projection.py`, and a bounded report. Prove v28→v29 checksum/reopen, deterministic/idempotent rebuild, corruption/missing-target/duplicate-current/cycle fail-closed behaviour, and transactional rollback in a temporary runtime root. Do not edit or absorb dirty `runtime/catalog.py`; the clean projection’s `rights_projection_*` tables are the intended seam.
3. **P4 fixture:** allowlist only `src/charitygraph/phase5_run_diagnostics_catalog.py`, `tests/runtime/test_phase5_run_diagnostics_catalog.py`, and a bounded report if the scope remains synthetic/local. Any claim about historical production persistence, provider-side exactly-once, or live readiness requires separately authorised evidence.

Private evidence, source bodies, prompts, model responses, runtime databases, caches, credentials, logs and generated public projections were not added to Git. No provider, model, source, network, spending, production database, watcher, GitHub, staging, commit, reset, checkout, release, publication or follow-on dispatch occurred.
