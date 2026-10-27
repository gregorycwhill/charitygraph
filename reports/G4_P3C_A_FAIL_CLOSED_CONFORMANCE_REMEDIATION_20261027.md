# G4 P3c-A fail-closed conformance remediation

Date: 2026-10-27 (Australia/Sydney)
Mode: local, provider-free, bounded worker task
Result: **REMEDIATED_WITH_PROVIDER_AUTHORITY_BLOCKED**

## Scope and non-acceptance

Only the permitted clean runtime/test paths were changed, plus this report:

- `src/charitygraph/runtime/rights_governance_record.py`
- `tests/runtime/test_rights_governance_record.py`
- `reports/G4_P3C_A_FAIL_CLOSED_CONFORMANCE_REMEDIATION_20261027.md`

Dirty and untracked work, including `source_rights.py`, `runtime/catalog.py`,
the historical worker and independent reports, and quarantined P3b2 material,
was preserved. No staging, commit, reset, checkout, provider/model call,
network access, source acquisition, spend, database, publication or gate
closure occurred.

The committed source-rights authority exposes `OPENAI_PROVIDER_POLICY_ID` but
does not expose an exact provider-policy version registry. The runtime now
fails closed for every authorized provider axis unless a source-owned
`PROVIDER_POLICY_REGISTRY` supplies an exact ID/version match. It does not
invent a version, duplicate the registry, or silently fall back. Therefore
provider authorization remains **BLOCKED**, and this report does not claim
provider readiness or Product Owner/Gate 4 acceptance.

## Remediation

1. Provider axes require exact source-owned ID/version mapping; the current
   committed authority's missing mapping is a deliberate blocker.
2. Public axes require exact registered version and basis, and reject a
   registry entry with `public_redistribution: false`. A known `CC_BY_4_0_V1`
   registry case remains positive; the private-provider policy is rejected.
3. `blocked`, `revoked`, `superseded` and `unknown` overall records cannot
   contain authorized axes. Current-view resolution remains deterministic and
   fail-closed.
4. An overdue retention review under `active_until_review`/`review_due`
   prevents promotion. Optional `expires_on` remains inclusive on equality and
   denies only later dates.
5. `RightsGovernanceStore.put_record()` validates the complete existing-plus-
   candidate history before writing. Missing lifecycle targets therefore fail
   before persistence; append-only event writes still require an existing
   record target.

Adversarial and positive cases cover unsupported provider versions, forbidden
public policy, mismatched public basis/version, inactive authorized axes,
overdue review, missing lifecycle targets, canonical local retention, and a
known public policy.

## Verification

Focused suite, with pytest cache disabled:

```text
tests/runtime/test_rights_governance_record.py — 19 passed
```

Complete relevant provider-free regression command (source-rights, governed
Factory, Factory integration, Factory, task state, P3b1, P3b2 and focused
rights record tests): **94 passed**.

The clean-HEAD Git-byte import/probe passed:

```text
CLEAN_HEAD_GIT_BYTE_IMPORT_AND_FAIL_CLOSED_POLICY_PROBE_OK
Git blob:  bab1f855c5c4721e093f6d169b2f5ce022c12691
SHA-256:   5a30a25d35de1ef9584592328306fe209e37337eaa350ca023e77f4050e28190
```

The probe loaded the exact bytes from `git cat-file`, confirmed the dirty-only
`governed_rights_policy` helper is absent, accepted known local/public policy
cases, and rejected provider version `9.9.9`. `git diff --check` and the
permitted-path diff review are required final checks before handoff.

## Historical hash reconciliation

The original worker report recorded raw source hash
`13824bbe1bea1bb87d77636eca38a2794c294ad5b05d00d0b5ce0ea2ae5ccc98`.
The independent review and this exact Git-byte probe record
`5a30a25d35de1ef9584592328306fe209e37337eaa350ca023e77f4050e28190`.
The discrepancy is byte-level line endings, not a source-policy change: the
exact committed Git bytes are 14,349-byte LF bytes and hash to `5a30…`; the
same text converted to 14,604-byte CRLF bytes hashes to `13824…`. Historical
reports were not altered.

This is a bounded remediation attestation only. It explicitly does not accept
provider authorization while the canonical committed source authority lacks
an exact provider-policy version mapping, and it does not close P3c, Gate 4,
or any downstream gate.
