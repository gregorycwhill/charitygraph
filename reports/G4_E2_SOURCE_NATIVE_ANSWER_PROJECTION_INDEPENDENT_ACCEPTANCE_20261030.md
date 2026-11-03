# G4 E2 independent acceptance — source-native answer projection

Date: 2026-10-30 (Australia/Sydney)  
Disposition: **PARTIAL**

## Scope and factual proposition

Reviewed the exact branch `gate3-cg406-remediation`, HEAD
`c3fc30c4e81e0a862d6b75bb78344b1ce7efa86c`, parent
`ebd8fdb270863aab05642c76b10eff40b2a6872d`, and the three-path direct-child
commit. The bounded proposition delivered is valid: the retained five-subject
ACNC cohort can be read locally and projected into 15 deterministic private
answer slots (activity, reporting-period scale, and explicit currentness
missingness per subject), without model/provider work or current availability,
donor-offer, impact, effectiveness, governance or conduct inference.

This is not canonical knowledge, publication, release, or North Star completion.

## Independent checks

- Commit diff: exactly these three added paths, with no unexpected commit path:
  `reports/G4_E2_SOURCE_NATIVE_ANSWER_PROJECTION_20261030.md`,
  `src/charitygraph/phase5_t4b_source_answer_projection.py`, and
  `tests/test_phase5_t4b_source_answer_projection.py`.
- Focused command: `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_phase5_t4b_source_answer_projection.py`
  — **8 passed in 0.62s**.
- The suite covers 5 subjects, 10 representations, 15 slots, deterministic
  replay, tamper rejection, subject/scope drift rejection, period/provenance
  retention, explicit source-silence missingness, and no-file behaviour.
- Code inspection confirms standard-library-only imports and no SQLite,
  network, credential, provider, acquisition, budget, publication or release
  operation. The projection returns zero counters for those effects at
  `src/charitygraph/phase5_t4b_source_answer_projection.py:471-481`.
- The pre-existing dirty and untracked workspace was preserved; the focused
  run produced no tracked code/test changes and no unexpected target artefact.
  Existing runtime `catalog.sqlite3`, `catalog.sqlite3-wal`, and
  `catalog.sqlite3-shm` files were present before this acceptance evidence was
  interpreted; this review did not open them and cannot claim their historical
  creation time.

## Source hash and binding evidence

The direct local audit recomputed SHA-256 for all ten exact files under
`C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\`.
Every computed hash matched both manifest `source_sha256` and
`representation_sha256`; every body had the expected ABN and source type.

| Subject | Family | Source record | Representation SHA-256 |
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

The manifest contains five consistent subject/scope pairs, one register and one
AIS row per subject. Register `LastReported` values and AIS `FinReportFrom` /
`FinReportTo` periods were retained. Field-basis paths distinguish the observed
top-level and nested `$.data.<field>` layouts. Register structured fields are
separate from AIS narrative fields; unrestricted prose is not interpreted.

## Defects and unverifiable claims

1. **Medium — manifest identity is trusted, not independently verified.** At
   `src/charitygraph/phase5_t4b_source_answer_projection.py:203-207`, the code
   compares a hard-coded expected value with the manifest’s
   `selected_manifest_sha256`, but does not recompute the selected-manifest
   identity or the file-byte hash, and ignores `manifest_identity_sha256`.
   The observed manifest file SHA-256 is
   `06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4`, while
   its declared selected identity is
   `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`.
   The two may represent different canonical identities, but that rule is not
   executable or independently demonstrated here.
2. **Medium — source-record binding is only prefix-checked.** At
   `src/charitygraph/phase5_t4b_source_answer_projection.py:240-241`, any value
   beginning `srcrec:` is accepted. The code does not verify the exact ten
   source-record IDs against a governed source-record/rights record or validate
   their content-addressed suffix. The tests likewise cover subject/scope drift
   but not source-record tampering (`tests/test_phase5_t4b_source_answer_projection.py:72-86`).
3. **Bounded fence limitation —** no local repository file or tracked bridge
   evidence independently exposed immutable fence `v62` / SHA-256
   `d1d4f4adc51afd58ce12bbe7ee025dc55024920f62e85a7ce85a3e98fe8e5670`; the
   exact HEAD and parent were verifiable. This is reported as unverifiable, not
   inferred.

## Prioritised next small product improvement

Add one read-only manifest/source-record binding verifier that recomputes the
canonical manifest identity, validates the exact ten governed source-record
IDs, and adds tamper tests for those two fields. Keep it private and
provider-free; do not broaden the source universe or add semantic heuristics.

## Boundary conclusion

The bounded source-native product proposition is technically demonstrated and
the focused tests pass, but independent acceptance remains **PARTIAL** until
manifest identity and exact source-record binding are executable rather than
trusted metadata, and the v62 fence evidence is locally verifiable. No source,
provider, model, network, credential, Drive, GitHub, watcher, publication,
release, budget or gate state was changed by this review.
