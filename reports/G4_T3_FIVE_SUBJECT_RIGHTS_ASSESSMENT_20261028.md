# G4 T3 five-subject exact-representation rights assessment

Date: 2026-10-28 (Australia/Sydney)  
Target: `gate3-cg406-remediation@700cfe1f4e576e00471155a6bfedbcc40fc36cab`  
Fence: `v43`  
Mode: local, read-only, no-send

## Result

`STOP / DECISION_REQUIRED`. The five ABN/ACNC-bound subjects and the selection
manifest SHA-256 below are **provisional rights-assessment scope only**. They
are not a frozen executable cohort, provider permission, or knowledge
promotion.

The recovery inventory reports 224 hash-verified member references, 189 unique
source objects, zero rights decisions, zero provider calls, and no trusted
provider authorisation. The ten rows below are the exact ACNC register/AIS
records inspected for this bounded assessment.

Evidence basis: `evidence/gate3-fresh36-bounded-recovery-v1/recovery-status.json`
and `source-lineage-recovery.json`; selected-manifest SHA-256
`41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`.
Inventory artifact hashes: `recovery-status.json` SHA-256
`828478f3dc2f78a008c91c0ce0a3135968fe07973551305c8fb5ac75ed1088df`;
`source-lineage-recovery.json` SHA-256
`7f3664ac1bfa5d1312aff5e8b8eee62ffdf048d18f00d4f6dc61ec69439743b2`.

## Ten-row audit matrix

`MATCH` means only that the retained source object was present and its expected
and actual physical SHA-256 matched. It does not establish source rights,
third-party-content clearance, local retention, provider processing, or public
redistribution. `rep-id MISSING` is the important distinction: the recovery
inventory observes source-native bytes/hashes, but not a separate exact
representation-artifact identity suitable for a v29 rights row.

| Row / observed subject | Source role / family; immutable source record | Source artifact / physical hash | Representation identity / hash | Receipt lineage, method, date | Governed scope / current v29 row | Rights record and axes | Exact policy ID/version bound to this row | Missingness and exact blockers |
|---|---|---|---|---|---|---|---|---|
| 1. **OBSERVED** `52000399744` / `subject:02649cdcb42049bb8dedd30f2333e150` | ACNC regulatory register/profile; `acnc_register`<br>`srcrec:4978c7ff7f9694d9d9d6db9ad871a8048cde5940c6e699a2dd4bd15360bcd28d` | `srcblob:f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2`<br>SHA `f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2` — MATCH | `rep-id MISSING`<br>source-native SHA observed only: `f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2` | `acq:0b099288968c5ac89fc4bff0811f021787281fb38737565221c506123098b63e`<br>`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH`; reused existing; contemporaneous top100 evidence bundle; 2026-08-29 (HTTP status not retained) | `scope_id MISSING`; preparation instance is not scope: `g3fresh-v1:subject:02649cdcb42049bb8dedd30f2333e150:SDC-C11:domain-11`<br>v29 current row: **NOT_OBSERVED** | Rights record ID/hash: **NONE**<br>local retention: `NOT_ASSESSED`<br>provider processing: `NOT_ASSESSED`<br>public redistribution: `NOT_AUTHORIZED` | **NONE BOUND**; no row-specific rights decision or source-owned provider-policy attestation/version | `B1 B2 B3 B4 B5 B6 B7 B8` |
| 2. **OBSERVED** `52000399744` / `subject:02649cdcb42049bb8dedd30f2333e150` | ACNC regulatory AIS/detail bundle; `acnc_ais_bundle`<br>`srcrec:554fa9df1414f0096b9035fea5ac5eee7ffb59e46eb767d6306d40d8f326f08a` | `srcblob:70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b`<br>SHA `70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b` — MATCH | `rep-id MISSING`<br>source-native SHA observed only: `70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b` | `acq:e094f723f29b2d0394805ee00d0c1f5cdce483d96c2dee14ca7ea4c1da69eac4`<br>`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH`; reused existing; contemporaneous top100 evidence bundle; 2026-08-29 (HTTP status not retained) | Same ungoverned preparation instance as row 1; `scope_id MISSING`<br>v29 current row: **NOT_OBSERVED** | Rights record ID/hash: **NONE**<br>local retention: `NOT_ASSESSED`<br>provider processing: `NOT_ASSESSED`<br>public redistribution: `NOT_AUTHORIZED` | **NONE BOUND**; ACNC general reuse language is not an exact AIS/third-party clearance | `B1 B2 B3 B4 B5 B6 B7 B8` |
| 3. **OBSERVED** `26164251245` / `subject:0889b4decb854e71ab4784479ca95c03` | ACNC regulatory register/profile; `acnc_register`<br>`srcrec:f05f137023221378d486eef96e0c4efe377bb4811ac63fbbbb9aa8f103c251d2` | `srcblob:8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773`<br>SHA `8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773` — MATCH | `rep-id MISSING`<br>source-native SHA observed only: `8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773` | `acq:fbb55f0fb70eecd14aa98017f1fc4b458c2522adde0c79a03237ac76e11ad05b`<br>`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH`; reused existing; contemporaneous top100 evidence bundle; 2026-08-29 (HTTP status not retained) | `scope_id MISSING`; preparation instance: `g3fresh-v1:subject:0889b4decb854e71ab4784479ca95c03:SDC-C11:domain-10`<br>v29 current row: **NOT_OBSERVED** | Rights record ID/hash: **NONE**<br>local retention: `NOT_ASSESSED`<br>provider processing: `NOT_ASSESSED`<br>public redistribution: `NOT_AUTHORIZED` | **NONE BOUND** | `B1 B2 B3 B4 B5 B6 B7 B8` |
| 4. **OBSERVED** `26164251245` / `subject:0889b4decb854e71ab4784479ca95c03` | ACNC regulatory AIS/detail bundle; `acnc_ais_bundle`<br>`srcrec:045161751edf9950655698373906590d67abf2c35ba33dd804b61b3ac95237f8` | `srcblob:ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33`<br>SHA `ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33` — MATCH | `rep-id MISSING`<br>source-native SHA observed only: `ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33` | `acq:c60f2a53e31086b4dfab8fbced7e1b0718a64e6694f8dcd6cd93eaffc2ef1c09`<br>`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH`; reused existing; contemporaneous top100 evidence bundle; 2026-08-29 (HTTP status not retained) | Same ungoverned preparation instance as row 3; `scope_id MISSING`<br>v29 current row: **NOT_OBSERVED** | Rights record ID/hash: **NONE**<br>local retention: `NOT_ASSESSED`<br>provider processing: `NOT_ASSESSED`<br>public redistribution: `NOT_AUTHORIZED` | **NONE BOUND** | `B1 B2 B3 B4 B5 B6 B7 B8` |
| 5. **OBSERVED** `52404606134` / `subject:16fba76fde2242d5870835b18b4e8b8d` | ACNC regulatory register/profile; `acnc_register`<br>`srcrec:188a391cee048ab2fa7720aeb2c58f5b1e025039ef674ef8a6fd6ea0ab91dd8a` | `srcblob:ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c`<br>SHA `ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c` — MATCH | `rep-id MISSING`<br>source-native SHA observed only: `ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c` | `acq:8cbf097d3ca6a8a0282158d7980d965b9b715886d01d9146b41ebc57c4115637`<br>`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH`; reused existing; contemporaneous top100 evidence bundle; 2026-08-29 (HTTP status not retained) | `scope_id MISSING`; preparation instance: `g3fresh-v1:subject:16fba76fde2242d5870835b18b4e8b8d:SDC-C03:domain-5`<br>v29 current row: **NOT_OBSERVED** | Rights record ID/hash: **NONE**<br>local retention: `NOT_ASSESSED`<br>provider processing: `NOT_ASSESSED`<br>public redistribution: `NOT_AUTHORIZED` | **NONE BOUND** | `B1 B2 B3 B4 B5 B6 B7 B8` |
| 6. **OBSERVED** `52404606134` / `subject:16fba76fde2242d5870835b18b4e8b8d` | ACNC regulatory AIS/detail bundle; `acnc_ais_bundle`<br>`srcrec:5cc396995aea23edbab90c78b47101651f3a085f34ab088417dc3e1caa6fda25` | `srcblob:9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678`<br>SHA `9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678` — MATCH | `rep-id MISSING`<br>source-native SHA observed only: `9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678` | `acq:0d954180bc7c8e26f48f1788164c9b2c900d7bcc43cff8d043944e68bd99bc18`<br>`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH`; reused existing; contemporaneous top100 evidence bundle; 2026-08-29 (HTTP status not retained) | Same ungoverned preparation instance as row 5; `scope_id MISSING`<br>v29 current row: **NOT_OBSERVED** | Rights record ID/hash: **NONE**<br>local retention: `NOT_ASSESSED`<br>provider processing: `NOT_ASSESSED`<br>public redistribution: `NOT_AUTHORIZED` | **NONE BOUND**; subject-level ABR successor/original-lineage issue is separate and not silently merged into this ACNC row | `B1 B2 B3 B4 B5 B6 B7 B8` |
| 7. **OBSERVED** `33107782196` / `subject:1823309bdd06417c9928033603cb6e39` | ACNC regulatory register/profile; `acnc_register`<br>`srcrec:5e1c9ac1b0378a22557a9bf804697719133663123e7f603d76eb41fd2601adf4` | `srcblob:1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6`<br>SHA `1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6` — MATCH | `rep-id MISSING`<br>source-native SHA observed only: `1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6` | `acq:fc6227ca5e16e8232088ef98cac3089927b208c3b35e236958dac9171a6bf960`<br>`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH`; reused existing; contemporaneous top100 evidence bundle; 2026-08-29 (HTTP status not retained) | `scope_id MISSING`; preparation instance: `g3fresh-v1:subject:1823309bdd06417c9928033603cb6e39:SDC-C11:domain-9`<br>v29 current row: **NOT_OBSERVED** | Rights record ID/hash: **NONE**<br>local retention: `NOT_ASSESSED`<br>provider processing: `NOT_ASSESSED`<br>public redistribution: `NOT_AUTHORIZED` | **NONE BOUND** | `B1 B2 B3 B4 B5 B6 B7 B8` |
| 8. **OBSERVED** `33107782196` / `subject:1823309bdd06417c9928033603cb6e39` | ACNC regulatory AIS/detail bundle; `acnc_ais_bundle`<br>`srcrec:e94d13fec302f9cefc42569b4d191dae5b360565c8c3d8b4e1cded8ece5c0c52` | `srcblob:692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb`<br>SHA `692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb` — MATCH | `rep-id MISSING`<br>source-native SHA observed only: `692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb` | `acq:64bd0dd82ff9fb56adf6ecf7f6f2612c3e0d27b358b7ffe74c453360ed6f1393`<br>`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH`; reused existing; contemporaneous top100 evidence bundle; 2026-08-29 (HTTP status not retained) | Same ungoverned preparation instance as row 7; `scope_id MISSING`<br>v29 current row: **NOT_OBSERVED** | Rights record ID/hash: **NONE**<br>local retention: `NOT_ASSESSED`<br>provider processing: `NOT_ASSESSED`<br>public redistribution: `NOT_AUTHORIZED` | **NONE BOUND** | `B1 B2 B3 B4 B5 B6 B7 B8` |
| 9. **OBSERVED** `82147006639` / `subject:1a9ec5de3fc043ff9226fb95a6cae31b` | ACNC regulatory register/profile; `acnc_register`<br>`srcrec:e6529d39e4cf32248a4792142cdc5e5bfb5cb45c505180f35662344c737544c` | `srcblob:a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c`<br>SHA `a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c` — MATCH | `rep-id MISSING`<br>source-native SHA observed only: `a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c` | `acq:842d49f9b58861da7dd3882c6a6bb30859dbdfb16c37697b912abc338d1efed2`<br>`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH`; reused existing; contemporaneous top100 evidence bundle; 2026-08-29 (HTTP status not retained) | `scope_id MISSING`; preparation instance: `g3fresh-v1:subject:1a9ec5de3fc043ff9226fb95a6cae31b:SDC-C08:domain-8`<br>v29 current row: **NOT_OBSERVED** | Rights record ID/hash: **NONE**<br>local retention: `NOT_ASSESSED`<br>provider processing: `NOT_ASSESSED`<br>public redistribution: `NOT_AUTHORIZED` | **NONE BOUND** | `B1 B2 B3 B4 B5 B6 B7 B8` |
| 10. **OBSERVED** `82147006639` / `subject:1a9ec5de3fc043ff9226fb95a6cae31b` | ACNC regulatory AIS/detail bundle; `acnc_ais_bundle`<br>`srcrec:39443daa20d28eadd1164573c635a5c0aa2d89d3b7a8753b14f8321b90f4aea9` | `srcblob:b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f`<br>SHA `b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f` — MATCH | `rep-id MISSING`<br>source-native SHA observed only: `b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f` | `acq:e7f6a062f2e1f799a0e22fe186ba660421ffa32bb27387c5cf3efc9c075da13b`<br>`ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH`; reused existing; contemporaneous top100 evidence bundle; 2026-08-29 (HTTP status not retained) | Same ungoverned preparation instance as row 9; `scope_id MISSING`<br>v29 current row: **NOT_OBSERVED** | Rights record ID/hash: **NONE**<br>local retention: `NOT_ASSESSED`<br>provider processing: `NOT_ASSESSED`<br>public redistribution: `NOT_AUTHORIZED` | **NONE BOUND** | `B1 B2 B3 B4 B5 B6 B7 B8` |

### Blocker key

- **B1:** no distinct representation-artifact ID; source-object SHA is not a v29 representation binding.
- **B2:** no governed `scope_id`; the preparation `instance_id` is not a governed scope.
- **B3:** no exact-representation `RightsGovernanceRecord`, decision ID, content hash, assessment authority, or review state; recovery says `rights_decisions_created: 0`.
- **B4:** local-retention axis has not been individually assessed. The approved product policy reference `CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1` / `1.0.0` is not an individual decision for these bytes.
- **B5:** provider-processing axis has not been individually assessed and nothing was transmitted. The ordinary OpenAI API no-training posture accepted by Greg does not replace source-owned provider-policy evidence, selected-service identity, effective version, no-sharing posture, and renewal/attestation for these exact representations. The clean rights substrate fails closed when that exact provider registry mapping is absent; no provider policy is created or inferred here.
- **B6:** the supplied ACNC copyright pointer describes general CC BY 4.0 reuse subject to third-party-supplied-material exclusions, and the ACNC data-policy pointer retains privacy/protected-information limits. Neither pointer is an automatic licence for these captured API/AIS bytes; field-level third-party-content assessment is missing, especially for AIS material.
- **B7:** public redistribution has no separate affirmative decision and is not authorized. A future public projection must use its own publication allowlist; physical source hashes do not authorize source-byte redistribution.
- **B8:** no candidate-specific current v29 projection row/reload identity exists, so clean rights preflight cannot validate the exact subject/scope/source/representation/receipt binding.

## Policy and authority reading

The active North Star is `north-star-v0.3`; it requires subject, scope, source
role, exact evidence/representation hash, rights, missingness and projection
version to remain distinct. Data source governance makes accessibility
insufficient for retention, provider transmission or redistribution, and
requires separate exact-representation decisions for those axes.

The current Data policy material observed includes:

- `AU_FAIR_DEALING_ANALYTICAL_PROCESSING_V1` / `1.0.0` — CharityGraph
  product policy, not external legal advice and not an automatic row decision;
- `CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1` / `1.0.0` — separate bounded
  local-retention policy, still requiring an exact representation and an
  individual auditable decision;
- `scale-s0-rights-transmission-boundary-v3` / `3` — a source/access boundary,
  not a per-artifact rights decision; and
- the Data governance text names
  `OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1` as a provider
  condition in its prior policy route. The current recovery inventory has no
  source-owned provider-policy registry/attestation bound to these ten rows;
  that text is therefore not used as transmission authority here.

The external ACNC copyright and data-policy URLs supplied for this task were
treated as research pointers only:
`https://www.acnc.gov.au/copyright` and
`https://www.acnc.gov.au/about/corporate-information/corporate-policies/corporate-policy-use-acnc-data`.
No network request or external-source access was made.

## Smallest safe later workflow

The smallest source-owned evidence needed before any later record creation is,
for each exact row: a dated terms/licence evidence reference; a field-level
determination of ACNC-owned versus third-party-supplied AIS content; lawful
access/no-circumvention and explicit-prohibition checks; the exact selected
representation class and bytes; a separate local-retention determination; a
separate source-owned provider-policy record (ID, version, effective evidence,
selected service, no-training/no-sharing posture and renewal rule); and a
separate public-redistribution determination. These are evidence inputs, not
values to be guessed from public accessibility or a physical hash.

Candidate next non-send engineering task (not executed here): on a separately
provisioned clean target-HEAD surface, build a report-only five-subject binding
verifier that (1) materializes explicit content-addressed representation
identities from the already retained source objects without reacquisition, (2)
binds each row to an explicitly supplied governed scope, (3) accepts only
human/Data-authorized per-representation records with the three independent
axes above, (4) reloads each record by content hash and verifies the matching
v29 current row, and (5) emits per-row diagnostics and a deterministic no-send
manifest. Any missing, stale, unbound, third-party-uncleared or mismatched row
must remain `DECISION_REQUIRED` and lower to zero tasks, attempts,
reservations, receipts and cost. This task must not create the missing policy
authority, call a provider, acquire sources, or promote knowledge.

## Boundary receipt

Only this report was written. No source bytes, private evidence, prompts, model
responses, provider policy, rights decision, v29 row, database, cache, code,
test, Git index, GitHub state, publication, release, watcher, fence or gate
state was changed. Existing dirty and quarantined T2 material remains
preserved.
