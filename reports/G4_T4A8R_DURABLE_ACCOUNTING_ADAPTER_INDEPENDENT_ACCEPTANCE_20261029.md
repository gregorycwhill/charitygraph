# G4 T4A8R durable accounting adapter — independent acceptance

Date: 2026-10-30 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free, report-only  
Branch: `gate3-cg406-remediation`  
HEAD: `b3e01793100b9c92e992559187a3177db650662b`  
Parent: `aeca5ce1bc57f381a0612f7b302c83db1680569b`  
Fence: `v58` / `9ca4ce44dc90eeb11640b3456e08d997d9be469d78590ad82e6f8c415b6567c6`

## Disposition

| Boundary | Result |
|---|---|
| CODE | **PARTIAL** — exact clean-path adoption and narrow provider-free adapter boundary pass; faithful current durable-export acceptance does not |
| Factual project-wide budget attestation | **REJECT** — not evidenced |
| Provider route/contract | **REJECT** — none established |
| Price/FX authority | **REJECT** — only caller-supplied IDs are checked |
| Cumulative AUD10 position | **REJECT** — no current project-wide authority supplied |
| Real-send readiness | **REJECT** — no ticket or authorization is produced |
| Gate 4 closure | **REJECT** — this report does not close the gate |

The code is acceptable as a deterministic, read-only adapter over already-open
caller-supplied views. It is not evidence that the current project-wide SQLite
accounting state has been exported or independently verified. The T4A8 and
T4A8R materials supplied no live view or independent accounting authority.

## Commit, path and dirty-boundary proof

`HEAD` is a one-parent direct child of the requested parent. The parent-to-HEAD
diff changes exactly three paths:

- `src/charitygraph/phase5_t4a_durable_accounting_export.py`
- `tests/test_phase5_t4a_durable_accounting_export.py`
- `reports/G4_T4A8R_QUARANTINED_ADAPTER_CLEAN_PATH_ADOPTION_20261029.md`

The committed target paths have no worktree diff. Worktree SHA-256 and Git blob
identity observed independently:

| Path | SHA-256 | Git blob |
|---|---|---|
| clean adapter | `6fc68a6a1ccbca9f8188c38d36286505f34af100882f8ca34264b32590395fe0` | `5e0ca34c53c810ed94dbc7e44c048de77148ef40` |
| clean focused test | `4fe08b92a178498990d210dbe05a1ac8a9aea76399d59246549ae8195da899a1` | `3bb99481d2c5cc3ab9845a9d6ffdb4f7c2d3a001` |
| committed T4A8R worker report | `c105ddb8ab37e2dbf89072aa5aa0335df0a163320c3c7cf01692ec80f0de9031` | `53231accec8366cda2418e299b08a5e44925b971` |

The quarantined forensic paths remain untouched and retain the required
identities:

- `src/charitygraph/phase5_t4a8_durable_accounting_export.py` —
  `6fc68a6a1ccbca9f8188c38d36286505f34af100882f8ca34264b32590395fe0`
- `tests/test_phase5_t4a8_durable_accounting_export.py` —
  `321c1061ccd5f93cbdcf62c27b5d7cb4e0f4bfd11191436d925d3cfc2e327bf5`
- original T4A8 report —
  `reports/G4_T4A8_READONLY_DURABLE_ACCOUNTING_SOURCE_EXPORT_20261029.md`,
  SHA-256 `2109f2c8114736f26e63518bf84df2b9f7f80edbaecaa4e25e5f5c1cdb896891`.

The complete dirty baseline observed before this report was 112 entries: 11
modified tracked paths and 101 untracked paths. No target, forensic path,
T4A2/T4A2A path or prior report was absorbed, cleaned or changed. This report
is the only new repository file from this task.

## One focused independent test

Exactly one permitted pytest invocation was run:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a8r-independent-acceptance-20261030-01 tests/test_phase5_t4a_durable_accounting_export.py
```

Exit status: **0**. Result: **8 passed, 0 failed** (`0.55s`). The unique
basetemp was outside the repository; bytecode and pytest cache were disabled.

## Independent technical assessment

- **Cross-cohort population:** the supplied synthetic view contains two
  cohorts and the reused T4A6 reconciliation checks set coverage for cohorts,
  logical tasks, retries, physical attempts, reservations and cost entries.
  Its passing fixture calculates AUD `2.00` actual and AUD `2.75` outstanding
  reservation exposure. Those are fixture results, not project facts. The
  adapter never enumerates the live catalogue.
- **Logical/retry/physical accounting:** IDs, some cohort links, retry
  identity and missing/ambiguous/unknown physical states are fail-closed. The
  synthetic test fixture nevertheless gives two provider request attempts the
  same physical attempt ID (`tests/test_phase5_t4a_durable_accounting_export.py`),
  while migration 13 makes `provider_request_attempts.physical_attempt_id`
  unique (`src/charitygraph/runtime/migrations.py:680-701`). The adapter does
  not reject that duplicate physical linkage and does not consume the full
  `physical_attempt_members`, request-item, delivery-job or receipt graph.
  Therefore the fixture is not a verified current SQLite export.
- **Amounts and currency:** decimal-string arithmetic, AUD checks, reservation
  release reconciliation and duplicate evidence IDs are covered. The adapter
  does not compare a live row's compatibility `aud_amount` to its v20
  `accounting_amount`, nor validate provider amount/currency conversion.
- **Pricing/FX identity:** actuals and terminal physical attempts require
  caller-supplied pricing and FX IDs. The adapter checks presence and returns
  pairs, but does not resolve the pricing/FX records, rate, authority, period,
  provider route or price version.
- **Authority and coverage:** source authority, retention identity, root
  provenance and manifest coverage shape are checked. Coverage completeness is
  still an assertion supplied by the caller. The declared source
  `content_sha256` is not recomputed from an exported source view, and row-level
  provenance is not proven to bind every row to that authority.
- **Duplicates, ambiguity and determinism:** evidence/manifest duplicate IDs,
  unpriced actuals, ambiguous/pending/unknown physical states and canonical
  replay are tested. The candidate SHA is reproducibility output only; there is
  no trusted-pin input and `independent_trust` remains `NOT_SUPPLIED`.
- **Side effects:** the adapter uses supplied mappings/bytes only. The focused
  side-effect test blocks filesystem and socket access; no database, provider,
  model, credential, network, acquisition, reservation or send operation
  occurred.

## Product and evidence boundary

The adapter constructs a candidate from caller-supplied open views and
synthetic fixtures. It does not construct or verify a current factual
project-wide SQLite export. Existing runtime accounting views are cohort-scoped
calculations, not independent project-wide authority. Missing or unpriced
records cannot be treated as zero. Consequently, no factual cumulative AUD10
attestation, current price/FX position, provider contract/route, real-send
authorization or Gate 4 closure follows from this commit.

## Smallest next tranche (recommendation only)

Within 600 seconds, perform one read-only, source-owned, schema-aligned export
from the existing durable runtime owner, then replay this adapter against it.
The exact implementation/evidence surfaces are:

- `src/charitygraph/runtime/migrations.py`
- `src/charitygraph/runtime/catalog.py`
- `src/charitygraph/phase5_t4a_durable_accounting_export.py`
- `tests/test_phase5_t4a_durable_accounting_export.py`

Enumerate every cohort, run, task, retry, reservation/release, cost entry,
physical attempt, physical-attempt member, request item, delivery job,
provider-attempt and receipt, plus pricing/FX authority. Bind the exported
canonical bytes to an independently supplied source SHA; preserve unknown,
ambiguous and unpriced states and do not infer zero. Do not reserve, send,
contact a provider, acquire sources, mutate GitHub/Drive, publish or close the
gate.
