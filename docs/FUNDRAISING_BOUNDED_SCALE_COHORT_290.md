# Fundraising bounded-scale cohort 290

Status: reproducible local-review regression; not an acquisition, production-ingestion, prevalence, precision/recall, or release packet.

Run from this repository root:

```powershell
python scripts/run_fundraising_cohort_regression.py --fixture tests/fixtures/fundraising_cohort_regression_v2.json --output artifacts/fundraising-cohort-regression-290.json
```

## Selection and evidence boundary

The cohort has 50 deliberately heterogeneous adversarial cases. It covers direct practice, F2F current/recent/historical/discontinued/unknown states, explicit campaign and provider relationships, PFRA and legal-permission controls, scoped silence, identity ambiguity, finance-only observations, incompatible finance, and a contradiction control. Every case has an internal fixture source identifier, locator, wording, binding outcome and adjudication flag. These are **fixture handles**, not retrieved documents, source-rights clearance, or independent real-world identity adjudications.

This makes the runner suitable for repeatable policy regression only. It does not clear the 5 October gate for a 30–50 case independently identity-adjudicated, source-backed cohort. Its selection denominator is 50 cases; no overlapping assertion count is a charity, page, source-family, or population denominator.

## Result and review findings

The committed generated report records 35/50 adapter-supplied practice observations, 25/50 available source-native money observations, 12/25 organisation-grain money observations left deliberately unattributed, 8/25 campaign-grain, 3/25 practice-grain, and 2/25 provider-relationship-grain observations. It records 5/50 ambiguous/unresolved binding refusals, 2/50 incompatible-finance refusals, 4/50 scoped non-findings, 3/50 not-processed money outcomes, and 0/25 share-or-bounds outcomes.

The method counts are evidence observations, not mutually exclusive charities or channel prevalence: face-to-face 9, community event 3, appeal 2, regular giving 2, peer-to-peer 2, giving day 2, major giving 2 and raffle 2; other represented methods have one observation each. Campaign and provider are separate facets: 10/50 explicit campaign cases and 3/50 explicit provider-relationship cases. PFRA binding is 2/4 confirmed, and no PFRA record promotes a practice.

Review examples are emitted by stable case id: incompatible finance (`s11`, `s36`), ambiguous binding (`s07`, `s09`, `s23`, `s28`, `s48`), scoped inventory outcomes (`s05`, `s18`, `s32`, `s46`), aggregate-money non-attribution (the 12 ids in `finance_without_method_attribution`), and contradiction control (`s50`). This report intentionally does not calculate ROI, net proceeds, shares, allocation, effectiveness, or causal attribution.

## Runtime and cost

The runner is deterministic and local: zero source retrievals and zero provider calls. Runtime/cost is therefore not a deployment estimate. The measured operational bottleneck is the next required work: rights-cleared source retention, independent identity binding and review adjudication. Until that is supplied, this cohort remains local review only and cannot stand in for Top-100, source-family coverage, or a public product surface.
