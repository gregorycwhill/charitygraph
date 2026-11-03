# CG-G4-P2 corrected independent product acceptance

Review instruction: `20261025-g4-p2-sol-acceptance-corrected-v2`  
Mode: `REPORT_ONLY`; provider-free local review only.  
Date: 2026-10-25 (Australia/Sydney)

## Disposition

**PARTIAL — the bounded governed Factory workflow passes, with one durable-catalogue boundary limitation.**

The corrected P2 change is present at the expected hashes. `FactoryPlan.packages()` and `physical_packages()` isolate subject and scope, and the real governed-reference → preflight → `FactoryPlan` → `ReferenceFactory` → `SQLiteCatalog` path passes the focused provider-free tests. Reopening and rerunning does not create duplicate physical attempts, receipts or cost entries; ambiguous sends remain held; synthetic accounting reconciles.

The limitation is material but bounded: the physical-attempt table has no `scope_id`. Scope is recoverable through persisted task members, and the governed Factory path only constructs same-scope packages, but `SQLiteCatalog.prepare_physical_attempt()` checks member run and subject only. An independent temporary-catalog probe accepted a directly supplied mixed-scope member set. Therefore this review does not claim a self-enforcing scope invariant at the lower catalog API boundary.

This is not a global safety stop. The fence, branch, HEAD, tree, governance authority, protected source paths and expected P2 hashes all matched. No provider, model, acquisition, external source, Git, bridge or watcher operation occurred.

## Authoritative fence and workspace control

Fence read independently, outside the checkout:

`C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\cg-g4-o1b-dormant-state-fence-20261020-v23.json`

| Check | Result |
|---|---|
| Fence SHA-256 | `8d58d6acccaa5933075a1492e0974fc6a1080868d78b3e58532a351b5cb5c342` |
| Fence state/version | `ACTIVE` / `23` |
| Branch | `gate3-cg406-remediation` |
| HEAD | `21bb0e621f2a1c52f19b59f261d71009defa4843` |
| HEAD tree | `f5851e02afab398326e145a34d142d9de5fe1a58` |
| Fence controls | provider calls `0`; GitHub mutation `false`; publication `false`; gate closure `false` |

The required report path was absent before this task. The external supervisor catalogue was read rather than treating its raw count as authoritative by itself:

- catalogue dirty paths: `342`;
- current `git status --porcelain=v1 -uall` records before tests: `262`;
- catalogue-only paths: exactly `80`;
- current paths absent from catalogue: `0`;
- all 80 catalogue-only paths are under `CharityGraph-cleancharitygraphtmppytest-bridge-recovery/`;
- stable catalogue/status identity sets: equal at `262` paths.

Git emitted access-denied warnings for the known synthetic temporary areas. These paths are inaccessible/ephemeral historical test material, not protected product, governance, evidence or report paths. They were not searched for repair, deleted, restored, cleaned or touched. The prior acceptance-v1 report remains terminal historical evidence and was not replayed or overwritten.

The local and sibling authority review covered `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, the current P2/P1 reports and archaeology, and the sibling Data repository's `DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, `ROADMAP.md`, `IMPLEMENTATION_PLAN.md`, `TEST_PLAN.md`, `INTEGRATED_PRODUCT_AND_DATA_MODEL.md`, `SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`, `TAXONOMY_AND_SCHEME_GOVERNANCE.md`, `COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`, `SEMANTIC_HEURISTIC_APPROVALS.md` and source-rights audit/clearance material. No semantic heuristic or new acquisition path is involved.

## Scoped source/test identity and diff

Current SHA-256 values match the task authority exactly:

```text
dc7f335873789c31f016351c9dccd20f04f7ed002689d0e6dd36b981ab100dfe  src/charitygraph/phase5_factory.py
ef7498153ef1d13b55bfd052c6c6f5aac3e88e85ccc6aeba62b4ba8cca0d1828  tests/test_phase5_factory.py
2912b5813743b8da6f8bced353559f4209896c8f3339952e5b2d866943f192e0  tests/test_phase5_governed_factory_integration.py
```

Scoped diffstat relative to full HEAD: **101 insertions, 11 deletions**; per file `6/6`, `13/0`, and `82/5` additions/deletions. The complete scoped unified diff follows.

```diff
diff --git a/src/charitygraph/phase5_factory.py b/src/charitygraph/phase5_factory.py
index d89c937..e0ffdb8 100644
--- a/src/charitygraph/phase5_factory.py
+++ b/src/charitygraph/phase5_factory.py
@@ -1,124 +1,124 @@
 """Isolated provider-free Factory orchestration for approved Phase-5 plans."""
 from __future__ import annotations
 
 import hashlib
 from decimal import Decimal
 from datetime import datetime, timedelta, timezone
 from collections import defaultdict
 from dataclasses import dataclass
 from typing import Any
 from .contracts.ids import deterministic_id
 from .phase5_delivery import DeliveryPolicy
 
 
 @dataclass(frozen=True)
 class FactoryPlan:
     logical_tasks: tuple[dict[str, Any], ...]
 
     @classmethod
     def from_manifest(cls, items: list[dict[str, Any]]) -> "FactoryPlan":
         ordered = tuple(sorted(items, key=lambda item: item["logical_task_id"]))
         ids = [item["logical_task_id"] for item in ordered]
         if len(ids) != len(set(ids)):
             raise ValueError("planned logical task identities must be unique")
         return cls(ordered)
 
     @property
     def manifest_hash(self) -> str:
         return hashlib.sha256("\n".join(item["logical_task_id"] for item in self.logical_tasks).encode()).hexdigest()
 
     def packages(self) -> tuple[tuple[dict[str, Any], ...], ...]:
         """Package only same-subject compatible opportunities; IDs stay logical."""
-        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
+        groups: dict[tuple[str, str | None, str], list[dict[str, Any]]] = defaultdict(list)
         for item in self.logical_tasks:
-            groups[(item["subject_id"], item.get("physical_bundle_opportunity") or item["logical_task_id"])].append(item)
-        return tuple(tuple(sorted(group, key=lambda item: item["logical_task_id"])) for _, group in sorted(groups.items()))
+            groups[(item["subject_id"], item.get("scope_id"), item.get("physical_bundle_opportunity") or item["logical_task_id"])].append(item)
+        return tuple(tuple(sorted(group, key=lambda item: item["logical_task_id"])) for _, group in sorted(groups.items(), key=lambda pair: (pair[0][0], pair[0][1] or "", pair[0][2])))
 
     def physical_packages(self, *, delivery_mode: str = "standard") -> tuple[tuple[dict[str, Any], ...], ...]:
         """Only semantic work is batchable; deterministic work stays single-task."""
         if delivery_mode not in {"batch", "flex", "standard"}: raise ValueError("unknown delivery mode")
-        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
+        groups: dict[tuple[str, str | None, str, str], list[dict[str, Any]]] = defaultdict(list)
         for item in self.logical_tasks:
             kind = "single" if item.get("difficulty") == "deterministic" else (item.get("physical_bundle_opportunity") or item["logical_task_id"])
-            groups[(item["subject_id"], kind, delivery_mode)].append(item)
-        return tuple(tuple(sorted(group,key=lambda item:item["logical_task_id"])) for _,group in sorted(groups.items()))
+            groups[(item["subject_id"], item.get("scope_id"), kind, delivery_mode)].append(item)
+        return tuple(tuple(sorted(group,key=lambda item:item["logical_task_id"])) for _,group in sorted(groups.items(), key=lambda pair: (pair[0][0], pair[0][1] or "", pair[0][2], pair[0][3])))
 
     def runtime_tasks(self, *, cohort_id: str) -> tuple[dict[str, Any], ...]:
         tasks=[]
         for item in self.logical_tasks:
             model_task = item.get("_model_task")
             cache = getattr(model_task, "cache_key", None) or hashlib.sha256(item["logical_task_id"].encode()).hexdigest()
             runtime = {"record_id": model_task.record_id if model_task is not None else deterministic_id("modeltask:", {"logical_task_id": item["logical_task_id"]}), "subject_id":item["subject_id"], "scope_id":item.get("scope_id"), "cohort_id":cohort_id, "task_type":"structured_extraction", "task_schema":{"schema_id":"urn:charitygraph:phase5:rehearsal:1"}, "cache_key":cache, "provider_id":"fake", "model_snapshot":"phase5-rehearsal-v1", "logical_task_id":item["logical_task_id"], "difficulty":item["difficulty"]}
             for key in ("source_definition_ids", "acquisition_receipt_ids", "source_record_ids", "evidence_locator_ids", "representation_artifact_ids", "representation_hashes", "rights_policy_ids", "rights_roles", "governed_reference_hash"):
                 if key in item:
                     runtime[key] = item[key]
             if model_task is not None:
                 runtime["model_task"] = model_task
             tasks.append(runtime)
         return tuple(tasks)
 
 
 @dataclass(frozen=True)
 class FakeProviderReceipt:
     request_id: str
     receipt_id: str
     raw_result_ref: str
     usage: dict[str, int]
 
 
 class RehearsalFakeProvider:
     """Network-free provider seam; it exposes no knowledge-producing output."""
     provider_id = "fake"
     tariffs = {"batch": "0.000500", "flex": "0.001000", "standard": "0.002000"}
     def execute(self, task: dict[str, Any], *, delivery_mode: str = "batch") -> FakeProviderReceipt:
         if delivery_mode not in self.tariffs: raise ValueError("unknown rehearsal delivery mode")
         request = "fake-request:" + task["cache_key"]
         return FakeProviderReceipt(request, "fake-receipt:" + hashlib.sha256(request.encode()).hexdigest(), "rehearsal-result:" + task["cache_key"], {"input_tokens": 1, "output_tokens": 1})
 
     def receipt_for_package(self, package_id: str, *, delivery_mode: str) -> FakeProviderReceipt:
         """Deterministic local stand-in for a provider receipt or later reconciliation lookup."""
         if delivery_mode not in self.tariffs: raise ValueError("unknown rehearsal delivery mode")
         request = "fake-package-request:" + hashlib.sha256(package_id.encode()).hexdigest()
         token = hashlib.sha256((package_id + delivery_mode).encode()).hexdigest()
         return FakeProviderReceipt(request, "fake-receipt:" + token, "rehearsal-result:" + token, {"input_tokens": 1, "output_tokens": 1})
 
     def execute_package(self, package_id: str, *, delivery_mode: str) -> FakeProviderReceipt:
         """The only fake send boundary; it exposes no semantic content."""
         return self.receipt_for_package(package_id, delivery_mode=delivery_mode)
 
 
 class FactoryInterrupted(RuntimeError):
     """Deliberate process-loss simulation after a durable recovery boundary."""
 
 
 class AmbiguousSendError(RuntimeError):
     """A send was durably started but no receipt is persisted; never auto-resend."""
 
 
 class ReferenceFactory:
     """Synchronous isolated runner; fake-only and never a knowledge producer."""
     def __init__(self, catalog: Any, plan: FactoryPlan, *, cohort_id: str, run_id: str, provider: RehearsalFakeProvider | None = None, delivery_mode: str | None = None, delivery_policy: DeliveryPolicy | None = None) -> None:
         self.catalog, self.plan, self.cohort_id, self.run_id = catalog, plan, cohort_id, run_id
         self.provider = provider or RehearsalFakeProvider()
         self.delivery_policy = delivery_policy or DeliveryPolicy.build()
         requested = {"delivery_mode": delivery_mode} if delivery_mode is not None else {}
         self.delivery_mode = self.delivery_policy.resolve(requested)
         self.interruptions_observed: list[str] = []
     def seed(self, now: datetime) -> tuple[dict[str, Any], ...]:
         tasks=self.plan.runtime_tasks(cohort_id=self.cohort_id)
         for task in tasks: self.catalog.register_task(task.get("model_task", task), run_id=self.run_id, now=now)
         return tasks
     def _physical_id(self, package_id: str) -> str:
         return "physical:" + package_id.split(":", 1)[1]
 
     def _claim_package(self, tasks: tuple[dict[str, Any], ...], *, now: datetime) -> bool:
         owner="phase5-factory-reference"
         for task in tasks:
             state=self.catalog.get_task(task["record_id"])
             if state["status"] == "succeeded":
                 continue
             if state["status"] == "leased" and state["lease_owner"] == owner:
                 continue
             if not self.catalog.claim_task(task["record_id"], owner=owner, lease_expires_at=now+timedelta(hours=1), now=now):
                 return False
         return True
```

The remaining two scoped files have the following complete materially changed hunks. Unchanged context omitted here is 78 lines in `tests/test_phase5_factory.py` and 254 lines in `tests/test_phase5_governed_factory_integration.py`; the exact file hashes and diffstat above identify the reviewed files.

```diff
--- a/tests/test_phase5_factory.py
+++ b/tests/test_phase5_factory.py
@@ -1,78 +1,91 @@
+def test_factory_plan_keeps_distinct_scopes_out_of_logical_and_physical_packages() -> None:
+    plan = FactoryPlan.from_manifest([
+        {"logical_task_id": "a", "subject_id": "subject:one", "scope_id": "scope:one", "physical_bundle_opportunity": "bundle:x"},
+        {"logical_task_id": "b", "subject_id": "subject:one", "scope_id": "scope:one", "physical_bundle_opportunity": "bundle:x"},
+        {"logical_task_id": "c", "subject_id": "subject:one", "scope_id": "scope:two", "physical_bundle_opportunity": "bundle:x"},
+        {"logical_task_id": "d", "subject_id": "subject:two", "scope_id": "scope:three", "physical_bundle_opportunity": "bundle:x"},
+    ])
+
+    expected = {frozenset({"a", "b"}), frozenset({"c"}), frozenset({"d"})}
+    assert {frozenset(item["logical_task_id"] for item in package) for package in plan.packages()} == expected
+    assert {frozenset(item["logical_task_id"] for item in package) for package in plan.physical_packages(delivery_mode="batch")} == expected
--- a/tests/test_phase5_governed_factory_integration.py
+++ b/tests/test_phase5_governed_factory_integration.py
@@ -1,259 +1,336 @@
-def _fixture(tmp_path, suffix: str = "1", *, scope: bool = True, catalog=None, store=None):
+def _fixture(tmp_path, suffix: str = "1", *, subject_suffix: str | None = None, scope_suffix: str | None = None, scope: bool = True, catalog=None, store=None):
     catalog = catalog or SQLiteCatalog(tmp_path / f"catalog-{suffix}.sqlite3").open(initialize=True)
     store = store or ContentAddressedArtifactStore(tmp_path / f"objects-{suffix}", catalog=catalog)
-    subject_id = "subject:" + suffix * 32
+    subject_suffix = subject_suffix or suffix
+    scope_suffix = scope_suffix or suffix
+    subject_id = "subject:" + subject_suffix * 32
     catalog.register_subject(_subject(subject_id))
     scope_id = None
     if scope:
-        scope_id = "scope:" + suffix * 32
+        scope_id = "scope:" + scope_suffix * 32
@@
-    result = preflight_governed_references(variants, catalog=catalog)
-    assert result.accepted_count == 0
+    result = preflight_governed_references([reference, *variants], catalog=catalog, retained_bytes=lambda _: b"represented source 1")
+    assert result.accepted_count == 1
+    assert len(result.tasks) == 1
@@
+def test_governed_factory_isolates_scopes_and_subjects_in_durable_physical_work(tmp_path):
+    catalog, store, reference_a, representation_a = _fixture(tmp_path, "1")
+    _, _, reference_same_scope, representation_same_scope = _fixture(
+        tmp_path, "1b", subject_suffix="1", scope_suffix="1", catalog=catalog, store=store
+    )
+    _, _, reference_other_scope, representation_other_scope = _fixture(
+        tmp_path, "1c", subject_suffix="1", scope_suffix="1c", catalog=catalog, store=store
+    )
+    _, _, reference_other_subject, representation_other_subject = _fixture(
+        tmp_path, "2", catalog=catalog, store=store
+    )
+    references = [reference_a, reference_same_scope, reference_other_scope, reference_other_subject]
+    bodies = {
+        representation_a.artifact_id: b"represented source 1",
+        representation_same_scope.artifact_id: b"represented source 1b",
+        representation_other_scope.artifact_id: b"represented source 1c",
+        representation_other_subject.artifact_id: b"represented source 2",
+    }
+
+    preflight = preflight_governed_references(references, catalog=catalog, retained_bytes=bodies.__getitem__)
+    assert preflight.accepted_count == 4
+    assert not preflight.diagnostics
+    assert {task["scope_id"] for task in preflight.tasks if task["subject_id"] == reference_a.subject_id} == {
+        reference_a.scope_id, reference_other_scope.scope_id
+    }
+    assert len({task["logical_task_id"] for task in preflight.tasks}) == 4
+
+    cohort_id, run_id = _run(catalog, "5", "5")
+    runner = ReferenceFactory(catalog, preflight.factory_plan, cohort_id=cohort_id, run_id=run_id)
+    runtime_tasks = runner.seed(NOW)
+    packages = runner.plan.physical_packages()
+    assert {(package[0]["subject_id"], package[0]["scope_id"], len(package)) for package in packages} == {
+        (reference_a.subject_id, reference_a.scope_id, 2),
+        (reference_other_scope.subject_id, reference_other_scope.scope_id, 1),
+        (reference_other_subject.subject_id, reference_other_subject.scope_id, 1),
+    }
+    assert runner.run(NOW) == 4
+
+    with catalog._connection() as conn:
+        member_rows = conn.execute(
+            """
+            SELECT pam.physical_attempt_id, t.subject_id, t.scope_id
+            FROM physical_attempt_members pam
+            JOIN tasks t ON t.model_task_id = pam.model_task_id
+            ORDER BY pam.physical_attempt_id, pam.model_task_id
+            """
+        ).fetchall()
+        attempt_count = conn.execute("SELECT COUNT(*) FROM physical_attempts").fetchone()[0]
+        receipt_count = conn.execute("SELECT COUNT(*) FROM provider_receipts").fetchone()[0]
+        cost_count = conn.execute("SELECT COUNT(*) FROM cost_entries").fetchone()[0]
+    members_by_attempt = {}
+    for row in member_rows:
+        members_by_attempt.setdefault(row[0], []).append((row[1], row[2]))
+    assert attempt_count == receipt_count == 3
+    assert cost_count == 6  # one actual and one release entry per physical package
+    assert all(len({subject_id for subject_id, _ in members}) == 1 for members in members_by_attempt.values())
+    assert all(len({scope_id for _, scope_id in members}) == 1 for members in members_by_attempt.values())
+    assert any(len(members) == 2 for members in members_by_attempt.values())
+
+    catalog.close()
+    reopened = SQLiteCatalog(catalog.path).open()
+    rerun = ReferenceFactory(reopened, preflight.factory_plan, cohort_id=cohort_id, run_id=run_id)
+    rerun.seed(NOW)
+    assert rerun.run(NOW) == 0
+    with reopened._connection() as conn:
+        assert conn.execute("SELECT COUNT(*) FROM physical_attempts").fetchone()[0] == attempt_count
+        assert conn.execute("SELECT COUNT(*) FROM provider_receipts").fetchone()[0] == receipt_count
+        assert conn.execute("SELECT COUNT(*) FROM cost_entries").fetchone()[0] == cost_count
+    position = reopened.budget_position(cohort_id)
+    assert position.outstanding_reserved_exposure_aud == Decimal("0.000000")
+    assert position.actual_spend_aud == Decimal("0.006000")
+    assert position.breach is False
```

The new unit test and the new governed integration test would both have failed against the old P1 scope-mixing grouping keys.

## Acceptance matrix

| Bounded criterion | Result | Evidence / limitation |
|---|---|---|
| Fence, branch, HEAD, tree and protected-path control | PASS | Independent v23 read and stable-path reconciliation above. |
| Expected P2 source/test identities | PASS | All three SHA-256 values match. |
| `packages()` and `physical_packages()` scope compatibility | PASS | Scope is included in both keys; deterministic sorting includes subject, `scope_id` with `None` normalization, opportunity/kind and delivery mode. |
| Same-subject/same-scope bundling | PASS | Unit and governed integration assertions bundle two compatible members. |
| Distinct-scope and distinct-subject isolation | PASS in governed Factory path | Integration produced three physical attempts for four accepted references; every persisted member set had one subject and one scope. |
| Source/evidence/representation lineage into durable tasks | PASS | Synthetic source definition, acquisition receipt, source record, raw and derived content-addressed artifacts, derived-from input, evidence locator, governed reference, rights role and task evidence were exercised. |
| Differentiated unavailable/blocked/invalid/missingness | PASS | Eight explicit diagnostic states remained distinct and produced no fabricated task/evidence; one accepted peer still lowered to one task. |
| Durable task/receipt lifecycle and independent failure isolation | PASS | Real `SQLiteCatalog` path, terminal child states, one receipt per physical package and successful peer not repeated. |
| Reopen/rerun idempotence | PASS | Zero additional physical attempts, receipts or cost entries on rerun. |
| Ambiguous send handling | PASS | `send_started` remains held for explicit reconciliation; no blind resend. |
| Synthetic reservation/actual/release/AUD reconciliation | PASS | Three actual plus three release entries; actual `AUD 0.006000`; outstanding reserve `AUD 0.000000`; breach `False`. |
| Physical-attempt scope self-description/enforcement | PARTIAL | `physical_attempts` has no `scope_id`; member-task joins preserve scope, but direct catalog insertion accepted mixed scopes because only run and subject were checked. |

The lower-catalog limitation does not invalidate the tested governed Factory route, which derives physical members from scope-aware `FactoryPlan` packages and preserves scope in `tasks`. It does mean a future durable catalogue hardening change should either enforce same-scope members in `prepare_physical_attempt()` or add an explicit physical scope identity; that is outside this REPORT_ONLY task.

## Commands and results

All pytest invocations used `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`, `-p no:cacheprovider`, and a fresh basetemp under `C:\CharityGraph-runtime`; each destination was verified absent before use.

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p2-acceptance-corrected-20261025 tests/test_phase5_preflight.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py tests/runtime/test_source_evidence.py tests/runtime/test_budget_ledger.py
37 passed in 8.98s

$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-p2-acceptance-corrected-20261025-additional tests/test_phase5_batch_bytes_and_attempts.py tests/test_phase5_delivery.py tests/runtime/test_task_state.py tests/runtime/test_cache_and_artifacts.py
31 passed in 8.27s

git diff --check HEAD -- src/charitygraph/phase5_factory.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py
exit 0
```

Independent temporary-catalog probe result:

```text
mixed_scope_catalog_accepts=True
physical_attempt_has_scope_id=False
physical_status=prepared
persisted_member_scopes=['scope:11111111111111111111111111111111', 'scope:22222222222222222222222222222222']
```

Probe and pytest state were written only under new external directories beginning `C:\CharityGraph-runtime\cg-g4-p2-acceptance-corrected-20261025`; no runtime SQLite, cache or temporary state was written in the checkout.

## Post-run delta and exclusions

Before tests, status had `262` records. After both pytest runs and the catalog probe, status still had `262` records and the branch/HEAD/tree remained unchanged. After this report was created, the only new checkout path is:

```text
?? reports/G4_P2_SOL_ACCEPTANCE_REVIEW_CORRECTED_20261025.md
```

The three pre-existing P2 source/test modifications and every other pre-existing stable tracked/untracked path remain unchanged; no files were staged. No raw/private evidence, prompts, model responses, credentials, logs, watchers, bridge state, providers, APIs, external sources, spending, publication, commit, GitHub mutation, merge, release, gate closure or follow-on dispatch was performed. This report separates bridge-process history from independently supportable product acceptance.
