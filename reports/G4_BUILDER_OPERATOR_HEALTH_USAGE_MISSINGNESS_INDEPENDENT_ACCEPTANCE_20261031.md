# G4 Builder operator-health usage/missingness independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Decision: **PARTIAL acceptance of the bounded local capability; Gate 4 remains open.**

This was an independent, report-only, provider-free review of the exact
bridge-owned direct child `gate3-cg406-remediation@c9e349f17b28eab34fc6c57aad9082130d6456d7`,
parent `799c85cabfd72cb436d96c54eb477eecc3d0f30c`. The local v81 instruction
records immutable fence SHA-256
`6fe67a0a0dca949b92d81f028d9615b9721e9a777f57e9792b082cbbc7161879`.
No code, source, provider, bridge, GitHub, publication, release or gate state
was changed.

## Authority and commit boundary

Read: `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, North Star v0.3,
the sibling Data `DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, source/evidence,
coverage/cost, integrated-model, implementation and test authorities, the
canonical `BUILDER_TO_65K_PLAN.md`, the prior v80 catalogue acceptance, and the
v80 usage-missingness instruction, terminal result and repair report. The local
Data authority confirms that missingness is not absence, evidence/observations
remain distinct from cost authority, and Python owns deterministic validation.

`git show` verifies exactly these five committed paths:

1. `src/charitygraph/phase5_operator_health.py`
2. `src/charitygraph/phase5_operator_health_catalogue.py`
3. `tests/test_phase5_operator_health.py`
4. `tests/test_phase5_operator_health_catalogue.py`
5. `reports/G4_BUILDER_OPERATOR_HEALTH_USAGE_MISSINGNESS_REPAIR_20261031.md`

The existing dirty Factory/T4A/T4E, evidence, reports and unrelated paths were
preserved. The target code/test paths matched `HEAD` before this report was
created; the target code/test paths are clean under `git diff --check`, with no
dirty-baseline absorption. The parent-to-HEAD diff check reports trailing
whitespace already present in the committed repair report metadata at lines
3-5; this acceptance did not edit that report. A whole-worktree check also
reports one pre-existing unrelated trailing-whitespace line at
`reports/G4_T4A4_SOURCE_OWNED_PROVIDER_CONTRACT_REGISTRY_20261029.md:4` (plus
harmless line-ending warnings); that path was not edited.

SHA-256 of the four target code/test files and the committed repair report:

| Path | SHA-256 |
|---|---|
| `phase5_operator_health.py` | `9c9fc5d70b3815c77673f456afdb12df593a8f45dc290d9736b31b3328d3c568` |
| `phase5_operator_health_catalogue.py` | `5fe0f13180fa7cb649586e579d63687b24868c5c27f9f28dc68e4347050dda66` |
| `test_phase5_operator_health.py` | `51b62db7463ec20df025c32ee18a8cdfa421fcea05cb1e0753771dc5e362ca26` |
| `test_phase5_operator_health_catalogue.py` | `8cef65154fe1d53ce2be708f6a17550a0698963ccc299026345098cfe5841ce4` |
| `G4_BUILDER_OPERATOR_HEALTH_USAGE_MISSINGNESS_REPAIR_20261031.md` | `5bbc2ba15a095503f1643e2adb75d3e728de2f99aa43684cf7af479f8bb0936d` |

## Verification

Cache-free isolated command, with external basetemp under
`C:\CharityGraph-runtime` and `PYTHONDONTWRITEBYTECODE=1`:

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-o1c-independent-acceptance-20261031b tests/test_phase5_operator_health.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_delivery.py tests/test_phase5_run_diagnostics.py tests/runtime/test_phase5_run_diagnostics_catalog.py tests/test_phase5_standard_transport.py tests/runtime/test_budget_ledger.py
105 passed in 10.37s
```

The independent direct-snapshot probe and persisted SQLite probe also passed.
Results were:

- malformed JSON: `ambiguous`, null token totals,
  `INVALID_USAGE_JSON` (`phase5_operator_health.py:595-609, 646-766`);
- non-dict JSON: `ambiguous`, null totals, `INVALID_USAGE_SHAPE`;
- missing, null, negative, fractional and noncanonical fields: `missing` or
  `ambiguous`, null totals, with traceable coverage reasons;
- a genuine `(input_tokens, output_tokens) = (0, 0)` pair: `observed`, zero,
  `OBSERVED_COMPLETE_USAGE`;
- one missing field plus one valid field: `missing`, null totals;
- identical identified receipt replay: one receipt, `10/4` tokens and a
  duplicate warning; conflicting identified replay: `ambiguous`, null totals;
- two unidentifiable receipt replays: `ambiguous`, null totals and
  `UNIDENTIFIABLE_RECEIPT_IDENTITY`;
- reordered rows: identical canonical bytes and SHA
  `42584985a5b80cc06e52726ff8a21420aecfd0cad51f852a90cd8fd80569541d`;
- persisted adapter: fixture hash unchanged, query-only read, mixed subjects
  and scopes preserved, `usage_json` absent from output, and actual cost null.

The persisted assertions are also covered by
`tests/test_phase5_operator_health_catalogue.py:103-183`, including the
parameterised usage cases at `:134-164`; direct semantics and replay cases are
covered by `tests/test_phase5_operator_health.py:120-220, 380-463`.

## Claim classification

| Claim | Result | Evidence and boundary |
|---|---|---|
| Fail-closed usage missingness and valid explicit zero | **PASS, bounded** | Catalogue projection allowlist/coverage at `phase5_operator_health_catalogue.py:98-136`; token validation and null-total state at `phase5_operator_health.py:621-783`. |
| Identified replay deduplication, conflicting identity and unidentifiable replay handling | **PASS, bounded** | Receipt identity handling at `:216-248, 686-763`; regressions at `test_phase5_operator_health.py:141-167, 440-463`. This is local aggregation, not provider exactly-once evidence. |
| Persisted SQLite and direct supplied-snapshot paths | **PASS, bounded** | Read-only adapter at `phase5_operator_health_catalogue.py:228-253, 281-401`; direct adapter at `phase5_operator_health.py:270-315`; fresh probes and 105-test run. The synthetic fixture was created outside the repository; adapter access did not write it. |
| Raw provider payload/reference exclusion | **PASS, bounded** | Receipt safe-field projection at `phase5_operator_health_catalogue.py:80-136`; payload-free regression `test_phase5_operator_health_catalogue.py:143-164` and persisted diagnostics tests. |
| Canonical JSON/SHA, mixed subject/scope/source provenance | **PASS, bounded** | Canonicalisation at `phase5_operator_health.py:182-190, 789-803`; per-run provenance at `:659-667`; fresh reordered-row and mixed-run probes. |
| Cost, pricing/FX and project-ledger non-inference | **PASS for fail-closed local diagnostics; PARTIAL for economics authority** | Ledger gates at `phase5_operator_health.py:400-418, 423-554` preserve null/ambiguous totals. Pricing/FX IDs and supplied rows are not independently verified. No cumulative AUD project ledger is established. |
| Live runtime wiring, provider policy/route, source-owned T3 rights, provider-side effects | **FAIL / not established** | This module is a read-only observer over supplied or persisted local rows (`phase5_operator_health.py:1-7, 787`). No live wiring, provider crossing, route policy, rights decision or source acquisition was authorised or tested. |
| Gate 4 closure or Builder-to-65k progress | **FAIL / not claimed** | This evidence does not close Gate 4 or alter the canonical scorecard: Gate 1 CLOSED, Gate 2 ACTIVE, 12% earned. |

No provider/source/spend/publication effect occurred. No raw provider payload,
private source material, prompt, model response, credential, runtime cache or
log was written to Git. The result is local diagnostic evidence only, not a
claim about live provider execution, source rights, provider permission,
verified FX/pricing, cumulative AUD expenditure or project-wide completeness.

## Highest-value next bounded industrialisation task

Add a provider-free contract harness at the actual Phase-5 runtime diagnostics
export seam: invoke the live read-only snapshot/export path, compare its
allowlisted persisted representation with the direct observer, and assert
missingness, provenance, payload minimisation and cost-ledger boundaries on a
reproducible fixture. Keep provider crossing, source-rights/T3 policy and
cumulative ledger reconciliation as separately authorised gates.
