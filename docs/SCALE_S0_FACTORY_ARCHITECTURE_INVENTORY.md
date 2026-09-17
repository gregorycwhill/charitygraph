# Scale S0 Factory architecture inventory

Status: implementation inventory for a future, separately authorised Scale S0 mandate. This document records the reconciliation performed before the S0 preflight controls were added. It does not authorise a cohort, acquisition, provider transmission, promotion, or release.

| Concern | Existing primitive | Reuse decision and ownership boundary |
|---|---|---|
| Campaign/run identity | `RunManifest`, `RunRecord`, and `SQLiteCatalog.register_run` | Reuse. Scale S0 supplies authorisation to attempt a bounded slice; it does not replace a run identity. Runtime owns mutable run state. |
| Logical execution identity | `ModelTask`/semantic contracts and `provider_request_items` | Reuse. `LogicalTaskRegistry` adds explicit scale-era task identity without inferring contracts from card sections. |
| Physical provider attempt | `physical_attempts`, `provider_request_attempts`, Standard transport trace | Reuse. `ScaleS0Preflight` is a provider-free intercept before the existing crossing boundary; it does not persist an alternative attempt ledger. |
| Execution state/restart | task leases, terminal states, `reopen_pre_send_failure`, ambiguity-safe Standard transport | Reuse. An active S0 halt prevents new sends after restart as it is evaluated before each future send. |
| Reservation/budget | `budget_reservations`, cost ledger, execution-mandate reservations and reconciliation | Reuse. The S0 contract requires an explicit reservation policy and each preflight requires a reservation ID. Existing runtime remains accounting authority. |
| Retry/recovery | exact provider request attempts, zero-crossing replacement, no ambiguous resend | Reuse. The preflight takes an explicit retry permission and rejects duplicate physical attempts. Recovery of a halt requires an append-only explicit recovery record. |
| Source acquisition/frozen source | source records, evidence fragments, source rights contracts, governed source universe | Reuse. `SourceAuthorisation` is an S0 policy view over frozen records; tasks cannot acquire sources. |
| Task/schema identity | Phase 5/6 semantic contracts and exact prompt/schema hashes | Extend. The scale registry binds a stable logical task/version, profile, output schema, validation and routing without introducing provider-specific semantic identity. |
| Validation/candidate storage | typed candidate contracts and mechanical validation | Reuse. S0 candidate checks require mechanical validity plus evidence, lineage, subject and scope. |
| Review/adjudication | `DecisionRecord`, taxonomy review and correction controls | Extend with auditable `ReviewItem`/`ReviewDecision` bindings, keeping a review decision distinct from a candidate. |
| Promotion | canonical observations, program promotion and North Star projection adapters | Extend with a central S0 promotion gate. No raw provider output or schema-valid candidate projects to a card. |
| Lineage/projection | typed lineage edges and `north-star-v0.2` projection | Reuse. Promotion returns a governed observation identity only; projection remains downstream and separately governed. |
| PDF/document handling | `document_v2` representations and visual routing | Extend with an explicit S0 representation authorisation policy so visually material pages cannot disappear into text-only absence. |
| CLI/orchestration | `charitygraph` CLI and Phase 5 packet/certification scripts | Reuse as future caller boundary. The new module is intentionally offline/provider-free until a product owner supplies an approved mandate. |

## Duplicate concepts deliberately avoided

The implementation does not create a second execution ledger, reservation account, provider receipt store, retry engine, source archive, candidate store, card writer, or semantic classifier. `ScaleMandate` is authorisation/configuration; a `RunManifest` is an invocation; a logical task is distinct from a physical provider attempt; and a review decision is distinct from schema validation and from canonical promotion.

## S0 policy controls

`charitygraph.scale_s0` provides immutable versioned mandate, logical task registry, provider-independent routing, sampling, acquisition/rights, representation, review, halt and promotion contracts. It is fail-closed for absent policy references, frozen-population drift, unauthorised sources, missing reservations, hard halts, duplicate paid attempts, inadequate representations, processing failures, missing review, rejected review, stale task/scope bindings and direct semantic-candidate promotion.

## Durable S0 restart authority

Migration 17 persists the missing S0 control-plane identities without
duplicating an existing canonical store. `scale_s0_mandates` carries complete
immutable mandate material and the exact task-registry, routing, policy and
source-authorisation snapshot used to reconstruct preflight. Frozen packets
bind that mandate and slice to their task/profile/schema, subject/scope,
source snapshot set, route, provider-request identity, content hash and freeze
time. Candidate material, review items, append-only review decisions and
promotion authorisation/result references are likewise immutable and
idempotent by material hash.

`ScaleS0Preflight.from_catalog` reconstructs a new preflight from these
records, including a durable reference to the existing reservation/accounting
state. A same ID with different material fails closed. The existing physical
attempt/request/response ledger still decides whether a provider crossing is
already complete or ambiguous; it is never copied into an S0 table. Promotion
uses a durable authorisation followed by one deterministic result reference to
the existing governed-observation authority, so recovery before persistence is
safe and recovery after persistence cannot create duplicate knowledge.

The deterministic source-native boundary is narrow: only a task registered with `deterministic_source_native_audited` may use it, and it remains source/evidence/lineage bound. Semantic candidates always require a review decision even when sampling would otherwise not select them.
