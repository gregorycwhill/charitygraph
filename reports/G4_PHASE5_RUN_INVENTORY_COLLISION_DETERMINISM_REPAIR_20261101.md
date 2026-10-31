# G4-O1C Phase-5 collision determinism repair

Date: 2026-11-01 (Australia/Sydney)  
Task: deterministic suffixes for same-key Phase-5 run-inventory audit collisions

## Result

Repaired the collision ordering defect at exact starting HEAD `70069adbc0e3d136786ef699f6cf84a66cac3786`.
Normalized run records are sorted by canonical bytes, and normalized sources are ordered by their stable source key and canonical normalized content before per-key `#1`, `#2`, ... suffixes are assigned. Exact duplicates remain separate records; suffixes are applied only to actual collision groups.

The audit remains strictly fail-closed: `NOT_AUTHORITATIVE` / `UNVERIFIED`, `project_wide_authoritative=false`, `authoritative_total=null`, and `remaining_spend=null`. No cost authority or provider-send path was changed.

## Counterexample

Two sources with the same `source_id`, role and digest, carrying `run:a` and `run:b` respectively:

- Before: `[run:a, run:b]` assigned `#1=run:a`, `#2=run:b`; reversed input assigned `#1=run:b`, `#2=run:a`.
- Before SHA-256: `fd5b9f892af45574b96d2cbf8c649f2f94947435039fc0083d781bfa583f246f` versus `c72bc03418642e60061da20d462c80e190add668c661dea1b5fd6e598980d82e`.
- After: both permutations assign `#1=run:a`, `#2=run:b` and produce byte-identical canonical output with SHA-256 `fd5b9f892af45574b96d2cbf8c649f2f94947435039fc0083d781bfa583f246f`.

Regression coverage includes two- and three-way collisions, exact duplicate records, reversed input, stable SHA, source-identity conflict, duplicate/conflicting metadata, and same-source false-independence reporting.

## Verification

Commands used cache-free with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and basetemp outside the checkout:

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-o1c-collision-repair-focused-final-20261101 tests/test_phase5_run_inventory_audit.py
21 passed in 0.77s

python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-o1c-collision-repair-related-final-20261101 tests/test_phase5_project_cost_reconciliation.py tests/test_phase5_operator_health.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_operator_health_runtime_contract.py
73 passed in 5.54s
```

Total: **94 passed**. No full-repository suite was run.

Only these allowlisted paths were changed or created:

- `src/charitygraph/phase5_run_inventory_audit.py`
- `tests/test_phase5_run_inventory_audit.py`
- `reports/G4_PHASE5_RUN_INVENTORY_COLLISION_DETERMINISM_REPAIR_20261101.md`

No unrelated pre-existing dirty paths were edited. No provider/model calls, source acquisition, spend, Drive/bridge operation, GitHub mutation, publication, release, gate closure or follow-on dispatch occurred. No raw provider payload or private evidence was added.

The real-world gap remains unchanged: there is still no independently authenticated, source-owned complete cumulative provider-run inventory with independently verified receipt, invoice, pricing/FX and exactly-once evidence. Observed IDs remain diagnostic subsets only; project-wide total and remaining spend are not established.
