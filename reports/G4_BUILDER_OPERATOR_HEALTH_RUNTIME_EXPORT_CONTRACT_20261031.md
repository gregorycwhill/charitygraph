# G4 Builder operator-health runtime export contract

Date: 2026-10-31 (Australia/Sydney)  
Result: **PASS for the bounded local contract harness; PARTIAL for industrialisation evidence.**

## Scope and boundary

At starting HEAD `c9e349f17b28eab34fc6c57aad9082130d6456d7` and immutable v81
fence SHA-256
`6fe67a0a0dca949b92d81f028d9615b9721e9a777f57e9792b082cbbc7161879`, this
task added a provider-free harness around the existing
`Phase5OperatorHealthCatalogueAdapter.project()` read-only SQLite seam. It
does not add a reader, database, schema, source, model task, semantic rule or
parallel exporter.

Changed paths are exactly:

- `src/charitygraph/phase5_operator_health_runtime_contract.py`
- `tests/test_phase5_operator_health_runtime_contract.py`
- this report

The pre-existing dirty Factory/T4A/T4E, evidence, reports and unrelated paths
were not edited, staged or reset.

## Contract evidence

The harness calls the real persisted export, captures its safe allowlisted rows,
and compares the export's delegated operator-health bytes with a second direct
`project_operator_health` call over the same snapshot. It covers:

- exact run/request/task plus subject/scope/source lineage;
- explicit as-of and reporting-window timestamps;
- stalled, retry, failure and recovery indicators;
- canonical JSON/SHA stability when fixture insertion order is reversed;
- missing and malformed usage versus an observed explicit `0/0`;
- duplicate/conflicting and unidentifiable receipt identities;
- payload/reference exclusion (`PROMPT_SENTINEL`, `SOURCE_SENTINEL`,
  `RAW_RESULT_SENTINEL` and `RESULT_REF_SENTINEL` absent from the contract);
- actual, committed-reserved and forecast cost missingness, plus ledger,
  pricing and FX provenance.

The persisted cost safe view intentionally lacks provider receipt identity.
Accordingly the fixture's actual/reserved/forecast amounts remain
`ambiguous`/null in the persisted contract; no spend total is fabricated. A
direct supplied snapshot with complete receipt identity and provenance remains
tested separately, including unidentifiable actual cost fail-closed behavior.

SQLite sidecar hashes were unchanged across the harness call. No network,
provider, Drive, source, credential, payload, prompt, response body, cache,
runtime state or private evidence was written to Git.

## Verification

Cache-free isolated command:

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-o1c-runtime-contract-regression-20261031 tests/test_phase5_operator_health_runtime_contract.py tests/test_phase5_operator_health.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_delivery.py tests/test_phase5_run_diagnostics.py tests/runtime/test_phase5_run_diagnostics_catalog.py tests/test_phase5_standard_transport.py tests/runtime/test_budget_ledger.py
```

Exact result: **111 passed in 21.22s**. New harness subset: **6 passed in
1.47s**. `git diff --check` passed for both new code/test paths.

SHA-256:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_operator_health_runtime_contract.py` | `A0D0A80F1353AE79DE1AB2880684FA54B418A2E617FDBF51DDC7A403548F109C` |
| `tests/test_phase5_operator_health_runtime_contract.py` | `7AD52EA4529A7B1A90FFDD3AF79B56C9F9341A15AD4323D671D65B50360B5C77` |

## Acceptance classification and residual gaps

| Claim | Result | Boundary |
|---|---|---|
| Existing read-only runtime export agrees with direct operator health | **PASS, bounded** | Synthetic SQLite fixture; no live provider crossing. |
| Identity, timestamps, health flags, missingness and safe representation | **PASS, bounded** | Supplied persisted rows only; no project-wide completeness inferred. |
| Cost non-inference and provenance | **PASS, fail-closed** | Missing/ambiguous cumulative ledger, receipt identity, pricing or FX stays null/ambiguous; no forced zero. |
| Live provider/runtime wiring, provider-side exactly-once effects and route policy | **NOT ESTABLISHED** | No provider or external-source access was authorised or performed. |
| Source rights/T3 permission and cumulative project economics | **NOT ESTABLISHED** | T3 `bound_not_task_eligible` is not treated as permission; no ledger or rights decision is invented. |
| Gate 4 closure or scorecard progress | **NOT CLAIMED** | This is opportunistic Gate 4 evidence only; Gate 1 remains CLOSED, Gate 2 ACTIVE, 12% earned. |

The next separately authorised industrialisation slice is live wiring/provider-
policy, rights and cumulative-ledger acceptance; it is not performed or
dispatched by this worker.
