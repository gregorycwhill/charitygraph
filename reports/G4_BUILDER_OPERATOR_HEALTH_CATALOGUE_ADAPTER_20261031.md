# G4 Builder operator-health catalogue adapter

Date: 2026-10-31 (Australia/Sydney)
Worker: bounded G4-O1C, local/provider-free
Target: `gate3-cg406-remediation@a058df5cc97787947cb4de0629162729c4f9da72`
Fence: v79, SHA-256 `cf8e4d5bcd3347f2edb775dcebb2d39a703f72e7fb86eefb15fb2a66e969495f`

## Verdict

**PASS for the bounded read-only adapter and receipt fail-closed repair; PARTIAL
for overall operator-health authority.** Gate 4 remains open. The canonical
Builder-to-65k state is unchanged: Gate 1 CLOSED, Gate 2 ACTIVE, 12% earned.

## Implemented

- Added `phase5_operator_health_catalogue.py`, accepting an explicit SQLite path
  or connection, explicit run IDs, and explicit timezone-aware as-of/window
  timestamps.
- Reads only the existing persisted Phase-5 operational tables through bounded,
  parameterised queries. It uses SQLite read-only/`query_only` controls, does
  not migrate or write, and does not call providers or networks.
- Preserves run, request, task, subject, scope, catalogue source lineage and
  timestamp provenance in a structured snapshot and canonical integrated
  diagnostic. Missing runs, tables, columns, unsupported schema versions and
  usage JSON are explicit coverage issues; they do not become fabricated zeroes.
- Projects only safe operational fields and the two required token counts from
  receipt usage JSON; provider payload/reference fields are not captured.
- Changed the pure diagnostic so receipt rows without `provider_receipt_id` or
  `receipt_id` produce `UNIDENTIFIABLE_RECEIPT_IDENTITY`, ambiguous usage with
  null token totals, and no observed actual-cost total. Identified identical
  receipt/reservation replays retain existing deduplication behaviour.

## Verification

All pytest runs used `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and an
external basetemp under `C:\CharityGraph-runtime`.

| Check | Result |
|---|---:|
| Operator health + catalogue adapter | 27 passed |
| Phase-5 delivery, run diagnostics, persisted catalogue, transport and accounting regressions | 86 passed |
| Budget/cost-cap regressions | 44 passed |
| **Total executed** | **157 passed** |

The adapter tests cover bounded selection with mixed subjects/scopes, exact
source lineage, canonical JSON/SHA stability, read-only path and connection
operation, query-only write rejection, incomplete schema, missing requested
runs, explicit time windows, provider-free operation, and no payload capture.
The health tests cover unidentifiable receipt replay ambiguity, identified
receipt deduplication, explicit zero versus missing release evidence, and
missing/stale ledger behaviour.

`git diff --check` is clean for the allowlisted edited paths. Pre-existing dirty
Factory/T4A/T4E, evidence, report, index and host/bridge paths were preserved.

## Residual boundary

The persisted Phase-5 `cost_entries` shape does not carry a provider receipt
identity. The adapter therefore deliberately leaves persisted actual cost
ambiguous/non-observed even when `entry_key` exists; it does not infer receipt
identity from row position, reservation, or entry key. A caller must supply an
explicit complete, versioned, current project-ledger descriptor for project
cost totals to become observed. Provider-side exactly-once effects, provider
authority, external FX verification, project-wide completeness, publication,
release and Gate 4 closure remain outside this local adapter.

No provider or external source was accessed. No credentials, private source
material, prompts, model responses, runtime state, caches or logs were added to
Git. No Drive, bridge, watcher, host, GitHub, publication, release, reservation,
spend or follow-on action occurred.
