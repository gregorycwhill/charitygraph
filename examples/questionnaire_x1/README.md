# X1 private questionnaire interface

This is a provider-free experiment, not a public data format or a canonical
observation. The two instruments contain only the Product Owner's experimental
questions; v0.2 changes the wording of one question. The source pack and all
answers produced by `demo.py` are synthetic, including its zero expenditure
and probabilities. No source bytes are embedded in the pack.

Run from the repository root in the managed Python environment:

```powershell
$env:PYTHONPATH = 'src'
python examples/questionnaire_x1/demo.py "$env:TEMP\charitygraph-x1-demo"
python -m pytest tests/test_questionnaire_x1.py -p no:cacheprovider
```

The output directory contains separate prepared requests and answer sets for
each questionnaire version against the same pack. They are private experimental
records, not public projections. Input objects forbid source text and output
objects contain no source text, but provenance references themselves may be
private; this interface is not a public export or a publication allowlist.

`SourcePack` references previously prepared representations with their snapshot,
content hash, family, period, provenance and availability. A program has an
explicit source-scoped identifier; names alone do not establish identity.
Unavailable program inventories stay explicit. The sample uses fixtures because
the inspected E5A regulator files contain ACNC program and charity identifiers,
but this slice has not verified durable CharityGraph subject bindings and
applicable representation decisions for two end-to-end real packs. An AIS
submission UUID is not a charity UUID, and a draft E5A processing decision is
not provider approval. Do not silently substitute either.

The questionnaire is external data. Choice answers must use declared options;
ordinal answers remain labels. Numeric results carry reporting period, source,
currency and reported/calculated basis. Missing, failure and not-applicable
remain distinct, as do source-native and model/fixture methods. Native
probabilities and confidence are copied only if supplied, never calculated.
All results are marked experimental and unpromoted. Explicit dependency fields
are rejected; independent wording still requires questionnaire author review.

## Machinery disposition and X2 seam

* Current/reusable: `sources/acnc.py` and existing ACNC source records for
  acquisition; `document_representation.py` and existing persisted representations
  for preparation; existing source binding and rights machinery for identity and
  eligibility. X1 calls none of these at answer time.
* Reusable outside the runner: the prior Decisions experiment used the existing
  OpenAI SDK `decisions.create` and retained native choice/probability results.
  `adapt_decisions_choice` accepts that native choice shape after the caller has
  verified the source, questionnaire-version and subject binding. No live adapter,
  credential, request, budget or provider transport is implemented in X1.
* Superseded for this purpose: E5/E6 instruments, routing and forensic scoring;
  historical outputs remain evidence, not this instrument's answers.
* New in X1: strict pack/questionnaire contracts, independent scoped request
  expansion, bounded choice batching, captured-response normalization and private
  answer validation. Numeric extraction is a separate future specialist input.

The smallest X2 is to bind one governed, eligible real charity snapshot and its
program IDs to this pack, accept a Product-reviewed questionnaire, then connect
the existing Decisions client through a separately verified mapping, budget
reservation, processing decisions and provider-data controls. Establish source
reference resolution and content-hash validation before live transmission. X1
does not grant permission to run a provider call or promote an answer.
