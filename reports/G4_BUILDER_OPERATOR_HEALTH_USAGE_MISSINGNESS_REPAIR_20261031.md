# G4 Builder operator-health usage missingness repair

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free  
Target: `gate3-cg406-remediation@799c85cabfd72cb436d96c54eb477eecc3d0f30c`  
Fence: v80 SHA-256 `b09ca2fde4228cea4c5a2e5d4071c9e1b7cc857696c85e11559fd7c8cea6b3f4`

## Result

**PASS for the bounded deterministic missingness repair.** Malformed or
incomplete usage is now explicitly `missing` or `ambiguous`; token totals are
`null` unless every deduplicated identified receipt has both valid counts.
Genuinely present `input_tokens=0` and `output_tokens=0` remains observed.

## Implementation

- `phase5_operator_health_catalogue.py` now projects only safe usage fields and
  derived coverage markers. Malformed JSON, invalid JSON shapes, missing token
  fields, nulls, negative/non-canonical counts and malformed numeric types are
  retained only as deterministic coverage reasons; raw usage payloads are not
  projected.
- `phase5_operator_health.py` handles direct `usage_json` snapshots as well as
  adapter rows, propagates coverage reasons into structured issues and
  `provider_usage.coverage_reasons`, and never fabricates zero for absent or
  invalid evidence.
- Existing identified-receipt deduplication, conflicting-identity exclusion,
  no-identity replay ambiguity, row-order canonical SHA behaviour, mixed
  subject/scope provenance, read-only SQLite operation and cost boundaries are
  preserved. No cost, provider authority, ledger completeness or send authority
  is inferred.

## Verification

Final cache-free local command, with `PYTHONDONTWRITEBYTECODE=1`,
`-p no:cacheprovider`, and external basetemp under `C:\CharityGraph-runtime`:

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-o1c-final-regressions-20261031 tests/test_phase5_operator_health.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_delivery.py tests/test_phase5_run_diagnostics.py tests/runtime/test_phase5_run_diagnostics_catalog.py tests/test_phase5_standard_transport.py tests/runtime/test_budget_ledger.py
105 passed
```

The focused additions cover malformed JSON, absent fields, null/invalid counts,
valid zero, identical/conflicting identified receipts, no-identity replays,
canonical row-order SHA, payload minimisation and read-only SQLite adapter
behaviour. `git diff --check` is clean for all four edited code/test paths.

Final SHA-256 values before this report was written:

| Path | SHA-256 |
| --- | --- |
| `src/charitygraph/phase5_operator_health.py` | `9c9fc5d70b3815c77673f456afdb12df593a8f45dc290d9736b31b3328d3c568` |
| `src/charitygraph/phase5_operator_health_catalogue.py` | `5fe0f13180fa7cb649586e579d63687b24868c5c27f9f28dc68e4347050dda66` |
| `tests/test_phase5_operator_health.py` | `51b62db7463ec20df025c32ee18a8cdfa421fcea05cb1e0753771dc5e362ca26` |
| `tests/test_phase5_operator_health_catalogue.py` | `8cef65154fe1d53ce2be708f6a17550a0698963ccc299026345098cfe5841ce4` |

## Boundary and residual gaps

This is opportunistic Gate 4 evidence only. The Builder-to-65k state remains
Gate 1 CLOSED, Gate 2 ACTIVE, 12% earned; no Gate 4 closure or progress is
claimed. No provider, network, source acquisition, spend, database migration,
publication, GitHub, Drive, watcher, host or follow-on action occurred. No raw
provider payload, private source material, prompt, model response, credential,
runtime cache or log was added to Git. Live wiring, provider-side exactly-once
effects, project-wide ledger completeness, pricing/FX verification, rights and
release authority remain outside this local repair.

The requested single local-only commit could not be created because the
workspace denied creation of `.git/index.lock`; no files were staged and no
commit was made.
