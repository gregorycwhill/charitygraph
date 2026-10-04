# Fundraising finance source contract v1

**Status:** Implemented internal, review-only contract. **Version:** 1.0.

`FundraisingFinanceSourceObservation` is the source envelope for a typed
fundraising money measurement. It preserves a source identifier, source family,
exact locator, native wording, subject-binding basis, observed/valid time,
geography/setting when supplied, production method, review state and coverage
or missingness. It does not classify unrestricted prose: that decision remains
with the governed extractor or reviewer that supplied the typed measurement.

## Deterministic statement-heading mapping

The extractor has a deliberately small mapping for exact headings in an
identified annual report or financial statement: `Fundraising costs`, `Costs
of fundraising`, `Direct fundraising costs`, `Fundraising income`,
`Fundraising revenue`, and `Gross fundraising proceeds`. It maps these to a
typed source-native measurement only when the row also carries the normal
period, scope, binding and accounting metadata. Generic `Income`, `Donations`,
`Marketing`, net headings, and headings from other source families are not
mapped. They remain review-only or unavailable rather than becoming a
fundraising fact by keyword proximity.

The permitted source families are annual report/financial statements;
ACNC/NSCOA return mappings where a source supports the mapping; state
fundraising disclosures; campaign and platform reports; provider records; and
organisation disclosures. A source family is provenance, not an assurance that
the reported quantity is comparable or attributable to fundraising.

## Components and scope

Every source fact states `direct`, `allocated`, `possible`, or `excluded`.
Direct and allocated are retained as separate component treatments. Possible
and excluded components are preserved for a governed bounds/exclusion envelope;
they cannot enter deterministic addition. This complements, rather than
replaces, the direct/allocated allocation metadata on
`FundraisingMoneyMeasurement`.

Each fact is scoped to either its reporting organisation or an explicitly
identified campaign. Organisation scope must use the measurement's reporting
subject identifier. Campaign scope requires a source-supported activity
identifier. The compatibility gate requires exactly the same scope kind and
identifier, so a financial-statement organisation total cannot be accidentally
mixed with or promoted into campaign finance.

`decide_finance_source_addition_compatibility` first invokes the existing
measurement compatibility gate (currency, exact period, entity, accounting
basis, gross/net, GST, pass-through, allocation basis, activity and
disjointness), then checks source-observation scope and treatment. Unknown,
missing, possible, excluded and incompatible observations stay unavailable for
deterministic addition. No ROI, cost-to-raise, causal revenue, channel result,
or method allocation is created.
