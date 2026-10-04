# Fundraising evidence-role contract v1

Status: implemented review-only contract. This version does not authorise source acquisition, public promotion, a public schema, or a claim that an unexamined source is absent.

`FundraisingEvidence` is the required envelope for an extracted fundraising observation. It retains source identity and locator, exact source wording, subject-binding basis, observed and valid time, scope, production method, review state, coverage and missingness. A source-role decision is a permission check, not a trust score.

| Source role | May support, only if explicitly extracted | Cannot support by role alone |
| --- | --- | --- |
| First-party practice page | practice, setting, channel, commitment pattern, currentness | campaign, provider, organisation-wide scope beyond stated scope |
| First-party campaign page | campaign and stated mechanics/currentness | standing practice or campaign revenue attribution |
| Annual-report statement | dated practice/campaign/mechanics | currentness without source-supplied continuity/time |
| Agency provider case evidence | explicit provider relationship and stated scoped practice/mechanics/time | unmentioned compensation, effectiveness, or organisation-wide use |
| Agency client directory | explicit provider relationship only | F2F, setting, channel, regular giving or currentness |
| Platform campaign page | bounded campaign and stated mechanics/time | standing practice or accounting revenue/proceeds |
| PFRA membership | membership fact retained outside this facet contract | F2F, delivery, setting, regular giving or currentness |
| Regulator registration/permitted methods | registration/legal context retained outside this facet contract | actual fundraising practice, campaign or currentness |
| Industry record, procurement/job evidence | research context unless a separately governed role is approved | practice deployment or currentness |
| Scoped source inventory | coverage description only | absence or negative practice claim |

The validator rejects a source attempting a facet outside its role. Promotion additionally requires a confirmed subject binding, observed coverage, a reviewed extraction and, for currentness, source-supplied validity time. Ambiguous/unresolved binding is blocked. Scoped silence is `coverage_only`. `pfra_membership` and `regulator_registration` have explicit mechanical non-inference gates.

The fixture contains strong (reviewed, directly scoped first-party), weak (review pending), negative (PFRA and regulator attempts), ambiguous-binding and scoped-silence cases. It preserves source-native wording rather than using keyword matching.
