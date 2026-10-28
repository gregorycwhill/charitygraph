# Gate 4 T3 governed real-source binding — 2026-10-29

## Result

The fixed five-subject, ten-row cohort was processed locally from the already retained ACNC register/AIS objects named by selected manifest SHA256 `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`. No source was acquired, substituted, expanded, sent, or published.

All 10 rows became genuinely bound in disposable state with exact source-family, source-definition, source-record, acquisition-receipt, source-artifact hash, derived representation hash, registered-entity scope, evidence-locator, and content-addressed rights-record identities. Representations were materialised through the existing derived-artifact contract; no source SHA was relabelled as a representation ID.

No row became downstream-task eligible. The clean T1B rights contract cannot authorise its local-retention axis for the PO-approved `public_source_private_processing` basis. The implementation therefore preserves that basis in each rights record but leaves local retention `not_assessed`; governed preflight lowers all 10 rows to zero accepted tasks. Provider processing is separately blocked because no provider contract identity/version is bound. Public redistribution remains `not_assessed` and was outside this private task.

## Verification

- Temporary SQLite catalog and rights store: v29 projection rebuilt, closed, reloaded, rebuilt, and matched exactly.
- Deterministic replay: manifest bytes and projection snapshot hash matched across two disposable work roots.
- Clean verification used a read-only `git archive HEAD` plus only the new candidate module, test, and manifest overlay; focused result: 4 passed.
- Focused cases cover all ten rows, exact identity/representation separation, explicit exclusion lowering to zero, retained-byte hash mismatch lowering one row to zero without substitution, provider denial, zero AUD spend, and absence of source bodies from the manifest.
- Emitted manifest: `evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json`; identity SHA256 `5c352f6a929508d9ecfe959cb4f8191cf776ef826b03be33f78d8c24bddbd14a`.

## Exact remaining gaps

1. The clean T1B local-retention authority needs a versioned rule that represents the Product Owner's approved internal-use basis, or an explicitly compatible policy record. Adding a licence claim or relabelling the current basis would be false and was not done.
2. Provider processing still needs a separately governed provider-contract identity and version. This task made no provider request and spent AUD 0.00.
3. The successful v29 rows exist only in the OS-temporary catalog used by the test. No production catalog or durable release projection was changed; a later authorized reload into the intended durable catalog is required.

No concrete source exclusion was observed in the selected run. The exclusion path requires material, authoritative wording, and affected operation and is tested fail-closed. Existing dirty and quarantined repository material was not imported or modified.
