# Baseline Charity Corpus v1

This Builder tranche defines the private, review-only corpus boundary for the
ten-subject Reality Slice 1 cohort. A corpus is an immutable subject-scoped
manifest over source material; source bodies remain in the private
content-addressed store.

Coverage is represented independently for discovery, acquisition, subject
binding, material origin and document-representation readiness. The contract
does not contain a `corpus_complete` flag and does not reuse program-level
`COMPLETE_ENOUGH`.

Material identity is the SHA-256 of the subject ID, corpus-profile version and
ordered material members. Cohort/run IDs, retrieval timestamps, Builder commit
and derived representations are provenance only and cannot change material
identity. Derived PDF representations retain exact source-artifact lineage and
page-level gaps.

Official-site candidates are enumerated mechanically from same-origin
navigation and sitemap material. Luna is used only to return a complete ordinal
ranking by durable information value; it does not classify or extract charity
semantics. Wikipedia and PFRA remain bounded contextual source families and are
never identity authorities. This tranche does not emit public cards, semantic
claims or Data/Viewer artefacts.

The private reality runner is `scripts/run_baseline_charity_corpus_v1.py`.
Runtime reports, source snapshots, SQLite state and derived representations are
written below `C:\\CharityGraph-runtime` and are excluded from Git.
