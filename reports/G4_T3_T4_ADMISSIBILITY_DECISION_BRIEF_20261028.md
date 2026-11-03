# Gate 4 T3/T4 admissibility and decision brief

Date: 2026-10-28 (Australia/Sydney)  
Target: `gate3-cg406-remediation@700cfe1f4e576e00471155a6bfedbcc40fc36cab`  
Fence: v43  
Mode: local, read-only, no-send

## Decision

**T3: `STOP / DECISION_REQUIRED`.** The recovered material contains useful,
hash-verified, ACNC-bound candidate lineage, but no candidate is yet admissible
for a governed T3 task. The inspected evidence has zero created rights
decisions, no trusted provider authorisation, and no candidate-specific current
v29 projection row. Scope must also be bound explicitly; a preparation
`instance_id` is not a governed scope.

**T4A: `PLAN_ONLY / NO-SEND`.** A no-send plan can be specified, but cannot be
accepted as executable until the T3 manifest, exact task contract and route
identities are frozen.

**T4B: `STOP`.** No provider/model crossing is authorised. Gate 4 remains
active and unearned. This brief does not select or freeze a cohort, create a
rights decision, reserve spend, promote knowledge, publish, release, or close
any gate.

## Authority and evidence boundary

The governing reading was `AGENTS.md`, `BUILDER_MACHINERY.md`, the v0.3 North
Star, Data `DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, `IMPLEMENTATION_PLAN.md`,
`TEST_PLAN.md`, `COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`,
`INTEGRATED_PRODUCT_AND_DATA_MODEL.md`,
`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`,
`TAXONOMY_AND_SCHEME_GOVERNANCE.md`, the local Gate 4 scorecard,
`G4_T2_T3_T4_SUPERVISORY_PLAN_20261028.md`, and
`G4_T2_CLEAN_BASELINE_VERIFICATION_20261028.md`.

The applicable rules are:

- Source Universe v1 is closed to exactly `acnc_register`, `acnc_ais_bundle`,
  `ato_abr_dgr`, `official_website`, `annual_report`,
  `wikipedia_wikimedia`, and `pfra`. No discovery or new source family is
  permitted.
- Subject, scope, source record, source artifact, representation, observation,
  rights, coverage and public projection are separate states. Public
  accessibility is not provider or redistribution permission.
- Every content-bearing provider input needs an exact representation-bound
  rights decision, separate local-retention and provider-processing axes, and
  an exact source/acquisition lineage. Model output remains candidate material
  until governed review and promotion.
- Coverage must distinguish unavailable, not acquired, source silent, not
  processed, failed, not reviewed, unknown, withheld and stale. Sparse output
  is not success.

The T2 baseline is authoritative for this checkout: there is no pristine T2
execution surface here, and the quarantined T2 prototype paths remain
untouched and inadmissible. The clean v29 rights-record/projection machinery
is a reusable substrate, not proof that these recovered candidates have
current v29 rows.

## Recovery inventory and manifest alternatives

The frozen recovery summary at
`evidence/gate3-fresh36-bounded-recovery-v1/recovery-status.json` records:

- selection manifest SHA-256
  `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`;
- 36 frozen identities, 224 hash-verified member references and 189 unique
  source objects;
- 74 contemporaneous reused matches, 149 successor acquisition receipts and
  one unresolved original receipt lineage;
- family references: 36 ACNC register, 36 AIS, 36 ABR/DGR, 28 annual reports,
  20 official websites, 36 PFRA and 32 Wikimedia;
- zero provider calls, zero request bodies compiled, zero rights decisions,
  and `trusted_authorization_obtained: false`.

The following are alternatives, not one merged count:

1. The bounded-recovery packet above is the strongest identity/receipt/source
   lineage alternative. Its exact source objects are present and hash matched,
   but its rights stop reason is explicit.
2. The local runtime `g3-fresh-36-v15/source-universe` acquisition and
   representation ledgers contain 182 rows each. They are a different ledger
   projection and must not be silently merged with the 224 recovery member
   references.
3. The Builder-preparation packet has 36 corpus identities and a 252-row
   provider-corpus admission ledger. It records mechanically admitted rows,
   but also `subject_not_bound` and unavailable states; it is not the recovery
   manifest and does not supply rights decisions.
4. The historical semantic-execution-v1 manifest has 36 packets and 120
   candidate evidence objects, but zero rights-approved objects and zero
   issued requests. Its default-deny result is evidence of a blocked attempt,
   not T3 approval.

No source bytes, prompts, model responses, credentials or protected personal
data are reproduced here.

## Provisional candidate-admissibility matrix

These five rows are a **review shortlist only**, not a cohort selection. Each
has an exact ABN/ACNC-bound subject, admitted ACNC register and AIS lineage,
hash-verified source objects, and a recovered acquisition receipt. For these
source-native records, the observed representation hash is the source-object
SHA; a separate representation-artifact ID was not observed. `scope_id`, a
current v29 row, and rights authority remain missing.

| ABN / subject | Bound source record and artifact; acquisition receipt | Observed source-native representation hash | Scope / v29 / rights state | Provisional disposition |
|---|---|---|---|---|
| `52000399744` / `subject:02649cdcb42049bb8dedd30f2333e150` | `acnc_register`: `srcrec:4978c7ff7f9694d9d9d6db9ad871a8048cde5940c6e699a2dd4bd15360bcd28d`; `srcblob:f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2`; `acq:0b099288968c5ac89fc4bff0811f021787281fb38737565221c506123098b63e`. `acnc_ais_bundle`: `srcrec:554fa9df1414f0096b9035fea5ac5eee7ffb59e46eb767d6306d40d8f326f08a`; `srcblob:70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b`; `acq:e094f723f29b2d0394805ee00d0c1f5cdce483d96c2dee14ca7ea4c1da69eac4`. | Register: `f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2`. AIS: `70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b`. | Scope `NOT_OBSERVED`; v29 current row `NOT_OBSERVED`; local/provider rights `NOT_ASSESSED`. | `HOLD — DECISION_REQUIRED` |
| `26164251245` / `subject:0889b4decb854e71ab4784479ca95c03` | Register: `srcrec:f05f137023221378d486eef96e0c4efe377bb4811ac63fbbbb9aa8f103c251d2`; `srcblob:8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773`; `acq:fbb55f0fb70eecd14aa98017f1fc4b458c2522adde0c79a03237ac76e11ad05b`. AIS: `srcrec:045161751edf9950655698373906590d67abf2c35ba33dd804b61b3ac95237f8`; `srcblob:ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33`; `acq:c60f2a53e31086b4dfab8fbced7e1b0718a64e6694f8dcd6cd93eaffc2ef1c09`. | Register: `8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773`. AIS: `ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33`. | Scope `NOT_OBSERVED`; v29 current row `NOT_OBSERVED`; local/provider rights `NOT_ASSESSED`. | `HOLD — DECISION_REQUIRED` |
| `52404606134` / `subject:16fba76fde2242d5870835b18b4e8b8d` | Register: `srcrec:188a391cee048ab2fa7720aeb2c58f5b1e025039ef674ef8a6fd6ea0ab91dd8a`; `srcblob:ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c`; `acq:8cbf097d3ca6a8a0282158d7980d965b9b715886d01d9146b41ebc57c4115637`. AIS: `srcrec:5cc396995aea23edbab90c78b47101651f3a085f34ab088417dc3e1caa6fda25`; `srcblob:9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678`; `acq:0d954180bc7c8e26f48f1788164c9b2c900d7bcc43cff8d043944e68bd99bc18`. | Register: `ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c`. AIS: `9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678`. | Scope `NOT_OBSERVED`; v29 current row `NOT_OBSERVED`; local/provider rights `NOT_ASSESSED`. | `HOLD — DECISION_REQUIRED` |
| `33107782196` / `subject:1823309bdd06417c9928033603cb6e39` | Register: `srcrec:5e1c9ac1b0378a22557a9bf804697719133663123e7f603d76eb41fd2601adf4`; `srcblob:1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6`; `acq:fc6227ca5e16e8232088ef98cac3089927b208c3b35e236958dac9171a6bf960`. AIS: `srcrec:e94d13fec302f9cefc42569b4d191dae5b360565c8c3d8b4e1cded8ece5c0c52`; `srcblob:692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb`; `acq:64bd0dd82ff9fb56adf6ecf7f6f2612c3e0d27b358b7ffe74c453360ed6f1393`. | Register: `1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6`. AIS: `692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb`. | Scope `NOT_OBSERVED`; v29 current row `NOT_OBSERVED`; local/provider rights `NOT_ASSESSED`. | `HOLD — DECISION_REQUIRED` |
| `82147006639` / `subject:1a9ec5de3fc043ff9226fb95a6cae31b` | Register: `srcrec:e6529d39e4cf32248a4792142cdc5e5bfb5cb45c505180f35662344c737544c`; `srcblob:a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c`; `acq:842d49f9b58861da7dd3882c6a6bb30859dbdfb16c37697b912abc338d1efed2`. AIS: `srcrec:39443daa20d28eadd1164573c635a5c0aa2d89d3b7a8753b14f8321b90f4aea9`; `srcblob:b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f`; `acq:e7f6a062f2e1f799a0e22fe186ba660421ffa32bb27387c5cf3efc9c075da13b`. | Register: `a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c`. AIS: `b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f`. | Scope `NOT_OBSERVED`; v29 current row `NOT_OBSERVED`; local/provider rights `NOT_ASSESSED`. | `HOLD — DECISION_REQUIRED` |

For all five, the recovery lineage class is
`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH` and the object hash matched the
retained object. This proves mechanical lineage only. It does not prove a
current legal name, a governed scope, a current rights decision, a provider
policy, or an admissible task input. The recovery `material_identity_hash` and
`provenance_hash` are available in the preparation manifest but are not
substitutes for the per-representation v29 rights record.

## Minimum T3 authority and rights steps

1. Greg/Product Owner selects one manifest alternative and explicitly records
   that it is the only T3 denominator; do not combine the 36, 182 and 252
   projections.
2. For every selected row, bind the durable CharityGraph subject and a
   governed scope. Confirm the ACNC ABN binding and preserve successor or
   unresolved-lineage states rather than repairing them by discovery.
3. Resolve each source record, immutable source artifact, acquisition receipt,
   exact representation artifact/hash and direct lineage. A source hash alone
   is not a representation-artifact record.
4. Obtain or record the separate local-retention authority and the separate
   provider-processing authority for the exact representation. Do not infer
   either from public access, ACNC licensing, family membership, URL, or a
   copied policy ID. ABR public-HTML rights are an explicit unresolved issue in
   the recovery stop reason.
5. Reload the authoritative rights record by content hash and verify the
   matching current v29 projection row for subject, scope, source record/family
   and role, source artifact, representation artifact/hash and receipt
   lineage. Missing, duplicate, stale, revoked, superseded, mismatched or
   unbound rows remain diagnostics and create zero tasks/attempts/reservations/
   receipts/costs.

## Small immutable T3 no-send manifest contract

Proposed report-only contract: `CG.G4.T3.NO_SEND_MANIFEST/v1`.

The immutable manifest must contain a manifest SHA, selected recovery-manifest
SHA, target HEAD/fence, fixed sorted entry IDs, and for every entry: subject ID,
external ACNC/ABN binding, governed scope ID, admitted source family, source
record ID, source artifact ID/SHA, representation artifact ID/SHA, acquisition
receipt ID/SHA, local-retention decision ID/SHA, provider-processing decision
ID/SHA or explicit `NOT_GRANTED`, current-v29 projection identity, and one
coverage/admissibility state. Allowed states should include
`ADMISSIBLE_NO_SEND`, `NOT_ADMISSIBLE`, `DECISION_REQUIRED`,
`SOURCE_UNAVAILABLE`, `IDENTITY_UNRESOLVED`, `LINEAGE_UNRESOLVED`, and
`STALE_OR_MISMATCHED`.

Acceptance is byte/hash stability, one declared denominator, admitted-family
membership, exact identity/scope and direct lineage, separate rights axes,
matching current v29 rows, deterministic ordering, and zero provider crossing.
The manifest must exclude source bytes, prompts, model responses, credentials
and protected personal data. `ADMISSIBLE_NO_SEND` means mechanically complete
for review; it is not permission to send or promote.

## T4A no-send plan contract

`CG.G4.T4A.NO_SEND_PLAN/v1` should be accepted only as a deterministic plan:

- **Route:** T3 manifest -> clean v29 rights reload -> clean `FactoryPlan`
  lowering -> logical task/request-item plan -> read-only diagnostics. Batch
  and Standard may be represented as alternatives, but neither may send.
- **Task identity:** fixed cohort/subject/scope/source/representation binding,
  task ID, task-contract/schema hash, prompt/template hash, model/provider
  route identity, and policy bundle version. The exact values are currently
  missing and must be supplied, not guessed.
- **Cost:** deterministic upper bound = sum of fixed per-task estimates plus
  explicitly bounded retry, ambiguity, escalation and human-review allowances,
  with currency, price-card/FX identity and cache treatment recorded. T4A
  spend is zero because it sends nothing; it does not reserve the AUD10 live
  ceiling.
- **Concurrency:** an explicit integer maximum, planned batch size and lease
  duration, with dry-run observed concurrency recorded separately from the
  configured cap. No default or observed fixture value is a live authority.
- **Restart and ambiguity:** stable logical task/request-item identity;
  lease ownership and expiry; restart/resume rules; zero duplicate sends;
  explicit `HELD_AMBIGUOUS` state after an uncertain crossing; and operator
  reconciliation before retry.
- **Diagnostics:** immutable run/plan/task hashes; admission counts and
  coverage states; per-item authority failures; reservation/actual/release
  fields (all zero for this no-send plan); failure isolation; and a stable
  diagnostic projection with a stop record.

T4A must stop before any provider boundary if any T3 row is incomplete, the
task/schema/prompt identity is absent, provider policy is absent or stale,
cohort budget cannot be deterministically bounded, a lease is ambiguous, or a
diagnostic is not reproducible.

## T4B live-crossing prerequisites

T4B is not authorised by this brief. Before any live crossing Greg/Product
Owner/Data authority must supply all of the following:

- exact source-owned provider-policy ID and version, effective evidence,
  selected service, no-training/no-sharing posture and renewal/expiry rule;
- exact source-rights decisions for every transmitted representation, with
  source role, lawful acquisition, retention and provider axes separated;
- one frozen T3 cohort/manifest, exact scope, task route, strict schema,
  prompt/template identity, model/provider identity and human-review plan;
- budget reservation and reconciliation plan inside the **AUD10 cumulative
  ceiling**, including extraction, judgement, writing, embeddings, retries and
  escalation, with actual cost and unused reserve handling; and
- explicit stop/escalation ownership for ambiguity, systemic failure,
  provider receipt uncertainty, privacy/rights challenge and human review.

## Product Owner checklist and gates

- [ ] Choose one immutable 36-charity manifest alternative; do not merge its
  counts with the 182-row or 252-row projections.
- [ ] Decide the five-row shortlist, or a different subset; this brief does
  not freeze it.
- [ ] Supply subject/scope treatment, including unresolved successor lineage.
- [ ] Authorise exact local-retention and provider-processing rights assessment
  for each exact representation; resolve the ABR/public-HTML issue.
- [ ] Confirm the source-owned provider-policy ID/version and no-training /
  no-sharing posture.
- [ ] Approve the exact task/schema/prompt/model route and human-review plan.
- [ ] Approve a deterministic no-send T4A plan, then reserve live budget only
  immediately before an authorised T4B request.
- [ ] Require independent review of candidate support, missingness,
  contradictions and promotion disposition.

**Gate map:** T3/T4 here are Gate 4 industrialisation work: evidence binding,
cost routing, restartability, concurrency, diagnostics and controlled provider
crossing. They are not the historical Gate 2 semantic-demand tranches with
the same labels. They are also not Gate 5's later cohort/release decision;
Gate 5 is neither selected nor inferred by this brief. Gate 4 remains open.

## Boundary receipt

Only this report is written. No code, test, manifest, source byte, rights
record, SQLite database, cache, Git metadata, GitHub state, watcher/fence,
provider/model, network, spend, publication, release or gate status was
changed. Pre-existing dirty and untracked files, including the quarantined T2
paths, were preserved.
