from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
import json
import re

import pytest

from charitygraph.llm_semantic_economics import (
    EvidenceBundle,
    RichSemanticOutput,
    SemanticProposal,
    SourceDocument,
    SpikeRunConfig,
    build_evidence_bundle,
    build_fx_snapshot,
    build_pricing_snapshot,
    build_model_task,
    parse_document,
    run_spike,
    ApiResult,
    ApiUsage,
    semantic_prompt,
    validate_output,
    rich_semantic_output_schema,
    rich_semantic_output_text_format,
    HUMAN_GOLD_DISPOSITIONS,
    score_human_gold,
)
from charitygraph.reality_slice1 import development_members
from charitygraph.contracts.economics import PriceRate


def _walk_schema(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_schema(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_schema(value)


def test_strict_wire_schema_is_exact_provider_schema():
    schema = rich_semantic_output_schema()
    assert rich_semantic_output_text_format()["schema"] == schema
    assert schema["type"] == "object"
    for node in _walk_schema(schema):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
        if node.get("type") == "array":
            assert node["type"] == "array"
    proposal = schema["$defs"]["SemanticProposal"]
    for field in ("durable", "parent_proposal_id", "description", "confidence", "competing_interpretation", "model_review_recommendation"):
        assert any(option.get("type") == "null" for option in proposal["properties"][field]["anyOf"])
    assert set(schema["required"]) == set(schema["properties"])

def _doc(url: str, text: str, digest: str = "a" * 64) -> SourceDocument:
    return SourceDocument(
        url=url,
        retrieved_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
        publisher="The Smith Family",
        content_hash=digest,
        artifact_id="srcblob:" + digest,
        media_type="text/html",
        byte_size=len(text),
        text=text,
    )


def test_parser_is_mechanical_and_does_not_classify_repeated_wording():
    text = parse_document(b"<h1>Mission</h1><p>program program</p><script>program</script>")
    assert text == "Mission\nprogram program"
    assert "semantic_outcome" not in text


def test_evidence_bundle_hash_and_selection_are_exact_and_deterministic():
    member = development_members()[0]
    docs = (_doc("https://example.test/a", "A"), _doc("https://example.test/b", "B", "b" * 64))
    one = build_evidence_bundle(member.subject_id, "broad", docs)
    two = build_evidence_bundle(member.subject_id, "broad", docs)
    assert one.bundle_hash == two.bundle_hash
    assert one.selection_hash == two.selection_hash
    assert [s.evidence_id for s in one.source_segments] == [s.evidence_id for s in two.source_segments]
    assert one.source_segments[0].content_hash == "a" * 64


def test_model_task_binds_every_input_to_bundle_hash_and_prompt_policy():
    member = development_members()[0]
    bundle = build_evidence_bundle(member.subject_id, "lean", (_doc("https://example.test", "delivered activity"),))
    task = build_model_task(member.subject_id, bundle, provider_id="openai", model_snapshot="gpt-5.6-luna")
    assert task.cache_key
    assert task.policy_refs[0].policy_id == "CG-D027"
    assert task.evidence_inputs[0].selection_hash == bundle.selection_hash
    assert bundle.evidence_content_hash in semantic_prompt(bundle, member.legal_current_name)


def test_unbound_model_evidence_is_rejected():
    member = development_members()[0]
    bundle = build_evidence_bundle(member.subject_id, "lean", (_doc("https://example.test", "evidence"),))
    output = RichSemanticOutput(
        programs=(SemanticProposal(proposal_id="p1", label="Example", kind="program", durable=None, parent_proposal_id=None, description=None, evidence_refs=("evidence:unknown",), aliases=(), confidence=None, competing_interpretation=None, model_review_recommendation=None),),
        services=(), projects=(), campaigns=(), organisational_units=(), activities=(), populations=(), geographies=(), sdg_alignments=(), assertions=(), classie_assignments=(), semantic_outcome="insufficient_evidence", blockers=(),
    )
    with pytest.raises(ValueError, match="unbound evidence"):
        validate_output(output, bundle)


def test_missing_evidence_refs_are_rejected():
    member = development_members()[0]
    bundle = build_evidence_bundle(member.subject_id, "lean", (_doc("https://example.test", "evidence"),))
    output = RichSemanticOutput(
        programs=(SemanticProposal(proposal_id="p1", label="Example", kind="program", durable=None, parent_proposal_id=None, description=None, evidence_refs=(), aliases=(), confidence=None, competing_interpretation=None, model_review_recommendation=None),),
        services=(), projects=(), campaigns=(), organisational_units=(), activities=(), populations=(), geographies=(), sdg_alignments=(), assertions=(), classie_assignments=(), semantic_outcome="insufficient_evidence", blockers=(),
    )
    with pytest.raises(ValueError, match="at least one evidence reference"):
        validate_output(output, bundle)

def test_fixture_run_is_seven_only_three_tiers_and_private(tmp_path: Path):
    def transport(url: str):
        return (f"<html><h1>Official</h1><p>Evidence for {url}</p></html>".encode(), "text/html")

    report = run_spike(SpikeRunConfig(runtime_root=str(tmp_path / "runtime")), transport=transport)
    assert report["development_abns"] == [m.abn for m in development_members()]
    assert report["holdout_firewall"]["enforced"] is True
    assert report["task_count"] == 21
    assert report["tiers"] == ["lean", "broad", "very_broad"]
    assert report["paid_execution"] is False
    assert report["human_review"]["denominator_current"] == 12
    assert report["human_review"]["model_output_is_not_gold"] is True
    assert report["human_review"]["required_distribution"] == {"The Smith Family": 4, "Australian Red Cross Society": 2, "Australian Communities Foundation Limited": 3, "The Fred Hollows Foundation": 3}

def test_fake_paid_path_reserves_before_call_and_reports_proposals(tmp_path: Path):
    calls = []
    pricing = build_pricing_snapshot(provider_id="fake", model_snapshot="fake-model", rates=(PriceRate(dimension="input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.20")), PriceRate(dimension="cached_input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.02")), PriceRate(dimension="output_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("1.20"))), source_content_hash="c" * 64, authoritative_source_url="https://pricing.example.test")
    fx = build_fx_snapshot(aud_per_usd=Decimal("1.50"), source_name="fixture", source_url="https://fx.example.test", source_content_hash="d" * 64)

    def transport(url: str):
        return (f"<html><h1>Official</h1><p>Delivered service for {url}</p></html>".encode(), "text/html")

    def provider(task, prompt):
        assert (tmp_path / "runtime" / "reality-slice1-llm-semantic-economics" / "ledger.sqlite3").is_file()
        calls.append(task.record_id)
        evidence_id = re.search(r"\[(evidence:[0-9a-f]+)\]", prompt).group(1)
        payload = {"programs": [{"proposal_id": "p1", "label": "Example service", "kind": "service", "durable": True, "parent_proposal_id": None, "description": None, "evidence_refs": [evidence_id], "model_review_recommendation": "required", "aliases": [], "confidence": None, "competing_interpretation": None}], "services": [], "projects": [], "campaigns": [], "organisational_units": [], "activities": [{"proposition": "delivered activity", "subject_proposal_id": None, "scope_kind": "organisation", "evidence_refs": [evidence_id], "confidence": None, "competing_interpretation": None}], "populations": [], "geographies": [], "sdg_alignments": [], "assertions": [], "classie_assignments": [], "semantic_outcome": "supported", "blockers": []}
        return ApiResult(response_id="fixture-response", model="fake-model", status="completed", output_text=json.dumps(payload), usage=ApiUsage(input_tokens=100, output_tokens=100, total_tokens=200))

    report = run_spike(SpikeRunConfig(runtime_root=str(tmp_path / "runtime"), provider_id="fake", model_snapshot="fake-model", execute_paid=True), transport=transport, pricing_snapshot=pricing, fx_snapshot=fx, provider_call=provider)
    assert len(calls) == report["unique_semantic_evidence_pack_count"] == 7
    assert report["task_count"] == 21
    assert sum(item["validation_status"] == "reused_exact_evidence_pack" for item in report["results"]) == 14
    assert report["human_review"]["proposed_durable_program_service_subjects"]
    row = report["human_review"]["proposed_durable_program_service_subjects"][0]
    assert row["model_recommendation"] == "required"
    assert row["review_status"] == "proposed"
    assert row["human_disposition"] is None
    assert report["human_review"]["denominator_current"] == 12
    assert report["ledger"]["budget_position"]["actual_spend_aud"] != "0"
    assert report["economics"]["aggregate"]["actual_cost_aud"] != "0"
    assert report["economics"]["aggregate"]["grounded_propositions"] > 0
    assert report["projected"]["max_reserved_output_tokens"] == 7 * 8000
    assert report["economics"]["aggregate"]["unresolved_count"] == 0
    assert report["economics"]["incremental_tier_yield"]
    assert report["pricing_snapshot"]["record_id"] == pricing.record_id
    assert report["fx_snapshot"]["record_id"] == fx.record_id
    assert report["holdout_firewall"]["holdout_model_tasks"] == 0
    assert Path(report["human_review_report"]).is_file()


def test_output_ceiling_and_model_prompt_hide_operational_tier():
    assert SpikeRunConfig(runtime_root="runtime").max_output_tokens == 8000
    member = development_members()[0]
    bundle = build_evidence_bundle(member.subject_id, "lean", (_doc("https://example.test", "evidence"),))
    prompt = semantic_prompt(bundle, member.legal_current_name)
    assert "evidence tier" not in prompt
    assert "lean evidence pack" not in prompt
    assert "broad evidence pack" not in prompt
    assert "very_broad evidence pack" not in prompt


def test_identical_evidence_content_hash_is_tier_independent():
    member = development_members()[0]
    docs = (_doc("https://example.test", "same evidence"),)
    lean = build_evidence_bundle(member.subject_id, "lean", docs)
    broad = build_evidence_bundle(member.subject_id, "broad", docs)
    assert lean.evidence_content_hash == broad.evidence_content_hash
    assert lean.bundle_id != broad.bundle_id


def test_genuinely_larger_evidence_pack_has_distinct_content_hash():
    member = development_members()[0]
    docs = (_doc("https://example.test", "x" * 17000),)
    lean = build_evidence_bundle(member.subject_id, "lean", docs)
    broad = build_evidence_bundle(member.subject_id, "broad", docs)
    assert len(lean.source_segments[0].text) < len(broad.source_segments[0].text)
    assert lean.evidence_content_hash != broad.evidence_content_hash


def test_larger_evidence_packs_are_independent_paid_calls(tmp_path: Path):
    calls = []
    pricing = build_pricing_snapshot(
        provider_id="fake",
        model_snapshot="fake-model",
        rates=(
            PriceRate(dimension="input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.20")),
            PriceRate(dimension="cached_input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.02")),
            PriceRate(dimension="output_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("1.20")),
        ),
        source_content_hash="e" * 64,
        authoritative_source_url="https://pricing.example.test",
    )
    fx = build_fx_snapshot(
        aud_per_usd=Decimal("1.3923698134"),
        source_name="fixture",
        source_url="https://fx.example.test",
        source_content_hash="f" * 64,
    )

    def transport(url: str):
        return (f"<html><h1>Official</h1><p>{'x' * 17000}</p></html>".encode(), "text/html")

    def provider(task, prompt):
        calls.append(task.record_id)
        evidence_id = re.search(r"\[(evidence:[0-9a-f]+)\]", prompt).group(1)
        payload = {"programs": [], "services": [], "projects": [], "campaigns": [], "organisational_units": [], "activities": [{"proposition": "activity", "subject_proposal_id": None, "scope_kind": "organisation", "evidence_refs": [evidence_id], "confidence": None, "competing_interpretation": None}], "populations": [], "geographies": [], "sdg_alignments": [], "assertions": [], "classie_assignments": [], "semantic_outcome": "supported", "blockers": []}
        return ApiResult(response_id="fixture-response", model="fake-model", status="completed", output_text=json.dumps(payload), usage=ApiUsage(input_tokens=100, output_tokens=100, total_tokens=200))

    report = run_spike(SpikeRunConfig(runtime_root=str(tmp_path / "runtime"), provider_id="fake", model_snapshot="fake-model", execute_paid=True), transport=transport, pricing_snapshot=pricing, fx_snapshot=fx, provider_call=provider)
    assert 7 < report["unique_semantic_evidence_pack_count"] <= report["task_count"] == 21
    assert len(calls) == report["unique_semantic_evidence_pack_count"]
    assert sum(item["validation_status"] == "reused_exact_evidence_pack" for item in report["results"]) == report["task_count"] - report["unique_semantic_evidence_pack_count"]


def test_paid_invalid_response_records_provider_cost_before_validation(tmp_path: Path):
    import sqlite3
    pricing = build_pricing_snapshot(
        provider_id="fake", model_snapshot="fake-model",
        rates=(
            PriceRate(dimension="input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.20")),
            PriceRate(dimension="cached_input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.02")),
            PriceRate(dimension="output_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("1.20")),
        ), source_content_hash="a" * 64, authoritative_source_url="https://pricing.example.test",
    )
    fx = build_fx_snapshot(aud_per_usd=Decimal("1.50"), source_name="fixture", source_url="https://fx.example.test", source_content_hash="b" * 64)

    def transport(url: str):
        return (f"<html><h1>Official</h1><p>Evidence for {url}</p></html>".encode(), "text/html")

    def invalid_provider(task, prompt):
        evidence_id = re.search(r"\[(evidence:[0-9a-f]+)\]", prompt).group(1)
        payload = {
            "programs": [{"proposal_id": "p1", "label": "Example", "kind": "program", "durable": True, "parent_proposal_id": None, "description": "x", "evidence_refs": [evidence_id], "aliases": [], "confidence": "high", "competing_interpretation": None, "model_review_recommendation": "required"}],
            "services": [], "projects": [], "campaigns": [], "organisational_units": [],
            "activities": [{"proposition": "activity", "subject_proposal_id": "missing-proposal", "scope_kind": "proposal", "evidence_refs": [evidence_id], "confidence": "high", "competing_interpretation": None}],
            "populations": [], "geographies": [], "sdg_alignments": [], "assertions": [], "classie_assignments": [],
            "semantic_outcome": "supported", "blockers": [],
        }
        return ApiResult(response_id="invalid-response", model="fake-model", status="completed", output_text=json.dumps(payload), usage=ApiUsage(input_tokens=123, output_tokens=45, total_tokens=168))

    report = run_spike(
        SpikeRunConfig(runtime_root=str(tmp_path / "runtime"), provider_id="fake", model_snapshot="fake-model", execute_paid=True),
        transport=transport, pricing_snapshot=pricing, fx_snapshot=fx, provider_call=invalid_provider,
    )
    assert report["run_lifecycle"]["run_status"] == "failed"
    assert report["results"][0]["validation_status"] == "invalid_output"
    assert report["results"][0]["usage"]["input_tokens"] == 123
    assert Decimal(report["ledger"]["budget_position"]["actual_spend_aud"]) > 0
    raw_ref = Path(report["results"][0]["raw_response_ref"])
    assert raw_ref.is_file()
    with sqlite3.connect(report["ledger"]["database"]) as conn:
        row = conn.execute("SELECT status, provider_request_id, usage_json, pricing_snapshot_id, fx_snapshot_id, result_artifact_id FROM task_attempts WHERE task_run_id=?", (report["results"][0]["task_run_id"],)).fetchone()
    assert row[0] == "failed_terminal"
    assert row[1] == "invalid-response"
    assert json.loads(row[2])["input_tokens"] == 123
    assert row[3] == pricing.record_id
    assert row[4] == fx.record_id
    assert row[5] == str(raw_ref)


def test_transient_retry_records_each_attempt_and_only_paid_response_cost(monkeypatch, tmp_path: Path):
    import sqlite3
    pricing = build_pricing_snapshot(
        provider_id="fake", model_snapshot="fake-model",
        rates=(
            PriceRate(dimension="input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.20")),
            PriceRate(dimension="cached_input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.02")),
            PriceRate(dimension="output_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("1.20")),
        ), source_content_hash="c" * 64, authoritative_source_url="https://pricing.example.test",
    )
    fx = build_fx_snapshot(aud_per_usd=Decimal("1.50"), source_name="fixture", source_url="https://fx.example.test", source_content_hash="d" * 64)

    def transport(url: str):
        return (f"<html><h1>Official</h1><p>Evidence for {url}</p></html>".encode(), "text/html")

    def retried_response(*, model, input_text, text_format, max_output_tokens, on_retry):
        on_retry(2, OpenAIRequestError("synthetic retry", status_code=429, retryable=True))
        evidence_id = re.search(r"\[(evidence:[0-9a-f]+)\]", input_text).group(1)
        payload = {"programs": [], "services": [], "projects": [], "campaigns": [], "organisational_units": [], "activities": [{"proposition": "activity", "subject_proposal_id": None, "scope_kind": "organisation", "evidence_refs": [evidence_id], "confidence": None, "competing_interpretation": None}], "populations": [], "geographies": [], "sdg_alignments": [], "assertions": [], "classie_assignments": [], "semantic_outcome": "supported", "blockers": []}
        return ApiResult(response_id="retry-response", model=model, status="completed", output_text=json.dumps(payload), usage=ApiUsage(input_tokens=100, output_tokens=20, total_tokens=120))

    monkeypatch.setattr("charitygraph.llm_semantic_economics.responses_create", retried_response)
    report = run_spike(SpikeRunConfig(runtime_root=str(tmp_path / "runtime"), provider_id="fake", model_snapshot="fake-model", execute_paid=True), transport=transport, pricing_snapshot=pricing, fx_snapshot=fx)
    assert report["run_lifecycle"]["run_status"] == "succeeded"
    with sqlite3.connect(report["ledger"]["database"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM task_attempts WHERE status='failed_retryable'").fetchone()[0] == report["unique_semantic_evidence_pack_count"]
        assert conn.execute("SELECT COUNT(*) FROM task_attempts WHERE status='succeeded'").fetchone()[0] == report["unique_semantic_evidence_pack_count"]
        assert conn.execute("SELECT COUNT(*) FROM cost_entries WHERE entry_type='actual'").fetchone()[0] == report["unique_semantic_evidence_pack_count"]
        assert conn.execute("SELECT COUNT(*) FROM task_attempts WHERE provider_request_id='retry-response' AND usage_json IS NOT NULL").fetchone()[0] == report["unique_semantic_evidence_pack_count"]

import sqlite3

from charitygraph.openai_client import OpenAIRequestError


def test_paid_run_twice_uses_distinct_execution_identity_and_preserves_history(tmp_path: Path):
    pricing = build_pricing_snapshot(
        provider_id="fake",
        model_snapshot="fake-model",
        rates=(
            PriceRate(dimension="input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.20")),
            PriceRate(dimension="cached_input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.02")),
            PriceRate(dimension="output_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("1.20")),
        ),
        source_content_hash="e" * 64,
        authoritative_source_url="https://pricing.example.test",
    )
    fx = build_fx_snapshot(
        aud_per_usd=Decimal("1.50"),
        source_name="fixture",
        source_url="https://fx.example.test",
        source_content_hash="f" * 64,
    )

    def transport(url: str):
        return (f"<html><h1>Official</h1><p>Evidence for {url}</p></html>".encode(), "text/html")

    def successful_provider(task, prompt):
        evidence_id = re.search(r"\[(evidence:[0-9a-f]+)\]", prompt).group(1)
        payload = {
            "programs": [],
            "services": [],
            "projects": [],
            "campaigns": [],
            "organisational_units": [],
            "activities": [{"proposition": "delivered activity", "subject_proposal_id": None, "scope_kind": "organisation", "evidence_refs": [evidence_id], "confidence": None, "competing_interpretation": None}],
            "populations": [],
            "geographies": [],
            "sdg_alignments": [],
            "assertions": [], "classie_assignments": [],
            "semantic_outcome": "supported",
            "blockers": [],
        }
        return ApiResult(response_id="run-twice-response", model="fake-model", status="completed", output_text=json.dumps(payload), usage=ApiUsage(input_tokens=100, output_tokens=100, total_tokens=200))

    root = tmp_path / "runtime"
    first = run_spike(
        SpikeRunConfig(runtime_root=str(root), provider_id="fake", model_snapshot="fake-model", execute_paid=True),
        transport=transport,
        pricing_snapshot=pricing,
        fx_snapshot=fx,
        provider_call=lambda task, prompt: (_ for _ in ()).throw(OpenAIRequestError("synthetic terminal failure", status_code=400, retryable=False)),
    )
    second = run_spike(
        SpikeRunConfig(runtime_root=str(root), provider_id="fake", model_snapshot="fake-model", execute_paid=True),
        transport=transport,
        pricing_snapshot=pricing,
        fx_snapshot=fx,
        provider_call=successful_provider,
    )

    first_lifecycle = first["run_lifecycle"]
    second_lifecycle = second["run_lifecycle"]
    assert first_lifecycle["run_status"] == "failed"
    assert second_lifecycle["run_status"] == "succeeded"
    assert first_lifecycle["run_id"] != second_lifecycle["run_id"]
    assert first_lifecycle["run_instance_id"] != second_lifecycle["run_instance_id"]
    assert first_lifecycle["logical_task_ids"] == second_lifecycle["logical_task_ids"]
    assert set(first_lifecycle["execution_task_ids"]).isdisjoint(second_lifecycle["execution_task_ids"])
    assert first_lifecycle["reservation_id"] != second_lifecycle["reservation_id"]
    assert Decimal(first["ledger"]["budget_position"]["actual_spend_aud"]) == 0
    assert Decimal(second["ledger"]["budget_position"]["actual_spend_aud"]) > 0
    assert first["ledger"]["new_reservation_position"]["outstanding"] == "0.000000"
    assert second["ledger"]["new_reservation_position"]["outstanding"] == "0.000000"

    db = root / "reality-slice1-llm-semantic-economics" / "ledger.sqlite3"
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cohorts").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM cost_entries WHERE entry_type='actual'").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM task_attempts WHERE status='failed_terminal'").fetchone()[0] >= 1
        assert conn.execute("SELECT COUNT(*) FROM task_attempts WHERE status='succeeded'").fetchone()[0] == second_lifecycle["logical_task_count"]


def test_correction_prompt_contains_model_boundary_and_sdg_policy():
    member = development_members()[0]
    bundle = build_evidence_bundle(member.subject_id, "lean", (_doc("https://example.test", "evidence"),))
    prompt = semantic_prompt(bundle, member.legal_current_name)
    assert "plural category" in prompt
    assert "proper name is not required" in prompt
    assert "need not mention SDGs" in prompt
    assert "Do not use keyword, regex or other lexical rules" in prompt
    assert "alignment distinct from impact" in prompt


def test_human_gold_dispositions_are_governed_and_scored():
    assert sum(value == "REQUIRED" for mapping in HUMAN_GOLD_DISPOSITIONS.values() for value in mapping.values()) >= 12
    result = {"charity": "The Smith Family", "output": {"programs": [{"proposal_id": "program:learning-for-life"}, {"proposal_id": "literacy-programs"}], "services": []}}
    score = score_human_gold([result])
    assert score["required_denominator"] == 12
    assert score["required_found"] == 1
    alias_score = score_human_gold([{"charity": "The Smith Family", "output": {"programs": [{"proposal_id": "program:learning-clubs"}], "services": []}}])
    assert alias_score["required_found"] == 1
    assert "The Smith Family:literacy-programs" in score["explicit_exclude_proposals"]
    assert score["zero_critical_scope_errors"] is False
