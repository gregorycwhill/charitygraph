# CG345 Ethos / Notable History Factory integration

This change starts from Builder `6cd3624a5fa0bf876f760a2745971d2d041413fc`
and Data `93a2621e9e1feb492a2f2e00767e1e4a396962b6`, the exact successors of
certification run `CG-ETHOS-NOTABILITY-CERTIFICATION-344-TERRA`.

The routing decision is derived from `certification/ethos-notability-v1-certification-matrix.json`,
`certification/ethos-notability-v1-failure-ledger.json`, and Data
`CERTIFICATION_ETHOS_NOTABILITY_V1_344.md`: 14/14 expected-vs-observed matches,
3 real controls and 11 synthetic fixtures. Positive semantic families are
`CERTIFIED_WITH_REVIEW`; beneficiary/non-transfer and missingness are the
bounded real-evidence controls. This is contract evidence, not extraction-rate
or production-readiness evidence.

## Executable routes

* Section 15 is owned by `ethos-v1`; section 17 by `notable-event-v1`.
* Source-native, already-governed observations may use `PRIVATE_PROJECTION`.
* Positive semantic interpretation is `REVIEW_REQUIRED` unless separately
  bounded by source-native evidence and the existing provenance/scope/date gates.
* External or disputed characterisation, political/ideological or religious
  characterisation, sensitive-person context, adverse/legal ambiguity, and
  unresolved identity/scope/lineage are `DISABLED`.
* Section 16 remains the sole owner of findings, allegations, sanctions and
  remediation; inquiries in section 17 are not findings.

Factory runtime task metadata now carries section owner, contract, certification
ID/status, disposition, risk family, and routing reason. It does not enable
provider acquisition or automatic governed promotion.

The private v0.3 adapters preserve subject/scope, event role/family, event and
observation/source time, qualification, disagreement/uncertainty, evidence,
source records, lineage, and explicit missingness. They do not infer current
ethos from history, quality from awards, findings from inquiries, or transfer
attributes across parent/affiliate/predecessor/successor subjects.

Validation run:

`python -m pytest -q tests/contracts/test_s0_ethos_notability_integration.py tests/contracts/test_ethos_history_v1.py tests/contracts/test_ethos_notability_certification_344.py tests/contracts/test_reality_corpus_ethos_notability_v1.py`

Result: **57 passed**. The additional Factory suite was attempted but its five
tests could not create pytest temporary directories because of the environment's
pre-existing access denial on `C:\Users\grego\AppData\Local\Temp\pytest-of-grego`.

Before loosening gates, the next tranche needs a larger real-source corpus,
identity/scope/lineage ambiguity measurements, repeated-source dedupe evidence,
and human-reviewed extraction error rates across the currently synthetic-only
positive subfamilies.
