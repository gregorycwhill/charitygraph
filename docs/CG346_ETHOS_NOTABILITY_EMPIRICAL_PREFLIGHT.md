# CG346 Ethos / Notability empirical pilot: stopped preflight

**Run:** `CG-ETHOS-NOTABILITY-EMPIRICAL-PILOT-346-TERRA`  
**Status:** `STOPPED_BEFORE_ACQUISITION_AND_PROVIDER_EXTRACTION`  
**Date:** 2026-10-08  
**Scope:** private experiment only; no canonical or public knowledge was created.

## Frozen inputs inspected

| Item | Exact state |
|---|---|
| Builder worktree | `C:\\Users\\grego\\OneDrive\\Documents\\GitHub\\CharityGraph\\cg346-empirical-builder` detached at `f52e4b894b05526eeb940f24f22c186289b356d8` |
| Data worktree | `C:\\Users\\grego\\OneDrive\\Documents\\GitHub\\CharityGraph\\cg346-empirical-data` detached at `93a2621e9e1feb492a2f2e00767e1e4a396962b6` |
| 344 corpus | `cg-reality-corpus-ethos-notability-v1` v1.0.0, SHA-256 `f49735791652d3a65ab627138662653c76a615496f0f154a325bf8729d662c1b` |
| 344 result | 14/14 contract matches: 3 retained-evidence real controls and 11 synthetic fixtures; positive semantic subfamilies remain `CERTIFIED_WITH_REVIEW` |
| 345 handoff | `docs/CG345_ETHOS_NOTABILITY_FACTORY_HANDOFF.md` |

## Stop condition met

This pilot must exercise the actual extraction/model-routing configuration and
then send each valid §15/§17 candidate through the `345` S0 route and private
v0.3 projection. The frozen implementation has no such end-to-end semantic
interface:

1. The only live provider-backed extraction route found is Compact Knowledge
   v0.1/v0.2 (`scripts/run_compact_knowledge_slice_v01.py` and
   `scripts/run_compact_e2e_v02.py`). It calls `gpt-5.6-luna` via
   `openai_client.responses_create`, using a generic schema that expressly
   instructs the model not to use North-Star sections.
2. Its actual persistence adapter (`compact_knowledge_persistence.adapt_compact_v02`)
   produces generic `Observation` records with predicate `compact_statement`.
   It has no output for `EthosObservation` or `NotableEvent`, and no mapping
   from a generic proposition to §15/§17 semantic roles/event families.
3. The `345` adapters (`ethos_history.py`) only validate and project an
   already-typed `EthosObservation` or `NotableEvent`; they do not consume a
   frozen evidence packet or a Compact Knowledge result. The S0 router
   (`s0_ethos_notability_routing.py`) routes metadata only.
4. The Factory runtime (`phase5_factory.py`) is explicitly provider-free and
   its sole provider is `RehearsalFakeProvider`, which deliberately exposes no
   knowledge-producing output.

Creating a bespoke §15/§17 extraction prompt or a Python/LLM semantic mapper
now would be a material new extraction path and product decision. It would
also make a claimed `345` traversal false. Accordingly, this is the explicit
stop condition: **the existing extraction interfaces cannot consume frozen
evidence through to a §15/§17 candidate without a material product decision.**

## What was not done

No real organisations were selected, no sources were fetched, and no corpus
or reference adjudication was frozen. This avoids creating a cohort whose
candidate phase could not validly run, and avoids post-freeze source work.

No provider request was issued (despite a credential being available), so:

- provider calls: `0`; cost: `US$0.00`;
- raw candidate outputs/valid candidates: `0/0`;
- S0 routing/projection observations: `0/0`;
- discrepancies/failure-ledger entries: `0/0`;
- challenge cases/blind controls: `0/0`;
- no empirical subfamily status is evaluable.

This is not a finding about real-world extraction quality, a failure of the
344/345 contracts, or a change to any certification status.

## Regression check

With `TEMP` and `TMP` set to
`C:\\CharityGraph-runtime\\cg346-empirical-preflight`:

```text
python -m pytest -q tests/contracts/test_s0_ethos_notability_integration.py tests/contracts/test_ethos_history_v1.py tests/contracts/test_ethos_notability_certification_344.py tests/contracts/test_reality_corpus_ethos_notability_v1.py
55 passed (exit 0)
```

## Recommended successor tranche

Before a 15-organisation real-world pilot, approve and implement an
instrumented, versioned domain extraction contract that consumes immutable
packet-local evidence and yields raw, schema-validated §15/§17 candidates.
It needs packet/evidence IDs, prompt and contract hashes, model/provider and
token/cost receipts, structural/grounding validation, and an explicit handoff
to `route_task_metadata` plus the two private v0.3 adapters. It must preserve
the current review/disabled gates; no automatic promotion should be added.

Only after that interface is frozen should a cohort be selected, sources
acquired, the corpus and independent reference adjudication frozen, and the
US$1.50 capped candidate run started.
