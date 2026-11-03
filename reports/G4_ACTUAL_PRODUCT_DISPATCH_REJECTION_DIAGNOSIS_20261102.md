# Gate 4 actual product dispatch rejection diagnosis

Read-only diagnosis at 2026-11-02. No bridge, watcher, Git, product code, test,
Drive, fence, ledger, provider or source state was changed. This report is the
only workspace artifact written by this task.

## Proven local state

- Branch: `gate3-cg406-remediation`.
- HEAD: `b6c9f30c98dd01978c7df3a937cd7e9001023f23`.
- Status: `runtime/g4-o1b-controlled-cutover-20261020/status.json` reports
  `watcher_state=EXECUTING`, the current diagnosis instruction active, and
  fence path `.../cg-g4-o1b-dormant-state-fence-20261020-v101.json`. The v101
  fence is not present in the repository workspace; only historical local
  fence files are present, so its bytes/hash could not be independently read
  here.
- Claim count: 1 active row in the read-only SQLite catalogue
  `runtime/g4-o1b-controlled-cutover-20261020/bridge/bridge.sqlite3`; it is
  this diagnosis instruction. The two named instructions have no catalogue
  row or claim.

## Correlation result

The following exact IDs were searched for, including their stated times:

| rejection time (UTC) | immutable instruction ID |
|---|---|
| `2026-11-02T10:36:48.760909Z` | `gate4:engineering:20261102-g4-t3-t4d-factory-fix-three-failures-v101-sol-20261102T103510Z-d3fb89ad` |
| `2026-11-02T10:44:32.085749Z` | `gate4:engineering:20261102-g4-t4d-mixed-scope-factory-guard-v101-sol-20261102T104245Z-7c25a1e0` |

Neither ID occurs in the local `bridge/inbox`, `bridge/results`, runtime text
logs, SQLite `instructions`, or SQLite `events`. SQLite currently contains
203 instruction rows and 809 events. Its only `rejected_input` event is the
older 2026-10-28 provenance-adoption rejection, with message:
`stale target identity: observed gate3-cg406-remediation@739e7da9515eb2a0435d6632d6bb8b2ad3d29767`.
Therefore the exact rejection message and immutable envelope fields for the
two 2026-11-02 attempts are not recoverable from the permitted local evidence.

## What the local bridge proves

`bridge/bridge.py` validates engineering admission before ledger import
(`_process_candidate`, lines 1445-1450). `_validate_engineering` captures and
validates the workspace/target/authority and, for `bounded_workspace`, calls
`validate_clean_commit_paths` before import (lines 731-742 and 788-796).
The preclaim exception path emits `rejected_input` without a worker; when no
matching pending row already exists, it also has no durable result to mirror
(lines 1456-1506). This exactly explains the reported shape, but does not
identify which missing envelope field failed.

The bounded route is active in `src/charitygraph/bounded_authority.py`.
However, the current checkout has pre-existing modifications in the Factory
implementation/tests, including:

- `src/charitygraph/phase5_factory.py`
- `src/charitygraph/phase5_governed_factory_integration.py`
- `src/charitygraph/phase5_t4d_e3_factory_handoff.py`
- the corresponding three `tests/test_phase5_*.py` files

For an ordinary bounded repair whose exact allowlist includes any such path,
the proven preclaim rule is:
`ordinary commit path was pre-dirty or staged: <path>`
(`validate_clean_commit_paths`, lines 278-291). Scope, authority, schema and
timing rejection cannot be proven for either missing envelope.

## Smallest correction

There is no evidence here for a bridge defect or an inactive code-change
route. The smallest safe correction is to make the exact Factory repair
allowlist clean at the target HEAD before issuing a fresh bounded instruction;
the bridge must not bypass the preclaim check. If the approved repair is meant
to touch the currently dirty tracked Factory paths, those edits require
supervisor-controlled reconciliation/clean-baseline handling first. No replay,
resubmission, repair or mutation of either rejected instruction was attempted.
