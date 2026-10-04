# Fundraising Vocabulary v1 Candidate

**Status:** Governed candidate for review; not a published taxonomy or assignment rule.  
**Scope:** CharityGraph fundraising practices, campaigns and financial evidence.

This candidate uses composable facets rather than a mutually exclusive method hierarchy. A single evidence-backed observation may independently record strategy/program, solicitation mechanism, communication channel, setting/placement, resource sought, commitment pattern, payment/transfer instrument, donor relationship stage, delivery party, compensation, destination/restriction and donor/funder class. Absence of a facet is unknown, not negative evidence.

The machine-readable candidate is `charitygraph.fundraising_vocabulary.FUNDRAISING_VOCABULARY_V1`. It is deliberately vocabulary-only: it does not extract prose, infer current use, make instance assignments or allocate money.

## Representative composition

“Regular giving + F2F + private-site + recurring + direct debit + acquisition + external agency” is represented as seven compatible facet terms, not as one compound label:

`regular_giving`, `face_to_face`, `private_site`, `recurring`, `direct_debit`, `acquisition`, and `external_agency`.

Each remains independently evidence-, scope- and time-bound. In particular, generic F2F evidence does not establish any of private-site, agency, recurring, direct debit, regular-giving, acquisition or currentness.

## Source schemes and crosswalk

The candidate registers PFRA F2F vocabulary as mapped domain evidence, FIA award categories and UK Fundraising Regulator guidance as reference-only, ACNC AIS and NSCOA finance language as reference-only, and Donor Republic/Funraisin P2P benchmark terms as mapped. These are distinct source schemes, not components of a single authoritative CharityGraph taxonomy.

Crosswalk entries preserve their predicate, rationale and unresolved/non-equivalence note. Examples deliberately left without a native equivalent include FIA award recognition, the generic UK “fundraising method” label, ACNC “donations and bequests”, and NSCOA “fundraising expense”. The latter two remain financial/source-native concepts and cannot allocate income or expenditure across methods or campaigns.

## Evidence and measurement boundaries

Use a source’s own term and version/date alongside any mapping. A mapping is never evidence that a charity uses a practice. Store supporting source, evidence span, subject/scope, valid time and currentness separately. Do not derive return on investment, cost to raise a dollar, donor-acquisition cost, effectiveness, causal uplift or profitability. Reported raffle/event/retail/sponsorship amounts also require their source accounting context and are not automatically donations or fundraising-generated revenue.

## Open research gaps

- Current Australian regulator wording for lottery/raffle and retail/goods activity needs a versioned source register before any wider mapping.
- FIA award-category terminology must be captured by award year; it remains source-native recognition context.
- PFRA terms need dated, scoped evidence on each use; membership alone is not continuous organisation-wide currentness.
