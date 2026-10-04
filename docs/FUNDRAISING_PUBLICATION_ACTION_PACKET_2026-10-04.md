# Fundraising review-only publication action packet — 4 October 2026

## Status

This packet consolidates the locally committed, review-only Builder slice that
implements the semantic boundaries approved by Data's fundraising vocabulary and
measurement research gate.  It is **not** authorisation to publish a schema,
release, Viewer surface, production source adapter, or Top-100 cohort.

## Exact local integration tip

Builder repository/worktree: `C:\CharityGraph-runtime\cg-fundraising-publication-288`  
Local branch: `cg-fundraising-publication-288`  
Integrated code tip: `97626d3349bb0c561d809ca64314d266997a962a`  
Packet commit: `faaa6181977a894736366daf0580a9c8487d1fec`

The integration base was `e384a5efacf9f3e6fc5856b716f4f89ded5ef5ff`
(`cg-t10-bounded-real-fundraising-cohort`).  Local integration commits are:

| Commit | Content |
| --- | --- |
| `304e490` | Typed practice, campaign, and explicit provider-relationship review contracts |
| `d35bcd5` | Attribution-grain research study and fixtures |
| `d2dcf2c` | Governed industry-promotion candidates |
| `97626d3` | Visible, local review-profile projection |

The integration retained the newer finance-compatibility implementation already
on the base; its original 287 commit is
`8a93cd9063e32b00981f87645d52f532525654a8`.  It was semantically present but
not re-applied because its older patch conflicted only with the base's stricter
allocation/approximation controls.

Upstream 287 evidence inputs remain separately auditable: `dccc7ab` (F2F
currentness), `a54d526` (typed contracts), `8a93cd9` (finance compatibility),
`50af91b` (attribution-grain study), `08ba60c` (industry candidates),
`2c8a331` (review profile), `e384a5e` (cohort), and `a7d2e66` (state map).

## Contract and file map

- `src/charitygraph/f2f_currentness.py` and `docs/F2F_CURRENTNESS_POLICY.md`:
  F2F lifecycle/currentness from supplied bound evidence only; no timeless
  Boolean, inferred setting, agency, regular giving, or organisation-wide
  continuity.
- `src/charitygraph/fundraising_vocabulary.py` and
  `docs/FUNDRAISING_VOCABULARY_V1_CANDIDATE.md`: composable source-term-to-facet
  crosswalk, deliberately not a flat universal taxonomy.
- `src/charitygraph/models.py` and `docs/TYPED_FUNDRAISING_CONTRACT_V1.md`:
  distinct standing practices, campaigns, and directed provider relationships,
  all retaining provenance, time, scope, and review state.
- `src/charitygraph/finance_measurement.py`,
  `src/charitygraph/fundraising_money_linkage.py`, and
  `docs/FINANCE_MEASUREMENT_COMPATIBILITY_V1.md`: scope/period/entity/basis
  compatibility and smallest explicit attribution grain.  Aggregate money stays
  unattributed without direct support.
- `src/charitygraph/fundraising_review_projection.py` and
  `docs/FUNDRAISING_REVIEW_PROFILE_V1.md`: fixture-bound local review output;
  not a public card or release renderer.

Data authority is on local branch `phase5-direct-service-v1.2-closeout`, at
`282733f`.  Its governing records are
`FUNDRAISING_VOCABULARY_MEASUREMENT_RESEARCH_GATE_2026-10-04.md` (`c5681c0`),
`FUNDRAISING_SUCCESSOR_MATRIX_2026-10-04.md` (`08f143e`), and the retained
design status notice (`282733f`).

## Verification and cohort result

On the integrated tip, this command passed on 4 October 2026:

```text
python -m pytest tests/test_f2f_currentness.py tests/test_fundraising_vocabulary.py tests/test_fundraising_money_scope_linkage.py tests/test_safe_fundraising_financial_derivatives.py tests/test_finance_measurement_compatibility.py tests/contracts/test_typed_fundraising_contracts.py tests/test_fundraising_money_attribution_study.py tests/test_fundraising_industry_promotion.py tests/test_fundraising_review_projection.py tests/test_fundraising_cohort_regression.py
```

Result: **55 passed in 1.95s**.

`python scripts/run_fundraising_cohort_regression.py --output
artifacts/fundraising-cohort-regression-288.json` produced the retained local
artifact.  The 24-case fixture has 12/24 practice observations; 3/5 confirmed
PFRA bindings; 4/24 unresolved/ambiguous bindings; 14/24 available money
observations; 0/14 available share-or-bounds observations; 9 finance-only
unattributed controls; and currentness of 3 current, 4 recent, 3 historical,
2 discontinued, 3 scoped non-findings, and 9 unknown.  These are regression
coverage counts, never population estimates, production acquisition, ROI, or
effectiveness evidence.

## Remaining risks and owner decisions

The research gate leaves these as explicit gaps: rights-cleared publishable
campaign-row money; time-varying PFRA membership semantics; what currentness a
provider case study can support; real finance disclosures with independently
checked definite/possible/excluded envelopes; and campaign facets that survive
cross-source mapping without flattening delivery, channels, or mechanics.

Product-owner decisions are required before any public schema/release/Viewer or
production ingestion: approve a 30–50-case rights-cleared source-backed cohort,
independent identity adjudication and error measurement; decide each source
family's rights/retention/refresh/republication posture; review vocabulary
pressure; and coordinate versioned Builder/Data/Viewer contract and correction
semantics.  No F2F currentness age threshold, flat method taxonomy, aggregate
money allocation, ROI/cost-share/net-proceeds metric, or public promotion is
implied by this packet.

## Guarded host action (human-operated only)

No remote action was performed.  If a maintainer authorises publication of the
review-only Builder integration, first fetch and compare the selected target
base, then push **only** the resolved local tip of
`cg-fundraising-publication-288` and open a PR to the explicitly
chosen Builder target branch.  PR title: `Review-only fundraising semantic
contracts and cohort gates`.  Include this packet, the focused 55-pass result,
and the Data authority commits `c5681c0`, `08f143e`, and `282733f`; require
review confirming that the diff has no public schema, release, Viewer, source
acquisition, or source-rights change.  Do not merge until the target-base
comparison and owner gates above are approved.

## Boundary confirmation

This work made **zero authenticated GitHub mutations**, **zero reset-credit
redemptions**, **zero paid/provider calls**, and **zero unauthorised
production-source acquisitions**.  No immutable release, public corpus, Viewer,
or canonical dirty checkout was changed.
