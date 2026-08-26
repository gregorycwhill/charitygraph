# Reality Slice 1 LLM semantic economics spike

This Builder component is private-run infrastructure for the seven-member Reality
Slice 1 development cohort. It is review-only and does not mint public subjects,
change the frozen 40-case benchmark, or produce semantic gold.

## Boundaries

- Only the seven manifest members are permitted; the three holdouts are rejected
  before acquisition, packing, task construction, or provider execution.
- Source navigation is an explicit allow-list. Acquisition stores raw bytes in a
  configured runtime content-addressed store and records URL, retrieval time,
  publisher, content hash, media type and size. Unavailable pages remain
  unacquired; no fallback page or semantic inference is substituted.
- HTML parsing is mechanical (markup/script removal, whitespace normalization,
  stable deduplication and deterministic limits). No lexical relevance,
  keyword, phrase, URL-word or frequency classifier is present.
- Each charity/tier has one typed semantic task. Evidence inputs carry exact
  content and selection hashes; responses must bind every evidence reference.
- Paid execution creates a SQLite reservation before the first provider call and
  records actual usage/cost against that reservation. The reservation is bounded
  by AU$25 and the model is selected by `CHARITYGRAPH_MODEL_SNAPSHOT` or the
  command-line override; no permanent provider/model choice is implied.

## Evidence tiers and review

`lean`, `broad` and `very_broad` vary only the deterministic evidence-volume
limit. The model output is a typed bundle of programs, services, projects,
organisational units, activities, populations, geographies and scoped SDG
alignments. Proposals include evidence references, confidence and competing
interpretation and are emitted to a private human-review queue. The current
adequacy denominator remains the approved Learning for Life reference once;
model proposals never raise it automatically.

Run a dry-run (no provider calls) with:

```text
python -m charitygraph.llm_semantic_economics --runtime-root C:\\CharityGraph-runtime\\reality-slice1-llm-semantic-economics
```

Use `--execute-paid` only after the external provider-egress approval and with a
current pricing/FX configuration. Raw sources, prompts, responses and SQLite
state are private runtime material and must not be committed.