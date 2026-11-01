# G4 Phase 5 provider-history adapter repair

Status: bounded implementation complete; independent report-only acceptance remains required.

Scope is limited to the approved local adapter repair at the requested HEAD. No
provider, model, external-source, Drive, publication, release, GitHub, watcher,
or gate action is authorised or performed.

Implemented bounded changes:

- replaced wholesale nested `export.source_identity` copying with an explicit
  four-field allowlist, string-shape validation, canonical alias handling, and
  deterministic unknown/malformed omission diagnostics;
- retained each run-index row without a usable physical attempt ID, emitted
  `MISSING_RUN_PHYSICAL_ATTEMPT_ID` plus safe run-ID diagnostics, excluded the
  missing value from physical-attempt sets, and made the projection fail
  closed without inventing an attempt;
- added focused regression coverage for nested private-material sentinels,
  malformed/missing attempts, valid attempts, duplicate/receipt behaviour, and
  reversed-input determinism while preserving raw-export hash provenance;
- verified the authority invariant: the adapter never certifies
  project-wide completeness or remaining spend.

The repository already contains unrelated dirty tracked and untracked work; it
will be preserved. Only this report, the named adapter, and its named focused
test file are in the task allowlist. Private/raw material will not be added to
the report or Git.

Verification completed with `PYTHONDONTWRITEBYTECODE=1`,
`python -m pytest -p no:cacheprovider`, and pytest basetemp outside the
checkout:

- focused adapter suite: 27 passed;
- adapter plus project-cost-reconciliation and run-inventory-audit suites: 78
  passed in 9.53 seconds.

The private-material regression found no sentinel in canonical bytes, the JSON
projection, diagnostics, or this report. No provider/model call, paid spend,
source acquisition, publication, release, GitHub mutation, watcher/fence/
ledger change, gate closure, or follow-on dispatch occurred. Existing dirty
tracked/untracked files and unactivated CGDOC1 were preserved; only the
allowlisted adapter, focused test file, and this report were changed by this
task.
