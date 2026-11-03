# G4 Builder operator-health catalogue independent acceptance

Date: 2026-10-31 (Australia/Sydney)
Decision: **PARTIAL acceptance of the bounded local adapter; Gate 4 remains open.**

Scope was the exact bridge-owned direct child
`gate3-cg406-remediation@799c85cabfd72cb436d96c54eb477eecc3d0f30c`, parent
`a058df5cc97787947cb4de0629162729c4f9da72`, under task-supplied immutable fence
v80 SHA-256 `b09ca2fde4228cea4c5a2e5d4071c9e1b7cc857696c85e11559fd7c8cea6b3f4`.
I read the Builder authority/machinery documents and the sibling Data
`DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, `BUILDER_TO_65K_PLAN.md`, source,
cost, integrated-model, taxonomy, implementation and test authorities. This
was local, provider-free acceptance only.

## Commit and boundary

The commit has exactly and only these five paths:

1. `src/charitygraph/phase5_operator_health.py`
2. `src/charitygraph/phase5_operator_health_catalogue.py`
3. `tests/test_phase5_operator_health.py`
4. `tests/test_phase5_operator_health_catalogue.py`
5. `reports/G4_BUILDER_OPERATOR_HEALTH_CATALOGUE_ADAPTER_20261031.md`

`git diff --check parent..HEAD` was clean. The bridge terminal result in
`runtime/g4-o1b-controlled-cutover-20261020/status.json` verifies the exact
HEAD/parent, `unexpected_paths=[]`, `baseline_preserved=true`,
`provider_calls=0`, `source_acquisition=false`, `publication=false`, and
`product_accepted=false`. Pre-existing dirty Factory/T4A/T4E, evidence,
report, host and bridge paths were not edited or absorbed. The five current
working-tree files match their HEAD blob IDs and have these SHA-256 values:

| Path | SHA-256 |
|---|---|
| `phase5_operator_health.py` | `a95eadc5440b89dd5d8eb2ce1c1d7fe2f55734b657cdf8626a36c2accd94a00a` |
| `phase5_operator_health_catalogue.py` | `f9bc479d71e146d484f537558ec146b7c73ca47e5d8d57b517eb09df2de15587` |
| `test_phase5_operator_health.py` | `1224e6bfd5c2e418de3e4d81dbcb1826618e710154362ffd513bfb8b323ee53c` |
| `test_phase5_operator_health_catalogue.py` | `18cedd9c54d21d36b06667564efb7b2625b14c8dcbcde2d5e015957fdab319ab` |
| prior adapter report | `1a3d940a49b27b0312da9a9cb662f2ae1334b11369a5561b591bd3d20aea30cf` |

## Verification

With `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and a fresh external
basetemp under `C:\CharityGraph-runtime`, the focused and regression set passed
**95 tests**: operator health, catalogue adapter, Phase-5 delivery, run
diagnostics, persisted diagnostics catalogue, standard transport and runtime
budget ledger.

Independent probes passed for:

- mixed-subject/scope selection, run scoping, exact source lineage and
  caller-supplied as-of/window provenance;
- parameterised run selection resisting a SQL-injection identifier;
- SQLite `query_only=1`, write/migration rejection, and no adapter migration;
- absent/incomplete schema and missing requested-run coverage states;
- identified identical/conflicting receipt and reservation replay handling;
- unidentifiable receipt replays failing closed for usage and actual cost;
- missing release versus explicit zero release;
- Decimal arithmetic, currency and pricing/FX provenance retention;
- order-independent canonical JSON and SHA-256; and
- absence of raw provider payload/reference capture in the projected document.

The adapter reads persisted Phase-5 tables through bounded allowlisted reads
(`phase5_operator_health_catalogue.py:35-60, 191-242, 244-346`), not caller-
supplied snapshots. It preserves selected run, subject, scope, source and
timestamp lineage and delegates diagnostics to the pure observer. Persisted
`cost_entries` have no provider-receipt identity; the adapter correctly leaves
their actual cost ambiguous/non-observed rather than deriving identity from an
entry key or row position (`phase5_operator_health_catalogue.py:57-60, 327-364`;
`phase5_operator_health.py:465-476`).

## Claim classification

| Claim | Result | Evidence and boundary |
|---|---|---|
| Exact five-path direct-child commit and dirty-baseline preservation | **PASS** | Commit tree, bridge result, hashes and `diff --check` above. |
| Deterministic status, throughput, latency, scheduling and run-scoped provenance | **PASS, bounded** | `phase5_operator_health.py:336-384, 557-624`; fresh tests/probes. Only explicit durable timestamps and supplied rows are measured. |
| Identified receipt/reservation deduplication and conflicting-identity fail-closed behaviour | **PASS** | `phase5_operator_health.py:214-248, 438-505`; fresh duplicate/conflict probes. This is local aggregation, not provider exactly-once evidence. |
| Unidentifiable receipt replays and receipt-less actual costs remain ambiguous | **PASS** | `phase5_operator_health.py:642-682` and `:465-476`; fresh probes. |
| Missing/stale/incomplete project ledger does not become zero | **PASS** | `phase5_operator_health.py:398-418, 527-554`; fresh ledger probes. |
| Decimal/currency/pricing/FX provenance | **PARTIAL** | Exact decimals and IDs are retained (`:387-395, 449-464`), but rates and external pricing/FX validity are not independently verified. |
| Malformed `usage_json` fails closed | **FAIL** | Adapter records `INVALID_USAGE_JSON` at `phase5_operator_health_catalogue.py:82-99`, but returns no usage fields; `_token_count` treats absent fields as zero (`phase5_operator_health.py:593-612`), yielding `state=observed`, `input_tokens=0`, `output_tokens=0`, not ambiguous/null. This contradicts the prior adapter report’s no-fabricated-zero claim. |
| Canonical JSON/SHA and raw-payload exclusion | **PASS, bounded** | Canonical serialization `phase5_operator_health.py:686-704`; adapter allowlist `:49-60, 82-99`; fresh order/payload probes. |
| Live runtime wiring, provider-side exactly-once effects, source-owned rights/route authority, verified price/FX, and cumulative project-wide AUD ledger completeness | **FAIL / not established** | The code is a read-only diagnostic over supplied/persisted local rows. No provider, source, rights, route, live-wiring or project-wide completeness operation was authorised or performed. These are industrialisation claims, not inferred from passing local tests. |

## Residual defect and next bounded task

The highest-value next local task is to propagate malformed or incomplete usage
parsing as an explicit ambiguous/non-observed usage state with null token totals,
then add a regression covering malformed JSON and missing token fields. It must
remain provider-free and preserve raw-payload minimisation. A later, separately
authorised task can assess live wiring and cumulative ledger completeness; this
review does not establish either.

The canonical Builder-to-65k scorecard is unchanged by this opportunistic
engineering evidence: Gate 1 CLOSED, Gate 2 ACTIVE, 12% earned; Gate 4 is not
earned and remains open. The verified terminal record reports zero provider
calls for that engineering execution; this is not a claim of zero cumulative
project expenditure. No provider call, source acquisition, reservation, spend,
publication, release, GitHub, watcher, bridge or follow-on action occurred in
this acceptance. No private source material, prompts, model responses,
credentials, runtime cache or raw provider payload was written to Git.
