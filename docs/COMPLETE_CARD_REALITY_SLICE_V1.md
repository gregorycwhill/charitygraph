# Complete-card reality slice v1

Status: bounded experimental slice in progress (2026-09-01).

## Purpose

Test whether the existing governed observation, scope, relationship, evidence,
lineage and persistence primitives can support a sparse but coherent card across
all 20 North Star sections. This is an experiment, not a production guarantee.

## Cohort and evidence

The initial cohort is the existing private Baseline Corpus v1 material for:

- Australian Red Cross Society (ABN 50 169 561 394)
- Life Without Barriers (ABN 15 101 252 171)
- Australian Conservation Foundation Incorporated (ABN 22 007 498 482)

All evidence and representations are reused from the governed private corpus;
no source acquisition is part of this slice. The immutable corpus and source
lineage remain private and unchanged.

## Task design

One coherent high-recall whole-card semantic task per subject uses the existing
v0.2 prompt/schema and exact prompt persistence. Luna is the primary model under
the standing semantic authorisation. Each subject is preflighted before any
evidence-bearing request; output is validated independently for JSON/schema,
cross-field structure and citations. Incomplete output is retained privately as
experimental evidence and is not treated as a valid governed result.

The acceptance frame is the existing 20-section North Star. Sparse sections are
valid outcomes when evidence is insufficient. No mega-card DTO, semantic Python
keyword rules, Terra/Sol call, automatic publication, or new durable primitive is
introduced.

## Preflight and observed bounded run

Using a 12,000-token output ceiling, the conservative projected maximum exposure
for the three packets was approximately USD 0.109 (Red Cross 0.051770; Life
Without Barriers 0.030769; Australian Conservation Foundation 0.026716).

The first bounded execution was attempted once per subject. Red Cross was
rejected by the provider before charge (HTTP 429 request-too-large/TPM; one HTTP
request, USD 0). Life Without Barriers and ACF each returned a paid incomplete
response at the output ceiling (one request each; USD 0.032958 and USD 0.026716,
respectively). Their raw responses, usage and structural diagnostics are retained
in the private runtime under `C:\CharityGraph-runtime\complete-card-slice-v01`.

These results exposed an execution-size limitation for this corpus/ceiling, not a
justification to change the semantic contract. The follow-up sharded run used
eight deterministic shards (Red Cross 5, LWB 2, ACF 1), one physical request per
shard, and a USD 0.114094 projected maximum. Actual charges were USD 0.125979
across eight requests. All eight responses reached the 5,000-token output ceiling
and failed JSON completion; consequently zero shard outputs were eligible for
governed observation persistence or a populated card projection. Raw responses
and per-shard reports remain private. This is evidence that the selected output
ceiling is still too small for the returned high-recall payloads, not evidence of
a missing durable observation primitive. No automatic retry or tuning iteration
was performed.

## Acceptance questions

1. Can one governed observation model support all North Star sections without
   manufacturing unsupported facts?
2. Which sections populate naturally, and which remain sparse because evidence is
   sparse?
3. Are representation gaps durable and source-specific or generic?
4. Do cross-section propositions remain non-duplicative and scope-correct?
5. Can evidence and lineage remain deterministically reachable?
6. What is the semantic cost of a reasonably complete card, and what must be
   solved before a Top-100 full-card build?

Section 16 remains frozen under the prior conclusion: no architecture change now.
