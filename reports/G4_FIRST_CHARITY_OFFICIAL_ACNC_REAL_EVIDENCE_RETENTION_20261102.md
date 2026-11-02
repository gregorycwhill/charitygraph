# G4-O1C — first official ACNC source retention

**Date:** 2026-11-02  
**Result:** `NOT RETAINED — official source bytes unavailable`

## Scope

The first manifest subject was selected without inventing an identity:

- ABN `52000399744` — `subject:02649cdcb42049bb8dedd30f2333e150`
- selected rows: `acnc_register` ordinal 1 and `acnc_ais_bundle` ordinal 2
- existing manifest: `evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json`
- selected manifest summary: 5 subjects, 10 metadata rows, `source_bytes_included=false`, 0 eligible private-retention rows

The existing runtime JSON for this subject was not reused: it is a derived ACNC API representation, not the required source-native bulk register/AIS download with an independently retained download hash.

## Acquisition result

The official publication page was checked:  
`https://www.acnc.gov.au/charity/about-charity-register/download-charity-register-data`

It identifies the official data.gov.au catalogue as the source for the regularly updated Charity Register dataset and annual AIS datasets. The first subject’s intended reporting-year AIS is the 2025 period (the existing derived representation records `StatementYear=2025` and `FinReportFrom=2024-07-01`, `FinReportTo=2025-06-30`).

The official raw resource could not be acquired from this worker:

- data.gov.au direct download/API access failed with connection errors (`curl`: unable to connect to `data.gov.au:443`);
- the official register landing page is known as `https://data.gov.au/data/dataset/b050b242-4487-4306-abf5-07ca073e5594`, but the exact current resource URL and bytes were not retrievable;
- the exact 2025 AIS resource URL and bytes were not retrievable;
- therefore original-download SHA-256, selected raw row bytes/base64, exact row hashes, extraction lineage, and acquisition receipt cannot be produced;
- no exact source-specific licence/local-retention evidence for the captured rows was verified. General ACNC reuse language and independent republications were not treated as evidence for these bytes.

Counts for this task: **0/2 source rows retained or bound; 2/2 missing at acquisition; 0 candidate files created; 0 provider/model calls; 0 public-rights assessments.** Provider processing remains blocked and public redistribution remains not assessed.

No file was created at `evidence/gate4-t3-five-subject-v1/first-charity-official-acnc-source-retention-v1.json` because the retention contract was not met. No raw source, cache, snapshot, or private material was added to the repository.

## Verification and next step

Focused checks passed: `pytest -q tests/test_phase5_t3_acnc_real_evidence_retention.py tests/test_phase5_t3_source_evidence_binding.py` — **14 passed**.

The next bounded step is to acquire the same official current Charity Register resource and exact 2025 AIS resource for ABN `52000399744`, retain and independently hash both complete downloads plus their selected rows, then proceed in manifest order for the remaining four ABNs only after the first pair satisfies the adapter contract.
