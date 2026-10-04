# Fundraising cohort regression v1

Status: reproducible local regression fixture.  This is not a prevalence study or production-source acquisition.

Run `python scripts/run_fundraising_cohort_regression.py --output <path>` from the Builder root. The fixture defines a bounded 24-case evidence universe and the runner emits all counts, denominators, review examples, coverage states, and residual gaps.

The cohort deliberately includes PFRA membership cases, ambiguous and unresolved bindings, scoped non-findings, finance-only negative controls, and explicit campaign/provider links. It must not be used to infer channel effectiveness, ROI, a universal practice rate, or attribution of organisation-level money to a fundraising method.
