# Gate 4 T3 independent acceptance review — 2026-10-29

## Verdict

**CONDITIONAL product acceptance.** The direct-child six-path patch is independently
sound for the bounded local-private path: the exact HEAD `61dd0cd1a89ed22118fc81bab89611eb1ddb2428`
produces 10/10 locally eligible rows, with provider transmission blocked and
public redistribution `not_assessed`. Unconditional acceptance is withheld because
the requested fence is `v46`, while committed HEAD emits and documents manifest
fence `v45`; no `v46` anchor exists in the target tree.

## Scope and diff inspection

Grounding read: Builder `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`,
sibling Data `DOCUMENT_AUTHORITY.md`, source/publication governance, North Star
v0.3, and `reports/G4_T3_SOURCE_BINDING_20261029.md`.

The target is the direct child of `c0112cca39de93ee988a3b13112b7d789273e50a`
and changes exactly six paths: the internal-private policy report, governed
rights preflight, governed source binding, rights governance record, and two
focused tests. `source_rights.py`, its legacy test, and `runtime/catalog.py` are
not changed by this commit. The policy identity is exact:
`CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1` / `1.0.0`, covering the seven admitted
source families and only `local_private_retention_and_processing`.

## Independent clean evidence

Tests were run from disposable `git archive` roots for exact HEAD and parent;
the dirty worktree and quarantined rights files were not imported.

- `pytest -q tests/test_phase5_governed_source_binding.py tests/test_phase5_governed_rights_preflight.py` — **8 passed**.
- `pytest -q tests/runtime/test_rights_governance_projection.py` — **6 passed**.
- Combined focused result — **14 passed**.
- `pytest -q tests/runtime/test_rights_governance_record.py` at HEAD — **18 passed, 1 failed**.
- The identical command at clean parent `c0112cc` — **18 passed, 1 failed**.

The one failure is genuinely pre-existing: the legacy `ArtifactRightsDecision`
constructor rejects four newer compatibility fields (`representation_artifact_id`,
`rights_policy_version`, `provider_processing_policy_version`, and
`assessment_authority`). It is outside the six-path diff and does not affect the
10/10 private-local preflight, which passes from clean HEAD without the dirty
`source_rights.py`.

The focused tests prove exact source/receipt/subject-scope/representation and
hash binding; distinct representation identity; no source bodies in the emitted
manifest; exclusion evidence lowering one row to zero; retained-byte tampering
lowering one row to `mismatched` with no substitution; and the seven-family
policy identity. An additional clean-archive fixture mutation produced
`0 mismatched: rights scope belongs to a different subject`.

The v29 projection suite proves numbered migration/checksum, restart and
deterministic reload, safe metadata only, and fail-closed corruption/lifecycle
cases. The binding implementation writes only under its caller-supplied
disposable `work_root` (`catalog.sqlite3`, representations, and rights store),
not a durable production catalogue. No provider/model call, source acquisition,
spend, publication, release, or public redistribution assessment occurred.

## Remaining gap and smallest next task

Resolve the fence discrepancy: Product Owner/bridge authority should confirm
whether this artifact must be re-bound to `v46` or whether `v45` is the intended
fence. The smallest follow-on engineering task is then a narrowly scoped
manifest-fence reconciliation plus deterministic assertion; provider contract,
public redistribution, durable catalogue reload, and legacy compatibility repair
remain separate tasks.

The pre-existing dirty workspace was preserved. No private evidence, raw source,
runtime state, cache, prompt, model response, credential, or log was added to
Git; this report is the only requested workspace output.
