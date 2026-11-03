# G4 T4A5 independent acceptance

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free, report-only  
Branch: `gate3-cg406-remediation`  
HEAD: `9993d9d64d035a395ad29da6b5f4841d4c1d6bb9`  
Fence: `v55` / `126aa26b215484a51728e9f43ba4587ebde1b5ced8b5edd14aa52473a1d695b1`

## Disposition

**PARTIAL.** The committed verifier implementation is **ACCEPTED** for its
narrow provider-free, evidence-only boundary. Factual project-wide budget
evidence is **NOT VERIFIED**; this is not real-send readiness and does not
close Gate 4.

## Commit and dirty-boundary proof

HEAD is a single-parent, non-merge direct child of
`5edcb38c6b101284782f2e5edcb146f32f972314`. Its tree is
`d75a333b9145e1f1176ce4e9f7e99a648883a5a0`; the parent tree is
`36e9b3fb462d49da43b006493e4213cae2deec1c`. The commit changes exactly these
three allowlisted paths:

- `src/charitygraph/phase5_t4a_budget_attestation.py`
- `tests/test_phase5_t4a_budget_attestation.py`
- `reports/G4_T4A5_CUMULATIVE_BUDGET_ATTESTATION_20261029.md`

Worktree SHA-256 values match the committed files:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_budget_attestation.py` | `da1b9f5da5f1b90b30493396ce646e386d3c06c5365e14aaa5da388cbdc25c6c` |
| `tests/test_phase5_t4a_budget_attestation.py` | `497c7eaaa1be3822cc345c1e70841e80e697003fe2469aa59d39b331b8efeb7c` |
| `reports/G4_T4A5_CUMULATIVE_BUDGET_ATTESTATION_20261029.md` | `c1d80a88581820c026cfc66acfb438317ea12534ce2b557e1635d675781943fd` |

The repository already had unrelated dirty tracked and untracked paths before
this review. The three committed paths had no worktree modifications, and no
pre-existing dirty file was absorbed or changed. This report is the only new
file written by this task. Its own digest is intentionally not embedded because
self-hashing would change the report bytes.

## Focused verification

Exactly one permitted invocation was run:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a5-independent-acceptance-20261029 tests/test_phase5_t4a_budget_attestation.py`

Result: **16 passed, 0 failed**. No provider, model, credential, network,
source acquisition, reservation, spend, publication, GitHub/Drive action or
existing-file mutation occurred.

## Independent semantic assessment

The code inspection and focused tests support these implementation checks:

- canonical UTF-8 JSON is required byte-for-byte; duplicate object keys are
  rejected recursively, and non-canonical bytes fail closed;
- the observed SHA-256 is compared with the separately supplied
  `trusted_sha256`; the optional snapshot `content_sha256` is not used as
  authority;
- exact project identity, schema, AUD currency, timezone-aware `as_of`, future
  timestamps and 24-hour freshness are checked;
- snapshot monetary fields are decimal strings only, finite and nonnegative;
  negative, NaN, Infinity and alternate JSON numeric types do not pass;
- required fields and exact coverage keys are enforced. Coverage must assert
  project-wide completeness for actuals, reservations and physical attempts;
- physical-attempt records are constrained to unique IDs and `pending` or
  `ambiguous` states, and any such attempt blocks a positive result;
- actuals plus outstanding reservations share the fixed AUD 10.00 cap, and
  caller-proposed one-request headroom is checked;
- the only positive status is `BUDGET_EVIDENCE_VERIFIED_NON_SEND`, with no
  request ticket and `send_authorization` fixed to
  `not_authorized_for_send`. The verifier performs no filesystem, catalogue,
  network, provider or mutable-ledger operation.

The 16 tests cover deterministic replay/non-send output, independent-pin
forgery, missing/incomplete coverage, cap and proposal headroom, pending or
ambiguous attempts, stale/project/currency rejection, negative/non-finite and
numeric-type rejection, and filesystem/network side-effect absence.

## Remaining defects and evidence boundary

1. No current, independently trusted project-wide cumulative ledger snapshot
   is present. The existing runtime `budget_position` and
   `accounting_budget_position` views are cohort-scoped catalogue calculations,
   not this project-wide authority. Synthetic, packet-local and historical
   ledgers cannot establish the requested factual position.
2. The pure verifier can validate a trusted hash and completeness assertions,
   but cannot prove the provenance of the caller's trusted pin or the truth of
   the asserted coverage. Thus omitted, unknown or unpriced physical attempts
   remain a factual-authority failure if the upstream snapshot is incomplete;
   the verifier itself has no catalogue/ledger access with which to discover
   them. This is why implementation acceptance is separate from evidence
   acceptance.
3. `proposed_max_one_request_reservation_aud` is annotated as `str | Decimal`,
   but `_parse_amount` accepts only strings. A `Decimal` proposal therefore
   fails closed rather than being handled according to the declared API.
   This is not a bypass, but it is an implementation defect. There are also no
   dedicated tests for duplicate-key, future-time or naive-timezone cases,
   although the inspected code has explicit checks for them.

No source-owned live provider contract/route, pricing or FX authority,
credential control, actual-send ticket, reservation, provider crossing or
send authorization is established here.

## Next bounded provider-free task

Implement one read-only, source-owned project-wide ledger snapshot/reconciliation
adapter using the existing durable runtime accounting, with explicit inclusion
of every paid logical task, retry, actual, outstanding reservation and
ambiguous/unknown physical attempt. Bind it to an independently supplied
canonical-byte SHA-256 authority, repair the declared `Decimal` proposal
contract, and add the missing duplicate-key/time-boundary tests. Re-run this
verifier only against that factual snapshot; do not reserve, send or infer
pricing/FX/route authority.
