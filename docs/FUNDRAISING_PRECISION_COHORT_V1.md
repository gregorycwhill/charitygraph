# Fundraising precision cohort v1

Status: reproducible review-only cohort report. It is not source acquisition, identity resolution, production ingestion, a public projection, a sector-prevalence estimate, or a performance analysis.

Run `python scripts/run_fundraising_precision_cohort.py --output <path>` from the Builder root. The input has two intentionally non-joinable populations: 30 heterogeneous charity discovery handles and 12 cached governed review cases. The handle count is a selection denominator only; no handle is a resolved subject or evidence-bearing record.

The report aggregates already reviewed, typed outcomes. It does not inspect wording or use a semantic heuristic. It reports source-role and coverage distributions, method/currentness states, finance state, attribution grain, supported promotions, false-positive and false-negative counts, explicit refusals, and every adversarial example.

The current fixture has five supported positive cases, zero reviewed false positives, zero reviewed false negatives, three correctly refused positive-looking but insufficient cases, and four additional review-only/coverage refusals. This is a gate check, not a claim of 100% production precision: the positive precision denominator is five and the negative denominator is three. Mixed or aggregate finance remains unallocated; no derived fundraising-performance metric is calculated.

Review cases remain anonymous by design. Joining them to a named selection handle would convert a selection exercise into an unsupported charity claim and is prohibited.
