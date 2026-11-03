# G4-O1C — first real charity publicdata.au local source ingest

Date: 2026-11-03 (Australia/Sydney)  
Result: **retained; governed binding remains `MISSING`**

## Target and retained source

- Subject: `subject:02649cdcb42049bb8dedd30f2333e150`
- Scope: `scope:0a10077aee9363200199a815e8198f3807fef97737ad89bfd1e2e17f61d63248`
- ABN/name: `52000399744` / Guide Dogs NSW/ACT
- Selected source: `acnc_register`, ordinal 1
- Transport schema: `charitygraph.private-source-transport/v1`
- Source kind: independent `publicdata.au` API representation of the ACNC register
- Version: `2026-10-26`; one exact row; CC-BY-3.0-AU

The supplied local transport was verified without network access. Its exact
`http_body_utf8` bytes were materialised at:
`C:\CharityGraph-runtime\g4-o1c-publicdata-acnc-register-20261103\raw-response.json`

- Bytes: `4086`
- SHA-256: `07b83ca8f241b23445818c2079883924929ecc5c72dd0aed04b10c3f8b5372fc`
- Normalized representation: `C:\CharityGraph-runtime\g4-o1c-publicdata-acnc-register-20261103\normalized-representation.json`
- Normalized representation SHA-256: `1405b49e6dcf06b399f2b1e5f3a40b14f17051cdc318a336813159e80d76af82`

The upstream CSV SHA-256 `1ff76b510e8155d7ab35df4b45b8791315c1f0a15f43f9c3057dff16646f816d`
and `15156962` bytes are retained only as the transport's explicit mirror
claim. They were not locally verified and are not treated as publisher-original
bytes. Source, receipt, representation, currentness and rights lineage are
recorded in [the metadata-only binding artifact](../evidence/gate4-t3-five-subject-v1/first-charity-official-acnc-source-retention-v1.json).

## Binding and rights

The T3 adapter now validates this bounded equivalent-register transport and
labels it as a third-party API representation, while preserving the admitted
`acnc_register` family. The existing source-evidence binder was exercised
against the retained source and then reloaded from the persisted raw and
normalized files.

Binding result: `MISSING`, `bound_count=0`, reason:
`private_provider_processing_rights_decision_not_observed`.

Local retention is authorized under the existing bounded policy. Private
provider processing remains `blocked`; public redistribution remains
`not_assessed`. No `BOUND` claim was made merely because the API returned a
row. Currentness is limited to the observed versioned source snapshot captured
on 2026-11-03.

The 2025 AIS target, ordinal 2, remains `MISSING`; 2024 was not substituted.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider \
  --basetemp C:\CharityGraph-runtime\g4-o1c-publicdata-pytest-20261103 \
  tests/test_phase5_t3_publicdata_acnc_api_source.py \
  tests/test_phase5_t3_acnc_real_evidence_retention.py \
  tests/test_phase5_t3_source_evidence_binding.py
21 passed

PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider \
  --basetemp C:\CharityGraph-runtime\g4-o1c-factory-pytest-20261103 \
  tests/test_phase5_factory.py \
  tests/test_phase5_governed_factory_integration.py \
  tests/test_phase5_t3_exact_representation_rights_binding.py
26 passed
```

No provider/model calls, external acquisition, spending, publication, release,
GitHub/Drive mutation, watcher/process change or gate closure occurred. Raw
and normalized private material remain outside Git; the repository artifact is
metadata-only. Existing selected-manifest, CGDOC1 overlay, Factory and bridge
worktree changes were preserved.

Next bounded step: obtain a separately governed 2025 AIS transport/source
artifact, verify its exact identity and rights, and bind it only if it matches
the selected subject/scope and reporting year.
