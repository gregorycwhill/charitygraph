# CG-G4-P2 — Sol local P1 archaeology

Status: **archaeology complete; no implementation authorised; Gate 4 remains open**

## Authority and baseline

- Workspace: `C:\CharityGraph-clean\charitygraph` (verified).
- Branch / HEAD: `gate3-cg406-remediation` / `c3a59b65815a1a8c7dda4492ac83ec91dc321347` (verified).
- HEAD tree: `87be7fde4f49156113a9089f897b11f063456364`.
- Active fence: `cg-g4-o1b-dormant-state-fence-20261020-v22.json`; SHA-256 `9b3b959f49a72089782f99dc4fe00f69c2f0cb4222c03e5a7ea45e98afa2fe3c` (verified read-only). Its workspace, branch and HEAD match; it records zero provider calls, no GitHub mutation, no publication and no gate closure.
- Pre-write `git status --porcelain=v1 -uall`: 255 lines = 2 tracked modifications and 253 untracked paths. Top-level counts: `docs/` 2, `evidence/` 239, `reports/` 14. The tracked paths were `docs/G4_O1B_SUPERVISORY_SUBMISSION.md` and `docs/G4_O1C_SUPERVISORY_SUBMISSION.md`; all baseline paths were preserved. The required report did not exist at the first check.

The local authority read was completed for `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, and the requested sibling Data documents under `C:\CharityGraph-clean\charitygraph-data\` (including `DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, `ROADMAP.md`, `IMPLEMENTATION_PLAN.md`, `TEST_PLAN.md`, the integrated model, source/publication governance, taxonomy governance, coverage/economics policy and semantic-heuristic register).

## P1 seam and provenance

P1 is current and reusable at HEAD. Commit `93bc8531ed7a2f93678313d2c5a6ec20d5c7e028` (`Integrate governed references with Phase 5 Factory`), parent `c239db1f30d87083bba22e4ff473fe4efea09994`, is an ancestor of HEAD. No P1 file changed after that commit. The earlier reports `reports/G4_P1_GOVERNED_FACTORY_INTEGRATION_20261025.md` and `_RETRY.md` are historical archaeology, not new authority or a second implementation path.

Current HEAD blob / working-tree SHA-256 pairs for the P1 seam are:

| Path | Git blob | SHA-256 |
|---|---|---|
| `src/charitygraph/phase5_preflight.py` | `acaadc58c932be045e369aa642b67f8c54f4debb` | `ee91b164e4ce658eda70d29134ebfaaa2d3e9636ca1754921d242b8bbcd15516` |
| `src/charitygraph/phase5_factory.py` | `d89c937c544f4939d2eb06b3a8aa47161275192a` | `3560ba44becba1c0b4bde1b22974e99394ba130c0f42cda22bb7c0781ab4f69a` |
| `src/charitygraph/phase5_governed_factory_integration.py` | `b2a381ede6e3958ac9400292e16f85b0862359bc` | `8bedb82daaa6b53cb29ee8e671930844866e7252a5b767889e42926b298e4d9d` |
| `tests/test_phase5_governed_factory_integration.py` | `9cbedec2d601c91a166950c6746660847d179744` | `a1f3c3ed4977cbb928dbd73e48c54a25956bfeaea4839e939dd3e85122706621` |

`phase5_preflight.py` supplies typed source-coverage/missingness states, exact hash-verified retained-material resolution, deterministic logical planning and interruption-safety representation. `phase5_governed_factory_integration.py` validates already-durable subject/scope, source definition, acquisition receipt, source record, evidence locator, representation hash/lineage and supplied rights fields, then lowers only available material to a `FactoryPlan`. `phase5_factory.py` preserves logical task identity, same-subject packaging, task leases, physical attempt/send/receipt boundaries, child-level outcomes and synthetic accounting. `runtime/catalog.py` is the operational SQLite implementation for these records; it is not the durable evidence authority.

## Verified provider-free trace

The retained synthetic fixture in `tests/test_phase5_governed_factory_integration.py` builds source definition → raw content-addressed artifact → derived representation with `derived_from` lineage → available acquisition receipt → subject-bound source record → evidence locator → `GovernedReference`. The corrected standalone diagnostic, using a temporary directory under `C:\CharityGraph-runtime`, observed:

`governed-ref:1` / `subject:111…111` / `scope:111…111` → accepted `1` → logical task `semtask:b9ddc66e2c005d03668d5dcb7a641abb2e1801405b4e1fbb6912179abcf82c35` → model task `modeltask:64d3115bf24875d85ec0fba48f13e8f6b7d89f71028c583055b4f6beb69f9628` → physical attempt `physical:c4d3239c7a0b040386b8b070999b28cd1b6c6f5c513a719166a7dd8bf6f5d3e5` → receipt `fake-receipt:e83f1dfb64c39760bc7ef304e3f7156e6784a10644ad45f9d417ff8c273c683e`.

The representation artifact’s catalogued lineage points to the raw `srcblob:` artifact. The durable task ended `succeeded`, physical state `validated`, first run completed `1`, rerun completed `0`; synthetic budget position was actual `AUD 0.002000`, released reserve `AUD 0.008000`, outstanding reserve `AUD 0.000000`, breach `False`. The integration test independently verifies the same lifecycle and evidence binding; the report’s prose is not being treated as test evidence.

## Capability classification

- **Multi-reference:** the preflight accepts an iterable, rejects duplicate reference identities, carries multiple source/receipt/record/locator/representation IDs, and creates independent logical tasks. This is test-verified. A single reference still has one source family/definition and one rights role; it is not a general multi-source authority resolver.
- **Multi-subject/scope:** subject binding and scope ownership are validated; different subjects remain separate and independent-failure testing passes. Scope is carried on the task, but `FactoryPlan.packages()` and `physical_packages()` group by subject/opportunity/mode and omit `scope_id`. A read-only probe with one subject, two scopes and the same opportunity produced one physical package containing both tasks. The physical-attempt record likewise stores subject but not scope. This is an independently harvestable defect.
- **Independent failures:** the integration test proves one subject can fail structurally while another succeeds and is not repeated. Child outcomes are terminalised independently, but same-subject multi-scope isolation lacks a regression test.
- **Rights and source roles:** source family, source definition, acquisition receipt, source record, representation and `rights_role` are carried into the typed task. `rights_policy_id` is optional and only copied; P1 does not resolve a durable artifact-bound provider-processing decision, verify source-role compatibility, or fail closed on missing rights policy. No provider work is authorised by this archaeology.
- **Explicit missingness:** `missing`, `blocked`, `structurally_invalid`, `unrecoverable`, `mismatched`, `not_applicable`, `not_processed` and `retrieval_failed` produce differentiated diagnostics and no Factory task; preflight/source coverage tests pass. These diagnostics are in-memory preflight results, not canonical coverage observations. SQLite task/attempt state is operational and rebuildable; source bytes and governed evidence remain separate content-addressed material.
- **Restart/idempotence:** task registration, receipt persistence, cost entries and releases are keyed/idempotent; ambiguous send remains held at `send_started` and requires explicit receipt reconciliation without resend. The tested rerun is a no-op. Paid-provider billing reconciliation and recovery across every crash point are not demonstrated by this provider-free slice.
- **Cost:** reservation → actual → release is exercised with synthetic tariffs, including runtime overrun, unreserved actual and release/idempotence tests. It proves ledger mechanics, not real pricing, FX, provider billing or paid execution.

## Focused diagnostics

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p2-pytest-focused tests/test_phase5_preflight.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py
27 passed in 7.26s

PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p2-pytest-runtime tests/runtime/test_source_evidence.py tests/runtime/test_budget_ledger.py
8 passed in 2.90s
```

The first two standalone trace attempts failed only because the ad hoc interpreter lacked the repository `src` path; the corrected run set `PYTHONPATH=...\src` and passed. No pytest cache, bytecode, fixture or runtime DB was created in the checkout.

## Smallest justified follow-on reliability tranche

Candidate allowlist, subject to separate approval after this report:

- `src/charitygraph/phase5_factory.py`: make package compatibility include `scope_id` so physical work cannot cross scopes.
- `tests/test_phase5_factory.py`: same-subject/different-scope packaging regression; retain the existing idempotence, ambiguity and cost tests.
- `tests/test_phase5_governed_factory_integration.py`: one provider-free accepted-reference case with the same subject and distinct scopes, proving no physical cross-scope package.
- this report only: `reports/G4_P2_SOL_P1_ARCHAEOLOGY_20261025.md`.

Acceptance: same-scope compatible logical tasks may bundle; different scopes never share a physical package/attempt; different subjects never share one; one failed unit cannot repeat a successful unit; ambiguous send cannot resend; reservation/actual/release remains balanced and idempotent; all focused provider-free tests pass with basetemp outside the checkout. Do not expand this tranche into rights-policy design, catalog migration, source acquisition, semantic execution or publication.

Residual risks are the unvalidated artifact-bound rights-policy gate, source-role authority alignment, ephemeral diagnostic missingness, physical scope representation, real cohort breadth, paid billing/FX and model-result governance. Stop globally if the fence/workspace/HEAD changes, rights or subject/scope authority is unresolved, cost cannot reconcile, a public contract/release would change, or a proposed diff teaches Python English; no semantic-heuristic approval is implicated by the mechanical candidate above.

## Attestation

Only this required report was written. No product code, test, fixture, runtime database, cache, source body, prompt, model response, credential, log, bridge/watchers/process, Drive setting, provider/API, external source, Git index, commit, GitHub, release, publication, merge, gate closure or follow-on task was touched. This is local archaeology evidence only and does not authorise execution or Gate 4 closure.
