# Gate 4 E3 independent reconciliation and missingness review

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C, report-only  
Branch: `gate3-cg406-remediation`  
Required HEAD: `d9f7635e6abc317905dd887bdf174f7db62e7098`  
Fence v66 SHA-256: `572933d62f41b07a21036e8d22d174bd51737c9529ec8be44f10feed9aa567ce`

## Result

**PARTIAL — useful provider-free private derivative; not Gate 4 closure.** The
five-subject brief is mechanically bounded and reproducible, but its currentness
epistemic label and the E3 report wording use `not_applicable` for evidence that
is source-silent/unassessed. That is not a safe substitute for the North Star
v0.3 missingness vocabulary. The E3 answer envelope also drops source-role and
rights-policy/status fields that exist in the governed T3 rows.

## Scope, dirty boundary and provenance

Only this report was written. No product, bridge, private evidence, runtime
state, cache, database/WAL, provider/model/network, source acquisition,
reservation/spend, publication, Git, watcher or process state was changed.
The two untracked T4A2 pilot-preflight files and all other dirty/untracked paths
were preserved.

The repository was at the required HEAD and branch. Direct-child commit
`beb2765e2136e9b11bd0610767e4f9ee6ac4b735` has parent
`6442e9abdc39d40d55b1653a1b98b24dfa78821b` and changes exactly:

```text
reports/G4_E3_PRIVATE_FIVE_CHARITY_ANSWER_BRIEF_20261030.md
src/charitygraph/phase5_t4c_private_answer_brief.py
tests/test_phase5_t4c_private_answer_brief.py
```

The two subsequent maintenance commits did not alter E3 product code or tests:
`66e20064645ea4b6c8c29832845db84fd66c1a1d` changes bridge/launcher and its
quiet-launch test; `d9f7635e6abc317905dd887bdf174f7db62e7098` changes
autonomous-loop/bounded-authority/windows-process and that bridge test. A
read-only `git diff --quiet beb2765..d9f7635 --` over the E3 code and test paths
returned clean.

Current worktree hashes:

| Path | SHA-256 | Git blob |
|---|---|---|
| `src/charitygraph/phase5_t4c_private_answer_brief.py` | `072d6ff12e6362c6aef92d8b2bf1b35c81df5c699d9d20e610fdccd0fcf1dd23` | `bf95340003d1cb9ea5cd77ae5453a5415ab678e5` |
| `tests/test_phase5_t4c_private_answer_brief.py` | `5863e8768d9aa5ebc697ff7f925a2637c7fb0d067271433eb9577f564325ff3e` | `c0eaa2e4185c46f9f266b4512ee21c618bf38113` |
| pre-existing dirty E3 product report | `80e23f270be4046a25f68618c4a49d16f89e20a31eddf4830889ea657f938a6a` | `b2af6e07cdc950eb448d4c67bd6af5d0bc942135` |

The committed E3 report blob is `326911890d063e975a16211af091844123a0680f`;
the current dirty report is a `108 insertions / 166 deletions` worktree diff
against HEAD. It was already modified when this task began. This is the prior
review-time report/worktree anomaly, not a change introduced by the two bridge
maintenance commits and not a semantic mutation of the E3 code/tests. The
exact external cause of the earlier failed independent result is not recoverable
from the current local evidence; it must not be conflated with E3 product
provenance.

## Independent product reconciliation

The governed T3 manifest has 10 rows, 5 subjects, 10 unique source-record IDs,
10 unique representation hashes and 10 unique rights-record IDs. All ten rows
are the expected pairs of `acnc_register/register_identity` and
`acnc_ais_bundle/annual_information_statement`; the exact source-record,
representation and rights IDs remain in
`evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json:18-330` and
are independently enumerated in `reports/G4_E1_FIVE_CHARITY_EVIDENCE_BACKED_PRODUCT_DEMONSTRATION_20261030.md:62-73`.
The T3 manifest file SHA-256 is
`06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4`.

The E2B loader re-hashes the ten exact content-addressed JSON files, checks
JSON shape, ABN and source family, and fail-closes the subject/scope/source/
representation/rights-record tuple (`src/charitygraph/phase5_t4b_source_answer_projection.py:293-383`).
E3 then composes only the validated E2B records
(`src/charitygraph/phase5_t4c_private_answer_brief.py:231-262,344-409`).
The observed composition was 5 subjects, 15 answer slots, 10 hash bindings,
20 coverage sections, 10 supported activity/scale slots and 5 unanswered
currentness slots. Reporting periods and field bases are retained in
`phase5_t4b_source_answer_projection.py:480-531` and
`phase5_t4c_private_answer_brief.py:276-312`.

## Missingness finding

North Star v0.3 says missingness is not absence and requires distinct states,
including source silent, not reviewed, not applicable and not processed
(`C:\CharityGraph-clean\charitygraph-data\NORTH_STAR_TARGET_CARD_V0_3.md:28-32`).
It also states that service description does not prove capacity, silence does
not prove unavailability (`:64-66`), a Giving Offer is a distinct currentness
proposition (`:70`), governance is its own evidence domain (`:72-74`), adverse
silence is not a clean record (`:100-102`), and outcomes/effectiveness require
their own evidence (`:108-110`). Builder architecture likewise forbids
collapsing inapplicability, not-yet-processed and scoped negative assessment
(`ARCHITECTURE.md:214-230`; `BUILDER_MACHINERY.md:23-35`).

The good boundary is real: `_unanswered()` emits `answer_state="unanswered"`,
`answer=None`, dimensions for current giving terms, service capacity,
outcomes/effectiveness, governance and conduct, and
`source_silence_is_not_absence=True`
(`src/charitygraph/phase5_t4b_source_answer_projection.py:387-418`). E3
requires the currentness slot to stay unanswered
(`src/charitygraph/phase5_t4c_private_answer_brief.py:356-381`). Coverage
sections 7, 8, 9, 16 and 18 are `M`/`unassessed`, not negative findings
(`phase5_t4c_private_answer_brief.py:207-227,315-341`). No false currentness,
efficacy, capacity, governance or conduct conclusion is produced.

The defect is nomenclature and contract precision: `_unanswered()` sets
`fact_vs_source_statement_vs_inference="not_applicable"` at line 417, and the
pre-existing E3 report repeats that the currentness records “remain
`not_applicable`”. A read-only adversarial composition probe observed, for all
five currentness slots: `missingness.status="not_established"`, source-silence
flag `true`, and epistemic label `not_applicable`. Thus the implementation does
not assert substantive inapplicability, but it does not expose the governed
`source_silent`/`not_reviewed` state cleanly enough for acceptance. This is
**PARTIAL semantic missingness**, not evidence of absence.

## Acceptance matrix

| Area | Result | Evidence-backed reason |
|---|---|---|
| Source bindings | **PARTIAL** | Underlying T3/E2B validation is 10/10 exact, but E2B/E3 records expose source family/record/hash and omit T3 `source_role`, rights policy ID/version and processing/publication status (`phase5_t4b_source_answer_projection.py:158-219`; T3 manifest rows). |
| Semantic missingness | **PARTIAL** | Explicit unanswered/source-silence protection passes, but `not_applicable` is used as the epistemic label for source-silent currentness and is repeated by the dirty E3 report. |
| Code provenance | **PASS** | Exact three-path E3 child commit; E3 code/tests unchanged by `66e2006` and `d9f7635`. The dirty report is separately identified and preserved. |
| Focused tests | **PASS** | No-cache/no-bytecode E2B+E3 run: `19 passed in 2.81s`; adversarial probe confirmed the counts and the missingness-label issue. Existing tests do not assert the governed vocabulary or role/policy carriage. |
| Operational controls | **PARTIAL** | Provider-free, read-only composition reports zero provider calls, transport, budget, acquisition, publication and SQLite opens (`phase5_t4b_source_answer_projection.py:534-579`), but E3 is not routed through governed Factory integration and live provider budget/route authority remains unresolved. |

## Focused verification

Command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts= tests/test_phase5_t4b_source_answer_projection.py tests/test_phase5_t4c_private_answer_brief.py -q
19 passed in 2.81s
```

The existing tests cover deterministic replay, 5 subjects/15 slots, 10 hashes,
period and field-basis retention, explicit source silence, hash/identity drift,
non-zero side effects and unknown display labels
(`tests/test_phase5_t4b_source_answer_projection.py:52-160`; `tests/test_phase5_t4c_private_answer_brief.py:34-124`). No product files or
pytest cache/bytecode were written by the run.

## Focused successor (<=900 seconds; not executed here)

1. `src/charitygraph/phase5_t4b_source_answer_projection.py`: carry the exact
   T3 `source_role`, `rights_record_id`, rights policy ID/version and
   provider/publication statuses into the typed citation/answer envelope; use a
   governed missingness value such as `source_silent` for reviewed source
   silence and reserve `not_reviewed`/`not_applicable` for their actual scopes.
2. `src/charitygraph/phase5_t4c_private_answer_brief.py`: preserve those fields
   in `CitedValue`/answer-slot output and version the North Star v0.3 coverage
   contract explicitly; do not turn M/unassessed into a negative claim.
3. `tests/test_phase5_t4b_source_answer_projection.py` and
   `tests/test_phase5_t4c_private_answer_brief.py`: add exact assertions for
   source-silent versus not-reviewed/not-applicable, and negative tests for
   tampered source role, rights policy ID/version and processing/publication
   status. Re-run the same 19-test command plus the new cases.

This is a narrow provider-free repair with exact paths and tests; estimated
implementation and verification time is under 900 seconds. No implementation
or follow-on task is authorised by this report.

## Prioritised blockers and boundary

1. **Governed Factory integration:** the E3 seam consumes an already-built
   `AnswerProjection`; it does not validate governed references into
   `FactoryPlan`/`ReferenceFactory`. The prior Factory review records that the
   governed-reference handoff and fresh end-to-end trace remain unproven
   (`reports/G4_P1_GOVERNED_FACTORY_INTEGRATION_20261025.md:63-75`).
2. **Live provider budget/route:** real-send readiness remains not ready. The
   current blocker set is a source-owned provider contract/policy registry,
   exact project/service/endpoint/model attestation, current pricing/FX,
   cumulative AUD10 ledger and outstanding reservations, plus request/transport
   identity and reconciliation (`reports/G4_T4A3_REAL_SEND_AUTHORITY_AND_BUDGET_READINESS_20261029.md:34-42`).
   No provider request, reservation or spend was made here.

The report contains no raw source bodies, private evidence, model responses,
credentials, runtime databases, WAL/SHM files or publication material. It claims
neither Gate 4 closure nor release/publication authority.
