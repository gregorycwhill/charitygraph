"""Execute the five byte-frozen product-value requests once, after live gates."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.request import getproxies

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charitygraph.openai_client import _output_text
from charitygraph.phase5_openai_dry_run import (
    PRICING, STANDARD_INPUT_BOUND_FACTOR, conservative_standard_hard_max_aud,
    standard_actual_cost,
)
from charitygraph.phase5_standard_transport import (
    OpenAIHTTPStandardClient, StandardTransportError,
    canonical_standard_body_bytes, client_request_id_for_physical_attempt,
)
from charitygraph.phase6_v5_campaign import _validate_v5_response
from charitygraph.phase6_v6_campaign import _validate_v6_packet
from charitygraph.product_value_baseline import (
    CampaignAttempt, ProviderPolicyAttestation, ProviderRightsRevalidation,
    certify_five_request_campaign_shape, require_campaign_ready,
)
from charitygraph.source_rights import FAIR_DEALING_POLICY_ID, OPENAI_PROVIDER_POLICY_ID


RUN_ID = "product-value-five-request-semantic-campaign-20260914-v1"
MAX_ATTEMPT_AUD = Decimal("0.25")
MAX_FIVE_REQUEST_RESERVATION_AUD = Decimal("1.25")
FX_AUD_PER_USD = Decimal("1.40")  # rounded up from RBA 11 Sep: USD per AUD 0.7172
FX_OBSERVED_USD_PER_AUD = Decimal("0.7172")
ORDER = (
    ("28004778081", "World Vision Australia", "outcomes", "phase6-corrected-contracts-v6"),
    ("78053639115", "Bush Heritage Australia", "outcomes", "phase6-corrected-contracts-v6"),
    ("50169561394", "Australian Red Cross Society", "commitments", "phase6-corrected-contracts-v5"),
    ("61002643852", "Greenpeace Australia Pacific Limited", "commitments", "phase6-corrected-contracts-v5"),
    ("65159324697", "The Sunrise Project Australia Limited", "commitments", "phase6-corrected-contracts-v5"),
)
OPENAI_PRICE_URL = "https://developers.openai.com/api/docs/models/gpt-5.6-luna"
RBA_FX_URL = "https://www.rba.gov.au/statistics/frequency/exchange-rates.html"
ACNC_COPYRIGHT_URL = "https://www.acnc.gov.au/copyright"
PROVIDER_SETTING = "Share inputs and outputs with OpenAI = Disabled"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_atomic(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _proxy_inventory() -> dict[str, Any]:
    proxies = getproxies()
    endpoints = {}
    for scheme, value in proxies.items():
        # Hostnames and embedded credentials can be sensitive; retain only a
        # redacted endpoint shape, as required by the transport runbook.
        try:
            from urllib.parse import urlsplit
            parsed = urlsplit(value if "://" in value else f"//{value}")
            endpoints[scheme] = f"{parsed.scheme or 'configured'}://[redacted-host]" + (f":{parsed.port}" if parsed.port else "")
        except Exception:
            endpoints[scheme] = "[redacted-endpoint]"
    return {"configured": bool(proxies), "redacted_endpoints": endpoints}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def _paths(builder: Path, data: Path) -> dict[str, Path]:
    work = builder / "work" / "product-value-baseline-2026-09-14"
    return {
        "work": work,
        "packet": work / "model-assisted-baseline" / "source-only",
        "lock": work / "model-assisted-baseline" / "source-only" / "source-only-baseline.lock.json",
        "campaign": work / "campaign-preflight",
        "requests": work / "campaign-preflight" / "requests",
        "source_metadata": work / "model-assisted-baseline" / "source-only" / "source-metadata.json",
        "deterministic": work / "deterministic-context",
        "adjudicated": work / "adjudicated-context",
        "rights_lineage": builder.parent / "archive" / "processed" / "phase6-v4-rights-minimized-2026-09-13-private-review" / "v4-artifact-rights-lineage.json",
        "v6_manifest": builder.parent / "archive" / "processed" / "phase6-outcomes-v6-2026-09-14-private" / "execution-manifest.json",
        "data": data,
        "execution": work / "campaign-execution-2026-09-14",
    }


def _preflight(builder: Path, data: Path, now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = _paths(builder, data)
    if paths["execution"].exists():
        raise ValueError("campaign execution directory already exists; refusing replay")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is unavailable")

    from charitygraph.product_value_baseline import validate_source_only_packet
    baseline_manifest_sha = validate_source_only_packet(paths["packet"])
    campaign_raw = (paths["campaign"] / "execution-manifest.json").read_bytes()
    campaign = json.loads(campaign_raw.decode("utf-8"))
    if _sha(campaign_raw) != "779bdbdf74c5fd5d1ea12ef708cbd52b8d87d6f60dbd6d927194f360bd931241":
        raise ValueError("frozen campaign execution manifest hash changed")
    if campaign.get("campaign_status") != "PREPARED_NOT_SENT" or campaign.get("provider_calls") != 0 or campaign.get("source_acquisitions") != 0:
        raise ValueError("frozen campaign is not in its pristine zero-crossing state")
    if campaign.get("baseline_lock_sha256") != _sha(paths["lock"].read_bytes()):
        raise ValueError("locked source-only baseline changed")
    if len(campaign.get("attempts", [])) != 5:
        raise ValueError("frozen request inventory does not contain exactly five attempts")

    actual_order = [(row["abn"], row["subject_name"], row["slice_id"], row["contract_version"]) for row in campaign["attempts"]]
    if actual_order != list(ORDER):
        raise ValueError("frozen request order or contract identity differs from Greg's authorization")
    if campaign.get("capacity_requests") != 0 or campaign.get("unused_budget_reusable") is not False:
        raise ValueError("frozen campaign includes an unauthorized request or reusable budget")

    context = _json(paths["adjudicated"] / "readiness-and-reconciliation.json")
    candidate_hash = _sha((paths["deterministic"] / "candidates.json").read_bytes())
    governed = _json(paths["adjudicated"] / "governed-items.json")
    if candidate_hash != "bbeac4843bce4714b778c8ec90c678528990b906d23b5a680a1657224e5b666b":
        raise ValueError("deterministic candidate inventory identity changed")
    if context.get("readiness") != "DETERMINISTIC_CONTEXT_READY_FOR_SEMANTIC_EXECUTION":
        raise ValueError("adjudicated deterministic context readiness changed")
    if len(governed.get("proposition_items", [])) != 106 or len(governed.get("coverage_items", [])) != 105:
        raise ValueError("adjudicated deterministic context counts changed")
    if any(row.get("canonical_public") is not False for row in governed["proposition_items"] + governed["coverage_items"]):
        raise ValueError("deterministic context is not private experiment-only data")

    metadata = _json(paths["source_metadata"])
    metadata_rows = metadata.get("sources", [])
    metadata_by_pair = {(row["source_artifact_id"], row["representation_sha256"]): row for row in metadata_rows}
    if len(metadata_rows) != 16:
        raise ValueError("locked cohort source metadata count changed")
    lineage = _json(paths["rights_lineage"])
    lineage_raw = paths["rights_lineage"].read_bytes()
    v6_execution = _json(paths["v6_manifest"])
    if _sha(lineage_raw) != v6_execution.get("rights_lineage_file_sha256"):
        raise ValueError("artifact rights-lineage bytes are not bound by the certified V6 record")
    if lineage.get("policy_id") != FAIR_DEALING_POLICY_ID:
        raise ValueError("artifact rights-lineage uses a different Fair Dealing policy")
    lineage_by_pair = {(row["source_artifact_id"], row["representation_sha256"]): row for row in lineage.get("artifacts", [])}

    revalidated: dict[str, ProviderRightsRevalidation] = {}
    rights_rows: list[dict[str, Any]] = []
    per_attempt_exposures: list[Decimal] = []
    client = OpenAIHTTPStandardClient()
    if client.socket_timeout_seconds != 300:
        raise ValueError("Standard transport timeout is not the authorized 300 seconds")
    if PRICING["gpt-5.6-luna"]["input"] != Decimal("0.20") or PRICING["gpt-5.6-luna"]["output"] != Decimal("1.20") or PRICING["gpt-5.6-luna"]["cache_write_input"] != Decimal("0.25"):
        raise ValueError("Builder model pricing table differs from the current official Luna rate card")

    attempt_rows: list[dict[str, Any]] = []
    for row, (abn, name, slice_id, contract) in zip(campaign["attempts"], ORDER, strict=True):
        if row["state"] != "PREPARED_NOT_SENT" or row["provider_post_count"] != 0:
            raise ValueError(f"{name}: request is not pristine PREPARED_NOT_SENT")
        body_path = paths["requests"] / f"{abn}.json"
        body_bytes = body_path.read_bytes()
        body = json.loads(body_bytes.decode("utf-8"))
        canonical_body = canonical_standard_body_bytes(body)
        if _sha(canonical_body) != row["request_body_sha256"]:
            raise ValueError(f"{name}: frozen request body hash mismatch")
        if body.get("model") != "gpt-5.6-luna" or body.get("reasoning", {}).get("effort") != "low" or body.get("store") is not False or body.get("max_output_tokens") != 8000:
            raise ValueError(f"{name}: request route/model/storage/output ceiling mismatch")
        if body.get("metadata", {}).get("logical_task_id") != row["logical_task_id"] or body.get("text", {}).get("format", {}).get("name") != row["provider_schema_name"]:
            raise ValueError(f"{name}: frozen body logical task or schema name mismatch")
        schema_bytes = _canonical(body["text"]["format"]["schema"])
        if _sha(schema_bytes) != row["provider_schema_sha256"]:
            raise ValueError(f"{name}: frozen schema hash mismatch")
        client_id = client_request_id_for_physical_attempt(row["physical_attempt_id"])
        if client_id != row["x_client_request_id"]:
            raise ValueError(f"{name}: frozen client request ID mismatch")
        if row["provider_schema_certification"].get("certification_status") != "certified":
            raise ValueError(f"{name}: provider schema is not certified")

        request_rights = row.get("source_rights", [])
        if len(request_rights) != 2:
            raise ValueError(f"{name}: expected exactly two frozen source rights records")
        for source in request_rights:
            key = (source["source_artifact_id"], source["representation_sha256"])
            meta = metadata_by_pair.get(key)
            lineage_row = lineage_by_pair.get(key)
            if meta is None or lineage_row is None:
                raise ValueError(f"{name}: source artifact or exact-hash rights record is absent")
            representation = paths["packet"] / meta["representation_path"]
            if _sha(representation.read_bytes()) != source["representation_sha256"]:
                raise ValueError(f"{name}: exact source representation hash mismatch")
            pairs = (
                meta["source_record_id"] == source["source_record_id"] == lineage_row["source_record_id"],
                meta["source_locator"] == source["source_origin_url"] == lineage_row["source_origin_url"],
                meta["source_role"] == source["source_role"] == lineage_row["source_role"],
                meta["source_artifact_id"] == lineage_row["source_artifact_id"],
                meta["evidence_locator_id"] == source["evidence_locator_id"],
                meta["legal_scope"] == source["legal_scope"] == "organisation",
                meta["retention_status"] == source["retention_status"] == "authorized",
                meta["provider_transmission_status"] == "separately_authorized_for_exact_hash_subject_to_revalidation",
                source["provider_transmission_allowed_in_frozen_decision"] is True,
                source["provider_rights_decision_disposition"] == "included",
                lineage_row["disposition"] == "included" and lineage_row["provider_transmission_allowed"] is True,
                source["rights_policy_id"] == lineage_row["rights_policy_id"] == FAIR_DEALING_POLICY_ID,
                source["provider_processing_policy_id"] == lineage_row["provider_processing_policy_id"] == OPENAI_PROVIDER_POLICY_ID,
                source["acquisition_lineage_ids"] == lineage_row["acquisition_lineage_ids"] and bool(source["acquisition_lineage_ids"]),
            )
            if not all(pairs):
                raise ValueError(f"{name}: source identity, rights, scope, role, policy or acquisition lineage mismatch")
            decision_id = source["provider_rights_decision_id"]
            if decision_id != lineage_row["rights_decision_id"]:
                raise ValueError(f"{name}: artifact-bound provider rights decision identity mismatch")
            revalidated[decision_id] = ProviderRightsRevalidation(source["representation_sha256"], "authorized", now)
            rights_rows.append({
                "subject": name, "source_artifact_id": source["source_artifact_id"],
                "source_record_id": source["source_record_id"],
                "representation_sha256": source["representation_sha256"],
                "rights_decision_id": decision_id,
                "rights_policy_id": FAIR_DEALING_POLICY_ID,
                "provider_processing_policy_id": OPENAI_PROVIDER_POLICY_ID,
                "provider_transmission_authorized": True,
                "source_role": source["source_role"], "legal_scope": source["legal_scope"],
                "acquisition_lineage_ids": source["acquisition_lineage_ids"],
                "revalidated_at": now.isoformat(), "source_acquisitions": 0,
            })

        bound = row["input_tokens_estimate"]
        exposure = conservative_standard_hard_max_aud(
            bound, 8000, FX_AUD_PER_USD, model="gpt-5.6-luna",
            input_bound_factor=STANDARD_INPUT_BOUND_FACTOR,
        )
        if exposure > MAX_ATTEMPT_AUD:
            raise ValueError(f"{name}: refreshed conservative exposure exceeds AUD 0.25")
        per_attempt_exposures.append(exposure)
        attempt_rows.append({
            "subject": name, "abn": abn, "slice_id": slice_id,
            "contract_version": contract, "request_item_id": row["request_item_id"],
            "physical_attempt_id": row["physical_attempt_id"],
            "client_request_id": client_id,
            "request_body_sha256": row["request_body_sha256"],
            "request_body_path": str(body_path.relative_to(paths["work"])),
            "provider_schema_sha256": row["provider_schema_sha256"],
            "semantic_contract_sha256": row["semantic_contract_sha256"],
            "prompt_sha256": row["prompt_sha256"],
            "model": "gpt-5.6-luna", "reasoning_effort": "low",
            "delivery": "Standard", "timeout_seconds": 300,
            "automatic_retries": 0, "manual_retries": 0,
            "max_output_tokens": 8000, "input_tokens_estimate": bound,
            "conservative_reserved_exposure_aud": str(exposure),
            "status": "PREPARED_NOT_SENT", "provider_posts": 0,
        })

    total_reserve = sum(per_attempt_exposures, Decimal("0"))
    if total_reserve > MAX_FIVE_REQUEST_RESERVATION_AUD:
        raise ValueError("refreshed five-request reservation exceeds AUD 1.25")
    shape_attempts = [CampaignAttempt(row["abn"], row["slice_id"], row["request_item_id"], exposure)
                      for row, exposure in zip(campaign["attempts"], per_attempt_exposures, strict=True)]
    certify_five_request_campaign_shape(shape_attempts)
    provider_attestation = ProviderPolicyAttestation(True, "Greg", now)
    context_run = _json(paths["deterministic"] / "run-metadata.json")
    candidate_generation_at = datetime.fromisoformat(context_run["generated_at"].replace("Z", "+00:00"))
    require_campaign_ready(
        paths["packet"], candidate_generation_at=candidate_generation_at,
        provider_attestation=provider_attestation,
        provider_rights_revalidated=revalidated,
        certified_request_ids=frozenset(row["request_item_id"] for row in campaign["attempts"]),
        attempts=shape_attempts, now=now,
    )
    preflight = {
        "preflight_status": "PASSED", "checked_at": now.isoformat(),
        "baseline_manifest_sha256": baseline_manifest_sha,
        "baseline_lock_sha256": _sha(paths["lock"].read_bytes()),
        "campaign_manifest_sha256": _sha(campaign_raw),
        "candidate_inventory_sha256": candidate_hash,
        "deterministic_context_readiness": context["readiness"],
        "deterministic_context_proposition_items": 106,
        "deterministic_context_coverage_states": 105,
        "frozen_requests": {"count": 5, "hashes_unchanged": True, "order_unchanged": True},
        "source_rights_revalidation": {"status": "authorized", "exact_representations": len(rights_rows), "items": rights_rows,
            "rights_lineage_sha256": _sha(lineage_raw), "acquisition_lineage_verified": True},
        "owner_attestation": {
            "attested_by": "Greg", "setting": "Share inputs and outputs with OpenAI",
            "observed_value": "Disabled", "attested_at": now.isoformat(),
            "evidence_type": "fresh owner attestation in the current campaign authorization handoff",
            "provider_calls": 0,
        },
        "provider_data_policy": {"policy_id": OPENAI_PROVIDER_POLICY_ID,
            "official_source": "https://openai.com/business-data/",
            "checked_at": now.isoformat(), "no_training_by_default": True},
        "pricing": {"model": "gpt-5.6-luna", "input_usd_per_million": "0.20",
            "cached_input_usd_per_million": "0.02", "cache_write_usd_per_million": "0.25",
            "output_usd_per_million": "1.20", "source_url": OPENAI_PRICE_URL,
            "checked_at": now.isoformat(), "reserved_input_rate": "0.25"},
        "fx": {"rba_observation_date": "2026-09-11", "usd_per_aud": str(FX_OBSERVED_USD_PER_AUD),
            "aud_per_usd_used": str(FX_AUD_PER_USD), "rounding": "rounded upward",
            "source_url": RBA_FX_URL, "checked_at": now.isoformat()},
        "reservation": {"per_request_aud": [str(v) for v in per_attempt_exposures],
            "total_aud": str(total_reserve), "per_attempt_cap_aud": str(MAX_ATTEMPT_AUD),
            "five_request_cap_aud": str(MAX_FIVE_REQUEST_RESERVATION_AUD),
            "aggregate_campaign_cap_aud": "2.00", "unused_budget_reusable": False},
        "transport": {"provider": "OpenAI", "endpoint": OpenAIHTTPStandardClient.base_url,
            "model": "gpt-5.6-luna", "reasoning": "low", "delivery": "Standard",
            "timeout_seconds": 300, "sequential": True, "automatic_retries": 0,
            "physical_attempt_maximum": 1, "client_request_ids_unique": True,
            "api_key_present": True, "proxy_configuration": _proxy_inventory(), "canary": False},
        "acnc_current_terms_review": {"copyright_url": ACNC_COPYRIGHT_URL,
            "checked_at": now.isoformat(),
            "finding": "ACNC states its CC BY material excludes third-party content; this campaign continues to rely on the already approved exact-hash Fair Dealing decisions for the ten bound representations. No source content was reacquired."},
        "source_acquisitions": 0,
        "execution_attempts": attempt_rows,
    }
    return preflight, {"paths": paths, "campaign": campaign, "attempts": attempt_rows,
                       "source_metadata": metadata_rows, "total_reserve": total_reserve,
                       "provider_attestation": provider_attestation}


def _source_tasks(builder: Path, data: Path, campaign: dict[str, Any]) -> dict[str, dict[str, Any]]:
    paths = _paths(builder, data)
    metadata = _json(paths["source_metadata"])["sources"]
    by_artifact = {row["source_artifact_id"]: row for row in metadata}
    task_map: dict[str, dict[str, Any]] = {}
    for row in campaign["attempts"]:
        sources = []
        for rights in row["source_rights"]:
            meta = by_artifact[rights["source_artifact_id"]]
            text = (paths["packet"] / meta["representation_path"]).read_text(encoding="utf-8")
            sources.append({
                "source_artifact_id": meta["source_artifact_id"],
                "source_record_id": meta["source_record_id"],
                "source_role": meta["source_role"], "source_locator": meta["source_locator"],
                "evidence_locator_id": meta["evidence_locator_id"],
                "evidence_representation_sha256": meta["representation_sha256"],
                "source_date": None, "retrieved_at": None,
                "exact_transmitted_representation": text,
            })
        task_map[row["request_item_id"]] = {
            "slice_id": row["slice_id"], "subject_id": row["subject_id"],
            "subject_name": row["subject_name"], "sources": sources,
            "allowed_scope_ids": [row["allowed_scope"]],
            "allowed_locators": list(row["allowed_locators"]),
        }
    return task_map


def _human_packet(row: dict[str, Any], output: Any, task: dict[str, Any], response_meta: dict[str, Any],
                  existing_coverage: list[dict[str, Any]]) -> dict[str, Any]:
    source_by_locator = {source["evidence_locator_id"]: source for source in task["sources"]}
    propositions = []
    for index, proposition in enumerate(output.propositions, start=1):
        value = proposition.model_dump(mode="json")
        evidence = []
        for ref in value.get("evidence", []):
            source = source_by_locator.get(ref.get("locator_id"))
            evidence.append({
                **ref,
                "source_artifact_id": source["source_artifact_id"] if source else None,
                "source_record_id": source["source_record_id"] if source else None,
                "source_carrier_role": source["source_role"] if source else None,
                "representation_sha256": source["evidence_representation_sha256"] if source else None,
                "private_supporting_snippet": source["exact_transmitted_representation"] if source else None,
            })
        value["evidence"] = evidence
        candidate_hash = _sha(_canonical(value))
        propositions.append({
            "candidate_id": f"candidate:semantic:{row['request_item_id'].split(':', 1)[-1]}:{index:03d}",
            "candidate_content_sha256": candidate_hash,
            "proposition": value,
            "human_review": {
                "adjudicator_role": "HUMAN_ADJUDICATOR",
                "disposition": None,
                "allowed_dispositions": ["ACCEPT", "ACCEPT_MINOR_CORRECTION", "REJECT_UNSUPPORTED", "REJECT_INCORRECT", "REJECT_SCOPE", "REJECT_EPISTEMIC_CLASS", "REJECT_MISSINGNESS", "MECHANICALLY_UNRESOLVED", "CRITICAL"],
                "corrected_representation": None,
                "rationale": None,
            },
        })
    cues = (
        ["reach vs outcome", "output vs outcome", "observation basis", "first-party measure vs independent evaluation", "contribution vs causal attribution", "causal evidence", "evaluator", "method", "comparator/counterfactual", "limitations"]
        if row["slice_id"] == "outcomes" else
        ["commitment", "self-reported implementation", "independent verification", "implementation outcome", "evidence of non-implementation", "reporting period", "activity underway vs completion"]
    )
    return {
        "packet_status": "READY_FOR_HUMAN_ADJUDICATION",
        "candidate_status": "CANDIDATES_ONLY_NOT_GOVERNED",
        "request_item_id": row["request_item_id"], "physical_attempt_id": row["physical_attempt_id"],
        "client_request_id": row["client_request_id"], "server_request_id": response_meta.get("server_request_id"),
        "request_body_sha256": row["request_body_sha256"],
        "response_body_sha256": response_meta["response_body_sha256"],
        "contract_version": row["contract_version"], "subject": row["subject"],
        "subject_id": row["subject_id"], "scope": row["allowed_scope"],
        "proposition_count": len(propositions), "propositions": propositions,
        "deterministic_context_coverage": existing_coverage,
        "model_coverage_items": 0,
        "mechanical_validation": "MECHANICAL_PASS",
        "human_review_cues": cues,
        "source_lineage": [{
            "source_artifact_id": source["source_artifact_id"],
            "source_record_id": source["source_record_id"], "source_role": source["source_role"],
            "representation_sha256": source["evidence_representation_sha256"],
            "evidence_locator_id": source["evidence_locator_id"],
            "acquisition_lineage_ids": next(x["source_rights"][i]["acquisition_lineage_ids"]
                for x in [row] for i in range(len(x["source_rights"]))
                if x["source_rights"][i]["source_artifact_id"] == source["source_artifact_id"]),
        } for source in task["sources"]],
        "provider_model": response_meta["provider_model"],
        "human_dispositions_prefilled": False,
    }


def execute(builder: Path, data: Path) -> dict[str, Any]:
    now = _now()
    preflight, prepared = _preflight(builder, data, now)
    paths = prepared["paths"]
    # Resolve every locally retained source task before creating a send ledger.
    # Any local task-construction problem therefore fails with zero crossings.
    tasks = _source_tasks(builder, data, prepared["campaign"])
    run_dir: Path = paths["execution"]
    run_dir.mkdir(parents=False, exist_ok=False)
    attestation = preflight["owner_attestation"]
    _write_atomic(run_dir / "preflight.json", _canonical(preflight) + b"\n")
    _write_atomic(run_dir / "provider-policy-attestation.json", _canonical(attestation) + b"\n")
    manifest = {
        "run_id": RUN_ID, "status": "EXECUTING", "created_at": now.isoformat(),
        "source_execution_manifest_sha256": preflight["campaign_manifest_sha256"],
        "provider_model": "gpt-5.6-luna", "reasoning_effort": "low", "delivery": "Standard",
        "execution_authorized_by": "Greg", "maximum_physical_attempts": 5,
        "automatic_retries": 0, "manual_retries": 0, "source_acquisitions": 0,
        "semantic_governed_promotions": 0, "provider_calls": 0,
        "attempts": prepared["attempts"],
    }
    _write_atomic(run_dir / "execution-manifest.json", _canonical(manifest) + b"\n")
    _write_atomic(run_dir / "execution-results.json", _canonical({
        "run_id": RUN_ID, "campaign_state": "EXECUTING", "results": [],
        "provider_calls": 0, "source_acquisitions": 0, "semantic_governed_promotions": 0,
    }) + b"\n")

    paths["responses"] = run_dir / "responses"
    paths["attempts_dir"] = run_dir / "attempts"
    paths["candidate_packets"] = run_dir / "human-adjudication-packet"
    for key in ("responses", "attempts_dir", "candidate_packets"):
        paths[key].mkdir()
    tasks = _source_tasks(builder, data, prepared["campaign"])
    governed = _json(paths["adjudicated"] / "governed-items.json")
    context_by_subject: dict[str, list[dict[str, Any]]] = {}
    for coverage in governed["coverage_items"]:
        context_by_subject.setdefault(coverage["subject_id"], []).append({
            "item_id": coverage["item_id"], "coverage_state": coverage["coverage_state"],
            "coverage_proposition_type": coverage["governed_proposition_type"],
            "reviewed_evidence_universe_id": coverage["reviewed_evidence_universe_id"],
        })

    client = OpenAIHTTPStandardClient()
    results: list[dict[str, Any]] = []
    candidates_total = 0
    stopped = False

    def persist_results() -> None:
        result_doc = {
            "run_id": RUN_ID,
            "campaign_state": "EXECUTING",
            "results": results,
            "provider_calls": sum(item.get("provider_posts", 0) for item in results),
            "local_transport_invocations": sum(1 for item in results if item.get("local_transport_invoked")),
            "source_acquisitions": 0,
            "semantic_governed_promotions": 0,
            "candidate_propositions": candidates_total,
            "known_actual_usd": str(sum((Decimal(item["actual_cost_usd"]) for item in results if item.get("actual_cost_usd") is not None), Decimal("0"))),
            "known_actual_aud": str(sum((Decimal(item["actual_cost_aud"]) for item in results if item.get("actual_cost_aud") is not None), Decimal("0"))),
            "conservative_reserved_exposure_aud": str(prepared["total_reserve"]),
            "conservative_exposure_incurred_aud": str(sum((Decimal(item["conservative_reserved_exposure_aud"]) for item in results if item.get("provider_posts", 0)), Decimal("0"))),
            "unattempted": sum(1 for item in results if item.get("provider_posts", 0) == 0),
        }
        _write_atomic(run_dir / "execution-results.json", _canonical(result_doc) + b"\n")

    for index, row in enumerate(prepared["attempts"], start=1):
        if stopped:
            results.append({"subject": row["subject"], "status": "NO_ATTEMPT_DUE_CAMPAIGN_STOP", "provider_posts": 0})
            persist_results()
            continue
        body_path = paths["requests"] / f"{row['abn']}.json"
        raw_body = body_path.read_bytes()
        body = json.loads(raw_body.decode("utf-8"))
        if _sha(canonical_standard_body_bytes(body)) != row["request_body_sha256"]:
            results.append({"subject": row["subject"], "status": "NO_ATTEMPT_DUE_CAMPAIGN_STOP", "provider_posts": 0, "stop_reason": "frozen request changed before send"})
            stopped = True
            persist_results()
            continue
        started = _now()
        row["status"] = "PHYSICAL_ATTEMPT_STARTED"
        row["provider_posts"] = 1
        row["request_started_at"] = started.isoformat()
        manifest["provider_calls"] += 1
        manifest["attempts"][index - 1] = row
        _write_atomic(run_dir / "execution-manifest.json", _canonical(manifest) + b"\n")
        start_record = {
            "status": "PHYSICAL_ATTEMPT_STARTED", "provider_posts": 1,
            "subject": row["subject"], "request_item_id": row["request_item_id"],
            "physical_attempt_id": row["physical_attempt_id"],
            "client_request_id": row["client_request_id"],
            "request_body_sha256": row["request_body_sha256"],
            "request_started_at": started.isoformat(),
            "maximum_conservative_exposure_aud": row["conservative_reserved_exposure_aud"],
        }
        results.append({"subject": row["subject"], "contract": row["contract_version"],
            "status": "PHYSICAL_ATTEMPT_STARTED", "provider_posts": 1,
            "local_transport_invoked": True,
            "client_request_id": row["client_request_id"], "model": row["model"],
            "conservative_reserved_exposure_aud": row["conservative_reserved_exposure_aud"]})
        persist_results()
        _write_atomic(paths["attempts_dir"] / f"{index:02d}-attempt.json", _canonical(start_record) + b"\n")
        with (run_dir / "transport-audit.jsonl").open("ab") as audit:
            audit.write(_canonical({"event": "one_shot_transport_invoked", **start_record}) + b"\n")
            audit.flush()
            os.fsync(audit.fileno())
        try:
            response = client.create_response_once(raw_body, client_request_id=row["client_request_id"], request_started_at=started.isoformat())
        except StandardTransportError as exc:
            is_ambiguous = exc.ambiguous
            state = "AMBIGUOUS_PHYSICAL_ATTEMPT" if is_ambiguous else "MECHANICAL_FAIL"
            provider_posts = 1 if is_ambiguous or exc.response_headers_received else 0
            response_hash = None
            if exc.raw_bytes is not None:
                response_path = paths["responses"] / f"{row['request_item_id'].split(':', 1)[-1]}.error.bin"
                _write_atomic(response_path, exc.raw_bytes)
                response_hash = _sha(exc.raw_bytes)
            detail = {
                **start_record, "status": state, "provider_posts": provider_posts,
                "server_request_id": exc.request_id,
                "http_status": exc.status_code, "response_headers_received": exc.response_headers_received,
                "transport_state": exc.transport_state, "exception_type": exc.exception_type,
                "cause_type": exc.cause_type, "error_number": exc.error_number,
                "exception": str(exc), "raw_error_body_sha256": response_hash,
                "elapsed_seconds": exc.elapsed_seconds,
            }
            _write_atomic(paths["attempts_dir"] / f"{index:02d}-attempt.json", _canonical(detail) + b"\n")
            row["status"] = state
            row["provider_posts"] = provider_posts
            row["transport_state"] = exc.transport_state
            manifest["attempts"][index - 1] = row
            manifest["provider_calls"] = sum(item["provider_posts"] for item in manifest["attempts"])
            _write_atomic(run_dir / "execution-manifest.json", _canonical(manifest) + b"\n")
            results[-1].update({"subject": row["subject"], "contract": row["contract_version"],
                "status": state, "provider_posts": provider_posts, "client_request_id": row["client_request_id"],
                "local_transport_invoked": True,
                "provider_boundary_crossed": bool(provider_posts), "mechanical_validation": state,
                "server_request_id": exc.request_id, "error": str(exc),
                "transport_state": exc.transport_state, "http_status": exc.status_code,
                "response_headers_received": exc.response_headers_received,
                "conservative_reserved_exposure_aud": row["conservative_reserved_exposure_aud"]})
            stopped = True
            persist_results()
            continue
        except Exception as exc:
            detail = {
                **start_record, "status": "AMBIGUOUS_PHYSICAL_ATTEMPT",
                "exception_type": type(exc).__name__,
                "cause_type": type(exc.__cause__).__name__ if exc.__cause__ else None,
                "exception": f"{type(exc).__name__}: {exc}"[:1000],
                "response_headers_received": False,
            }
            _write_atomic(paths["attempts_dir"] / f"{index:02d}-attempt.json", _canonical(detail) + b"\n")
            row["status"] = "AMBIGUOUS_PHYSICAL_ATTEMPT"
            row["provider_posts"] = 1
            manifest["attempts"][index - 1] = row
            _write_atomic(run_dir / "execution-manifest.json", _canonical(manifest) + b"\n")
            results[-1].update({"subject": row["subject"], "contract": row["contract_version"],
                "status": "AMBIGUOUS_PHYSICAL_ATTEMPT", "provider_posts": 1,
                "local_transport_invoked": True,
                "client_request_id": row["client_request_id"], "error": detail["exception"],
                "server_request_id": None, "transport_state": "TRANSPORT_PHASE_UNKNOWN",
                "conservative_reserved_exposure_aud": row["conservative_reserved_exposure_aud"]})
            stopped = True
            persist_results()
            continue

        raw_response = response.raw_bytes
        response_path = paths["responses"] / f"{row['request_item_id'].split(':', 1)[-1]}.json"
        _write_atomic(response_path, raw_response)
        usage = response.body.get("usage") or {}
        try:
            actual_usd, actual_aud = standard_actual_cost(usage, FX_AUD_PER_USD, model="gpt-5.6-luna")
            cost_error = None
        except Exception as exc:
            actual_usd = actual_aud = None
            cost_error = f"{type(exc).__name__}: {exc}"[:512]
        parsed = None
        validation_error = None
        try:
            if not 200 <= response.status_code < 300 or response.body.get("status") != "completed" or response.body.get("incomplete_details") is not None:
                raise ValueError("Responses object was not completed")
            if response.body.get("model") != "gpt-5.6-luna":
                raise ValueError("provider returned a model identity different from pinned Luna")
            output_text = _output_text(response.body)
            if not output_text:
                raise ValueError("completed response contained no structured output text")
            packet = json.loads(output_text)
            validation_row = {
                "slice_id": row["slice_id"], "subject_id": row["subject_id"],
                "allowed_scope": row["allowed_scope"], "allowed_locators": row["allowed_locators"],
                "source_metadata": [{
                    "evidence_locator_id": s["evidence_locator_id"], "source_role": s["source_role"],
                    "source_date": None, "retrieved_at": None,
                } for s in tasks[row["request_item_id"]]["sources"]],
                "source_texts": [s["exact_transmitted_representation"] for s in tasks[row["request_item_id"]]["sources"]],
            }
            if row["contract_version"] == "phase6-corrected-contracts-v6":
                parsed = _validate_v6_packet(validation_row, tasks[row["request_item_id"]], packet)
            else:
                parsed = _validate_v5_response(validation_row, tasks[row["request_item_id"]], packet)
        except Exception as exc:
            validation_error = f"{type(exc).__name__}: {exc}"[:1200]

        state = "MECHANICAL_PASS" if parsed is not None else "MECHANICAL_FAIL"
        response_meta = {
            "status": state, "http_status": response.status_code,
            "response_id": response.body.get("id"), "server_request_id": response.server_request_id,
            "provider_model": response.body.get("model"),
            "response_headers_received": response.response_headers_received,
            "request_started_at": response.request_started_at or started.isoformat(),
            "elapsed_seconds": response.elapsed_seconds,
            "response_body_sha256": _sha(raw_response),
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
            "usage": usage, "actual_cost_usd": str(actual_usd) if actual_usd is not None else None,
            "actual_cost_aud": str(actual_aud) if actual_aud is not None else None,
            "cost_error": cost_error, "mechanical_validation": state,
            "validation_error": validation_error,
            "conservative_reserved_exposure_aud": row["conservative_reserved_exposure_aud"],
        }
        _write_atomic(paths["attempts_dir"] / f"{index:02d}-attempt.json", _canonical({**start_record, **response_meta}) + b"\n")
        result = {
            "subject": row["subject"], "contract": row["contract_version"],
            "status": state, "provider_posts": 1,
            "client_request_id": row["client_request_id"],
            "server_request_id": response.server_request_id,
            "model": response.body.get("model"),
            "mechanical_validation": state,
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
            "actual_cost_usd": response_meta["actual_cost_usd"],
            "actual_cost_aud": response_meta["actual_cost_aud"],
            "conservative_reserved_exposure_aud": row["conservative_reserved_exposure_aud"],
            "proposition_count": len(parsed.propositions) if parsed is not None else 0,
            "response_body_sha256": response_meta["response_body_sha256"],
            "validation_error": validation_error,
        }
        if parsed is not None:
            coverage = context_by_subject.get(row["subject_id"], [])
            packet_record = _human_packet(row, parsed, tasks[row["request_item_id"]], response_meta, coverage)
            _write_atomic(paths["candidate_packets"] / f"{index:02d}-{row['abn']}.json", _canonical(packet_record) + b"\n")
            candidates_total += len(parsed.propositions)
        results[-1].update(result)
        if state != "MECHANICAL_PASS" or cost_error is not None or (actual_aud is not None and Decimal(actual_aud) > Decimal(row["conservative_reserved_exposure_aud"])):
            stopped = True
        persist_results()

    if not (run_dir / "execution-results.json").exists():
        raise RuntimeError("execution result ledger was not persisted")
    final = _json(run_dir / "execution-results.json")
    if len(results) == 5 and all(item.get("mechanical_validation") == "MECHANICAL_PASS" for item in results):
        final["campaign_state"] = "SEMANTIC_CANDIDATES_READY_FOR_HUMAN_ADJUDICATION"
    elif any(item.get("status") == "AMBIGUOUS_PHYSICAL_ATTEMPT" for item in results):
        final["campaign_state"] = "AMBIGUOUS_PHYSICAL_ATTEMPT_CAMPAIGN_STOPPED"
    elif any(item.get("transport_state") for item in results):
        final["campaign_state"] = "TRANSPORT_FAILURE_CAMPAIGN_STOPPED"
    elif any(item.get("mechanical_validation") == "MECHANICAL_FAIL" for item in results):
        final["campaign_state"] = "MECHANICAL_FAILURE_CAMPAIGN_STOPPED"
    elif any(item.get("provider_posts", 0) for item in results):
        final["campaign_state"] = "TRANSPORT_FAILURE_CAMPAIGN_STOPPED"
    else:
        final["campaign_state"] = "CAMPAIGN_STOPPED_BEFORE_PROVIDER_CROSSING"
    final["human_adjudications"] = 0
    final["semantic_governed_promotions"] = 0
    final["viewer_changes"] = 0
    final["public_v0_5_changes"] = 0
    _write_atomic(run_dir / "execution-results.json", _canonical(final) + b"\n")
    if final["campaign_state"] == "SEMANTIC_CANDIDATES_READY_FOR_HUMAN_ADJUDICATION":
        _write_atomic(run_dir / "human-adjudication-packet" / "README.md", (
            "# Private product-value semantic adjudication packet\n\n"
            "Five completed responses passed their frozen V6/V5 mechanical contracts. "
            "Each proposition has a blank human disposition, blank correction and blank rationale. "
            "Raw provider responses and bounded evidence text are local private work data. "
            "No human adjudication or governed promotion has occurred.\n"
        ).encode("utf-8"))
    manifest["status"] = final["campaign_state"]
    manifest["completed_at"] = _now().isoformat()
    manifest["candidate_propositions"] = candidates_total
    _write_atomic(run_dir / "execution-manifest.json", _canonical(manifest) + b"\n")
    return final


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    data = repo.parent / "charitygraph-data"
    result = execute(repo, data)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
