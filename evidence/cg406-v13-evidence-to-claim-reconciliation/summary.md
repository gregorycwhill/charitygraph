# CG406 v1.3 evidence-to-claim reconciliation

This packet records a provider-free repair to the evidence-to-claim interface.
The frozen v1.3 replay remains unchanged: result-manifest self-hash
`04cf508dc11bea243212b14839befc26c085d55dbb8a3b78241f45afd0073ed1`.
No source was acquired, no frozen input/result/oracle was changed, and no
provider request was posted.

The repair promotes the evidence-selection contract to 1.4.  It places each
provider-visible record in a mechanical provenance envelope (source record,
family, role, source-native URL, source artifact, representation identity and
hash). Retained document pages remain marked with their source-native page.
The schema still validates packet-local citations, exact frozen IDs, complete
proposition/requirement coverage, resolved scope/time for strong proposition
assertions, and fail-closed positive conclusions.

It deliberately no longer treats a model-selected `scope_basis` label as a
Python proof of source meaning. That caused a false mechanical rejection of
the Cancer Council bounded service assertion. Semantic entailment remains an
adjudication question; uncited factual requirements, unresolved scope/time,
and unsupported strong conclusions still fail closed. Non-inference demands
now have a distinct `guarded` state: it is a qualified model compliance
acknowledgement, not evidence, and is valid only for an exact frozen
non-inference requirement.

All twelve frozen instances materialize under the new contract without a
provider call. See `candidate-packet-preflight.json`, `case-diagnosis.md`, and
`validation-results.json`.
