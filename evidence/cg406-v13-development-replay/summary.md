# CG406 v1.3 development replay

First terminal responses are frozen before any oracle consultation. This is a development/regression result, not a blind-holdout result or Gate-3 decision.

- Requests completed: 12; provider posts: 12; retries/resends: 0
- Raw outcomes: {'insufficient_evidence': 11, 'supported': 1}
- Mechanical validation: {'valid': 6, 'invalid': 6}
- Actual spend: USD 0.138571 / AUD 0.210634; cumulative development spend: AUD 0.510035 of AUD 1.00
- Tokens: {'input_tokens': 414319, 'output_tokens': 29155, 'total_tokens': 443474}
- Frozen result manifest SHA-256: `04cf508dc11bea243212b14839befc26c085d55dbb8a3b78241f45afd0073ed1`
- Source Universe v1 unchanged; SDC-0019 remains `CANDIDATE_SOURCE_GAP`.

Sol must independently assess semantic entailment. Mechanical validity is not a semantic-quality score.
