# G4-O1C — ACNC original register mirror binding

**Date:** 2026-11-03 (Australia/Sydney)  
**Result:** `MISSING` — source acquisition was not performed

## Target

- Subject: `subject:02649cdcb42049bb8dedd30f2333e150`
- ABN: `52000399744`
- Selected target: `acnc_register`, ordinal `1`
- Manifest: `evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json`

## Acquisition outcome

The required original ACNC bytes were not available in the repository or
configured runtime workspace. The required expected source is the dated
`publicdata.au` `source.csv` mirror object, not `data.csv`; expected size is
`15156962` bytes and expected SHA-256 is
`1ff76b510e8155d7ab35df4b45b8791315c1f0a15f43f9c3057dff16646f816d`.

External-source access is outside this worker's safety boundary, so the mirror
and its manifest were not fetched. Consequently there is no verified source
size/hash, CSV row, source-lineage receipt, separate representation hash, or
retained source file. The existing selected manifest and CGDOC1 overlays were
left untouched.

## Binding and rights state

The target remains `MISSING`; no `BOUND` claim was made. No allowlisted JSON
retention or binding output was created. No source bytes, representations,
receipts, source records, or rights records were retained. Source rights and
attribution therefore remain unassessed for this capture. The 2025 AIS ordinal
2 remains `MISSING`; it was not substituted with the 2024 AIS.

No provider/model calls, spending, publication, or external mutation occurred.

## Verification

Focused provider-free regression:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider \
  --basetemp C:\CharityGraph-runtime\g4-o1c-acnc-binding-20261103 \
  tests/test_phase5_t3_acnc_real_evidence_retention.py \
  tests/test_phase5_t3_source_evidence_binding.py
```

Result: **14 passed**. No code change or test-output path was added to the
repository.

## Next bounded step

When external acquisition is permitted, fetch only the dated mirror's
original `source.csv`, verify the exact size and SHA-256 before parsing, extract
ABN `52000399744` with CSV-safe parsing, retain the full original bytes at the
single allowlisted source path, and then exercise the existing T3 adapter.
Proceed to the remaining four selected charities only after this first
register row genuinely binds.
