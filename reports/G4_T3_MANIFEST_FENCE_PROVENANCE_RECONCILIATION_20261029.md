# Gate 4 T3 manifest-fence provenance reconciliation — 2026-10-29

## Outcome

The v45 value is legitimate immutable source-binding provenance, not the
current bridge execution fence. Commit `61dd0cd1a89ed22118fc81bab89611eb1ddb2428`
changed the T3 generator from the earlier v44 source-binding output to the
versioned `CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1` / `1.0.0` policy. The
selected source cohort and its identity binding did not change. The active
bridge execution fence for this run is v47 at exact local HEAD
`9e4c36cdc5f7383eca58b81fdc6f23238f7cae17`.

The actual inconsistency was an ambiguous generator seam: the committed
historical JSON remains a v1/v44 artifact with manifest identity
`5c352f6a929508d9ecfe959cb4f8191cf776ef826b03be33f78d8c24bddbd14a`, while
the post-policy generator emitted a generic `fence: v45`. Historical v44
evidence was not rewritten. The generator now emits manifest v2 with separate
`source_evidence_provenance` and `bridge_execution_context` objects.

The v45 epoch is anchored to the unchanged ten-row binding below (the two
rows per subject are the ACNC register and AIS records):

| row | subject | source record | source SHA-256 |
|---:|---|---|---|
| 1 | `subject:02649cdcb42049bb8dedd30f2333e150` | `srcrec:4978c7ff7f9694d9d9d6db9ad871a8048cde5940c6e699a2dd4bd15360bcd28d` | `f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2` |
| 2 | `subject:02649cdcb42049bb8dedd30f2333e150` | `srcrec:554fa9df1414f0096b9035fea5ac5eee7ffb59e46eb767d6306d40d8f326f08a` | `70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b` |
| 3 | `subject:0889b4decb854e71ab4784479ca95c03` | `srcrec:f05f137023221378d486eef96e0c4efe377bb4811ac63fbbbb9aa8f103c251d2` | `8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773` |
| 4 | `subject:0889b4decb854e71ab4784479ca95c03` | `srcrec:045161751edf9950655698373906590d67abf2c35ba33dd804b61b3ac95237f8` | `ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33` |
| 5 | `subject:16fba76fde2242d5870835b18b4e8b8d` | `srcrec:188a391cee048ab2fa7720aeb2c58f5b1e025039ef674ef8a6fd6ea0ab91dd8a` | `ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c` |
| 6 | `subject:16fba76fde2242d5870835b18b4e8b8d` | `srcrec:5cc396995aea23edbab90c78b47101651f3a085f34ab088417dc3e1caa6fda25` | `9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678` |
| 7 | `subject:1823309bdd06417c9928033603cb6e39` | `srcrec:5e1c9ac1b0378a22557a9bf804697719133663123e7f603d76eb41fd2601adf4` | `1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6` |
| 8 | `subject:1823309bdd06417c9928033603cb6e39` | `srcrec:e94d13fec302f9cefc42569b4d191dae5b360565c8c3d8b4e1cded8ece5c0c52` | `692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb` |
| 9 | `subject:1a9ec5de3fc043ff9226fb95a6cae31b` | `srcrec:e6529d39e4cf32248a4792142cdc5e5bfb5cb45c5055180f35662344c737544c` | `a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c` |
| 10 | `subject:1a9ec5de3fc043ff9226fb95a6cae31b` | `srcrec:39443daa20d28eadd1164573c635a5c0aa2d89d3b7a8753b14f8321b90f4aea9` | `b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f` |

Each row retains its exact acquisition receipt and `srcblob:<source SHA>`;
the derived representation is `artifact:<same SHA>` with explicit source-artifact
lineage, and the rights record is content-addressed separately. This is why
changing the execution fence must not rewrite the source binding.

## Exact bounded diff

- `src/charitygraph/phase5_governed_source_binding.py`: preserve immutable
  source provenance as epoch `v45` and producer revision `61dd0cd1…`; require
  explicit bridge fence, branch and HEAD context; emit v2 namespaced fields;
  remove the ambiguous top-level `fence` field.
- `tests/test_phase5_governed_source_binding.py`: pass the active v47 context
  and add `test_bridge_execution_fence_cannot_be_claimed_as_source_provenance_epoch`.
- This report.

`phase5_governed_rights_preflight.py` and its focused test remain unchanged.
No evidence JSON, source-rights prototype, quarantined test, or unrelated dirty
path was changed.

## Provenance and manifest semantics

Before, the generator's `fence` could be read either as source-evidence
provenance or as the bridge's current execution fence. The checked-in v44 JSON
also predates the v45 policy seam and remains historical evidence.

After, the generated manifest records:

- `source_evidence_provenance.epoch = v45`;
- `source_evidence_provenance.producer_revision = 61dd0cd1…`;
- the selected manifest identity
  `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`;
- `bridge_execution_context.bridge_fence = v47`, branch
  `gate3-cg406-remediation`, and exact HEAD above; and
- schema `charitygraph.gate4.t3.selected-binding-manifest/v2`, with no generic
  top-level `fence`.

The five-subject/ten-source identity, source and representation hash binding,
policy identity/version, v29 reload determinism, 10/10 local-private
eligibility, provider fail-closed state, public redistribution `not_assessed`,
zero spend, and zero durable production-catalogue writes remain unchanged.

## Verification

From a disposable `git archive` at exact HEAD `9e4c36c…`, with only the two
modified allowlisted code/test files overlaid:

```text
pytest -q tests/test_phase5_governed_source_binding.py tests/test_phase5_governed_rights_preflight.py
9 passed
```

The new negative regression proves the bridge execution fence is not emitted
as the source provenance epoch. The run used only already-retained local
archive objects and disposable SQLite/rights state; no provider, network,
acquisition, model call, spend, publication, release or GitHub mutation was
performed. Raw/private source bodies were not added to Git.

## Remaining T3/T4 work

Provider processing still requires an independently verified provider-contract
identity/version. Public redistribution remains a separate, unassessed
decision. A durable production-catalogue reload is not authorized. Supervisor
review of this reconciliation remains required; this worker does not claim
final product acceptance or close a gate.
