# G4 T4A provider-processing policy authority

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free  
HEAD: `15d28d56aefd0e9194e4bf1111b1819d30ef23b5`  
Branch: `gate3-cg406-remediation`  
Bridge fence: `v49`

## Result

Implemented a separate, content-addressed provider-processing authority in
`phase5_provider_processing_policy.py`. It composes the clean T1B/v29 rights
preflight only after exact policy, configured-provider, operation, source-family,
rights-record, subject/scope, source, and representation checks pass. The v29
`RightsGovernanceRecord` remains authoritative for local retention and the
independent public-redistribution axis; no competing rights registry or side
table was added.

The provider policy uses the existing source-owned OpenAI policy identity
`OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1` / `1.0.0`, the
Product Owner dated approval basis, ordinary retention with no data-sharing
opt-in, an exact allowlist of operations, Source Universe v1, and the bounded
ACNC register/AIS pilot. Policy provenance and review rule are required. An
operation-specific exclusion requires exact wording and an evidence locator.
Unknown policy/version, provider/project/model/service drift, stale or changed
rights, changed representation, local-axis denial, explicit exclusion, and
public-redistribution confusion all fail closed.

The authority accepts configuration metadata only: provider/project/service,
endpoint, model, delivery and reasoning settings, and retention posture. It
does not contain source bodies, prompts, credentials, tokens, provider
responses, or public-release material.

## Technical identity boundary

The existing source-owned configuration exposes the OpenAI policy identifier,
but does not expose an exact provider-policy registry/contract binding for the
current T4A send route. The new authority therefore has no guessed project,
service, model, or credential default: a caller must provide and match the
configured binding. The T3 evidence gap remains precisely
`provider_contract_identity_and_version`; this implementation does not claim
that gap is resolved and does not authorize a send.

## Verification

All runs were local and no-send:

- Focused provider-policy tests: **13 passed, 0 skipped, 0 failed**.
- Clean-archive focused provider + T1B tests: **17 passed, 0 skipped, 0 failed**.
- Clean-archive T3/T2 regression set: **40 passed, 0 skipped, 0 failed**.
- Provider/model calls: **0**; requests, receipts, reservations and cost entries: **0**; spend: **AUD 0.00**.

The existing local-private eligibility, deterministic v29 reload, and source /
representation hash checks remain unchanged. No external source, provider,
Drive, watcher, bridge, GitHub, publication, release, or gate state was
accessed or mutated. Pre-existing dirty and untracked paths were preserved.

## T4A route status

The no-send policy route and spend-plan preflight can proceed to independent
supervisory review using this authority. A hypothetical provider crossing must
still stop until the exact source-owned provider contract/configuration
identity and version are supplied and revalidated immediately before send.
This report makes no product-acceptance or Gate 4 closure claim.
