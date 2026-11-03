# G4-O1C — quarantined P3b2 forward evidence and P3c/P4 archaeology

Date: 2026-10-26 (Australia/Sydney)  
Mode: provider-free, local, `REPORT_ONLY`  
Disposition: **P3b2 remains quarantined; no Gate 4 acceptance or closure.**

## 1. Control and preservation

The required report path was absent before this task (`Test-Path` returned
`False`). Local repository identity independently verified:

| Item | Observed |
|---|---|
| workspace | `C:\CharityGraph-clean\charitygraph` |
| branch | `gate3-cg406-remediation` |
| HEAD | `4b3fbcaeaace5170994da57a4fe502e6f450ba29` |
| HEAD tree | `627fafae46e097d4d4f8d67b57a385c374b0ab84` |

The pre-existing worktree was not cleaned, staged, reset, checked out or
otherwise repaired. The final pre-report read showed 280 visible
`git status --porcelain=v1 --untracked-files=all` records (10 modified and 270
untracked), with the known access-denied warnings for the two synthetic
pytest-recovery prefixes. The UTF-8 LF-joined status fingerprint was
`ea9596961fc787dd69b3bf4898858bf2242669694e5619764c8a011afbfa4028`.

No provider/API, network, source acquisition, spending, watcher/process,
Drive, bridge, GitHub, publication, release, merge, follow-on dispatch or
semantic inference occurred. The only checkout write from this task is this
fresh report. Temporary pytest bases were outside the checkout under
`C:\CharityGraph-runtime`.

The sibling Data authority documents are not present in this configured
workspace. External copies were not accessed because this task is explicitly
provider-free and repository-local. Prior local Gate 4 archaeology records
the previously inspected Data authority hashes and describes the applicable
source/rights, product/data, policy, roadmap, implementation and test-plan
boundaries; this report does not claim a fresh external Data checkout.

## 2. Quarantine boundary

The supplied supervisor facts identify active v28 fence SHA-256
`9f60d5f3252f59d0ab24650fad1a3357d2b961d472c5bc14194d0407566a0a5a`, one
managed worker, active code-change route, zero claims and
`dispatch_clear=true`. Those are supervisor controls and were not re-read from
outside the workspace.

The P3b2 bridge result remains `CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES`
with baseline error that the allowlisted dirty baseline was not preserved for
`src/charitygraph/phase5_governed_factory_integration.py`. No private pre-edit
snapshot existed for that attempt. v28's private reconciliation snapshots
apply only to future attempts; they cannot reconstruct the missing historical
pre-edit bytes. P3b2 is therefore not replayed, upgraded, or retroactively
accepted here.

Supplied report hashes were independently verified:

```text
bd5f3d4d1e02f431f1cf3a3befa41f2c55a768307c0ba9370534987d5d682116  reports/G4_P3B2_RIGHTS_POLICY_IDENTITY_20261026.md
bf87d8287069b1025fe876600cc97cd21b5fd97b28d98078c4a5654554d8fef8  reports/G4_P3B1_SOURCE_SUBJECT_PROVENANCE_20261026.md
a6710ea5afa219cbce6f1d0bc8f0540ea57fc9d4f33f2beba3374ceca7977f39  reports/G4_P3_SOL_INDEPENDENT_ACCEPTANCE_20261026.md
```

## 3. Current implementation and evidence matrix

| Area | Observed current behaviour | Authority/evidence | Disposition |
|---|---|---|---|
| Durable subject provenance | `_validate_available()` requires non-empty `about_subject_ids` and the planned subject; mismatches fail before Factory lowering. Explicit multi-subject bindings remain accepted. | `phase5_governed_factory_integration.py:250-330`; P3b1 test/report; fresh focused run below. | **Locally passing; not P3b2 acceptance.** |
| Rights policy registry | `RIGHTS_POLICY_REGISTRY` contains exact `PUBLIC_FACTS_ONLY_V1/1.0.0` and `AU_FAIR_DEALING_ANALYTICAL_PROCESSING_V1/1.0.0`. `governed_rights_policy()` checks exact ID, version and basis. | `source_rights.py:25-68`; `tests/test_source_rights.py` covers both policy families, including Fair Dealing fail-closed predicates and Public Facts structured-factual requirements. | **Independently present and tested; code is not legal authority.** |
| Exact rights/material binding | Current preflight resolves a durable decision for each exact representation, checks hash, source record/origin/role, acquisition lineage, current supersession, provider policy and rights basis. | `phase5_governed_factory_integration.py:341-509`; P3b1/P3b2 reports and 75-case rerun. | **Provider-free behaviour observed.** |
| Expiry | Absent expiry is accepted; equality at `expires_on` is accepted; a later planned date is blocked. | `source_rights.py:260-330`; rights integration/P3b2 tests. | **Passing in fake path.** |
| Negative side effects | Missing, mismatched, duplicate, revoked/superseded, expired and policy-invalid cases do not lower to tasks or create attempts, receipts, reservations or cost entries. | P3b1/P3b2/rights tests; fresh full suite. | **Passing provider-free.** |
| Positive path/accounting | Authorized synthetic `PUBLIC_FACTS_ONLY_V1/1.0.0` lowers to one task and fake Factory execution; one receipt, one reservation and two reconciled cost entries; actual fake cost `AUD 0.002000`. | Fixture in `tests/test_phase5_governed_factory_integration.py`; P3b2/rights tests. | **Passing provider-free; not real spend.** |
| Multi-subject/scope/isolation | Matching explicit multi-subject references are accepted independently; wrong subject/scope, role and policy references fail without suppressing an unaffected peer. | P3b1/P3b2 tests; `runtime/test_task_state.py` run/subject/scope guards. | **Passing for exercised cases.** |
| Restart/idempotence | Reopen/rerun adds no task, attempt, receipt, reservation or cost rows. Physical attempt re-entry checks run, subject, scope, mode, request, reservation and member identity. | `catalog.py:4083-4122`; fresh 75-case suite. | **Passing locally; no provider-side exactly-once proof.** |
| Failure isolation | Factory and Standard transport retain independent terminal/ambiguous outcomes and continue unaffected peers where policy permits. | `phase5_factory.py`; `phase5_standard_transport.py`; existing provider-free tests. | **Offline control evidence; no live run.** |
| Rights schema authority | Rights tables are installed by `ARTIFACT_RIGHTS_TABLE_SQL`/`_ensure_artifact_rights_tables()` and are not represented by a numbered migration. `MIGRATIONS` ends at v28. | `catalog.py:78-124,450-475`; `runtime/migrations.py:1192-1223`. | **P3c gap: migration/versioned evolution/rebuild semantics absent.** |
| Governance-record authority | Rights decision material is stored in SQLite `material_json` plus hashes/events/diagnostics. No content-addressed governance-record export/import/rebuild authority is required by this path. | `catalog.py:2993-3123`; Builder architecture says SQLite is rebuildable operational state, not sole evidence authority. | **P3c gap: product authority incomplete.** |
| Current-decision uniqueness | Preflight detects multiple current matching decisions and fails closed, but there is no database uniqueness constraint for one current decision per exact representation. | `catalog.py:78-105`; `phase5_governed_factory_integration.py:381-405`. | **P3c gap: application check, not transactional uniqueness.** |
| Execution-boundary revalidation | Preflight validates before Factory planning; the fake `ReferenceFactory` consumes the resulting plan and does not revalidate rights immediately before a future provider crossing. | `phase5_factory.py`; P3 independent acceptance report. | **P3c/P4 gap; provider use remains unauthorized here.** |
| Concurrency/scheduling | SQLite immediate transactions and competing-claim tests exist. Standard transport bounds workers, records observed concurrency and stops on systemic/ambiguous conditions. The governed ReferenceFactory path is not a production multi-worker scheduler. | `runtime/catalog.py`; `phase5_standard_transport.py`; G4 offline scorecards. | **Offline partial/proven; production operation absent.** |
| Monitoring | Durable rows and run results expose state/counts, but no operator health report, alerting, SLO or live diagnostic surface was found. | G4 A3E and industrialisation evidence reviews; direct code search. | **P4 gap; chosen next tranche.** |

This distinguishes observed code/test behaviour from the source/product
authority it is intended to implement. It does not convert a passing fake
fixture into source authority, a human decision, live-provider evidence or
historical byte-preservation proof.

## 4. Fresh verification

Commands were run exactly with `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`,
`pytest -p no:cacheprovider`, and unique basetemps outside the checkout:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3c-archaeology-p3b1-20261026-01 tests/test_phase5_source_subject_provenance_p3b1.py
2 passed in 2.52s

$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3c-archaeology-p3b2-20261026-02 tests/test_phase5_rights_policy_identity_p3b2.py
7 passed in 4.91s

$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3c-archaeology-full75-20261026-03 tests/test_source_rights.py tests/test_phase5_governed_factory_rights.py tests/test_phase5_governed_factory_integration.py tests/test_phase5_factory.py tests/runtime/test_task_state.py tests/test_phase5_source_subject_provenance_p3b1.py tests/test_phase5_rights_policy_identity_p3b2.py
75 passed in 17.98s
```

No test invoked a real provider or API. The positive cases use the repository
fake provider and synthetic durable catalogue fixtures only.

Final expected current hashes matched:

```text
72f0cc0b3fb1f1ad0f3bb92700e6fe26bc85a9a97510a261e4ae285e66da79bc  src/charitygraph/source_rights.py
503d357761ab4884c4099b58e8ff15becb7214611984b46af7d68b236a8b0224  src/charitygraph/phase5_governed_factory_integration.py
3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1  src/charitygraph/runtime/catalog.py
df6e7049ab6c3bb36e517ae6d4cc73240c826d13dbc17e1417e145b1b99d44c9  tests/test_phase5_rights_policy_identity_p3b2.py
dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281  tests/test_phase5_governed_factory_rights.py
41bb23e49f22e63b0f5fc6fd0b69babf508389292e2b9469f2992e43f0866cae  tests/test_phase5_source_subject_provenance_p3b1.py
fa85b7fdf949e58a0e0819634e97d1265e27e97a90ac4ca867874ab6ab5683b7  tests/runtime/test_task_state.py
```

## 5. One smallest safe next tranche

**Recommend one additive P4 provider-free run-diagnostics projection**, not a
rights repair or scheduler rewrite. It is the smallest product tranche that
closes the locally observed monitoring-surface gap while making existing
offline concurrency, scheduling/stop, restart/no-resend, failure-isolation and
cost-reconciliation evidence inspectable in one deterministic artifact. It
does not execute work, discover sources, interpret prose, authorize rights or
replace the existing Factory/transport.

Exact future allowlist:

| Path | State now | Pre-edit hash/status |
|---|---|---|
| `src/charitygraph/phase5_run_diagnostics.py` | fresh absent | absent; no hash |
| `tests/test_phase5_run_diagnostics.py` | fresh absent | absent; no hash |
| `reports/G4_P3C_P4_RUN_DIAGNOSTICS_20261026.md` | fresh absent | absent; no hash |

Read-only clean dependencies inspected for the future task:

```text
195d15c3ce0a1f4452984cabb71c5c6ab84efd1a898ea542fbe3dc0866396c5b  src/charitygraph/phase5_standard_transport.py
7370a7be3080e4923a6b75c1c5596f053441c00da1d83d80dac164313fb09eea  tests/test_phase5_standard_transport.py
ee91b164e4ce658eda70d29134ebfaaa2d3e9636ca1754921d242b8bbcd15516  src/charitygraph/phase5_preflight.py
a24eaa07db4b439e0caa76b0ecb033e4e4cc71d981fe3278692884d9ed27fce5  src/charitygraph/phase5_delivery.py
```

The future implementation should be a pure, versioned, content-hashed
projection over caller-supplied run results and existing durable ledger
positions. It may add no scheduler, provider route, rights registry, source
family, semantic heuristic or alternative authority. It must not edit the
following dirty/quarantined paths in that task:

```text
src/charitygraph/source_rights.py
src/charitygraph/phase5_governed_factory_integration.py
src/charitygraph/runtime/catalog.py
tests/test_phase5_rights_policy_identity_p3b2.py
tests/test_phase5_governed_factory_rights.py
tests/runtime/test_task_state.py
```

Minimum acceptance tests for that one tranche:

1. deterministic diagnostic identity and content hash for identical run input;
2. complete status/count/stop/unattempted/concurrency/provider-post summary;
3. fake Standard transport run showing the configured concurrency cap and
   independent terminal failure isolation;
4. saved-response/restart run showing zero new provider posts;
5. ambiguous/systemic stop state retained distinctly from item failure;
6. a SQLite fake ledger fixture showing reservation, actual and release
   amounts reconcile and no cost is counted twice; and
7. missing/incomplete diagnostic inputs fail closed without creating tasks,
   attempts, receipts, reservations or cost entries.

The future report must include the fresh module/test/report hashes, exact
commands, isolated runtime roots, output hash and a clear `offline only`
acceptance statement. This would be meaningful product progress while P3b2
remains quarantined because it depends only on existing generic runtime
results, not on the disputed rights-policy bridge result.

## 6. Deferred P3c/P4 closure needs

The following are not included in the one recommended tranche:

- an explicit versioned rights schema migration and upgrade/rebuild contract;
- content-addressed governance-record authority independent of rebuildable
  SQLite, with Data/Product Owner agreement on the record schema;
- a transactional current-decision uniqueness/revalidation design at the
  actual execution boundary;
- multi-worker Factory scheduling/monitoring beyond the existing bounded
  Standard feeder;
- live provider receipts, external ambiguity and provider-side exactly-once
  effects;
- an approved current subject/source cohort, real cost/latency/SLO evidence,
  operational alerting and population-scale Gate 4 evidence; and
- current sibling Data authority reconciliation before any cross-product
  behaviour or policy change.

These are product-acceptance/evidence requirements, not permission to discover
sources, call a provider, spend, publish, change public schemas or close Gate
4. The explicit policy question, if work proceeds on P3c, is the durable
governance-record and migration authority; it must be resolved before code
chooses one.

## 7. Historical reconstruction conclusion

Independent retrospective byte-exact reconstruction of the quarantined P3b2
pre-edit state is genuinely impossible from the current evidence because the
attempt did not retain a private pre-edit snapshot and its bridge result is
`CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES`. The current hashes prove only
current bytes. v28 can make future attempts auditable; it cannot manufacture
the absent historical bytes. Only authoritative Work recovery or an explicit
Product Owner decision could change that evidentiary position. No such recovery
or decision is asserted here.

Gate 4 therefore remains open and P3b2 remains quarantined/unaccepted. This
report does not authorize or dispatch any follow-on task.
