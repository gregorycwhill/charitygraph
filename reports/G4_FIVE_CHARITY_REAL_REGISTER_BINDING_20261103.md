# G4-O1C — five-charity real ACNC register binding

Date: 2026-11-03 (Australia/Sydney)  
HEAD: `5a2bbe317d3b844550a37ce23dad4e1227ca74e8`

Result: **5 BOUND register rows / 5 MISSING AIS rows / 0 BLOCKED**.

The supplied transport was independently verified before processing:

| Item | SHA-256 / result |
|---|---|
| Four-entry transport | `5cd5fc916d6356f147f7218cb9ade9c167bedff4a760a7d8fb08ddafcec92f73` — match |
| Selected manifest file | `06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4` |
| Upstream original CSV claim | `1ff76b510e8155d7ab35df4b45b8791315c1f0a15f43f9c3057dff16646f816d` — mirror claim, not locally verified |

## Four new real register rows

Each response is the exact raw UTF-8 `publicdata.au` API body, version
`2026-10-26`, one row and 69 fields. The source is the independent
`publicdata.au` representation, attributed to ACNC and National Digital under
CC BY 3.0 AU; it is not treated as ACNC publisher-original CSV.

| Ordinal | Charity / ABN | Source bytes / SHA-256 | Representation bytes / SHA-256 |
|---:|---|---:|---:|
| 3 | Human Appeal International Australia / `26164251245` | 4173 / `3ad023beed624de3ca5f1ed17f29b01a64141b70e3166eb6c6df99e7ebf1e357` | 3305 / `d002d17c132918078d63b5b1f9738fa2d87fcf3750f6e0947850158ea4a58719` |
| 5 | The Peter & Lyndy White Foundation / `52404606134` | 4085 / `7ae05d8b38a106663a28c4a70c1c573828519f5d9d64742da7c362f1d830cd93` | 3217 / `24b0d8a311c90569ec1f51896950f172daab77fceefaebe8bb95785d9d6f1e26` |
| 7 | Oz Harvest Limited / `33107782196` | 4028 / `d80552005dcafc554f978e1d863db141d6c9f3aa15c7f5bcc9d276668a741425` | 3160 / `cbbcc97b68ecfde91718363b74782f4e4809467596f7675e528ad38e607c508e` |
| 9 | Islamic Relief Australia / `82147006639` | 4219 / `48750195040c4e829f82d9f0f7bb7584e9732d615d8fe343dfe9efffaab4b8f8` | 3351 / `75cdf6b33e0be8a1e46e5390af8f1a65284f68189f2ae2507cc975754460b1d2` |

Ordinal 1, Guide Dogs NSW/ACT, was replayed from its already-bound exact
metadata (`07b83ca8…5372fc` source; `1405b49e…76af82` representation). Its
prior first-charity artifacts and decision were not changed or duplicated.

## Artifacts and rights

New metadata-only artifacts:

- `evidence/gate4-t3-five-subject-v1/publicdata-20261026-four-charity-acquisition-receipts.json`
- `evidence/gate4-t3-five-subject-v1/publicdata-20261026-four-charity-rights-decisions.json`
- `evidence/gate4-t3-five-subject-v1/publicdata-20261026-four-charity-bindings.json`

Raw responses and canonical normalized representations are private only under
`C:\CharityGraph-runtime\g4-o1c-publicdata-acnc-register-remaining-four-20261103\`.
No raw bytes or base64 payloads are in Git.

Each new row has separate source/representation identities, acquisition
receipt, source record, scope, local-retention decision, and private-provider
processing decision. The rights basis is the existing governed
`CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1` / `1.0.0` policy with the
existing provider-policy identity. Provider calls and transmission were not
requested (`provider_call_authorized=false`, spend `AUD 0.00`). Public
redistribution remains `not_assessed`.

AIS ordinals `2, 4, 6, 8, 10` remain correctly `MISSING`: no selected AIS
source, receipt, representation, scope-bound rights record, or provider-rights
record was supplied for those rows. No synthetic or URL-only evidence was used.

## Verification

Focused source, rights, binder, and Factory regressions:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-o1c-four-real-regressions-20261103 tests/test_phase5_t3_publicdata_four_charity_real.py tests/test_phase5_t3_acnc_real_evidence_retention.py tests/test_phase5_t3_source_evidence_binding.py tests/test_phase5_t3_publicdata_acnc_api_source.py tests/test_phase5_t3_publicdata_rights_decision_real.py tests/test_source_rights.py tests/test_phase5_factory.py
65 passed
```

No provider/model call, external acquisition, publication, release, GitHub or
Drive mutation, watcher/process change, Gate 4 closure, or follow-on dispatch
occurred. The next bounded data step is the selected 2025 AIS path for each
charity; any future provider transmission still requires a separately
authorized exact provider contract and remains unrequested here.
