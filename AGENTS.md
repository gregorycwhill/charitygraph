# CharityGraph Builder — Agent Instructions

**Status:** Canonical repository instructions  
**Architecture authority:** [ARCHITECTURE.md](ARCHITECTURE.md)

Read the sibling Data repository's DOCUMENT_AUTHORITY.md, current state and plans before changing cross-product behaviour. Builder's internal authority is governed typed observations attached to durable subjects and scopes. Cards are public release projections, not canonical stored knowledge.

Builder is Python-controlled and LLM-powered. Follow the sibling Data repository's [`COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`](https://github.com/gregorycwhill/charitygraph-data/blob/main/COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md): routine semantic work uses typed model tasks; Python owns evidence preparation, batching, scheduling, caching, cost enforcement, validation and release compilation. Read the canonical [`INTEGRATED_PRODUCT_AND_DATA_MODEL.md`](https://github.com/gregorycwhill/charitygraph-data/blob/main/INTEGRATED_PRODUCT_AND_DATA_MODEL.md), [`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`](https://github.com/gregorycwhill/charitygraph-data/blob/main/SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md), [`TAXONOMY_AND_SCHEME_GOVERNANCE.md`](https://github.com/gregorycwhill/charitygraph-data/blob/main/TAXONOMY_AND_SCHEME_GOVERNANCE.md), [`IMPLEMENTATION_PLAN.md`](https://github.com/gregorycwhill/charitygraph-data/blob/main/IMPLEMENTATION_PLAN.md) and [`TEST_PLAN.md`](https://github.com/gregorycwhill/charitygraph-data/blob/main/TEST_PLAN.md) before cross-product work.

## Boundaries

- Do not add raw sources, private evidence, reports, website snapshots, prompts, model responses, runtime state, caches, credentials, logs or debug files to Git.
- Do not manually edit generated public projections.
- Do not change public contract 0.5, immutable release bytes, schemas, Viewer selection or compatibility identifiers without a separately approved migration.
- Do not create a database, index the archive, acquire sources or call a model unless the task specifically authorises it.
- Do not introduce custom local NER, relevance, taxonomy or summarisation infrastructure unless an approved total-cost-of-ownership benchmark authorises it.
- Reserve cohort budget before every paid request and reconcile actual cost afterwards. Paid work includes extraction, judgement, writing, embeddings, retries and escalation.

## Evidence and identity

Names and domains never create or resolve a subject by themselves. Preserve source records, bindings, evidence, candidates, governed decisions, canonical observations, coverage and derivatives as separate states. A local SQLite catalogue is rebuildable operational state, never the only evidence authority.

Model output is never a human decision. It may become canonical only through an applicable versioned automation policy. Coverage is the optimisation objective; provenance, supported-claim quality, risk routing and correction are constraints. Do not treat sparse output as success merely because it is easy to defend.

Treat funding source, fundraising practice, campaign and expenditure as different domains. Expenditure may be unavailable; universal priors, peer fill, forced midpoint and forced point estimates are prohibited.

## Compatibility

Former-brand compatibility identifiers remain isolated where code, tests or immutable public 0.5 bytes require exact matching. Do not spell them out or introduce them into active architecture, product prose, current outputs or user-facing documentation.

## Completion

Run relevant tests, inspect generated diagnostics where applicable, verify publication allowlists and representation consistency, and report private-material exclusion. Do not use broad add-all Git commands.

## SEMANTIC HEURISTIC GATE -- STOP BEFORE CODING

Before changing Builder logic that touches unrestricted natural-language semantics, ask: **Does this diff teach Python English?** If yes, stop. Do not add regexes, keyword/phrase lists, lexical scoring, capitalization/title-case, URL-word rules, repetition/frequency, fuzzy lexical similarity or equivalent semantic heuristics without a specific Greg-approved CG-SH-* entry in the sibling Data repository's SEMANTIC_HEURISTIC_APPROVALS.md. Custom/local NLP needs a benchmark, explicit failure boundary, owner and approval; total cost alone is not authorization. Mechanical code remains appropriate for stable syntax, identifiers, URLs, dates, arithmetic, exact joins and explicit source-native structured fields; unrestricted prose is an LLM task by default.

**BUILDER DOESN'T DO DISCOVERY.** Builder and specialist sections consume the
centrally governed evidence universe and persisted reusable representations.
Sparse evidence may expose a coverage gap, but does not authorise external
search or new source-family acquisition.
