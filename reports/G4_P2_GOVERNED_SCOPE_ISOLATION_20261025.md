# CG-G4-P2 — governed scope-isolation tranche

Status: **STOPPED before implementation**. Product acceptance was not attempted.

## Process completion

- Workspace, branch and HEAD matched the request: `C:\CharityGraph-clean\charitygraph`, `gate3-cg406-remediation`, `21bb0e621f2a1c52f19b59f261d71009defa4843`. HEAD tree: `f5851e02afab398326e145a34d142d9de5fe1a58`.
- Required fence `cg-g4-o1b-dormant-state-fence-20261020-v23.json` with SHA-256 `8d58d6acccaa5933075a1492e0974fc6a1080868d78b3e58532a351b5cb5c342` could not be located in the checkout, configured runtime workspace, or local sibling Data repository. The retained P2 archaeology instead records only v22 (`9b3b959f49a72089782f99dc4fe00f69c2f0cb4222c03e5a7ea45e98afa2fe3c`) and an older HEAD. This is the required global fence mismatch.
- Read-only authority review covered `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, the retained P1 archaeology, and the local Data `DOCUMENT_AUTHORITY.md`, current state, roadmap, implementation/test plans, integrated model, source/publication governance, taxonomy governance, coverage/economics policy and semantic-heuristic register.
- Pre-write `git status --porcelain=v1 -uall`: 256 lines (2 tracked modifications, 254 untracked). Git emitted pre-existing permission warnings for `CharityGraph-cleancharitygraphtmppytest-bridge-recovery/` and `CharityGraph-runtimecg405-pytest/`. The four requested implementation/test/report paths were clean before this report.

## Verified P1 evidence

Current `src/charitygraph/phase5_factory.py` (SHA-256 `3560ba44becba1c0b4bde1b22974e99394ba130c0f42cda22bb7c0781ab4f69a`) groups `FactoryPlan.packages()` by subject/opportunity and `physical_packages()` by subject/kind/mode; both omit `scope_id`, matching the independently recorded defect. Current test hashes were unchanged: `tests/test_phase5_factory.py` `822273145bbad3751d71decca2ad7e9ad2da20bf80aed18b487cecfeef4e8795`; `tests/test_phase5_governed_factory_integration.py` `a1f3c3ed4977cbb928dbd73e48c54a25956bfeaea4839e939dd3e85122706621`.

## Product acceptance

Not assessed. Focused pytest commands, reruns, SQLite execution, lineage/cost reconciliation and failure harvesting were intentionally not run after the global stop. Therefore no test counts, failure output or SQLite evidence are claimed for this tranche.

No source acquisition, provider/API call, model call, database/runtime creation, code/test change, semantic heuristic, schema, public contract or publication change was made. No file was staged, committed, reset, checked out, published or dispatched. The pre-existing dirty and untracked paths remain preserved; this report is the only new path.

## Residual limitations

The scope-isolation defect remains open. The requested mechanical fix and regression coverage must wait for an active, verifiable v23 fence matching the supplied hash. Existing P1 limitations recorded by the archaeology report remain outside this stopped task, including artifact-bound rights-policy validation, source-role authority alignment, ephemeral diagnostic missingness, paid billing/FX and model-result governance.

