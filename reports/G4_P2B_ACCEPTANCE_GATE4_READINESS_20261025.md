# G4-P2b independent acceptance, Gate 4 readiness and P3 authority archaeology

Date: 2026-10-25 (Australia/Sydney)  
Mode: REPORT_ONLY; provider-free local repository audit.  
Verdict: **P2b PARTIAL overall** — PASS for the direct catalogue guard and the current governed preflight/Factory path, with a material residual risk in lower-level append-only replacement paths. **Gate 4 is not closed. P3 is not implemented.**

## 1. Control, fence and protected-work proof

The required report path was absent before this task. Exact control identity:

| Control | Result |
|---|---|
| workspace | C:\CharityGraph-clean\charitygraph |
| branch | gate3-cg406-remediation |
| HEAD | 21bb0e621f2a1c52f19b59f261d71009defa4843 |
| HEAD tree | f5851e02afab398326e145a34d142d9de5fe1a58 |
| active fence | C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\cg-g4-o1b-dormant-state-fence-20261020-v23.json |
| fence SHA-256 | 8d58d6acccaa5933075a1492e0974fc6a1080868d78b3e58532a351b5cb5c342 |
| fence state | ACTIVE, version 23; provider calls 0; GitHub mutation false; publication false; gate closure false |

All preconditions matched exactly. No watcher, bridge, provider, external source, GitHub, Git, publication or release action was used. The supervisor catalogue declares 346 dirt paths; visible local git status had 266 records. Git emitted access-denied warnings for the known 80 synthetic pytest-bridge-recovery identities under the CharityGraph-cleancharitygraphtmppytest-bridge-recovery/ and CharityGraph-runtimecg405-pytest/ prefixes. Raw-count equality was not treated as proof; stable identities and hashes were used.

Pre-existing tracked dirt was preserved, including the P2 Factory/test paths and src/charitygraph/runtime/catalog.py and tests/runtime/test_task_state.py. The only new checkout path made by this task is this report.

## 2. Independent P2b acceptance

Reviewed historical evidence:

- reports/G4_P2B_CATALOG_SCOPE_GUARD_20261025.md — SHA-256 f2bcdbd10fedaa822af970551ce26e03f64271de4d61d59ee886cc34bf28f464.
- reports/G4_P2_SOL_ACCEPTANCE_REVIEW_CORRECTED_20261025.md — SHA-256 682c65e13b20433b2a66a7ef858a0f0b954c525c1439289b85687d371a705344.
- reports/G4_P2_GOVERNED_SCOPE_ISOLATION_CORRECTED_20261025.md — SHA-256 48236a0e8f324c06d8e35ad04487912d51bc86e6381b331f0c2bc8ab65b2a068.

Current hashes match the task authority:

```text
7e1bd2d19732102f9840a6c7ce1a55c95042ef4d88b874cd3a6ef43aa49c4020  src/charitygraph/runtime/catalog.py
5804053f05619604896ace5f0149c2442c46dfdbaa3491811dc1a60844c8e42f  tests/runtime/test_task_state.py
e3f8a6c1566e7241f6bf10d2203fd49454b6b5a147befbacc72e6c22223f176a  tests/test_phase5_batch_bytes_and_attempts.py
```

### Finding and case matrix

SQLiteCatalog.prepare_physical_attempt() at src/charitygraph/runtime/catalog.py:3873-3898 runs inside the existing BEGIN IMMEDIATE connection. It reads every member’s run_id, subject_id and scope_id, rejects run/subject mismatch, rejects len(member_scopes) > 1, then checks an existing attempt’s member set before physical-attempt/member insertion. The connection rolls back on a raised exception and commits only after both inserts.

| Case | Result |
|---|---|
| same run/subject, same non-null scope | prepared; reversed-order reentry stable |
| same run/subject, null/null scope | prepared; reversed-order reentry stable |
| same subject, two scoped values | rejected before writes |
| same subject, null versus scoped | rejected before writes |
| cross-subject and cross-run | existing guards reject before writes |
| existing physical ID, same member set | existing row returned; no new rows |
| existing physical ID, different member set | deterministic ConflictError |
| existing historical mixed member set | not migrated or rewritten; replacement copier can preserve it |

Immediate transaction serialisation protects this preparation operation against competing writers. It does not add a database same-scope constraint. Reentry also does not compare existing delivery/provider/reservation metadata; same members can return the existing row despite changed non-member arguments. That is residual identity risk.

The current governed path is safer than the old boundary: preflight validates durable subject/scope, source definitions, receipts, source-record family/payload hashes, representation availability/hash/lineage and evidence locators; FactoryPlan includes scope_id; ReferenceFactory uses SQLiteCatalog. The lower-level append-only replacement at catalog.py:4107-4169 inserts a new physical attempt and copies old members directly at 4154-4156 without calling prepare_physical_attempt(). Therefore the invariant is PASS for direct preparation/current governed Factory, but PARTIAL for all physical-attempt creation paths.

### Complete meaningful P2b unified diff

```diff
diff --git a/src/charitygraph/runtime/catalog.py b/src/charitygraph/runtime/catalog.py
index 5954ce8..1057705 100644
--- a/src/charitygraph/runtime/catalog.py
+++ b/src/charitygraph/runtime/catalog.py
@@ -3877,12 +3877,22 @@ class SQLiteCatalog:
             raise CatalogError("physical attempt needs a delivery mode and members")
         with self._connection(immediate=True) as conn:
             existing = conn.execute("SELECT * FROM physical_attempts WHERE physical_attempt_id=?", (physical_attempt_id,)).fetchone()
-            if existing:
-                return dict(existing)
+            member_scopes = set()
             for task_id in model_task_ids:
-                task = conn.execute("SELECT run_id, subject_id FROM tasks WHERE model_task_id=?", (task_id,)).fetchone()
+                task = conn.execute("SELECT run_id, subject_id, scope_id FROM tasks WHERE model_task_id=?", (task_id,)).fetchone()
                 if task is None or task["run_id"] != run_id or task["subject_id"] != subject_id:
                     raise ConflictError("physical attempt members must belong to its run and subject")
+                member_scopes.add(task["scope_id"])
+            if len(member_scopes) > 1:
+                raise ConflictError("physical attempt members must share one task scope_id; null and non-null scopes cannot be mixed")
+            if existing:
+                existing_member_ids = {
+                    row["model_task_id"]
+                    for row in conn.execute("SELECT model_task_id FROM physical_attempt_members WHERE physical_attempt_id=?", (physical_attempt_id,)).fetchall()
+                }
+                if existing_member_ids != set(model_task_ids):
+                    raise ConflictError("physical attempt re-entry member set conflicts with existing attempt")
+                return dict(existing)
             conn.execute("INSERT INTO physical_attempts(physical_attempt_id,run_id,subject_id,delivery_mode,status,provider_request_id,reservation_id,provider_batch_id,created_at,updated_at) VALUES (?,?,?,?, 'prepared',?,?,?,?,?)", (physical_attempt_id,run_id,subject_id,delivery_mode,provider_request_id,reservation_id,provider_batch_id,when,when))
             conn.executemany("INSERT INTO physical_attempt_members(physical_attempt_id,model_task_id) VALUES (?,?)", [(physical_attempt_id, task_id) for task_id in model_task_ids])
             self._commit(conn); return dict(conn.execute("SELECT * FROM physical_attempts WHERE physical_attempt_id=?", (physical_attempt_id,)).fetchone())
diff --git a/tests/runtime/test_task_state.py b/tests/runtime/test_task_state.py
index 83ed587..9196f29 100644
--- a/tests/runtime/test_task_state.py
+++ b/tests/runtime/test_task_state.py
@@ -19,6 +19,147 @@ def opened(tmp_path):
     return catalog

+def _register_task(catalog, task_id, *, subject_id=TASK["subject_id"], scope_id=None, run_id=RUN["record_id"]):
+    catalog.register_task({**TASK, "record_id": task_id, "subject_id": subject_id, "scope_id": scope_id}, run_id=run_id, now=NOW)
+    return task_id
+
+def _physical_counts(catalog):
+    with catalog._connection() as conn:
+        return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("physical_attempts", "physical_attempt_members", "provider_receipts", "cost_entries", "budget_reservations")}
+
+def test_prepare_physical_attempt_enforces_member_scope_before_side_effects_and_is_idempotent(tmp_path):
+    catalog = opened(tmp_path)
+    same_scope_a = _register_task(catalog, "modeltask:scope-a", scope_id="scope:one")
+    same_scope_b = _register_task(catalog, "modeltask:scope-b", scope_id="scope:one")
+    other_scope = _register_task(catalog, "modeltask:scope-c", scope_id="scope:two")
+    unscoped = _register_task(catalog, "modeltask:scope-null")
+    unscoped_b = _register_task(catalog, "modeltask:scope-null-b")
+    first = catalog.prepare_physical_attempt(physical_attempt_id="physical:scope-valid", run_id=RUN["record_id"], subject_id=TASK["subject_id"], delivery_mode="batch", provider_request_id="request:scope-valid", model_task_ids=(same_scope_a, same_scope_b), reservation_id=None, now=NOW)
+    assert first["status"] == "prepared"
+    assert catalog.prepare_physical_attempt(physical_attempt_id="physical:scope-valid", run_id=RUN["record_id"], subject_id=TASK["subject_id"], delivery_mode="batch", provider_request_id="request:scope-valid", model_task_ids=(same_scope_b, same_scope_a), reservation_id=None, now=NOW) == first
+    null_first = catalog.prepare_physical_attempt(physical_attempt_id="physical:scope-null-valid", run_id=RUN["record_id"], subject_id=TASK["subject_id"], delivery_mode="batch", provider_request_id="request:scope-null-valid", model_task_ids=(TASK["record_id"], unscoped_b), reservation_id=None, now=NOW)
+    assert catalog.prepare_physical_attempt(physical_attempt_id="physical:scope-null-valid", run_id=RUN["record_id"], subject_id=TASK["subject_id"], delivery_mode="batch", provider_request_id="request:scope-null-valid", model_task_ids=(unscoped_b, TASK["record_id"]), reservation_id=None, now=NOW) == null_first
+    before = _physical_counts(catalog)
+    with pytest.raises(ConflictError, match="share one task scope_id"):
+        catalog.prepare_physical_attempt(physical_attempt_id="physical:scope-mixed", run_id=RUN["record_id"], subject_id=TASK["subject_id"], delivery_mode="batch", provider_request_id="request:scope-mixed", model_task_ids=(same_scope_a, other_scope), reservation_id=None, now=NOW)
+    assert _physical_counts(catalog) == before
+    before = _physical_counts(catalog)
+    with pytest.raises(ConflictError, match="share one task scope_id"):
+        catalog.prepare_physical_attempt(physical_attempt_id="physical:scope-null-mixed", run_id=RUN["record_id"], subject_id=TASK["subject_id"], delivery_mode="batch", provider_request_id="request:scope-null-mixed", model_task_ids=(same_scope_a, unscoped), reservation_id=None, now=NOW)
+    assert _physical_counts(catalog) == before
+    with pytest.raises(ConflictError, match="member set conflicts"):
+        catalog.prepare_physical_attempt(physical_attempt_id="physical:scope-valid", run_id=RUN["record_id"], subject_id=TASK["subject_id"], delivery_mode="batch", provider_request_id="request:scope-valid", model_task_ids=(same_scope_a,), reservation_id=None, now=NOW)
+
+def test_prepare_physical_attempt_retains_subject_and_run_guards(tmp_path):
+    catalog = opened(tmp_path)
+    scoped = _register_task(catalog, "modeltask:guard-scoped", scope_id="scope:one")
+    other_subject = _register_task(catalog, "modeltask:guard-subject", subject_id="subject:other", scope_id="scope:one")
+    other_run = {**RUN, "record_id": "run:other", "configuration_hash": "f" * 64}
+    catalog.register_run(other_run)
+    other_run_task = _register_task(catalog, "modeltask:guard-run", scope_id="scope:one", run_id=other_run["record_id"])
+    for attempt_id, task_id in (("physical:cross-subject", other_subject), ("physical:cross-run", other_run_task)):
+        before = _physical_counts(catalog)
+        with pytest.raises(ConflictError, match="belong to its run and subject"):
+            catalog.prepare_physical_attempt(physical_attempt_id=attempt_id, run_id=RUN["record_id"], subject_id=TASK["subject_id"], delivery_mode="batch", provider_request_id="request:" + attempt_id.split(":", 1)[1], model_task_ids=(scoped, task_id), reservation_id=None, now=NOW)
+        assert _physical_counts(catalog) == before

 def test_registration_is_idempotent_and_conflicts_are_rejected(tmp_path):
```

The displayed diff contains the complete meaningful changed source/test hunk; unchanged pre-existing test bodies are not repeated.

### Fresh verification and SQL evidence

All commands used PYTHONDONTWRITEBYTECODE=1, PYTHONPATH=src, -p no:cacheprovider and fresh basetemps outside the checkout:

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-o1c-direct-catalog-20261025 tests/runtime/test_task_state.py tests/test_phase5_batch_bytes_and_attempts.py
16 passed in 4.04s

python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-o1c-factory-20261025-rerun tests/test_phase5_preflight.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py tests/runtime/test_source_evidence.py tests/runtime/test_budget_ledger.py
37 passed in 7.57s
```

Successful SQL probe database: C:\CharityGraph-runtime\cg-g4-o1c-sql-probe-20261025-final\probe.sqlite3.

```text
before_rejected = after_rejected = after_valid_idempotent_reentry =
{'budget_reservations': 1, 'cost_entries': 2, 'physical_attempt_members': 2,
 'physical_attempts': 1, 'provider_receipts': 1}
errors: mixed_scoped and null_scoped both rejected with
  physical attempt members must share one task scope_id; null and non-null scopes cannot be mixed
member_set_reentry rejected with physical attempt re-entry member set conflicts with existing attempt
rejected_side_effects_unchanged=True
valid_reentry_side_effects_unchanged=True
```

Two earlier probe harness attempts stopped before assertions because their synthetic task_run_id was not a valid hex typed ID; they created only external temporary databases and no checkout changes. The final probe corrected that harness input. This is not a product failure.

The exact unabridged test-file diff for the changed P2b additions is:

```diff
@@ -19,6 +19,147 @@ def opened(tmp_path):
     return catalog

+def _register_task(catalog, task_id, *, subject_id=TASK["subject_id"], scope_id=None, run_id=RUN["record_id"]):
+    catalog.register_task(
+        {
+            **TASK,
+            "record_id": task_id,
+            "subject_id": subject_id,
+            "scope_id": scope_id,
+        },
+        run_id=run_id,
+        now=NOW,
+    )
+    return task_id
+
+def _physical_counts(catalog):
+    with catalog._connection() as conn:
+        return {
+            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
+            for table in ("physical_attempts", "physical_attempt_members", "provider_receipts", "cost_entries", "budget_reservations")
+        }
+
+def test_prepare_physical_attempt_enforces_member_scope_before_side_effects_and_is_idempotent(tmp_path):
+    catalog = opened(tmp_path)
+    same_scope_a = _register_task(catalog, "modeltask:scope-a", scope_id="scope:one")
+    same_scope_b = _register_task(catalog, "modeltask:scope-b", scope_id="scope:one")
+    other_scope = _register_task(catalog, "modeltask:scope-c", scope_id="scope:two")
+    unscoped = _register_task(catalog, "modeltask:scope-null")
+    unscoped_b = _register_task(catalog, "modeltask:scope-null-b")
+
+    first = catalog.prepare_physical_attempt(
+        physical_attempt_id="physical:scope-valid",
+        run_id=RUN["record_id"],
+        subject_id=TASK["subject_id"],
+        delivery_mode="batch",
+        provider_request_id="request:scope-valid",
+        model_task_ids=(same_scope_a, same_scope_b),
+        reservation_id=None,
+        now=NOW,
+    )
+    assert first["status"] == "prepared"
+    assert catalog.prepare_physical_attempt(
+        physical_attempt_id="physical:scope-valid",
+        run_id=RUN["record_id"],
+        subject_id=TASK["subject_id"],
+        delivery_mode="batch",
+        provider_request_id="request:scope-valid",
+        model_task_ids=(same_scope_b, same_scope_a),
+        reservation_id=None,
+        now=NOW,
+    ) == first
+    null_first = catalog.prepare_physical_attempt(
+        physical_attempt_id="physical:scope-null-valid",
+        run_id=RUN["record_id"],
+        subject_id=TASK["subject_id"],
+        delivery_mode="batch",
+        provider_request_id="request:scope-null-valid",
+        model_task_ids=(TASK["record_id"], unscoped_b),
+        reservation_id=None,
+        now=NOW,
+    )
+    assert catalog.prepare_physical_attempt(
+        physical_attempt_id="physical:scope-null-valid",
+        run_id=RUN["record_id"],
+        subject_id=TASK["subject_id"],
+        delivery_mode="batch",
+        provider_request_id="request:scope-null-valid",
+        model_task_ids=(unscoped_b, TASK["record_id"]),
+        reservation_id=None,
+        now=NOW,
+    ) == null_first
+
+    before = _physical_counts(catalog)
+    with pytest.raises(ConflictError, match="share one task scope_id"):
+        catalog.prepare_physical_attempt(
+            physical_attempt_id="physical:scope-mixed",
+            run_id=RUN["record_id"],
+            subject_id=TASK["subject_id"],
+            delivery_mode="batch",
+            provider_request_id="request:scope-mixed",
+            model_task_ids=(same_scope_a, other_scope),
+            reservation_id=None,
+            now=NOW,
+        )
+    assert _physical_counts(catalog) == before
+
+    before = _physical_counts(catalog)
+    with pytest.raises(ConflictError, match="share one task scope_id"):
+        catalog.prepare_physical_attempt(
+            physical_attempt_id="physical:scope-null-mixed",
+            run_id=RUN["record_id"],
+            subject_id=TASK["subject_id"],
+            delivery_mode="batch",
+            provider_request_id="request:scope-null-mixed",
+            model_task_ids=(same_scope_a, unscoped),
+            reservation_id=None,
+            now=NOW,
+        )
+    assert _physical_counts(catalog) == before

+    with pytest.raises(ConflictError, match="member set conflicts"):
+        catalog.prepare_physical_attempt(
+            physical_attempt_id="physical:scope-valid",
+            run_id=RUN["record_id"],
+            subject_id=TASK["subject_id"],
+            delivery_mode="batch",
+            provider_request_id="request:scope-valid",
+            model_task_ids=(same_scope_a,),
+            reservation_id=None,
+            now=NOW,
+        )
+
+def test_prepare_physical_attempt_retains_subject_and_run_guards(tmp_path):
+    catalog = opened(tmp_path)
+    scoped = _register_task(catalog, "modeltask:guard-scoped", scope_id="scope:one")
+    other_subject = _register_task(catalog, "modeltask:guard-subject", subject_id="subject:other", scope_id="scope:one")
+    other_run = {
+        **RUN,
+        "record_id": "run:other",
+        "configuration_hash": "f" * 64,
+    }
+    catalog.register_run(other_run)
+    other_run_task = _register_task(catalog, "modeltask:guard-run", scope_id="scope:one", run_id=other_run["record_id"])
+
+    for attempt_id, task_id in (("physical:cross-subject", other_subject), ("physical:cross-run", other_run_task)):
+        before = _physical_counts(catalog)
+        with pytest.raises(ConflictError, match="belong to its run and subject"):
+            catalog.prepare_physical_attempt(
+                physical_attempt_id=attempt_id,
+                run_id=RUN["record_id"],
+                subject_id=TASK["subject_id"],
+                delivery_mode="batch",
+                provider_request_id="request:" + attempt_id.split(":", 1)[1],
+                model_task_ids=(scoped, task_id),
+                reservation_id=None,
+                now=NOW,
+            )
+        assert _physical_counts(catalog) == before
```

## 3. Canonical Gate 4 truth

### Authority register

Local Builder authority was read at Builder HEAD 21bb0e621f2a1c52f19b59f261d71009defa4843, tree f5851e02afab398326e145a34d142d9de5fe1a58:

| Path | Current SHA-256 | HEAD blob | Relevant authority |
|---|---|---|---|
| AGENTS.md | 7694737c75ef8c32eb930f7e17225e20a03aa51ca589c1d21ed0a59a1639ba57 | ecd21e0aa7fa265a8a7f98f853c760dac79a1e01 | closed Source Universe v1, no discovery, semantic heuristic gate, no gate closure |
| ARCHITECTURE.md | c497783d3c6fe94637f29278905cfe35881bba2461c8f58409e2da40637c3319 | e3773bb35dcbff7cf24bb6a46be27124f78ba591 | typed artefact graph, Python control/model semantics, scope/lineage, coverage and cost |
| BUILDER_MACHINERY.md | fa9bc48e69f52f506f9d029b01de5d0836979d36f9b207e42b4967e30f3d5055 | 5a2d0f1d0bc3c2cb93f88325f17cfe5f696cd081 | existing machinery, before-building archaeology, source/evidence/representation seams |

The sibling Data authority checkout was read at branch docs/gate3-closure-gate4-activation-2026-10-20, revision f5f154cf2e3f107a9a2563c94626a0e39419fd3e, tree c6aa4fd59c9f3cb7f88a9575b1860417d0951be6:

| Data path | SHA-256 | HEAD blob | Relevant section |
|---|---|---|---|
| DOCUMENT_AUTHORITY.md | 693af004b54cd0b23f5a02e7c2f9da1d93a01655045c073ff2e8e4e04f6fcf08 | 2e43f4994a12d998d6fe77c72d2439cff2bb045a | §§2–4 authority hierarchy and current authorities |
| CURRENT_STATE.md | 9cd2617e3d5a7ceda21ece433452b060fa06536e3778033f2c01022b58335428 | e5474bc8d2aff81545e8ffefb7299adbf639bc25 | opening Gate 4 state; rights and Phase 5 missingness sections |
| ROADMAP.md | eee1e3a52336197783a906fdfa8c94985fef59d16ab8860480411dc96dcbf4b5 | 6cb795c9b27174d6a6588f46d68675299266e955 | opening gates; Phase 2 source universe; Factory hardening |
| IMPLEMENTATION_PLAN.md | 8b59ac1d609a35ba92f9fc229ce5b25708e2de08c31dca609d0e34757fcb2655 | 2814eb467de213fceacba76d7f43a52a5dbc7e96 | active Phase 5 sequence and target architecture |
| TEST_PLAN.md | a980ca1fc470fd89091cba64fddd8863d87bae6a8be25e143379ed36fa53a536 | 3d61b73d9d338ec19bea03f46bbfed329cec1826 | test layers, persistence, rights, missingness and cost |
| INTEGRATED_PRODUCT_AND_DATA_MODEL.md | 812356fc0d6879648ace0163547586917d1b666ea7c2022ec28281d576bfe497 | de8afa01efe516df6c537dd285571920a2a067df | integrated source/evidence/knowledge/projection model |
| SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md | 59a31bb01900d801cb762ad351bb58d00979c14532a9bfbceb25bd8e0260c627 | 59498c00f89ed558520ba5ddaefb31809b701b57 | §§3.1–5.1 source admission, roles, exact artifact-bound rights; §§9, 12–15 processing/publication/release |
| TAXONOMY_AND_SCHEME_GOVERNANCE.md | e0e233204225810df2611a6b593b15e70f78c4922443987fc3d2ed22eb05c8bb | d5059c698c657013ede0022c076ff6d4c14bcd47 | taxonomy ownership, external scheme and permission separation |
| COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md | 891cd0f869b7882f078669d22ac8e4ae5fdf53712721b5230fba29ca279d4463 | 67096bb3656680c610b6ad41ceb6e8c906ba6d41 | model economics, source universe/roles, coverage and publication |
| SEMANTIC_HEURISTIC_APPROVALS.md | c80560ff1e9745cd282271209c745b0a50f5e9c2788d36e1459b360b312e81ec | 7b9df9469160e6efbd6d13e1e88372c030fb739b | no CG-SH-* exceptions; deterministic semantic heuristics remain prohibited |
| PHASE6_V3_SOURCE_RIGHTS_AUDIT_2026-09-13.md | f2142c34d229e0dbf141652d053227a7568f14414943b165399442e801ecbed3 | fd213d2655e5cf4474a81bb9c9d8bf74ba9b774f | historical rights audit: unknown/blocked is not permission |
| PHASE6_V3_POST_POLICY_RIGHTS_ASSESSMENT_2026-09-13.md | e1a3c855e24dbe99be00716c2a3cc5bff27b1f839e188b9e89c7eb5a996228a8 | 755c9f20cee73912f6c0944803eee2bc83763153 | exact representation decisions and remaining blocked inputs |
| SCALE_S0_RUNTIME_SOURCE_AUTHORITY_REPAIR_2026-09-21.md | 12248819d03ebbde243826c84fcb1d6f20547f436c60ac4ee5d5e9d4fb0666da | b3654658bd75904daab5b1cba6ae8e88f49cf6d8 | concrete attempt-bound source authority separate from mandate |
| SCALE_S0_SOURCE_RIGHTS_CLEARANCE_2026-09-18.md | 8278cb107a1095c7d6b13a3b47b7e2ae704301d687e73d2890553ac7df722f73 | 84b280bc783caa100c7bc167634b8b269c2de9fa | exact artifact/representation, role, lineage and fail-closed rights rules |

### What Gate 4 actually is

The canonical current decision is not inferred from the P2b name. BUILDER_TO_65K_PLAN.md:13-18, 56-70, 89-91 and docs/gates/GATE3_CLOSURE_GATE4_ACTIVATION_2026-10-20.md state that Gate 4 is Builder industrialisation, weight 20%, active and not earned. Its objective is evidence for model/cost routing, batch execution, concurrency, restart/resume, idempotence, scheduling, monitoring, failure isolation and cost telemetry. The 65k accepted full-population Builder/corpus run is the overall endpoint, not a Gate 4-local synthetic test.

Actual Gate 3 closure evidence is evidence/gate3-final-semantic-review/summary.md (SHA-256 c82386d024878ae81f2d1be26eb55f7ef3b23c8ff100ca4ed3b2af5bd3b671d3), plus the Data handoff docs/gates/GATE3_CLOSURE_GATE4_ACTIVATION_2026-10-20.md (SHA-256 d1985af996645398d7b5a685f972886174dea78bcbdf2c68df75e3623b4fcf5a; blob 608dd8d24e26e4ceacc0913ed7c86a94260ef8f7). Gate 3 was explicitly accepted with limitations: Builder saw only 36 ACNC Register and 36 ACNC AIS records; the evaluation was 36 bounded cases; the oracle aggregate had an unreconciled 51-versus-36 count; and the handoff says this does not establish all seven Source Universe families, population-scale quality or production readiness.

### Gate 4 evidence matrix

| Criterion | Proven evidence | Missing/limiting evidence | Status |
|---|---|---|---|
| model/cost routing | FactoryPlan, DeliveryPolicy, fake tariffs, reservation/actual/release tests | no approved paid route, real model usage or production cost sample | partial |
| batch execution | three fake physical packages from four references | no provider batch crossing or reconciliation | partial |
| concurrency | SQLite immediate transactions and competing-claim tests | no measured multi-worker Factory/concurrency run | missing |
| restart/resume | reopen/rerun and ambiguous-send hold/reconcile tests | no real provider ambiguity or production recovery exercise | partial |
| idempotence | reruns add zero physical attempts, receipts or costs | replacement copier bypasses guard; no broad historical audit | partial |
| scheduling | deterministic package ordering and delivery policy | no production scheduler/queue/monitoring evidence | missing |
| monitoring | durable task/attempt/cost/fence telemetry | Gate 3 handoff says failed bridge is not fit; no accepted operations proof | missing |
| failure isolation | distinct diagnostics; accepted peer still runs | only synthetic provider-free cases | partial |
| cost telemetry | synthetic AUD reservation/actual/release reconciliation | no paid-provider rate-limit/retry/cohort evidence | partial |

This matrix supports a bounded engineering slice; it does not satisfy Gate 4 exit evidence. Meaningful closure is not possible with provider-free local evidence alone because critical operational and real-execution evidence is missing, and Product Owner closure is required. This task does not authorise source acquisition, provider/model inference, paid work, semantic publication, release, GitHub push/PR or formal closure.

## 4. P3 rights and source-role seam archaeology

### Current behaviour

GovernedReference in src/charitygraph/phase5_governed_factory_integration.py:42-129 requires a free-text rights_role and optionally accepts rights_policy_id. Its available-material validator checks source/evidence/representation identity and hashes but does not load an ArtifactRightsDecision. preflight_governed_references() copies rights_policy_id and rights_role into planned task and model-task parameters. FactoryPlan.runtime_tasks() copies them again. rights_policy_id is therefore copied input, not a resolved permission.

The regular Phase 5 catalogue stores source-definition authority roles/material JSON, source-record source_role and payload lineage, evidence-locator artifact/source-record references, artifact hash/availability and task material. It has no Phase 5 artifact/representation-specific provider-rights decision table or resolver. scale_s0_source_authorities is a separate attempt-bound control plane, not a Phase 5 governed-reference permission.

src/charitygraph/source_rights.py:55-153 and tests/test_source_rights.py define the deterministic policy object: ArtifactRightsDecision binds source artifact, source record, public origin, source_role, acquisition lineage and exact transmitted-representation SHA, and checks provider policy, rights basis, representation class, access, lawful acquisition and prohibition flags. require_provider_rights() fails closed for absent, duplicate, mismatched or non-permitted decisions. BoundedLocalRetentionDecision is separate; local retention cannot authorize provider transmission. The frozen-experiment path uses this resolver, but current Phase 5 preflight does not.

Current fail-closed states are precise: declared blocked, not_processed, missing, not_applicable, retrieval_failed, structurally_invalid, unrecoverable and mismatched inputs remain diagnostics and do not lower to tasks; absent subject/scope/source/receipt/artifact/evidence is diagnosed; blocked acquisition or quarantined representation is blocked; unavailable/failed acquisition is retrieval_failed; non-available retained material is unrecoverable; hash, subject or lineage mismatch is mismatched.

Absent, contradictory, stale/expired or role-incompatible provider rights are not currently checked by Phase 5 preflight. A reference with otherwise valid evidence can be lowered while rights_policy_id is absent or merely copied. This is a rights-enforcement gap, not evidence unavailability.

Canonical governance does authorize the exact rule that content-bearing material needs a versioned artifact/representation-bound rights decision before external-model processing (SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md:113-133). It does not specify a Phase 5 durable record/table, resolver location, or provider-decision expiry/review-validity rule. ArtifactRightsDecision has assessed_on but no provider-expiry field; local-retention records have review_due_on but cannot authorize provider transmission. These schema/expiry authorities must be settled before implementation. No speculative expiry or role-compatibility logic is proposed.

### Conditional smallest bounded P3 tranche (not implemented)

After Product Owner/Data authority resolves the Phase 5 durable rights-record and validity semantics, the smallest provider-free tranche would use these currently clean paths:

```text
src/charitygraph/phase5_governed_factory_integration.py
  8bedb82daaa6b53cb29ee8e671930844866e7252a5b767889e42926b298e4d9d
src/charitygraph/source_rights.py
  13824bbe1bea1bb87d77636eca38a2794c294ad5b05d00d0b5ce0ea2ae5ccc98
tests/test_source_rights.py
  526aee5c520975e66e9e7b5c2843f68d374e228ce3fb4beaa8d46532285b6447
```

Do not touch the pre-existing dirty tests/test_phase5_governed_factory_integration.py or src/charitygraph/runtime/catalog.py. New clean test/report paths would be needed if a durable Phase 5 record is approved.

The approved wiring would resolve one durable decision per (representation_artifact_id, representation_hash), require exact source-record/origin/source-role/acquisition-lineage match and provider_transmission_allowed=True, and fail closed for missing, duplicate, contradictory, stale/expired once the approved validity rule exists, incompatible provider policy, role mismatch or explicit prohibition. Positive and negative fixtures would run through preflight_governed_references -> FactoryPlan -> ReferenceFactory -> SQLiteCatalog: the positive exact decision produces one task/physical attempt and fake receipt with idempotent rerun; each negative decision produces a diagnostic, no task, no physical attempt, no receipt, no reservation and no cost. No provider spend or source acquisition is needed.

Because the Phase 5 durable rights-record/expiry authority is not specified and the natural catalogue path is pre-existing dirty, this is a conditional proposal only. The smallest immediate P3 action is an authority decision naming the durable record, decision ID, representation binding, source-role compatibility and validity/review semantics. Until then, the safe current behaviour for an unproven provider route is no external processing; copied rights_policy_id is not permission evidence.

## 5. Final unchanged-path proof and disposition

Post-test control reads retained the branch, HEAD, tree and fence identities above. Visible status remained 266 records before this report. Required unchanged hashes remained:

```text
7e1bd2d19732102f9840a6c7ce1a55c95042ef4d88b874cd3a6ef43aa49c4020  src/charitygraph/runtime/catalog.py
5804053f05619604896ace5f0149c2442c46dfdbaa3491811dc1a60844c8e42f  tests/runtime/test_task_state.py
e3f8a6c1566e7241f6bf10d2203fd49454b6b5a147befbacc72e6c22223f176a  tests/test_phase5_batch_bytes_and_attempts.py
```

No code, test, Data, evidence, source, cache, credential, provider, model, watcher, bridge or Git state was changed by this task. Temporary pytest bases and SQLite probe databases are outside the checkout under C:\CharityGraph-runtime. This report is the sole new repository artifact. Process success is not product acceptance and does not close Gate 4.
