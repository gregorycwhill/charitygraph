# G4 T4A7 budget verifier edge-case repair — independent acceptance

Date: 2026-10-29 (Australia/Sydney)
Worker: bounded G4-O1C, local/provider-free, report-only
Branch: `gate3-cg406-remediation`
HEAD: `aeca5ce1bc57f381a0612f7b302c83db1680569b`
Fence: `v57` / `546fd536da2fa28c91bcf78583323146525090d453794d06718e85d5e70ce3b3`

## Disposition

**PARTIAL.** The committed edge-case repair is **ACCEPTED** for its narrow,
provider-free, caller-supplied-evidence verifier boundary. Gate 4 budget
accounting and real-send readiness are **NOT ACCEPTED**. This report does not
close a gate.

## Commit, hashes and dirty boundary

The commit is a single-parent direct child of
`59d982d0862c76d7af5bcefd8ba1e138e31af637`; commit tree
`3ee6d480a139c606c129445f2047c20eeff36b3e`, parent tree
`51227dcb39474a25605b1f34540401a33c6ee334`. The exact diff has only these
three paths:

- `src/charitygraph/phase5_t4a_budget_attestation.py`
- `tests/test_phase5_t4a_budget_attestation.py`
- `reports/G4_T4A7_BUDGET_VERIFIER_EDGECASE_REPAIR_20261029.md`

Worktree SHA-256 values match the committed worker assertions for the code and
tests; the worker report is also unchanged:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_budget_attestation.py` | `14324f22ba94aa374adae6c82402c4cb0d40610213a9522de523bb05b3e436fc` |
| `tests/test_phase5_t4a_budget_attestation.py` | `356514864fd86b23e256e3257b61d1fc1fa5b35aaef7def5e74a9fd200c4ca80` |
| `reports/G4_T4A7_BUDGET_VERIFIER_EDGECASE_REPAIR_20261029.md` | `2199669b7cc817b325bde622d7306c9f770f75dc66e17560afa378bb61d538df` |

The pre-existing dirty worktree remains outside these target paths; no dirty
T4A2/T4A2A or other file was edited, staged, absorbed or deleted. The exact
allowlisted commit is real. However, exact `git diff --check` independently
reports trailing whitespace in the committed T4A7 worker report lines 3–6.
That is a report-hygiene defect, not a verifier correctness failure.

## One focused independent test run

Exactly one focused invocation was run:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a7-independent-acceptance-20261029-ec44951cf188492b937e93d0c2407d7c tests/test_phase5_t4a_budget_attestation.py`

Exit status: **0**. Result: **31 passed, 0 failed**. The basetemp was outside
the repository, bytecode and pytest cache were disabled, and the target paths
were unchanged after the run.

## Independent technical assessment

The implementation and tests support acceptance of the bounded verifier:

- `Decimal` caller proposals are copied and accepted only when finite and
  nonnegative; strings are parsed as `Decimal`; floats, bools, NaN, Infinity,
  negatives and unknown values fail closed.
- Canonical UTF-8 JSON is required. Duplicate object keys are rejected at root
  and nested levels; non-canonical numeric JSON is rejected; monetary snapshot
  fields are not accepted as JSON binary numbers.
- Naive, future and stale `as_of` values fail closed. The exact observed
  snapshot SHA must match the separately supplied lowercase trusted SHA pin.
  The optional snapshot `content_sha256` is only shape-checked and is not used
  as authority.
- Exact project-wide coverage keys and boolean assertions are required.
  Pending or ambiguous physical attempts are retained in diagnostics and
  produce `BLOCKED`; duplicate or malformed attempt records fail closed.
- Replay is deterministic. A positive result is exactly
  `BUDGET_EVIDENCE_VERIFIED_NON_SEND`, with `request_ticket is None` and
  `send_authorization == "not_authorized_for_send"`. The focused side-effect
  test blocks filesystem and socket access; the code has no send/provider
  operation.

Independent limitations remain material. The verifier trusts caller-provided
coverage and does not discover omitted, unknown or unpriced attempts. It does
not prove the trusted pin’s provenance, the truth of the export, or that the
export is source-owned and complete. It has no required source-authority,
pricing identity or FX identity in the snapshot contract. Thus this is code
acceptance, not acceptance of factual project-wide accounting.

## Explicit non-acceptance boundaries

No evidence here establishes a live provider contract, selected project route,
current no-opt-in state, pricing or FX authority, cumulative AUD10 reservation
and actual attestation, or one real governed T3 cohort. The Data current-state
authority still records Gate 4 as active and not earned; the existing
industrialisation review is provider-free/offline evidence, not current
industrialisation proof. No provider/model/network/credential call,
acquisition, spend, reservation, publication, authority change or send occurred.

## Smallest separate successor

Within **600 seconds**, produce one read-only, source-owned current accounting
export from the durable runtime owner covering every cohort, logical task,
retry, physical attempt, actual, outstanding reservation, pricing/FX identity
and ambiguous/unknown state, then run the existing verifier against it. The
trusted SHA must be supplied independently by the authority; the export must
not self-pin, and missing or unknown records must not be inferred as zero.
Do not reserve, send, call a provider, publish, alter Git, or touch the dirty
T4A2/T4A2A files. This is a distinct factual-accounting successor, not another
edge-case repair.
