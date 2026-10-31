# G4 provider authority registry repair

Date: 2026-10-31 (Australia/Sydney)

## Result

The provider-free registry tranche now reports positive structural consistency
as `STRUCTURE_ONLY_UNAUTHENTICATED`. A caller-supplied SHA pin is never
authentication, `authority_verified` cannot be caller-promoted to true, the
action is `NONE`, `real_send_ready` is always false, and
`host_authentication_required` is true.

`authority_content_sha256` is compared with SHA-256 of the exact separately
supplied `authority_document_bytes`. Those bytes must be non-empty canonical
JSON, must not equal the registry record bytes, and are never substituted by
the record hash or locator. Missing, non-canonical, self-referential or
mismatched authority-document bytes fail closed.

The no-send rights preflight retains its provider-free fake-provider Factory
lowering and no longer treats its compatibility `provider_policy_authority`
argument as a send gate. The explicit
`require_authenticated_provider_authority_for_real_send` boundary fails closed
for missing or unauthenticated source-owned policy authority, rights, current
v29 projection, or route, while separately preserving local-retention and
provider-transmission checks.

## Validation

- Focused repair/adversarial tests: **19 passed**.
- Clean preflight/Factory regression selection: **16 passed, 1 skipped**. The
  skip is the existing dirty-rights-seam isolation test.
- Broader relevant selection: **73 passed, 1 skipped, 12 failed**. The failures
  are the pre-existing dirty `rights_decision_ids`/rights-prototype and
  T4D-scope overlay failures documented by the independent acceptance; they
  are outside the four allowed repair paths. No repair-path failure was
  identified.
- `git diff --check` is clean for the three changed existing paths. The new
  report has no trailing whitespace or extra blank EOF by direct byte scan.

## Repository boundary

The requested exact-path local commit was not possible in this managed
workspace: `git add` was denied because `.git/index` is read-only, with no
stale `index.lock` present. No Git metadata or unrelated worktree path was
modified.

## Residual authority boundary

No durable source-owned provider-policy registry or independently authenticated
trust root was available or invented. Therefore this tranche does not produce
an authenticated resolution and does not make any existing path real-send
ready. No provider, credential, source or Drive access, network activity,
budget reservation, spend, acquisition, publication or runtime side effect was
performed. Private evidence and runtime material remain excluded.
