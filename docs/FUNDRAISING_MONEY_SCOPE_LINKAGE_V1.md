# Fundraising money scope linkage v1

**Status:** Implemented internal contract. **Version:** 1.0.

`FundraisingMoneyScopeLink` attaches an existing `FundraisingMoneyMeasurement`
to the smallest scope expressly supported by evidence: organisation, fundraising
portfolio, practice, campaign, appeal, or provider relationship. It does not
change `MoneyObservation`, source-native rows, financial-statement categories,
functional allocations, or the existing finance reconstruction/bounds model.

An explicit downstream link requires both source wording and evidence IDs. An
unknown link stays at the organisation level. This is an attachment state, not
an absence claim and not permission to choose the closest observed practice.

## Source-to-link guard

`link_source_observation_at_smallest_scope` is the deterministic construction
path for a reviewed finance-source observation. It copies a lower-grain link
only when the observation itself declares the exact `scope_kind` and
`scope_id` (fundraising portfolio, practice, campaign, appeal, or provider
relationship). It uses the observation's source-native wording and evidence
identifiers; it never selects a target based on a practice's presence,
recency, number of methods, a shared reporting period, or nearby text.

An organisation-scoped source fact is projected as `unknown` linkage and
`organisation (not attributed)`, even if other evidence in the review profile
mentions a method or campaign. Non-observed source states cannot be converted
to money links.

`decide_linked_addition_compatibility` invokes
`decide_addition_compatibility` and additionally requires the same explicit
attributed scope. Thus aggregate portfolio figures cannot be distributed among
methods, practices, campaigns, appeals, or provider relationships mechanically.

The fixture records t05-study controls: c12 is an organisation total; c15 is a
portfolio functional allocation; c14 is a mixed source-native row; c14/c15 do
not authorise a method or campaign split. The controlled positive cases show
what an explicit campaign or practice note would require. None create ROI,
cost-to-raise-dollar, effectiveness, or causal claims.
