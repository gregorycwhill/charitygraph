# Phase-5 source-owned run inventory audit

Date: 2026-11-01 (Australia/Sydney)
Task: bounded G4-O1C, provider-free local audit
Result: **implemented; observed subset useful, project-wide authority unverified**

## What is present

The repository contains these existing Phase-5 seams:

- `phase5_operator_health_catalogue.py`: a read-only, immutable/query-only
  SQLite adapter over explicitly selected run IDs. Its source lineage and
  timestamps describe the supplied catalogue snapshot; they do not establish
  historical or provider-side population completeness.
- `phase5_operator_health_runtime_contract.py`: a contract harness over that
  same catalogue snapshot. The acceptance evidence dated 2026-10-31 is
  provider-free and fixture-backed, with no independently authenticated second
  run-population ingress.
- `phase5_project_cost_reconciliation.py`: the existing cost projection now
  rejects missing, caller-forged, project-wide-shaped and duplicate population
  manifests as trusted authority. Its current safe outcome is
  `MISSING_TRUSTED_RUN_INVENTORY`, with no authoritative total or remaining
  spend.
- The local bridge instruction ledger and its runtime instruction/result files
  are engineering transport records. They are not provider run IDs and are not
  a source-owned project history. Existing reports dated 2026-10-31 and
  2026-11-01 explicitly describe the runtime export and cost manifests as
  bounded or synthetic.

No independently captured, authenticated, complete source-owned run index or
provider-receipt population was found in the local repository. No source-owned
capture timestamp, source byte hash/durable evidence digest, completeness
attestation, invoice, pricing or FX record was available for project-wide
reconciliation. This audit therefore does not claim a real source population.

## Change

Added exactly the requested three paths:

- `src/charitygraph/phase5_run_inventory_audit.py`
- `tests/test_phase5_run_inventory_audit.py`
- this report

The new pure projection accepts already-captured source records and preserves
source role/identity, byte SHA-256 or stable evidence digest, observation time,
scope, schema version, missingness, provenance and observed run IDs. It compares
sorted unique IDs across sources and reports omitted, orphaned, duplicate and
conflicting IDs, source identity mismatch, stale/malformed evidence, source
silence, unknown receipt run IDs and same-source false independence. It emits no
raw provider payload.

Caller-supplied `source_owned`, `authenticated`, `complete` or attestation
fields remain unverified observations. The result is always
`NOT_AUTHORITATIVE`/`UNVERIFIED`, with `project_wide_authoritative=false`,
`authoritative_total=null` and `remaining_spend=null`. Existing cost authority
and send paths were not changed.

## Verification

Focused command:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-o1c-run-inventory-focused-20261101 tests\test_phase5_run_inventory_audit.py
```

Result: **18 passed**.

The final focused-plus-regression command ran the new audit with the existing
project-cost reconciliation and operator-health/catalogue/runtime-contract
tests: **91 passed** in total.

Final working-tree SHA-256 values:

```text
9c0c5e658d2965b34c1b9f9eb932b07ae106d05a4f7f1b9f738bdecc75bccd84  src/charitygraph/phase5_run_inventory_audit.py
7da57cd40c5286f1c6027722fb7174657a9c95ca9837d354bef5fcd51e86877e  tests/test_phase5_run_inventory_audit.py
```

The focused fixtures cover self-declared and forged completeness, omitted and
orphaned IDs, duplicates, conflicting metadata, source mismatch, same-source
false independence, missing digest, stale/malformed schema, stale evidence,
source silence, unknown provider receipts, bridge/local-history rejection,
deterministic order, raw-payload exclusion and preservation of a known observed
subset. No provider, model, external source, Drive, bridge, watcher, database
or credential was accessed or modified. Existing dirty paths were not edited.

## Limitation and next source capture

The next concrete integration is an independently authenticated, immutable
source-owned capture of the cumulative run index and provider-receipt
population. It must bind source identity and exact bytes/digest, acquisition and
observation timestamps, schema version, bounded/project scope, missingness and
an externally proven completeness boundary. A narrow read-only adapter can then
feed this comparison seam. Until that capture exists, observed IDs are useful
subsets only; no project-wide spend or AUD 10 remainder is defensible.
