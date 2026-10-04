# Fundraising financial derivative guardrail

**Status:** Implemented Builder review-only contract, version 1.0

**Scope:** deterministic handling of fundraising expenditure and the refusal
boundary for financial-performance claims. This document implements the
bounded disposition in Data's
`FUNDRAISING_VOCABULARY_MEASUREMENT_RESEARCH_GATE_2026-10-04.md`; it creates
no public projection, source adapter, acquisition path, or public schema.

## Safe paths

`fundraising_financial_derivatives` permits only the following representations:

1. direct source-reported fundraising expenditure, with source measurement,
   evidence, period/scope metadata and approximation status;
2. functional allocation reconstruction only where the source allocation basis
   and governed deterministic method are recorded;
3. lower/upper expenditure bounds composed of definite, possible and excluded
   components with non-overlapping additivity bases; and
4. an explicit `unavailable` result rather than a filled-in value.

An expressly source-reported fundraising cost share or net-proceeds amount may
be retained as `SourceReportedFundraisingDerivative`. It must retain its
source measurement, source wording, evidence, reporting scope, exact period
and accounting basis. CharityGraph does not recompute that value.

## Mechanical refusal boundary

`fundraising_cost_share` and `net_proceeds` always raise
`ProhibitedFundraisingCalculation`. Matching currency, entity and period rows
do not establish a method/campaign attribution, a valid allocation, or a
performance outcome. The module has no result type for ROI, cost-to-raise-$1,
donor acquisition cost, lifetime value, profitability, channel effectiveness,
causal uplift, or method-generated revenue.

This prevents a projection from silently presenting those causal or
performance claims as facts. A missing component, source silence, incompatible
period/scope/basis, or unsupported attribution remains unavailable; it is not a
prior, peer fill, midpoint, zero, or arbitrary allocation.

## Regression evidence

`tests/test_safe_fundraising_financial_derivatives.py` covers direct,
reconstructed, bounded and unavailable expenditure; explicit refusal of the
two tempting arithmetic calculations; source-reported derivative provenance;
and prohibited metric names. Finance compatibility and fundraising money-scope
tests remain the adjacent contract checks.

## Guarded integration record

This change is a local unpublished commit on
`terra/t06-enforce-safe-fundraising-financial-derivatives`:
`5b1bc1db6833f8e59d0f889d0cd2bb6497ddcad3`. It is a follow-up to the isolated
baseline commit `fe0c0d44efec0459b358f7533f25a39bf44dd1b8`.

When a maintainer selects a clean target branch, the exact host-side inputs are:

```text
git cherry-pick fe0c0d44efec0459b358f7533f25a39bf44dd1b8
git cherry-pick 5b1bc1db6833f8e59d0f889d0cd2bb6497ddcad3
```

No publication, merge, source acquisition, or public-contract action is
authorised by this record.
