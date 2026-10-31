# G4 E3 missingness and rights-carriage repair

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free  
Branch/HEAD: `gate3-cg406-remediation` / `d9f7635e6abc317905dd887bdf174f7db62e7098`  
Fence: v66, SHA-256 `572933d62f41b07a21036e8d22d174bd51737c9529ec8be44f10feed9aa567ce`

## Result

**PASS — bounded implementation and focused verification.** This report does
not claim product acceptance, Gate 4 closure, publication, release or Factory
integration. Separate supervisory review remains required.

## Exact changed paths and diff

- `src/charitygraph/phase5_t4b_source_answer_projection.py`: private E2B
  contract v2; exact T3 source role, rights-record ID, rights-policy ID/version,
  binding status, provider-processing status and public-redistribution status
  are carried in `SourceCitation` and `AnswerRecord`. The ten
  source/representation/rights tuples are retained as an explicit inventory.
  Manifest carriage values are checked against the governed ten-row cohort and
  fail closed on role, policy or status tampering.
- `src/charitygraph/phase5_t4c_private_answer_brief.py`: private E3 contract
  v2; `CitedValue` retains the same carriage fields, E2B inventories are
  cross-checked, currentness requires `source_silent` with a reviewed-source
  `north-star-v0.3` assessment basis, and coverage records carry the explicit
  `north-star-v0.3` projection contract.
- `tests/test_phase5_t4b_source_answer_projection.py`: 11 focused missingness,
  carriage and tampering cases.
- `tests/test_phase5_t4c_private_answer_brief.py`: 5 focused E3 carriage,
  inventory and tampering cases.
- This report only; no other report was edited.

The allowed code/test diff is 312 insertions and 7 deletions across the four
paths above. No commit was created. Pre-existing dirty and untracked paths were
preserved.

## Missingness and semantic probes

The five currentness slots remain `answer_state="unanswered"` and
`answer=null`. Each now has `missingness.status="source_silent"`,
`source_silence_is_not_absence=true`, and an explicit basis identifying the
`north-star-v0.3` reviewed-source-silence assessment and the exact source-record
IDs. `source_silent`, `not_reviewed`, `not_processed` and `not_applicable` are
distinct governed vocabulary values with distinct basis kinds; the latter
three are not asserted for this reviewed currentness slice. Missingness remains
separate from `fact_vs_source_statement_vs_inference`, which remains
`not_applicable` only because no fact, source statement or inference answer is
being emitted. No current giving terms, capacity, outcomes, governance or
conduct conclusion is produced.

Direct replay probe: 5 subjects, 15 slots, 10 representation hashes, 10
source/representation/rights bindings and 20 North Star sections. All five
currentness statuses were `source_silent`; all side-effect counters were zero.

## Provenance, source rights and scope

The input was the existing governed manifest
`evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json`, whose file
SHA-256 is `06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4`.
The implementation reads the ten exact content-addressed representations and
does not enumerate, acquire or substitute sources. The five-subject cohort,
two admitted source families, source-native periods/field bases and 20-section
North Star v0.3 coverage are unchanged.

The exact per-row rights values are preserved from the authenticated T3
manifest: policy ID `CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1`,
version `1.0.0`, provider processing
`blocked_provider_contract_not_bound`, public redistribution `not_assessed`,
and binding status `bound_not_task_eligible`, alongside each row's exact role
and rights-record ID. The applicable internal-private-use authority was read;
no permissive default, rights weakening, provider authorization or publication
authorization was synthesized.

## Verification and operational controls

Command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts= tests/test_phase5_t4b_source_answer_projection.py tests/test_phase5_t4c_private_answer_brief.py -q
```

Result: **35 passed in 1.37s** (19 pre-existing focused tests plus 16 new
cases). `git diff --check` passed for the four changed code/test paths. The
projection imports only local JSON/hash/path/dataclass code, and the replay
probe reported zero provider calls, transport requests, budget reservations,
source acquisitions, publications and SQLite opens. No network, provider,
model, database/WAL, acquisition, spend, publication, watcher or process
action occurred. No bytecode or pytest cache was requested by the verification
command.

## Disposition

| Area | Result | Boundary |
|---|---|---|
| Missingness repair | **PASS** | Currentness is source-silent, explicit and non-negative; other governed states remain distinct and unasserted. |
| Rights/provenance carriage | **PASS** | Ten exact T3 source/representation/rights bindings and statuses are retained and tamper-checked. |
| Regression/adversarial tests | **PASS** | 35/35 focused tests passed, deterministic replay and zero counters retained. |
| Operational controls | **PASS** | Provider-free, read-only local projection only. |
| Product acceptance | **PARTIAL** | Supervisory acceptance, governed Factory integration, provider contract authority and any future public redistribution decision remain outside this task. |

Residual limitation: this repair does not reassess source evidence, provider
eligibility, live budgets, publication rights or any unrepresented currentness
proposition. The next Factory integration tranche is not part of this report.
