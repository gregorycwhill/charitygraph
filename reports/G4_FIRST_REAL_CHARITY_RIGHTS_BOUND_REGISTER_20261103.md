# G4-O1C — first real charity rights-bound register

Date: 2026-11-03 (Australia/Sydney)  
Result: **BOUND for ordinal 1; 1/10 cohort rows bound**

## Exact bounded result

- Subject: `subject:02649cdcb42049bb8dedd30f2333e150` — Guide Dogs NSW/ACT
- Scope: `scope:0a10077aee9363200199a815e8198f3807fef97737ad89bfd1e2e17f61d63248`
- Selected row: `acnc_register`, ordinal `1`, ABN `52000399744`
- Source SHA-256: `07b83ca8f241b23445818c2079883924929ecc5c72dd0aed04b10c3f8b5372fc` (4,086 bytes)
- Representation SHA-256: `1405b49e6dcf06b399f2b1e5f3a40b14f17051cdc318a336813159e80d76af82` (3,214 bytes)
- Acquisition receipt: `acq:ac1279c49bb36c9c31c3f2651ca9ad1369bb9fede9c6a32c58ac823bbc38cbae`
- Rights decision: `rights:private-provider:1405b49e6dcf06b399f2b1e5f3a40b14f17051cdc318a336813159e80d76af82`

The source is an independent `publicdata.au` API representation of the ACNC
register, version `2026-10-26`, under the observed CC BY 3.0 AU record. The
decision credits the Australian Charities and Not-for-profits Commission and
National Digital/publicdata.au. It does not claim ACNC-original CSV bytes: the
mirror's upstream CSV SHA-256 remains explicitly `mirror_claim_not_locally_verified`.

The new exact decision is bound to the source artifact, source record,
representation artifact/hash and scope. It records the governed private
processing policy `CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1` / `1.0.0`,
the existing OpenAI no-training/no-sharing policy identity, lawful public
access, no circumvention and no explicit prohibition. Public redistribution is
`not_assessed`; provider calls, publication and spend remain unauthorized/zero.

## Persisted metadata-only artifacts

- `evidence/gate4-t3-five-subject-v1/first-charity-publicdata-provider-rights-20261103.json`
- `evidence/gate4-t3-five-subject-v1/first-charity-publicdata-api-binding-20261026.json`

The retained raw response and normalized representation remain outside Git at
`C:\CharityGraph-runtime\g4-o1c-publicdata-acnc-register-20261103\`. No raw
bytes, base64 payload, credentials, provider output or private runtime state
was added to the repository. The existing T3 adapter consumed the exact local
source and normalized representation; no additional product fix was required.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts='' \
  --basetemp C:\CharityGraph-runtime\g4-o1c-rights-binding-20261103 \
  tests/test_phase5_t3_publicdata_rights_decision_real.py \
  tests/test_phase5_t3_source_evidence_binding.py \
  tests/test_source_rights.py \
  tests/test_phase5_t3_acnc_real_evidence_retention.py
48 passed

After the final rights-basis separation correction, the focused rights/binder
regression was rerun:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts='' \
  --basetemp C:\CharityGraph-runtime\g4-o1c-rights-final-20261103 \
  tests/test_phase5_t3_publicdata_rights_decision_real.py \
  tests/test_phase5_t3_source_evidence_binding.py \
  tests/test_source_rights.py
43 passed
```

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts='' \
  --basetemp C:\CharityGraph-runtime\g4-o1c-prior-publicdata-test-20261103 \
  tests/test_phase5_t3_publicdata_acnc_api_source.py
7 passed
```

The real T3 replay produced `BOUND` ordinal 1 with no deficits and a full
cohort result of `1 BOUND / 9 MISSING / 0 BLOCKED` across the ten selected
rows. The nine other rows remain explicit missingness; no sparse evidence was
substituted. No provider/model call, external acquisition, spending,
publication, release, GitHub/Drive mutation, watcher/process change or Gate 4
closure occurred. The prior untracked evidence and test paths, selected
manifest, Factory, CGDOC1 and bridge were preserved.

Next five-charity step: obtain and govern the selected 2025 AIS ordinal 2 for
this subject, then continue with the remaining four selected charities using
the same exact source/representation/acquisition/rights-bound path.
