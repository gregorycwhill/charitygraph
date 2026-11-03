# Gate 4 P3b1 — source-subject provenance

Date: 2026-10-26 (Australia/Sydney)  
Mode: provider-free, local, bounded engineering report

## Disposition

**Closed in the allowed local path:** an available source record with an empty
`about_subject_ids` binding now fails closed as `mismatched` before rights
resolution or Factory lowering. The diagnostic identifies missing explicit
durable subject provenance; it is not reported as unavailable source or
fabricated evidence.

The reviewed canonical architecture permits zero, one, or multiple source
bindings as governed states, but no admitted source-family exception was found
that permits an unscoped source record to become available Factory material.
Explicit multi-subject binding remains accepted and is covered by the new
test. The separate rights-policy-version registry/identity gap from the prior
P3 acceptance remains open and was not changed.

## Control and preservation

- Branch: `gate3-cg406-remediation`
- HEAD unchanged: `8b7018f7507d52928d3e306bbf6f9d863f245937`
- HEAD tree unchanged: `514867d5cdfdb28ac81cc80815baae83ca91d02c`
- Active v26 fence SHA-256: `ce0d91b3b4584e87d0ce9f23c0525edfb93dc7cbc7b8a9646ac4c727bf01c97a`
- Independent P3 acceptance report SHA-256: `a6710ea5afa219cbce6f1d0bc8f0540ea57fc9d4f33f2beba3374ceca7977f39`
- Supplied pre-edit integration SHA-256 verified: `9c69e04a50f56ec7a9a6b1364aa7c36f4e7d9d3ad087e886bc3636ea3286fb89`
- New test and report were absent before action.
- Existing dirty/untracked paths were preserved. The forbidden
  `tests/test_phase5_governed_factory_rights.py` remained byte-identical:
  `dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281`.

## Allowed changes

1. `src/charitygraph/phase5_governed_factory_integration.py`: after source
   family validation, reject an empty durable `about_subject_ids` set with a
   `mismatched` diagnostic; existing matching, role, hash, receipt and
   representation lineage checks remain unchanged.
2. `tests/test_phase5_source_subject_provenance_p3b1.py`: new focused test
   path using the existing real file-backed fixture, SQLite catalogue, exact
   rights decision and fake provider/Factory path.
3. This report.

No rights-policy version resolution, provider, source acquisition, spend,
publication, release, GitHub, bridge, watcher or process state was changed.

## Test evidence

Focused command:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3b1-source-subject-provenance-20261026-focused-03 tests/test_phase5_source_subject_provenance_p3b1.py
```

Result: **2 passed**.

Required prior P3 suite plus new suite:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3b1-source-subject-provenance-20261026-full-05 tests/test_source_rights.py tests/test_phase5_governed_factory_rights.py tests/test_phase5_governed_factory_integration.py tests/test_phase5_factory.py tests/runtime/test_task_state.py tests/test_phase5_source_subject_provenance_p3b1.py
```

Result: **68 passed** (the prior 66 plus 2 new tests).

The new cases independently verified:

- empty source-record subject binding: rejected as `mismatched`, with zero
  `tasks`, `physical_attempts`, `provider_receipts`, `budget_reservations`,
  `cost_entries` and `provider_request_attempts`;
- cross-subject source binding: rejected independently;
- accepted explicitly bound peer: one task, one physical attempt, one fake
  provider receipt, one reservation, two reconciled cost entries, and
  `AUD 0.002000` actual spend; restart/re-entry produced no additional work;
- a source explicitly bound to two subjects: both matching subject references
  were accepted independently.

No real provider request occurred; the positive path used the repository's fake
provider. Temporary databases and pytest basetemps were outside the checkout
under `C:\CharityGraph-runtime`.

## Final hashes

```text
7140efddfbea3077ab74b715bf1cbee8454b928d1e3d984da8bca4811eb9ba8d  src/charitygraph/phase5_governed_factory_integration.py
41bb23e49f22e63b0f5fc6fd0b69babf508389292e2b9469f2992e43f0866cae  tests/test_phase5_source_subject_provenance_p3b1.py
dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281  tests/test_phase5_governed_factory_rights.py
```

No private evidence, runtime database, cache, provider payload, credential or
log was added to the repository. No staging, commit, reset, checkout,
publication, release or Gate 4 closure was performed.
