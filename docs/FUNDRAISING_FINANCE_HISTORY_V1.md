# Fundraising finance history v1

`fundraising_finance_history` holds annual, nominal fundraising-money facts in source chronology. It does not add them and does not adjust for inflation.

Each history entry is a complete source observation with its source locator, wording, subject binding, scope, review state and financial-period metadata. The history envelope adds only source/reviewer-supported change metadata: a source classification identifier, restatement target, reporting-entity change and accounting-policy change.

A comparison is emitted only between adjacent facts. It is comparable only where both facts have exact normal annual periods anchored to the same reporting-year day, a stable measurement/scope/accounting basis and gross/net treatment, stable source classification, and no restatement, entity or policy change. A comparison contains nominal change and nominal change fraction; it is not a fundraising-performance metric.

Any restatement, classification shift, entity/policy change, unknown semantic dimension, short/transitional period, changed reporting-year anchor, scope change or currency change is a discontinuity. The facts remain in the chronology and the reason remains attached; no trend is emitted.
