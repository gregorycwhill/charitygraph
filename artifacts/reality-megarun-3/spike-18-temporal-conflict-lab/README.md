# Reality Spike 18 — Temporal Conflict Lab

Status: local, disposable experiment. This is not a canonical observation store, release candidate, source acquisition, or promotion.

## Result

`MEGARUN3_TEMPORAL_CONFLICT_COMPLETE`

The ledger contains 31 attributable propositions and 16 comparison pairs over five real retained organisations; 30 propositions participate in at least one comparison. It uses regulator, annual-report and official-website evidence already retained in the local governed-input reality-spike corpus. It does not create a contradiction merely because values, sources, dates, or claim families differ.

## Classification outcome

| Classification | Pairs | What it demonstrated |
|---|---:|---|
| Compatible | 6 | Same fact or coexisting facets can remain separately attributable. |
| Scoped difference | 4 | Financial measures, group scope, unknown consolidation and a nine-month period cannot be flattened. |
| Source-role difference | 6 | A regulator, report and current official website have different authority and temporal roles. |
| Temporal supersession | 0 | No real retained pair supported one; none was invented. The routing behaviour was still exercised against historical/current propositions. |
| Ambiguous / true conflict | 0 / 0 | None was manufactured. |

The Red Cross FY23 case is the strongest discriminator: total expenses agree exactly; revenue figures differ because the annual-report total includes a separately presented gain while the AIS value is the report's revenue-and-other-income subtotal. It is explicitly non-comparable rather than a conflict.

## Deterministic routing demonstration

The router is a stable ordering rule, not semantic inference:

1. Preserve every proposition keyed by subject, predicate, scope, valid time, source role and locator.
2. For a historical card, select the requested valid-time interval and show all retained source roles.
3. For a current activity card, prefer an applicable current official-site observation but retain an older report proposition as history.
4. If a comparison is `source-role difference`, `scoped difference`, or `ambiguous`, show both propositions plus the classification; never choose a silent winner.
5. Only a reviewed correction/supersession link may change a display slot. The raw predecessor remains queryable.

Applied to MCMC, `mcmc-04` (current volunteering-page observation) can occupy a current-activity slot, while `mcmc-02`, `mcmc-03`, and `mcmc-06` remain the FY25 nine-month report history. It is not valid to treat the page as a correction or supersession of the report's financial or reporting-period claims. A future reviewed correction/supersession record would alter only the relevant display slot under rule 5.

## Rendering effect

The progressive card needs: a current/historical toggle; compact source-role and reporting-period labels; a non-comparable badge for Red Cross revenue; an explicit `9 months` label for MCMC; and a review badge for self-description candidates. The evidence ledger exposes locator/source, scope, valid time, review state, relation classification and any supersession link. No new canonical fields are required for the atomic proposition spine, but these satellites are required for safe display: `valid_at`, `source_role`, `reporting_scope`, `comparison_classification`, `review_state`, and `supersedes_display_slot`.

## Hypothesis

Strengthened. Atomic attributed propositions remain a durable spine when coverage/missingness, scope, source role, valid time, review state and comparison/supersession links remain satellites. A card must be a deterministic projection over those facts. The primary hazard was false conflict: 16/16 pairs were kept out of the true-conflict queue; nine candidate/self-description propositions still require review before promotion.

## Boundaries observed

No external fetch, provider call, new subsystem, production or S0 action, canonical mutation, GitHub mutation, or credential operation occurred. Raw evidence remains in its original retained packet; this artifact stores references and analytical classifications only.
