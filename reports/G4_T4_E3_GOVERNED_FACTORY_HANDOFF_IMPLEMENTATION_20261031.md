# G4 T4 E3 governed Factory handoff implementation

Date: 2026-10-31 (Australia/Sydney)
Branch/HEAD: `gate3-cg406-remediation` / `90e5f5a443293d93619d8e49f4ed7f78d0087f6a`
Fence supplied: v67 / `fc89c311cc6e0e44fa5fa7d5c61e4bfd16dd9e07cf0f2727b5b9929e88b0e395`

## Result

Implemented one provider-free, versioned E3-to-governed-Factory adapter and
one focused test file. The adapter validates the accepted E3 shape and
side-effect counters, joins the exact ten E3 tuples to the selected T3 rows,
checks E3/T3 subject, scope, source family/role, source record,
representation, rights policy/version and processing/redistribution/binding
carriage, and then delegates authoritative rights and durable lineage checks
to the existing `preflight_governed_rights` seam.

The handoff constants are:

- task identity: `g4_t4_e3_factory_handoff_v1`;
- schema/profile version: `1`;
- difficulty: `deterministic`;
- bundle key: none;
- build ID: `phase5-t4-e3-factory-handoff-v1`;
- route policy: `phase5-t4-e3-deterministic-route-v1`.

Any row-level authority, lineage, current-projection, rights-lifecycle or
route failure rejects the complete cohort and returns diagnostics with zero
Factory tasks. The adapter creates no rights record, source, evidence,
canonical observation, provider route or publication state.

## Verification

Tests ran from an exact `git archive` of the target HEAD with only these new
paths overlaid, avoiding the pre-existing dirty Factory/provider-rights
overlay:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts= tests/test_phase5_t4d_e3_factory_handoff.py -q
28 passed in 111.32s

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts= tests/test_phase5_t4b_source_answer_projection.py tests/test_phase5_t4c_private_answer_brief.py tests/test_phase5_governed_cohort_rehearsal.py -q
41 passed in 12.14s
```

The positive trace observed five subjects, fifteen answer slots, twenty North
Star v0.3 coverage entries, ten source hashes, ten current rights bindings,
ten deterministic logical children, Factory seed/run success for all ten,
and replay with zero new work. The stable disposable-fixture plan hash was
`a6e36aa5adbaafc203a0a0a3fa15ab2985bb790c27eea9d766110da5bdb0bba7`.
Factory replay observed zero provider calls, reservations, receipts or cost
entries; all ten task rows were `succeeded` after the first run.

The negative suite covers missing/duplicate tuples; subject, scope, source,
representation and hash drift; rights policy/version and status drift;
missing, expired, denied and superseded rights; current-projection mismatch;
missing source definition, acquisition receipt or evidence locator; source
and representation lineage mismatch; and attempted non-deterministic/provider
routing under `blocked_provider_contract_not_bound`. Each is cohort-level
zero work with a bounded diagnostic.

## Attestation and limits

The new file identities at attestation were:

| Path | Lines | SHA-256 |
|---|---:|---|
| `src/charitygraph/phase5_t4d_e3_factory_handoff.py` | 407 | `91f71f3b8292a98b47eb852124d6484c7b8c5078b9686c10071fe65d299fa220` |
| `tests/test_phase5_t4d_e3_factory_handoff.py` | 605 | `3bc03724b1279920ee4503086f4e1ad0f04b1b6c54186ef5e414c40f2dd62ae5` |

The adapter is a pure preflight and returns the plan; the test invokes the
existing `ReferenceFactory.seed()` and `run()` against disposable catalog
state. No dirty scope-bundling or rights prototype was used as authority. The
current dirty-worktree `git diff --check` warning is pre-existing in
`reports/G4_T4A4_SOURCE_OWNED_PROVIDER_CONTRACT_REGISTRY_20261029.md`; both
new files have zero trailing-space lines.

No provider/model/network request, acquisition, budget reservation, spend,
publication, release, watcher/process action or GitHub mutation occurred. No
raw/private source body, prompt, model response, runtime database, cache,
credential or log was added to Git. The test reads the already accepted
representation fixture but stores only disposable test state outside the
repository.

No commit, Gate 4 acceptance/closure or follow-on dispatch was performed.
Next bounded independent acceptance is bridge-owned exact-path review and a
direct-child commit of only this report plus the adapter and its test.
