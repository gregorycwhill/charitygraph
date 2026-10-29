# G4 T3→T2 real-evidence Factory integration

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free  
HEAD: `18668e7b197086ab95e1faf6ba5aa665377164dd`  
Branch: `gate3-cg406-remediation`  
Bridge fence: `v48`

## Result

The retained five-subject/ten-source cohort traversed the clean source binding,
T1B rights preflight, `FactoryPlan`, and `ReferenceFactory` control-plane seam
in disposable local state. No provider or model request was made; real-evidence
execution used only deterministic tasks, so fake send calls were also zero.

This is an engineering evidence report, not product acceptance or gate closure.

## Exact real-evidence identities

- selected recovery manifest: `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`
- emitted manifest schema: `charitygraph.gate4.t3.selected-binding-manifest/v2`
- emitted manifest identity: `622c4d6a27427fee891b7537e67279efe00bdf73dde124c968fd3774759c5acf`
- immutable source-evidence epoch: `v45`
- current bridge execution context: `v48`, exact HEAD above
- rights policy: `CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1` / `1.0.0`
- real cohort: 5 subjects, 10 ACNC rows (one register and one AIS row per subject)
- clean preflight: 10 accepted tasks, 0 diagnostics
- cohort: `cohort:ae3e091a5809aeba5af803e56b612fe1970d24de0d7525904e2a89845bde1460`
- content-hashed cohort plan: `d14c8968035a4ae6ec3b5301fad0eba4a42f0cfcfb44c6f88da261093eb82ef0`
- run: `run:c7bf84ced54e212a22f32f58da0bf8f78a6be5111427bd54358429719b559c19`
- real task IDs: `semtask:06afa41ef233f881925d539a1b3f71a2afe42a2738dd524ab051435a056f8a2e`, `semtask:29025a36f030db1520977e89a3e91c8289092338891829524ff867a847396bc5`, `semtask:2e8bc479d215467418aa3071bc433318b845741a94b75715ff5ae2d79c453503`, `semtask:5399fe12ffd6f8502016bdbbc4745d54310a4c0c7b546b09ab631c677967cb16`, `semtask:53baa5223cad01d0f066fd711b4fef4bad1395f925bbf308dc1ddb6be7b7a9d8`, `semtask:5d5c55cfcf33956560e6c131163f58786e41d631c58f1f48100638839c8ad8cd`, `semtask:7a0a6e3bd945d6f48de4c2944faeb1d0bb0e53b88b67b2e60c5af4beb1faac92`, `semtask:850bcd530a3de099bfa103d497b0fe7edcdb9ff788800306978d8889271dcb46`, `semtask:b219bfa2b9722894be71314fb78ea0b431aa8cb608a7baf7f9cbda15c21870af`, `semtask:da3814faf1d6fa273de412d7cc5b221716291d0fe7c654e4ff4d57e22f3db081`.

Each manifest row retained its exact acquisition receipt, source record,
`srcblob` source hash, derived representation artifact/hash, durable subject and
scope, and content-addressed v29 rights identity. The immutable v45 source
epoch and historical v44/v45 evidence were not rewritten to follow fence v48.

Real execution and replay observed: 10 tasks, 10 deterministic attempts, 0
physical attempts, 0 reservations, 0 receipts, 0 cost entries, AUD `0`, and
0 fake sends. Both executions returned diagnostic SHA
`6aca040b0e3aee69f37acd1d50a981b71e66105050fa69b6648fd39e6809e654`; replay
completed 0 additional tasks.

## Negative and control-mechanics evidence

The new focused test covered five fail-closed cases: missing retained row 2,
mismatched selected-manifest identity, tampered row-2 bytes, explicit row-4
exclusion, and source epoch `v44`. Each produced an empty FactoryPlan and zero
tasks, attempts, reservations, receipts, sends and cost entries. Existing clean
T1B regression tests additionally cover missing rights authority and v29
projection mismatch with zero runtime side effects.

The control mechanics use the existing synthetic T2 fixture only; its replies
are not real evidence and do not become knowledge:

- Standard FakeProvider item-failure isolation: two tasks, two fake sends, one
  synthetic structural failure isolated from one success.
- Batch planning: one planned batch package, zero Batch sends.
- Ambiguous crossing: one fake send, explicit reconciliation, zero resend;
  replay added no send and retained the stable diagnostic.
- Fresh synthetic ledger: model task
  `modeltask:4bd41da86ad2abe400acc5a7b787c24b154dce4c77fc211c5c19e443efc83793`,
  task run `taskrun:be9ecf1fba874d2f93f9c71a8f087c2fec3acd1c33565bb9b32f1c795be5ae30`,
  physical attempt
  `physical:fb35da8de397cbb23642aec10bdd5f7b11cf705d6b4fc6db42ca811a131f38bc`,
  receipt `fake-receipt:99d81e641b31cf613acfac6457a8211337cec6a0caa6afe664a6354d807926af`,
  reservation `reservation:133291d28e270ba78015b4b28ec29062e0ec354959f58375fc2fb21926d3d398`,
  cost keys `actual:reservation:133291d28e270ba78015b4b28ec29062e0ec354959f58375fc2fb21926d3d398` and
  `release:reservation:133291d28e270ba78015b4b28ec29062e0ec354959f58375fc2fb21926d3d398`,
  actual AUD `0.002000`, release AUD `0.008000`, diagnostic
  `85035923579bcd1b5a134569bf4bfa7fe41a38bf8bdce9835639ef546f45eb0f`.

## Verification

Fresh `git archive HEAD` with only the two allowed candidate files overlaid:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts= --basetemp C:\CharityGraph-runtime\g4t3-real-integration-basetemp -ra tests/test_phase5_governed_real_cohort_rehearsal.py tests/test_phase5_governed_source_binding.py tests/test_phase5_governed_rights_preflight.py tests/test_phase5_governed_cohort_rehearsal.py
23 passed, 0 skipped, 0 failed

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts= --basetemp C:\CharityGraph-runtime\g4t3-baseline-integration-basetemp -ra tests/test_phase5_governed_factory_integration.py
4 passed, 0 skipped, 0 failed
```

The 23 focused tests comprise 8 new real-integration tests, 5 source-binding
tests, 4 rights-preflight tests, and 6 accepted T2 rehearsal tests. No network,
source acquisition, provider/model call, spend, production catalogue write,
publication, release, GitHub mutation, watcher, or bridge state change was
performed. Raw evidence remained in the existing private archive or disposable
runtime; no raw source body, prompt, model response, cache, credential, log, or
runtime database was added to Git.

## Omissions, limits, and T4A readiness

The real ten rows are source-bound and locally retained, but provider processing
is still explicitly blocked because an exact provider contract identity/version
is not bound. Public redistribution remains `not_assessed`. The real plan is
deterministic control-plane work, not semantic model output, and does not prove
semantic quality, provider behaviour, production-catalogue reload, publication,
or release readiness.

The next T4A route/policy/spend preflight is ready to enter as a separate
bounded review: the route and exact real-evidence identities are available, but
the preflight is not passed and no provider crossing is ready. It still needs
the exact provider-policy/contract identity and version, per-run AUD reservation
and reconciliation, and any remaining Product Owner/Data-authority checks.

Existing dirty and quarantined paths were preserved. No product acceptance is
claimed; supervisor review remains required.
