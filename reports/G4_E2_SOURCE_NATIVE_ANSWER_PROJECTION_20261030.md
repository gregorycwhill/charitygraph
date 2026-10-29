# G4 E2 source-native answer projection — 2026-10-30

## Result

Implemented one provider-free, read-only `AnswerProjection` derivative in
`src/charitygraph/phase5_t4b_source_answer_projection.py`. It reads the local
T3 JSON manifest and the ten exact content-addressed JSON representations,
checks every representation SHA-256, preserves the governed subject/scope and
source identities, and emits exactly 15 deterministic records (three per
subject).

This is a private derivative only. It is not canonical promotion, a public
projection, publication, release work, or a North Star completion claim.

## Exact retained inputs

- Branch: `gate3-cg406-remediation`
- Instructed HEAD: `ebd8fdb270863aab05642c76b10eff40b2a6872d`
- Instructed bridge fence: `v61`
- Instructed fence SHA-256: `c96b1a435d3b4c5b806c97e597dc868cf146a561b4611db7a5549daf79b069a6`
- T3 manifest: `evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json`
- Declared selected-manifest SHA-256: `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`
- Representation root: `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\<first-two>/<sha256>`

The ten physically read representation hashes and source record identities
were:

| Subject | Source family | Source record | Representation SHA-256 |
|---|---|---|---|
| Guide Dogs NSW/ACT | `acnc_register` | `srcrec:4978c7ff7f9694d9d9d6db9ad871a8048cde5940c6e699a2dd4bd15360bcd28d` | `f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2` |
| Guide Dogs NSW/ACT | `acnc_ais_bundle` | `srcrec:554fa9df1414f0096b9035fea5ac5eee7ffb59e46eb767d6306d40d8f326f08a` | `70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b` |
| Human Appeal International Australia | `acnc_register` | `srcrec:f05f137023221378d486eef96e0c4efe377bb4811ac63fbbbb9aa8f103c251d2` | `8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773` |
| Human Appeal International Australia | `acnc_ais_bundle` | `srcrec:045161751edf9950655698373906590d67abf2c35ba33dd804b61b3ac95237f8` | `ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33` |
| The Peter & Lyndy White Foundation | `acnc_register` | `srcrec:188a391cee048ab2fa7720aeb2c58f5b1e025039ef674ef8a6fd6ea0ab91dd8a` | `ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c` |
| The Peter & Lyndy White Foundation | `acnc_ais_bundle` | `srcrec:5cc396995aea23edbab90c78b47101651f3a085f34ab088417dc3e1caa6fda25` | `9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678` |
| Oz Harvest Limited | `acnc_register` | `srcrec:5e1c9ac1b0378a22557a9bf804697719133663123e7f603d76eb41fd2601adf4` | `1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6` |
| Oz Harvest Limited | `acnc_ais_bundle` | `srcrec:e94d13fec302f9cefc42569b4d191dae5b360565c8c3d8b4e1cded8ece5c0c52` | `692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb` |
| Islamic Relief Australia | `acnc_register` | `srcrec:e6529d39e4cf32248a4792142cdc5e5bfb5cb45c5055180f35662344c737544c` | `a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c` |
| Islamic Relief Australia | `acnc_ais_bundle` | `srcrec:39443daa20d28eadd1164573c635a5c0aa2d89d3b7a8753b14f8321b90f4aea9` | `b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f` |

The Peter & Lyndy White representations use the observed nested `data` body
layout; the projection records the exact `$.data.<field>` basis for those
fields. Their governed manifest binding remains the identity authority.

## Projection and answerability

Each subject receives:

1. `source_native_activity_and_footprint`: supported structured selection from
   register `Programs`, `OperatingInStates`, `Countries`, and `Beneficiaries`.
2. `retained_reporting_period_scale`: supported structured selection from AIS
   reporting dates, accounting basis, receipts, expenses, result, employees,
   and unpaid volunteers.
3. `current_giving_capacity_outcomes_governance_conduct`: explicitly
   `unanswered`, with missingness for current giving terms, current capacity,
   outcomes/effectiveness, governance, and conduct/adverse history. Source
   silence is retained as missingness and is not converted to a negative claim.

Register structured facts and AIS narrative fields remain distinct: this
projection does not select or summarise `SummaryOfActivities` or
`ActivityPersuitPurposesDescription`, and it does not infer from unrestricted
prose. The 20-section North Star vocabulary is not emitted as knowledge.

## Validation and tests

New tests: `tests/test_phase5_t4b_source_answer_projection.py` — **8 passed**.

The focused suite covers all five subjects, all ten representations, 15 slots,
deterministic replay, exact reporting periods and provenance, representation
hash tampering rejection, cross-subject and cross-scope manifest drift, explicit
missingness, and no-file side effects. The projection also reports zero
provider calls, transport requests, budget reservations, source acquisitions,
publications, and SQLite opens.

## Boundaries and limitations

- No SQLite, WAL, SHM or journal was opened.
- No provider, model, network, credential, Drive, GitHub, watcher or external
  source was accessed.
- No source was acquired and no runtime or data file was changed.
- No canonical observation, public projection, publication, release, commit,
  gate closure or follow-on task was performed.
- The supported answers are source-native selections, not independent
  effectiveness, availability, donor-suitability, governance, conduct or
  outcome assessments. Currentness remains unanswered as designed.
- The code uses only stable identifiers, exact JSON field paths, hash checks,
  and typed missingness. It adds no regex, keyword list, lexical scoring,
  fuzzy matching, local NLP, or other unrestricted-prose semantic heuristic;
  the Semantic Heuristic Gate is therefore satisfied for this bounded path.

Only the three allowlisted paths were created/changed by this task. Existing
dirty and untracked unrelated work was preserved.
