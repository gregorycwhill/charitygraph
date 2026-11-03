# CharityGraph live reality-spike product readout

Status: complete. This is non-production inspection material, not canonical CharityGraph data.

## Run facts

- Output root: `artifacts/reality-spike-live-2026-09-28/`
- Exact machine summary: `artifacts/reality-spike-live-2026-09-28/run_summary.json`
- Exact script: `scripts/reality_spike.py`
- Charities/cards: 3; model calls: 3; warnings: 0.
- Recorded model for all three responses: `gpt-5.6-terra`.
- Card folders: `01-74068758654`, `02-37646526132`, `03-47613674461`.
- Each folder contains `sources.json`, `retained_evidence.json`, `model_response.json`, `card.json`, and `card.md`.

## Medecins Sans Frontieres Australia Limited — ABN 74068758654

Card path: `01-74068758654/card.json`; readable presentation: `01-74068758654/card.md`.

The most useful propositions/sections are:

1. Identity: active Australian public company, ACN, ACNC registration date, and NSW 2007 main business location.
2. Purpose: the organisation describes itself as an independent medical humanitarian organisation responding to conflict, epidemics, disasters, and exclusion from healthcare.
3. Activity scope: medical humanitarian assistance, with the retained site presenting work areas and crisis-response navigation.
4. Geography: a clearly qualified distinction between the Australian entity's registered location and the wider movement's claim of projects in more than 70 countries.
5. Workforce/scale: global movement and 2022 workforce figures are retained, but explicitly not attributed to the Australian legal entity.
6. Relationships: the Australian office, New Zealand entity, worldwide movement, and international association are surfaced with the legal/control relationship left unresolved.
7. Current operating evidence: active regulator status plus current-looking official-site content, explicitly labelled as not independent verification of operations or outcomes.
8. Source-reported claims: medical ethics/impartiality/independence/neutrality, support for 100+ Australian/New Zealand professionals annually, and global donor/funding claims.

Sources and roles:

- Regulator identity/status: https://abr.business.gov.au/ABN/View?abn=74068758654
- Official purpose and organisational context: https://www.msf.org.au/about-us
- Official activity-scope context: https://www.msf.org.au/our-work
- Live discovery (retrieved but bot-challenged and non-substantive): https://html.duckduckgo.com/html/?q=%22Medecins+Sans+Frontieres+Australia+Limited%22+%2274068758654%22

Missingness/limitations: no retained audited financials, revenue, expenses, assets, fundraising allocation, board/executive detail, entity-level project list, service volumes, beneficiaries, independent impact/effectiveness evidence, or resolved legal relationship to the wider MSF movement. This is recognisably useful as a cautious CharityGraph discovery card: it combines identity, purpose, activity, geography, relationships, operating signals, and explicit provenance/unknowns, but it is not a complete entity profile.

## SUNRISE FOUNDATION LIMITED — ABN 37646526132

Card path: `02-37646526132/card.json`; readable presentation: `02-37646526132/card.md`.

The most useful propositions/sections are:

1. Identity: Australian public company, ABN/ACN, and active status from 10 Dec 2020.
2. Geography: NSW 2323 is recorded as the main business location, without treating it as a service area.
3. Registration/relationship: ACNC charity registration, Public Benevolent Institution classification, and DGR endorsement are surfaced.
4. Current operating evidence: active ABN status is recorded, but correctly not treated as proof of current service delivery.
5. Tax/status claims: GST and tax-concession endorsements are retained as regulator-reported claims.
6. Explicit unknowns: mission, beneficiaries, activities, workforce, finances, programs, governance, impact, and ROI are all marked not established.

Sources and roles:

- Regulator identity/status/classification: https://abr.business.gov.au/ABN/View?abn=37646526132
- Live discovery (retrieved but bot-challenged and non-substantive): https://html.duckduckgo.com/html/?q=%22SUNRISE+FOUNDATION+LIMITED%22+%2237646526132%22

Missingness/limitations: no usable official website or substantive discovery evidence was retained; mission, program scope, beneficiaries, geography beyond the registry location, scale, financials, governance, and outcomes are absent. It is a useful but very thin CharityGraph card for identity/status triage and evidence-aware missingness; it does not yet satisfy the product promise of a meaningful organisation profile.

## Noongar Boodja Trust — ABN 47613674461

Card path: `03-47613674461/card.json`; readable presentation: `03-47613674461/card.md`.

The most useful propositions/sections are:

1. Identity: ABN Lookup names the entity “The Trustee for Noongar Boodja Trust” and records it as a Fixed Trust.
2. Status: active ABN and GST registration from 29 Mar 2021.
3. Geography: WA 6000 is recorded as the main business location, explicitly not a service geography.
4. Registration: ACNC registration is surfaced.
5. Tax/status claims: GST concession, income-tax exemption, and FBT rebate are retained; the record says the entity is not entitled to tax-deductible gifts.
6. Operating evidence: regulator status is separated from evidence of current charitable activity.
7. Explicit unknowns: purpose, beneficiaries, programs, outcomes, leadership/trustee identity, staffing, finances, and service geography are all marked not established.

Sources and roles:

- Regulator identity/status/classification: https://abr.business.gov.au/ABN/View?abn=47613674461
- Live discovery (retrieved but bot-challenged and non-substantive): https://html.duckduckgo.com/html/?q=%22Noongar+Boodja+Trust%22+%2247613674461%22

Missingness/limitations: no substantive official or discovery source was retained. The card cannot establish mission, activities, beneficiaries, trustee/leadership, financial scale, outcomes, or operational geography. It is useful as a cautious identity/status card and as a clear demonstration of missingness, but not yet as a rich product card.

## Component diagnostic inventory

### REUSED_SUCCESSFULLY

- `src/charitygraph/openai_client.py` via `responses_create`: 3 successful structured model responses.
- Existing North Star card semantics/schema concepts: identity, purpose, programs, geography, scale, finance, relationships, operating evidence, claims, unknowns, cautions.
- Local source/evidence/card rendering conventions in the spike script: manifests, retained excerpts, model metadata, `card.json`, and `card.md`.

### BYPASSED_FOR_SPIKE

- Governed production acquisition and provenance adjudication.
- A3/reservation/economics/accounting paths.
- Production card projection/publication and canonical data writes.
- Replay/identity hardening and Top100 workflows.

### BROKEN_OR_BLOCKING

- No spike component blocked card generation. The live discovery endpoint returned bot challenges for all three searches, limiting evidence for Sunrise and Noongar and adding no substantive evidence for MSF.
- The run140 harness cleanup crash was outside acquisition/model/card generation and is not a card-output defect.

### NOT_NEEDED

- S0/Attempt20 runtime, A3, pricing capture, hashes, replay IDs, publication schema, production accounting, and broad tests/refactors.

## Retention and change boundary

`scripts/reality_spike.py` is worth retaining as a product-development inspection tool: it is small, explicit about non-production scope, records sources/evidence/model metadata, uses structured output, and renders human-readable cards. It should not be mistaken for a production acquisition path; no refactor is proposed here.

Observed git status in the ordinary Builder repository shows run140's spike additions as `scripts/reality_spike.py` and the untracked `artifacts/` output tree, alongside pre-existing/unrelated Builder changes (`scripts/run_v12_from_preflight.py`, deletion of `scripts/run_v12_large_harvest.py`, and other untracked archaeology/builder directories). No commit or PR was created.

Attempt20/S0 confirmation: this readout inspected only the ordinary Builder repo and the local spike output. `.s0-attempt20-history-builder`, `C:\CharityGraph-runtime\s0-attempt20-final-rebind-runtime-v2`, and Attempt20/S0 runtime, A3, reservation, and publication state were not touched.

CHARITYGRAPH_LIVE_REALITY_SPIKE_READOUT_COMPLETE
