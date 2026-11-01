# G4 T3 ACNC evidence/receipt/rights/Factory binding

Status: PARTIAL — implementation and offline acceptance are complete; the
retained real-data cohort remains all-ten missing/not-observed.

Scope is limited to the exact bounded local task at branch `gate3-cg406-remediation`,
HEAD `c824011b407abef6c709e79d936c3338255e69c9`, under immutable fence v100
(`90fa7cc9af8c68673a686f0573cb11b1859e802c11940efd9d06861fd8d36b45`). No
provider/model calls, network/source acquisition, Drive/GitHub mutation, watcher
operation, commit, publication, release or gate action is performed.

The implementation will write only the deterministic local adapter
`src/charitygraph/phase5_t3_source_evidence_binding.py` and its focused test
`tests/test_phase5_t3_source_evidence_binding.py`. It consumes already-retained
metadata/bytes and lowers only verified rows through the existing governed Factory
reference contract. A locator without retained bytes is not evidence. Subject,
scope, receipt, source-record, representation-hash, rights-policy/version and
provider-use checks fail closed. Missing rows remain explicit missingness and are
not counted as observations.

## Checked retained evidence

The selected manifest at `evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json`
has manifest identity `5c352f6a929508d9ecfe959cb4f8191cf776ef826b03be33f78d8c24bddbd14a`,
10 rows, 5 durable-subject references, and only `acnc_register` plus
`acnc_ais_bundle`. It declares `source_bytes_included: false`; each declared
representation ID/SHA is the corresponding source artifact ID/SHA. Its provider
state is `blocked` and public redistribution is `not_assessed`. It is therefore
a selection/coverage input, not proof of ten captured source-native bytes.

With no supplied retained catalogue material, the adapter replay produced 10
`MISSING` rows, 0 bound rows, 5 subjects, and 10 explicit `missingness` rows.
No source URL, locator, ABN, synthetic fixture, or `NOT_OBSERVED` row was counted
as an observation. The positive fixture is explicitly synthetic and is not
reported as real-data acceptance.

## Implementation and tests

The new adapter validates durable subject identity, exact original evidence
scope, source record and source-byte SHA, acquisition receipt outcome and hash,
representation bytes and hash, citation locator, date/period, and independent
versioned local/provider/public rights decisions. It lowers only fully verified
observations to the existing `GovernedReference` Factory contract. Candidate
rows require governance; missingness remains missingness; no provider call or
Factory runtime send is made.

Focused and relevant committed regressions:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-t3-final-pytest tests/test_phase5_t3_source_evidence_binding.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py tests/test_phase5_t3_exact_representation_rights_binding.py tests/test_source_rights.py
66 passed
```

The focused tests cover confirmed binding, absent source/body, stale receipt,
altered SHA, wrong/ambiguous subject, rights version/status, cross-scope,
duplicate source/rights identity, candidate/missingness, deterministic replay,
changed source policy, and honest all-ten-missing replay. The allowlisted files
have no trailing whitespace. Full `git diff --check` is **FAIL/PRE-EXISTING**
only because unrelated dirty baseline file
`reports/G4_T4A4_SOURCE_OWNED_PROVIDER_CONTRACT_REGISTRY_20261029.md:4` already
contains trailing whitespace; no allowlisted file is implicated.

Allowlisted output hashes at completion:

| Path | Lines | SHA-256 |
|---|---:|---|
| `src/charitygraph/phase5_t3_source_evidence_binding.py` | 651 | `c9be2e4196233bf531b65b92d53e73de736ba920e9018d22ec4689c05a26511e` |
| `tests/test_phase5_t3_source_evidence_binding.py` | 262 | `f4ec6ef4f6f896969f725d65fc73494998a2e6f9437d32502926e547d16cf006` |
| `reports/G4_T3_ACNC_EVIDENCE_RECEIPT_RIGHTS_FACTORY_BINDING_20261101.md` | 76 | report self-hash intentionally omitted |

No commit was created. Existing dirty and untracked baseline paths were
preserved; no raw/private source material, runtime catalogue, cache, credential,
provider/model output, or generated public projection was added.

Reproducible commands and final PASS/PARTIAL/FAIL results will be appended after
the focused tests, relevant Factory regressions, and `git diff --check` complete.
