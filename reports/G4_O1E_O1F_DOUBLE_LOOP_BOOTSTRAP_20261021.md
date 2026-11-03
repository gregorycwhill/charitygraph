# CharityGraph G4-O1E/O1F Double-Loop Harness Bootstrap

**Mission:** `cg-g4-double-loop-20261021-v1`  
**Disposition:** `READY_FOR_SUPERVISORY_TEST`  
**Authority:** bounded local implementation, provider-free tests and one scoped local commit. No GitHub publication, provider calls, source acquisition, gate closure or route activation.

## 1. Architecture and key decisions

The existing `LocalAutonomousBridge` remains the sole execution authority. O1E adds durable mission, event, review-cursor, supervisor-claim and supervisor-decision tables to the existing bridge SQLite database; it does not create a second queue or worker. O1F adds a reusable fail-closed authority and workspace-diff guard while leaving the bounded code-changing route inactive.

The mission ledger is operational state only. Repository documents and governed product records remain canonical product authority. The mission charter was read from the private Google Doc and confirmed inert: it records supervisory intent, not executable authority.

The managed launcher, watcher, raw private Drive ingress, existing instruction claim ledger and immutable result/report publication path were reused. The active watcher was not stopped, restarted or modified in place.

## 2. Components

New components:

- `src/charitygraph/mission_ledger.py` — versioned O1E contract, append-only event sequence, review cursor, CAS review/dispatch claims, idempotent decisions, execution evidence, stop/escalation states and Supervisor Brief.
- `src/charitygraph/bounded_authority.py` — O1F exact-target validation, inactive-route rejection, workspace snapshot and bounded dirty-diff guard.
- `tests/test_double_loop_harness.py` — provider-free O1E/O1F acceptance tests.

Integrated components:

- `src/charitygraph/autonomous_loop.py` initializes and exposes the O1E ledger on the same SQLite database.
- `bridge/bridge.py` delegates bounded implementation validation to the O1F guard while retaining the existing inactive-route fail-closed behavior.

## 3. Mission and review schemas

O1E uses these durable tables in the existing `bridge.sqlite3`:

- `missions`: versioned contract, stable mission/tranche/instruction/run/review identifiers, repository branch and HEAD, state and contract hash.
- `mission_events`: append-only per-mission sequence, idempotent `event_key`, event payload hash and timestamp.
- `review_cursors`: reviewer-specific durable evidence cursor and last decision.
- `supervisor_claims`: compare-and-swap `review` and `dispatch` claims with owner, token, version and lease.
- `supervisor_decisions`: immutable review decision with separate execution and semantic/product dispositions.

Execution events retain instruction/result hashes, repository identity and immutable report references. Duplicate event and decision ingestion with identical bytes is idempotent; changed bytes are rejected.

## 4. O1F authority boundary

The prepared authority is:

`charitygraph.g4-o1d-local-implementation/v1`

Scope:

`bounded_local_builder_code_change`

The route remains `INACTIVE`. Bounded instructions require the exact ChatGPT authority envelope, workspace, branch, HEAD, `luna-high` model, relative allowed paths, `local_commit_only`, fresh report path and explicit bounded execution fields. Inactive-route rejection occurs before the instruction is claimed.

The workspace guard snapshots branch, HEAD, dirty entries, file hashes and tracked diff hashes. It rejects unexpected paths and any mutation of pre-existing dirty paths. `report_only` remains a separate narrow execution policy and rejects bounded authority fields.

## 5. Tests

Command:

```text
python -m pytest tests/test_autonomous_loop.py tests/test_bridge_cutover.py tests/test_double_loop_harness.py -q -p no:cacheprovider -o addopts=''
```

Result: **22 passed, 1 skipped**. The skip is the existing explicit real-Codex opt-in rehearsal.

Covered evidence includes:

- mission start and duplicate contract idempotence;
- append-only sequencing and duplicate/changed event handling;
- competing review and dispatch claims with CAS conflicts;
- review cursor persistence after reopening the same SQLite database;
- duplicate review idempotence and backwards-cursor rejection;
- exact execution/result/report/head identity and stale-HEAD rejection;
- explicit stop and escalation states;
- inactive bounded-route rejection;
- report-only compatibility;
- dirty-baseline preservation and allowed-path enforcement;
- existing adapter exactly-once, interruption quarantine and replay-safety tests;
- historical completed duplicate reconciliation before stale-HEAD verification;
- production bridge poll entrypoint, terminal telemetry, heartbeat/deduplication and fence tests.

Static AST parsing and `git diff --check` also passed.

## 6. Restart, idempotence and competing-supervisor proof

The O1E tests close and reopen the same SQLite database, then recover the mission state, latest decision and reviewer cursor. Identical event and decision delivery returns the existing durable record; changed bytes fail closed. A second review or dispatch claimant cannot acquire an active claim, and stale expected versions are rejected.

The existing instruction ledger continues to provide exactly-once execution and explicit ambiguous-interruption quarantine. No live instruction was created or replayed by this tranche.

## 7. Current managed state

The active managed pair was safely reloaded only after the failed pair had exited,
the ledger was proven terminal-only and fence v11 matched the final commit:

- launcher PID: `21616`
- watcher PID: `396`
- watcher instance: `g4-o1b-396-75fee3dc2112`
- watcher state: `READY`
- branch: `gate3-cg406-remediation`
- HEAD: `064c783e283d7431ce0ce95b8eeb190789acefa9`
- file-based runtime fingerprint: `ff502c4406305fc4d19e81b3151ebbe427bd4971c12a833f6e2e1dd1a0d4b24e`
- code-change route: inactive
- heartbeat: 120 seconds

The current status records the completed provider-free A3E rehearsal as its latest terminal result. The prior O1D supervisory acceptance is also terminal. No active or ambiguous execution was found in the bridge ledger. All five durable instructions have one attempt and `complete` status.

The first restart after the commit failed closed because v7 targeted the prior HEAD. A second attempt exposed that historical completed instructions were being target-verified before duplicate detection; that replay-safety defect was repaired. The final controlled restart used the supported launcher under the Windows identity with Drive status access. An 8-second idle sample was byte-for-byte unchanged: publication sequence `1` to `1`, mtime unchanged, state `READY`.

## 8. Fence and safety confirmation

Fence v7 remains untouched historical evidence. Fence v11 is `ACTIVE`, targets the current branch and HEAD, and supersedes v10. Its private Drive copy is [cg-g4-o1b-dormant-state-fence-20261020-v11.json](https://drive.google.com/file/d/1nszcsALIBpyHKqJlpNX_PnQyYKB-WBTS/view?usp=drivesdk); local and Drive Desktop bytes match at 2,687 bytes with SHA-256 `f1e7ff71ee693b947f26c0f6105a50a6e52e1a9f67a078201c681f89e7807b94`. Technical specification `007` and campaign `403` remain excluded. Historical deletion and modification counts remain zero. The watcher continues to ignore the legacy queue, supervisor inbox, technical-spec Markdown and campaign/tranche state.

No provider calls, source acquisition, GitHub mutation, Drive reconfiguration, destructive history operation, new watched instruction or successor tranche was performed.

## 9. Local commit

The intended implementation files are committed in one scoped local commit. Unrelated pre-existing dirty documentation, evidence and report files were not staged.

**Commit:** `064c783e283d7431ce0ce95b8eeb190789acefa9`

## 10. Next supervisory certification procedure

The supervising ChatGPT conversation must independently review this report and, if satisfied, originate one fresh canonical raw Drive instruction. This session must not create it and must not activate the route.

Required envelope shape:

```json
{
  "schema_version": "charitygraph.autonomous-instruction/v1",
  "instruction_id": "gate4:engineering:20261021-o1f-bounded-certification",
  "authority": {
    "source": "chatgpt",
    "approved": true,
    "authority_envelope": "gate4-engineering"
  },
  "target": {
    "repository": "charitygraph",
    "workspace_path": "C:\\CharityGraph-clean\\charitygraph",
    "branch": "gate3-cg406-remediation",
    "head": "064c783e283d7431ce0ce95b8eeb190789acefa9",
    "model": "luna-high"
  },
  "operation": "codex_engineering",
  "execution": {
    "mode": "codex_exec",
    "change_policy": "bounded_workspace",
    "model": "luna-high",
    "report_path": "reports/G4_O1F_BOUNDED_CERTIFICATION_20261021.md",
    "timeout_seconds": 300,
    "authority_version": "charitygraph.g4-o1d-local-implementation/v1",
    "scope": "bounded_local_builder_code_change",
    "allowed_paths": ["<one harmless approved implementation path>", "<one corresponding test path>"],
    "commit_policy": "local_commit_only"
  },
  "content": "Perform one provider-free harmless bounded local code change exactly within the two approved paths. Preserve the dirty baseline, verify branch and full HEAD, run the focused tests, write exactly the fresh report, create only one local commit, and do not call providers, acquire sources, mutate GitHub, alter dormant evidence, dispatch follow-on work or close a gate.",
  "content_sha256": "<SHA-256 of exact UTF-8 content>",
  "created_at": "<supervising ChatGPT timestamp>"
}
```

Acceptance criteria are: one fresh canonical file; exact target identity; no active or ambiguous worker; route activation explicitly authorized outside this session; unchanged pre-existing dirty baseline; only the allowed paths changed; one local commit; private result and report hashes; duplicate polling produces no replay; `report_only` remains unchanged; and fence v7, spec `007` and campaign `403` remain untouched. A failure or uncertain physical execution must be quarantined and reconciled, never replayed automatically.

## 11. O1G/O1H dependencies and risks

O1G is not implemented. It requires a separately fenced namespace, finite task/attempt/time budgets, dependency-aware serial execution, pause/resume, zero unapproved provider spend and ambiguous-execution quarantine.

O1H is not implemented or certified. It requires two genuine hourly scheduled ChatGPT review cycles with live Drive/GitHub access, independent North Star/public-web challenge, durable cursor evidence and safe successor dispatch. Scheduled model/tool availability must be verified rather than assumed. The current hourly supervisor remains read-only.

The principal immediate risk is that O1G/O1H remain uncertified. The live O1E mission tables are explicit opt-in state on the same bridge SQLite database; watcher startup does not acquire a schema migration lock. Supervisory certification must precede bounded-route activation.
