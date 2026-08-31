# CharityGraph Builder Architecture

**Status:** Canonical Builder implementation authority  
**Version:** 0.3.0-draft  
**Scope:** local internal knowledge construction, governed review, private evidence/archive boundary, and validated Builder-to-Data release candidates; not a public-schema proposal  
**Reconciled:** 2026-08-23 from approved target architecture revision 0.1.1, retaining the required v0.2 amendments

This architecture implements the shared authority in the sibling Data repository. Read [DOCUMENT_AUTHORITY.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/DOCUMENT_AUTHORITY.md), [PRODUCT.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/PRODUCT.md), [PRINCIPLES.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/PRINCIPLES.md), [INTEGRATED_PRODUCT_AND_DATA_MODEL.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/INTEGRATED_PRODUCT_AND_DATA_MODEL.md), [COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md), [SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md), [TAXONOMY_AND_SCHEME_GOVERNANCE.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/TAXONOMY_AND_SCHEME_GOVERNANCE.md), and [PUBLIC_CONTRACT_0_5.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/PUBLIC_CONTRACT_0_5.md) before changing internal or release-boundary behaviour.

## 1. Decision in one sentence

Builder vNext will be a local, Python-controlled and LLM-powered pipeline that turns immutable source material into typed candidates, policy-governed canonical observations and separately versioned derivatives; CharityGraph cards and releases will be projections of those records, not Builder's internal data model.

This is a rearchitecture, not a rewrite of the evidence. The existing archive, source records, extracts, schemas, model runs, human decisions, public releases, and golden cases are migration inputs and validation evidence.

## 2. What the archaeology establishes

The current Builder contains valuable working solutions, but they accumulated around successive release phases rather than a durable internal architecture.

The strongest retained findings are:

- The three-layer public contract—source-native, canonical, derived—is sound.
- The private processing path needs two additional layers: **candidate** and **governed decision**.
- A public card is too broad and release-specific to be the internal unit of work.
- The legacy internal card model and the v0.5 public `Card` are both historical/public projections, not a universal vNext model.
- Source absence, retrieval failure, non-applicability, and not-yet-processed must remain distinct.
- Identity binding is an explicit governed process; names and domains never create subject identity.
- Extraction method and claim basis are independent.
- Deterministic acquisition, hashing, obvious structure recovery and evidence preparation should constrain semantic work; they must not become a brittle substitute for routine model-assisted interpretation.
- The Phase 2A synthesis call combined evidence interpretation, taxonomy assignment, uncertainty handling, and editorial writing in one model response. Those tasks have different validity and refresh rules and must be separated.
- Historical cache identity based on evidence, prompt, taxonomy, and model was directionally correct, but cache records lacked explicit task and subject identity.
- Lineage inferred merely from a shared subject is not lineage. Causal relationships require typed edges.
- A model result is not a human decision. Governed decisions require authority, rationale, applicability and supersession semantics. A model candidate may become canonical through an explicit benchmarked automation policy, but never merely because a model emitted it and never under a human-governed label.
- All 114 audited v0.5 `legacy_unbound` origins are recoverable from the immutable RC4 cards when the documented canonical JSON hash is used. The 1,399 origin-only items are preserved historical assertions, not unresolved origins and not canonical facts.
- The 299 synthesis-cache records are recoverable experimental runs. They demonstrate prompt evolution and cost, but they are not governed canonical observations.
- The current archive is active CharityGraph evidence, not a legacy archive. Old releases and identifiers remain historical; the active workspace and operating paths use CharityGraph.

## 3. Architectural boundaries

Builder has four responsibilities:

1. **Evidence engineering:** acquire, retain, parse, normalise, bind, and retrieve public-source evidence.
2. **Knowledge production:** produce typed candidates, apply governed promotion decisions, and maintain canonical observations.
3. **Derivative production:** create summaries, classifications, embeddings, similarities, and transparent analytics from governed inputs.
4. **Release compilation:** project selected canonical records and derivatives into a validated immutable CharityGraph Data release.

Python is the control plane: it acquires, hashes, parses obvious structure, selects evidence, joins, batches, schedules, caches, validates, accounts for cost and compiles releases. LLMs are the routine semantic engine: they recover difficult text/vision, screen relevance, extract typed facts, interpret activities and participation, classify, adjudicate and write bounded derivatives.

Builder is not:

- the public data repository;
- the Viewer;
- a generic knowledge graph or EAV database;
- a recommendation or mandate-decision engine;
- an LLM that writes whole cards directly from a dossier;
- a system in which an operational database, cache state, or a current card is the sole source of truth.

## 4. Internal record model

The internal model is a typed artefact graph. Each persisted artefact has an ID, schema name and version, content hash, creation provenance, and explicit relationships to its inputs.

| Record | Purpose | Authority |
| --- | --- | --- |
| `SubjectRecord` | Durable opaque `subject_id`, subject kind, lifecycle, identity attributes, external identifiers and provenance | Governed identity authority |
| `ScopeRecord` | Program, service, unit, fund or other scoped thing related to a subject, with time and promotion status | Governed scoped identity |
| `SubjectRelationship` | Real-world relation between subjects/scopes, distinct from production lineage | Governed relationship observation |
| `SourceBlob` | Immutable acquired bytes plus retrieval and integrity metadata | Upstream evidence, privately retained |
| `SourceRecord` | Source-native structured record or document/page representation | Upstream observation; not automatically canonical |
| `SubjectBinding` | Resolution of a source record to zero, one, or multiple subjects | Governed or policy-authorised binding |
| `EvidenceFragment` | Bounded attributable text, table cell, visual region, or structured field | Evidence input; not a proposition by itself |
| `CandidateObservation` | Typed proposed proposition extracted or interpreted from evidence | Unapproved private candidate |
| `DecisionRecord` | Human or explicitly governed-policy disposition of candidates | Promotion/rejection authority |
| `CanonicalObservation` | Accepted typed assertion with scope, time, evidence, and claim basis | Internal canonical knowledge eligible for projection |
| `CoverageAssessment` | Result of applying a defined assessment scope to available evidence/observations | Governed current-state assessment |
| `DerivativeArtifact` | Summary, classification, embedding, similarity, or analytic projection | Recomputable output with independent lineage |
| `BudgetCohort`, `BenchmarkDefinition`, `SourceOpportunity`, `PropositionReviewLedger`, `CostLedger`, `PricingSnapshot` | Versioned processing cohort, donor-exposure proxy, evaluation opportunity, adjudication, pricing and economics records | Private evaluation and cost authority |
| `CorrectionSubmission`, `CorrectionProposal`, retraction/challenge records | Private intake and governed contestability workflow | Governed correction authority |
| `TaskRun` | One deterministic, local-model, or remote-model execution | Operational and reproducibility record |
| `RunManifest` | A bounded pipeline invocation, its configuration, inputs, outputs, and failures | Operational audit record |
| `ReleaseProjection` | Exact selection and transformation into a public contract | Candidate release input |

The common envelope must not turn domain payloads into generic key/value claims. Financial rows, activities, beneficiaries, relationships, classifications, programs, fundraising practices, campaigns, and other domains retain typed schemas.

### Subject, scope and correction invariants

`SubjectRecord` lifecycle supports creation, active/inactive status, merge, split, predecessor, successor and tombstone semantics without silently reassigning identity. Source bindings are reversible and retain resolution basis, conflict and review state. Names, domains, filenames and structural proximity never create a subject or subject binding. A program or service may stay a `ScopeRecord` until governed evidence justifies durable promotion.

Artefact lineage explains how a record was produced; `SubjectRelationship` explains the world. Neither may be inferred from the other. `about_subject` is an indexable association only, never causal lineage.

Role-bearing `RelationshipStatement` records preserve directed source and target
subjects, optional governed scope, evidence and temporal bounds. The structured
activity roles are `operator`, `deliverer`, `funder`, `sponsor`, `partner`,
`auspice` and `network_context`; they remain distinct from the legacy
relationship type/predicate and are never inferred by scanning prose. A shared
domain or network context does not propagate proposition ownership, and a
replacement relationship is retained append-only through directed supersedes
lineage.

Raw correction submissions remain private. Moderation creates a `CorrectionProposal`; a governed `DecisionRecord` accepts, edits, rejects, holds, retracts or otherwise disposes of it. An accepted change creates append-only replacement artefacts and typed `invalidates` edges to affected candidates, coverage, derivatives and release projections. Challenges and exceptional privacy/legal removal follow explicit procedures; no published object is silently hand-edited.

#### Domain-policy invariants

Claim basis and extraction method are independent. Legitimate conflicting observations are retained with reconciliation status. Funding source, standing fundraising practice, campaign and expenditure are separate typed domains. Fundraising expenditure may be unavailable/null; universal priors, peer-imputation fill, forced midpoint and forced point estimates are prohibited.

Participation is populated from initial production, with stable modes distinct from transient opportunities and action destinations distinct from evidence URLs. Ethos is separate from service/mission orientation. `notable_context` is neutral, sourced context rather than a score. Evaluated shadow registries are only claim-specific authorities: membership, applicable code or stated fee rule may be direct candidates under a versioned source-role policy, but membership does not prove compliance and a fee rule does not establish member-specific spend or volume. Promotional/provider-effectiveness claims remain source-native or review-only until separately governed.

### 4.1 Identifiers and schema names

- Use `subject_id` throughout Builder vNext. Do not encode either the current or former brand into a new internal identifier name.
- The v0.5 compatibility adapter maps `subject_id` to the legacy public subject-identifier field required by that immutable contract. The literal historical field name is confined to adapter code, compatibility tests, and quarantined migration material.
- New internal artefact IDs use type-specific prefixes such as `srcblob:`, `srcrec:`, `binding:`, `evidence:`, `candidate:`, `decision:`, `observation:`, `derivative:`, `taskrun:`, and `run:`.
- IDs are stable opaque identifiers or deterministic hashes only where the identity rule is documented. A filename is never the identity.
- Private schema identifiers use `urn:charitygraph:builder:schema:<record-name>:<major.minor>` until and unless a schema becomes part of the public Data contract.
- Public contract schema IDs remain the canonical `charitygraph-data` GitHub URLs. Public contract 0.5 is implemented compatibility authority; a future public contract requires separate governance.
- Python packages, commands, environment variables, logs, schemas, documentation, and current outputs use `charitygraph`. Former-brand compatibility surfaces remain isolated from vNext modules and are not copied into new designs.

## 5. Typed lineage

Every relationship states what happened. The initial controlled edge vocabulary is:

| Edge | Meaning |
| --- | --- |
| `acquired_as` | Retrieval produced a source blob |
| `parsed_from` | A source record was deterministically parsed from a blob |
| `bound_to` | A governed resolution associates a source record with a subject |
| `excerpted_from` | An evidence fragment was selected from a source record/blob |
| `proposed_from` | Evidence produced a candidate observation |
| `reviewed_by` | A decision disposed of a candidate |
| `promoted_as` | An accepted candidate produced a canonical observation |
| `derived_from` | A derivative or mechanical observation depends on specified inputs |
| `supersedes` | A newer decision/observation replaces an earlier one without erasing it |
| `invalidates` | A change makes a prior derivative or assessment unusable |
| `projected_as` | An internal record became a public release object |
| `included_in_release` | A projected object is present in a named immutable release |

`about_subject` may be stored as an indexable association, but it must never be interpreted as causal lineage.

## 6. Pipeline stages and gates

The production flow is:

```text
plan → acquire → parse → bind → evidence → candidates → decide → canonicalise
                                                               ↓
                                      release ← derive ← assess coverage
```

### 6.1 Plan

Create a `RunManifest` from explicit source scope, subject/cohort scope, cohort budget, pricing/FX snapshot, adapter versions, policy versions, cost limits and requested outputs. Discovery and refresh planning are deterministic where possible. Paid tasks must reserve budget before scheduling.

### 6.2 Acquire

Download to runtime staging, validate status/type/size, hash the completed bytes, then place or index the durable blob. Record retrieval time, source URL without secrets, upstream version/ETag where available, licence/attribution policy, and failure status.

### 6.3 Parse

Produce source-native records without canonical interpretation. Preserve original field names, table labels, row order, page/region, units, signs, and source time.

The current structured-source parsers, `document_v2` page routing, OCR routing, and web snapshot normalisation are salvage candidates. Phase/date-specific orchestration is not.

### 6.4 Bind

Resolve source records to subjects using authoritative identifiers and governed rules. Persist `resolved`, `candidate`, `ambiguous`, and `unresolved` states. A binding may be reviewed independently of any semantic observation.

### 6.5 Build evidence

Create bounded, attributable fragments suitable for mechanical rules or an LLM task. Evidence selection has its own version and hash. A fragment retains exact source location and does not silently become a paraphrased claim.

### 6.6 Generate candidates

Source-native structured parsers may emit mechanically explicit `CandidateObservation` records. Unrestricted prose candidates come from typed LLM tasks. Candidate generation is non-destructive and may be non-exclusive: the same evidence can support candidates in several domains. Custom local NER, relevance, taxonomy or summarisation models require a benchmark, explicit failure boundary, owner and product approval.

### 6.7 Decide

Apply a human decision or an explicitly approved automation policy. A `DecisionRecord` requires:

- decision authority and actor/policy ID;
- status (`accepted`, `edited`, `rejected`, `insufficient`, `identity_blocked`, `scope_blocked`, or another controlled outcome);
- rationale or rule result;
- candidate and evidence references;
- decision time;
- policy/schema applicability;
- any decision it supersedes.

No model output is labelled `human_governed`. Automation is authorised by a separately versioned policy backed by domain-specific benchmark evidence.

### 6.8 Canonicalise

Create or supersede typed `CanonicalObservation` records from accepted decisions. Canonicalisation preserves the approved proposition, subject/scope, world time, observation time, claim basis, extraction method, evidence, source records, confidence where meaningful, and warnings.

### 6.9 Assess coverage

Coverage is computed against an explicit capability, source scope, time window, and policy version. `not_found_in_source` is valid only after that defined assessment; it is never inferred from an empty result list.

### 6.10 Derive

Generate independently cacheable derivatives. Summary writing, taxonomy assignment, embeddings, similarities, and financial analytics have separate task schemas and invalidation rules.

### 6.11 Project, validate, publish

Select governed records into a declared public contract, render all formats, validate references and invariants, and stage a complete candidate. Only a passing immutable candidate crosses into `charitygraph-data`. Viewer consumes an explicitly selected release and never Builder working state.

### 6.12 Governance status and pipeline gates

Every stage records whether a requested result is `available`, `unprocessed`, `inapplicable`, `not_found_after_assessment`, `failed`, `held`, `quarantined`, or another controlled policy state. Missing input, retrieval failure, inapplicability, not-yet-processed work and a scoped negative assessment are never collapsed. `not_found_after_assessment` requires the source families/roles, time window, capability and policy version actually assessed.

A decision gate separates candidate generation from canonicalisation. No model output, heuristic, cache hit or historical assertion may be represented as a human-governed decision. Automation is authorised only through a separately versioned, domain-specific policy with applicable benchmark evidence and secure subject binding. Human review is targeted to samples, conflicts, sensitive claims and higher-exposure cases rather than imposed universally.

## 7. Model-task and cost-orchestration architecture

LLM use is task-specific, bounded and routine. The production design separates at least these logical tasks:

| Task | Python preparation/control | Model output |
| --- | --- | --- |
| Page text recovery | Native parse and off-the-shelf OCR; select failed page/region | Vision recovery of specified content; output remains extracted syntax |
| Relevance screening | Segment, deduplicate and supply task context | Bounded classification with reason/evidence reference; no factual claim |
| Structured extraction | Preserve obvious fields, spans, units and signs | Typed candidates with exact evidence references |
| Semantic interpretation | Supply schema, alternatives and domain policy | Typed candidate with uncertainty, including activity, participation, fundraising, ethos and context judgements |
| Taxonomy mapping | Validate vocabulary and version | Proposed classification candidate, never a taxonomy-governance decision |
| Editorial synthesis | Select governed observations and evidence | Reader-facing derivative that cannot introduce new facts |
| Embeddings | Produce stable release-safe derivative text and hash it | Versioned vector derivative for descriptive search/navigation |

The historical monolithic Phase 2A/2B synthesis prompt is retained as experimental evidence, not copied into vNext. It showed useful neutrality and sparsity policies, but it coupled summary prose, activity/beneficiary extraction, geography, participation, taxonomy selection, taxonomy-maintenance signals, and uncertainty into one cache and refresh boundary.

Each new model task records:

- `task_type` and task schema version;
- exact input artefact IDs and canonical input hash;
- prompt/template and policy versions;
- model provider, model snapshot, parameters, and tool/response schema;
- attempt/request identifiers and timestamps;
- validation result;
- token, latency, and cost telemetry;
- output artefact IDs;
- reuse, supersession, and invalidation status.

Cache identity is:

```text
H(task type, task schema, evidence hashes, prompt/policy version,
  model snapshot, parameters, material tool versions)
```

Subject ID is recorded explicitly even when derivable from a joined artefact. The cache retains the request specification, selected evidence, raw response, separately validated logical outputs, usage/cost, retries/escalations and validity/invalidation state.

Several logical tasks may share one physical request after benchmark evidence shows acceptable contamination and validation behaviour. Provider batch processing of independent requests is preferred where its price/latency contract fits. Optional multi-subject batching requires a contamination benchmark; optional multi-task bundling for one subject retains separately validated output artefacts.

The scheduler ranks subjects by an approved `BudgetCohort`, discovers evidence, groups work by model/schema/prompt, reserves cost, observes rate limits, retries safely, resumes incomplete batches and prevents duplicate paid work. It reconciles actual cost after each request, returns unused reserve and stops new paid work before a cohort cap can be exceeded.

The initial paid-model budgets are pooled within cohorts and include text/vision extraction, judgement, writing, embeddings, retries and escalation:

| Cohort | Priority rule | Cap |
| --- | --- | ---: |
| first 100 | highest total donations | AUD 100 |
| next 1,000 | next highest total donations | AUD 100 |
| next 10,000 | next highest total donations | AUD 100 |

Total donations is stored as `donor_decision_exposure_proxy`. It estimates processing exposure, not donor count, merit, quality, credibility or recommendation. Easy subjects may subsidise difficult ones inside a cohort; cross-cohort transfer requires explicit approval. Cost records retain provider currency, actual usage, pricing-table version, AUD conversion rate/source and reservation/reconciliation events.

Embeddings are part of the budget even when negligible. Generate them only from stable release-safe text and cache them by text hash, embedding model and material parameters.

Custom local NLP is not a default tier. Simple parsing, exact source-native structure, vocabulary validation and off-the-shelf OCR remain. Deterministic semantic lexical heuristics (regexes, keyword/phrase lists, lexical scoring, capitalization/title-case, URL words/slugs, repetition/frequency, fuzzy lexical similarity or equivalents) require a registered Greg-approved CG-SH-* exception in the Data approval register. A custom NER, relevance, taxonomy or summarisation component also requires a benchmark of total cost of ownership, a failure boundary, an owner and explicit product approval.

## 8. Storage and local operation

Recommended Windows layout:

```text
CharityGraph\
  charitygraph\                 Builder Git repository
  charitygraph-data\            public Data Git repository
  charitygraph-viewer\          Viewer Git repository
  archive\                      durable private evidence and processed artefacts
  archaeology\                  durable read-only findings and migration reports

C:\CharityGraph-runtime\
  state\                        operational catalogue and locks
  work\                         bounded in-progress runs
  cache\                        safely disposable/rebuildable caches
  staging\                      candidate release staging
  logs\                         privacy-safe operational logs
```

### 8.1 Storage roles

The storage choices are complementary rather than interchangeable:

| Component | Job | Authority |
| --- | --- | --- |
| Immutable files | Source blobs, evidence fragments, governed records, model/task records and run manifests | Authoritative durable content |
| JSON/JSONL | Inspectable typed records, interchange and streaming imports/exports | Authoritative where declared by the artefact contract |
| Parquet | Large tabular snapshots and efficient analytical scans | Authoritative snapshot or reproducible projection, as declared |
| SQLite | Mutable local workflow state and a rebuildable index over durable artefacts | Operational authority only |
| DuckDB | Ad hoc/batch analysis over JSON, Parquet and indexed metadata | Disposable query engine unless a later decision says otherwise |

SQLite is the recommended initial operational catalogue, not a repository for raw documents or the only copy of governed knowledge. The first implementation is deliberately thin: task/batch state, idempotency, budget reservations, reconciled cost, cache validity and artefact locations/hashes. Domain knowledge remains in durable typed artefacts. Broader catalogue tables are added only when a working vertical slice requires them.

### 8.2 Alternatives and trade-offs

| Option | Strengths for CharityGraph | Weaknesses | Decision |
| --- | --- | --- | --- |
| Files and manifests only | Maximally inspectable, portable and easy to archive; no database lifecycle | Dependency queries require repeated scans; atomic updates across several records are awkward; task queues, retries and uniqueness rules move into application code | Retain as content authority, but insufficient alone once incremental orchestration begins |
| SQLite | Ships with Python; no server; transactional constraints and indexes; excellent fit for a single-machine application making many small state changes | One writer at a time; poor choice for large analytical scans compared with a columnar engine; database rows are less directly inspectable in Git/text tools | Recommended for local operational state and indexing |
| DuckDB as the only database | Fast columnar scans and joins; directly queries Parquet/JSON; excellent for archaeology, cohort construction and economics analysis | Optimised for analytical rather than queue/state workloads; adds a dependency; making it the mutable scheduler store gains little and complicates concurrency expectations | Use as an optional analytical tool, not the initial workflow authority |
| PostgreSQL | Strong concurrent writers, network access, mature server operations and multi-user application support | Requires a running service, credentials, backup/upgrade administration and a client/server failure surface; unnecessary for one local Builder | Defer unless Builder becomes a shared service or multi-machine worker system |
| Graph database | Convenient graph traversal and visual exploration | Another specialist service and query language; typed lineage at this scale fits ordinary relational edge tables | Do not adopt |

This results in a deliberately modest combination:

1. immutable files and manifests preserve evidence and governed history;
2. SQLite coordinates the local Builder and indexes those files;
3. DuckDB may be invoked directly over Parquet/JSON for large joins and analytical evaluation, without requiring a persistent DuckDB database;
4. public releases remain files in CharityGraph Data.

Reconsider SQLite only if evidence shows sustained lock contention, several independent writers, workers on multiple machines, or a continuously available multi-user API. Those are PostgreSQL-shaped requirements, not current requirements.

### 8.3 Operating rules

- Do not use Windows Temp for project reports or authoritative artefacts.
- Do not bulk-move or rewrite the 1.4 GB archive merely to make it match a proposed layout. Index existing files first; migrate lazily and verify hashes.
- Durable source blobs and completed processing artefacts are immutable or append-only. Corrections create new artefacts/decisions.
- The SQLite catalogue is stored in local runtime, not OneDrive or another network-synchronised folder.
- The catalogue exposes a deterministic `reindex`/rebuild path from durable manifests and artefact metadata; transient queue/lock state may be lost without losing evidence.
- DuckDB queries durable files or read-only exported catalogue views. Builder does not maintain the same mutable workflow truth independently in two databases.
- Runtime work/cache may be deleted and rebuilt; archive, governed inputs, archaeology reports, and immutable releases may not.
- Recreate virtual environments after path changes. Do not repair embedded old absolute paths.

### 8.4 Catalogue and recovery semantics

SQLite is the mutable local control plane, not the evidence store. The catalogue must define deterministic idempotency keys; explicit transaction boundaries; single-writer and bounded-worker assumptions; retry, backoff and terminal-failure rules; leases and locks with process-death recovery; resumable slices; held/quarantined handling; schema migrations and integrity checks; and deterministic reindex from durable manifests and artefact metadata. Cache and runtime work are disposable, while durable evidence, governed inputs, archaeology and immutable releases are not.

No authoritative project output is written to Temp. No SQLite database is stored in OneDrive or another synchronised directory. PostgreSQL remains deferred unless observed lock contention, independent writers, multi-machine workers or a continuously available multi-user API justify its operating cost. A graph database remains unnecessary while typed lineage fits ordinary relational edge tables.

## 9. Recycling the existing treasure trove

| Existing material | vNext treatment |
| --- | --- |
| Raw regulator archives, DGR ZIPs, PDFs, website snapshots | Retain in place; hash/index as `SourceBlob` migration inputs |
| National and DGR source-record JSONL | Import/index as historical `SourceRecord` artefacts after schema validation |
| Document v2 and web v2 extraction routes | Salvage behind new adapters and contracts |
| Current Pydantic financial/source models | Split and adapt into typed internal observation schemas |
| Golden corpus and approved semantic decisions | Promote to first-class benchmark/governance fixtures |
| Phase 2A synthesis cache | Import as historical `TaskRun` plus derivative/candidate evidence where safely joinable; never auto-promote |
| Candidate cards and phase releases | Treat as projections/checkpoints for regression and migration comparison |
| `legacy_unbound` | Preserve origin lineage; prioritise re-extraction/review; do not treat origin-only assertions as canonical observations |
| v0.5 schemas, examples, manifest and checksum | Preserve unchanged as the public compatibility/release baseline |
| Phase/date-specific orchestration modules | Freeze as historical recipes and fixtures; do not use as the new core |
| Old flat CSV scripts | Retain only as archaeology/regression evidence for known failure modes |

## 10. Release compatibility

The first Builder vNext milestone is not a new public schema. It must prove that the new internal architecture can reproduce or intentionally explain the current v0.5 release boundary.

Required safeguards:

- The immutable v0.5 manifest checksum remains unchanged.
- Existing v0.5 artefacts are never rewritten in place.
- A vNext release projector has an explicit contract adapter and fixture suite.
- Differences between a historical projection and a new controlled build are classified as input change, governed decision, policy change, derivative refresh, or defect.
- The v0.5 adapter preserves its legacy public subject-key field. Any future public replacement with neutral `subject_id` requires a separately governed Data-contract migration.

## 11. Bounded implementation sequence

This document authorises no implementation by itself. Each following stage is a bounded PR with tests, migration notes and explicit exclusions:

1. **Authority and minimum contracts** — install the product/architecture amendment and define only the artefact, logical-task, budget-cohort, pricing and cache contracts needed for a model-assisted spike; no real model call.
2. **Thin operational ledger** — implement SQLite task/batch/cache/cost state, idempotency and recovery behind a rebuildable interface.
3. **Scheduler and fake provider** — batching, reservation/reconciliation, retry/resume, duplicate prevention and hard cohort stops, tested without paid calls.
4. **Bounded economics spike** — run 10–20 representative charities against existing evidence under a separately approved micro-budget; cover difficult extraction, judgement, writing and embeddings; publish nothing.
5. **LLM-powered vertical slice** — complete the typed candidate/decision/observation/derivative path for representative subjects, including fixture-only release projection.
6. **Read-only archive index and evidence reuse** — index existing files in place and bind the most useful existing extracts, model runs and governed cases without automatic promotion.
7. **Core-domain expansion** — program/service scope, participation, activities/beneficiaries, geography, fundraising/shadow registries, ethos/service orientation, notable context and taxonomy policies.
8. **Governance and corrections** — risk-weighted automation policies, review sampling, conflicts, sensitive claims, challenges, retractions and dependent invalidation.
9. **First-100 cohort** — process the highest-donation cohort within AUD 100, including embeddings and risk-aligned assurance; evaluate anti-sparsity acceptance before any public proposal.
10. **Next-1,000 cohort** — process within AUD 100 using proven batching/caching/routing and sampled quality assurance.
11. **Next-10,000 cohort** — process within AUD 100 using the economical route, targeted escalation and explicit coverage states.
12. **Cutover proposal** — only after cohort evidence, propose production commands, phase-orchestration deprecation and any future public-contract change separately.

Architecture-critical stages use Terra-High. Later bounded adapters, fixtures and mechanical migrations may use Luna-High only after the governing contracts are fixed.

## 12. Architecture acceptance criteria

Before material implementation begins, confirm:

- cards are release projections, not internal canonical records;
- `SubjectRecord` lifecycle, scoped records and real-world relationships are distinct from artefact lineage;
- candidate, decision, canonical, coverage and derivative artefacts have typed contracts and promotion boundaries;
- every causal relationship uses the controlled lineage vocabulary, and `about_subject` is only an association;
- model tasks are separated by schema and invalidation boundary and cannot create human-governed decisions;
- participation is in the initial production scope and shadow-registry authority is claim-specific;
- correction, challenge, retraction and dependent invalidation are explicit and append-only;
- budget/economics artefacts enforce the three cohort caps, label total donations only as a donor-decision-exposure proxy and never imply worthiness;
- Python orchestration proves batching, scheduling, caching, cost reservation/reconciliation, duplicate prevention and resumability;
- model-assisted extraction, judgement, writing and embeddings are routine, separately typed and included in cost accounting;
- custom local NLP is absent from the initial build unless a total-cost-of-ownership benchmark approves it;
- acceptance measures coverage and recoverable recall as well as precision; a high-precision sparse pipeline fails;
- durable evidence is indexed/reused rather than destructively reorganised;
- SQLite operating semantics, recovery and deterministic reindex are testable; durable evidence never exists only in SQLite;
- public contract 0.5, its compatibility adapter, fixtures and immutable checksum remain protected;
- release and distribution acceptance covers Data handoff, Viewer inputs, routes, alternates, source references, bulk artefacts, sitemap/robots, citations, privacy/rights and prior-valid-release preservation;
- current workspace paths are authoritative and Temp is prohibited for durable output.

## 13. Non-blocking migration questions

These questions can be answered during implementation without changing the architecture:

- Which historical source artefacts already have enough metadata to import directly, and which need wrapper records?
- Which 143 synthesis-cache records without a direct candidate-card join can be rebound through exact evidence-pack joins?
- Which approved knowledge-validation decisions should become current governed fixtures rather than benchmark-only history?
- Which `legacy_unbound` domains merit first re-extraction based on public value and review cost?
- Whether any custom local NLP component later reduces total cost of ownership after implementation, evaluation, maintenance and operational cost are included.

They should be recorded in `CharityGraph\archaeology\tranche-4\` or a later durable tranche directory, never Temp.

## 14. Immediate implementation boundary

After the bounded knowledge-primitives tranche, the next implementation task is the private Phase 1 pre-run engine: versioned taxonomy registration, deterministic source/identity/program mechanics, typed semantic tasks and a fake-provider end-to-end fixture. It must be proven before the first private reality slice described by the canonical Data [IMPLEMENTATION_PLAN.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/IMPLEMENTATION_PLAN.md). It remains synthetic/recorded, private and review-only. Do not alter public schemas, rebuild a release, move archive evidence, inspect holdout charities, or make unapproved provider/model calls.
## Semantic heuristic gate

Builder is Python-controlled and LLM-powered: LLMs are the routine semantic engine for unrestricted prose relevance, entity/program/service interpretation, extraction, classification, ambiguity and bounded rationale. Python may acquire, parse stable structure, assemble/select evidence, join, validate, schedule, account and compile releases; it must not teach Python English through deterministic lexical interpretation.

Before coding any unrestricted natural-language semantic rule, ask: **Does this diff teach Python English?** If yes, stop unless the exact exception has a registered Greg-approved CG-SH-* entry in the sibling Data repository's SEMANTIC_HEURISTIC_APPROVALS.md. Mechanical parsing remains permitted only for stable syntax, IDs, URLs, dates, numbers, formats, markup, exact source-native structured fields, schema validation, arithmetic and joins.
