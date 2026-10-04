# Fundraising archaeology and state map — 2026-10-04

## Purpose and snapshot

This is a before-building map for the Fundraising / F2F-currentness / structured-financials slice. It is an implementation-planning record, not a new semantic contract or a source-acquisition authority.

| Repository / checkout | Observed SHA / state | Role in this map |
| --- | --- | --- |
| Builder `charitygraph` | `215173392db12cdddfc4bff7f211fd86f2448b49`, branch `charitygraph-structured-source-and-prose-harvest`, dirty | Current local implementation; read only because it contains predecessor-campaign changes. |
| Data `charitygraph-data` | `f514df3119c28acf9d552ff204488062ba7ddf88`, branch `phase5-direct-service-v1.2-closeout`, dirty only for campaign directories/history archive | Canonical product/documentation authority. |
| Builder remote/canonical reference supplied at campaign construction | `2221d4e1c252451dbea3e4e98ae0d535cd36e6d1` | Construction-time reference only; the local checkout has legitimately advanced. |
| Data remote/canonical reference supplied at campaign construction | `1513648ec358645c23ff49a34769ae91365bf47e` | Construction-time reference only; the local checkout has legitimately advanced. |

This record was made in isolated Builder worktree branch `cg-fundraising-archaeology-287` at the Builder local HEAD. No predecessor worktree was modified.

## Authority and North Star seam

`charitygraph-data/DOCUMENT_AUTHORITY.md` makes the integrated model and domain authorities controlling over working designs and historical artefacts. The relevant design inputs are:

- `FUNDRAISING_KNOWLEDGE_DESIGN.md:130-171,250-303,640-671`: funding source, standing practice, campaign and expenditure are separate; historical F2F is not current F2F; the legacy flat method list is only exploratory.
- `FUNDRAISING_INDUSTRY_SOURCE_DESIGN.md:141-172,680-784`: PFRA is a bounded experimental source family, current membership is strong evidence of a recent F2F program in its domain, and the listed hard cases prohibit inferred agency, setting, effectiveness and currentness.
- `NORTH_STAR_TARGET_CARD.md:180-216,590-607`: section 8 needs multi-axis practice context (setting, delivery party, compensation, time); section 13 retains source-faithful finance; the F2F question crosses fundraising, relationships, workforce/contractor, time and evidence.

The slice maps to North Star **8** (practice/campaign), **12** (provider and delivery-party relationships), **13** (financial record, accounting scope and expenditure) and **20** (source/evidence/coverage/freshness). It reuses identity binding, source/evidence records, coverage observations, reporting-period fields, `MoneyObservation`, financial-record IDs and the Phase-5 projection gate. It does not yet justify scale, a method-performance model, public-contract change, or Top-100 processing.

## Capability matrix

| Capability | State | Evidence / exact implementation | Consequence |
| --- | --- | --- | --- |
| Direct source-faithful money and scale | Proven/current | `src/charitygraph/models.py:135-162` `MoneyObservation`; `tests/test_money_observation.py:9-35` | Reuse for direct expenditure and financial components. |
| Financial rows, statements, functional allocations | Proven/current | `models.py:192-383`; `phase2d.py:470-529`; `tests/test_phase2d_statements.py:7-75` | Reuse native rows/period/scope before any fundraising interpretation. |
| Explicit coverage for unavailable expenditure | Proven/current | `models.py:648-666`; `phase2a.py:92`; `phase2d.py:507-508`; `tests/test_phase2a.py:63-81` | Preserve `not_available_from_source`, never turn silence into zero/absence. |
| Direct expenditure estimate | Proven but legacy-card-bound | `fundraising.py:18-44`; `tests/test_fundraising.py:17-22`; financial-record linkage validated in `tests/test_financial_reconciliation.py:9-19` | Can inform migration, but output is legacy `FundraisingEstimate`, not governed observation. |
| Bounds with definite/possible/excluded components | Experimental but sound narrow arithmetic | `src/charitygraph/v05/fundraising.py`; `tests/test_v05_fundraising_bounds.py:9-17` | Reuse the arithmetic principle only after source/evidence and accounting-scope envelopes are supplied. |
| PFRA directory acquisition and exact-domain binding | Experimental adapter | `baseline_corpus.py:373-425`; `scripts/run_baseline_charity_corpus_v1.py:586-621`; `tests/test_baseline_corpus.py:134-143` | It currently records membership/source lineage, not a typed F2F practice/currentness observation. |
| FIA / Donor Republic / Funraisin adapters | Research design only | `FUNDRAISING_INDUSTRY_SOURCE_DESIGN.md:680-714` | No production adapter found in scoped Builder/Data search. |
| F2F practice, setting, delivery party, compensation and lifecycle | Missing typed implementation | No F2F-specific class or test was found in current Builder; only legacy `FundraisingMethodObservation` at `models.py:546-559`. | First implementation target; it must be scoped/time/evidence bound, not a Boolean. |
| Named fundraising campaign | Missing typed implementation | No campaign model/adapter found; only Phase-5 predicate history below. | Build separately from standing practice. |
| Provider relationship | Partly proven generic substrate; fundraising specialization missing | Generic `SubjectRelationship` is retained and evidence-checked in `models.py:636-679`; no fundraising-provider relation model or PFRA-bulletin adapter found. | Reuse generic relationship/time/evidence machinery; add no agency inference. |
| Currentness/freshness | Weakly typed / incomplete | Legacy `FundraisingMethodObservation.status` has `current/historical/stale/unknown` and dates, `models.py:546-559`; no evidence-time or review-state lifecycle contract is enforced. | Do not rely on status alone for current F2F. |
| North-Star fundraising/campaign distinction | Projection vocabulary only | Historical commits `03436b441066f6a5d015ef111d3d75bcc78f9666` and `f85efdce6f152096d485d7eb626ea700dd6cc32d` add/test predicates `fundraising_practice_observed` and `fundraising_campaign_observed`; current `north_star_projection.py` is only assignment/gating shell. | Predicate names are not a typed observation implementation. |
| Legacy method taxonomy | Obsolete/unsafe as durable model | `models.py:546-559`; design diagnosis `FUNDRAISING_KNOWLEDGE_DESIGN.md:143-171`. | Retain only in compatibility adapters; do not extend or elevate it. |

## The historically described estimator: exact finding

The scoped history proves that the surviving routine is **not an F2F estimator**. `src/charitygraph/fundraising.py:18-74`, introduced in the Phase 0.5 lineage (`e3a216f8f24a007030ef462bc14634423bf4fe20`) and amended by `f21efbb2ccf6867a5ec6cdc4eb5d76c0cbf81cd9` (“Align fundraising expenditure with canonical policy”), defines `estimate_fundraising(source)`.

It estimates one legacy-card **annual fundraising-expenditure scalar** from either:

1. `source["fundraising"]["direct"]`, emitted as `direct_extract`; or
2. an exact, local English-label list (`marketing`, `public relations`, `pr`, `fundraising events`, `donor acquisition`), emitted as `heuristic_estimate`, rule `CB-FUND-H03`.

The associated test `tests/test_fundraising.py:24-35` explicitly expects the heuristic sum of Marketing plus Public relations. Thus it estimates neither F2F use, F2F setting, provider, regular giving, campaign, lifecycle/currentness, nor fundraising effectiveness. It is also unsafe for new work: the label list is an unapproved semantic heuristic under `AGENTS.md` and can misattribute general marketing/PR. `f21efbb` removed priors/peer fill and correctly permits `None`, but did **not** remove `CB-FUND-H03`.

The separate `v05/fundraising.py` is not the old estimator: it only computes disclosed attribution bounds and correctly leaves `point_estimate=None`. No other F2F estimator was found by scoped all-history search over Builder source/tests for `F2F`, `face_to_face`, `estimate_fundraising`, `FundraisingMethodObservation`, `heuristic_estimate`, and `CB-FUND-H03`.

## Current projection paths and gaps

1. Legacy cards: `pipeline.py:124-160` passes the legacy estimate into `CauseBaseCard.fundraising_expenditure`; `render.py:159-161` exposes scalar/method/confidence. `change_detection.py:51` still treats `fundraising_methods` and expenditure as one change family.
2. Report extraction: `phase2d.py:492-493` creates `FundraisingMethodObservation(method="other", status="current")` merely because a page contains `fundrais`; this is explicitly unsafe and conflicts with the semantic gate/currentness requirements. `phase2d.py:507-508` correctly records unavailable expenditure coverage after processing relevant pages.
3. Baseline PFRA: it has separate charity/agency role records and exact-domain matching, but does not project a practice, campaign or relationship assertion. This is the appropriate adapter starting point, not evidence of a complete F2F capability.
4. Phase-5 successor: historical `north_star_projection.py` distinguishes section-8 practice/campaign predicates in a projection response; current `src/charitygraph/north_star_projection.py` contains only immutable section assignments plus a compatibility gate. It has no observation payload, evidence link, time interval, scope, setting or provider field.

## Ordered next work

1. **Quarantine legacy semantics before reuse:** prevent new callers from using `estimate_fundraising` and the `phase2d.py:492` keyword-derived “current” method. Preserve legacy release compatibility; do not silently delete it.
2. **Introduce the smallest governed observation contract:** separate practice and campaign, with source wording, mapping disposition, subject/scope, effective/observed/assessment time, evidence/source IDs, and explicit unknowns. Model setting, delivery party and compensation as independently evidenced facets, not F2F defaults.
3. **Wire a PFRA fixture-only adapter:** exact binding only; current membership may emit a time-bounded F2F practice candidate with its source semantics. It must not emit agency relationship, street/door/private-site, regular-giving, compensation or universal currentness. Add all twelve design hard cases before any acquisition/scale.
4. **Add finance attribution envelope before computation:** retain source-native rows, accounting entity/period/basis and definite/possible/excluded component treatment; allow direct, deterministic reconstruction, bounds, or unavailable. Remove/disable `CB-FUND-H03` only through a compatibility-aware change and tests.
5. **Only then project:** attach the governed observations to the Phase-5 section-8/12/13/20 path and add freshness/coverage tests. FIA/P2P adapters remain research-dependent until their source-role/rights/identity fixtures are proven.

## Deliberately untouched

No source was acquired, no provider/model call made, no public schema/release altered, and no claim was promoted. This remains a Tier-1 archaeology result: it does not establish fundraising ROI, allocation of aggregate revenue/expenditure, causal effectiveness, or corpus-scale readiness.
