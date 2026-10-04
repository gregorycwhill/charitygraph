# Finance measurement compatibility v1

**Status:** Implemented internal contract  
**Version:** 1.0  
**Scope:** deciding whether two source-native fundraising money observations can be added in one deterministic calculation.

This contract extends, rather than replaces, `MoneyObservation` exact unit normalisation and the existing `Financials`, `FinancialStatementObservation`, `FinancialLineItem`, and `FunctionalExpenseAllocation` records. It never rewrites a printed financial-statement row or source label.

`FundraisingMoneyMeasurement` carries the original wording, evidence, exact period, subject/consolidation identity, recognition, gross/net, GST, pass-through and cost-attribution treatment. Unknown is a valid persisted state and is incompatible for addition. `decide_addition_compatibility` is mechanical validation over supplied structured fields; it does not classify prose.

## Decision rule

Addition is allowed only when both observations have the same measurement kind and normalised currency; identical complete period dates and length; identical scope and subject or consolidation identifier; known and identical accounting/presentation dimensions; the same fundraising activity; and a shared source-supported aggregation set with both components explicitly marked disjoint. This is intentionally narrower than “can be shown beside each other.”

| Measurement concepts | Addition result | Why |
| --- | --- | --- |
| Same kind, same complete dimensions, source-declared disjoint components | Allowed | Deterministic sum is bounded by an explicit source grouping. |
| `pledged` / `cash_received` / `recognised_revenue` | Separate | Commitment, cash and recognition events are different measurements. |
| `gross_proceeds` / `amount_raised` / net amount | Separate | Gross/net treatment cannot be recovered safely. |
| Campaign year / financial year | Separate | No annualisation or period overlap inference. |
| Charity / organisation group / consolidated group | Separate | Entity boundary is material. |
| `donations_received` / ticket, merchandise or sponsorship revenue | Separate | A revenue category is not proof of fundraising-generated revenue. |
| Direct cost / administration allocation / total fundraising cost | Separate | Direct and allocated costs, and totals and components, risk overlap and have different bases. |
| Agency fee, commission, media, staff, event/prize cost | Separate by default | They may be components only when explicitly represented as the same kind in a disjoint source grouping; no label-derived allocation occurs. |
| Different GST or pass-through treatment | Separate | Tax and custodied/pass-through amounts affect the economic quantity. |

## Existing semantics and evidence examples

The current implementation preserves `MoneyObservation`'s exact source-unit invariant in `src/charitygraph/models.py`, source-ordered statement rows in `FinancialStatementObservation`, and direct-versus-derived allocation semantics in `FunctionalExpenseAllocation`. `tests/test_phase2d_statements.py` demonstrates a mixed source row, “Donations, Fundraisings, Lectures”, being retained without a canonical donations metric. The v1 fixture supplies an audited-statement-style direct-cost example and a regulator-return “Donations and bequests” example only as test evidence; neither is production ingestion or causal fundraising attribution.

Source role and assurance remain attached for auditability but do not make incompatible quantities compatible. This contract neither calculates ROI nor attributes aggregate income/expenditure to a practice, campaign, or method.
