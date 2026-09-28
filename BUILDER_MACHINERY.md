# Builder machinery grounding map

**Status:** Compact operational companion to the canonical Builder architecture  
**Scope:** Existing evidence-acquisition, representation, interpretation, governance and projection machinery  
**Authority:** Subordinate to Builder `ARCHITECTURE.md` and shared product authority in CharityGraph Data

## 1. Purpose

The North Star says what CharityGraph is trying to know and project. This document says what Builder already has to acquire evidence, represent it, interpret it, govern it and compile projections. It is a grounding map, not a new architecture. Its purpose is anti-amnesia: a new session should encounter proven machinery before proposing a replacement scraper, parser, report path, OCR route or semantic harness.

## 2. New-session grounding order

Read these in order:

1. Data [`NORTH_STAR_TARGET_CARD.md`](https://github.com/gregorycwhill/charitygraph-data/blob/main/NORTH_STAR_TARGET_CARD.md), the active pointer to immutable North Star v0.2;
2. this `BUILDER_MACHINERY.md`;
3. Builder [`ARCHITECTURE.md`](ARCHITECTURE.md);
4. Data `CURRENT_STATE.md` plus the current roadmap and implementation plan; then
5. task-specific code, experiments or harness state.

The order keeps product intent and existing capability ahead of local implementation enthusiasm.

## 3. Stable operating invariants

- CharityGraph owns durable internal identity. The ACNC registered-charity record and ACNC UUID are the primary external charity-source spine. ABN is an external identifier and join key, not CharityGraph subject identity.
- Prefer source-native structured evidence before semantic reconstruction. ACNC profile/register data, AIS detail and lodged-report locators are baseline freebies before general web enrichment.
- Keep source, evidence, candidate, decision, canonical observation, coverage and derivative layers distinct. Cards are projections, not the internal knowledge store.
- Use native PDF extraction before OCR or model vision; escalate narrowly when unresolved material actually needs it.
- Python controls stable mechanics: acquisition, hashing, joins, preparation, scheduling, validation and release compilation. Unrestricted prose interpretation is a model task under the semantic heuristic gate.
- Model output is candidate knowledge unless promoted by applicable governance. Missing, not applicable, retrieval failure and not-yet-processed remain distinct states.
- Domain and section logic does not independently discover sources. Acquisition is centrally governed and reusable.

## 4. End-to-end machinery map

These are durable capability seams; filenames are current proven pointers and may move without changing the seam.

| Seam | Current/proven pointer | Role |
| --- | --- | --- |
| Subject/source identity | `ARCHITECTURE.md` typed record model; ACNC UUID bindings | Durable internal subject plus external source spine |
| ACNC profile and latest AIS | `scripts/acquire_acnc_public_profiles.py` | Dynamics search, charity UUID, entity/profile, latest submitted AIS and AIS detail |
| AIS structured projection | `src/charitygraph/phase2d.py` | Preserves `acnc-ais-detail` and projects structured program/financial observations |
| Filing/report discovery | `scripts/discover_public_sources.py`; `select_filing_documents` | Discovers Annual Report/Financial Report URLs from profile `Documents` and selects filings |
| Report acquisition and lineage | `scripts/run_baseline_charity_corpus_v1.py` | Filing and official-site acquisition, hashes and lineage |
| PDF/document representation | `src/charitygraph/baseline_corpus.py` (`represent_pdf`) | Source packet and document/page representation |
| OCR/visual escalation | `src/charitygraph/sources/documents.py`; `sources/vision.py`; `scripts/extract_private_reports.py` | Native extraction, diagnostics, established OCR, then narrow auditable vision |
| Source packet construction | `baseline_corpus.py` and corpus scripts | Bounded attributable evidence inputs |
| Semantic extraction/interpretation | whole-card and specialist contracts; `src/charitygraph/openai_client.py` | Model-assisted candidates and bounded derivatives |
| Governance/promotion | architecture governance records and applicable policies | Decisions, promotion, rejection and supersession |
| Projection | existing validation/reprojection/rendering path | Governed observations into cards and release candidates |
| Validation/release | existing RC4/release audit and validation machinery | Consistency, allowlists, diagnostics and release gates |

Historical/released evidence is part of this map: RC4 and released audits show `acnc-ais-detail`, `organisation-report-extract`, report rows and visual-escalation diagnostics operating on real charities.

## 5. Canonical ACNC path

The current-profile path is already solved and must be searched and reused before implementing a new scraper, bulk parser or search path:

**search charity → ACNC UUID → entity/profile → submitted AIS list → latest submitted AIS → AIS detail endpoint.**

`acquire_acnc_public_profiles.py` implements this public Dynamics path. `phase2d.py` retains the AIS detail source record and projects structured observations. The ACNC profile `Documents` collection is the first report-discovery surface: `discover_public_sources.py` finds Annual Report and Financial Report URLs, after which the filing selection and acquisition machinery applies. Bulk data may help with scale, ranking or history; it is not a reason to rebuild the current-profile/AIS path when that path meets the task.

## 6. Canonical document/PDF path

The established sequence is:

**source bytes and lineage → native PDF extraction → page diagnostics → local OCR where established → explicit gaps → narrow model vision for unresolved visual material → attributable observations.**

`extract_pdf_evidence` in `src/charitygraph/sources/documents.py` handles native extraction and extraction diagnostics. `sources/vision.py` provides narrow auditable vision for selected unresolved material, and `extract_private_reports.py` records the established report-extraction/vision escalation use. Do not jump directly from a URL to unrestricted prose or treat a model reconstruction as source-native evidence. `organisation-report-extract`, report-derived financial rows and visual-escalation diagnostics already exist in prior and released evidence.

## 7. Semantic machinery

Whole-card and specialist semantic contracts define bounded model tasks; `openai_client.py` is the existing transport boundary. Python prepares evidence, controls stable mechanics, validates shape, accounts for cost and routes outputs. The model interprets evidence, extracts typed candidates or writes bounded derivatives. Promotion remains a governed decision, not an automatic consequence of model output. Reprojection and rendering consume governed records; they do not become a second semantic store.

## 8. Before-building archaeology gate

Before implementing a new acquisition, representation, extraction, semantic or projection capability:

1. search this document;
2. search the current Builder implementation;
3. search released or historical evidence showing whether the path ran on real data;
4. classify the existing path as **current**, **reusable historical**, **intentionally superseded** or **genuinely absent**; and
5. only then implement a new path, with the reason and boundary recorded.

A disposable product spike may bypass production controls for learning, but it must not silently duplicate proven product machinery or become a second canonical path.

## 9. Product-feedback cadence

Development should regularly return visible product output on which semantic, editorial and user-value feedback can be given. Several consecutive execution turns without such output are a drift signal. Repeated `continue` without new product feedback is a smell unless the work is genuinely mechanical and already bounded toward a visible result. This is a cadence and attention rule, not a rigid numeric gate.

## 10. What this document is not / maintenance rule

This is not a replacement for `ARCHITECTURE.md`, a harness or runtime manual, a phase history, a list of every script, authority to revive superseded semantics or change public contracts, or a claim that every referenced historical implementation remains production-canonical forever.

It changes slowly: only durable capability seams, implementation-path moves, approved machinery-invariant changes or recurring rediscovery failures belong here. Do not add run IDs, transient hashes, branch heads, model prices or S0 attempt details.
