# CharityGraph Builder

CharityGraph Builder creates governed charity knowledge and validated release candidates for [CharityGraph Data](https://github.com/gregorycwhill/charitygraph-data).

Builder is one of the four CharityGraph products: Data publishes reusable governed data, Viewer supports human inspection and navigation, and [CharityGraph Playbooks](https://github.com/gregorycwhill/charitygraph-playbooks) publishes governed, open analytical methods for use with general-purpose AI. Playbooks is a separate product; Builder constructs knowledge and release candidates but does not generate Playbooks or downstream external-model analysis.

Its internal authority is durable subjects, source-native records, evidence, candidates, governed decisions, canonical observations, coverage and derivatives. Public cards are versioned release projections.

Read [ARCHITECTURE.md](ARCHITECTURE.md) and [AGENTS.md](AGENTS.md) first. Shared product authority, current state, public commitments and reuse policy live in the sibling [CharityGraph Data repository](https://github.com/gregorycwhill/charitygraph-data), especially its [DOCUMENT_AUTHORITY.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/DOCUMENT_AUTHORITY.md), [PRODUCT.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/PRODUCT.md), [BRAND_AND_REUSE.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/BRAND_AND_REUSE.md), [INTEGRATED_PRODUCT_AND_DATA_MODEL.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/INTEGRATED_PRODUCT_AND_DATA_MODEL.md), [COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md), [SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md), [IMPLEMENTATION_PLAN.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/IMPLEMENTATION_PLAN.md) and [TEST_PLAN.md](https://github.com/gregorycwhill/charitygraph-data/blob/main/TEST_PLAN.md).

The active CLI is `charitygraph`. A former-brand command remains an isolated warning-emitting compatibility alias and is intentionally not repeated in active product prose. New configuration uses `CHARITYGRAPH_ARCHIVE_ROOT`, `CHARITYGRAPH_RUNTIME_ROOT` and `CHARITYGRAPH_DATA_REPOSITORY`.

Builder never publishes raw source archives, annual-report PDFs, website snapshots, credentials, model traces or private runtime material.
