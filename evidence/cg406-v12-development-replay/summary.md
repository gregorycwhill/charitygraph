# CG406 v1.2 development replay — Sol handoff

Status: first terminal results frozen; provider replay complete. This is a development/regression replay, not a new holdout. No independent-oracle comparison or semantic adjudication is included.

- Branch / commit: `gate3-cg406-remediation` / `62d6be34bec745b9ebfd6abac3eef8f577dcf2f7`.
- Original prepared run: `a4a86dba629e4d91c5477809230cf9f73c1ebfee277b61775e398faf2a7eb6a7`; project-bound execution run: `ab5b5cf62b7475237544e1ccc26047b3c134e5893dc448800c5a7f3b5247d61c`. Normalized semantic request bodies, prompt, schema/contract and evidence IDs are equivalent after masking only project-derived identifiers.
- Requests / first posts / completed responses: 12 / 12 / 12; concurrency 1; retries 0. Resume replayed 12 terminal rows and posted 0.
- Contract/schema: `1.2` / `1.2-packet-proposition-identity`.
- Raw outcomes: `{"ambiguous": 2, "insufficient_evidence": 7, "supported": 3}`. Mechanical validity: `{"invalid": 2, "valid": 10}`. Invalid first responses remain preserved.
- Provider-visible records: 63 across `{"acnc_ais_bundle": 12, "acnc_register": 12, "annual_report": 11, "ato_abr_dgr": 12, "official_website": 9, "pfra": 3, "wikipedia_wikimedia": 4}`.
- v1.2 actual: USD 0.117749 / AUD 0.178983; cumulative v1.1+v1.2 actual: AUD 0.299401; combined hard maximum AUD 0.398063 against AUD 0.50.
- SDC-0019 remains `CANDIDATE_SOURCE_GAP`; Source Universe v1 unchanged.
- Frozen result manifest SHA-256: `f7e27abca01ac8266d6b2e5f81e12802ccc4fbe47c9e27e7206aa25c35c23a43`; terminal ledger SHA-256: `73dbf6163556c898964ad002f430046d9b25cac56e1de62f7c123aee0b321cc2`.
- Packet excludes raw governed source bodies, raw request bodies and credentials. Drive status: local-only; optional upload not attempted.

See `handoff.json` for all 12 model outcomes, proposition states, rationale, evidence-family references, identity/scope context and prior mechanical results. `artifact-inventory.json` hashes every other packet artifact.
