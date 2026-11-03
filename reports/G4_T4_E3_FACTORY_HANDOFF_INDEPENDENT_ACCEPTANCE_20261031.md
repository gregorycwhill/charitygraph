# Gate 4 T4D E3-to-Factory independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C, report-only, provider-free  
Branch/HEAD: `gate3-cg406-remediation` / `d41fd766e8e5d9c1f9e63d17b30350c956bbcfc2`  
Parent: `90e5f5a443293d93619d8e49f4ed7f78d0087f6a`  
Fence: v68 / `e06d652988383909e72cf59367c8d4e290c9a9778407e72c644bae4a8c103ea3`

## Verdict

**PARTIAL acceptance of the provider-free adapter; not Gate 4 closure.** The
committed adapter is mechanically sound and rights-fail-closed, but the
independent evidence does not prove the exact committed T3 rights authority or
cross-scope bundling boundary. Provider-route, budget, publication and release
readiness remain out of scope.

## Exact commit and dirty boundary

`d41fd766` is the exact direct child of `90e5f5a`; its raw diff contains exactly
these three additions and no source/test changes outside them:

| Path | Lines | raw content SHA-256 |
|---|---:|---|
| `src/charitygraph/phase5_t4d_e3_factory_handoff.py` | 407 | `91f71f3b8292a98b47eb852124d6484c7b8c5078b9686c10071fe65d299fa220` |
| `tests/test_phase5_t4d_e3_factory_handoff.py` | 605 | `3bc03724b1279920ee4503086f4e1ad0f04b1b6c54186ef5e414c40f2dd62ae5` |
| `reports/G4_T4_E3_GOVERNED_FACTORY_HANDOFF_IMPLEMENTATION_20261031.md` | 86 | `cdf78ed4496af29ede41f7a404f466860ec460c674be540063edd607a7c45f76` |

The pre-existing dirty and untracked Factory, rights, T4A2 and E3-overlay
paths were preserved and not used as authority. The clean archive overlay was
`C:\CharityGraph-runtime\g4-t4d-independent-acceptance-20261031-r2`; bytecode
and pytest cache were disabled.

## Independent verification

- The exact reported focused command reproduced **28 passed** in 93.12s.
- The exact reported E2B/E3 regression command reproduced **41 passed** in
  14.41s. The expanded relevant E2B/E3/Factory/rights set was **56 passed**.
- An explicit disposable-fixture trace observed: 5 subjects, 15 answer slots,
  20 North Star v0.3 entries, 10 source hashes, 10 rights bindings, 10 logical
  tasks, 10 seeded, 10 first-run completions, 0 replay work, 0 provider sends,
  0 provider receipts, 0 budget reservations and 0 cost entries. Plan hash:
  `a6e36aa5adbaafc203a0a0a3fa15ab2985bb790c27eea9d766110da5bdb0bba7`.
- Tamper tests cover tuple duplication/missingness, subject/scope/source/
  representation/hash drift, rights policy/version/status drift, missing or
  expired/denied/superseded rights, projection mismatch, missing durable
  source/receipt/locator, source/representation lineage mismatch and blocked
  non-deterministic/provider routing (`tests/test_phase5_t4d_e3_factory_handoff.py:437-605`).

## Acceptance matrix

| Area | Result | Evidence and finding |
|---|---|---|
| Mechanical trace | **PASS** | The real committed E3 projection is composed from the selected T3 manifest and representation fixture; the adapter validates 5/15/20 and exact ten-row inventories (`src/charitygraph/phase5_t4d_e3_factory_handoff.py:181-205`). Exact T3 has 10 rows, 5 subjects, the two admitted ACNC families, `bound_not_task_eligible`, and blocked provider status (`evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json:18-40`). |
| Rights / no bypass | **PARTIAL** | The adapter performs row-level rights checks then calls `preflight_governed_rights` (`src/charitygraph/phase5_t4d_e3_factory_handoff.py:328-390`); that seam resolves the authoritative record, current projection and durable lineage (`src/charitygraph/phase5_governed_rights_preflight.py:160-298`). However, the test fixture rewrites the exact T3 rights IDs and policy to synthetic internal-policy records before testing (`tests/test_phase5_t4d_e3_factory_handoff.py:166-174,332-339`), so exact committed T3 rights-record resolution is not independently proven. |
| Missingness / v0.3 coverage | **PARTIAL** | Counts and projection-contract version are fail-closed, and the adapter does not create or upgrade claims (`src/charitygraph/phase5_t4d_e3_factory_handoff.py:184-205,239-257`). It does not validate the actual 20 status values or explicitly assert the five `source_silent` currentness records; that distinction remains dependent on the accepted E3 constructor. |
| Provenance / lineage | **PASS mechanically; PARTIAL evidence exactness** | E3/T3 envelope equality is checked and positive lowering delegates to the governed source/receipt/evidence/representation checks (`src/charitygraph/phase5_t4d_e3_factory_handoff.py:295-392`). The disposable fixture registers matching lineage, but not the committed production rights records. |
| Replay / idempotence | **PASS** | Stable task IDs and plan hash; `seed()` gives 10, first deterministic run gives 10, replay gives 0. No provider, reservation, receipt or cost rows were created. |
| Test isolation | **PASS** | All runs used a fresh `git archive` overlay, `PYTHONDONTWRITEBYTECODE=1`, `-B`, `-p no:cacheprovider`, and temporary SQLite/rights state outside the repository. Dirty overlay imports could not affect the run. |
| Side effects | **PASS** | No provider/model/network request, acquisition, spend/reservation, publication, release, watcher/process action or Git mutation occurred. |
| Scope-bundling exclusion | **PARTIAL** | The adapter sets no bundle opportunity and reports `bundle_key=None` (`src/charitygraph/phase5_t4d_e3_factory_handoff.py:350-362`; focused test `:389-428`). The committed `FactoryPlan` groups physical packages by subject/kind/mode, not scope (`src/charitygraph/phase5_factory.py:30-44`); this cohort has one scope per subject, so adversarial same-subject/different-scope isolation was not exercised. The independent trace therefore produced 5 deterministic physical groups for 10 logical children, with no external send. |
| Bridge-owned commit | **PASS** | Exact direct-child identity and three-path allowlist verified. This worker made no commit; this report is the only new worktree path. |

## Material limitations and smallest successor

1. The 28-test fixture is a valid seam test but not an exact production-rights
   replay: it replaces the T3 `CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1`
   rights IDs with newly generated internal-policy records. A current durable
   T3 rights-store/projection fixture is required for full rights acceptance.
2. Add one provider-free regression (under 900 seconds) with two same-subject,
   different-scope deterministic references and the exact T3 rights records;
   assert ten exact current-record resolutions and scope-separated physical
   groups before any provider route is enabled. Do not dispatch or implement
   that successor in this report-only task.

The prior archaeology correctly identified both the missing exact authority
join and the committed scope-grouping caveat (`reports/G4_T4_FACTORY_E3_INTEGRATION_ARCHAEOLOGY_20261031.md:47-73`). Conditional on closing those two evidence boundaries, the adapter core can proceed to the separately governed Gate 4 industrialisation/provider-route and accounting-readiness assessment. No such task is dispatched here.

No raw/private source body, prompt, model response, runtime database, cache,
credential or log was added to Git. No Gate 4 gate was closed and no public
projection or release was changed.
