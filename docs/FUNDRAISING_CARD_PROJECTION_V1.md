# Fundraising card/API projection v1

**Status:** review-only Builder projection; not a public-contract or release change.

`project_fundraising(card, money_links)` is the normal North-Star projection path for the bounded fundraising slice. It composes the typed practice, campaign and provider assertions already attached to a `CauseBaseCard` with supplied, governed money-scope links. It preserves their source wording, scope, lifecycle/currentness, source role, production method, evidence references and coverage states.

Money links remain an explicit compiler input pending a separately governed persistence and public-contract decision. The compiler rejects a link whose reporting entity does not match the card subject or whose evidence is absent from the card. It does not allocate an organisation or portfolio fact to a practice, campaign or provider.

The renderer presents distinct practices, campaigns, providers, money facts and coverage. Empty collections are not negative findings: the coverage section carries `unknown`, scoped non-finding, unavailable or not-yet-processed states. It does not calculate or display fundraising performance measures.

The deterministic fixture at `tests/fixtures/fundraising_card_projection.json` includes current F2F, historical campaign, unknown provider coverage and an organisation-level, non-attributed financial fact. The accompanying tests cover repeatability, provenance, missingness, historical/current separation and rejected subject binding.
