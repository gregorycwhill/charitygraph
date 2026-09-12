# Phase 5 Direct Service V1.2 closeout

**Status:** Completed experimental tranche

**Date:** 12 September 2026

**Branch:** `phase5-direct-service-v1.2-cutover-v1`

**Scope:** Direct Service representation and its bounded live experiment; this does not close the broader Top-100 full-card Phase 5 objective or authorize data promotion.

## Objective and decision

Test whether a section-discriminated Direct Service V1.2 response contract fixes
the V1.1 section/type representation defect. The conservative decision is
**`V1_2_REPRESENTATION_FIX_SUPPORTED`**. Select V1.2's own wire DTO and converter
for future Direct Service work. Keep V1.1 as historical evidence. The defect is
resolved for purposes of proceeding with implementation, but this small,
non-random experiment does not establish statistical significance, universal
quality, or production readiness.

This is a semantic representation decision only. There were no governed
assertion promotions, canonical observation promotions, public releases, or
Viewer changes.

## V1.1 and V1.2 results

| Measure | V1.1 historical baseline | V1.2 live sample |
|---|---:|---:|
| Completed provider responses | 42 | 14 |
| Directly valid | 19 | 14 |
| Deterministically recovered | 22 | 0 |
| Semantically unusable | 1 | 0 |
| Responses affected by representation problems | 20 | 0 |
| Illegal section/type proposition instances | 32 | 0 |
| Propositions retained | — | 49 |
| Propositions discarded | — | 0 |

The original V1.2 continuation population was 18: 13 newly executed eligible
requests, one local pre-send validation failure abandoned before crossing the
provider boundary, and three requests excluded because corrected conservative
hard exposure exceeded the binding AUD `0.25` per-request authority. Those four
are not semantic failures. Do not reopen the excluded observations merely to
increase the sample. The historical V1.1 terminal HTTP 429 was not retried.

## Economics, authority, and experiment boundary

| Population | USD | AUD |
|---|---:|---:|
| Historical successful canary | `0.113160` | `0.172003` |
| Final 13 executions | `0.324526` | `0.493287` |
| Total V1.2 provider cost | `0.437686` | `0.665290` |
| Corrected conservative exposure for final 13 | `0.578307` | `0.879033` |

All final unused reservations were released. Amendment 3 remained active;
Amendment 4 was never activated. Provider operations after the authorized 13
were zero. Source acquisition, governed promotions, merge, and runtime mutations
for this documentation closeout were zero.

## Factory and control-plane requirements learned

Carry these requirements into future Factory implementation planning; this
closeout does not start a Factory redesign or implement new control-plane work.

1. **Certify the executor-consumed row immediately before send.** Preparation-
   time certification alone is insufficient; validate required hydration fields
   at the actual execution boundary.
2. **Separate provider-significant request identity from physical-attempt
   identity.** An attempt may change while immutable semantic/provider material
   remains the same.
3. **Use provider crossings as the at-most-once invariant.** A local failure
   before crossing is not a provider retry; physical attempt count alone does
   not establish whether a request was sent.
4. **Keep execution tickets immutable and append-only.** Never repin a historical
   ticket in place; supersede it with explicit lineage.
5. **Preserve raw provider usage separately from strict cost-ledger usage.** Keep
   the full Responses usage object and project only accepted billable fields into
   accounting contracts.
6. **Give V1.2 its own wire DTO and converter.** Section-array responses must not
   pass through the legacy V1.1 `propositions` DTO.
7. **Calibrate conservative token/exposure bounds against observed usage.**
   Enforce per-request authority before send; the original estimate materially
   understated exposure.
8. **Record economic exclusions as first-class outcomes.** Do not force the
   authority model to accommodate a request above its cap or classify that
   exclusion as a semantic failure.
9. **Preserve at-most-once provider crossing during local recovery.** No
   completed provider request was resent to recover a local processing defect.

## Project sequencing

The Direct Service experimental tranche is complete. The existing roadmap's
Phase 6, “Risk-gated depth and specialist profiles,” remains the named successor
only after the broader Phase 5 Top-100 full-card exit criteria. This experiment
does not meet those criteria. Which already-planned work tranche should follow
within remaining Phase 5 scope is unresolved; this closeout does not select a
new product direction or begin the next implementation phase. Discovery V2
remains complete and is not reopened.

## Primary empirical source

Runtime report (kept outside Git):
`C:\CharityGraph-runtime\phase5-top100-direct-service-v1.2-cutover-v1\phase5-direct-service-v1.2-final-report-2026-09-12.json`
SHA-256: `588707746dee2de90a14ed099d13235a34d3b18bf88e9f43008c22712c047777`.

The full report includes per-response hashes, usage, receipts, costs, and
provider-free reconciliation. This document records only the durable compact
summary; it contains no prompts, raw model responses, provider IDs, or private
source content.
