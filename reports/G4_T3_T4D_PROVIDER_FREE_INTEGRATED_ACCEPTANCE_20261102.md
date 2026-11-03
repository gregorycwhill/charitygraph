# G4 T3→T4D provider-free integrated acceptance

Date: 2026-11-02 (Australia/Sydney)  
Worker: bounded G4-O1C, report-only, provider-free  
Branch/HEAD: `gate3-cg406-remediation` / `b6c9f30c98dd01978c7df3a937cd7e9001023f23`  
Fence: v101, SHA-256 `4c295f75d30c8f987a1f3fe6ffe06ce0e2e55d173db57e8448b6e6c6370124e5`

## Verdict

**PARTIAL.** The committed T3 adapter is ready for provider-free, fail-closed
binding tests. The current T4D E3-to-Factory path is a tracked-dirty candidate,
not committed and not currently integration-ready: the current overlay has
three reproducible failures. The retained five-subject cohort does not cross
T3: it has metadata declarations but no retained source bytes, representations,
receipts, source records or rights records. No real row reaches an eligible
Factory task. Provider-send readiness is **NO-SEND**.

This report is an acceptance observation, not product acceptance, Gate 4
closure, release authority or a provider/source execution authorisation.

## Authority and identity

I read the repository `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`
and `bridge/SUPERVISOR_PROTOCOL.md`, plus the sibling Data repository's
`DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, active North Star v0.3 card,
Phase 5 completion-gate record, source-evidence/publication governance,
LLM-economics policy, implementation plan and test plan. The controlling
principles for this check are: durable subject/scope identity; source,
representation, observation and missingness separation; exact rights and
lineage; 20-section North Star coverage; and no provider crossing without a
current artifact-bound decision.

The branch and HEAD were re-read locally and match the task fence. The v101
raw bytes were not re-read from Drive or reconstructed; their exact-byte
identity and checkout binding are taken from the preceding independent v101
report, as required by this task's no-Drive/no-repeat boundary.

## Seam classification

| Seam | Present state | Observation |
|---|---|---|
| `phase5_t3_source_evidence_binding.py` and its test | **Committed, clean** | Current SHA-256s are `c9be2e4196233bf531b65b92d53e73de736ba920e9018d22ec4689c05a26511e` and `f4ec6ef4f6f896969f725d65fc73494998a2e6f9437d32502926e547d16cf006`. |
| `phase5_t4d_e3_factory_handoff.py` and its test | **Tracked-dirty candidate** | Current SHA-256s are `e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8` and `38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7`; neither is committed at this HEAD. |
| `phase5_factory.py` / `phase5_governed_factory_integration.py` and tests | **Tracked-dirty dependencies** | The current overlay adds scope-keyed physical grouping and provider-rights preflight. These are not clean committed dependencies for accepting T4D. |
| selected five-subject manifest | **Committed metadata-only input** | Present and hash-verified locally; it is not a retained evidence catalogue. |
| retained source/representation/receipt/rights catalogue | **Absent locally** | No real-data crossing can be credited. |

The committed T3 adapter is mechanically bounded: it requires durable subject
and scope, source/receipt lineage, independently hashed representation bytes,
citation, and separate local-retention/provider/public rights decisions. It
does not acquire, discover, interpret prose, call a model or send material.

## Real five-subject / ten-row manifest

The file
`evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json` is 18,597
bytes with SHA-256
`06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4`.
Its declared `manifest_identity_sha256` is
`5c352f6a929508d9ecfe959cb4f8191cf776ef826b03be33f78d8c24bddbd14a` and its
declared `selected_manifest_sha256` is
`41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`.
It has 10 rows, 5 durable-subject IDs, 5 scope IDs, and the two admitted
families `acnc_register` and `acnc_ais_bundle`.

The manifest declares `source_bytes_included: false`, and its summary is a
selection declaration (`bound_rows: 10`, `bound_not_task_eligible_rows: 10`,
`downstream_tasks: 0`), not proof of binding. All ten declared
representation IDs and SHAs equal their corresponding source artifact IDs and
SHAs. That is not an independently retained representation and would be
rejected by T3 as source/representation substitution if the catalogue and
bytes were supplied.

Read-only repository inspection found none of the ten source blobs, ten
representations, ten acquisition receipts, ten source records or ten rights
records by their declared identities. No locator, declared hash, synthetic
fixture or source-silent row was promoted to an observation.

Running the committed adapter against the manifest with an empty retained
catalogue produced:

| Result | Count |
|---|---:|
| `BOUND` | 0 |
| `MISSING` | 10 |
| `BLOCKED` | 0 |
| `missingness` rows | 10 |
| governed Factory references | 0 |
| eligible Factory tasks | 0 |

The ten rows retain five subjects and five scopes, but no durable catalogue
continuity is observed. The reasons include absent durable subjects/scopes,
source records, source definitions, acquisition receipts, representations,
citations and both local/provider rights decisions. This is correctly blocked
missing evidence, not a successful real-data binding.

The manifest declares provider processing
`blocked_provider_contract_not_bound` and public redistribution
`not_assessed`. Those declarations do not supply rights authority.

## Provider-free test exercise

Environment: `PYTHONDONTWRITEBYTECODE=1`, `python -B`,
`pytest -p no:cacheprovider`, with external basetemp
`C:\CharityGraph-runtime\g4-t3-t4d-acceptance-20261102`.

Command:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider \
  --basetemp C:\CharityGraph-runtime\g4-t3-t4d-acceptance-20261102 \
  tests/test_phase5_t3_source_evidence_binding.py \
  tests/test_phase5_t4d_e3_factory_handoff.py \
  tests/test_phase5_factory.py \
  tests/test_phase5_governed_factory_integration.py
```

Result: **51 passed, 3 failed, 0 skipped, 0 errors** in 134.96 seconds.
Collection was T3 9, T4D 32, Factory 8 and governed integration 5 tests.
The committed T3 file was also run alone with the same cache-free settings:
**9 passed in 1.03 seconds**.

The three current failures are:

1. `test_synthetic_authorized_internal_policy_fixture_lowers_to_ten_children_and_replays` — the dirty governed integration now requires durable provider-rights decision references, so the existing synthetic fixture receives `rights_missing` before positive lowering.
2. `test_mixed_scope_physical_package_is_rejected_with_zero_seedable_work` — the current dirty `FactoryPlan` groups physical packages by `scope_id`, so the T4D adapter's mixed-scope package guard sees separate packages and returns no diagnostic.
3. `test_adapter_blocks_mixed_scope_plan_before_any_catalogue_seed` — the same grouping permits two synthetic tasks instead of zero.

Failures 2 and 3 are a current integration defect in the combined dirty
overlay: the scope guard is ineffective against the current Factory grouping.
Failure 1 is a current T4D/dependency fixture-contract mismatch, not evidence
that missing real rights are acceptable. The committed T3 negative tests for
missing bodies, stale/mismatched rights, cross-scope and deterministic replay
pass.

The earlier T4E reconciliation report records that clean disposable archives
of historical revisions passed these three T4D nodes. That is historical
evidence about those clean overlays only; it does not override the three
failures observed in the present dirty worktree.

## Coverage, continuity and hard stops

The candidate T4D validator currently checks the E3 contract for 15 answer
slots, all 20 `north-star-v0.3` coverage entries, five `source_silent`
currentness records, ten source/hash bindings, ten rights tuples and zero
side-effect counters. The real manifest alone does not contain an accepted E3
brief, a current rights store, or representations to feed that validator.

The committed T3 suite verifies deterministic replay and preserves
same-subject/scope identity and rights hard stops in synthetic fixtures. The
current T4D scope-separation assertions fail for the dirty Factory dependency,
so scope-isolated Factory acceptance is not presently proven. No provider
task, reservation, receipt, cost entry, model request, source acquisition or
publication occurred.

## Direct acceptance decisions

1. **Committed T3 adapter readiness: PASS for provider-free fail-closed machinery; PARTIAL for real-data readiness.** Code and 9 focused tests are clean and passing. The real ten rows remain missing/not observed.
2. **Candidate T4D handoff readiness: NO / not accepted.** It is tracked-dirty and its current integrated test set has the three failures above. The candidate's shape/coverage checks are useful, but current positive lowering and scope isolation are not proven in this overlay.
3. **Actual retained real-data crossing: NONE.** Real rows: 0 `BOUND`, 10 `MISSING`/`missingness`; 0 eligible Factory tasks.
4. **Current provider-send readiness: NO-SEND.** No exact current rights records, retained representations or provider contract authority are available, and no provider/model call was authorised or attempted.
5. **Smallest meaningful next bounded tranche:** first reconcile the dirty dependency contract, with exact candidate allowlist:
   `src/charitygraph/phase5_factory.py`,
   `src/charitygraph/phase5_governed_factory_integration.py`,
   `src/charitygraph/phase5_t4d_e3_factory_handoff.py`,
   `tests/test_phase5_factory.py`,
   `tests/test_phase5_governed_factory_integration.py`, and
   `tests/test_phase5_t4d_e3_factory_handoff.py`.
   Its minimum tests are the four focused files above, including the three
   failing nodes, with a clean dependency identity check and zero-task
   assertions for mixed scopes and absent rights. Separately, real-data
   acceptance requires a governed retained-evidence prerequisite: the exact
   ten source bytes, distinct representations, source records, acquisition
   receipts, durable subject/scope records and current artifact-bound rights
   decisions, plus an accepted E3 brief. That prerequisite must be satisfied
   before any real Factory crossing; it does not authorise acquisition or a
   provider request in this report.

## Protection and exclusions

Only this report was written in the repository. No source, test, manifest,
bridge, fence, index, branch/ref, Drive, provider, model, watcher, process,
publication, release or GitHub state was changed. The four protected CGDOC1
overlay files retained their pre-check hashes:

```text
bridge/bridge.py                         91f53253f9357be05d44ded0727391083e4b2a8626e21064c744fed5d0a26168
bridge/g4_doc_export_ingress.py          bfd914ded7d52bfd1d97035dd8c4d5ae393fbcd981ef9a7a38f60c75cc6a0b4d
tests/test_bridge_cutover.py              161c10363a510503d77e9e78660a09af542b031faac798b9098fb2fa99cf5ce0
tests/test_bridge_doc_export_ingress.py   0665acd8d9c648e8ed36f44fd000031e8e83207104b723465117ac6522e83462
```

Targeted `git diff --check` for the inspected T3/T4D/Factory/integration seams
passed. Git status remained dirty with pre-existing permission warnings for
two disposable directories; no cleanup or reconciliation was attempted.
