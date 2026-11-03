# Gate 4 E3 missingness and rights — independent product acceptance

Status: review in progress. This is a private derivative acceptance review only; it is not Factory integration, provider-authority approval, public redistribution approval, or Gate 4 closure.

Review target: exact local HEAD `90e5f5a443293d93619d8e49f4ed7f78d0087f6a`, branch `gate3-cg406-remediation`, fence v67 SHA-256 `fc89c311cc6e0e44fa5fa7d5c61e4bfd16dd9e07cf0f2727b5b9929e88b0e395`.

## Baseline and scope

- Review is report-only. No code, tests, source data, provider, network, Git, publication, watcher, or follow-on task action is authorised.
- The worktree was dirty before review, with pre-existing tracked modifications and untracked evidence/reports/source/test files. Baseline preservation is required; no unrelated change is attributed to this review.
- HEAD is the stated direct-child commit of `d9f7635e6abc317905dd887bdf174f7db62e7098`.
- HEAD changes exactly five paths: the E2B projection, E3 private brief, their focused tests, and `reports/G4_E3_MISSINGNESS_RIGHTS_CARRIAGE_REPAIR_20261031.md`.

## Acceptance result

**PASS for the bounded private E3 derivative at this exact HEAD.** The result is
not Factory integration, provider-authority approval, public-redistribution
approval, release/promotion, or Gate 4 closure.

## Authorities and review basis

I read the local Builder authorities (`AGENTS.md:1-73`, `ARCHITECTURE.md:204-232`,
`BUILDER_MACHINERY.md:23-35,143-160`), the local North Star projection lens
(`docs/NORTH_STAR_PROJECTION_LENS_REALITY_SLICE_V01.md:1-27`) and private-provider
policy (`docs/PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_POLICY.md:1-13`),
the sibling Data authority/current-state/plan/test and governance documents,
and the sibling North Star v0.3 (`C:\CharityGraph-clean\charitygraph-data\NORTH_STAR_TARGET_CARD_V0_3.md:18-36,64-118`).
The governing rules require separate source/rights/provenance, explicit
missingness, version-bound coverage, and no collapse of unavailable,
unprocessed, inapplicable or negative states (`C:\CharityGraph-clean\charitygraph-data\SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md:113-133,168-189`,
`C:\CharityGraph-clean\charitygraph-data\TEST_PLAN.md:43-45,71-84`).

The earlier E3 reconciliation and repair reports were read, but this review
independently inspected the committed code/test diff and reran the checks
(`reports/G4_E3_INDEPENDENT_RECONCILIATION_AND_MISSINGNESS_REVIEW_20261031.md:60-156`,
`reports/G4_E3_MISSINGNESS_RIGHTS_CARRIAGE_REPAIR_20261031.md:14-104`).

## Exact commit and dirty boundary

- Exact HEAD and branch match the task: `90e5f5a443293d93619d8e49f4ed7f78d0087f6a` on `gate3-cg406-remediation`; parent is `d9f7635e6abc317905dd887bdf174f7db62e7098`.
- The direct-child commit message is the v66 engineering instruction identifier. Its diff is exactly five paths, `416 insertions / 7 deletions`:
  `src/charitygraph/phase5_t4b_source_answer_projection.py`,
  `src/charitygraph/phase5_t4c_private_answer_brief.py`,
  `tests/test_phase5_t4b_source_answer_projection.py`,
  `tests/test_phase5_t4c_private_answer_brief.py`, and
  `reports/G4_E3_MISSINGNESS_RIGHTS_CARRIAGE_REPAIR_20261031.md`.
- The v67 fence value was taken from the task. No current v67 bridge result or attestation matching the supplied HEAD/fence was present in the local reports/evidence inventory; the commit object and changed paths were verified directly.
- The worktree was already dirty with unrelated tracked modifications and many untracked evidence/reports/source/test paths. Those paths were preserved. The only new path from this review is this required report; the five HEAD code/test/report paths remain worktree-clean.

## Acceptance matrix

### 1. Exact rights and provenance carriage — PASS

The local T3 binding manifest contains 5 subjects, 10 rows, 10 unique source
record IDs, 10 unique representation hashes and 10 unique rights record IDs;
the ten rows are the exact register/AIS pairs and carry the single policy,
version, provider, public-redistribution and binding statuses
(`evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json:1-330`).

E2B has exact expected source/representation/rights bindings and carriage
constants (`src/charitygraph/phase5_t4b_source_answer_projection.py:94-195`),
requires the manifest identity and exact ten rows, checks subject/scope/ABN,
and rejects any source-record, role, rights, policy or operational-status drift
(`src/charitygraph/phase5_t4b_source_answer_projection.py:324-335,382-441`).
The citation and answer envelopes carry source role, rights-record ID, policy
ID/version, provider-processing status, public-redistribution status and
binding status (`src/charitygraph/phase5_t4b_source_answer_projection.py:202-291,352-379`).

E3 preserves the same fields in every cited comparison value and retains the
ten source/representation/rights tuples (`src/charitygraph/phase5_t4c_private_answer_brief.py:28-93,186-218`).
It verifies each answer envelope against a citation and cross-checks the
ten-tuple inventory before composition (`src/charitygraph/phase5_t4c_private_answer_brief.py:266-315`).
There is no permissive rights default in the admitted path: missing required
manifest fields fail closed (`phase5_t4b_source_answer_projection.py:331-335`),
the exact statuses remain `blocked_provider_contract_not_bound`, `not_assessed`
and `bound_not_task_eligible`, and no provider/publication operation is called.

### 2. Currentness and missingness — PASS

All five currentness records are explicitly `answer_state="unanswered"` with
`answer=null`; `_unanswered` emits governed missingness, a v0.3 reviewed-source
basis, the five distinct currentness dimensions, and
`source_silence_is_not_absence=true` for `source_silent`
(`src/charitygraph/phase5_t4b_source_answer_projection.py:31-66,481-531,682-689`).
The vocabulary maps `source_silent`, `not_reviewed`, `not_processed` and
`not_applicable` to distinct basis kinds, and tests exercise those distinctions
(`tests/test_phase5_t4b_source_answer_projection.py:179-222`). E3 rejects a
currentness slot unless it is reviewed-source `source_silent` with the v0.3
basis and non-absence flag (`src/charitygraph/phase5_t4c_private_answer_brief.py:417-435`).

The missingness state is kept separate from
`fact_vs_source_statement_vs_inference`; `not_applicable` there means no
proposition is being emitted, not that the currentness proposition is
inapplicable (`tests/test_phase5_t4b_source_answer_projection.py:191-195`).
Coverage leaves capacity, giving terms, governance, conduct and outcomes
unassessed rather than asserting absence (`src/charitygraph/phase5_t4c_private_answer_brief.py:242-262,369-395`).
No false currentness, efficacy, governance, capacity or conduct assertion was
observed.

### 3. Slots, coverage, source-native bases and replay — PASS

E2B compiles exactly fifteen slots from the five subject/two-source cohort and
retains source-native reporting periods and field paths
(`src/charitygraph/phase5_t4b_source_answer_projection.py:534-656,659-708`).
E3 declares the v0.3 projection contract, enumerates all 20 North Star sections,
and cites selected values back to exact field bases
(`src/charitygraph/phase5_t4c_private_answer_brief.py:138-160,223-263,319-327`).
The independent replay observed 5 subjects, 15 slots, 10 hashes, 10 rights
bindings and 20 coverage entries; a second replay produced an identical
document.

### 4. Negative tampering, regression and side effects — PASS

Committed tests cover representation hash, manifest identity, subject/scope,
source-record/rights, role/policy/status, missingness, answer-envelope,
inventory, side-effect and unknown-label tampering
(`tests/test_phase5_t4b_source_answer_projection.py:86-146,161-230`,
`tests/test_phase5_t4c_private_answer_brief.py:109-159`).

Focused command, run without bytecode or pytest cache:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts= tests/test_phase5_t4b_source_answer_projection.py tests/test_phase5_t4c_private_answer_brief.py -q
35 passed in 1.58s
```

Independent read-only probes also passed: deterministic replay, exact ten
rights tuples, citation-rights tamper rejection, and currentness-state tamper
rejection. Observed side-effect counters were all zero (`provider_calls`,
`transport_requests`, `budget_reservations`, `source_acquisitions`,
`publications`, `sqlite_opens`), consistent with the explicit E2B counters
(`src/charitygraph/phase5_t4b_source_answer_projection.py:693-707`) and E3
zero-side-effect guard (`src/charitygraph/phase5_t4c_private_answer_brief.py:266-270,462-479`).

## Boundary and disposition

This PASS accepts the private, provider-free E2B/E3 derivative at the stated
commit. It does not establish governed Factory integration, live provider
contract/route/budget authority, public redistribution eligibility, immutable
release promotion, Viewer compatibility, or Gate 4 closure. Those are separate
governance and supervisory decisions. No substantive defect was found, so no
bounded successor is specified.

The report contains no raw source bodies, private evidence, prompts, model
responses, credentials, runtime databases, WAL/SHM files, caches or publication
material.

