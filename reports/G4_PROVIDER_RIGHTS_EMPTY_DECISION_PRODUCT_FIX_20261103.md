# Gate 4 provider-rights empty-decision product fix

## Result

The governed Factory integration now treats an empty or omitted
`rights_decision_ids` reference as `rights_missing`. The reference is rejected
before Factory lowering, and the subsequent Factory seed/run creates zero
tasks, physical attempts, provider receipts, reservations, cost entries, or
provider request attempts. Affirmative, durable rights decisions continue to
produce the ordinary same-subject/same-scope Factory task.

## Reproduced failure

Before the fix, the existing rights suite failed its
`missing-decision` case: an empty `rights_decision_ids` tuple was accepted as
one Factory task (`accepted_count == 1`) instead of producing
`rights_missing`. The failure was caused by the dirty integration's legacy
current-decision inference path, which filled an absent reference from
catalogue rows.

## Correction and tests

The inference path was removed from governed preflight. Preflight now sends
all references directly through the existing durable provider-rights
validator; its existing missing-reference diagnostic is therefore authoritative
before Factory work is planned. The new focused test covers empty and omitted
references, affirmative rights, zero unauthorised work, replay idempotency,
and subject/scope isolation.

With pytest cache disabled (`-p no:cacheprovider`) and external basetemps:

- reproduction before correction: `16 passed, 1 failed`;
- focused corrected run: `27 passed`;
- broader Factory/rights run: `82 passed, 1 skipped`.

## Five-charity replay

The committed replay at `fbabffac80dfefe9de2217adc57a6c8f26d9068f` remains
provider-free and deterministic: five bound register rows produced five
local tasks on the first run, the deterministic second replay produced zero
additional tasks, identities and diagnostics were stable, and provider calls
remained zero. The replay retained five missing AIS rows, zero blocked rows,
zero spend, and rejected a mixed subject/scope reference.

## Preservation and remaining gaps

The pre-existing dirty integration edits were preserved except for the
bounded removal of the fail-open decision-inference path. The new test and
this report are newly created. No reset, checkout, commit, provider/model
call, source acquisition, publication, GitHub mutation, or Drive mutation was
performed; private source/representation material was not added to Git. The
managed bridge may perform its own exact three-path dirty-file reconciliation;
no worker commit was attempted.

Provider pilot work remains unscheduled: the preserved exact decisions have
`provider_call_authorized=false`, and no affirmative provider-processing
authority, AIS acquisition/rights/retained-representation evidence, provider
transmission, spend, publication, or route activation was introduced.
