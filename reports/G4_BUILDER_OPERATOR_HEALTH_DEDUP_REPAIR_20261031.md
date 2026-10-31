# G4 Builder operator-health dedup repair

Date: 2026-10-31 (Australia/Sydney)
Worker: bounded G4-O1C, local/provider-free

## Verdict

**PASS for the bounded local repair; PARTIAL for the overall operator-health
capability.** Gate 4 remains open. No provider exactly-once effect, project-wide
completeness, external FX-rate verification, publication, or gate closure is
claimed.

## Repair evidence

- `phase5_operator_health.py` now uses one stable receipt-identity path for
  receipt usage and actual-cost observations. Identical replays count once;
  conflicting same-identity payloads are excluded and emit an explicit
  `AMBIGUOUS_RECEIPT_IDENTITY` error.
- Reservation/commitment rows are deduplicated by `reservation_id`. Identical
  repeats count once; conflicting IDs fail closed with
  `AMBIGUOUS_RESERVATION_IDENTITY`.
- Release evidence distinguishes an observed explicit zero from no release
  rows: the latter is `missing` with a null amount and cannot reconcile as an
  observed zero. Existing missing, incomplete, unknown, and stale ledger paths
  remain fail-closed.
- Nested object adapters are traversed for float rejection. Currency and
  pricing/FX identifiers require structured, non-empty forms; no rates are
  externally verified.

## Verification

Cache-free pytest runs used external basetemps under
`C:\CharityGraph-runtime`:

- focused operator-health suite: **21 passed**;
- focused operator-health plus Phase-5 delivery, run diagnostics, persisted
  diagnostics catalogue, standard transport, and budget-ledger regressions:
  **89 passed**.

Regression coverage includes identical/conflicting receipt usage, identical/
conflicting reservation IDs, zero versus unobserved releases, Decimal cost
handling, missing/stale/partial ledger behaviour, order-independent canonical
JSON/SHA-256, nested float rejection, no file opening, and provider-free
limitations.

`git diff --check` was clean for the three task paths. Only these exact paths
were changed:

1. `src/charitygraph/phase5_operator_health.py`
2. `tests/test_phase5_operator_health.py`
3. `reports/G4_BUILDER_OPERATOR_HEALTH_DEDUP_REPAIR_20261031.md`

No provider, network, source acquisition, credential, reservation, spend,
Drive, bridge, watcher, host, GitHub, publication, or release action occurred.
Pre-existing dirty files, including Factory/T4A/T4E work and the independent
acceptance report, were preserved. No private source material, prompts, model
responses, runtime state, caches, credentials, or logs were added.
