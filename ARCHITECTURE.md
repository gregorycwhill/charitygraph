# CharityGraph Builder Target Architecture

**Status:** Canonical Builder architecture  
**Version:** 0.2  
**Scope:** future internal knowledge construction; not a public-schema proposal

This architecture implements the product authority in the sibling Data repository. Read its DOCUMENT_AUTHORITY.md and the implemented PUBLIC_CONTRACT_0_5.md before changing distribution or compatibility behaviour.

## 1. Architectural boundary

Builder transforms durable source artefacts into governed knowledge and validated release candidates:

source blobs → source-native records → bindings and evidence → candidates → governed decisions → canonical observations and coverage → derivatives → release projections

A public card is a versioned release projection. It is not Builder's canonical stored object.

## 2. Canonical internal records

The minimum durable record set is:

- SubjectRecord: opaque subject_id, kind, lifecycle, identity attributes, external identifiers and provenance;
- ScopeRecord and SubjectRelationship: program/service/unit scope and real-world relationships, distinct from artefact lineage;
- SourceBlob, SourceRecord and SubjectBinding: source identity, source-native preservation and governed resolution;
- EvidenceFragment: bounded source support, location, rights and time;
- CandidateObservation, DecisionRecord and CanonicalObservation: proposed, governed and accepted knowledge states;
- CoverageAssessment and DerivativeArtifact: what was assessed and release-safe computed outputs;
- CorrectionSubmission, CorrectionProposal and retraction/disposition records;
- benchmark, source-opportunity, proposition/review and cost artefacts;
- TaskRun, RunManifest and ReleaseProjection.

Names and domains never mint or bind a SubjectRecord by themselves. A program or service may remain subject-local scope until governed evidence justifies durable promotion. Artefact lineage explains production; subject relationships explain the world.

## 3. Subject lifecycle and corrections

Subject lifecycle supports creation, active/inactive status, merges, splits, predecessors, successors and tombstones without silently reassigning identity. Source bindings remain reversible and record resolution basis, conflict and review state.

Raw correction submissions are private. Moderation produces a governed proposal and disposition. An accepted correction changes evidence, bindings, decisions or observations, then invalidates affected candidates, coverage, derivatives and release projections. Retraction, challenge and exceptional privacy/legal removal remain explicit workflows, not manual edits to published files.

## 4. Evidence, domains and authority

Durable artefacts, not a local database or card, are evidence authority. Claim basis and extraction method are independent. Conflicting legitimate observations remain represented with reconciliation status.

Domain policies keep funding source, standing fundraising practice, campaign and expenditure distinct. Fundraising expenditure may be unavailable; universal priors, peer fill, forced midpoints and forced points are prohibited. Ethos is separate from service or mission orientation; notable_context is neutral sourced context. Participation is a first-production domain, with stable modes separate from transient opportunities.

Evaluated shadow registries are claim-specific authorities for registry-defined facts such as membership, applicable code or stated fee rule. A code establishes what applies, not compliance; a fee rule does not establish member-specific spend or volume. Promotional effectiveness claims remain source-native or review-only unless separately governed.

## 5. Operational control plane

SQLite is the local operational catalogue and rebuildable index, outside synchronised storage. It may index locations, hashes, edges, task states, cache validity and refresh state, but no governed fact may exist only in SQLite.

All execution contracts specify deterministic idempotency keys, transaction boundaries, bounded concurrency, retry/backoff, terminal failures, leases/locks, process-death recovery, resumable slices, held/quarantined cases, migrations and deterministic reindex from durable artefacts. The database may be deleted and rebuilt without loss of governed evidence.

## 6. Evaluation and economics

Production telemetry is not sufficient to choose methods. Builder maintains versioned cohort/benchmark definitions, source-opportunity inventories, proposition/review ledgers and cost ledgers. It measures precision, recoverable recall, oracle and source-scope gaps, sparsity, review burden, accepted observations per dollar and refresh cost.

Every eligible subject receives a cheap common baseline. Additional processing follows evidence opportunity and measured information yield, never prestige, size, perceived quality or donor appeal. Model outputs are candidates or derivatives, never human decisions and never automatically promoted.

## 7. Release and distribution

Builder selects observations, coverage and derivatives into a complete ReleaseProjection. Data owns immutable public artefacts; Viewer renders an explicitly selected release and never private Builder state.

Release acceptance includes allowlisted artefacts, privacy and source-rights checks, schemas, manifests and hashes, stable subject routes, JSON/Markdown alternatives, source references, bulk projections where declared, citation metadata, sitemap/robots responsibilities, cross-representation consistency and preservation of the previous valid release on failure.

Public contract 0.5 is an isolated implemented compatibility boundary. It does not constrain the internal object model. A future public contract needs separate approval, schemas, examples, migration analysis and Data/Viewer acceptance.

## 8. Implementation sequence

The next code PR defines typed contracts and no-op interfaces only after this documentation authority is accepted. It must not create a runtime database, index the archive, import evidence, rebuild a release or change public schemas. The first material vertical slice is deterministic, fixture-bounded and projects through an explicit 0.5 compatibility adapter.