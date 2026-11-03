# G4 Factory integration three-test repair v102

Date: 2026-11-02 (Australia/Sydney)  
Worker: bounded G4-O1C, provider-free local repair

## Result

The three observed failures are repaired in the existing dirty overlay.

Before: the three named tests were `3 failed`; the cited integrated acceptance
run was `51 passed, 3 failed`.

After, the three named tests passed. The final required cache-free focused run
passed **54 tests, 0 failed**:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider \
  --basetemp C:\CharityGraph-runtime\g4-o1c-v102-focused-final2-20261102 \
  tests/test_phase5_t3_source_evidence_binding.py \
  tests/test_phase5_t4d_e3_factory_handoff.py \
  tests/test_phase5_factory.py \
  tests/test_phase5_governed_factory_integration.py
```

An intermediate over-broad Factory runner guard was caught by two existing
scope-neutral/isolation tests and removed; the final rerun is the result above.

## Product repair

- The synthetic positive fixture now persists an exact, artifact-bound,
  representation-hash- and acquisition-lineage-bound provider-rights decision
  derived from its current internal-use authority. Legacy references bind only
  to one unique current exact decision. Missing, conflicting, stale, expired,
  or denied provider authority remains fail-closed; the deterministic fixture
  is explicitly no-send and produced no provider work.
- `FactoryPlan` now exposes physical identities before scope-keyed execution
  grouping. T4D validates that view, so a same-subject physical bundle with
  multiple scopes is blocked before task/catalogue seeding. Valid same-scope
  bundling and existing scope-isolated execution remain unchanged.
- The positive replay retained all 20 `north-star-v0.3` coverage entries, five
  `source_silent` currentness records, ten exact source/representation/rights
  bindings, deterministic plan identity, ten children, zero provider receipts,
  zero reservations and zero cost entries. Mixed-scope cases produced zero
  accepted tasks and zero catalogue tasks.

## Boundary evidence

Only the six allowlisted source/test paths and this report were in scope. No
provider, model, source acquisition, Drive, watcher, bridge, GitHub,
publication, release, manifest or retained-evidence state was changed. The
protected CGDOC1 overlay hashes remain those recorded by the cited acceptance
report. `src/charitygraph/bounded_authority.py` and its dirty allowlist test
were not touched. No commit or follow-on dispatch was performed.
