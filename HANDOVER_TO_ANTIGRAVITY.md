# HANDOVER TO ANTIGRAVITY

Final preservation verification: 3 November 2026, Australia/Sydney.

## 1. Executive Summary & State of play

CharityGraph development transfers to direct VS Code / Google Antigravity. The Product Owner permanently shut down ChatGPT/Codex autonomous development involvement, the Google Drive Agent Bridge, autonomous JSON queue, Executor, Supervisor, Harness Repairer and overnight restart roles. Do not resume these roles or execute archived queue instructions.

Final audit: **195 distinct accessible Git checkouts report empty `git status --porcelain -uall`; every audited current HEAD is present on a GitHub remote branch.** Older divergent branch histories were preserved under `decommission-20261103/*` without force-pushing or merging product code. The root handover commit necessarily follows the baseline SHA listed below; use `git rev-parse HEAD` / the current GitHub branch tip for the handover revision.

Primary continuation checkout: `C:\CharityGraph-clean\charitygraph`, branch `gate3-cg406-remediation`. Sibling canonical Data checkout: `C:\CharityGraph-clean\charitygraph-data`. Viewer and Playbooks checkouts remain under `C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph`.

Recent work (27 Octoberâ€“3 November) includes exact source/representation and acquisition-lineage retention, provider authority and rights registry changes, scope/physical-identity isolation, governed factory integration, real ACNC/register binding and source ingestion, project-cost reconciliation, durable accounting exports, operator health, bounded authority and bridge recovery/adoption changes. Preservation commits combine pre-existing concurrent work; they are not independent product acceptance.

Important recent source paths: `src/charitygraph/phase5_factory.py`, `phase5_t3_acnc_real_evidence_retention.py`, `phase5_t4d_e3_factory_handoff.py`, `phase5_governed_factory_integration.py`, `source_rights.py`, `bounded_authority.py`, `runtime/catalog.py`; bridge changes are retained for archaeology only.

## 2. Current System & Code Base Health

Focused fresh offline check: `python -m pytest tests/test_source_rights.py tests/test_phase5_t4d_e3_factory_handoff.py -q --basetemp <separate writable temporary directory> --tb=short`: **62 passed, 1 failed (63 tests)**. The default temporary location initially caused setup errors; the writable-location rerun exposed the actual product failure. Pytest also reported cache permission warnings. The full suite was not run; no full-suite green claim is made.

Known failure: `tests/test_phase5_t4d_e3_factory_handoff.py:438`, `test_synthetic_authorized_internal_policy_fixture_lowers_to_ten_children_and_replays`. `assert not first.diagnostics` fails because preflight emits `rights_missing` / `provider rights decision references are absent`, yielding zero tasks. Investigate the synthetic fixture and exact provider-rights lineage together; do not weaken production fail-closed rules to pass a fixture.

Runtime migrations are append-only in `src/charitygraph/runtime/migrations.py`; `SUPPORTED_VERSION` currently resolves to **29**, `rebuildable_private_rights_projection`. Other recent versions cover locator/subject identity (26), preprovider checkpoints (27), and historical terminals (28). No existing SQLite database was opened for migration or altered as part of this shutdown. Per-database applied versions and pending upgrades remain unverified. Preserve DB/WAL/SHM sets together before any future migration.

## 3. Incomplete Work & Known Debt

The one focused factory handoff failure remains for the incoming agent. Real-charity source ingestion, provider rights, answer projection, costs and Viewer integration require end-to-end product validation. Historic acceptance reports describe their original exact revisions and do not certify this combined preservation baseline.

Read `reports/G4_FACTORY_INTEGRATION_THREE_TEST_REPAIR_V102_20261102.md`, `reports/G4_FIRST_REAL_CHARITY_PUBLICDATA_LOCAL_SOURCE_INGEST_20261103.md`, `reports/G4_FIVE_CHARITY_REAL_REGISTER_BINDING_20261103.md`, and the Gate 4 closure-gap reports before prioritizing the product work.

Windows denied access while scanning old generated test directories in **31 audited checkouts**. Git still returned empty porcelain output, but those inaccessible contents cannot be certified. Ownership/access repair was attempted for `C:\CharityGraph-clean\charitygraph\CharityGraph-runtimecg405-pytest` and Windows denied it. No destructive cleanup was used to bypass this. Detailed warnings appear in the appendix.

Generated nested test repositories were retained outside the main source checkout at `C:\CharityGraph-clean\decommission-preserved-test-fixtures-20261103`. A nested historical experiment was preserved at `C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\decommission-preserved-nested-experiment-20261103`; its Git HEAD and parent experiment HEAD were pushed to `decommission-20261103/nested-*`. Existing registered worktree metadata may still reference that experimentâ€™s former path; repair metadata before using that archival copy.

The audit covers the discovered project roots, their registered existing worktrees and the additional top-level CharityGraph clones. Missing/prunable registrations are not live checkouts. Ignored runtime datasets/caches and inaccessible directories are retained locally; this is not a claim that all operational data is stored in Git.

## 4. Core Architecture Invariants for the New Agent

Read each repository AGENTS.md and the Data-owned canonical documents: `INTEGRATED_PRODUCT_AND_DATA_MODEL.md`, `SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`, `TAXONOMY_AND_SCHEME_GOVERNANCE.md`, `IMPLEMENTATION_PLAN.md`, `TEST_PLAN.md`, and `COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`. Data owns cross-product contracts; Builder implements governed processing; Viewer consumes released projections; Playbooks carry operating guidance.

Builder entry point: `charitygraph.cli:main`, configured in `pyproject.toml`. Python >=3.12; dev dependencies are in the `dev` extra. Source lives in `src/charitygraph`; tests in `tests`. Read `BUILD_AND_PUBLICATION.md` and the Viewer package scripts before building/publishing. No release or deployment occurred during closeout.

Durable subjects/scopes with governed typed observations are authoritative. Cards are public release projections. Keep source records, bindings, evidence, candidates, governed decisions, canonical observations, coverage and derivatives separate. Names/domains alone do not resolve identity. SQLite is rebuildable operational state, never sole evidence authority. Model output is not a human decision.

Python owns deterministic preparation, batching, scheduling, caching, cost controls, validation and compilation. Semantic work uses typed model tasks. Do not add unrestricted-language heuristics without the recorded semantic-heuristic approval. Preserve provenance, correction lineage, rights and cost accounting.

Builder does not discover new source families. The exhaustive admitted universe is `acnc_register`, `acnc_ais_bundle`, `ato_abr_dgr`, `official_website`, `annual_report`, `wikipedia_wikimedia`, `pfra`. Preserve public contract 0.5, compatibility identifiers and immutable release bytes; coordinate schema/Viewer migrations. Do not manually edit generated public projections.

Historical harness instructions are archival. This shutdown does not authorize restarting automation or recurring agent work.

## 5. Immediate Next Tasks (Prioritized)

1. Open the primary checkout in VS Code/Antigravity and investigate the failing synthetic factory handoff fixture against provider-rights lineage.

2. Run the broader offline Builder suite with a writable temporary directory and cache; record genuine product failures separately from Windows access issues.

3. Back up the intended operational SQLite catalogue, inspect its applied migration versions, and reconcile to schema 29 using documented migrations.

4. Complete and inspect one real-charity evidence-to-answer-to-Viewer product path, including identity, source provenance, rights, missingness and cost accounting.

5. Agree the next product milestone with the Owner; consolidate useful preserved branches deliberately and keep the autonomous harness retired.

## 6. Shutdown verification

Stopped managed launcher PID 47508. No managed watcher Python process remained at final process inspection. The Windows tasks `CharityGraph managed bridge liveness`, `CharityGraph overnight safety restart 0300`, and `CharityGraph overnight safety restart 0800` are Disabled. Task-action inspection found the same three CharityGraph jobs.

Drive root `bridge-status.json`, both cutover status artifacts, the active local runtime `status.json`, and the supervisor ledger were stamped `HALTED_DECOMMISSIONED`, `decommissioned=true`, and `dispatch_clear=false`. A permanent `HALTED_DECOMMISSIONED.txt` notice sits beside the Drive queue. Historical instructions were retained. These are local synced-folder writes; remote Google Drive delivery was not independently verified.

No local Codex `automations` directory exists. No tool available in this session enumerates ChatGPT cloud scheduled tasks; account-level recurring ChatGPT roles therefore cannot be independently certified as cancelled. The local execution harness is disabled.

## 7. Final checkout and GitHub preservation inventory

Every row below had empty porcelain output and at least one matching remote branch. Remote branches are exact-SHA matches from `git ls-remote --heads origin`. Branch upstream configuration may differ from preservation refs.

| Checkout | Local branch | Baseline HEAD | Matching GitHub branch |

|---|---|---|---|

| C:\CharityGraph-clean\charitygraph | gate3-cg406-remediation | `940b158ed721f058efec74c34393648adb665ff2` | `gate3-cg406-remediation` |

| C:\CharityGraph-clean\charitygraph-data | docs/gate3-closure-gate4-activation-2026-10-20 | `f5f154cf2e3f107a9a2563c94626a0e39419fd3e` | `decommission-20261103/checkout-3fd2aad06d3d` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.codex-v5rr-worktree | decommission-20261103/worktree-059384875240 | `115d84cfbd745062dbb99ecb8dcb3d64597e8fc8` | `decommission-20261103/checkout-059384875240` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/charitygraph-data | phase5-product-value-canon-2026-09-15 | `112765fd0e2442ca1d6b1eecacd12553a6980348` | `decommission-20261103/checkout-f3e104ce636c` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-attempt10-prelaunch | s0-attempt10-prelaunch | `780285c3679a543a4eb15d4e9ee25baeb655fdf1` | `decommission-20261103/checkout-edc7dd4dcd13` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-attempt9-locator-packet-repair | s0-attempt9-locator-search-packet-repair | `537a365edec461b0da6afabfc82354eeb1deb3b1` | `decommission-20261103/checkout-dfd289e678b1` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-authorisation-builder | scale-s0-product-owner-authorisations | `8262f538ccd1ccfbf289532cd5001e61a3f26a0e` | `decommission-20261103/checkout-6922d27f0030` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-authorisation-data | scale-s0-product-owner-authorisations | `635068e97e78a26423fe3fa17f91594c7b19aa0b` | `decommission-20261103/checkout-a7c8615c41b3` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-canon-builder | (detached) | `4f1ed1724c8e4277bd4d9e5e251833d7d9707fe8` | `decommission-20261103/checkout-115b0f139f2b` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-canon-data | (detached) | `5240337fb8ea3e44dc34ff394f466245689a2075` | `decommission-20261103/checkout-d6e3a42b23f1` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-execution-data | scale-s0-execution | `e92a31fa4e8362eaa85782e12b45ac60cbce61b8` | `decommission-20261103/checkout-9a41b7303a30` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-factory-merge-builder | (detached) | `535d8701cad0236cfe0a679372f770dd092a9697` | `decommission-20261103/checkout-89ad8637effc` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-factory-merge-data | (detached) | `524d98dabf9c8f8c5d05b2d108331f895512d880` | `decommission-20261103/checkout-e7d758f5ffee` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-policy-builder | scale-s0-authorisation-package | `22fa3cf5e8e6be2b7ed7e19ed3dff992009ed4b8` | `decommission-20261103/checkout-75168cc50f9b` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-policy-data | scale-s0-policy-calibration | `155ee65576231ae4ce94a15a29043f17ede8fa5b` | `decommission-20261103/checkout-e54e8faf59c3` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-reconcile-builder | (detached) | `7cede8bddfbd5cc3c83169dfbcccbf83ed777a7c` | `decommission-20261103/checkout-6fce5d58af7c` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-reconcile-data | (detached) | `7148f4cfae4b12d8dbce5a435bd4038a24c50844` | `decommission-20261103/checkout-27fe515216a1` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/bitemporal-governed-knowledge-data-v1 | bitemporal-governed-knowledge-data-v1 | `6113ec85eeac4726cd2b68d606408c2051cae94b` | `bitemporal-governed-knowledge-data-v1` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/bitemporal-governed-knowledge-v1 | bitemporal-governed-knowledge-v1 | `1fd7ecc4d46ba5f4b71813019c143781e5fca123` | `bitemporal-governed-knowledge-v1` |

| C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph | charitygraph-structured-source-and-prose-harvest | `915d82ce6bebc98689a8d2d628d7859c1491cdd8` | `decommission-20261103/checkout-ac3789365914` |

| C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph-data | phase5-direct-service-v1.2-closeout | `12c699ec0ceefdac579e955ac92e0024b9101851` | `decommission-20261103/checkout-37b3111095c0` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph-data/.s0-factory-data | scale-s0-factory-hardening | `e99c761622122fcbca5a21d90e7ee77cca964488` | `decommission-20261103/scale-s0-factory-hardening` |

| C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph-playbooks | review-readiness-2026-09-11 | `f0cd9fe76b9fd402ec53b82210e148feeb984af6` | `review-readiness-2026-09-11` |

| C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph-viewer | review-readiness-2026-09-11 | `d1746e1432e6ba3dc5b81299da97075ecb42ad08` | `decommission-20261103/checkout-d955937233fa` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.s0-factory-builder | scale-s0-factory-hardening | `68574a0b0dcc0985369ce933195a0678c235b555` | `decommission-20261103/scale-s0-factory-hardening` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/phase5-execution-packet | phase5-direct-service-v1.2-cutover-v1 | `3c8049293de8839a4cdc184bd8996382abc5dec1` | `decommission-20261103/phase5-direct-service-v1.2-cutover-v1` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/phase5-semantic-contract-registry | phase5-semantic-contract-registry-v1 | `9dd6f7b4517b17191f08d822a2d3bd131b270493` | `decommission-20261103/phase5-semantic-contract-registry-v1` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/s0-acquisition-bridge-certification-data | scale-s0-execution-identity-certification | `81ad41752432366079736ffa815a9566fb7a9432` | `decommission-20261103/scale-s0-execution-identity-certification` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/s0-acquisition-packet-bridge-builder | scale-s0-execution-identity-binding | `918de807eb557a48cb1d6448b20e1800529671e6` | `decommission-20261103/scale-s0-execution-identity-binding` |

| C:/tmp/c10-normal/charitygraph | (detached) | `49ae6d54910d8001ce08197dd95adf11b5d26f44` | `decommission-20261103/phase5-overnight-specialist-closure` |

| C:/tmp/c10-normal/charitygraph-data | (detached) | `0b1e717c73db7f6162eba9fb3a04ef6091746239` | `decommission-20261103/checkout-d5b0c2cbb193` |

| C:/tmp/cgc9-normal/charitygraph | (detached) | `04da061f43e727ddee59235663909470fec77151` | `decommission-20261103/checkout-f90bb5a14196` |

| C:/CharityGraph-runtime/attempt18-authority-data | s0-attempt18-authority-local | `f733bf2b85fef704528624008fc3faa38d957157` | `decommission-20261103/s0-attempt18-authority-local` |

| C:/CharityGraph-runtime/attempt18-builder | s0-attempt18-locator-body-repair | `fe854c5bcae2ec264cae78a3de7bac32f136f61d` | `decommission-20261103/s0-attempt18-locator-body-repair` |

| C:/CharityGraph-runtime/attempt19-builder | (detached) | `92683f96bc5fbe50e71a82466919380b0293f108` | `decommission-20261103/checkout-7115ddfac0fa` |

| C:/CharityGraph-runtime/attempt20-cert | (detached) | `6f00f222c9991f8f9d7f008d9a6acf1251ca1451` | `decommission-20261103/checkout-6ff89f2ce85c` |

| C:/CharityGraph-runtime/attempt20-data-canonical | (detached) | `18a0b74e87f7dd16403013ec92c8ae35c62c5410` | `s0-attempt20-data-authority-v1` |

| C:/CharityGraph-runtime/attempt20-history-reconcile-20260926 | (detached) | `175b74c7736bd8a038b03aa08253979a6ffdda27` | `s0-attempt20-preauth-stabilisation-repair-v1` |

| C:/CharityGraph-runtime/attempt6-prelive-20260921 | cg-s0-attempt6-timestamp-canonicalization-repair | `065c96dee91d893b61d89b50114a4cdd3237bd1c` | `cg-s0-attempt6-timestamp-canonicalization-repair` |

| C:/CharityGraph-runtime/attempt6-prelive-20260921-data-authority | cg-s0-attempt6-prelive-identity-invalid-record | `f722bf46b5f28edf4fd406c66f91c35218a58ba9` | `cg-s0-attempt6-prelive-identity-invalid-record` |

| C:/CharityGraph-runtime/attempt8-builder-canonical | (detached) | `d4b07799fc6a26ee088cccf8db1295d2e1b1b23e` | `decommission-20261103/checkout-e31a1dfff81b` |

| C:/CharityGraph-runtime/attempt8-data-canonical | (detached) | `6cb3d2839331e1aece99ec3f3f5af2d5d8b1376d` | `decommission-20261103/checkout-0da92078f93a` |

| C:/CharityGraph-runtime/builder-corrective | cg309-builder-corrective | `284fe605370164ad0a5e558dc1536bfa0ec1f413` | `cg306-builder-machinery` |

| C:/CharityGraph-runtime/builder-s0-web-search-sources-accounting-repair | s0-web-search-sources-accounting-repair | `293740420feb73aa985664d9c03120b0841c2052` | `decommission-20261103/s0-web-search-sources-accounting-repair` |

| C:/CharityGraph-runtime/cg-builder-machinery-v1 | spike-10-reconnect-islands-ii-terra-161 | `115f50378f11a161fc9ece9f6f79bc377f9eb065` | `decommission-20261103/checkout-2631301b6bf5` |

| C:/CharityGraph-runtime/cg-data-machinery-v1 | docs-builder-machinery-v1 | `d1c5974b893af8dfe260a7fb4d14bce10a659e6f` | `decommission-20261103/docs-builder-machinery-v1` |

| C:/CharityGraph-runtime/cg-ethos-notability-certification-344-builder | cg-ethos-notability-certification-344-builder | `6cd3624a5fa0bf876f760a2745971d2d041413fc` | `cg-ethos-notability-certification-344-builder` |

| C:/CharityGraph-runtime/cg-ethos-notability-certification-344-data | cg-ethos-notability-certification-344-data | `93a2621e9e1feb492a2f2e00767e1e4a396962b6` | `cg-ethos-notability-certification-344-data` |

| C:/CharityGraph-runtime/cg-ethos-notability-foundations-builder-341 | cg-ethos-notability-reality-corpus-342-builder | `fb1e999eca7d0d2748a5ee5df5e5bdd9b35d80b4` | `cg-ethos-notability-reality-corpus-342-builder` |

| C:/CharityGraph-runtime/cg-ethos-notability-foundations-data-341 | cg-ethos-notability-reality-corpus-342-data | `3ab8b6d405e0d98fba9ca223ce193b6d7f793b07` | `cg-ethos-notability-reality-corpus-342-data` |

| C:/CharityGraph-runtime/cg-f2f-currentness-287 | cg-f2f-currentness-287 | `dccc7ab2440137205893d385a68d72863ca8550c` | `cg-f2f-currentness-287` |

| C:/CharityGraph-runtime/cg-f2f-estimator-disposition-287 | cg-f2f-estimator-disposition-287 | `a7d2e66dfaff48e717491098af629909f589757e` | `cg-f2f-estimator-disposition-287` |

| C:/CharityGraph-runtime/cg-finance-measurement-compatibility-287 | cg-finance-measurement-compatibility-287 | `04e58955dd3c9ed2c2a606123408b4ebf721780c` | `decommission-20261103/finance-compatibility-staged` |

| C:/CharityGraph-runtime/cg-fundability-builder | cg-fundability-f2-builder | `1f9b55c658fbbaa21356b1925e712fd58d455065` | `cg-fundability-f2-builder` |

| C:/CharityGraph-runtime/cg-fundability-data | cg-fundability-f2-data | `9874dc339c30d6b0a64d8ba6bc7ec047e8da5831` | `cg-fundability-f2-data` |

| C:/CharityGraph-runtime/cg-fundability-product-builder | cg-fundability-productisation-301-builder | `04f02c31b5570b3788c7f3848e0cb3abbd02898b` | `cg-fundability-productisation-301-builder` |

| C:/CharityGraph-runtime/cg-fundability-product-data | cg-fundability-productisation-301-data | `2be9feb81465e648babac5481ba705698d56ac43` | `cg-fundability-productisation-301-data` |

| C:/CharityGraph-runtime/cg-fundraising-archaeology-287 | cg-fundraising-archaeology-287 | `a7d47f3f945a00ac3ef93efe7ab2cde8ab418b57` | `cg-fundraising-archaeology-287` |

| C:/CharityGraph-runtime/cg-fundraising-cohort-regression-287 | cg-fundraising-cohort-regression-287 | `26e0b8c72ab623290e8e1b7efb2d3a3c59a0106f` | `cg-fundraising-cohort-regression-287` |

| C:/CharityGraph-runtime/cg-fundraising-publication-288 | cg-fundraising-publication-288 | `ef55a9add5e8827e39d04d1a07750393064a7d13` | `cg-fundraising-publication-288` |

| C:/CharityGraph-runtime/cg-fundraising-t03 | terra/t03-close-second-method-gap | `1704cf0ece42f8433b544967d59ed5e28a0f2714` | `decommission-20261103/terra/t03-close-second-method-gap` |

| C:/CharityGraph-runtime/cg-fundraising-t11-cleanroom | (detached) | `5424296e94dfc679008e300aef214be8aa0e092d` | `decommission-20261103/checkout-267f7ea56a31` |

| C:/CharityGraph-runtime/cg-industry-promotion-287 | cg-industry-promotion-287 | `08ba60c203d70d5b70e4cb305ad3809963904388` | `cg-industry-promotion-287` |

| C:/CharityGraph-runtime/cg-money-attribution-grain-study-287 | cg-money-attribution-grain-study-287 | `50af91b0c988d64ca867bc90de4dadfbafed522f` | `cg-money-attribution-grain-study-287` |

| C:/CharityGraph-runtime/cg-s0-baseline-302 | cg-s0-baseline-reconciliation-302 | `1eabebe7952792c88a436a225098cc94f10349d4` | `cg-s0-baseline-reconciliation-302` |

| C:/CharityGraph-runtime/cg-s0-cleanroom-286-builder | cg-s0-cleanroom-reproducibility-286 | `2ec0e4fbf46c84c0a694b39e84ef430dc37f6666` | `cg-s0-cleanroom-reproducibility-286` |

| C:/CharityGraph-runtime/cg-s0-cleanroom-286-data | (detached) | `191f6140cfd65cc74e70f854e40918e76026cbee` | `decommission-20261103/s0-attempt21-successor-data` |

| C:/CharityGraph-runtime/cg-s0-data-validation-286 | (detached) | `1513648ec358645c23ff49a34769ae91365bf47e` | `decommission-20261103/checkout-680f698cf082` |

| C:/CharityGraph-runtime/cg-s0-locator-identity-286 | cg-s0-locator-identity-286 | `08b499d00b03ee9d10822e3f6ed647c4cbd1cd81` | `cg-s0-locator-identity-286` |

| C:/CharityGraph-runtime/cg-s0-observation-invariants-a1 | cg-s0-observation-invariants-a1 | `99522687fc564086e6e3a5dfb014cbb7f8f9e1ab` | `cg-s0-observation-invariants-a1` |

| C:/CharityGraph-runtime/cg-s0-prelive-blocker-repair-002 | cg-s0-usd-accounting-repair-001 | `c5a4ce32464f831bf616396a8be3859722ef81dc` | `cg-s0-usd-accounting-repair-001` |

| C:/CharityGraph-runtime/cg-s0-typed-relationships-286 | cg-s0-typed-relationships-286 | `9bb0fe3a3e7bb23e5c4313b6629def426bb5bfbf` | `cg-s0-typed-relationships-286` |

| C:/CharityGraph-runtime/cg-s1-readiness-286 | cg-s1-readiness-286 | `1b76c67f773bda6e9b5d84429aa3dd3626e0a186` | `cg-s1-readiness-286` |

| C:/CharityGraph-runtime/cg-semantic-demand-persona-final-curation-327 | cg-semantic-demand-persona-final-curation-327 | `587ee2c23734f82e111de292971c01eddb08bf5a` | `cg-semantic-demand-persona-final-curation-327` |

| C:/CharityGraph-runtime/cg-t02-method-gap | terra/t02-close-highest-method-gap | `dc1c96bfd10f26c304b1c3946cae7e4514893fff` | `decommission-20261103/terra/t02-close-highest-method-gap` |

| C:/CharityGraph-runtime/cg-t08-contradiction-negative-controls | terra/t08-contradiction-negative-controls | `470f7d4b5c932fa9328a7e4091dbbb7128b492c0` | `decommission-20261103/terra/t08-contradiction-negative-controls` |

| C:/CharityGraph-runtime/cg-t10-bounded-real-fundraising-cohort | cg-t10-bounded-real-fundraising-cohort-v2 | `bdb65d3161068695402d545690e06df9ea893617` | `cg-t10-bounded-real-fundraising-cohort-v2` |

| C:/CharityGraph-runtime/cg-t10-cross-section-integrity | terra/t10-cross-section-integrity | `0edd49403c32ff14323793f699729c6a15e67a31` | `decommission-20261103/terra/t10-cross-section-integrity` |

| C:/CharityGraph-runtime/cg-t13-precision-cohort | cg-t13-precision-cohort | `d34a7005d66043bcd0df896199153a851792c98a` | `cg-t13-precision-cohort` |

| C:/CharityGraph-runtime/cg-typed-practice-campaign-provider-contracts-287 | cg-typed-practice-campaign-provider-contracts-287 | `a54d5267d02afb4a0fadb1ed21df57f933cc76bc` | `cg-typed-practice-campaign-provider-contracts-287` |

| C:/CharityGraph-runtime/cg-visible-fundraising-profile-287 | cg-visible-fundraising-profile-287 | `77c0d6c2fb6ccbbbd3dd50d99103ba8c77b726c1` | `cg-visible-fundraising-profile-287` |

| C:/CharityGraph-runtime/cg306/builder | cg306-builder-machinery | `5d983d4f4d683a20561fb4bbb18243e7b740a5f2` | `decommission-20261103/cg306-builder-machinery` |

| C:/CharityGraph-runtime/cg306/data | cg306-data-northstar-v03 | `2c0c865b3d6a1d065dab8fe02da23d445c8b7c44` | `decommission-20261103/cg306-data-northstar-v03` |

| C:/CharityGraph-runtime/cg348-pilot-builder | (detached) | `74689a9a04f2e5ee58fc7303a29157c503495f02` | `decommission-20261103/checkout-c264f44754bc` |

| C:/CharityGraph-runtime/cg348-pilot-data | (detached) | `93a2621e9e1feb492a2f2e00767e1e4a396962b6` | `cg-ethos-notability-certification-344-data` |

| C:/CharityGraph-runtime/cg355-builder | decommission-20261103/worktree-8329233f0d7d | `6cb243baecbdfab1416ad1d529d5c41ddd846fc2` | `decommission-20261103/checkout-8329233f0d7d` |

| C:/CharityGraph-runtime/cg358-builder-audit | (detached) | `5a9ca4e594c8082ea091e717876e1d2013e8f059` | `decommission-20261103/checkout-b007c805ef85` |

| C:/CharityGraph-runtime/cg383-builder | (detached) | `cef02cb80c26ea4c52cd3c4ea97b996023ba686c` | `main` |

| C:/CharityGraph-runtime/cg399-legacy-demand-reconciliation-luna | (detached) | `0f506c38de396bc7a22c610d420e68fe514d4b5c` | `decommission-20261103/checkout-701cd44b1889` |

| C:/CharityGraph-runtime/cg399-legacy-demand-recovery-data | (detached) | `b082d30784494b7d8570edbd5e05da36e040d2c4` | `decommission-20261103/checkout-0a901f5522a4` |

| C:/CharityGraph-runtime/cg401c-builder | (detached) | `cef02cb80c26ea4c52cd3c4ea97b996023ba686c` | `main` |

| C:/CharityGraph-runtime/cg401c-data | (detached) | `443d195abea91d7da111f5e573e90247ae823c36` | `main` |

| C:/CharityGraph-runtime/cg401f-builder | (detached) | `2bfd86d424fd47ec35ae6a97b056cdb448ea3802` | `decommission-20261103/checkout-f90576b9f549` |

| C:/CharityGraph-runtime/cg401f-data | (detached) | `443d195abea91d7da111f5e573e90247ae823c36` | `main` |

| C:/CharityGraph-runtime/cg403-builder | (detached) | `8e76372406fbf08a52beb3aa39ba93fa735b7e8b` | `decommission-20261103/checkout-5aad035e11f3` |

| C:/CharityGraph-runtime/cg403-data | (detached) | `443d195abea91d7da111f5e573e90247ae823c36` | `main` |

| C:/CharityGraph-runtime/data-corrective | cg309-data-corrective | `cf118f425f2edf22e4683caae0db687be7cf641c` | `cg306-data-northstar-v03` |

| C:/CharityGraph-runtime/projection-compatibility-257 | cg-projection-compatibility-257 | `9b3e282cb9aeb06f8f30dc49c58f7f05595835b0` | `cg-projection-compatibility-257` |

| C:/CharityGraph-runtime/projection-compatibility-261-baseline | (detached) | `eedf561a204d14bf235fdc5e322054f036b7fcb0` | `decommission-20261103/checkout-25395c5c3217` |

| C:/CharityGraph-runtime/s0-attempt20-final-authority-rebind-v1 | s0-attempt20-final-authority-rebind-v1 | `baf5e01e4a5ddecdcdd672e33389041a51b24fb5` | `decommission-20261103/s0-attempt20-final-authority-rebind-v1` |

| C:/CharityGraph-runtime/s0-attempt20-final-rebind-builder | (detached) | `9b84b09dcdde0f31ba8662e471d56b514cf6064c` | `decommission-20261103/checkout-4f1e59fb0b33` |

| C:/CharityGraph-runtime/s0-attempt20-final-rebind-data | (detached) | `b991e6180e47c6b3c4c683b7ab2b830df43ea10a` | `decommission-20261103/checkout-3b8f2c0d0e6c` |

| C:/CharityGraph-runtime/s0-attempt21-successor-builder | s0-attempt21-successor-builder | `228066e00bc7dec07a00ddcd45fed07372f0bda7` | `decommission-20261103/s0-attempt21-successor-builder` |

| C:/CharityGraph-runtime/s0-attempt21-successor-data | cg-s0-doc-code-drift-286-terra-t15 | `cfb32b43d4d914d07688bf0d7bd8e9b5c7c2bae3` | `cg-s0-doc-code-drift-286-terra-t15` |

| C:/CharityGraph-runtime/s0-attempt3-preparation-builder | (detached) | `e43ca61a44c250d4baad2c370870d3fdd15639ec` | `decommission-20261103/checkout-41af75657ed6` |

| C:/CharityGraph-runtime/s0-attempt3-preparation-data | (detached) | `e4b938b4825ec859f8134abd030ed4be8eec675c` | `decommission-20261103/checkout-a8e680c3b503` |

| C:/CharityGraph-runtime/s0-attempt4-preparation/builder | (detached) | `ca587fc54eabc683684b95e3f6cda4b2a330e1ee` | `decommission-20261103/checkout-71ec1a0bb681` |

| C:/CharityGraph-runtime/s0-attempt4-preparation/data | (detached) | `e4b938b4825ec859f8134abd030ed4be8eec675c` | `decommission-20261103/checkout-a8e680c3b503` |

| C:/CharityGraph-runtime/s0-attempt7-builder | (detached) | `d4dd962aac2630c48310a89551a03dfa7caf8f7a` | `decommission-20261103/checkout-652ed92fcb73` |

| C:/CharityGraph-runtime/s0-attempt7-data | (detached) | `70e273fa3bdf25188ea4e4ef4959a8def7500bf4` | `decommission-20261103/checkout-26935532f438` |

| C:/CharityGraph-runtime/s0-attempt8-identity-reconciliation-v1 | s0-attempt8-identity-reconciliation-v1 | `7ec3236b07229674017f078b9276505b903800cc` | `decommission-20261103/s0-attempt8-identity-reconciliation-v1` |

| C:/CharityGraph-runtime/s0-identity-lineage-builder | s0-identity-lineage-repair-builder | `abe60fb6ecffddefae8bd2625128271b8124bc74` | `decommission-20261103/s0-identity-lineage-repair-builder` |

| C:/CharityGraph-runtime/s0-identity-lineage-data | s0-identity-lineage-repair-data | `bc1f71ba0715d4a7e671faff5274a043a4ceef71` | `decommission-20261103/s0-identity-lineage-repair-data` |

| C:/CharityGraph-runtime/s0-live-locator-activation-v1-data | s0-live-locator-activation-v1 | `01a7c6fe126cfc58d6bb42c765674d9f27e987ec` | `decommission-20261103/s0-live-locator-activation-v1` |

| C:/CharityGraph-runtime/s0-locator-http-adapter-repair | s0-locator-http-adapter-repair | `54ff44379b798390c9717c26f7b81b37d5177167` | `decommission-20261103/s0-locator-http-adapter-repair` |

| C:/CharityGraph-runtime/s0-locator-subject-population-repair | s0-locator-subject-population-repair-v1 | `b99282613a7ffafccdc95f728e316fd8510ecad2` | `decommission-20261103/s0-locator-subject-population-repair-v1` |

| C:/CharityGraph-runtime/s0-postmerge-data | (detached) | `0f73f399b0d5feeff75b0716fc31da07866b6d14` | `decommission-20261103/checkout-cacedb14f4fe` |

| C:/CharityGraph-runtime/s0-postmerge-main | (detached) | `00d3abb71c03122759a158b15d78abdb89452c69` | `decommission-20261103/checkout-c5831888cae0` |

| C:/CharityGraph-runtime/s0-poststabilisation-builder | s0-poststabilisation-local-repair | `dcbdb41e822cba81cc021f18c631904a84a68560` | `decommission-20261103/s0-poststabilisation-local-repair` |

| C:/CharityGraph-runtime/s0-poststabilisation-data | (detached) | `f4da30d0410e107351f215ea573abdcce264e6f2` | `s0-attempt19-authority` |

| C:/CharityGraph-runtime/s0-runtime-source-authority-repair-v1-builder | s0-runtime-source-authority-repair-v1 | `499d86596be99537418c24292c5fccb56077ca90` | `decommission-20261103/s0-runtime-source-authority-repair-v1` |

| C:/CharityGraph-runtime/s0-runtime-source-authority-repair-v1-data | s0-runtime-source-authority-repair-v1 | `05595755a88c88a4bc209a8c56a66c14d1b847e4` | `decommission-20261103/s0-runtime-source-authority-repair-v1` |

| C:/CharityGraph-runtime/s0-web-locator-builder | s0-web-locator-discovery-repair | `c415172beb7ce1c3251e1b00b7ad054caf610224` | `decommission-20261103/s0-web-locator-discovery-repair` |

| C:/CharityGraph-runtime/s0-web-locator-data | s0-web-locator-discovery-repair | `1668d2a54e5d3f7d06478ebfab7e1ecc5d1d8135` | `decommission-20261103/s0-web-locator-discovery-repair` |

| C:/CharityGraph-runtime/semantic-demand-catalogue-completion | cg-semantic-demand-catalogue-pilot-completion | `2ec8b9e90c1f7dffb7e37d06ca4da77e7b7eb8b6` | `cg-semantic-demand-catalogue-pilot-completion` |

| C:/CharityGraph-runtime/semantic-demand-catalogue-pilot | cg-semantic-demand-catalogue-pilot | `fe3d1ff09c8d0112e2abeb3c4c5aa7399541cf74` | `cg-semantic-demand-catalogue-pilot` |

| C:/CharityGraph-runtime/t03-source-acquisition-cache | terra/t03-source-acquisition-cache | `28c0ef46f54268ef1a548f4b0cc51f70d285bee7` | `decommission-20261103/terra/t03-source-acquisition-cache` |

| C:/CharityGraph-runtime/t04-practice-campaign-provider | t04-practice-campaign-provider | `4b2adfb02838b465b5d1be3f59817522754508d6` | `decommission-20261103/t04-practice-campaign-provider` |

| C:/CharityGraph-runtime/t04-practice-campaign-provider-data | t04-practice-campaign-provider-data | `74d35eab4219dc88069679ba2493a46d6bab5b62` | `decommission-20261103/t04-practice-campaign-provider-data` |

| C:/CharityGraph-runtime/t05-provider-platform-network | terra/t05-provider-platform-network | `8b15adcf59e5d80f67a7ccd479eef2b30ea21056` | `decommission-20261103/terra/t05-provider-platform-network` |

| C:/CharityGraph-runtime/t06-identity-binding-hardening | terra/t06-identity-binding-hardening | `63cc629b17fecc5c3039e24866fcfaec16f187f4` | `decommission-20261103/terra/t06-identity-binding-hardening` |

| C:/CharityGraph-runtime/t06-safe-fundraising-financial-derivatives | terra/t06-enforce-safe-fundraising-financial-derivatives | `88221ceef5302a1cec9d03118b8a9d93aa53a621` | `decommission-20261103/terra/t06-enforce-safe-fundraising-financial-derivatives` |

| C:/CharityGraph-runtime/terra-attempt13-builder | s0-live-boundary-integration-repair-v1 | `529550c36f169e8693311bb084fe238cc89a3e03` | `decommission-20261103/s0-live-boundary-integration-repair-v1` |

| C:/CharityGraph-runtime/terra-fundraising-canonical-vocabulary-v1 | terra/fundraising-canonical-vocabulary-v1 | `741b73081f44b0146f230b6a7c98f84a2afe039c` | `decommission-20261103/terra/fundraising-canonical-vocabulary-v1` |

| C:/CharityGraph-runtime/terra-s0-a3-endtoend-repair-284 | cg-s0-structured-a3-endtoend-repair-284 | `0cf0017552e2a0608cd123ee16849767d7092a78` | `cg-s0-structured-a3-endtoend-repair-284` |

| C:/CharityGraph-runtime/terra-s0-a3-endtoend-repair-286-consolidated | cg-s0-structured-a3-endtoend-repair-286-consolidated | `a0f684ecd94f63dd30221c2aac22ff5dcf78ed2a` | `cg-s0-structured-a3-endtoend-repair-286-consolidated` |

| C:/CharityGraph-runtime/terra-s0-stabilisation | (detached) | `513d5579f8d839b15fbd5f8150b208a4a5af71d2` | `s0-stabilisation-subject-identity` |

| C:/CharityGraph-runtime/terra-s0-structured-authority-repair | terra-s0-structured-authority-repair | `c91f8b99edc66b0b770c3ab8017d7eb15e7e8972` | `decommission-20261103/terra-s0-structured-authority-repair` |

| C:/CharityGraph-runtime/terra-t04-temporal-method-history | terra/t04-temporal-method-history | `4ecb3f67916616b01b18d9aa449e92af6e7184d1` | `decommission-20261103/terra/t04-temporal-method-history` |

| C:/CharityGraph-runtime/terra-t06-multiyear-fundraising-finance | terra/t06-multiyear-fundraising-finance | `9cdc84c29dae09edeada7cabf4742a950e73c655` | `decommission-20261103/terra/t06-multiyear-fundraising-finance` |

| C:/CharityGraph-runtime/terra-t07-evidence-dedup-conflict | terra/t07-evidence-dedup-conflict | `ecc9dff1185f4d875d234b3ac5fc6ef9fcd25fb8` | `decommission-20261103/terra/t07-evidence-dedup-conflict` |

| C:/CharityGraph-runtime/terra-t07-industry-promotion | terra/t07-govern-industry-source-promotion-paths | `05a28f42f127d6ff35ed1291ad21628410f8ba42` | `decommission-20261103/terra/t07-govern-industry-source-promotion-paths` |

| C:/CharityGraph-runtime/terra-t07-practice-campaign-provider | terra/t07-practice-campaign-provider-disambiguation | `9e1ab701c3a72ac153a7e8bd665c20738403062f` | `decommission-20261103/terra/t07-practice-campaign-provider-disambiguation` |

| C:/CharityGraph-runtime/terra-t08-migrate-legacy-fundraising-observation | terra/t08-migrate-legacy-fundraising-observation | `cb1ca40a07c5f7183944d0bc1c165039415f4f95` | `decommission-20261103/terra/t08-migrate-legacy-fundraising-observation` |

| C:/CharityGraph-runtime/terra-t09-integrate-visible-fundraising-card-api | terra/t09-integrate-visible-fundraising-card-api | `9ebe417e6d2dd7f79acbe86f0546bdd763387301` | `decommission-20261103/terra/t09-integrate-visible-fundraising-card-api` |

| C:/CharityGraph-runtime/terra-t09-user-question-regression | terra/t09-user-question-regression | `d0a4f5d12c57fa82a0eca99601f41927eddc6c41` | `charitygraph-structured-source-and-prose-harvest` |

| C:/CharityGraph-runtime/terra-t09-user-question-regression-clean | terra/t09-user-question-regression-clean | `a0590c86abdc54110218805306be53db7db5a21d` | `decommission-20261103/terra/t09-user-question-regression-clean` |

| C:/CharityGraph-runtime/terra-t23-runtime-robustness | cg-s0-t23-runtime-robustness-286 | `0df408d9d0edc277644eba7f42cfa7c94e984735` | `cg-s0-t23-runtime-robustness-286` |

| C:/CharityGraph-runtime/terra-t24-failure-injection | cg-s0-t24-failure-injection-286 | `bff6e099435d275ed0882780bf6a50a71ba3bbdc` | `cg-s0-t24-failure-injection-286` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg316-data-reconciliation | cg316-data-reconciliation | `c9ad8f62d6ab8e68b4722124825c2bb200537cc7` | `cg316-data-reconciliation` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg345-builder | decommission-20261103/worktree-75ca0ecf1a71 | `308a6d2c439797d6a35f0558a026af94c4321b61` | `decommission-20261103/checkout-75ca0ecf1a71` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg345-data | decommission-20261103/worktree-5df4170c3958 | `e45045593322e5e361c607e72880fcffe21c4704` | `decommission-20261103/checkout-5df4170c3958` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg385-builder | decommission-20261103/worktree-240256173467 | `1f4d285845f0ff9d3c6e735b36d84007aae12062` | `decommission-20261103/checkout-240256173467` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg385-builder/.cg386-builder | (detached) | `ccf8f32281c7dcd630df9ce880228562c0cdad5c` | `decommission-20261103/checkout-fae39fa791a1` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.cg398-data-clean | (detached) | `4e86109167693427ac96afe6a45a491230f4a954` | `decommission-20261103/checkout-a1ccab4e5f8a` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.northstar-gap-audit-286 | cg-s0-northstar-gap-audit-286 | `2fd804dd5b4ca3be48c12ab0a19813f043c83575` | `cg-s0-northstar-gap-audit-286` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/cg399-semantic | cg399-semantic-canonical | `fcdd01256eac54384b843fc65b714754950d7eda` | `cg399-semantic-canonical` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/fundability-recert-builder-303 | cg-fundability-recertification-303-builder | `7de942f4f60f1b82170ffa85d2c14e6cddbd6912` | `cg-fundability-recertification-303-builder` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/fundability-recert-data-303 | cg-fundability-recertification-303-data | `0a02166450081e863b6e2028de0c8ce7e9c0898b` | `cg-fundability-recertification-303-data` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/phase5-north-star-builder | phase5-north-star-completion-v1 | `f247c8c68ff6dcf4424df641eabe70a0cad6fd68` | `decommission-20261103/phase5-north-star-completion-v1` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/phase5-north-star-data | phase5-north-star-completion-v1 | `2919f329eb054347a79081ef7b35a11ae8ebaf9a` | `decommission-20261103/phase5-north-star-completion-v1` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/semantic-demand-builder-324 | cg-semantic-demand-corrections-324 | `7d4626e9f705b650687c864f47ec77d0b7b03b5e` | `cg-semantic-demand-corrections-324` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/semantic-demand-builder-325 | cg-semantic-demand-corrections-326-terra | `e0119d581fa21f0148ef8b804611825678968e9e` | `cg-semantic-demand-corrections-326-terra` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/semantic-demand-data-324 | cg-semantic-demand-corrections-324 | `e6ed78c81d46a7668dc55d8880a7fb778a66e061` | `cg-semantic-demand-corrections-324` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/semantic-demand-data-325 | cg-semantic-demand-corrections-326-terra | `0b15014e7363a31e82a1682f597b11d7ef2af831` | `cg-semantic-demand-corrections-326-terra` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/source-universe-builder | cg-source-universe-v1-publication | `88cee017ad3ec4073f68f219c71e6db634110e17` | `cg-source-universe-v1-publication` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.publish-worktrees/source-universe-data | cg-source-universe-v1-publication | `f0c12c9fabfd62fc714cc32520b0320152a7fc21` | `cg-source-universe-v1-publication` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-orchestration-runtime-v1 | s0-orchestration-runtime-v1 | `5dffdccd09cc8fccfba6d999a149abb203c1a699` | `decommission-20261103/checkout-65051bb284d7` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-orchestration-runtime-v1/.s0-provider-boundary-a1 | terra-s0-provider-boundary-a1 | `a5526fce88ef60e8d677b7504d1daeaa05c294e8` | `decommission-20261103/terra-s0-provider-boundary-a1` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/cg346-empirical-builder | decommission-20261103/worktree-666a9b1507aa | `315a6a0d1fe4c33fc0d71d198c705ee83dbe965b` | `decommission-20261103/checkout-666a9b1507aa` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/cg346-empirical-data | (detached) | `91d3c13a4e5d165ea78f21a3a828de6fb8eacdd5` | `decommission-20261103/checkout-98d37c836ac2` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph-data/.campaign-data | phase5-overnight-specialist-closure | `349860de83364d2adf17750a090d9e34d69e6004` | `decommission-20261103/phase5-overnight-specialist-closure` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph-t09-finance-extraction | terra/t09-finance-extraction-normalisation | `89bec488d5ee33697c5068e177102d142dd9d557` | `decommission-20261103/terra/t09-finance-extraction-normalisation` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.campaign-builder | phase5-overnight-specialist-closure | `49ae6d54910d8001ce08197dd95adf11b5d26f44` | `decommission-20261103/phase5-overnight-specialist-closure` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.s0-owner-attestation-builder | cg-s0-owner-attestation-binding-repair-001 | `c6d7c5dbccfbc3403b6074ef6a5f8ebe440c0590` | `cg-s0-owner-attestation-binding-repair-001` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.t06-fundraising-vocabulary | cg-fundraising-vocabulary-crosswalk-287 | `18d89958913313b286e9460b63691433241de4fd` | `cg-fundraising-vocabulary-crosswalk-287` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.t08-typed-money-scope-linkage | terra/t08-typed-money-scope-linkage | `bda2a7cc48c10aad9eaab13d89d99794e6de3db0` | `decommission-20261103/terra/t08-typed-money-scope-linkage` |

| C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.t09-safe-derived-financial-metrics | terra/t09-safe-derived-financial-metrics | `0aede0cd03176f77b86b7f644f21c085c3548550` | `decommission-20261103/terra/t09-safe-derived-financial-metrics` |

| C:/tmp/cgc9-normal/charitygraph-data | (detached) | `294ef7ba1ada14125f2fb815afd2c8d153cf4471` | `decommission-20261103/checkout-39bb0d431767` |

| C:/tmp/charitygraph-brand-reuse-builder | charitygraph-brand-reuse-builder | `2b5a30041ce0123b34c2e2919c5cd12d9ba32c3a` | `charitygraph-brand-reuse-builder` |

| C:/tmp/charitygraph-brand-reuse-data | charitygraph-brand-reuse-data | `2044e28efa90a0b0a1518d89a82773199f84ad63` | `charitygraph-brand-reuse-data` |

| C:/tmp/charitygraph-brand-reuse-viewer | charitygraph-brand-reuse-viewer | `4502871e3764852f0587e7b9965409f6b6b341ae` | `charitygraph-brand-reuse-viewer` |

| C:/tmp/charitygraph-native-lifecycle-harness | charitygraph-native-v5rr-overlay-lifecycle | `0366c625c427470ff6917b2eb31381fea9913c9c` | `charitygraph-native-v5rr-overlay-lifecycle` |

| C:/tmp/charitygraph-native-v4-faceted-disposition | charitygraph-native-v4-faceted-disposition | `12c5e7fa8841a0bd599e49b6d91d54758a845998` | `charitygraph-native-v4-faceted-disposition` |

| C:/tmp/charitygraph-native-v4r-faceted-disposition-repair | charitygraph-native-v4r-faceted-disposition-repair | `9eb2f4210b4861f967f364495e57ee839113c6c3` | `charitygraph-native-v4r-faceted-disposition-repair` |

| C:/tmp/charitygraph-phase3-integrated-card-closeout | phase5-top100-factory-preflight-v1 | `4f53a8a83555a6d7c01faa5a44c16f2dfb8012ba` | `decommission-20261103/phase5-top100-factory-preflight-v1` |

| C:/tmp/charitygraph-phase3-relationship-role-proof | charitygraph-phase3-relationship-role-proof | `72a3918b89235c98558e3123eed989256d59bf1c` | `charitygraph-phase3-relationship-role-proof` |

| C:/tmp/charitygraph-phase5-top100-baseline-corpus | phase5-real-provider-dry-run-v1 | `697c1130a0d3972abf77fea8c6ce4d439e697d15` | `decommission-20261103/phase5-real-provider-dry-run-v1` |

| C:/tmp/charitygraph-semantic-lab-docs | charitygraph-native-induction-v1 | `3db9c9b61d2833a31042295e609eb0a4625faf84` | `charitygraph-native-induction-v1` |

| C:/tmp/charitygraph-v5 | charitygraph-native-v5-overlay-lifecycle | `875727141c076b943a6bc13846c56ad2a0f1ade9` | `charitygraph-native-v5-overlay-lifecycle` |

| C:/tmp/charitygraph-v5r | charitygraph-native-v5r-overlay-quality-lifecycle | `df5033ae982e2df185c94ab078826f22dec811d2` | `charitygraph-native-v5r-overlay-quality-lifecycle` |

| C:/tmp/charitygraph-v5rr | charitygraph-native-v5rr-executable-lifecycle | `2a7110554bee56829b294b2d423ac477e59d8780` | `charitygraph-native-v5rr-executable-lifecycle` |

| C:\CharityGraph-runtime\.s0-policy-data | s0-runtime-source-authority-repair-v1 | `05595755a88c88a4bc209a8c56a66c14d1b847e4` | `decommission-20261103/s0-runtime-source-authority-repair-v1` |

| C:\CharityGraph-runtime\charitygraph-data | s0-runtime-source-authority-repair-v1 | `05595755a88c88a4bc209a8c56a66c14d1b847e4` | `decommission-20261103/s0-runtime-source-authority-repair-v1` |

| C:\CharityGraph-runtime\g4-doc-review-65c7e086a5c64a34950cb33ce5588c7a | gate3-cg406-remediation | `f4d4bff98a1264f91ced565ae9320d9b8f67f900` | `decommission-20261103/checkout-c4dc0fb07a52` |

## Windows scan warnings (verification limits)

### C:\CharityGraph-clean\charitygraph

```text
warning: could not open directory 'CharityGraph-runtimecg405-pytest/': Permission denied
```

### C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-authorisation-builder

```text
warning: could not open directory '.pytest-merge-review/': Permission denied
warning: could not open directory '.pytest-s0-full/': Permission denied
warning: could not open directory '.pytest-s0-wire/': Permission denied
```

### C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph

```text
warning: could not open directory '.test-owner-attestation/': Permission denied
warning: could not open directory '.test-owner-attestation-accept/': Permission denied
warning: could not open directory '.test-owner-attestation-accept-2/': Permission denied
warning: could not open directory '.test-owner-attestation-accept-3/': Permission denied
warning: could not open directory '.test-owner-attestation-final/': Permission denied
warning: could not open directory '.test-owner-attestation-final-accept/': Permission denied
warning: could not open directory '.test-owner-attestation-final-accept-2/': Permission denied
warning: could not open directory '.test-owner-attestation-full/': Permission denied
warning: could not open directory '.test-owner-attestation-independent/': Permission denied
warning: could not open directory '.test-owner-attestation-literal/': Permission denied
warning: could not open directory '.test-owner-attestation-rerun/': Permission denied
warning: could not open directory '.test-owner-attestation-runtime/': Permission denied
warning: could not open directory '.test-owner-attestation-runtime-current/': Permission denied
warning: could not open directory '.test-owner-attestation-runtime-verify/': Permission denied
warning: could not open directory '.test-owner-attestation-s0/': Permission denied
warning: could not open directory '.test-owner-attestation-s0-green/': Permission denied
warning: could not open directory '.test-runtime-independent/': Permission denied
warning: could not open directory '.test-t06-vocab/': Permission denied
warning: could not open directory '.pytest-t09/': Permission denied
warning: could not open directory '.pytest-t09-rerun/': Permission denied
```

### C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph-viewer

```text
warning: could not open directory '.pytest_cache/': Permission denied
```

### C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/phase5-execution-packet

```text
warning: could not open directory '.pytest-temp-final2/': Permission denied
warning: could not open directory '.pytest-temp-transport/': Permission denied
```

### C:/CharityGraph-runtime/cg-finance-measurement-compatibility-287

```text
warning: could not open directory '.pytest-work/': Permission denied
warning: could not open directory '.pytest-work-2/': Permission denied
```

### C:/CharityGraph-runtime/cg-s0-cleanroom-286-builder

```text
warning: could not open directory '.pytest-tmp-burn/': Permission denied
warning: could not open directory '.pytest-tmp-burn-final/': Permission denied
warning: could not open directory '.pytest-tmp-lineage/': Permission denied
```

### C:/CharityGraph-runtime/cg-s0-locator-identity-286

```text
warning: could not open directory '.pytest-t18/': Permission denied
warning: could not open directory '.pytest-t18-final/': Permission denied
warning: could not open directory '.pytest-t18-runtime/': Permission denied
```

### C:/CharityGraph-runtime/cg-s0-observation-invariants-a1

```text
warning: could not open directory '.pytest-t19/': Permission denied
warning: could not open directory '.pytest-t19-2/': Permission denied
warning: could not open directory '.pytest-t19-3/': Permission denied
```

### C:/CharityGraph-runtime/cg-s0-prelive-blocker-repair-002

```text
warning: could not open directory '.pytest-currency/': Permission denied
warning: could not open directory '.pytest-final/': Permission denied
warning: could not open directory '.pytest-full/': Permission denied
warning: could not open directory '.pytest-full2/': Permission denied
```

### C:/CharityGraph-runtime/cg-s0-typed-relationships-286

```text
warning: could not open directory '.pytest-typed-relationships/': Permission denied
warning: could not open directory '.pytest-typed-relationships-final/': Permission denied
warning: could not open directory '.pytest-typed-relationships-final2/': Permission denied
warning: could not open directory '.pytest-typed-relationships-full/': Permission denied
warning: could not open directory '.pytest-typed-relationships-repair/': Permission denied
warning: could not open directory '.pytest-typed-relationships-repair2/': Permission denied
warning: could not open directory '.pytest-typed-relationships-suite/': Permission denied
warning: could not open directory '.pytest-typed-relationships-suite2/': Permission denied
```

### C:/CharityGraph-runtime/cg-t13-precision-cohort

```text
warning: could not open directory '.pytest-t13/': Permission denied
```

### C:/CharityGraph-runtime/cg-typed-practice-campaign-provider-contracts-287

```text
warning: could not open directory '.pytest-worktree/': Permission denied
warning: could not open directory '.pytest-worktree-2/': Permission denied
```

### C:/CharityGraph-runtime/cg348-pilot-builder

```text
warning: could not open directory '.pytest-cg348/': Permission denied
```

### C:/CharityGraph-runtime/cg355-builder

```text
warning: could not open directory '.pytest-cg355/': Permission denied
warning: could not open directory '.pytest-cg355-final/': Permission denied
```

### C:/CharityGraph-runtime/s0-locator-subject-population-repair

```text
warning: could not open directory '.pytest-tmp-run1/': Permission denied
warning: could not open directory '.pytest-tmp-run2/': Permission denied
warning: could not open directory '.pytest-tmp-run3/': Permission denied
```

### C:/CharityGraph-runtime/s0-runtime-source-authority-repair-v1-builder

```text
warning: could not open directory '.pytest-cert-current/': Permission denied
warning: could not open directory '.pytest-cert-final/': Permission denied
warning: could not open directory '.pytest-full-authority/': Permission denied
warning: could not open directory '.pytest-review-control-plane-20260921/': Permission denied
warning: could not open directory '.pytest-review-control-plane-20260921-rerun/': Permission denied
warning: could not open directory '.pytest-review-fixture-rerun-20260921/': Permission denied
warning: could not open directory '.pytest-review-focused-20260921/': Permission denied
warning: could not open directory '.pytest-review-focused-final-20260921/': Permission denied
warning: could not open directory '.pytest-review-full-20260921/': Permission denied
warning: could not open directory '.pytest-review-lastfailed-20260921/': Permission denied
warning: could not open directory '.pytest-s0-authority/': Permission denied
```

### C:/CharityGraph-runtime/t04-practice-campaign-provider

```text
warning: could not open directory '.pytest-tmp/': Permission denied
warning: could not open directory '.pytest-tmp-final/': Permission denied
```

### C:/CharityGraph-runtime/terra-fundraising-canonical-vocabulary-v1

```text
warning: could not open directory '.pytest-canonical-v1/': Permission denied
```

### C:/CharityGraph-runtime/terra-s0-a3-endtoend-repair-284

```text
warning: could not open directory '.pytest-286/': Permission denied
warning: could not open directory '.pytest-286-cert/': Permission denied
warning: could not open directory '.pytest-286-crossrepo/': Permission denied
warning: could not open directory '.pytest-286-crossrepo-auth/': Permission denied
warning: could not open directory '.pytest-286-crossrepo-auth-fixed/': Permission denied
warning: could not open directory '.pytest-286-crossrepo-canonical/': Permission denied
warning: could not open directory '.pytest-286-crossrepo-first/': Permission denied
warning: could not open directory '.pytest-286-crossrepo-full/': Permission denied
warning: could not open directory '.pytest-286-crossrepo-full-final/': Permission denied
warning: could not open directory '.pytest-286-crossrepo-full-fixed/': Permission denied
warning: could not open directory '.pytest-286-crossrepo-last/': Permission denied
warning: could not open directory '.pytest-286-lineage/': Permission denied
```

### C:/CharityGraph-runtime/terra-s0-stabilisation

```text
warning: could not open directory '.pytest-lifecycle/': Permission denied
warning: could not open directory '.pytest-migration-26/': Permission denied
warning: could not open directory '.pytest-migrations/': Permission denied
warning: could not open directory '.pytest-one/': Permission denied
warning: could not open directory '.pytest-root-a/': Permission denied
warning: could not open directory '.pytest-root-b/': Permission denied
warning: could not open directory '.pytest-root-c/': Permission denied
warning: could not open directory '.pytest-root-d/': Permission denied
warning: could not open directory '.pytest-runtime-a/': Permission denied
warning: could not open directory '.pytest-runtime-b/': Permission denied
warning: could not open directory '.pytest-runtime-final-a/': Permission denied
warning: could not open directory '.pytest-runtime-final-b/': Permission denied
warning: could not open directory '.pytest-runtime-final-c/': Permission denied
warning: could not open directory '.pytest-s0-full/': Permission denied
warning: could not open directory '.pytest-s0-policy/': Permission denied
warning: could not open directory '.pytest-s0-regression/': Permission denied
warning: could not open directory '.pytest-s0-repair/': Permission denied
warning: could not open directory '.pytest-terra-s0/': Permission denied
```

### C:/CharityGraph-runtime/terra-t07-industry-promotion

```text
warning: could not open directory '.pytest-local/': Permission denied
```

### C:/CharityGraph-runtime/terra-t07-practice-campaign-provider

```text
warning: could not open directory '.pytest-base/': Permission denied
warning: could not open directory 'CharityGraph-runtimeterra-t07-practice-campaign-provider.pytest-cache/': Permission denied
warning: could not open directory 'CharityGraph-runtimeterra-t07-practice-campaign-provider.pytest-tmp/': Permission denied
```

### C:/CharityGraph-runtime/terra-t24-failure-injection

```text
warning: could not open directory '.pytest-t24-authority/': Permission denied
warning: could not open directory '.pytest-t24-final/': Permission denied
warning: could not open directory '.pytest-t24-lifecycle/': Permission denied
```

### C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-orchestration-runtime-v1

```text
warning: could not open directory '.run-provider-boundary-final-proof/': Permission denied
warning: could not open directory '.run-provider-boundary-proof/': Permission denied
warning: could not open directory '.run-provider-boundary-pytest/': Permission denied
warning: could not open directory '.run-provider-boundary-pytest-2/': Permission denied
warning: could not open directory '.run-provider-boundary-pytest-3/': Permission denied
warning: could not open directory '.run-provider-boundary-pytest-4/': Permission denied
```

### C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/.s0-orchestration-runtime-v1/.s0-provider-boundary-a1

```text
warning: could not open directory '.run-provider-boundary-final-proof/': Permission denied
warning: could not open directory '.run-provider-boundary-proof/': Permission denied
warning: could not open directory '.run-provider-boundary-pytest/': Permission denied
warning: could not open directory '.run-provider-boundary-pytest-2/': Permission denied
warning: could not open directory '.run-provider-boundary-pytest-3/': Permission denied
warning: could not open directory '.run-provider-boundary-pytest-4/': Permission denied
```

### C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/cg346-empirical-builder

```text
warning: could not open directory '.pytest-tmp/': Permission denied
warning: could not open directory '.pytest-tmp-cg351/': Permission denied
warning: could not open directory '.pytest-tmp-cg351-run/': Permission denied
warning: could not open directory '.pytest-tmp-cg351-run2/': Permission denied
warning: could not open directory '.pytest-tmp-cg351-run3/': Permission denied
warning: could not open directory '.pytest-tmp-cg351-run4/': Permission denied
warning: could not open directory '.pytest-tmp-cg351-run5/': Permission denied
warning: could not open directory '.pytest-tmp-cg351-run6/': Permission denied
warning: could not open directory '.pytest-tmp-cg351-run7/': Permission denied
warning: could not open directory '.pytest-tmp-cg351-run8/': Permission denied
warning: could not open directory '.pytest-tmp-cg354/': Permission denied
warning: could not open directory '.pytest-tmp-cg354-final/': Permission denied
warning: could not open directory '.pytest-tmp-cg359/': Permission denied
warning: could not open directory '.pytest-tmp-cg360/': Permission denied
warning: could not open directory '.pytest-tmp-cg360-completeness/': Permission denied
warning: could not open directory '.pytest-tmp-cg360-local/': Permission denied
warning: could not open directory '.pytest-tmp-cg360-run/': Permission denied
warning: could not open directory '.pytest-tmp-cg360-t07/': Permission denied
warning: could not open directory '.pytest-tmp-cg360-verify/': Permission denied
```

### C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph-t09-finance-extraction

```text
warning: could not open directory '.pytest-t09-full/': Permission denied
```

### C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.s0-owner-attestation-builder

```text
warning: could not open directory '.test-owner-attestation/': Permission denied
warning: could not open directory '.test-owner-attestation-accept/': Permission denied
warning: could not open directory '.test-owner-attestation-accept-2/': Permission denied
warning: could not open directory '.test-owner-attestation-accept-3/': Permission denied
warning: could not open directory '.test-owner-attestation-final/': Permission denied
warning: could not open directory '.test-owner-attestation-final-accept/': Permission denied
warning: could not open directory '.test-owner-attestation-final-accept-2/': Permission denied
warning: could not open directory '.test-owner-attestation-full/': Permission denied
warning: could not open directory '.test-owner-attestation-independent/': Permission denied
warning: could not open directory '.test-owner-attestation-literal/': Permission denied
warning: could not open directory '.test-owner-attestation-rerun/': Permission denied
warning: could not open directory '.test-owner-attestation-runtime/': Permission denied
warning: could not open directory '.test-owner-attestation-runtime-current/': Permission denied
warning: could not open directory '.test-owner-attestation-runtime-verify/': Permission denied
warning: could not open directory '.test-owner-attestation-s0/': Permission denied
warning: could not open directory '.test-owner-attestation-s0-green/': Permission denied
warning: could not open directory '.test-runtime-independent/': Permission denied
```

### C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.t06-fundraising-vocabulary

```text
warning: could not open directory '.test-t06-vocab/': Permission denied
```

### C:/Users/grego/OneDrive/Documents/GitHub/CharityGraph/charitygraph/.t09-safe-derived-financial-metrics

```text
warning: could not open directory '.pytest-t09/': Permission denied
warning: could not open directory '.pytest-t09-rerun/': Permission denied
```

## VS Code startup shutdown correction
A subsequent VS Code folder open launched the legacy watcher from the outer workspace `.vscode/tasks.json`. Watcher PID 14692 and child Codex PID 19260 were terminated. Removed the CharityGraph Bridge task from both the outer OneDrive workspace and the primary clean checkout. Set VS Code user `task.allowAutomaticTasks` to `off`. The earlier shutdown had missed these folder-open tasks. Keep these launch tasks removed when merging historical branches.
