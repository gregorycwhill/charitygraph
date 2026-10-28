# G4-O1C T2 clean factory reconstruction

Date: 2026-10-29 (Australia/Sydney)  
Target: `gate3-cg406-remediation@700cfe1f4e576e00471155a6bfedbcc40fc36cab`  
Fence: v43  
Mode: local, provider-free, synthetic TEST fixtures only

## Implementation

Added only the two fresh T2 paths:

- `src/charitygraph/phase5_governed_cohort_rehearsal.py`
- `tests/test_phase5_governed_cohort_rehearsal.py`

The fixture creates explicitly labelled TEST subjects, scopes, source-native
records, representations, acquisition receipts, and content-addressed
rights records. The exercised chain is the clean HEAD
`RightsGovernanceStore` → v29 `rights_projection_current` → governed-rights
preflight → `FactoryPlan`/`ReferenceFactory` → SQLite task/attempt/receipt/
reservation/cost rows → pure allowlisted diagnostics projection. No new rights
authority, Factory, scraper, semantic inference, source, provider or network
path was added.

## Clean-surface verification

An exact read-only `git archive HEAD` was exported to:
`C:\Users\grego\AppData\Local\Temp\charitygraph-g4t2-clean-13e9acdd34af4535b734dd8fe2da63ab`.
Only the two candidate files were overlaid. Tests used
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`, `-p no:cacheprovider`,
`-o addopts=`, and an external basetemp. The import probe reported
`CLEAN_IMPORT_BOUNDARY_OK`: no `rights_decision_ids` field and no
`get_artifact_rights_decisions`; the SQLite schema contained v29 rights
projection tables and no `artifact_rights_*` tables.

Exact focused command result:

```text
python -m pytest -p no:cacheprovider -o addopts= --basetemp <outside-checkouts> -ra tests/test_phase5_governed_cohort_rehearsal.py
6 passed in 6.22s
0 skipped
```

Coverage includes deterministic task/request identity, denial and projection
mismatch with zero tasks/attempts/reservations/receipts/cost entries, standard
failure isolation, batch planning with zero batch sends, ambiguous crossing
held for explicit reconciliation without resend, replay with zero new sends,
stable diagnostic SHA, and persisted accounting identities.

## Persisted identity evidence

The successful replay fixture recorded:

- task: `modeltask:4bd41da86ad2abe400acc5a7b787c24b154dce4c77fc211c5c19e443efc83793`
- attempt: `taskrun:be9ecf1fba874d2f93f9c71a8f087c2fec3acd1c33565bb9b32f1c795be5ae30`
- physical request: `fake-package-request:dc896f83c61ddf611dd039f5b065cb762402779fc4162fce00c64438d7c5f0f9`
- receipt: `fake-receipt:99d81e641b31cf613acfac6457a8211337cec6a0caa6afe664a6354d807926af`
- reservation: `reservation:133291d28e270ba78015b4b28ec29062e0ec354959f58375fc2fb21926d3d398`
- cost entries: `actual:<reservation>` and `release:<reservation>`; AUD `0.002000` actual, `0.008000` released
- diagnostic SHA: `1f1bd9924db0988d6a890213fc4e11536572e90d90be7e6fa3af55d235a07474`

## Preservation and limits

A read-only two-pass SHA/length comparison covered 308 pre-existing dirty or
untracked files and reported `PREEXISTING_BYTE_STABILITY_OK`. The quarantined
offline rehearsal, its test, prior report, dirty tracked modules, evidence,
runtime state, and caches were not imported, copied, modified, staged, or
promoted. No private material was added.

This is synthetic control-plane evidence only. It does not establish T3
rights determinations, real subject/source binding, provider readiness,
provider-side exactly-once behaviour, semantic quality, acquisition,
publication, release, or gate closure.

The one permitted local-only commit was not creatable: explicit staging of
these three fresh paths failed before any index write with
`Unable to create .git/index.lock: Permission denied`. No commit, GitHub
mutation, or unrelated staging occurred. The smallest remedy is a local
checkout permission that permits the normal Git index-lock operation.
