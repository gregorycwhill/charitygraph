# G4 Phase-5 project-cost population independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Disposition: **PARTIAL for bounded code semantics; FAIL for project-wide authoritative completeness**

## Scope and provenance

Reviewed the exact local `gate3-cg406-remediation` HEAD
`33cf117c69fbe8785e6803cda108fc08d4651838`, parent
`0a3a2e8f85703798aed95ee27287de3a06b5714c`, against the supplied v87 fence
SHA-256 `a4e6dd6629831658d6505118c72cb6090dd2fc18f48ecae065f15562b1f0a05c`.
The direct-child `git diff-tree` contains exactly:

- `src/charitygraph/phase5_project_cost_reconciliation.py`
- `tests/test_phase5_project_cost_reconciliation.py`
- `reports/G4_PHASE5_PROJECT_COST_POPULATION_COMPLETENESS_20261031.md`

The live checkout had many unrelated pre-existing dirty and untracked paths.
They were read-only inspected and left untouched; none was included in the
acceptance report or test overlay.

The committed implementation report is not exact-HEAD metadata: it names
`0a3a2e8f...` and v86, not this commit and the supplied v87 fence. Its claimed
`62 passed` related count was not used as independent evidence.

## Independent test evidence

An exact-HEAD `git archive` ZIP was expanded under
`C:\CharityGraph-runtime\g4-phase5-cost-acceptance-bc220660e09b4065bd5b500a4b0b6c28\overlay`.
All pytest basetemp directories were outside the repository, with
`PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`.

- Focused `tests/test_phase5_project_cost_reconciliation.py`: **22 passed**.
- Related operator-health/accounting suite (`test_phase5_operator_health.py`,
  `test_phase5_operator_health_catalogue.py`,
  `test_phase5_operator_health_runtime_contract.py`,
  `test_phase5_t4a11_immutable_catalogue_snapshot.py`,
  `test_phase5_t4a9_sqlite_accounting_contract.py`,
  `test_phase5_t4a_budget_attestation.py`,
  `test_phase5_t4a_durable_accounting_export.py`, and
  `test_phase5_t4a_project_budget_snapshot.py`): **108 passed**.

No provider, model, external source, Drive, watcher, GitHub, publication,
release, gate-closure, or follow-on action occurred.

## Bounded code semantics: PARTIAL

Passing evidence:

- `phase5_project_cost_reconciliation.py:286-385` opens a path using
  SQLite `mode=ro&immutable=1`, rejects an uncheckpointed WAL, sets
  `query_only`, requires schema 29, and deterministically orders the
  `runs.run_id` inventory. The existing adapter also enforces read-only access
  and safe allowlisted fields at `phase5_operator_health_catalogue.py:228-366`.
- `:1313-1334` passes discovered IDs to the existing bounded adapter. The
  projection uses exact joins, Decimal parsing and canonical sorted JSON
  (`:78-99`, `:857`, `:1172-1185`), and does not include raw usage JSON or
  provider result payloads.
- Missing/stale schema, missing attempts/receipts/cost rows, missing pricing or
  FX, contradictory IDs, duplicate/conflicting receipts, retry ambiguity and
  reservation/release uncertainty are represented as blockers or unknowns in
  the focused tests (`tests/test_phase5_project_cost_reconciliation.py:93-351,
  376-438`). A known observed subtotal is retained while authoritative totals
  and `remaining_spend` are null for incomplete cases.
- The synthetic two-run fixture at `tests/test_phase5_project_cost_reconciliation.py:354-373`
  deterministically produces AUD 3.3. This is a valid bounded fixture result
  only if its expected two-run population is independently established.

Material false-positive found:

The authority predicate at `:1214-1228` checks population state, schema state,
and actual cost rows, but does not require the complete blocker/unreconciled
set to be empty. The population check at `:544-545` only reports a missing cost
record when a run has no cost entries at all.

In a provider-free probe, I added a second structurally complete but
`send_ambiguous` request/attempt/receipt path to an otherwise valid two-run
fixture and gave it no cost entry. The result was:

- population: `complete`;
- project-wide status: `AUTHORITATIVE`, `authoritative_total: "3.3"`;
- blocker: `AMBIGUOUS_PROVIDER_CROSSING`;
- `unreconciled.count`: `1`.

Therefore a materially unreconciled provider crossing can coexist with an
authoritative project-wide total. This is a code-level acceptance failure for
the required fail-closed semantics, even though the ordinary negative tests
pass.

## Project-wide authoritative completeness: FAIL

The default `project_wide=True` path derives `expected_run_ids` by selecting
all non-empty IDs from the current database's `runs` table
(`:355-375`, called from `:1315-1319`). Schema 29, a non-empty table, and
equality between that table and the same database's exported rows establish
only internal consistency of the currently available SQLite file. They do not
establish that the file contains every historical or provider run.

Thus an incomplete database can be a closed world: omitted historical runs
are invisible, the inferred expected inventory omits them too, and all
remaining rows may be incorrectly considered complete. The caller-supplied
boundary is deliberately bypassed as an authority when the inferred
`persisted_schema29_runs` inventory is present (`:659-665`). The code supports
an externally supplied `population_inventory` and correctly rejects a missing
run in the focused test, but the default `project_wide=True` call does not
require such an independently authenticated, complete source-owned inventory.

The two-run synthetic authority result is consequently acceptable only as a
bounded self-consistency demonstration, not as authority for all project-wide
historical/provider runs or for cumulative project spend. No AUD 10 remainder
is inferred: `remaining_spend` remains null, correctly separated from this
failed completeness claim.

## Provenance, scope and limitations

The changed implementation and test SHA-256 values at this exact checkout
are, respectively:

- implementation: `69848e58383ade666f7e26a7e6f93215aea675f1eb060380bc2b836a0d85e736`
- focused tests: `757a342d1072ee92b44e23d95d48def5e53828cba6aaa59461b8eeb22d5f4e29`.

The source lineage IDs are safe projected identifiers, not independent
authority. Provider-side exactly-once effects, invoice truth, pricing/FX
validity, unpersisted charges, and historical population completeness remain
unobserved. No code repair is made by this report-only acceptance, and no Gate
4 closure or scorecard change is claimed.
