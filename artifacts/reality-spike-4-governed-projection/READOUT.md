# Reality Spike 4 — governed projection archaeology

## Principal token

`REALITY_SPIKE_4_PRODUCT_PIPELINE_DISCOVERED`

## Reproducibility

Builder local HEAD: `9768d619a2129d4a2d1823b456fb2813c1452bee`.  The worktree is dirty: pre-existing modified/deleted v12 scripts and numerous untracked campaign/archaeology/Spike 1–3 files; this experiment adds `scripts/reality_spike_4_disposable_bridge.py` and this output directory. The result is therefore a dirty-worktree run, not a HEAD-only claim. No provider call was made (USD 0).

## Inputs and executed path

Reused exactly: `artifacts/reality-spike-3-acnc-substance/{37646526132,74068758654,47613674461}/packet.json`, their selected filing PDFs and Spike 3 cards. Path actually executed:

`retained ACNC profile/latest AIS + filing representation → experimental SourceRecord/EvidenceFragment descriptors → typed historical-vNext SubjectRecord/ScopeRecord/Observation → EXPERIMENTAL_PRODUCT_OWNER_PROMOTION CardEvidence → integrated_card.project_subject / compile_matrix → Markdown card and JSON projection`.

The source record and evidence descriptor are retained in each `experimental_governed_records.json`; the full typed graph is validated by `IntegratedGraph`. The bridge deliberately maps only exact ACNC fields and profile collections. It neither extracts report prose nor calls a model.

## Machinery map

| Seam | Pointer | Classification / evidence | Composable now / missing adapter |
|---|---|---|---|
| ACNC acquisition, AIS and documents | current `scripts/acquire_acnc_public_profiles.py`; `baseline_corpus.py` | current; Spike 3 packets prove three real ABNs and filings | yes; cached packet adapter required |
| PDF representation | current `baseline_corpus.represent_pdf` | current; retained PDF representation diagnostics | yes; semantic extraction is separate |
| current card model/rendering | `models.py`, `render.py`, `phase2d.py` | intentionally superseded/RC4-bound; historical release compiler | not directly; it wants RC4 CauseBaseCard |
| current North Star lens | `north_star_projection.py` | current contract only; no executable compiler | assignment only |
| governed vNext records/persistence | historical `bitemporal-governed-knowledge-v1/contracts`, `runtime/catalog.py` | reusable_historical; typed records and tests exist | adapter from packet/source records required |
| vNext 20-section compiler | historical `integrated_card.py` | reusable_historical; executable `project_subject`, `compile_matrix` and contract tests | yes; bridge calls it unchanged |
| section reprojections | historical `section13_*`, `section3_6_11_*`, `section7_*`, `section14_*`, `section16_*` | reusable_historical but section-specific and campaign-bound | no general packet adapter |
| semantic contracts / complete card | historical `whole_card_semantic_v02.py`, `phase5_semantic_contracts.py` | reusable_historical; Phase 5 artifacts/tests | provider/campaign and adjudication path disconnected |
| readable product renderer | current `render.py` is RC4 card renderer; vNext compiler returns JSON only | genuinely absent integration seam | disposable Markdown renderer used |

No `BUILDER_MACHINERY.md` exists in the accessible Builder/Data checkout despite recursive search; the map above substitutes the required current/historical evidence inspection, and does not create acquisition, parsing, OCR, provider, semantic-store, canonical renderer, or identity machinery.

## Disposable decisions and consequences

1. **Promotion fork:** current human governance cannot be naturally invoked from retained packets. Chose `EXPERIMENTAL_PRODUCT_OWNER_PROMOTION`. Consequence: 8–12 evidence-backed observations per charity reach 20-section coverage, but remain `EXPERIMENTAL_REVIEW`, never canonical.
2. **Projection fork:** current lens has no compiler. Chose the historical vNext `integrated_card` compiler rather than write a new 20-section compiler. Consequence: all cells have explicit missingness and a real contract, but dependency is historical.
3. **Semantic fork:** report text/model route unavailable. Chose exact source-native fields only, no faux model prose. Consequence: 9 of 20 sections remain explicitly `NOT_PROCESSED`; reports improve trust metadata but not substantive output.

## Outputs and delta

Sunrise: Spike 2 [card](../reality-spike-v2-acnc-first-2026-09-28/02-sunrise-acnc-f1413902/card.md), Spike 3 [inspection](../reality-spike-3-acnc-substance/37646526132/card.md), Spike 4 [projection](37646526132/card.md) and [typed graph](37646526132/experimental_governed_records.json). Spike 4 makes the passage from evidence to sectioned governed observations visible, including source/evidence IDs, promotion status and honest missingness. It does not add semantic content over Spike 3.

MSF: [projection](74068758654/card.md). Noongar: [projection](47613674461/card.md). Multi-charity comparison: [matrix](COHORT_COMPARISON.md).

All three: sections 1, 2, 3, 4, 5, 10, 11, 13, 14, 17 and 20 receive `EXPERIMENTAL_REVIEW` where the packet supplies values; 6–9, 12, 15, 16, 18 and 19 are `NOT_PROCESSED` unless a particular packet lacks another mapped field. See `cohort_matrix.json` for exact per-charity counts.

## Top product gaps (ranked by consequence)

1. No current packet-to-governed-record adapter.
2. No current 20-section projection compiler/renderer.
3. Report representations do not reach semantic candidates or cards.
4. Governance/promotion cannot practically operate over acquired current evidence.
5. North Star is a contract/lens, not a product assembly path.
6. RC4 cards, vNext contracts and campaign pipelines are overlapping stores.
7. Missingness is strong in historical integrated-card but absent from current direct-render spike path.
8. Section specialists are isolated, campaign/RC4 bound and not generalised.
9. Subject identity is deliberately not resolved by the packet; the bridge uses experimental ABN join identities.
10. 100-charity scale would amplify manual promotion, per-phase translation and report semantic bottlenecks first.

## Stress-question answers

1. Perfect evidence: current path surfaces little without bespoke adapters; this run surfaces only exact structured ACNC fields through disposable glue.
2. Working projection: historical generic vNext compiler and isolated specialists; current has only assignment contract. The remaining sections are contracts/examples/history.
3. Observation-first is executable in historical vNext contracts, but current runnable card machinery remains phase-specific/RC4-shaped.
4. Several overlapping stores exist: Spike packets, RC4 CauseBaseCard, historical vNext graph/catalog, and phase campaign artifacts.
5. This run needs four translations: packet→source/evidence, source→observation, experimental decision→assignment, graph→Markdown.
6. Historical integrated cards are projections; current RC4 cards still co-locate much semantic state.
7. Explicit coverage survives in `CoverageInput`/`SectionCoverage`; it is lost in direct source-native cards and unprocessed reports.
8. Reports mostly accumulate inaccessible provenance today; this bridge uses their count/readiness only.
9. At 100 charities, promotion/adjudication and semantic report extraction fail first, followed by phase-specific adapter maintenance.
10. PDF representation/OCR escalation is mature in isolation, not evidence-to-product.
11. “Simple 20-section card” hides acquisition, identity, evidence, candidate, governance and projection translations.
12. Honest evidence/coverage cards are easier: the historical compiler already expresses them once observations exist.

## Validation and next tranche

Ran the bridge successfully for three packets; generated typed graphs/projections/matrix. The existing Spike 3 pytest command was attempted but blocked before tests by sandbox access denial to the user Temp pytest directory; it is unrelated to bridge semantics. No mature source machinery was added: the only code is disposable composition calling retained packet data and historical compiler types.

Next: a bounded current adapter that persists SourceRecord/EvidenceFragment/Candidate/Decision records under the current runtime, then replay one report through the existing OCR/vision/extraction route and one actual governed adjudication into sections 3, 9, 16 or 18. Success criterion: delete this bridge while preserving the visible projection.
