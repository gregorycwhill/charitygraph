# G4 T4E recovery-authority validator

Date: 2026-10-31 (Australia/Sydney)
Worker: bounded G4-O1C, dormant pure validator, provider-free

## Result

Implemented only the three requested new paths. The validator returns a
serialisable `DRY_RUN_ELIGIBLE` or `BLOCKED` plan and is not connected to the
bridge, watcher, ingress, Git, Drive, providers, source acquisition, spending,
publication, or repository transactions.

The independent caller must provide immutable pins separately from the
candidate envelope. Validation binds repository `charitygraph`, the supplied
workspace, branch `gate3-cg406-remediation`, HEAD
`070c96a854e1a2ba8e674f21d06f3df602d86006`, fence `v71` /
`b7eee29b72031f3b3ca501c381921ac28a139304a5782d5709b02159e7bab689`, source
instruction/result identities, reconciliation report/result identities, the
manifest/source-anchor hashes, and the exact two-file hash allowlist:

- `src/charitygraph/phase5_t4d_e3_factory_handoff.py` —
  `e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8`
- `tests/test_phase5_t4d_e3_factory_handoff.py` —
  `38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7`

The timed-out source result is accepted only as terminal evidence
(`CODEX_EXECUTION_TIMEOUT`, zero provider/acquisition/publication activity,
semantic work not performed). It cannot become success. A separate
`COMPLETED`, `verified`, `independent` reconciliation record and independently
pinned 32-focused / 50-regression test attestations are required. Dirty,
staged, untracked or ignored target paths, altered/duplicate/extra paths,
missing provenance, fake results, and self-asserted candidate hashes fail
closed.

The returned plan is dormant dry-run intent only. T3 remains blocked; no
provider promotion, rights promotion, ordinary tracked-dirty adoption, bridge
ingress, or authority grant is represented. No raw source bodies are accepted
or returned. The validator provides integrity comparison, not cryptographic
signature verification or independent-origin proof; the later supervisor/
bridge remains responsible for establishing the pins and their provenance.

## Verification

Focused disposable-fixture tests: **21 passed**. They cover the positive shape,
canonical serialisation, missing independent provenance, identity/fence/source
result mismatches, reconciliation separation, exact allowlist and hashes,
duplicate/extra paths, dirty target states, missing test proof, scope limits,
self-hash substitution, and invalid trusted pins. Tests perform no Git,
provider, Drive, network, watcher, or process-management action.

Private evidence, raw sources, prompts, model responses, credentials, caches,
runtime state and logs were not added. No existing path was changed.
