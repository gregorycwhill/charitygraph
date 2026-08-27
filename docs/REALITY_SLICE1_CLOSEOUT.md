# Reality Slice 1 closeout

Status: frozen diagnostic complete; no further Reality Slice semantic tuning is authorised.

## Product conclusions

The holdout diagnostic is qualitative evidence, not an unbiased precision/recall estimate: no pre-output holdout gold labels existed. Historical experiment results and provenance remain unchanged.

- Stage-A model-assisted semantic extraction generalised materially better than the original development calibration suggested.
- Landscape Recovery Foundation declined to promote several navigation/project headings without sufficient delivery evidence.
- Indigenous Literacy Foundation distinguished substantive programs from a recurring campaign/event and from fundraising or participation mechanisms.
- Life Without Barriers returned stable service areas while declining to manufacture named programs, intervention models, geographies or outcomes unsupported by evidence.
- Development over-fragmentation therefore does not justify a mandatory two-stage normalisation pipeline for every charity.
- SDG alignment and private CLASSIE 4.2 inference transferred adequately for this experiment; no further tuning is authorised here.

The production architecture is:

```text
evidence
  -> Stage-A model-assisted semantic extraction
  -> validated evidence-bound candidate observations
  -> governed promotion/review
```

A second model-assisted normalisation/adjudication task is optional and triggered only where identity or scope needs it (merge/split suspicion, ambiguous boundaries, conflicting evidence, crowded portfolios or consequential scope ambiguity). Stage B is not a mandatory production stage.

## Exactly-once execution incident

Three provider requests were authorised and five were sent. Indigenous Literacy Foundation and Life Without Barriers were duplicated after a first harness process remained active after its visible output stream stopped. Duplicate outputs were excluded from interpretation. Duplicate actual spend was AU$0.064012; total recorded holdout provider spend was AU$0.153991. This is classified as an exactly-once execution/authorization-consumption defect, not a semantic-model defect.

The operational catalogue now provides durable, cross-process authorization slots keyed by authorization scope, subject, task family and material hash. Claims are transactional and fail closed while active, completed, terminal-failed or abandoned. Ambiguous abandoned slots require explicit review before reset; provider accounting remains independent.

## PR #15 harvest inventory (read-only)

The following areas are inventory only; they are not ported by this closeout.

### KEEP / port to clean production PR

- `src/charitygraph/runtime/catalog.py`, `src/charitygraph/runtime/migrations.py`: lifecycle/attempt ledger, cost-before-validation accounting and exactly-once authorization slots. Dependency: SQLite runtime; destination PR 1.
- `src/charitygraph/contracts/tasks.py`, `src/charitygraph/openai_client.py`: generic model-task contracts and bounded structured transport. Dependencies: contract/runtime callers; destination PR 2.
- Evidence-bound validation portions of `src/charitygraph/llm_semantic_economics.py`: strict request schemas, evidence references and provider-cost recording. Destination PR 2.
- `src/charitygraph/private_classie.py`, `src/charitygraph/contracts/taxonomy.py`, `src/charitygraph/phase1.py`, and `src/charitygraph/scoped_benchmark_v2.py` classification/publication controls where independently mergeable. Destination PR 3.

### KEEP AS EXPERIMENTAL / research implementation

- `src/charitygraph/reality_slice1.py` and the cohort-specific portions of `src/charitygraph/llm_semantic_economics.py`: seven-charity source plans, development calibration gold, tier economics, holdout harness and experiment lifecycle.
- `src/charitygraph/program_subject_normalisation.py`: Stage-B split/merge machinery and its scorer; retain as optional research capability pending a separate product decision.
- `tests/test_llm_semantic_economics.py`, `tests/test_program_subject_normalisation.py`, `tests/test_classification_layers.py` and related experiment fixtures: preserve reproducibility, do not treat as production cohort logic.

### DISCARD / superseded

- Earlier lexical or mandatory-normalisation repairs superseded by the frozen Stage-A findings; no current production path should reintroduce them.
- Development/holdout-specific gold labels and source lists must not become permanent production logic.

## Proposed small production sequence

1. **PR 1 ? execution safety:** durable authorization slots, lifecycle/attempt hardening and provider-cost accounting.
2. **PR 2 ? semantic task primitives:** generic model-task registration, evidence-bound candidate observations, strict schemas and validation.
3. **PR 3 ? classification controls:** private external-taxonomy loading, assignment provenance and publication controls, if independently mergeable.
4. **PR 4 ? bounded native vertical slice:** one CharityGraph-native extraction path with governed review and explicit publication allowlist.

Optional Stage-B adjudication may be added later for cases that actually require identity/scope resolution. The seven development and three holdout charities are not permanent production logic.

## Preservation

PR #15 remains open and unmerged. Its run histories, diagnostic packets, cost records, failed executions and duplicate-call incident remain private archaeological evidence and are not rewritten by this document.
