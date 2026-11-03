# G4-O1C post-adoption read-only next-tranche review

Date: 2026-10-26 (Australia/Sydney)
Mode: provider-free, local, report-only
Fenced HEAD: 7671932137312ad0ee0e22c351eccaeb5bdcf0ef

## Disposition

PARTIAL; planning only. The v3 provenance-bound adoption commit is present
and its prior independent PARTIAL assessments remain evidence, not acceptance.
P3b2 remains quarantined and unaccepted. Gate 4 remains open. No code or test
changes, SQLite database, provider, source, bridge, watcher, Git staging or
commit action was performed by this review.

## Authority and evidence read

Read locally: AGENTS.md, ARCHITECTURE.md, BUILDER_MACHINERY.md, the Gate 4
objective/industrialisation records, source_rights.py, the P3c/P4 reports, the
adoption reports, rights_governance_record.py and its tests,
phase5_run_diagnostics.py and its tests, runtime/catalog.py,
runtime/migrations.py, the Factory rights boundary, and the bridge protocol,
implementation and harness.

The sibling C:\CharityGraph-clean\charitygraph-data was available and read
read-only: DOCUMENT_AUTHORITY.md, CURRENT_STATE.md, IMPLEMENTATION_PLAN.md,
TEST_PLAN.md, INTEGRATED_PRODUCT_AND_DATA_MODEL.md,
SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md,
TAXONOMY_AND_SCHEME_GOVERNANCE.md,
COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md, and
SEMANTIC_HEURISTIC_APPROVALS.md. The controlling rights policy requires a
versioned decision bound to the source artifact and exact transmitted
representation, with independent local-retention, provider-transmission and
public-redistribution axes; SQLite is operational/rebuildable state, not the
sole evidence authority (SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md:113-133,
INTEGRATED_PRODUCT_AND_DATA_MODEL.md:189-207,1140-1142,1224-1258).

## Repository and adoption state

Observed before writing this report:

| Item | Evidence |
|---|---|
| Branch | gate3-cg406-remediation |
| HEAD / tree | 7671932137312ad0ee0e22c351eccaeb5bdcf0ef / 09bc6c3af0c57bf9eeede4795d85072e0476c0ce |
| HEAD parent | fe8dbe0c7b83acd4270f97b1e5ab2c94b8f6cccb |
| HEAD subject | bridge: adopt gate4:engineering:20261026-g4-p3c-p4-bridge-owned-provenance-adoption-v3 |
| Visible status baseline | 76 records: 10 tracked-dirty, 66 untracked; status fingerprint a1841744370ee7576cf370f1079e2ea23ca731bbaf600e284afaec820357d514 |
| Required report | absent before this write |

The adoption commit contains the three P3c paths, the three P4 paths, and the
bridge-owned adoption report. The adopted implementation/test bytes remain:

| Path | Status before report | SHA-256 |
|---|---:|---|
| src/charitygraph/runtime/rights_governance_record.py | clean | e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9 |
| tests/runtime/test_rights_governance_record.py | clean | 3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486706ab6c06f9ca310 |
| src/charitygraph/phase5_run_diagnostics.py | clean | 9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372 |
| tests/test_phase5_run_diagnostics.py | clean | 869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325 |
| src/charitygraph/runtime/migrations.py | clean | 2c145bb6e13038bd3f92bffcb7dc0671b6e8a8b02fd1d41b8af2fea07ebd8dc7 |
| src/charitygraph/runtime/catalog.py |  M | 3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1 |
| src/charitygraph/source_rights.py |  M | 72f0cc0b3fb1f1ad0f3bb92700e6fe26bc85a9a97510a261e4ae285e66da79bc |
| src/charitygraph/phase5_governed_factory_integration.py |  M | 503d357761ab4884c4099b58e8ff15becb7214611984b46af7d68b236a8b0224 |
| tests/test_phase5_governed_factory_rights.py | ?? | dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281 |

The prior reports were retained, including
reports/G4_P3C_RIGHTS_RECORD_INDEPENDENT_ACCEPTANCE_MIGRATION_SEAM_20261026.md,
reports/G4_P3C_P4_PROVENANCE_BOUND_ADOPTION_RETRY_20261026.md, and
reports/G4_P3C_P4_PROVENANCE_BOUND_ADOPTION_BRIDGE_COMMIT_20261026.md. They
remain historical/diagnostic PARTIAL evidence; the adoption commit does not
convert them into P3c/P4 acceptance.

## Clean-HEAD conformance findings

1. The adoption is not self-contained at fenced HEAD. The adopted module imports
   governed_rights_policy at rights_governance_record.py:27-33. The current
   dirty source_rights.py:55-67 supplies it, but the HEAD blob has no such
   function. A clean checkout of the fenced HEAD therefore cannot import the
   adopted record without an additional code change. This is a concrete
   dependency/conformance defect, not P3b2 acceptance.

2. The record is a useful substrate, not yet the authority. It correctly
   provides canonical content-addressed bytes, exact representation hash
   fields, three independent axes, optional expiry, and append-only
   supersession/revocation (rights_governance_record.py:108-151,252-313).
   However, auxiliary policy versions are not all resolved against a fixed
   governed registry (:205-211), substantive source-rights predicates are
   not fully carried/delegated from ArtifactRightsDecision
   (source_rights.py:70-183), events validate their own bytes but not target
   existence/replay (rights_governance_record.py:315-412), and lifecycle
   validation lacks temporal/event replay semantics (:542-605).

3. SQLite is still a side-installed operational projection. Rights DDL is
   embedded in catalog.py:77-124 and installed by
   _ensure_artifact_rights_tables() (:450-496); MIGRATIONS ends at v28 in
   runtime/migrations.py:1192-1223. The catalogue persists material_json
   and hashes (catalog.py:2993-3123), but there is no numbered rights
   migration, authoritative-record import, deterministic rebuild, or
   transactional current-frontier projection. Duplicate-current detection is
   application logic in the dirty integration path, not a complete projection
   contract.

4. P4 is a pure offline projection only. phase5_run_diagnostics.py:322-440
   consumes caller-supplied run and ledger records, produces canonical
   diagnostic bytes, and explicitly states that it does not observe provider
   exactly-once effects, live scheduling/multiworker SLOs, rights acceptance or
   production health (:433-437). The retained P4 report is therefore an
   offline diagnostic seam, not real-run acceptance.

## Smallest meaningful next tranches

### P3c-A — provider-free authority conformance

Exact intended paths, after a clean/promoted baseline is supplied:

    src/charitygraph/source_rights.py
    src/charitygraph/runtime/rights_governance_record.py
    tests/test_source_rights.py
    tests/runtime/test_rights_governance_record.py
    reports/G4_P3C_AUTHORITY_CONFORMANCE_20261026.md

Keep this tranche narrow. Make the content-addressed record delegate the
substantive policy predicates to the one source-rights authority, add exact
version resolution for every authorized policy axis, retain the exact source /
record / role / acquisition-lineage / representation-artifact / representation
hash / subject-scope binding, and require event targets before event storage.
Preserve independent retention, provider and redistribution decisions,
append-only supersession/revocation, and optional expiry. Do not change the
Factory, provider route, source universe, public contract, or SQLite schema in
this tranche.

Acceptance tests should cover clean-HEAD import, all supported policy identity
and version combinations, missing/unsupported predicates, changed exact
representation and lineage, subject/scope/role mismatch, missing event target,
duplicate successor/cycle, revoke/supersede, and inclusive/expired optional
expiry. No provider call or real source is needed. No test was run in this
review because the task forbids workspace-writing tests.

### P3c-B — SQLite projection and deterministic rebuild

Separate exact paths:

    src/charitygraph/runtime/migrations.py
    src/charitygraph/runtime/catalog.py
    tests/runtime/test_migrations.py
    tests/runtime/test_rights_governance_projection.py
    reports/G4_P3C_SQLITE_PROJECTION_REBUILD_20261026.md

Add one numbered migration after v28 for projection tables and constraints;
remove the authority implication from side-installed DDL. Import only
validated private content-addressed records, project record IDs/hashes and
safe metadata into SQLite, enforce deterministic current-frontier conflict
handling, and provide an idempotent wipe/rebuild from the private record store
with corruption, missing-target and duplicate failures remaining fail closed.
The private record bytes remain authoritative; SQLite remains rebuildable
control/query state. Validate migration checksums, upgrade from v28, restart,
rebuild equivalence and concurrent current-decision conflict in a temporary
runtime root outside the checkout.

### P4-C — real local-run diagnostics, separately authorised

Exact intended paths:

    src/charitygraph/phase5_run_diagnostics.py
    src/charitygraph/runtime/catalog.py       # read-only run/ledger snapshot seam only
    tests/test_phase5_run_diagnostics.py
    tests/runtime/test_phase5_run_diagnostics_catalog.py
    reports/G4_P4_REAL_RUN_DIAGNOSTICS_20261026.md

Join an actual persisted local Factory/Standard run and its durable ledger by
run identity, snapshot the existing rows read-only, and feed that snapshot to
the existing canonical projection. Acceptance requires non-synthetic run,
task, attempt, receipt, reservation and exact-decimal cost evidence, restart
no-resend evidence, distinct ambiguous/systemic stop evidence, and stable
diagnostic hash/provenance. A fake/recorded provider may be used only as the
existing provider-free test seam; this tranche authorizes no live provider,
source acquisition, spend, scheduler rewrite, alerting claim or Gate 4 closure.

## Bridge bounded-workspace decision

The current bridge separates the routes as intended:

- Codex is launched with --sandbox workspace-write
  (bridge/bridge.py:903-920); ordinary bounded_workspace permits the
  worker's one local commit, while the bridge attests it afterward.
- The bridge-owned exact-path staging/commit helper is deliberately called
  only for provenance_bound_adoption (bridge/bridge.py:812-859,1057-1085).
- Ordinary commit acceptance is implemented by
  verify_local_commit() (src/charitygraph/bounded_authority.py:363-413):
  one non-merge direct child, exactly one commit, allowlisted committed paths,
  no pre-existing dirty path absorbed, and no committed symlink.
- The harness covers ordinary worker-side commit acceptance at
  tests/test_double_loop_harness.py:410-420,551-597; bridge-owned adoption
  and rollback are separate at :680-794.

Decision: no new bridge-owned bounded_workspace staging/commit repair is
prerequisite for a future ordinary tracked-file change on clean paths. The
worker-owned one-commit route is statically and harness-proven. However, this
checkout is NO-GO for the P3c-A implementation as a single ordinary commit
until its dirty dependencies are cleanly promoted or otherwise supplied as a
new exact baseline: source_rights.py, catalog.py and
phase5_governed_factory_integration.py are already dirty, and the current
adopted record depends on the dirty source_rights.py. A dirty file cannot be
absorbed into the ordinary bounded commit (SUPERVISOR_PROTOCOL.md:60-70).

If a supervisor instead requires bridge-owned staging for ordinary
bounded_workspace, that is a separate, narrowly scoped bridge repair and
must be tested/recertified before use; it is not silently inferred or applied
by this report. No fence, staging, commit, watcher, GitHub, release,
publication, provider/source, spend, or follow-on action is authorised here.

## Explicit out-of-scope

No P3b2 adoption or retroactive acceptance; no Gate 4 closure; no public
contract/schema/viewer change; no source-family expansion or discovery; no
provider/API/model call or spend; no production SQLite database; no real
source acquisition; no migration execution; no tests that write the workspace;
no scheduler, alerting, SLO or live-health claim; no publication, release,
GitHub mutation, merge, fence, watcher, Drive action, deletion, reset,
checkout, staging, commit, or follow-on dispatch.

