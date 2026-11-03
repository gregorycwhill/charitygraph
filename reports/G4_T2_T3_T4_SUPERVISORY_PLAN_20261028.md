# Gate 4 T2/T3/T4 supervisory archaeology plan

Date: 2026-10-28 (Australia/Sydney)  
Mode: local, read-only archaeology and planning; no provider/model/network/source acquisition or spend  
Target: branch `gate3-cg406-remediation`, HEAD `700cfe1f4e576e00471155a6bfedbcc40fc36cab`, active fence v43

## Disposition

Gate 4 remains `ACTIVE` and unearned. This report is a plan, not acceptance,
promotion, release evidence, or gate closure. The T2 artefact currently visible
in the worktree is `ACCEPT_BOUNDED_OFFLINE_REHEARSAL` only; its real-evidence
claim is explicitly unproven. Treat the two untracked T2 source/test files and
the prior T2 report as quarantined/unverified evidence. Do not adopt, overwrite,
stage, commit, or cite them as accepted provenance.

The labels here are Gate 4 industrialisation T2/T3/T4. They are not the
historical Gate 2 semantic-demand tranches with the same names.

## Authority correction and evidence read

Read-only inspection covered `AGENTS.md`, `BUILDER_MACHINERY.md`,
`ARCHITECTURE.md`, the North Star v0.3 definition in the sibling Data
repository, Data `DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`,
`IMPLEMENTATION_PLAN.md`, `TEST_PLAN.md`,
`COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`,
`INTEGRATED_PRODUCT_AND_DATA_MODEL.md`,
`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`,
`TAXONOMY_AND_SCHEME_GOVERNANCE.md`, and `SEMANTIC_HEURISTIC_APPROVALS.md`.
The local Gate 4 industrialisation review, P3c/P4 archaeology and acceptance
reports, `bridge/SUPERVISOR_PROTOCOL.md`, the T1/T1B reports, the unverified T2
report, relevant Factory/transport/diagnostics/rights code and tests, and the
36-charity recovery/preparation inventory were also inspected.

The canonical Builder-to-65k scorecard defines Gate 4 as: model/cost routing,
batch execution, concurrency, restart/resume, idempotence, scheduling,
monitoring, failure isolation and cost telemetry. It does not say that an
offline fake run closes the gate. The supervisory chain remains objective ->
gate evidence -> tranche -> run/tasks -> handoff -> semantic review -> Product
Owner/Sol decision. Worker completion is process evidence only.

Data authority corrects the implementation order: source registration and
acquisition/receipt lineage precede evidence and representations; exact rights
and retention/provider/publication axes remain separate; semantic work is typed
model work; human review owns high-consequence sufficiency and promotion. The
seven-family Source Universe v1 is exhaustive. A gap or failed acquisition is
not permission for open-web discovery or a new source family.

## Current clean/dirty boundary

Before this report, the checkout had 10 modified tracked paths and 79
untracked status entries. They were preserved. The latest clean commit only
changes bridge admission/test code; it does not make the worktree prototype
clean.

Clean HEAD contains the T1B provider-free seam:

- `src/charitygraph/phase5_governed_rights_preflight.py` validates an
  authoritative private rights record plus the v29 current projection before
  lowering to `FactoryPlan`.
- `src/charitygraph/runtime/rights_governance_projection.py` rebuilds/querys
  the v29 `rights_projection_*` tables; private record bytes remain authority.
- `tests/test_phase5_governed_rights_preflight.py`, the rights-record and
  projection/migration tests, and the existing Factory/transport/diagnostics
  tests are clean baseline machinery.
- The clean T1B rerun recorded 29 focused passes. Earlier T1B evidence also
  recorded one known committed compatibility failure in the clean rights-record
  suite; it was not weakened.

The current worktree additionally contains dirty overlays in
`source_rights.py`, `runtime/catalog.py`, `phase5_governed_factory_integration.py`,
`phase5_factory.py` and related tests. Those overlays add side-installed
`artifact_rights_*` tables, copied provider-rights fields, and scope/physical
attempt changes. They are not the v29 clean projection, have not been promoted,
and are not an admissible dependency for T2/T3/T4.

The T2 paths are untracked and therefore not clean/new in this checkout:

- `src/charitygraph/phase5_offline_cohort_rehearsal.py`
  (SHA-256 `9dd267a84f856069c6ea3ac0d14d0b36df49318ed1906c9d5800695047e0beaa`)
- `tests/test_phase5_offline_cohort_rehearsal.py`
  (SHA-256 `56bb3da80e18209ebac09cd64a95ac941564d803c70215902607cc20788da70f`)
- `reports/G4_T2_EVIDENCE_BACKED_FACTORY_REHEARSAL_20261028.md`
  (SHA-256 `e15bf805943cade7b66b50aa1560fd4d5363dca10417636c227cbad9572e6e62`)

The prototype test itself skips when the dirty governed-integration module is
present. That is diagnostic evidence of contamination, not an independent
passing test. The prior T2 full exact-HEAD archive result (1,249 passed, 13
failed, 4 skipped) likewise is not a T2 acceptance result; its 2 live new tests
were skipped at the dirty seam. No accepted T2 implementation allowlist exists
against this current worktree. A future code task needs a genuinely clean
baseline or explicitly fresh path names; it must not overwrite these paths.

## 36-charity evidence and admissibility

The local evidence is useful lineage, not yet a governed processing cohort.
`evidence/gate3-fresh36-bounded-recovery-v1/recovery-status.json` records 36
frozen identities, 224 hash-verified member references, 189 unique source
objects, 74 contemporaneous reused matches, 149 successor acquisition receipts,
and one unresolved original receipt lineage. Its family reference counts are
36 ACNC register, 36 AIS, 36 ATO/ABR, 28 annual reports, 20 official websites,
36 PFRA and 32 Wikimedia. It records zero provider calls and zero rights
decisions. The recovery summary expressly stopped before provider-request
compilation because exact representation rights authority was absent.

A separate runtime `g3-fresh-36-v15/source-universe` ledger used by the T2
report has 182 rows: 36 each for the five principal families and one PFRA plus
one Wikimedia row. The repository preparation ledger has a different 252-row
projection. These are not silently merged into one cohort count. Before T3,
choose one immutable manifest and retain its exact subject/source/representation
identity.

For T3, a row is admissible only if it has the intended Australian subject
binding, admitted source family, durable source record and scope, exact source
artifact, exact representation artifact/hash, acquisition receipt lineage,
local-retention authority, and current v29 rights projection/reload. `pfra` and
`wikipedia_wikimedia` are admitted families, but `subject_not_bound` rows are
not admissible merely because bytes exist. Unavailable, partial, unresolved or
identity-blocked rows remain explicit coverage states; they are not repaired by
discovery or by a guessed subject.

## Dependency-ordered tranche plan

### T2 — clean reconstruction of the offline control-plane rehearsal

Purpose: reproduce the Gate 4 control-plane evidence from clean HEAD without
claiming real evidence, provider readiness or live industrialisation.

Dependencies: accepted T1B clean rights preflight; clean v29 projection and
Factory/SQLite/diagnostics seams; no provider-policy registry is needed because
the rehearsal must not cross a provider boundary.

Safe implementation boundary:

- Read-only clean dependencies are `phase5_governed_rights_preflight.py`,
  `runtime/rights_governance_projection.py`, clean-head `phase5_factory.py`,
  `phase5_delivery.py`, `phase5_run_diagnostics_catalog.py`,
  `phase5_run_diagnostics.py`, and the clean runtime catalogue plus their
  committed focused tests.
- No current worktree implementation path is safe to edit. The intended T2
  module/test names already exist as untracked prototype files and must remain
  untouched. Do not add the prior report to an allowlist.
- If a clean baseline is later supplied, the implementation may compose the
  existing `FactoryPlan`/`ReferenceFactory`, FakeProvider, durable task/attempt/
  receipt/reservation/cost lifecycle and read-only diagnostics projection. It
  must not import dirty `artifact_rights_*` tables or the dirty provider-rights
  helper. It must not introduce semantic heuristics or source fixtures.

Independent acceptance tests, with zero skips in the accepted focused set,
must prove: exact T1B lowering; five or another explicitly fixed TEST FIXTURE
  subjects only; standard failure isolation; batch planning without a batch
  send; ambiguous crossing held for explicit reconciliation; replay produces
  zero new fake calls and stable diagnostic bytes; exact reservation/actual/
  release reconciliation; and no forbidden side effect on denied authority.
  The existing clean delivery, standard transport, task-state, diagnostics and
  rights-preflight tests are reusable evidence, but the quarantined T2 test is
  not the independent test. A test using `example.invalid` fixture material is
  synthetic and cannot support T3 real-evidence claims.

T2 output is `LOCAL_ONLY` offline control-plane evidence. It does not prove
source rights, real-data binding, provider-side exactly-once, monitoring/SLOs,
human promotion or Gate 4 exit.

### T3 — real-evidence governed cohort binding, no-send first

Purpose: bind a frozen subset of the already acquired 36-charity evidence to
the clean authority chain, without acquiring sources or calling a model.

Dependencies: clean T2 reconstruction; one selected, immutable 36-charity
manifest; existing content-addressed source/representation objects and
receipts; a durable `RightsGovernanceRecord` and current v29 row for every
representation intended for a task; exact scope and identity bindings.

No-send acceptance:

1. Load each authoritative record by content hash and verify current v29
   identity, subject, scope, source record/family/role, source artifact,
   representation bytes/hash, acquisition receipt lineage, and direct artifact
   lineage.
2. Require separate local-retention authority and separate provider-processing
   authority. Never infer either from public accessibility, source family, URL,
   publication eligibility or a copied policy ID.
3. Lower only admitted rows through clean rights preflight. Missing, duplicate,
   stale, superseded, revoked, mismatched or unbound rows must produce a
   diagnostic and zero tasks, attempts, reservations, receipts or costs.
4. Produce a content-hashed cohort/binding manifest and coverage ledger that
   preserves unavailable, partial, not-bound, unresolved-lineage and
   `DECISION_REQUIRED` states. No raw source bytes, prompts or model responses
   enter Git or the report.

T3 costs AUD 0 and crosses no provider boundary. The prior AUD 10 aggregate
   programme ceiling is not a T3 send authority. T3 is ready only when every
   selected task has exact source/rights/receipt/scope evidence; otherwise its
   result is `DECISION_REQUIRED` or a bounded evidence gap, not a successful
   sparse cohort.

### T4 — industrialisation validation

Purpose: validate the Gate 4 scorecard on the accepted T2 control path and a
T3-admissible real-evidence cohort, in two separately reported phases.

Phase 4A is no-send: freeze the cohort, task/schema/prompt identities, route,
model/provider policy, expected task count, concurrency, retry/ambiguity rules,
and projected spend; run all mechanical preflight, dry-run economics and
diagnostic checks. This phase must stop before provider crossing if any rights,
provider-policy, authority, budget or identity input is absent.

Phase 4B is the model/provider crossing only after an explicit current Product
Owner/Data authority supplies the exact cohort, task, model/provider, provider
policy/version and no-opt-in posture, and a paid-run authority reserves budget
before each request. The AUD 10 aggregate cap includes extraction, judgement,
writing, embeddings, retries and escalation; actual USD/AUD usage, pricing and
FX must reconcile, with unused reserve returned. No call is authorised by this
report alone.

T4 acceptance evidence must be per-run and content-hashed: model/cost route;
Batch/Standard request and logical-task identity; bounded concurrency;
restart/resume with zero duplicate sends; explicit provider receipt and
send-boundary state; ambiguous/systemic/item failure separation and isolation;
schedule/lease recovery; exact cost ledger and reconciliation; stable persisted
diagnostic projection; and an operator-visible health/stop record. Offline fake
tests can establish control invariants but cannot substitute for provider
receipt or real-run evidence at the crossing.

Model output remains candidate/observation material. Human/Sol review must
record proposition-level support, missingness, contradictions and disposition
before any promotion. The worker cannot promote canonical knowledge, publish,
alter a release, or close Gate 4. T4 can recommend `READY_FOR_REVIEW`, `PARTIAL`
or `DECISION_REQUIRED`; Greg remains the Product Owner for product/source-policy
acceptance and Gate 4 closure.

## Missing authority and stop conditions

The following are genuine authority gaps, not Builder failures:

- a source-owned, versioned provider-policy registry with exact ID/version,
  effective evidence, selected service/no-sharing posture and renewal rule;
- an authorised exact-representation rights-assessment workflow/authority for
  the recovered 36-charity material, including the ABR/public-HTML and
  third-party-content questions;
- the immutable T3 subject/scope/representation subset and treatment of
  unresolved successor lineage and subject-not-bound rows;
- the T4 task/schema/prompt/model/provider route, sample and human-review
  design, with a per-tranche reservation inside the AUD 10 aggregate cap;
- the product-owner interpretation of which real-run and monitoring evidence is
  sufficient for a Gate 4 closure recommendation.

Do not guess any of these, create synthetic rights decisions, or classify a
source-policy gap as a Builder retrieval failure. Stop if an implementation
would need the dirty prototype, a new source family, a new discovery rule,
unresolved identity/rights, a provider crossing without a receipt/policy, an
unreconciled cost, a semantic heuristic, or a human promotion decision.

## Next single concrete instruction specification

**Do not issue a T2 code-change instruction against this checkout.** The next
safe instruction is a fresh `report_only` clean-baseline verification targeting
the exact HEAD above, with the sole allowed path
`reports/G4_T2_CLEAN_BASELINE_VERIFICATION_20261028.md`. It must verify that a
clean execution surface exists without modifying or deleting any current dirty
or untracked path; compare clean HEAD availability for the T1B/Factory/
diagnostics dependencies; and report whether the two T2 prototype paths are
absent from that execution surface. If they are still present, or if the
provider-policy/rights authorities above remain unresolved, **STOP**: no T2
implementation, T3 binding, T4 crossing, spend, adoption or Gate 4 exit claim
is supported.

No tests, source acquisition, archive write, model/provider call, runtime
database, Git staging/commit, network, publication, watcher/fence operation or
follow-on dispatch was performed by this archaeology task. Only this report was
written; all pre-existing dirty/untracked material remains preserved.
