# Gate 4 T4 Factory/E3 integration archaeology

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C, report-only, provider-free  
Branch: `gate3-cg406-remediation`  
Required HEAD: `90e5f5a443293d93619d8e49f4ed7f78d0087f6a`  
Fence: v67, SHA-256 `fc89c311cc6e0e44fa5fa7d5c61e4bfd16dd9e07cf0f2727b5b9929e88b0e395`

## Result

**PARTIAL: the reusable Factory machinery is present; the accepted E2B/E3
projection has no governed handoff into it.** This is not Gate 4 closure,
rights-policy processing approval, provider readiness, spend, publication or
release authority.

The smallest credible successor is one versioned, deterministic adapter that
uses E3 only as a bounded consistency/selection input, rejoins every one of its
ten source/representation/rights tuples to the exact T3 selected-binding
manifest and current governed rights record, then delegates to the existing
`preflight_governed_rights` → `FactoryPlan` → `ReferenceFactory` path. It must
run only deterministic Factory children while provider transmission remains
blocked.

## Acceptance matrix

| Area | Result | Finding |
|---|---|---|
| Existing E3 → Factory integration | **FAIL** | No E2B/E3 source or test imports `FactoryPlan`, `ReferenceFactory`, `GovernedReference` or either Factory preflight. E3 ends at `PrivateAnswerBrief`. |
| Reusable Factory machinery | **PASS** | `FactoryPlan` and `ReferenceFactory` already provide deterministic IDs, task seeding, durable attempts, replay, failure isolation and explicit ambiguity handling (`src/charitygraph/phase5_factory.py:15-58,98-226`). |
| Code/provenance | **PASS** for the inspected accepted paths | E3 acceptance is independently recorded at the exact HEAD in `reports/G4_E3_MISSINGNESS_RIGHTS_INDEPENDENT_ACCEPTANCE_20261031.md`; E2B/E3 retain exact source, hash, rights and status carriage. The dirty Factory/rights overlay is not treated as accepted HEAD. |
| Test coverage | **PARTIAL** | E2B/E3 acceptance has 35 focused tests and T2 has provider-free Factory tests, but no test crosses the real E3 ten-source/five-subject derivative into Factory. |
| Rights | **PARTIAL** | E3 carriage and tamper rejection pass (`phase5_t4b_source_answer_projection.py:202-291,382-441`; `phase5_t4c_private_answer_brief.py:266-315`), but rights must be re-resolved from authoritative records before planning. `blocked_provider_contract_not_bound` is not permission to transmit. |
| Operational controls | **PARTIAL** | E3 reports zero provider, transport, acquisition, reservation, SQLite-open and publication side effects; T2 proves Factory replay/accounting machinery. The E3-specific plan/run trace is absent. |

## What exists and what is missing

The accepted E2B loader validates the immutable selected-binding manifest,
exactly ten rows, five subjects, subject/scope/ABN bindings, source and
representation hashes, source-record/rights carriage and content-addressed
representations (`src/charitygraph/phase5_t4b_source_answer_projection.py:382-478`).
It emits fifteen answer slots and explicit zero-side-effect counters
(`...phase5_t4b_source_answer_projection.py:659-708`). E3 composes those slots,
keeps the ten `(source_record_id, representation_sha256, rights_record_id)`
bindings, rejects envelope/inventory drift and emits all 20 North Star coverage
entries (`src/charitygraph/phase5_t4c_private_answer_brief.py:187-220,266-315,369-480`).

The missing seam is architectural, not a missing scraper or semantic engine:

1. E3 records carry the derivative envelope and ten rights tuples, but do not
   carry the full `source_definition_id`, acquisition receipt IDs, evidence
   locator IDs or authoritative rights-record bytes needed by a governed
   Factory reference.
2. `phase5_governed_factory_integration.py` at the committed HEAD accepts a
   manually assembled `GovernedReference` (`:47-71`) and lowers it to a typed
   task (`:169-248`); it has no E3 adapter and, at HEAD, no durable rights
   decision-resolution field. The current dirty working-tree overlay adds a
   separate `ArtifactRightsDecision`/catalog prototype; it is not a clean
   T4 authority and must not be used as evidence of accepted integration.
3. The clean, reusable authority path is
   `src/charitygraph/phase5_governed_rights_preflight.py:45-66,160-298,301-356`:
   it resolves a content-addressed `RightsGovernanceRecord`, checks its current
   projection, subject/scope/source/receipt/representation/evidence lineage,
   and delegates positive lowering to existing Factory preflight. T2 tests
   prove that machinery only with synthetic TEST fixtures
   (`tests/test_phase5_governed_cohort_rehearsal.py:27-40,73-148,179-234`).

There is also a committed-HEAD scope caveat: `FactoryPlan.packages()` and
`physical_packages()` group by subject plus bundle/mode but not scope
(`git show HEAD:src/charitygraph/phase5_factory.py:30-44`). The dirty working
tree adds `scope_id` to those keys, but that change is pre-existing and
uncommitted. The proposed E3 successor must use one-source deterministic
children (no physical bundle) and retain `scope_id`; a later accepted Factory
change must test scope isolation before enabling bundled E3 work.

## North Star v0.3 coverage carried by E3

The adapter must copy these statuses without upgrading them. E3 currently
projects: **1 P**, **2 M**, **3 P**, **4 P**, **5 P**, **6 M**, **7 M**, **8 M**,
**9 M**, **10 S**, **11 P**, **12 M**, **13 S**, **14 M**, **15 M**, **16 M**,
**17 M**, **18 M**, **19 P**, **20 S**. Here P means bounded partial, S source-
native support, and M explicit unassessed/missing detail, as implemented by
`_NORTH_STAR_SECTIONS` and `_coverage`
(`src/charitygraph/phase5_t4c_private_answer_brief.py:242-263,369-395`).

The handoff must preserve all 20 entries, the five `source_silent` currentness
records, fifteen answer slots, ten source hashes and ten rights tuples. It must
not turn source silence into unavailability, add canonical observations, infer
semantic claims, or create a second answer store. This follows North Star v0.3
and Data source governance: missingness is distinct, source role is
proposition-specific, and accessibility is not provider or publication
permission (`charitygraph-data/NORTH_STAR_TARGET_CARD_V0_3.md:18-36,64-118`;
`charitygraph-data/SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md:113-133,168-189`).

## Exact bounded successor instruction (<=900 seconds; not executed)

Implement only:

- `src/charitygraph/phase5_t4d_e3_factory_handoff.py`, version
  `phase5-t4-e3-factory-handoff/v1`, with a pure entry point such as
  `preflight_e3_private_answer_brief(brief, selected_manifest, rights_store,
  rights_projection, catalog, as_of, retained_bytes)`. Do not add a database,
  source acquisition, model call, scraper, semantic heuristic or canonical
  E3 store.
- `tests/test_phase5_t4d_e3_factory_handoff.py` with a disposable local fixture
  that reuses the accepted E3 projection and the existing T2 governed-rights
  fixture machinery. No raw/private bodies belong in Git.

The adapter contract is:

1. Validate the E3 shape and side-effect counters, then join its ten unique
   source/representation/rights tuples to
   `evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json` by exact
   tuple. Require equal subject, scope, source family/role, source record,
   representation hash, rights record, rights policy/version and processing /
   redistribution / binding status. Labels are display-only.
2. For each exact manifest row, construct a
   `RightsPreflightReference` from the manifest's source definition,
   acquisition and evidence-locator IDs and the rights-record content hash.
   Use deterministic task identity
   `g4_t4_e3_factory_handoff_v1`, schema/profile version `1`,
   `difficulty="deterministic"`, and no bundle key. Reuse
   `preflight_governed_rights`; do not copy rights fields into a new authority.
3. Require the durable rights record/current projection and all source,
   receipt, representation, hash, lineage, scope and locator checks to pass.
   Lower only the ten exact source tasks to `FactoryPlan`, then call
   `ReferenceFactory.seed()` and `run()` in a temporary test catalogue. Since
   the tasks are deterministic, the trace must contain no provider send,
   reservation, receipt, cost entry or publication.
4. Return the preflight diagnostics and Factory plan/run summary as an
   operational derivative only. Do not promote E3 answers or emit canonical
   knowledge. Set `build_id=phase5-t4-e3-factory-handoff-v1` and
   `route_policy_version=phase5-t4-e3-deterministic-route-v1` so replay is
   versioned and deterministic.

## Required deterministic trace and negative tests

Positive trace: accepted E2B → accepted E3 → exact ten-row T3 join → ten
current governed rights records → ten deterministic logical tasks →
`FactoryPlan` → `ReferenceFactory.seed/run` → ten successful deterministic
children; replay returns zero new work, with stable task IDs, plan hash,
subject/scope/source/rights lineage and zero provider/budget/publication
effects. Assert five subjects, fifteen slots, twenty coverage entries, ten
source hashes and ten rights tuples throughout.

Negative cases must each produce diagnostics and zero Factory tasks/runtime
work: missing or duplicate E3 tuple; subject/scope drift; source-record or
representation hash drift; rights-record/policy/role/status drift; missing or
non-current/superseded/expired/denied rights record; rights projection mismatch;
missing source definition, acquisition receipt or evidence locator; source or
representation lineage mismatch; and a requested non-deterministic/provider
route while the manifest says `blocked_provider_contract_not_bound`.

The existing T2 acceptance already supplies the needed lower-level machinery:
current-record resolution, fail-closed denial/mismatch, deterministic lowering,
Factory replay, ambiguous-send controls, failure isolation and accounting
tests. It does not supply the E3 join or the five-subject real derivative
fixture, so reusing T2 without the adapter would leave the requested claim
unproven.

## Acceptance gates and remaining blockers

- **G4-T4-E3-1:** exact HEAD/dirty boundary, E3 acceptance and private-material
  exclusion — PASS (this report adds no private material).
- **G4-T4-E3-2:** exact E3↔T3↔rights join and provenance-preserving lowering —
  required successor; currently FAIL/absent.
- **G4-T4-E3-3:** ten-task deterministic Factory trace, replay and negative
  zero-work cases — required successor; currently PARTIAL through separate T2
  and E3 suites.
- **G4-T4-E3-4:** rights carriage remains separate from provider permission —
  PASS for E3 carriage, PARTIAL for the missing handoff.
- **G4-T4-E3-5:** provider route, budget and send readiness — **later blocker**;
  no action here. The accepted T4A3 readiness report records missing
  source-owned provider policy/contract registry, exact project/service/
  endpoint/model attestation, authoritative current pricing/FX, cumulative
  AUD10 ledger/reservations and pilot-bound transport identity/reconciliation
  (`reports/G4_T4A3_REAL_SEND_AUTHORITY_AND_BUDGET_READINESS_20261029.md:26-44`).
  No provider request, reservation or spend is implied by this archaeology.
- **G4-T4-E3-6:** publication/release/Gate 4 closure — not in scope and not
  satisfied.

No tests were run in this report-only task because the requested boundary
prohibits SQLite/WAL runtime writes; the findings use the accepted E2B/E3 and
T2 focused evidence plus read-only code, manifest and status inspection. No
code, tests, source data, runtime state, cache, provider/model/network,
publication, Git, watcher or process state was changed. All pre-existing dirty
and untracked paths, including the E3 product report and T4A2 pilot preflights,
were preserved.
