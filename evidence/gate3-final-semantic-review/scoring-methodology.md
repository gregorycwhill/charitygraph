# Gate 3 final semantic review methodology

This dossier compares the immutable v1.5.1 execution with certified independent oracle v2. The case join is by exact `question_id` / `frozen_question_id`, never row order. Subject IDs and exact frozen question text are compared directly. Builder parameter maps are normalized from the oracle's slot/value list and compared by exact slot and exact value. The 36 unique `oracle_intake_record_id` values are retained as case identities.

The frozen preregistered rubric at `evidence/gate3-fresh-semantic-holdout-preparation/preregistered-scoring-rubric.md` is the scoring authority. In particular, “not established” is not negation; bounded partial answers remain partial; output validity is separate from semantic correctness; and a source-coverage limitation is not relabelled as a model semantic failure.

Case-level categories in `case-assessments.json` are mutually exclusive:

- `CORRECT`: conclusion and material scope/time treatment align with the oracle, including an appropriately bounded `NOT_ESTABLISHED` result.
- `PARTIALLY_CORRECT`: some useful, evidence-bounded information or an honest evidence limitation is given, but the reference conclusion or material demand is not fully covered. This includes positive oracle material unavailable in the Builder packet.
- `UNSUPPORTED`: the response makes a stronger conclusion than the independent reference supports. The one such case has source-cited facts but an overstrong outcome state; it is not a fabricated factual value.
- `INCORRECT`: materially false or wrong-scope assertions.
- `UNSCORABLE`: the semantic content cannot be assessed.

Structural validity, evidence-ID membership, and hallucination are reported independently from those categories. The invalid response is still semantically scored from its retained raw output. A “material hallucination” means a material factual assertion not supported by the exact packet; a state-strength overreach is separately identified.

Builder's admitted evidence was limited to `acnc_register` and `acnc_ais_bundle` (36 records from each family). The oracle's source-provenance ledger and certification are used to identify positive facts outside that permitted Builder corpus; those facts are classified as coverage limitations, not as Builder hallucinations. No oracle answer or source body was sent to Builder or used to change a generation artifact.

The review does not introduce a numerical acceptance threshold. The closure recommendation is a qualitative judgement against the frozen rubric and stated North Star / Gate 3 purpose, with the sample and source restrictions stated explicitly.
