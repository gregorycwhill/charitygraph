# Fundraising review profile

- Contract: `fundraising-review-profile-v1`
- Capability: `review_only_representative_slice` (not the whole product)
- Deterministic input hash: `53613799619e03fbaa0992fff4ec71a4a87d9cefcd2517d771b54973d0297949`
- Money is displayed at its explicit attributed scope; an organisation-level fact is not attributed to a practice, campaign or provider.

## Review case: direct F2F disclosure (`cb_review_f2f`)
- Evidence set: `cached-governed-review-case-f2f-v1`

### Practices
- `fp_review_f2f`: face-to-face fundraising; lifecycle `current`; scope `subject`; evidence `ev_review_f2f`

### Campaigns
- Unknown or not processed; see coverage.

### Providers
- No provider relationship is asserted in this review set.

### Money facts
- No money fact available in the selected evidence.

### Coverage
- `practices`: `observed` — Currentness is stated by the selected evidence. (scope: subject; direct statement)
- `campaigns`: `not_found_in_scoped_source` — This is not a conclusion about all campaigns. (scope: selected statement only)
- `providers`: `unknown` — No provider is inferred from F2F. (scope: selected evidence set)
- `money`: `unavailable` — No financial amount is supplied. (scope: selected evidence set)

## Review case: bounded peer-to-peer appeal (`cb_review_campaign`)
- Evidence set: `cached-governed-review-case-campaign-v1`

### Practices
- Unknown or not processed; see coverage.

### Campaigns
- `fc_review_appeal`: Winter Community Appeal; lifecycle `ended`; scope `program`; evidence `ev_review_campaign`

### Providers
- `fpr_review_platform`: `fundraising_platform_provider` to `cb_review_platform`; lifecycle `historical`; evidence `ev_review_platform`

### Money facts
- No money fact available in the selected evidence.

### Coverage
- `practices`: `not_yet_processed` — A campaign is not promoted to an ongoing practice. (scope: standing-practice review)
- `campaigns`: `observed` — Campaign lifecycle is bounded by the source. (scope: named appeal and stated period)
- `providers`: `observed` — The relationship is not extrapolated beyond its stated period. (scope: named platform relationship for the bounded campaign)
- `money`: `unavailable` — No amount is tied to this appeal. (scope: campaign)

## Review case: organisation-level financial disclosure (`cb_review_finance`)
- Evidence set: `cached-governed-review-case-finance-v1`

### Practices
- Unknown or not processed; see coverage.

### Campaigns
- Unknown or not processed; see coverage.

### Providers
- No provider relationship is asserted in this review set.

### Money facts
- `fm_review_total_cost`: 125000 AUD; `total_fundraising_cost`; period `FY2026`; scope `organisation (not attributed)`; linkage `unknown`; source wording: Fundraising expenses

### Coverage
- `practices`: `not_yet_processed` — Finance labels do not establish a method. (scope: selected financial statement)
- `campaigns`: `not_yet_processed` — Finance labels do not establish a campaign. (scope: selected financial statement)
- `providers`: `unknown` — No provider relationship is asserted. (scope: selected financial statement)
- `money`: `observed` — Direct source-native aggregate fundraising-cost fact; not allocated downstream. (scope: reporting entity, FY2026)

## Review case: insufficient scoped evidence (`cb_review_insufficient`)
- Evidence set: `cached-governed-review-case-insufficient-v1`

### Practices
- Unknown or not processed; see coverage.

### Campaigns
- Unknown or not processed; see coverage.

### Providers
- No provider relationship is asserted in this review set.

### Money facts
- No money fact available in the selected evidence.

### Coverage
- `practices`: `not_found_in_scoped_source` — No conclusion outside this reviewed source section. (scope: reviewed annual-report fundraising section)
- `campaigns`: `not_found_in_scoped_source` — No conclusion outside this reviewed source section. (scope: reviewed annual-report fundraising section)
- `providers`: `not_found_in_scoped_source` — No conclusion outside this reviewed source section. (scope: reviewed annual-report fundraising section)
- `money`: `unavailable` — No usable source-native money fact was present. (scope: reviewed annual-report fundraising section)
