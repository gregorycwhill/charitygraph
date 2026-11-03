# G4-O1C Phase-5 run-inventory audit — independent acceptance

Date: 2026-11-01 (Australia/Sydney)  
Result: **PARTIAL for code semantics; FAIL/UNKNOWN for real-world inventory authority**

## Scope and baseline

- Branch: `gate3-cg406-remediation`
- Exact HEAD: `70069adbc0e3d136786ef699f6cf84a66cac3786`
- Parent: `7654e9c8ccb370f9fa4f3cd43fdd50a76ede477f`
- Fence: v90, SHA-256 `218a83ddb1f313c666ca8f31602ec174f242178814d2efaacc116cdea228707e`
- The direct-child diff contains exactly the three claimed paths: the new audit module, its focused test, and the source-owned audit report. The substantial unrelated dirty/untracked baseline was inspected and preserved.

I read the local agent, architecture, machinery and supervisor-protocol instructions; the sibling Data authority/current-state/roadmap/implementation/test and governing evidence documents; the exact diff; the new source, tests and report; the existing project-cost reconciliation; and the Phase-5 catalogue/runtime-export contracts.

## Code-semantics review

**PARTIAL.** The core safety properties independently pass:

- Caller-provided `source_owned`, `authenticated`, `complete`, attestation-shaped fields, project-wide scope, totals or remainder values never create authority. Results remain `NOT_AUTHORITATIVE`/`UNVERIFIED`, with `project_wide_authoritative=false`, `authoritative_total=null` and `remaining_spend=null`.
- Same-source views are grouped as false independence. Omitted IDs known from the supplied union, orphaned IDs, duplicates, conflicting metadata, identity mismatch, malformed/stale schema, missing digest, stale evidence, source silence, unknown receipt IDs, sorted observed subsets and raw-payload exclusion are surfaced without guessing.
- Bridge instruction-ledger IDs and local SQLite run IDs are explicitly rejected as provider history. The module has no import or call path to the cost-reconciliation or provider-send code, and the direct-child diff modified no existing cost authority/send path.

The additional independent determinism probe found a defect not covered by the 18 focused tests: when two records share the same source key (same source ID, role and digest) but carry different run IDs, the `#1`/`#2` collision suffix is assigned in caller order. Reversing input changes the canonical document and SHA-256. The supplied collision test uses different evidence digests and therefore does not exercise this case. This prevents a full code-semantics PASS; no source/test file was changed under the report-only write boundary.

## Independent tests

All tests ran from a disposable exact-HEAD `git archive` overlay outside the live checkout, with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and basetemp outside the repository.

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-o1c-run-inventory-focused-20261101-v2 tests/test_phase5_run_inventory_audit.py
18 passed in 1.30s

python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-o1c-run-inventory-related-exact-20261101 tests/test_phase5_project_cost_reconciliation.py tests/test_phase5_operator_health.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_operator_health_runtime_contract.py
73 passed in 5.63s
```

Required focused-plus-related total: **91 passed**. An additional bounded run including `tests/runtime/test_phase5_run_diagnostics_catalog.py` also passed **82 tests** in the five-file related set. No full-repository or network suite was run. The extra deterministic collision probe failed as described above.

## Real-world authority

**FAIL for acceptance; UNKNOWN in fact.** No independently captured, authenticated, source-owned complete historical provider-run inventory was present locally. No actual historical provider population, invoice, provider pricing/FX record, or exactly-once evidence was acquired or verified. The bridge ledger is local engineering transport state, not provider run history. The 175-complete ledger claim therefore cannot be used as source-owned inventory authority, and no project-wide total or remaining spend is established.

No provider/model call, acquisition, spend, Drive/bridge operation, publication, GitHub mutation, release, gate closure or follow-on dispatch occurred. No speculative completeness promotion or scorecard credit is granted; the canonical Builder scorecard remains 12% Gate2 ACTIVE.

## Next bounded substantive task

Capture, through an independently authenticated read-only source adapter, the cumulative source-owned run index and provider-receipt population. Bind immutable bytes/digest, source identity, acquisition and observation times, schema and scope, explicit missingness, a proven completeness boundary, exactly-once evidence, and invoice/pricing/FX evidence. Then feed that captured evidence into this comparison seam and the existing cost authority under a separate bounded acceptance task. Until then, observed IDs remain useful subsets only.
